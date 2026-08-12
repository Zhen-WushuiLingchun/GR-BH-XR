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
from validation.bbh_transfer_keyframes.scripts.compare_native_playback_probe import (
    PROBE_SCHEMA,
    compare_probe,
    expected_probe_records,
)
from validation.bbh_transfer_keyframes.scripts.benchmark_native_playback_residency import (
    parse_native_output,
)


ROOT = Path(__file__).resolve().parents[1]
NPGS = ROOT / "runtime" / "NPGS" / "NPGS"
PLAYBACK = NPGS / "Sources/Engine/Core/Runtime/XR/TransferKeyframePlayback.cpp"
SHADER = NPGS / "Sources/Engine/Shaders/BlackHole_common.glsl"
PROBE_SHADER = NPGS / "Sources/Engine/Shaders/BlackHole_transfer_probe.frag.glsl"
SMOKE_SCRIPT = (
    ROOT
    / "validation/bbh_transfer_keyframes/scripts/run_native_playback_smoke.ps1"
)


def test_native_playback_prefetch_is_fence_safe_and_wired_to_dedicated_shader() -> None:
    implementation = PLAYBACK.read_text(encoding="utf-8")
    application = (NPGS / "Sources/Program/Application.cpp").read_text(encoding="utf-8")
    config = (NPGS / "Tools/ShaderCompiler/CompileShaders.cfg").read_text(encoding="utf-8")
    header = (PLAYBACK.with_suffix(".h")).read_text(encoding="utf-8")
    assert "LogicalSlotCount = 2" in header
    assert "SlotCount = 3" in header
    load_slot = implementation[
        implementation.index("void FTransferKeyframePlayback::LoadSlot") :
        implementation.index("std::uint32_t FTransferKeyframePlayback::EnsureResident")
    ]
    assert "WaitIdle" not in load_slot
    assert "SlotIsReferenced" in load_slot
    assert "std::async(std::launch::async" in implementation
    assert "PumpIncrementalUpload" in implementation
    assert "NPGS_TRANSFER_UPLOAD" in implementation
    assert "MaxSliceUploadMilliseconds" in header
    assert "NextFace" in header
    assert "UploadFace" in implementation
    assert "AppliedMetricTimeM" in application
    assert "NPGS_TRANSFER_STALL" in implementation
    assert "ReadFrame(FrameIndex)" in implementation
    assert "ActivateBracket" in implementation
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
    assert "Sequence.Frames.size() > Runtime::XR::FTransferKeyframePlayback::LogicalSlotCount" in application
    assert "ReleaseFrameReferences(CurrentFrame)" in application
    assert "WriteDynamicDescriptors" in application
    playback_clock = application[
        application.index("double RequestedMetricTime"):
        application.index("TransferPlayback->Update(RequestedMetricTime);")
    ]
    assert "std::clamp" not in playback_clock
    assert "BlackHole_transfer_prepass.frag.spv" in config
    assert "BlackHole_transfer_composite.frag.spv" in config
    smoke = SMOKE_SCRIPT.read_text(encoding="utf-8")
    assert "slot=2 frame=2" in smoke
    assert "slot=0 frame=3" in smoke
    assert "resident_frames=3" in smoke
    assert "extrapolation is forbidden" in smoke


def test_shader_interpolates_physics_before_visual_shading() -> None:
    shader = SHADER.read_text(encoding="utf-8")
    assert "TransferInterpolateDisk" in shader
    assert "packedA.rgb / coverageA" in shader
    assert "azimuth *= inversesqrt" in shader
    assert "endpointDot > -0.999" in shader
    assert "matchingKnownEvent = all(equal(eventA, eventB))" in shader
    assert "if (!matchingKnownEvent)" in shader
    assert shader.index("TransferInterpolateDisk(") < shader.index("TransferShadeDisk(")
    disk_interpolator = shader[
        shader.index("bool TransferInterpolateDisk(") : shader.index("vec4 TransferShadeDisk(")
    ]
    assert disk_interpolator.index("disk = vec4(0.0)") < disk_interpolator.index(
        "if (coverageA <= 1e-4"
    )
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


def test_native_transfer_probe_reuses_visual_physical_evaluator() -> None:
    common = SHADER.read_text(encoding="utf-8")
    probe = PROBE_SHADER.read_text(encoding="utf-8")
    application = (NPGS / "Sources/Program/Application.cpp").read_text(encoding="utf-8")
    main = (NPGS / "Sources/Program/main.cpp").read_text(encoding="utf-8")
    config = (NPGS / "Tools/ShaderCompiler/CompileShaders.cfg").read_text(encoding="utf-8")
    assert "TransferEvaluatePhysicalSample" in common
    assert common.count("TransferEvaluatePhysicalSample(") == 2
    assert "TransferEvaluatePhysicalSample(unityRay)" in probe
    assert "BlackHole_transfer_probe.frag.spv" in config
    assert "--transfer-probe-out" in main
    assert "gr-bh-xr.npgs.transfer-probe.raw.v1" in application
    assert "shared_visual_physical_evaluator" in application


