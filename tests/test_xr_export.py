import json
import math

import h5py
import numpy as np
import pytest

from gr_bh_xr.gpu.backend import select_vulkan_adapter
from gr_bh_xr.gpu.generate_lens_map import generate_gpu_lens_map
from gr_bh_xr.types import MetricParams
from gr_bh_xr.xr.export_unity_textures import (
    export_unity_texture_package,
    unity_basis_from_inclination,
)


def test_unity_basis_maps_positive_alpha_to_unity_right():
    basis = unity_basis_from_inclination(60.0)

    np.testing.assert_allclose(basis.forward_bh, [-math.sqrt(3.0) / 2.0, 0.0, -0.5])
    np.testing.assert_allclose(basis.right_bh, [0.0, -1.0, 0.0], atol=1.0e-15)
    assert abs(float(np.dot(basis.right_bh, basis.up_bh))) < 1.0e-15
    assert abs(float(np.dot(basis.right_bh, basis.forward_bh))) < 1.0e-15
    assert abs(float(np.dot(basis.up_bh, basis.forward_bh))) < 1.0e-15


def test_export_unity_texture_package_writes_raw_buffers_and_metadata(tmp_path):
    source = tmp_path / "gpu_lensmap.h5"
    out_dir = tmp_path / "unity_package"
    height = 2
    width = 3
    basis = unity_basis_from_inclination(60.0)
    forward = basis.forward_bh.astype(np.float32)

    with h5py.File(source, "w") as handle:
        handle.attrs["schema"] = "gr-bh-xr.phase2.gpu_lens_map.v2"
        handle.attrs["inclination_deg"] = 60.0
        handle.attrs["a"] = 0.5
        handle.attrs["M"] = 1.0
        handle.create_dataset("alpha", data=np.linspace(-1.0, 1.0, width))
        handle.create_dataset("beta", data=np.linspace(-2.0, 2.0, height))
        event = np.zeros((height, width), dtype=np.int16)
        event[:, 1:] = 1
        handle.create_dataset("gpu_event_code", data=event)
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        rgba[..., 3] = 255
        handle.create_dataset("event_rgba8", data=rgba)
        dirs = np.zeros((height, width, 3), dtype=np.float32)
        dirs[:, 1:, :] = forward
        handle.create_dataset("gpu_escape_dir_x", data=dirs[..., 0])
        handle.create_dataset("gpu_escape_dir_y", data=dirs[..., 1])
        handle.create_dataset("gpu_escape_dir_z", data=dirs[..., 2])

    summary = export_unity_texture_package(input_path=source, out_dir=out_dir, command="pytest")

    assert summary["width"] == width
    assert summary["height"] == height
    assert summary["escape_pixels"] == 4
    assert (out_dir / "event_rgba8.bytes").stat().st_size == width * height * 4
    assert (out_dir / "escape_dir_bh_rgba32f.bytes").stat().st_size == width * height * 16
    assert (out_dir / "escape_dir_unity_rgba32f.bytes").stat().st_size == width * height * 16
    assert (out_dir / "event_preview.png").read_bytes().startswith(b"\x89PNG")

    metadata = json.loads((out_dir / "lens_map_metadata.json").read_text(encoding="utf8"))
    assert metadata["schema"] == "gr-bh-xr.task5.unity_texture_package.v2"
    assert metadata["resolution"]["nativeTraceResolution"] is True
    assert metadata["screenConvention"]["textureOrigin"] == "bottom_left"
    assert metadata["screenConvention"]["verticalFlipApplied"] is True
    assert metadata["screenConvention"]["vToBeta"] == "beta = beta_max - v * (beta_max - beta_min)"
    assert metadata["unityBasisInBhCoordinates"]["rightBh"] == [0.0, -1.0, 0.0]

    unity_raw = np.fromfile(out_dir / "escape_dir_unity_rgba32f.bytes", dtype="<f4").reshape(
        (height, width, 4)
    )
    np.testing.assert_allclose(
        unity_raw[:, 1:, :3], np.full((height, width - 1, 3), [0.0, 0.0, 1.0]), atol=1.0e-7
    )
    np.testing.assert_allclose(unity_raw[:, 1:, 3], 1.0)
    np.testing.assert_allclose(unity_raw[:, 0, 3], 0.0)


def test_export_unity_texture_package_can_write_display_resampled_target_size(tmp_path):
    source = tmp_path / "gpu_lensmap.h5"
    out_dir = tmp_path / "unity_package_4k_style"
    height = 2
    width = 2
    target_size = 4
    basis = unity_basis_from_inclination(60.0)
    forward = basis.forward_bh.astype(np.float32)

    with h5py.File(source, "w") as handle:
        handle.attrs["schema"] = "gr-bh-xr.phase2.gpu_lens_map.v2"
        handle.attrs["inclination_deg"] = 60.0
        handle.create_dataset("alpha", data=np.linspace(-1.0, 1.0, width))
        handle.create_dataset("beta", data=np.linspace(-1.0, 1.0, height))
        handle.create_dataset("gpu_event_code", data=np.ones((height, width), dtype=np.int16))
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        rgba[..., 2] = 255
        rgba[..., 3] = 255
        handle.create_dataset("event_rgba8", data=rgba)
        dirs = np.broadcast_to(forward, (height, width, 3)).copy()
        handle.create_dataset("gpu_escape_dir_x", data=dirs[..., 0])
        handle.create_dataset("gpu_escape_dir_y", data=dirs[..., 1])
        handle.create_dataset("gpu_escape_dir_z", data=dirs[..., 2])

    summary = export_unity_texture_package(
        input_path=source,
        out_dir=out_dir,
        command="pytest target size",
        target_size=target_size,
    )

    assert summary["width"] == target_size
    assert summary["height"] == target_size
    assert summary["source_width"] == width
    assert summary["source_height"] == height
    assert (out_dir / "event_rgba8.bytes").stat().st_size == target_size * target_size * 4
    assert (out_dir / "escape_dir_unity_rgba32f.bytes").stat().st_size == (
        target_size * target_size * 16
    )

    metadata = json.loads((out_dir / "lens_map_metadata.json").read_text(encoding="utf8"))
    assert metadata["resolution"]["sourceWidth"] == width
    assert metadata["resolution"]["exportWidth"] == target_size
    assert metadata["resolution"]["nativeTraceResolution"] is False
    assert "display resample" in metadata["resolution"]["resampling"]

    unity_raw = np.fromfile(out_dir / "escape_dir_unity_rgba32f.bytes", dtype="<f4").reshape(
        (target_size, target_size, 4)
    )
    np.testing.assert_allclose(unity_raw[..., 3], 1.0)
    np.testing.assert_allclose(np.linalg.norm(unity_raw[..., :3], axis=-1), 1.0, atol=1.0e-6)


