import json
import math
import re
import importlib.util
import sys
from pathlib import Path

import h5py
import numpy as np
import pytest

from gr_bh_xr.gpu.backend import select_vulkan_adapter
from gr_bh_xr.gpu.generate_transfer_cubemap import (
    UNITY_CUBE_FACES,
    _face_directions,
    _premultiply_disk_samples,
    _validity_boundary_mask,
)
from gr_bh_xr.gpu.generate_lens_map import generate_gpu_lens_map
from gr_bh_xr.types import MetricParams
from gr_bh_xr.xr.export_unity_textures import (
    export_unity_texture_package,
    unity_basis_from_inclination,
)


UNITY_RUNTIME_DIR = Path(__file__).resolve().parents[1] / "xr" / "unity_frontend" / "Runtime"
UNITY_EDITOR_DIR = Path(__file__).resolve().parents[1] / "xr" / "unity_frontend" / "Editor"
COMPARE_LIVE_TRACER = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "quest_pcvr"
    / "scripts"
    / "compare_live_tracer.py"
)
PROTRACTOR_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "quest_pcvr"
    / "scripts"
    / "compare_protractor_gate.py"
)
PCVR_PREFLIGHT_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "quest_pcvr"
    / "scripts"
    / "quest_pcvr_preflight.ps1"
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
        handle.attrs["schema"] = "gr-bh-xr.phase2.gpu_lens_map.v3"
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
    assert metadata["schema"] == "gr-bh-xr.task5.unity_texture_package.v3"
    assert metadata["sourceEscapePixels"] == 4
    assert metadata["escapePixels"] == 4
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
        handle.attrs["schema"] = "gr-bh-xr.phase2.gpu_lens_map.v3"
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
    assert summary["source_escape_pixels"] == width * height
    assert summary["escape_pixels"] == target_size * target_size
    assert (out_dir / "event_rgba8.bytes").stat().st_size == target_size * target_size * 4
    assert (out_dir / "escape_dir_unity_rgba32f.bytes").stat().st_size == (
        target_size * target_size * 16
    )

    metadata = json.loads((out_dir / "lens_map_metadata.json").read_text(encoding="utf8"))
    assert metadata["resolution"]["sourceWidth"] == width
    assert metadata["resolution"]["exportWidth"] == target_size
    assert metadata["resolution"]["nativeTraceResolution"] is False
    assert metadata["sourceEscapePixels"] == width * height
    assert metadata["escapePixels"] == target_size * target_size
    assert "display resample" in metadata["resolution"]["resampling"]

    unity_raw = np.fromfile(out_dir / "escape_dir_unity_rgba32f.bytes", dtype="<f4").reshape(
        (target_size, target_size, 4)
    )
    np.testing.assert_allclose(unity_raw[..., 3], 1.0)
    np.testing.assert_allclose(np.linalg.norm(unity_raw[..., :3], axis=-1), 1.0, atol=1.0e-6)


def test_display_resample_marks_cancelled_direction_as_invalid(tmp_path):
    source = tmp_path / "cancelled_direction.h5"
    out_dir = tmp_path / "unity_package_cancelled"
    target_size = 3

    with h5py.File(source, "w") as handle:
        handle.attrs["schema"] = "gr-bh-xr.phase2.gpu_lens_map.v3"
        handle.attrs["inclination_deg"] = 90.0
        handle.create_dataset("alpha", data=np.asarray([-1.0, 1.0]))
        handle.create_dataset("beta", data=np.asarray([-1.0, 1.0]))
        handle.create_dataset("gpu_event_code", data=np.ones((2, 2), dtype=np.int16))
        rgba = np.zeros((2, 2, 4), dtype=np.uint8)
        rgba[..., 3] = 255
        handle.create_dataset("event_rgba8", data=rgba)
        dirs = np.asarray(
            [
                [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]],
                [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]],
            ],
            dtype=np.float32,
        )
        handle.create_dataset("gpu_escape_dir_x", data=dirs[..., 0])
        handle.create_dataset("gpu_escape_dir_y", data=dirs[..., 1])
        handle.create_dataset("gpu_escape_dir_z", data=dirs[..., 2])

    export_unity_texture_package(
        input_path=source,
        out_dir=out_dir,
        command="pytest cancelled direction",
        target_size=target_size,
    )

    unity_raw = np.fromfile(out_dir / "escape_dir_unity_rgba32f.bytes", dtype="<f4").reshape(
        (target_size, target_size, 4)
    )
    metadata = json.loads((out_dir / "lens_map_metadata.json").read_text(encoding="utf8"))
    assert metadata["sourceEscapePixels"] == 4
    assert metadata["escapePixels"] == 6
    assert np.all(np.isfinite(unity_raw))
    np.testing.assert_allclose(unity_raw[:, 1, :3], 0.0)
    np.testing.assert_allclose(unity_raw[:, 1, 3], 0.0)


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
        handle.attrs["schema"] = "gr-bh-xr.phase2.gpu_lens_map.v3"
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


def test_unity_preview_shader_has_screen_space_gate_and_world_space_sampling():
    shader = (UNITY_RUNTIME_DIR / "BlackHoleLensStaticPreview.shader").read_text(encoding="utf8")

    assert "unity_ObjectToWorld" in shader
    assert "_WorldSpaceCameraPos" in shader
    assert "_LensScreenBounds" in shader
    assert "_LensRObs" in shader
    assert "_UseAngularWindow" in shader
    assert "_UseFullSkyTransfer" in shader
    assert "_EscapeDirCube" in shader
    assert "_EventCube" in shader
    assert "_DiskOrder0Cube" in shader
    assert "_DiskOrder1Cube" in shader
    assert "_DiskOrder0RedshiftCube" in shader
    assert "_DiskOrder1RedshiftCube" in shader
    assert "_UseDiskCoverageTransfer" in shader
    assert "_DiskColorLut" in shader
    assert "_DiskRadialLut" in shader
    assert "_UseDiskColorLut" in shader
    assert "_DiskTemperatureScale" in shader
    assert "_DiskColorLutLogT" in shader
    assert "_DiskRadialLutBounds" in shader
    assert "_UseDiskTransfer" in shader
    assert "_DiskAuditMode" in shader
    assert "_DiskVisualMode" in shader
    assert "_DiskGPower" in shader
    assert "_ProbeMode" in shader
    assert "_LensWorldRight" in shader
    assert "_LensWorldUp" in shader
    assert "_LensWorldForward" in shader
    assert "#pragma multi_compile_instancing" in shader
    assert "UNITY_VERTEX_INPUT_INSTANCE_ID" in shader
    assert "UNITY_VERTEX_OUTPUT_STEREO" in shader
    assert "UNITY_SETUP_INSTANCE_ID(v)" in shader
    assert "UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o)" in shader
    assert "UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i)" in shader
    assert "ZWrite On" in shader
    assert "ComputeScreenPos" in shader
    assert "float2 screenUv = i.screenPos.xy" in shader
    assert "if (localRay.z > 1.0e-5)" in shader
    assert "float beta = -_LensRObs * localRay.y / localRay.z" in shader
    assert "abs(localRay.z)" not in shader
    assert "worldDirectionToLens(worldRay)" in shader
    assert "lensDirectionToWorld(dir.xyz)" in shader
    assert "if (_UseFullSkyTransfer > 0.5)" in shader
    assert "diskAuditColor" in shader
    assert "unpackDiskSample" in shader
    assert "coverage = saturate(transfer.w)" in shader
    assert "sampleDiskColorLut" in shader
    assert "sampleDiskRadialLut" in shader
    assert "diskVisualLayer" in shader
    assert "compositeDiskVisual" in shader
    assert "T_obs = g T_emit" in shader
    assert "g^4 weighting" in shader
    assert "texCUBE(_DiskOrder0Cube, localRay)" in shader
    assert "texCUBE(_DiskOrder1Cube, localRay)" in shader
    assert "texCUBE(_DiskOrder0RedshiftCube, localRay)" in shader
    assert "texCUBE(_DiskOrder1RedshiftCube, localRay)" in shader
    assert "texCUBE(_EscapeDirCube, localRay)" in shader
    assert "texCUBE(_EventCube, localRay)" in shader
    assert "fullSkyColor" in shader
    assert "smoothstep(0.0, 0.04, edgeDistance)" in shader
    assert "lerp(fullSkyColor, localColor, localWeight)" in shader
    assert "mul((float3x3)unity_ObjectToWorld, dir.xyz)" not in shader
    assert "mul((float3x3)unity_WorldToObject, worldRay)" not in shader
    assert "protractorProbe(worldDir)" in shader
    assert "sampleBackground(worldRay, worldRay, _SkyboxLodBias)" in shader
    assert "sampleBackground(worldDir, worldRay, _StrongLensLodBias)" in shader
    assert "texCUBEbias(_SkyboxCubemap" in shader


def test_unity_sky_chromatic_shift_contract():
    """Sky chromatic shift: per-pixel blackbody ratio on the LUT v2 alpha.

    The emitter model fits each sky texel's temperature from its own
    chromaticity (inverse Planck locus in the LUT alpha channel); the
    observed color is rgb * LUT(T*g)/LUT(T) with bolometric g^4 - exactly
    the identity at g=1, so the fit cannot distort the unshifted sky.
    """

    shader = (UNITY_RUNTIME_DIR / "BlackHoleLensStaticPreview.shader").read_text(encoding="utf8")
    assert "_UseSkyChromaticShift" in shader
    assert "float3 applySkyObserver(float3 rgb, float obsFactor)" in shader
    assert "float chroma = rgb.r / max(rgb.r + rgb.b, 1.0e-5)" in shader
    assert "tex2D(_DiskColorLut, float2(chroma, 0.5)).a" in shader
    assert "sampleDiskColorLut(tEmit * obsFactor)" in shader
    # Both sky paths (single set and blend macro) must route through it.
    assert shader.count("applySkyObserver(") >= 3
    # The old brightness-only boost must not survive anywhere.
    assert "skyColor.rgb * pow(min(skyObsFactor" not in shader


def test_unity_disk_lut_uses_producer_endpoint_row_coordinate():
    """The LUT consumer must honour the producer's published texel contract.

    `disk_spectrum.py` publishes `rgbCoordinateExact` / `radiusCoordinateExact`:
    row i of a `samples`-row LUT holds the value at s = i / (samples - 1), so
    the coordinate landing exactly on that row is
    `u = (s * (samples - 1) + 0.5) / samples`. Sampling with `u = s` is a
    half-texel offset - 0.72% in effective temperature at 256 rows and 0.027 M
    in radius (0.048 in normalized flux) at 512.

    The alpha channel is the deliberate exception: the producer already
    resamples it at texel centers of `u = R/(R+B)`, so a direct fetch is the
    correct consumer and applying the row correction there would be a bug.
    """

    shader = (UNITY_RUNTIME_DIR / "BlackHoleLensStaticPreview.shader").read_text(encoding="utf8")
    assert "float lutRowCoordinate(float s, float samples)" in shader
    assert "return (s * (samples - 1.0) + 0.5) / samples;" in shader
    # Both RGB consumers route through the correction...
    assert "tex2D(_DiskRadialLut, float2(lutRowCoordinate(s, _DiskRadialLutBounds.z), 0.5))" in shader
    assert "tex2D(_DiskColorLut, float2(lutRowCoordinate(s, _DiskColorLutLogT.z), 0.5)).rgb" in shader
    # ...and the uncorrected u = s form must not survive on either.
    assert "tex2D(_DiskRadialLut, float2(u, 0.5))" not in shader
    assert "tex2D(_DiskColorLut, float2(u, 0.5)).rgb" not in shader
    # The alpha fetch stays uncorrected, by contract.
    assert "tex2D(_DiskColorLut, float2(chroma, 0.5)).a" in shader

    # The row count has to actually reach the shader, or the correction is a
    # no-op that silently keeps the old mapping.
    tracer = (UNITY_RUNTIME_DIR / "BlackHoleLiveTracer.cs").read_text(encoding="utf8")
    assert "private const int RadialLutSamples = 512;" in tracer
    assert 'new Vector4((float)rIsco, (float)rOut, RadialLutSamples, 0.0f)' in tracer