def test_spatial_probe_fixture_varies_across_faces_and_exercises_fail_closed_events(
    tmp_path: Path,
) -> None:
    manifest_path = build_fixture(tmp_path / "fixture", face_size=4, spatial_probe=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.parent
    left = np.fromfile(
        base / manifest["frames"][0]["buffers"]["escape_direction"]["path"], dtype="<f4"
    ).reshape(6, 4, 4, 4)
    left_event = np.fromfile(
        base / manifest["frames"][0]["buffers"]["event"]["path"], dtype="u1"
    ).reshape(6, 4, 4, 4)
    right_event = np.fromfile(
        base / manifest["frames"][1]["buffers"]["event"]["path"], dtype="u1"
    ).reshape(6, 4, 4, 4)
    assert np.unique(left[..., :3].reshape(-1, 3), axis=0).shape[0] > 20
    assert np.count_nonzero(np.any(left_event != right_event, axis=-1)) > 0
    assert np.count_nonzero(np.all(left_event == [0, 0, 0, 255], axis=-1)) > 0
    assert np.count_nonzero(np.all(left_event == [48, 132, 255, 255], axis=-1)) > 0


def test_transfer_probe_comparator_accepts_exact_contract_records(tmp_path: Path) -> None:
    manifest_path = build_fixture(tmp_path / "fixture", face_size=3, spatial_probe=True)
    raw_path = tmp_path / "probe.bin"
    metadata = {
        "schema": PROBE_SCHEMA,
        "raw_file": raw_path.name,
        "dtype": "float32-little-endian",
        "width": 18,
        "height": 3,
        "face_size": 3,
        "record_float_count": 72,
        "bracket": {
            "requested_metric_time_M": 0.5,
            "left_index": 0,
            "right_index": 1,
            "left_metric_time_M": 0.0,
            "right_metric_time_M": 1.0,
            "alpha": 0.5,
        },
    }
    expected = expected_probe_records(manifest_path, metadata)
    expected.astype("<f4").tofile(raw_path)
    Path(str(raw_path) + ".json").write_text(json.dumps(metadata), encoding="utf-8")
    summary = compare_probe(raw_path, manifest_path)
    assert summary["passed"] is True
    assert summary["metrics"]["texel_identity_mismatches"] == 0
    assert summary["metrics"]["event_mismatches"] == 0


def test_native_residency_output_parser_preserves_swap_measurements() -> None:
    parsed = parse_native_output(
        "\n".join(
            (
                "NPGS_TRANSFER_RESIDENT slot=0 frame=0 metric_time_M=0 bytes=4992 io_hash_ms=0.25 upload_ms=1.25 total_ms=1.5",
                "NPGS_TRANSFER_RESIDENT slot=1 frame=1 metric_time_M=1 bytes=4992 io_hash_ms=0.3 upload_ms=1.5 total_ms=1.8",
                "NPGS_TRANSFER_PLAYBACK_READY face_size=4 resident_frames=2 resident_bytes=9984",
                "NPGS_TRANSFER_PREFETCH frame=2 bytes=4992 io_hash_ms=0.35",
                "NPGS_TRANSFER_UPLOAD slot=2 frame=2 role=event role_index=0 face=0 bytes=384 upload_ms=0.25",
                "NPGS_TRANSFER_UPLOAD slot=2 frame=2 role=escape_direction role_index=1 face=0 bytes=1536 upload_ms=0.75",
                "NPGS_TRANSFER_UPLOAD slot=2 frame=2 role=disk_order0_transfer role_index=2 face=0 bytes=768 upload_ms=0.2",
                "NPGS_TRANSFER_UPLOAD slot=2 frame=2 role=disk_order0_redshift role_index=3 face=0 bytes=768 upload_ms=0.2",
                "NPGS_TRANSFER_UPLOAD slot=2 frame=2 role=disk_order1_transfer role_index=4 face=0 bytes=768 upload_ms=0.15",
                "NPGS_TRANSFER_UPLOAD slot=2 frame=2 role=disk_order1_redshift role_index=5 face=0 bytes=768 upload_ms=0.2",
                "NPGS_TRANSFER_RESIDENT slot=2 frame=2 metric_time_M=2 bytes=4992 io_hash_ms=0.35 upload_ms=1.75 max_slice_upload_ms=0.75 total_ms=2.1",
                "NPGS_TRANSFER_PLAYBACK_OK left=1 right=2 alpha=0.5 resident_frames=3 resident_bytes=14976",
            )
        )
    )
    assert [(entry["slot"], entry["frame"]) for entry in parsed["uploads"]] == [
        (0, 0),
        (1, 1),
        (2, 2),
    ]
    assert parsed["uploads"][2]["upload_ms"] == 1.75
    assert parsed["uploads"][2]["max_slice_upload_ms"] == 0.75
    assert parsed["uploads"][2]["io_hash_ms"] == 0.35
    assert parsed["prefetches"] == [
        {"frame": 2, "bytes": 4992, "io_hash_ms": 0.35}
    ]
    assert [entry["role_index"] for entry in parsed["role_uploads"]] == list(range(6))
    assert [entry["face"] for entry in parsed["role_uploads"]] == [0] * 6
    assert parsed["ready"]["resident_bytes"] == 9984
    assert parsed["final"] == {
        "left": 1,
        "right": 2,
        "alpha": 0.5,
        "resident_frames": 3,
        "resident_bytes": 14976,
    }
