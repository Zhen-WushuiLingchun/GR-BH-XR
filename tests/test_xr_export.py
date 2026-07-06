import json
import math

import h5py
import numpy as np

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
    assert metadata["schema"] == "gr-bh-xr.task5.unity_texture_package.v1"
    assert metadata["screenConvention"]["textureOrigin"] == "bottom_left"
    assert metadata["unityBasisInBhCoordinates"]["rightBh"] == [0.0, -1.0, 0.0]

    unity_raw = np.fromfile(out_dir / "escape_dir_unity_rgba32f.bytes", dtype="<f4").reshape(
        (height, width, 4)
    )
    np.testing.assert_allclose(
        unity_raw[:, 1:, :3], np.full((height, width - 1, 3), [0.0, 0.0, 1.0]), atol=1.0e-7
    )
    np.testing.assert_allclose(unity_raw[:, 1:, 3], 1.0)
    np.testing.assert_allclose(unity_raw[:, 0, 3], 0.0)