def _shader_code_only(source: str) -> str:
    """Shader text with `//` line comments removed.

    Every pin below must match executable HLSL; a comment restating the
    convention must never be able to turn a test green.
    """

    return "\n".join(re.sub(r"//.*$", "", line) for line in source.splitlines())


def _cg_function_body(source: str, header: str) -> str:
    """Return the brace-balanced body that follows `header`."""

    start = source.index(header)
    open_brace = source.index("{", start)
    depth = 0
    for index in range(open_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace : index + 1]
    raise AssertionError(f"unbalanced braces after {header!r}")


def test_unity_package_metadata_describes_both_runtime_paths():
    """The shipped manifest is what a package consumer actually reads.

    It described this package as a "Static texture bridge" long after the live
    Kerr-Schild tracer landed, and declared `unity: 2022.3`, a generation that
    has never been tested against it.
    """

    root = Path(__file__).resolve().parents[1] / "xr" / "unity_frontend"
    manifest = json.loads((root / "package.json").read_text(encoding="utf8"))
    readme = (root / "README.md").read_text(encoding="utf8")

    description = manifest["description"]
    assert "Static texture bridge for physics-auditable Kerr lens maps." != description
    assert "static texture bridge" in description.lower()  # only as a denial
    assert "Not a static texture bridge" in description
    # Both paths must be distinguished, and the overclaim ruled out.
    assert "Kerr-Schild" in description
    assert "baked" in description.lower()
    assert "not a full-resolution per-eye per-frame solve" in description.lower()
    # Supported generation, with no unverified backward-compatibility claim.
    assert manifest["unity"] == "6000.0"

    assert "Unity PCVR Static Texture Bridge" not in readme
    assert "6000.0.76f1" in readme and "17.0.4" in readme and "1.17.1" in readme
    assert "85.0.0" in readme
    assert "No backward compatibility with earlier Unity generations" in readme
    # Task 10 stays explicitly pending.
    assert "unaccepted" in readme.lower()

    # Complete .meta coverage: an absent .meta means a per-clone random GUID.
    missing = [
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and path.suffix != ".meta" and not (path.parent / (path.name + ".meta")).exists()
    ]
    assert not missing, f"assets without a .meta: {missing}"
    for folder in ("Runtime", "Editor"):
        assert (root / f"{folder}.meta").exists(), folder
    guids = [
        line.split(":", 1)[1].strip()
        for path in root.rglob("*.meta")
        for line in path.read_text(encoding="utf8").splitlines()
        if line.startswith("guid:")
    ]
    assert len(guids) == len(set(guids)), "duplicate asset GUIDs"


def test_unity_disk_layer_weights_observed_radiance_exactly_once():
    """`F(r) g^p` must reach the frame buffer once, not squared.

    `diskVisualLayer` returns premultiplied radiance in `.rgb`
    (`color * observedWeight`) and EVERY compositor - full-sky cube,
    GRBHXR_ROAM_BLEND macro, live angular window, legacy 2D - adds
    `layer.rgb * layer.a`. When `.a` also carried `observedWeight` the
    rendered intensity was `F(r)^2 g^(2p)` (`F^2 g^8` on the documented LUT
    path), and `_DiskBrightness` / `_DiskSecondaryScale` were squared too,
    while docs/equations.md and the shader comment claim `F_norm g^4`.

    `.a` is the producer's sub-texel coverage times the `_DiskOpacity`
    display knob and nothing else.
    """

    shader = (UNITY_RUNTIME_DIR / "BlackHoleLensStaticPreview.shader").read_text(encoding="utf8")
    code = _shader_code_only(shader)
    layer = _cg_function_body(code, "fixed4 diskVisualLayer(")

    # observedWeight is built once and read once, by rgb:
    #   1: `float observedWeight = emissivity * pow(g, redshiftPower) ...`
    #   2: `observedWeight += hotSpot * ...`
    #   3: `... * observedWeight;` on the color line
    # A fourth occurrence means it leaked into a second channel, including
    # via an alias such as `float w = observedWeight;`.
    assert layer.count("observedWeight") == 3, layer
    assert "float observedWeight = emissivity * pow(g, redshiftPower)" in layer
    assert re.search(r"float3 color = lerp\(.*\) \* observedWeight;", layer), layer

    # The alpha channel is coverage/opacity only.
    alpha_statements = [
        line.strip() for line in layer.splitlines() if re.search(r"\bfloat\s+alpha\s*=", line)
    ]
    assert len(alpha_statements) == 1, alpha_statements
    alpha = alpha_statements[0]
    assert "observedWeight" not in alpha, alpha
    assert "emissivity" not in alpha and "pow(g" not in alpha, alpha
    assert "_DiskBrightness" not in alpha and "orderScale" not in alpha, alpha
    assert "_DiskOpacity" in alpha and "coverage" in alpha, alpha

    # Nothing outside the helper may re-apply a radiance weight, and all
    # paths must consume the layer through the same single multiplication.
    outside = code.replace(layer, "")
    assert "observedWeight" not in outside
    consumers = sorted(re.findall(r"(\w*[Ll]ayer\d)\.rgb\s*\*\s*\1\.a", code))
    assert consumers == [
        "layer0", "layer1",            # compositeDiskVisual: cube + legacy 2D
        "shadeLayer0", "shadeLayer1",  # GRBHXR_SHADE_SET: roam blend
        "winLayer0", "winLayer1",      # live angular window
    ], consumers
    # Every layer produced must be composited; no path may drop or re-scale one.
    assert code.count("diskVisualLayer(") == len(consumers) + 1  # +1 definition

    # Lock the convention the shader is held to.
    equations = (Path(__file__).resolve().parents[1] / "docs" / "equations.md").read_text(encoding="utf8")
    assert "baseline Unity LUT path: normalized F(r) times g^4" in equations


def test_unity_live_tracer_refine_and_resolution_contract():
    """Live tracer: limb-refine subray AA plus distance-adaptive resolution."""

    compute = (UNITY_RUNTIME_DIR / "BlackHoleLiveTracer.compute").read_text(encoding="utf8")
    assert "#pragma kernel RefineTexels" in compute
    assert "RWStructuredBuffer<uint> _EventMask" in compute
    assert "TraceOutputs TraceDirection(float3 d)" in compute
    # 3x3 subray grid with fractional escape coverage, premultiplied values,
    # and a genuine (not synthetic) representative escape direction.
    assert "for (int sub = 0; sub < 9; sub += 1)" in compute
    assert "float coverage = escCount * inv;" in compute
    assert "_OutEscapeDir[coord] = float4(rep * coverage, coverage);" in compute
    assert "_OutDisk0[coord] = disk0Sum * inv;" in compute
    # The main kernel keeps the packed view-priority face order; the refine
    # kernel walks the mask spatially (face-major).
    assert "int face = (_FaceOrderPacked >> (slot * 3)) & 7;" in compute
    assert "uint flat = face * pixelsPerFace + py * _FaceSize + px;" in compute
    assert "_EventMask[flat] = MaskOf(o);" in compute

    tracer = (UNITY_RUNTIME_DIR / "BlackHoleLiveTracer.cs").read_text(encoding="utf8")
    # Pin the declaration, not the bare identifier: a comment mentioning
    # "autoResolution" would satisfy a substring match.
    assert "[SerializeField] private bool autoResolution = true;" in tracer
    assert "private int AutoLadderSize(float radiusM)" in tracer
    assert "Mathf.Sqrt(27.0f) * mass" in tracer
    assert "EnsureSnapshotTextures(back, passFaceSize)" in tracer
    assert "EnsureEventMaskBuffer(passFaceSize)" in tracer
    assert "BindOutputs(refineKernel, snapshots[backIndex])" in tracer
    # HARD swap stays: exactly one complete solution on screen, never a blend.
    assert "(frontIndex, backIndex) = (backIndex, frontIndex);" in tracer
    assert "live_event_mask_u32.bytes" in tracer
    assert "live_escape_dir_refined_rgba32f.bytes" in tracer

    compare = COMPARE_LIVE_TRACER.read_text(encoding="utf8")
    assert "live_event_mask_u32.bytes" in compare
    assert "refineCoverageMeanDiff" in compare
    assert "nonLimbUntouched" in compare


def test_unity_live_window_contract():
    """Live angular window: headset-density strong-field map, never stale.

    The window shares the audited TraceDirection physics; only the texel ->
    direction map differs (inverse of the display shader's gnomonic window
    lookup). It is traced while stationary and displayed ONLY when its pass
    origin matches the displayed cube's - stale sharp data must never be
    composited with fresh data.
    """

    compute = (UNITY_RUNTIME_DIR / "BlackHoleLiveTracer.compute").read_text(encoding="utf8")
    assert "#pragma kernel TraceWindow" in compute
    assert "#pragma kernel RefineWindow" in compute
    assert "float3 WindowDirection(int px, int py)" in compute
    assert "normalize(float3(alpha / rObs, -beta / rObs, 1.0))" in compute
    assert "RWStructuredBuffer<uint> _WinEventMask" in compute

    tracer = (UNITY_RUNTIME_DIR / "BlackHoleLiveTracer.cs").read_text(encoding="utf8")
    assert "StepWindowPass" in tracer
    assert "windowDensityPxPerDeg" in tracer
    assert "_UseLiveWindow" in tracer
    assert "live_window_dir_rgba32f.bytes" in tracer
    # The staleness gate is inlined, so pin the actual comparison terms. A
    # pin on the unused `SameObserverState` helper would stay green if the
    # composite were reduced to `liveWindowEnabled && frontWindow.Valid` -
    # exactly the stale-composite bug the docstring warns about.
    assert "bool showWindow = liveWindowEnabled" in tracer
    for term in ("OriginR", "OriginTheta", "OriginAz", "OriginMass", "OriginSpin"):
        assert f"frontWindow.{term}" in tracer, term
    assert "frontWindow.OriginMass == front.OriginMass" in tracer
    assert "frontWindow.OriginSpin == front.OriginSpin" in tracer

    shader = (UNITY_RUNTIME_DIR / "BlackHoleLensStaticPreview.shader").read_text(encoding="utf8")
    assert "_UseLiveWindow" in shader
    assert "_WindowDisk0Tex" in shader
    assert "_WindowRedshift1Tex" in shader
    # Window shading must route sky through the chromatic observer path and
    # feather into the complete cube composite (one solution, two densities).
    assert "applySkyObserver(winSky.rgb, winObs)" in shader
    assert "lerp(cubeComposite, winColor, windowWeight)" in shader

    compare = COMPARE_LIVE_TRACER.read_text(encoding="utf8")
    assert "windowEventAgreement" in compare
    assert "windowHalfAlpha" in compare


