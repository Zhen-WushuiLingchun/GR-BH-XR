import json
from pathlib import Path

import numpy as np
import pytest

from gr_bh_xr.transfer_keyframes import (
    interpolate_disk_sample,
    interpolate_escape_direction,
    validate_time_indexed_manifest,
)
from validation.bbh_transfer_keyframes.scripts.build_native_playback_fixture import (
    build_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
NPGS = ROOT / "runtime" / "NPGS" / "NPGS"
PLAYBACK = NPGS / "Sources/Engine/Core/Runtime/XR/TransferKeyframePlayback.cpp"
SHADER = NPGS / "Sources/Engine/Shaders/BlackHole_common.glsl"
SMOKE_SCRIPT = (
    ROOT
    / "validation/bbh_transfer_keyframes/scripts/run_native_playback_smoke.ps1"
)


def test_native_playback_is_bounded_and_wired_to_dedicated_shader() -> None:
    implementation = PLAYBACK.read_text(encoding="utf-8")
    application = (NPGS / "Sources/Program/Application.cpp").read_text(encoding="utf-8")
    config = (NPGS / "Tools/ShaderCompiler/CompileShaders.cfg").read_text(encoding="utf-8")
    assert "SlotCount = 2" in (PLAYBACK.with_suffix(".h")).read_text(encoding="utf-8")
    assert "WaitIdle" in implementation
    assert "ResidentResourceChanged" in implementation
    assert "ReadVerifiedTransferAsset" in implementation
    for role in (
        "event",
        "escape_direction",
        "disk_order0_transfer",
        "disk_order0_redshift",
        "disk_order1_transfer",
        "disk_order1_redshift",
    ):
        assert role in implementation
    assert "RequiredCompositeSamplers = 21" in application
    assert "RequestedMetricTime < Sequence.ExpectedStartMetricTimeM" in application
    assert "Sequence.Frames.size() > Runtime::XR::FTransferKeyframePlayback::SlotCount" in application
    playback_clock = application[
        application.index("double RequestedMetricTime"):
        application.index("if (TransferPlayback->Update(MetricTime))")
    ]
    assert "std::clamp" not in playback_clock
    assert "BlackHole_transfer_prepass.frag.spv" in config
    assert "BlackHole_transfer_composite.frag.spv" in config
    smoke = SMOKE_SCRIPT.read_text(encoding="utf-8")
    assert "slot=0 frame=2" in smoke
    assert "resident_frames=2" in smoke
    assert "extrapolation is forbidden" in smoke


def test_shader_interpolates_physics_before_visual_shading() -> None:
    shader = SHADER.read_text(encoding="utf-8")
    assert "TransferInterpolateDisk" in shader
    assert "packedA.rgb / coverageA" in shader
    assert "azimuth *= inversesqrt" in shader
    assert "dot(escapeA, escapeB) > -0.999" in shader
    assert "!all(equal(eventA, eventB))" in shader
    assert shader.index("TransferInterpolateDisk(") < shader.index("TransferShadeDisk(")
    assert "visual proxy until" in shader


def test_native_fixture_matches_authoritative_midpoint_contract(tmp_path: Path) -> None:
    manifest = build_fixture(tmp_path / "fixture")
    validation = validate_time_indexed_manifest(manifest)
    assert validation.valid is True
    assert validation.runtime_asset_ready is True
    assert len(json.loads(manifest.read_text(encoding="utf-8"))["frames"]) == 3

    direction, valid = interpolate_escape_direction(
        [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], 0.5,
        left_valid=True, right_valid=True,
    )
    assert valid is True
    assert direction == pytest.approx([np.sqrt(0.5), np.sqrt(0.5), 0.0])

    phi_a = np.deg2rad(179.0)
    phi_b = np.deg2rad(-179.0)
    left = np.array([3.0, 0.5 * np.sin(phi_a), 0.5 * np.cos(phi_a), 0.5])
    right = np.array([10.0, np.sin(phi_b), np.cos(phi_b), 1.0])
    transfer, redshift, disk_valid = interpolate_disk_sample(
        left,
        np.array([0.4, 0.0, 0.0, 0.0]),
        right,
        np.array([1.2, 0.0, 0.0, 0.0]),
        0.5,
    )
    assert disk_valid is True
    assert transfer[3] == pytest.approx(0.75)
    assert transfer[0] / transfer[3] == pytest.approx(8.0)
    assert redshift[0] / transfer[3] == pytest.approx(1.0)