def test_export_flips_solver_beta_rows_so_texture_top_is_visual_up(tmp_path):
    source = tmp_path / "direction_signs.h5"
    out_dir = tmp_path / "unity_package"
    basis = unity_basis_from_inclination(60.0)
    alpha = np.asarray([-1.0, 0.0, 1.0])
    beta = np.asarray([-1.0, 0.0, 1.0])
    right = basis.right_bh
    up = basis.up_bh
    forward = basis.forward_bh
    dir_top_bh = _unity_to_bh(np.asarray([0.0, 0.25, 0.96824584]), right, up, forward)
    dir_bottom_bh = _unity_to_bh(np.asarray([0.0, -0.25, 0.96824584]), right, up, forward)
    dirs = np.zeros((3, 3, 3), dtype=np.float32)
    dirs[0, :, :] = dir_top_bh
    dirs[1, :, :] = forward
    dirs[2, :, :] = dir_bottom_bh

    with h5py.File(source, "w") as handle:
        handle.attrs["schema"] = "gr-bh-xr.phase2.gpu_lens_map.v2"
        handle.attrs["inclination_deg"] = 60.0
        handle.create_dataset("alpha", data=alpha)
        handle.create_dataset("beta", data=beta)
        handle.create_dataset("gpu_event_code", data=np.ones((3, 3), dtype=np.int16))
        handle.create_dataset("event_rgba8", data=np.zeros((3, 3, 4), dtype=np.uint8))
        handle.create_dataset("gpu_escape_dir_x", data=dirs[..., 0])
        handle.create_dataset("gpu_escape_dir_y", data=dirs[..., 1])
        handle.create_dataset("gpu_escape_dir_z", data=dirs[..., 2])

    export_unity_texture_package(input_path=source, out_dir=out_dir, command="pytest")

    unity_raw = np.fromfile(out_dir / "escape_dir_unity_rgba32f.bytes", dtype="<f4").reshape(
        (3, 3, 4)
    )
    assert unity_raw[2, 1, 1] > 0.0
    assert unity_raw[0, 1, 1] < 0.0


def test_weak_deflection_export_has_correct_unity_screen_handedness(tmp_path):
    pytest.importorskip("wgpu")
    try:
        select_vulkan_adapter()
    except RuntimeError as exc:
        pytest.skip(str(exc))

    h5_path = tmp_path / "weak_deflection_gpu.h5"
    out_dir = tmp_path / "unity_package"
    generate_gpu_lens_map(
        params=MetricParams(M=1.0, a=0.0),
        inclination_deg=60.0,
        grid=17,
        alpha_max=120.0,
        beta_max=120.0,
        r_obs=300.0,
        step_size=0.1,
        steps=12000,
        horizon_eps=0.3,
        critical_refine_band=0.0,
        out=h5_path,
        command="pytest weak deflection handedness",
    )
    export_unity_texture_package(input_path=h5_path, out_dir=out_dir, command="pytest")

    unity_raw = np.fromfile(out_dir / "escape_dir_unity_rgba32f.bytes", dtype="<f4").reshape(
        (17, 17, 4)
    )
    alpha_step = 15.0
    beta_step = 15.0
    col_pos = int(round((30.0 + 120.0) / alpha_step))
    col_neg = int(round((-30.0 + 120.0) / alpha_step))
    source_row_beta_pos = int(round((60.0 + 120.0) / beta_step))
    source_row_beta_neg = int(round((-60.0 + 120.0) / beta_step))
    row_visual_down = 16 - source_row_beta_pos
    row_visual_up = 16 - source_row_beta_neg

    assert unity_raw[row_visual_up, col_pos, 0] > 0.0
    assert unity_raw[row_visual_up, col_pos, 1] > 0.0
    assert unity_raw[row_visual_down, col_pos, 0] > 0.0
    assert unity_raw[row_visual_down, col_pos, 1] < 0.0
    assert unity_raw[row_visual_up, col_neg, 0] < 0.0
    assert unity_raw[row_visual_up, col_neg, 1] > 0.0


def _unity_to_bh(
    direction_unity: np.ndarray, right_bh: np.ndarray, up_bh: np.ndarray, forward_bh: np.ndarray
) -> np.ndarray:
    direction_unity = direction_unity / np.linalg.norm(direction_unity)
    direction_bh = (
        direction_unity[0] * right_bh
        + direction_unity[1] * up_bh
        + direction_unity[2] * forward_bh
    )
    return direction_bh / np.linalg.norm(direction_bh)