def test_live_tracer_validity_is_hamiltonian_not_launch_radius():
    """The near-horizon darkening bug must be gone, not re-tuned.

    The kernel darkened an escaped ray when `minR < _HugMinR`, with
    `_HugMinR = r_+ + 0.05 M`. `minR` includes the LAUNCH radius, so every
    genuinely escaped ray of an observer at `r_obs < r_+ + 0.05 M` went dark.
    The accepted Task 8 default near-horizon frame sits at r = 1.4423 M -
    only 0.0064 M above the horizon - with a physically valid escape fraction
    of about 0.847, so that whole keyframe rendered black.

    The comparator MIRRORED the same rule, which is why the gate reported
    perfect agreement: two identical wrong implementations agree. Validity is
    now the Hamiltonian residual, which is first-principles, observer-radius
    independent and spin independent.
    """

    compute = (UNITY_RUNTIME_DIR / "BlackHoleLiveTracer.compute").read_text(encoding="utf8")
    tracer = (UNITY_RUNTIME_DIR / "BlackHoleLiveTracer.cs").read_text(encoding="utf8")
    compare = COMPARE_LIVE_TRACER.read_text(encoding="utf8")

    # The launch-radius and affine-length criteria are gone from the kernel.
    code = _shader_code_only(compute)
    assert "_HugMinR" not in code
    assert "_HugLambda" not in code
    assert "minR < _HugMinR" not in code
    # ...and from both C# paths.
    cs_code = "\n".join(
        line for line in tracer.splitlines() if not line.lstrip().startswith("//")
    )
    assert "_HugMinR" not in cs_code
    assert "_HugLambda" not in cs_code

    # Hamiltonian residual is computed, tracked, and used to reject.
    assert "float HamiltonianKs(StateKS s)" in compute
    assert "hMax = max(hMax, abs(HamiltonianKs(s)));" in code
    assert "o.hamiltonianRejected = (eventCode == 1) && (hMax > _HamiltonianMax);" in code
    assert "o.escaped = (eventCode == 1) && !o.hamiltonianRejected;" in code

    # The threshold is published, not restated on both sides.
    assert "[SerializeField] private float hamiltonianMax = 1.0e-2f;" in tracer
    assert r'\"hamiltonianMax\"' in tracer
    assert 'meta["hamiltonianMax"]' in compare

    # The comparator must NOT mirror the removed heuristics.
    assert 'meta["hugMinR"]' not in compare
    assert 'meta["hugLambda"]' not in compare
    assert 'result_dict["h_max_abs"] <= hamiltonian_max' in compare

    # Fail-closed floors taken from the accepted producer/validator.
    assert 'summary["excludedFraction"] <= 0.35' in compare
    assert 'summary["escapeFraction"] >= 0.25' in compare


def test_live_tracer_exposes_structured_event_classification():
    """Capture, numerical invalid, and budget exhaustion must stay distinct.

    The kernel collapsed all three into one dark `eventCode == 0`, so the
    scientific artifact could not tell a physically captured ray from one the
    integrator destroyed. The display may still render every non-escape class
    dark; the dump and comparator may not.
    """

    compute = (UNITY_RUNTIME_DIR / "BlackHoleLiveTracer.compute").read_text(encoding="utf8")
    tracer = (UNITY_RUNTIME_DIR / "BlackHoleLiveTracer.cs").read_text(encoding="utf8")
    compare = COMPARE_LIVE_TRACER.read_text(encoding="utf8")
    code = _shader_code_only(compute)

    # Raw codes survive to the outputs, matching gr_bh_xr.gpu.codes.
    for field in ("int eventCode;", "int failureCode;", "float hMaxAbs;", "float minR;", "float lambdaEnd;"):
        assert field in compute, field
    assert "int eventCode = 3;" in code            # EVENT_INVALID
    assert "int failureCode = 2;" in code          # FAILURE_UNCLASSIFIED_MAX_LAMBDA
    assert "eventCode = 3; failureCode = 3;" in code   # solver failure
    assert "eventCode = 0; failureCode = 0;" in code   # physical capture
    assert "eventCode = 1; failureCode = 0;" in code   # escape
    # The non-finite radius branch the audited WGSL kernel has.
    assert "IsBad(r) || r <= 1.0e-6" in code

    # A separate audit buffer: widening the 3-bit limb mask would make a texel
    # that differs only in failure code look like a shadow edge.
    assert "uint ClassOf(TraceOutputs o)" in compute
    assert "RWStructuredBuffer<uint> _ClassBuffer;" in compute
    assert "RWStructuredBuffer<float> _HMaxBuffer;" in compute
    assert "_ClassBuffer[flat] = ClassOf(o);" in code
    assert "_HMaxBuffer[flat] = o.hMaxAbs;" in code

    # Dumped, with the decoding contract published.
    assert "live_class_u32.bytes" in tracer
    assert "live_h_max_abs_f32.bytes" in tracer
    for key in ("eventCodes", "failureCodes", "classBits"):
        assert rf'\"{key}\"' in tracer, key

    # The comparator requires them and compares per class.
    assert "live_class_u32.bytes" in compare
    assert 'summary["eventCodeAgreement"]' in compare
    assert 'summary["failureCodeAgreement"]' in compare
    assert 'summary["classCounts"]' in compare
    assert 'summary["classCounts"]["numericalInvalid"] == 0' in compare
    # A solver failure must be visibly distinct in the audit map, not black.
    assert "solverFailure" in code


def test_live_tracer_applies_the_accepted_chart_rotation_sign():
    """Escape directions must use +delta, and be gated by improvement.

    Accepted `batch_escape_directions` applies +delta; the kernel applied
    -delta. The position-space chart offset and the momentum-direction offset
    carry opposite signs, so -delta is worse than no rotation at all. A plain
    angular threshold at r_escape = 200 M cannot catch this - the whole
    correction is smaller than the measured agreement there - so the gate is
    the dimensionless improvement comparison.
    """

    compute = (UNITY_RUNTIME_DIR / "BlackHoleLiveTracer.compute").read_text(encoding="utf8")
    compare = COMPARE_LIVE_TRACER.read_text(encoding="utf8")
    code = _shader_code_only(compute)

    assert "float delta = atan2(_SpinA, rEnd) + PhiShift(rEnd);" in code
    assert "float cosD = cos(delta);" in code
    assert "float sinD = sin(delta);" in code
    assert "cos(-delta)" not in code
    assert "sin(-delta)" not in code

    # The discriminating gate, not a threshold.
    assert "apply_chart_rotation=False" in compare
    assert 'summary["rotationIsImprovement"]' in compare
    assert "escape-direction rotation sign is wrong" in compare


def test_live_tracer_rain_frame_matches_accepted_construction():
    """The Unity rain frame must match the accepted Kerr construction.

    Three independent defects, none of which a Gram-matrix check can see:

    - The normalization quadratic was solved with the cancellation-unstable
      naive roots. `quad_a` goes to zero exactly at `r_+` (the outgoing branch
      diverges as Delta -> 0 in the ingoing chart), so the naive form returned
      a vector that is not a unit timelike four-velocity at all - measured
      `|u.u + 1| = 0.876` at a/M = 0.9 and 5.26 at a/M = 0.998, silently.
    - On failure it fell back to the static frame, whose `1/sqrt(-g_tt)` is
      NaN inside the ergosphere, so a NaN tetrad went to the GPU.
    - `sin(theta)` was reconstructed as `sqrt(max(1 - cos^2, 1e-16))`. That is
      the Boyer-Lindquist sine, a different quantity from the accepted
      `rho / r`, and it floors near the axis. The resulting `e_theta` stays
      perfectly orthonormal while being mis-oriented, so a Gram check passes.
    """

    tracer = (UNITY_RUNTIME_DIR / "BlackHoleLiveTracer.cs").read_text(encoding="utf8")
    code = "\n".join(
        line for line in tracer.splitlines() if not line.lstrip().startswith("//")
    )

    # Vieta-stable roots, not the naive quadratic formula.
    assert "double helper = -0.5 * (qb + signB * sqrtDisc);" in code
    assert "candidates.Add(qc / helper);" in code
    assert "candidates.Add(helper / qa);" in code
    assert "(-qb - disc) / (2.0 * qa)" not in code
    assert "(-qb + disc) / (2.0 * qa)" not in code

    # No silent static fallback; refuse instead.
    rain = _csharp_block(tracer, "private double[] RainVelocity(double[] pos, double[,] g)")
    assert "return StaticVelocity(g)" not in rain
    assert "No ingoing future-pointing rain solution found." in rain

    # Near-axis refusal, matching gr_bh_xr.observers.RAIN_MIN_SIN_THETA.
    assert "private const double RainMinSinTheta = 1.0e-6;" in tracer
    assert "rhoAxis <= RainMinSinTheta * r" in code
    assert "undefined on the Kerr symmetry axis" in tracer

    # Oriented polar leg from rho / r, not the floored BL sine.
    assert "double sinT = rhoCyl / r;" in code
    assert "Math.Sqrt(Math.Max(1.0 - cosT * cosT" not in code

    # The refusal must reach a guard, not escape through Update, and must not
    # break the hard-swap contract.
    assert "private bool TryConfigureObserverUniforms(Snapshot snapshot)" in tracer
    assert code.count("TryConfigureObserverUniforms(") >= 3
    assert "GR-BH-XR live pass refused" in tracer


def test_live_tracer_horizon_thresholds_scale_with_mass():
    """Horizon-relative radii are geometric lengths and must carry M.

    `_CaptureR`, `_HugMinR` and the validation dump's `captureR`/`hugMinR`
    used bare `0.05f` offsets. Those are geometric lengths, so at any mass
    other than 1 the live tracer terminated integration at a different
    physical radius than its own Python reference, and the mass slider spans
    0.5-2.0 M - a factor of 4 in the guard's physical size. Both the runtime
    pass and the dump path must go through the same M-scaled helper.

    The static and rain capture surfaces stay deliberately different (the
    exterior branch guards just outside r_+, the past-directed branch must
    reach inside it); only the missing M factor is corrected.
    """

    tracer = (UNITY_RUNTIME_DIR / "BlackHoleLiveTracer.cs").read_text(encoding="utf8")

    # A single helper, used by both paths, so they cannot drift apart again.
    assert "private const double HorizonGuardOverM = 0.05;" in tracer
    assert "private float HorizonGuardRadius()" in tracer
    assert "private float CaptureRadius(bool pastTracing)" in tracer

    guard = _csharp_block(tracer, "private float HorizonGuardRadius()")
    assert "(float)HorizonGuardOverM * mass" in guard

    capture = _csharp_block(tracer, "private float CaptureRadius(bool pastTracing)")
    assert "(float)HorizonGuardOverM * mass" in capture
    # Parity with gr_bh_xr.geodesic_ks._inner_capture_radius, including the
    # 0.25 * gap clamp that the previous code omitted entirely.
    assert "0.25f * (rPlus - rMinus)" in capture
    assert "Mathf.Max(1.0e-4f, rMinus + margin)" in capture
    # Both branches still exist - the fix must not collapse them into one.
    assert "if (!pastTracing)" in capture

    # Runtime pass and dump path both route through the helpers...
    runtime = _csharp_block(tracer, "private void ConfigureObserverUniforms(Snapshot snapshot)")
    assert 'SetFloat("_CaptureR", CaptureRadius(pastTracing))' in runtime
    # _HugMinR is gone entirely (see the validity test); the guard radius now
    # survives only as the exterior capture surface. Comments may still name
    # it to explain the removal, so check executable lines only.
    runtime_code = "\n".join(
        line for line in runtime.splitlines() if not line.lstrip().startswith("//")
    )
    assert "_HugMinR" not in runtime_code
    assert 'SetFloat("_HamiltonianMax", hamiltonianMax)' in runtime_code
    dump = _csharp_block(
        tracer,
        "private string ConfigureValidationUniforms(Snapshot snapshot, float radiusM, float thetaDeg, bool rainFrame)",
    )
    assert "float captureR = CaptureRadius(rainFrame);" in dump

    # ...and the unscaled literals must be gone from every horizon threshold.
    for banned in (
        "rMinus + 0.05f",
        "rPlus + 0.05f",
        "Mathf.Max(rMinus + 0.05f, 1.0e-4f)",
    ):
        assert banned not in tracer, banned

    # The adjacent dimensionful controls must at least be documented as an
    # intentionally fixed world scale rather than left ambiguous.
    assert "UNITS AUDIT" in tracer
    for control in ("stepSize", "maxStep", "stepRRef", "maxLambda", "rEscape"):
        assert control in tracer, control


def test_live_tracer_gate_imports_the_accepted_public_physics_api():
    """The gate must import the names the physics worktree actually exports.

    The snapshot this branch was ported from used the private
    `_batch_escape_directions`; the accepted merge on `main` exports
    `batch_escape_directions`. A stale private name makes the whole
    live-tracer gate fail at import time the moment the two branches are
    combined - and because the gate's pytest coverage here is source-text
    pinning, nothing else would have caught it.

    Structural half runs everywhere; the live import runs only where the
    physics module is actually present (i.e. after the merge), so this test
    tightens automatically instead of silently passing forever.
    """

    compare = COMPARE_LIVE_TRACER.read_text(encoding="utf8")

    assert (
        "from gr_bh_xr.gpu.generate_descent_keyframes import batch_escape_directions"
        in compare
    )
    # The private spelling must not come back anywhere, including call sites.
    assert "_batch_escape_directions" not in compare
    assert compare.count("batch_escape_directions(") >= 3

    importlib_util = importlib.util
    if importlib_util.find_spec("gr_bh_xr.gpu.generate_descent_keyframes") is None:
        pytest.skip(
            "gr_bh_xr.gpu.generate_descent_keyframes is owned by the Task 7-8 "
            "physics worktree and is not present on this branch; the structural "
            "pin above still applies."
        )

    from gr_bh_xr.gpu.generate_descent_keyframes import (  # noqa: PLC0415
        batch_escape_directions,
    )

    # Signature parity: the gate calls it positionally with four arguments.
    import inspect  # noqa: PLC0415

    positional = [
        name
        for name, p in inspect.signature(batch_escape_directions).parameters.items()
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    assert positional[:4] == ["params", "final_x", "final_p", "escaped"], positional


def test_live_tracer_dump_and_gate_share_every_physics_constant():
    """A constant hardcoded on both sides is an assumption, not a test.

    The capture surface was independently hardcoded in Unity (`r_+ + 0.05`)
    and in Python (`horizon_eps = 0.3`), differing by 0.35 M in the static
    case, while the gate still reported `eventAgreement = 1.0` because no
    escaping ray approaches either surface. Every such constant must now be
    published by the dump and consumed from it.
    """

    tracer = (UNITY_RUNTIME_DIR / "BlackHoleLiveTracer.cs").read_text(encoding="utf8")
    compare = COMPARE_LIVE_TRACER.read_text(encoding="utf8")

    for key in (
        "captureR",
        "hamiltonianMax",
        "diskRIn",
        "diskROut",
        "timeOrientation",
        "maxStep",
        "stepRRef",
        "adaptiveStep",
    ):
        # The C# writes JSON as an escaped string literal, so the source
        # carries \"captureR\" rather than "captureR".
        assert rf'\"{key}\"' in tracer, f"{key} not published by the dump"
        assert f'meta["{key}"]' in compare, f"{key} not consumed by the gate"

    # The exactness assertion is the point: publishing without checking would
    # still allow the two capture surfaces to drift apart.
    assert "capture surface mismatch" in compare
    assert "abs(config.capture_r - unity_capture_r) > 1.0e-6" in compare

    # The old independent hardcodes must be gone.
    assert "horizon_eps=1.0 if rain else 0.3" not in compare
    assert "disk_r_out=30.0," not in compare
    # ...and the dump's own disk outer radius must carry M.
    assert 'float diskROut = 30.0f * mass;' in tracer

    # The dumped tetrad is the common ancestor of every launch state on both
    # sides, so an unchecked tetrad cancels out of the comparison entirely.
    assert "tetradGramError" in compare
    assert "is not orthonormal" in compare


def test_live_tracer_validation_is_fail_closed_on_stages():
    """Missing stages must fail the run, not silently shrink it.

    Every stage used to be guarded by a bare `path.exists()`, and a dump
    containing only the three main buffers printed PASS. The window keys were
    also spliced into finished JSON with `metadata.Replace("\\n}\\n", ...)`,
    so any reformatting of the writer would have silently disabled the window
    stage while still emitting its `.bytes` files.
    """

    tracer = (UNITY_RUNTIME_DIR / "BlackHoleLiveTracer.cs").read_text(encoding="utf8")
    compare = COMPARE_LIVE_TRACER.read_text(encoding="utf8")

    # Structural composition, not string splicing into a closed document.
    assert "metadata.Replace(" not in tracer
    assert "stages" in tracer
    for stage in ("main", "refine", "window", "windowRefine"):
        assert rf'\"{stage}\"' in tracer, stage

    # The window limb-refine kernel must actually be dispatched by the dump;
    # it previously shipped entirely unvalidated.
    assert 'windowRefineKernel = tracerCompute.FindKernel("RefineWindow");' in tracer
    assert "live_window_dir_refined_rgba32f.bytes" in tracer
    assert "live_window_mask_u32.bytes" in tracer

    assert 'REQUIRED_STAGES = ("main", "refine", "window", "windowRefine")' in compare
    assert "--allow-missing-stage" in compare
    assert "were not validated" in compare
    assert "unvalidated:" in compare
    assert "windowRefineCoverageMeanDiff" in compare
    # Vacuous passes are errors, not skipped thresholds.
    assert 'assert both.any(), "no texel escaped in both tracers' in compare
    assert 'assert disk_both.any(), "no disk crossing in both tracers' in compare
    assert "Refusing to report a vacuous pass." in compare
    # The old permissive guards must be gone.
    assert 'if summary.get("refineSamples"):' not in compare
    assert 'if "windowEventAgreement" in summary:' not in compare


def test_unity_lens_map_loader_keeps_raw_textures_linear():
    source = (UNITY_RUNTIME_DIR / "BlackHoleLensMap.cs").read_text(encoding="utf8")
    binder = (UNITY_RUNTIME_DIR / "BlackHoleLensMaterialBinder.cs").read_text(encoding="utf8")

    assert "new Texture2D(width, height, format, mipChain: false, linear: true)" in source
    assert "new Cubemap(faceSize, format, mipChain: false)" in source
    assert "sourceAttributes" in source
    assert "FullSkyTransferMetadata" in source
    assert "LoadFullSkyCubemapIfPresent" in source
    assert "diskOrder0TransferCubeRgba16fBytes" in source
    assert "diskOrder1TransferCubeRgba16fBytes" in source
    assert "diskOrder0RedshiftCubeRgba16fBytes" in source
    assert "diskOrder1RedshiftCubeRgba16fBytes" in source
    assert "diskColorLutRgba32fBytes" in source
    assert "diskRadialLutRgba32fBytes" in source
    assert "DiskColorLutMetadata" in source
    assert "DiskRadialLutMetadata" in source
    assert "LoadDiskLutsIfPresent" in source
    assert "TextureFormat.RGBAHalf" in source
    assert "TextureFormat.RGBAFloat" in source
    assert "SetVector(" in source
    assert '"_UseFullSkyTransfer"' in source
    assert '"_EscapeDirCube"' in source
    assert '"_EventCube"' in source
    assert '"_DiskOrder0Cube"' in source
    assert '"_DiskOrder1Cube"' in source
    assert '"_DiskOrder0RedshiftCube"' in source
    assert '"_DiskOrder1RedshiftCube"' in source
    assert '"_UseDiskCoverageTransfer"' in source
    assert '"_DiskColorLut"' in source
    assert '"_DiskRadialLut"' in source
    assert '"_UseDiskColorLut"' in source
    assert '"_DiskColorLutLogT"' in source
    assert '"_DiskRadialLutBounds"' in source
    assert '"_DiskTemperatureScale"' in source
    assert '"_UseDiskTransfer"' in source
    assert '"_LensScreenBounds"' in source
    assert '"_LensRObs"' in source
    assert '"_LensWorldRight"' in source
    assert '"_LensWorldUp"' in source
    assert '"_LensWorldForward"' in source
    assert "ApplyBasisToMaterial" in source
    assert "Debug.LogWarning" in source
    assert "refreshBasisEveryFrame" in binder
    assert "LateUpdate" in binder
    assert "TryResolveLensMap" in binder
    assert "Debug.LogWarning" in binder
    assert "lensMap.ApplyBasisToMaterial(targetMaterial)" in binder


def test_unity_xr_sky_shell_runtime_is_versioned():
    source = (UNITY_RUNTIME_DIR / "BlackHoleXrSkyShell.cs").read_text(encoding="utf8")

    assert "[ExecuteAlways]" in source
    assert "RequireComponent(typeof(Renderer))" in source
    assert "RequireComponent(typeof(BlackHoleLensMap))" in source
    assert "targetCamera" in source
    assert "lensAnchor" in source
    assert "followCameraPosition" in source
    assert "refreshBasisEveryFrame" in source
    assert "public void SyncNow()" in source
    assert "Camera.main" in source
    assert "transform.position = targetCamera.transform.position" in source
    assert "transform.rotation = lensAnchor.rotation" in source
    assert "Vector3(diameter, diameter, diameter)" in source
    assert "lensMap.ApplyBasisToMaterial(ResolvedMaterial())" in source


def test_unity_lens_anchor_controls_runtime_is_versioned():
    source = (UNITY_RUNTIME_DIR / "BlackHoleLensAnchorControls.cs").read_text(encoding="utf8")

    assert "public enum DragMode" in source
    assert "YawPitch" in source
    assert "YawOnly" in source
    assert "ApplyScreenDrag" in source
    assert "AddYawDegrees" in source
    assert "AddPitchDegrees" in source
    assert "AddRollDegrees" in source
    assert "SetRollDegrees" in source
    assert "RequestObserverRadiusChange" in source
    assert "transferMapStale = true" in source
    assert "Observer-radius or apparent-size changes require a new transfer map" in source
    assert "Quaternion.Euler(pitchDegrees, yawDegrees, rollDegrees)" in source
    assert "skyShell.SyncNow()" in source
    assert "Lens Placement" in source
    # The status line must not advertise controls that no longer exist or
    # constraints that no longer hold: bare-A placement was removed, and
    # r_obs is roamed rather than locked.
    assert "place lens at current view" not in source
    assert "Size/r_obs locked" not in source
    assert "Rigid re-aim of the cached map; r_obs is roamed, not locked" in source
    assert "Input.GetMouseButtonDown" in source
    assert "KeyCode.Q" in source
    assert "KeyCode.E" in source
    assert "KeyCode.R" in source
    assert "FindAnyObjectByType<BlackHoleXrSkyShell>()" in source


def test_unity_lens_floating_panel_runtime_is_versioned():
    source = (UNITY_RUNTIME_DIR / "BlackHoleLensFloatingPanel.cs").read_text(encoding="utf8")

    assert "[ExecuteAlways]" in source
    assert "targetCamera" in source
    assert "BlackHoleLensAnchorControls" in source
    assert "cameraLocalOffset" in source
    assert "public void SetVisible" in source
    assert "public void RefreshNow()" in source
    assert "targetCamera.transform.TransformPoint(cameraLocalOffset)" in source
    assert "transform.rotation = targetCamera.transform.rotation" in source
    assert "controls.StatusText()" in source
    assert "TextMesh" in source
    assert "StatusText" in source
    assert "FindAnyObjectByType<BlackHoleLensAnchorControls>()" in source


def test_unity_runtime_settings_and_vr_panel_are_versioned():
    settings = (UNITY_RUNTIME_DIR / "BlackHoleLensRuntimeSettings.cs").read_text(encoding="utf8")
    panel = (UNITY_RUNTIME_DIR / "BlackHoleLensSettingsPanel.cs").read_text(encoding="utf8")
    controls = (UNITY_RUNTIME_DIR / "BlackHoleLensXrControllerControls.cs").read_text(encoding="utf8")
    asmdef = (UNITY_RUNTIME_DIR / "GRBHXR.asmdef").read_text(encoding="utf8")

    assert "BlackHoleLensRuntimeSettings" in settings
    assert "ToggleDiskVisualMode" in settings
    assert "CycleDiskAuditMode" in settings
    assert "AddDiskOpacity" in settings
    assert "AddDiskBrightness" in settings
    assert "AddDiskGPower" in settings
    assert '"_DiskVisualMode"' in settings
    assert '"_DiskGPower"' in settings
    assert "disk visual" in settings

    assert "BlackHoleLensSettingsPanel" in panel
    assert "Canvas" in panel
    assert "GraphicRaycaster" in panel
    assert "WorldSpace" in panel
    assert "PlaceInFrontOfCamera" in panel
    assert "DragToRay" in panel
    assert "Navigate(Vector2 axis)" in panel
    assert "ActivateSelected" in panel
    assert "Move inward" in panel
    assert "Move outward" in panel
    assert "Tier 0 playback" in panel
    assert "LegacyRuntime.ttf" in panel
    assert "Arial.ttf" not in panel

    assert "BlackHoleLensSettingsPanel" in controls
    # Right B toggles by explicit Open/Close on the visibility flag.
    assert "settingsPanel.Open()" in controls
    assert "settingsPanel.Close()" in controls
    assert "settingsPanel.IsVisible" in controls
    assert "settingsPanel.Navigate(axis)" in controls
    assert "settingsPanel.ActivateSelected()" in controls
    assert "settingsPanel.DragToRay" in controls
    assert "GetDevicePositionOrCamera" in controls
    assert "GetDeviceForwardOrCamera" in controls
    assert "UnityEngine.UI" in asmdef


def _csharp_block(source: str, header: str) -> str:
    """Return the brace-balanced body that follows `header`."""

    start = source.index(header)
    open_brace = source.index("{", start)
    depth = 0
    for index in range(open_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace : index + 1]
    raise AssertionError(f"unbalanced braces after {header!r}")


def _enclosing_if_conditions(block: str, needle: str) -> list[str]:
    """Conditions of every `if (...)` whose braced body contains `needle`."""

    target = block.index(needle)
    conditions: list[str] = []
    for match in re.finditer(r"\bif\s*\(", block[:target]):
        depth = 0
        for close in range(match.end() - 1, len(block)):
            if block[close] == "(":
                depth += 1
            elif block[close] == ")":
                depth -= 1
                if depth == 0:
                    condition = block[match.end() : close]
                    body_open = block.index("{", close)
                    body_depth = 0
                    for scan in range(body_open, len(block)):
                        if block[scan] == "{":
                            body_depth += 1
                        elif block[scan] == "}":
                            body_depth -= 1
                            if body_depth == 0:
                                if body_open < target < scan:
                                    conditions.append(" ".join(condition.split()))
                                break
                    break
    return conditions


def test_mr_acceptance_log_requires_a_genuinely_updated_frame():
    """The gate string may only be printed on a real delivered frame.

    `IsPlaying` plus an allocated texture above 16 px proves an allocation,
    not a photon - the same failure class as the WebCamTexture placeholder.
    This string is treated as *the* Task 10 acceptance criterion in several
    documents, so it must sit inside a branch whose condition names the
    delivery latch. Checked structurally (brace-balanced method body plus its
    enclosing `if` conditions), not by bare substring, so the pin cannot be
    satisfied by a comment.
    """

    mr = (UNITY_RUNTIME_DIR / "BlackHoleMrPassthrough.cs").read_text(encoding="utf8")
    bridge = (UNITY_RUNTIME_DIR / "BlackHoleMrukCameraBridge.cs").read_text(encoding="utf8")

    # The latch counts distinct MRUK timestamps rather than trusting
    # IsUpdatedThisFrame, whose readability depends on script execution order.
    assert "public bool HasEverUpdated" in bridge
    assert "public long DeliveredFrames" in bridge
    assert "timestampProperty" in bridge
    assert "deliveredFrames += 1;" in bridge
    assert "hasEverUpdated = true;" in bridge
    # Timestamp must be in the editor-domain contract check too, so an MRUK
    # version bump that drops it fails loudly instead of reverting acceptance.
    assert '"Timestamp",' in bridge

    body = _csharp_block(mr, "private void UpdateCameraBringUp()")
    acceptance = "Meta MRUK delivering calibrated"
    assert acceptance in body, "acceptance log moved out of UpdateCameraBringUp"

    conditions = _enclosing_if_conditions(body, acceptance)
    assert conditions, "acceptance log is unconditional"
    # HasDeliveredStream is the strengthened form of the latch (N distinct
    # timestamps rather than one); either name satisfies "gated on delivery",
    # but one of them must be present in an enclosing condition.
    assert any(
        "HasEverUpdated" in c or "HasDeliveredStream" in c for c in conditions
    ), f"acceptance log is not gated on the delivery latch; guards were {conditions}"

    # A distinguishable weaker line must exist for playing-but-not-updated, so
    # the two states are separable in Player.log.
    assert "awaiting a delivered stream" in body

    # The acceptance line must carry calibration, not just a resolution echo.
    accept_start = body.index(acceptance)
    assert "DescribeCalibration()" in body[accept_start : accept_start + 500]


def test_mr_delivery_evidence_cannot_survive_a_bridge_restart():
    """Frame evidence is per session and must not cross a start/stop edge.

    `Start()` begins with `Stop()`, but if `Stop()` leaves the latch set then
    after one genuine frame in an earlier attempt a later
    allocated-but-stalled camera satisfies the delivery latch immediately and
    emits the calibrated-delivery acceptance line without a single new
    timestamp.
    """

    bridge = (UNITY_RUNTIME_DIR / "BlackHoleMrukCameraBridge.cs").read_text(encoding="utf8")

    reset = _csharp_block(bridge, "private void ResetDeliveryEvidence()")
    for field in ("hasEverUpdated", "deliveredFrames", "distinctTimestamps", "lastTimestamp"):
        assert field in reset, f"{field} not cleared on the session boundary"

    start = _csharp_block(bridge, "public bool Start(Transform parent, int width, int height, int fps)")
    assert "ResetDeliveryEvidence();" in start
    stop = _csharp_block(bridge, "public void Stop()")
    assert "ResetDeliveryEvidence();" in stop

    # The acceptance rule itself must not be weakened to compensate.
    assert "timestamp != lastTimestamp" in bridge


def test_mr_acceptance_requires_a_stream_not_one_timestamp():
    """One timestamp transition proves one buffer fill, not a live stream.

    The bridge previously latched on the first distinct timestamp and then
    accepted the same stale texture forever; a frozen feed is invisible in a
    screenshot.
    """

    bridge = (UNITY_RUNTIME_DIR / "BlackHoleMrukCameraBridge.cs").read_text(encoding="utf8")
    mr = (UNITY_RUNTIME_DIR / "BlackHoleMrPassthrough.cs").read_text(encoding="utf8")

    assert "public const int RequiredDistinctTimestamps = 3;" in bridge
    assert "public bool HasDeliveredStream =>" in bridge
    assert "distinctTimestamps >= RequiredDistinctTimestamps" in bridge
    assert "public const float StaleAfterSeconds" in bridge
    assert "public bool IsStreamStale =>" in bridge
    assert "public float DeliveryAgeSeconds" in bridge

    # Acceptance must be gated on the STREAM predicate, not the first-frame
    # latch. Checked structurally so a comment cannot satisfy it.
    body = _csharp_block(mr, "private void UpdateCameraBringUp()")
    conditions = _enclosing_if_conditions(body, "Meta MRUK delivering calibrated")
    assert any("HasDeliveredStream" in c for c in conditions), conditions

    # A post-acceptance stall must be reported.
    assert "IsStreamStale" in body
    assert "STALE MRUK stream" in body

    # Freshness and sample count must reach the in-headset status too.
    status = _csharp_block(mr, "public string StatusText()")
    assert "DistinctTimestamps" in status
    assert "DeliveryAgeSeconds" in status or "age" in status


def test_mr_bridge_replacement_never_leaves_two_active_camera_hosts():
    """`Destroy` is deferred to end-of-frame, so the old host must be shut
    down synchronously or two PassthroughCameraAccess components run at once.
    """

    bridge = (UNITY_RUNTIME_DIR / "BlackHoleMrukCameraBridge.cs").read_text(encoding="utf8")

    stop = _csharp_block(bridge, "public void Stop()")
    assert "host.SetActive(false);" in stop
    assert "behaviour.enabled = false;" in stop
    # Ordering: deactivate BEFORE scheduling destruction.
    assert stop.index("host.SetActive(false);") < stop.index("UnityEngine.Object.Destroy(host);")
    assert stop.index("behaviour.enabled = false;") < stop.index("UnityEngine.Object.Destroy(host);")


def test_mr_acceptance_records_corroborating_device_evidence():
    """A ticking timestamp can still be MRUK's mock camera.

    MrukConfig.disablePcaMockFallback is left false and the package exposes no
    supported way to turn it off, so the acceptance string alone must never
    upgrade Task 10 to device-verified RGB.
    """

    mr = (UNITY_RUNTIME_DIR / "BlackHoleMrPassthrough.cs").read_text(encoding="utf8")

    assert "public static string DeviceEvidenceText()" in mr
    evidence = _csharp_block(mr, "public static string DeviceEvidenceText()")
    assert "GetSystemHeadsetType" in evidence
    assert "OpenXRRuntime" in evidence
    assert "CameraExtensionStateText()" in evidence
    assert "mockFallback=NOT-DISABLEABLE" in evidence
    assert "deviceVerified=NO" in evidence
    # No compile-time Meta dependency may be introduced for this.
    assert "using OVRPlugin" not in mr
    assert 'GetType("OVRPlugin", false)' in evidence

    # The evidence must be attached to the acceptance line itself.
    body = _csharp_block(mr, "private void UpdateCameraBringUp()")
    accept_at = body.index("Meta MRUK delivering calibrated")
    assert "DeviceEvidenceText()" in body[accept_at : accept_at + 600]


def test_mr_bridge_logs_full_calibration_and_resolves_type_robustly():
    """validation_targets.md demands intrinsics, pose and backend in the gate
    record; all of it was computed and discarded into a Vector4.
    """

    bridge = (UNITY_RUNTIME_DIR / "BlackHoleMrukCameraBridge.cs").read_text(encoding="utf8")

    describe = _csharp_block(bridge, "public string DescribeCalibration()")
    for field in ("FocalLength", "PrincipalPoint", "SensorResolution", "LensOffset"):
        assert field in describe, f"{field} missing from DescribeCalibration"
    assert "CurrentResolution" in describe or "current=" in describe
    assert "pose.position" in describe
    assert "pose.rotation" in describe
    assert "poseSource=" in describe
    assert "backend=" in describe
    assert "proj=" in describe

    # Assembly-qualified lookup FIRST, then the AppDomain scan, and the route
    # that won must be recorded.
    find = _csharp_block(bridge, "private static Type FindAccessType()")
    assert "Type.GetType(" in find
    assert "AppDomain.CurrentDomain.GetAssemblies()" in find
    assert find.index("Type.GetType(") < find.index("AppDomain.CurrentDomain.GetAssemblies()")
    assert 'AccessTypeQualifiedName =\n            "Meta.XR.PassthroughCameraAccess, meta.xr.mrutilitykit"' in bridge
    assert "resolvedVia" in find


def test_mr_gate_mode_can_forbid_the_legacy_webcam_fallback():
    """A gate build must be able to run MRUK-only.

    The 10 s ladder destroyed the supported path mid-gate with no way to
    disable it, so an ambiguous run was the default outcome. Both fall-through
    sites have to honour the flag.
    """

    mr = (UNITY_RUNTIME_DIR / "BlackHoleMrPassthrough.cs").read_text(encoding="utf8")

    # Default false = MRUK-only. An implicit default is the safe one here.
    assert "[SerializeField] private bool allowLegacyFallback;" in mr
    assert "officialBackendTimeoutSeconds = 30.0f" in mr

    preferred = _csharp_block(mr, "private bool TryStartPreferredCamera()")
    assert "allowLegacyFallback" in preferred
    guards = _enclosing_if_conditions(preferred, "return TryStartLegacyCamera();")
    assert any("allowLegacyFallback" in g for g in guards) or "!allowLegacyFallback" in preferred, (
        f"legacy fallback reachable without the flag; guards were {guards}"
    )

    bringup = _csharp_block(mr, "private void UpdateCameraBringUp()")
    assert "allowLegacyFallback" in bringup
    # The timeout branch may guard either by nesting the fallback inside
    # `if (allowLegacyFallback)` or by an early return on its negation.
    # Accept both, but require one of them: a bare mention of the field
    # anywhere in the method would not prove the fallback is unreachable.
    legacy_at = bringup.index("trying legacy WebCamTexture")
    timeout_guards = _enclosing_if_conditions(bringup, "trying legacy WebCamTexture")
    nested = any("allowLegacyFallback" in g for g in timeout_guards)
    early_return = False
    guard_at = bringup.find("if (!allowLegacyFallback)")
    if 0 <= guard_at < legacy_at:
        early_return = "return;" in bringup[guard_at:legacy_at]
    assert nested or early_return, (
        f"legacy fallback reachable at timeout without the flag; "
        f"guards were {timeout_guards}"
    )

    # A stalled session must leave continuous evidence, not one line at timeout.
    assert "ThrottledWaitingLine" in bringup
    assert "mrukCamera.LastError" in mr


def test_mr_records_camera_extension_enabled_vs_available():
    """The extension was last observed AVAILABLE but not ENABLED.

    That distinction is the single most decisive fact about a session and it
    must reach Player.log without retrieving a JSON file off the device. The
    pre-port pin matched only a doc comment.
    """

    mr = (UNITY_RUNTIME_DIR / "BlackHoleMrPassthrough.cs").read_text(encoding="utf8")
    probe = (UNITY_RUNTIME_DIR / "GRBHXRXrCapabilityProbe.cs").read_text(encoding="utf8")
    depth = (UNITY_RUNTIME_DIR / "GRBHXREnvironmentDepthFeature.cs").read_text(encoding="utf8")

    extension = "XR_METAX1_passthrough_camera_data"

    # Fail-closed against a comment-only match.
    code_only = "\n".join(
        line for line in mr.splitlines()
        if not line.lstrip().startswith(("//", "/*", "*", "///"))
    )
    assert "IsExtensionEnabled(CameraExtensionName)" in code_only
    assert f'CameraExtensionName = "{extension}"' in code_only
    assert "GetAvailableExtensions()" in code_only

    set_mr = _csharp_block(mr, "public void SetMr(bool enabledValue)")
    assert "CameraExtensionStateText()" in set_mr
    assert "EnsurePassthroughStarted()" in set_mr

    for key in ("cameraExtensionEnabled", "cameraExtensionAvailable", "mrukTypePresent"):
        assert rf'\"{key}\"' in probe, key
    assert "BlackHoleMrPassthrough.ProbeOfficialCameraBackend" in probe
    assert "cameraExt=" in probe

    # P1-7 again: never append the camera extension to the depth feature.
    assert extension not in depth


def test_capability_probe_json_is_escaped():
    """Camera friendly names are vendor-controlled and routinely contain
    quotes and backslashes; one corrupted the artifact the gate depends on.
    """

    probe = (UNITY_RUNTIME_DIR / "GRBHXRXrCapabilityProbe.cs").read_text(encoding="utf8")

    assert "private static string Esc(string value)" in probe
    esc = _csharp_block(probe, "private static string Esc(string value)")
    for pair in ('case \'\\\\\':', 'case \'"\':', "case '\\n':", "case '\\r':", "case '\\t':"):
        assert pair in esc, pair
    assert '\\\\u' in esc  # control chars below 0x20

    # Every externally-sourced value must go through it.
    assert "Esc(cam.name)" in probe
    assert "Esc(loaderName)" in probe
    assert "Esc(OpenXRRuntime.name)" in probe
    assert "Esc(ext)" in probe
    # ...and the raw interpolations must be gone.
    assert '\\"{cam.name}\\"' not in probe
    assert '\\"{loaderName}\\"' not in probe


def test_mr_status_is_visible_in_headset_and_types_are_preserved():
    """Diagnosing MR must not require quitting to read Player.log."""

    panel = (UNITY_RUNTIME_DIR / "BlackHoleLensSettingsPanel.cs").read_text(encoding="utf8")
    mr = (UNITY_RUNTIME_DIR / "BlackHoleMrPassthrough.cs").read_text(encoding="utf8")

    assert "BlackHoleMrPassthrough.Ensure().StatusText()" in panel
    status = _csharp_block(mr, "public string StatusText()")
    assert "n=" in status
    assert "ext=" in status

    # Runtime preservation without a compile-time MRUK dependency.
    link = (UNITY_RUNTIME_DIR / "link.xml").read_text(encoding="utf8")
    assert '<assembly fullname="meta.xr.mrutilitykit">' in link
    assert '<type fullname="Meta.XR.PassthroughCameraAccess" preserve="all" />' in link
    assert "PassthroughCameraAccess/CameraIntrinsics" in link
    asmdef = (UNITY_RUNTIME_DIR / "GRBHXR.asmdef").read_text(encoding="utf8")
    assert "meta.xr" not in asmdef.lower()


def test_meta_xr_feature_opt_in_is_explicit_auditable_and_fails_closed():
    """The MR device gate needs a deliberate MetaXRFeature opt-in.

    MRUK initialises its native OpenXR layer only when OVRPlugin reports
    initialised, and under the Unity OpenXR loader only MetaXRFeature does
    that. With the feature disabled - the formal project's current Standalone
    state - PassthroughCameraAccess cannot start and the camera extension can
    remain merely available, and no repository-side change works around it.

    But enabling it adds Meta's full OpenXR extension set and can perturb the
    working environment-depth path, so it must be a separate, explicit,
    logged action rather than something the generic setup helper does.
    """

    setup = (UNITY_EDITOR_DIR / "GRBHXRQuestPcvrSetup.cs").read_text(encoding="utf8")

    # Explicit opt-in exists as both a menu item and a batch entry point.
    assert 'MenuItem("GR-BH-XR/Quest PCVR/Enable MetaXRFeature (MR device gate opt-in)")' in setup
    assert "public static void EnableMetaXrFeatureForMrGateBatch()" in setup

    opt_in = _csharp_block(
        setup, "private static void EnableMetaXrFeatureForMrGate(BuildTargetGroup buildTarget)"
    )
    # It actually enables the existing instance...
    assert "feature.enabled = true;" in opt_in
    # ...logs before AND after...
    assert "BEFORE enabled=" in opt_in
    assert "AFTER enabled=" in opt_in
    # ...and fails loudly rather than no-opping when anything is missing.
    assert opt_in.count("throw new InvalidOperationException") >= 4
    for missing in (
        "no OpenXR settings",
        "type not found",
        "instance exists",
        "did not report enabled",
    ):
        assert missing in opt_in, missing

    # The generic setup path stays report-only.
    report = _csharp_block(setup, "private static string ReportMetaXrFeature(OpenXRSettings settings)")
    assert "feature.enabled = true" not in report
    assert "MetaXRFeature=disabled(reported,notChanged)" in report

    # Correct assembly, and the versionDefine caveat is recorded so a null
    # result is not misread as a wrong assembly name.
    assert '"Meta.XR.MetaXRFeature, Oculus.VR"' in setup
    assert "Meta.XR.SDK.Core" not in setup
    assert "USING_XR_SDK_OPENXR" in setup

    # Enabling the feature is not evidence of camera delivery.
    assert "does NOT by" in opt_in or "does NOT" in opt_in


def test_setup_reports_meta_xr_feature_state_without_changing_it():
    """MetaXRFeature gates OVRPlugin init, which gates MRUK's OpenXR init.

    It is disabled for Standalone in the formal project, which no
    repository-side change can work around - but enabling it adds ~95
    extensions and can perturb the working depth path, so the setup helper
    makes the state explicit and auditable rather than flipping it silently.
    """

    setup = (UNITY_EDITOR_DIR / "GRBHXRQuestPcvrSetup.cs").read_text(encoding="utf8")

    assert "ReportMetaXrFeature" in setup
    assert "MetaXRFeature=disabled(reported,notChanged)" in setup
    assert "MetaXRFeature=absent" in setup
    assert "MetaXRFeature=enabled" in setup
    # Reflection only: no compile-time Meta dependency may be introduced.
    # The assembly is Oculus.VR (the package-root asmdef). Meta.XR.SDK.Core is
    # the PACKAGE name and would never resolve; the editor's AppDomain
    # fallback masks that mistake, so pin the correct string explicitly.
    assert '"Meta.XR.MetaXRFeature, Oculus.VR"' in setup
    assert "Meta.XR.SDK.Core" not in setup
    assert "using Meta." not in setup
    # It must not enable the feature.
    report = _csharp_block(setup, "private static string ReportMetaXrFeature(OpenXRSettings settings)")
    assert "feature.enabled = true" not in report
    assert "EnableFeature(" not in report


def test_unity_mr_passthrough_capability_baseline():
    """Task 10 baseline: capability discovery and late-bound MRUK adapter.

    This commit may claim capability discovery and environment-depth
    acquisition. It may NOT claim delivered calibrated RGB frames; the
    strengthened delivery contract is pinned separately.
    """

    mr = (UNITY_RUNTIME_DIR / "BlackHoleMrPassthrough.cs").read_text(encoding="utf8")
    bridge = (UNITY_RUNTIME_DIR / "BlackHoleMrukCameraBridge.cs").read_text(encoding="utf8")
    probe = (UNITY_RUNTIME_DIR / "GRBHXRXrCapabilityProbe.cs").read_text(encoding="utf8")
    depth = (UNITY_RUNTIME_DIR / "GRBHXREnvironmentDepthFeature.cs").read_text(encoding="utf8")
    asmdef = (UNITY_RUNTIME_DIR / "GRBHXR.asmdef").read_text(encoding="utf8")

    # Late binding: the core package must load with no Meta package present,
    # so nothing here may reference MRUK at compile time.
    assert "Meta.XR.PassthroughCameraAccess" in bridge
    assert "System.Reflection" in bridge
    assert "using Meta." not in bridge
    assert "meta.xr" not in asmdef.lower()
    assert "ProbeOfficialCameraBackend" in mr
    assert "ValidateContract" in bridge

    # Capability probe writes what the runtime reports, including the
    # available-vs-enabled distinction that the device gate turns on.
    assert "OpenXRRuntime" in probe
    assert "GetAvailableExtensions" in probe
    assert "GetEnabledExtensions" in probe
    assert "xr_capability_probe.json" in probe

    # Environment depth is a separate feature with its own extension list.
    assert "XR_META_environment_depth" in depth
    # P1-7: the camera extension must never be appended to the depth feature's
    # required list - one unavailable string would disable the working depth
    # path as collateral.
    assert "XR_METAX1_passthrough_camera_data" not in depth

    # Depth is acquired but not consumed: there is no depth sampler anywhere
    # in the lens shader, and that boundary must not quietly change.
    shader = (UNITY_RUNTIME_DIR / "BlackHoleLensStaticPreview.shader").read_text(encoding="utf8")
    assert "_EnvironmentDepth" not in shader


def test_unity_mr_reports_when_passthrough_is_inert_under_roam_blend():
    """MR must not report ON when the active shader variant discards it.

    GRBHXR_ROAM_BLEND compiles out _MrCameraTex and sampleBackground to stay
    inside the sampler budget, and roam playback enables that keyword for
    essentially its whole range. The camera started, _UseMrPassthrough was
    set, and the log said "ON" while not one pixel changed.
    """

    mr = (UNITY_RUNTIME_DIR / "BlackHoleMrPassthrough.cs").read_text(encoding="utf8")
    shader = (UNITY_RUNTIME_DIR / "BlackHoleLensStaticPreview.shader").read_text(encoding="utf8")

    assert 'IsKeywordEnabled("GRBHXR_ROAM_BLEND")' in mr
    assert "ON but INERT" in mr
    # The unconditional confident line must be gone.
    assert 'Debug.Log($"GR-BH-XR MR passthrough {(mrEnabled ? "ON" : "OFF")}.");\n        }' not in mr

    # The precondition for the warning: the sampler really is compiled out.
    assert "#ifndef GRBHXR_ROAM_BLEND" in shader
    assert "sampler2D _MrCameraTex;" in shader


def test_unity_observer_rig_turns_tracking_space_not_lens_basis():
    """Comfort yaw rotates the observer's tracking space, never the map.

    Rotating the cached lens basis would silently pass as "looking around"
    while actually re-aiming a physical solution.
    """

    rig = (UNITY_RUNTIME_DIR / "BlackHoleObserverRigControls.cs").read_text(encoding="utf8")
    head = (UNITY_RUNTIME_DIR / "BlackHoleXrHeadPoseDriver.cs").read_text(encoding="utf8")

    assert "trackingOrigin.RotateAround" in rig
    assert "targetCamera.transform.position" in rig
    assert "TrackingToWorldPoint" in rig
    assert "TrackingToWorldDirection" in rig
    assert "public Transform TrackingOrigin" in head
    assert "public void SetTrackingOrigin" in head
    # The comfort yaw must never reach the lens basis.
    assert "controls.AddYawDegrees" not in rig
    assert "AddPitchDegrees" not in rig


def test_unity_observer_rig_radial_roam_is_keyframe_gated():
    """Roam locomotion is bounded by what has actually been traced."""

    rig = (UNITY_RUNTIME_DIR / "BlackHoleObserverRigControls.cs").read_text(encoding="utf8")
    roam = (UNITY_RUNTIME_DIR / "BlackHoleRoamKeyframes.cs").read_text(encoding="utf8")

    # Walking decomposes the pushed direction onto the observer's spherical
    # axes; radial motion is exponential in radius, polar motion swaps grid
    # rows, azimuthal motion is exact by axisymmetry, and every component is
    # clamped so the view cannot outrun keyframe loading.
    assert "AddWalkInput" in rig
    assert "AddSphericalInput" in rig
    assert "KerrObserverBasis.SphericalDirections" in rig
    assert "RadialLocomotionAvailable" in rig
    assert "Mathf.Log(virtualRadiusM)" in rig
    assert "roamKeyframes.ClampRadius" in rig
    assert "roamKeyframes.ClampThetaDeg" in rig
    assert "roamKeyframes.SetTarget" in rig
    assert "KeyCode.W" in rig
    assert "KeyCode.S" in rig

    assert "roam_keyframes_metadata.json" in roam
    assert "streamingAssetsPath" in roam
    assert "gr-bh-xr.task7.roam_keyframes.v2" in roam
    assert "public float ClampRadius" in roam
    assert "public float ClampThetaDeg" in roam
    assert "public void SetTarget" in roam
    assert "public void ForceBind" in roam
    assert '"_SkyBlueshift"' in roam
    # Nearest keyframe is selected in log radius; binding rebinds every cube
    # slot and disables the single-radius hybrid angular window.
    assert "Mathf.Log" in roam
    for slot in (
        "_EventCube",
        "_EscapeDirCube",
        "_DiskOrder0Cube",
        "_DiskOrder1Cube",
        "_DiskOrder0RedshiftCube",
        "_DiskOrder1RedshiftCube",
    ):
        assert f'"{slot}"' in roam, slot
    # Off would select the legacy full-screen 2D mode; the roam bind keeps the
    # angular window on but collapses it to an empty (inverted) range so all
    # pixels take the full-sky cubemap path.
    assert '"_UseAngularWindow", 1.0f' in roam
    assert "new Vector4(1.0f, -1.0f, 1.0f, -1.0f)" in roam
    assert '"_LensRObs"' in roam
    # Pin the descent schema constant, not a docstring adjective: a comment
    # containing "quasi-static" survives deleting the entire feature.
    assert 'SupportedDescentSchema = "gr-bh-xr.task8.descent_keyframes.v1"' in roam


def test_unity_roam_makes_no_task8_physics_claim():
    """This worktree must not assert rain-frame / descent physics validity.

    The rain-frame worldline, its descent keyframes, and their gates are owned
    by the Task 7-8 physics worktree, and the descent producer is not present
    on this branch at all. Runtime strings that told the operator the falling
    frame carried "true" or "exact" aberration/Doppler were therefore claims
    this code cannot support - and they were emitted unconditionally, even in
    plain grid mode with no descent assets bound.
    """

    rig = (UNITY_RUNTIME_DIR / "BlackHoleObserverRigControls.cs").read_text(encoding="utf8")
    roam = (UNITY_RUNTIME_DIR / "BlackHoleRoamKeyframes.cs").read_text(encoding="utf8")
    shader = (UNITY_RUNTIME_DIR / "BlackHoleLensStaticPreview.shader").read_text(encoding="utf8")

    for banned in (
        "true aberration/Doppler",
        "carries true aberration",
        "aberration and Doppler of\n    /// the falling frame are exact",
        "aberration/Doppler switch on",
        "validated rain-frame",
    ):
        for name, text in (("rig", rig), ("roam", roam), ("shader", shader)):
            assert banned not in text, f"{banned!r} still claimed in {name}"

    # The retracted observer-factor figure must never again be presented as a
    # validation result. It may only appear as an explicit retraction.
    assert "validated against traced conserved q_t to 2.7e-8" not in shader
    if "2.7e-8" in shader:
        assert "retracted" in shader
        assert "is not used" in shader

    # The honest statement of what playback is must be present.
    assert "no boost between keyframes" in roam.lower()
    assert "intermediate radii are not solved" in roam

    # Free fall must be refused, not silently run on Schwarzschild pacing,
    # when the audited descent keyframes are absent.
    assert "public bool FreeFallAvailable" in rig
    assert "roamKeyframes.DescentAvailable" in rig
    assert "GR-BH-XR free fall refused" in rig
    assert "SCHWARZSCHILD pacing" in rig
    # And the pacing error has to be stated where the expression lives.
    assert "5.91% at 2.5M" in rig
    assert "33.6% at 2.5M" in rig


def test_unity_roam_asset_absence_is_loud():
    """A missing manifest must not silently disable every control.

    Grid-manifest absence used to `return null` with no Debug call at all, so
    every locomotion control did nothing and the only evidence was an empty
    status line. That is also the exact signature of an Android/Quest-native
    build, where StreamingAssets is inside the APK and System.IO cannot read
    it.
    """

    rig = (UNITY_RUNTIME_DIR / "BlackHoleObserverRigControls.cs").read_text(encoding="utf8")
    roam = (UNITY_RUNTIME_DIR / "BlackHoleRoamKeyframes.cs").read_text(encoding="utf8")

    assert "GR-BH-XR roam disabled:" in roam
    assert "descent keyframes not bound" in roam.lower()
    assert "return null;  // descent is optional" not in roam
    assert "GR-BH-XR observer locomotion ignored" in rig
    assert "GR-BH-XR free fall unavailable" in rig


def test_unity_panel_reports_the_metric_it_lets_you_change():
    """Spin and mass are the metric; they must be readable and logged."""

    panel = (UNITY_RUNTIME_DIR / "BlackHoleLensSettingsPanel.cs").read_text(encoding="utf8")
    tracer = (UNITY_RUNTIME_DIR / "BlackHoleLiveTracer.cs").read_text(encoding="utf8")
    controls = (UNITY_RUNTIME_DIR / "BlackHoleLensXrControllerControls.cs").read_text(encoding="utf8")

    assert "tracer.MassValue" in panel
    assert "tracer.SpinValue" in panel
    assert "GR-BH-XR live metric: a =" in tracer
    assert "GR-BH-XR live metric: M =" in tracer
    # The hidden left-grip metric chord must be discoverable from a status
    # string rather than only from the source.
    assert "L grip + R stick changes the metric" in controls
    # The rendered polar row must be shown next to the walked one.
    assert "BoundThetaDeg" in controls


def test_unity_editor_gate_automation_is_versioned():
    source = (UNITY_EDITOR_DIR / "GRBHXRGateAutomation.cs").read_text(encoding="utf8")
    asmdef = (UNITY_EDITOR_DIR / "GRBHXR.Editor.asmdef").read_text(encoding="utf8")

    assert "BatchConfigureAndCapture" in source
    assert "BatchCaptureQuadrantHandedness" in source
    assert "BatchCaptureProtractorBands" in source
    assert "BatchCaptureAngularWindowYawGate" in source
    assert "BatchCaptureFullSkyProtractorYawGate" in source
    assert "BatchCaptureFullSkyDiskAuditGate" in source
    assert "BatchCaptureFullSkyDiskVisualLutGate" in source
    assert "CaptureFullSkyDiskVisualLutGate" in source
    assert "BatchConfigurePcvrSkyShellFirstRun" in source
    assert "ConfigurePcvrSkyShellFirstRun" in source
    assert "CaptureYaw" in source
    assert "FullSkyTransferDir" in source
    assert "-grbhxrFullSkyTransferDir" in source
    assert "-grbhxrUseSkyShell" in source
    assert "full_sky_transfer_metadata.json" in source
    assert "event_cube_rgba8.bytes" in source
    assert "escape_dir_unity_cube_rgba32f.bytes" in source
    assert "disk_order0_transfer_cube_rgba16f.bytes" in source
    assert "disk_order1_transfer_cube_rgba16f.bytes" in source
    assert "disk_order0_redshift_cube_rgba16f.bytes" in source
    assert "disk_order1_redshift_cube_rgba16f.bytes" in source
    assert "disk_color_lut_metadata.json" in source
    assert "disk_color_lut_rgba32f.bytes" in source
    assert "disk_radial_lut_metadata.json" in source
    assert "disk_radial_lut_rgba32f.bytes" in source
    assert "diskColorLutMetadataJson" in source
    assert "diskRadialLutRgba32fBytes" in source
    assert '"_UseFullSkyTransfer"' in source
    assert '"_UseDiskColorLut"' in source
    assert '"_ProbeMode"' in source
    assert '"_DiskAuditMode"' in source
    assert "unity_gate_square_2048.png" in source
    assert "unity_gate_quadrant_square_1024.png" in source
    assert "unity_gate_protractor_square_1024.png" in source
    assert "unity_gate_angular_yaw_000_square_1024.png" in source
    assert "unity_gate_angular_yaw_002_square_1024.png" in source
    assert "unity_gate_angular_yaw_004_square_1024.png" in source
    assert "unity_gate_fullsky_protractor_yaw_000_square_1024.png" in source
    assert "unity_gate_fullsky_protractor_yaw_002_square_1024.png" in source
    assert "unity_gate_fullsky_protractor_yaw_004_square_1024.png" in source
    assert "unity_gate_fullsky_disk_audit_m0_square_1024.png" in source
    assert "unity_gate_fullsky_disk_audit_m1_square_1024.png" in source
    assert "unity_gate_fullsky_disk_visual_proxy_square_1024.png" in source
    assert "unity_gate_fullsky_disk_visual_lut_square_1024.png" in source
    assert "refreshLensMaps: false" in source
    assert "LensSkyShell" in source
    assert "BlackHoleLensAnchor" in source
    assert "BlackHoleXrSkyShell" in source
    assert "BlackHoleLensAnchorControls" in source
    assert "BlackHoleLensFloatingPanel" in source
    assert "BlackHoleLensSettingsPanel" in source
    assert "BlackHoleLensRuntimeSettings" in source
    assert "LensControlPanel" in source
    assert "LensSettingsPanel" in source
    assert '"_DiskVisualMode"' in source
    assert "-grbhxrDiskVisualMode" in source
    assert "PrimitiveType.Sphere" in source
    assert "AssignSerializedObject(skyShellComponent, \"targetCamera\", camera)" in source
    assert "AssignSerializedObject(skyShellComponent, \"lensAnchor\", lensAnchor.transform)" in source
    assert "AssignSerializedFloat(skyShellComponent, \"shellDiameter\", 200.0f)" in source
    assert "AssignSerializedBool(skyShellComponent, \"followCameraPosition\", true)" in source
    assert "skyShellComponent.SyncNow()" in source
    assert "AssignSerializedObject(controls, \"lensAnchor\", lensAnchor.transform)" in source
    assert "AssignSerializedObject(controls, \"skyShell\", skyShellComponent)" in source
    assert "AssignSerializedObject(panel, \"targetCamera\", camera)" in source
    assert "AssignSerializedObject(panel, \"controls\", controls)" in source
    assert "panel.RefreshNow()" in source
    assert "new Vector3(20.0f, 20.0f, 20.0f)" in source
    assert "new Vector3(20.0f, 20.0f, 1.0f)" not in source
    assert "GRBHXR.Editor" in asmdef
    assert '"includePlatforms"' in asmdef
    assert '"Editor"' in asmdef


def test_quest_pcvr_preflight_is_read_only_and_checks_assets():
    source = PCVR_PREFLIGHT_SCRIPT.read_text(encoding="utf8")

    assert "D:\\unity\\Hub\\Editor\\6000.5.2f1\\Editor\\Unity.exe" in source
    assert "F:\\UnityProjects\\GRBHXR_PCVR_Gate\\GRBHXR_PCVR_Gate" in source
    assert "Assets\\GRBHXR\\FullSkyTransfer1024" in source
    assert "full_sky_transfer_metadata.json" in source
    assert "event_cube_rgba8.bytes" in source
    assert "escape_dir_unity_cube_rgba32f.bytes" in source
    assert "adb devices -l" in source
    assert "Get-PnpDevice" in source
    assert "VID_2833" in source
    assert "ConvertTo-Json" in source
    assert "adb install" not in source
    assert "adb push" not in source
    assert "Set-" not in source


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


def test_protractor_gate_comparison_detects_old_scale_skew():
    module = _load_module(PROTRACTOR_SCRIPT, "compare_protractor_gate")
    direction = np.asarray([0.45, 0.0, math.sqrt(1.0 - 0.45**2), 1.0], dtype=np.float32)
    directions = np.broadcast_to(direction, (8, 8, 4)).copy()
    raw_band = module.band_from_direction(direction)
    assert raw_band is not None

    linear_red = (raw_band + 0.5) / 18.0
    linear_rgb = np.asarray([linear_red, 0.0, 1.0 - linear_red], dtype=np.float64)
    srgb_rgb = _linear_to_srgb(linear_rgb)
    image = np.broadcast_to(srgb_rgb, (8, 8, 3)).copy()

    result = module.compare_protractor(image, directions, samples=5)

    assert result.valid == 25
    assert result.exact_raw == 25
    assert result.raw_closer == 25
    assert result.exact_old_skew == 0
    assert result.old_skew_closer == 0


def test_full_sky_protractor_loader_matches_generated_cubemap_faces(tmp_path):
    module = _load_module(PROTRACTOR_SCRIPT, "compare_protractor_gate_fullsky")
    face_size = 4
    package = tmp_path / "fullsky_package"
    package.mkdir()
    (package / "full_sky_transfer_metadata.json").write_text(
        json.dumps(
            {
                "schema": "gr-bh-xr.task5.full_sky_transfer_cubemap.v1",
                "faceSize": face_size,
                "faceOrder": list(UNITY_CUBE_FACES),
            }
        ),
        encoding="utf8",
    )

    cube = np.zeros((len(UNITY_CUBE_FACES), face_size, face_size, 4), dtype=np.float32)
    for face_index, face_name in enumerate(UNITY_CUBE_FACES):
        directions = _face_directions(face_name, face_size).reshape((face_size, face_size, 3))
        cube[face_index, ..., :3] = directions
        cube[face_index, ..., 3] = 1.0
    cube.astype("<f4", copy=False).tofile(package / "escape_dir_unity_cube_rgba32f.bytes")

    loaded = module.load_full_sky_direction_package(package)
    np.testing.assert_allclose(loaded, cube)
    for face_name in UNITY_CUBE_FACES:
        directions = _face_directions(face_name, face_size)
        for direction in directions:
            sampled = module.bilinear_cubemap_direction(loaded, direction)
            np.testing.assert_allclose(sampled[:3], direction, atol=1.0e-6)
            assert sampled[3] == pytest.approx(1.0)


def test_full_sky_disk_transfer_premultiplies_coverage_channels():
    face_disk = np.zeros((2, 4, 4), dtype=np.float32)
    face_disk[0, 0] = [6.0, 0.25, 0.97, 0.8]
    face_disk[0, 1] = [7.0, -0.1, 0.99, 1.1]
    face_disk[1, 2] = [12.0, 0.5, 0.86, 0.6]

    transfer, redshift, coverage = _premultiply_disk_samples(face_disk)

    np.testing.assert_allclose(coverage[0], [1.0, 1.0, 0.0, 0.0])
    np.testing.assert_allclose(coverage[1], [0.0, 0.0, 1.0, 0.0])
    np.testing.assert_allclose(transfer[0, 0], [6.0, 0.25, 0.97, 1.0])
    np.testing.assert_allclose(redshift[0, 0], [0.8, 0.0, 0.0, 0.0])
    np.testing.assert_allclose(redshift[1, 2], [0.6, 0.0, 0.0, 0.0])


def test_disk_validity_boundary_mask_marks_both_sides_of_edge():
    valid = np.asarray(
        [
            [False, False, False],
            [False, True, True],
            [False, False, False],
        ],
        dtype=bool,
    )

    boundary = _validity_boundary_mask(valid)

    assert boundary[1, 1]
    assert boundary[1, 2]
    assert boundary[0, 1]
    assert boundary[2, 2]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _linear_to_srgb(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    return np.where(values <= 0.0031308, values * 12.92, 1.055 * np.power(values, 1 / 2.4) - 0.055)
