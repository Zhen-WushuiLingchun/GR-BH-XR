import json
import math
from pathlib import Path

import numpy as np
import pytest

from gr_bh_xr.transfer_keyframes import (
    TIME_INDEXED_TRANSFER_SCHEMA,
    TIME_INDEXED_TRANSFER_SOURCE_SCHEMA,
    TRANSFER_FRAME_GATE_SCHEMA,
    TRANSFER_SEQUENCE_GATE_SCHEMA,
    build_time_indexed_manifest,
    interpolate_discrete_code,
    interpolate_disk_sample,
    interpolate_escape_direction,
    select_time_bracket,
    validate_time_indexed_manifest,
)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _write_frame(root: Path, name: str, *, face_size: int = 2) -> None:
    frame = root / name
    frame.mkdir(parents=True)
    sizes = {
        "eventCubeRgba8": 6 * face_size * face_size * 4,
        "escapeDirUnityCubeRgba32f": 6 * face_size * face_size * 4 * 4,
        "diskTransferCubesRgba16f": [6 * face_size * face_size * 4 * 2] * 2,
        "diskRedshiftCubesRgba16f": [6 * face_size * face_size * 4 * 2] * 2,
    }
    files = {
        "event_cube_rgba8.bytes": sizes["eventCubeRgba8"],
        "escape_dir_unity_cube_rgba32f.bytes": sizes["escapeDirUnityCubeRgba32f"],
        "disk_order0_transfer_cube_rgba16f.bytes": sizes["diskTransferCubesRgba16f"][0],
        "disk_order1_transfer_cube_rgba16f.bytes": sizes["diskTransferCubesRgba16f"][1],
        "disk_order0_redshift_cube_rgba16f.bytes": sizes["diskRedshiftCubesRgba16f"][0],
        "disk_order1_redshift_cube_rgba16f.bytes": sizes["diskRedshiftCubesRgba16f"][1],
    }
    for index, (filename, size) in enumerate(files.items(), start=1):
        (frame / filename).write_bytes(bytes([index]) * size)
    _write_json(
        frame / "full_sky_transfer_metadata.json",
        {
            "schema": "gr-bh-xr.task5.full_sky_transfer_cubemap.v3",
            "faceSize": face_size,
            "faceOrder": [
                "PositiveX",
                "NegativeX",
                "PositiveY",
                "NegativeY",
                "PositiveZ",
                "NegativeZ",
            ],
            "eventCubeRgba8": "event_cube_rgba8.bytes",
            "escapeDirUnityCubeRgba32f": "escape_dir_unity_cube_rgba32f.bytes",
            "diskTransferCubesRgba16f": [
                "disk_order0_transfer_cube_rgba16f.bytes",
                "disk_order1_transfer_cube_rgba16f.bytes",
            ],
            "diskRedshiftCubesRgba16f": [
                "disk_order0_redshift_cube_rgba16f.bytes",
                "disk_order1_redshift_cube_rgba16f.bytes",
            ],
            "bytes": sizes,
        },
    )


def _write_source(root: Path, times=(0.0, 1.0), *, max_gap: float = 1.0) -> Path:
    for index in range(len(times)):
        _write_frame(root, f"frame_{index}")
        _write_json(
            root / f"frame_{index}_gate.json",
            {"schema": TRANSFER_FRAME_GATE_SCHEMA, "passed": True},
        )
    _write_json(
        root / "sequence_gate.json",
        {"schema": TRANSFER_SEQUENCE_GATE_SCHEMA, "passed": True},
    )
    source = root / "sequence_source.json"
    _write_json(
        source,
        {
            "schema": TIME_INDEXED_TRANSFER_SOURCE_SCHEMA,
            "metricSource": {
                "providerSchema": "gr-bh-xr.bbh.adm-snapshot.v1",
                "evidenceLabel": "bounded_nr_fixture",
                "sourceRevision": "fixture-sha",
            },
            "coverage": {
                "expectedStartMetricTimeM": times[0],
                "expectedEndMetricTimeM": times[-1],
                "maxGapM": max_gap,
            },
            "requiredBufferRoles": [
                "event",
                "escape_direction",
                "disk_order0_transfer",
                "disk_order0_redshift",
                "disk_order1_transfer",
                "disk_order1_redshift",
            ],
            "sequenceGateEvidence": "sequence_gate.json",
            "frames": [
                {
                    "metricTimeM": time,
                    "directory": f"frame_{index}",
                    "gateEvidence": f"frame_{index}_gate.json",
                }
                for index, time in enumerate(times)
            ],
        },
    )
    return source


def test_builds_ready_content_addressed_time_sequence(tmp_path):
    source = _write_source(tmp_path)
    output = tmp_path / "asset" / "manifest.json"

    manifest = build_time_indexed_manifest(source, output)

    assert manifest["schema"] == TIME_INDEXED_TRANSFER_SCHEMA
    assert manifest["runtimeAssetReady"] is True
    assert manifest["readinessReasons"] == []
    assert manifest["coverage"]["frameCount"] == 2
    assert manifest["coverage"]["actualMaxGapM"] == pytest.approx(1.0)
    assert len(manifest["frames"][0]["buffers"]["event"]["sha256"]) == 64
    validation = validate_time_indexed_manifest(output)
    assert validation.valid is True
    assert validation.runtime_asset_ready is True


def test_manifest_hash_verification_detects_asset_mutation(tmp_path):
    source = _write_source(tmp_path)
    output = tmp_path / "manifest.json"
    manifest = build_time_indexed_manifest(source, output)
    event_path = output.parent / manifest["frames"][0]["buffers"]["event"]["path"]
    event_path.write_bytes(b"changed")

    validation = validate_time_indexed_manifest(output)

    assert validation.valid is False
    assert validation.runtime_asset_ready is False
    assert any("byte count changed" in error for error in validation.errors)
    assert any("SHA-256 changed" in error for error in validation.errors)


def test_missing_gate_or_time_gap_writes_fail_closed_manifest(tmp_path):
    source = _write_source(tmp_path, times=(0.0, 2.0), max_gap=1.0)
    (tmp_path / "frame_1_gate.json").unlink()

    manifest = build_time_indexed_manifest(source, tmp_path / "manifest.json")

    assert manifest["runtimeAssetReady"] is False
    assert any("frame 1" in reason and "missing" in reason for reason in manifest["readinessReasons"])
    assert any("maxGapM" in reason for reason in manifest["readinessReasons"])
    validation = validate_time_indexed_manifest(tmp_path / "manifest.json")
    assert validation.valid is True
    assert validation.runtime_asset_ready is False


def test_gate_evidence_hash_is_part_of_runtime_readiness(tmp_path):
    source = _write_source(tmp_path)
    output = tmp_path / "manifest.json"
    build_time_indexed_manifest(source, output)
    _write_json(
        tmp_path / "frame_0_gate.json",
        {"schema": TRANSFER_FRAME_GATE_SCHEMA, "passed": False},
    )

    validation = validate_time_indexed_manifest(output)

    assert validation.valid is False
    assert validation.runtime_asset_ready is False
    assert any("gateEvidence SHA-256 changed" in error for error in validation.errors)


def test_manifest_cannot_silently_drop_a_required_buffer(tmp_path):
    source = _write_source(tmp_path)
    output = tmp_path / "manifest.json"
    manifest = build_time_indexed_manifest(source, output)
    del manifest["frames"][1]["buffers"]["disk_order1_redshift"]
    _write_json(output, manifest)

    validation = validate_time_indexed_manifest(output)

    assert validation.valid is False
    assert validation.runtime_asset_ready is False
    assert any("inventory" in error for error in validation.errors)


def test_rejects_legacy_or_static_grid_frame_schema(tmp_path):
    source = _write_source(tmp_path)
    metadata_path = tmp_path / "frame_1" / "full_sky_transfer_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["schema"] = "gr-bh-xr.task7.roam_keyframes.v2"
    _write_json(metadata_path, metadata)

    with pytest.raises(ValueError, match="static roam grids"):
        build_time_indexed_manifest(source, tmp_path / "manifest.json")


def test_time_bracket_is_bounded_and_exact_at_keyframes():
    assert select_time_bracket([0.0, 1.0, 3.0], 0.0) == (0, 0, 0.0)
    assert select_time_bracket([0.0, 1.0, 3.0], 2.0) == (1, 2, 0.5)
    assert select_time_bracket([0.0, 1.0, 3.0], 3.0) == (2, 2, 0.0)
    with pytest.raises(ValueError, match="outside"):
        select_time_bracket([0.0, 1.0], -0.1)
    with pytest.raises(ValueError, match="strictly increasing"):
        select_time_bracket([0.0, 0.0], 0.0)


def test_discrete_events_and_escape_directions_fail_closed():
    assert interpolate_discrete_code(1, 1) == 1
    assert interpolate_discrete_code(0, 1) is None
    direction, valid = interpolate_escape_direction(
        [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], 0.5, left_valid=True, right_valid=True
    )
    assert valid is True
    assert np.linalg.norm(direction) == pytest.approx(1.0)
    assert direction == pytest.approx([math.sqrt(0.5), math.sqrt(0.5), 0.0])
    _, valid = interpolate_escape_direction(
        [1.0, 0.0, 0.0], [-1.0, 0.0, 0.0], 0.5, left_valid=True, right_valid=True
    )
    assert valid is False
    _, valid = interpolate_escape_direction(
        [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], 0.5, left_valid=True, right_valid=False
    )
    assert valid is False


def test_disk_interpolation_preserves_coverage_and_wraps_azimuth():
    phi_left = math.radians(179.0)
    phi_right = math.radians(-179.0)
    coverage_left = 0.5
    coverage_right = 1.0
    left = np.array(
        [6.0 * coverage_left, math.sin(phi_left) * coverage_left, math.cos(phi_left) * coverage_left, coverage_left]
    )
    right = np.array(
        [10.0 * coverage_right, math.sin(phi_right) * coverage_right, math.cos(phi_right) * coverage_right, coverage_right]
    )
    left_g = np.array([0.8 * coverage_left, 0.0, 0.0, 0.0])
    right_g = np.array([1.2 * coverage_right, 0.0, 0.0, 0.0])

    transfer, redshift, valid = interpolate_disk_sample(left, left_g, right, right_g, 0.5)

    assert valid is True
    coverage = transfer[3]
    assert coverage == pytest.approx(0.75)
    assert transfer[0] / coverage == pytest.approx(8.0)
    phase = transfer[1:3] / coverage
    assert phase == pytest.approx([0.0, -1.0], abs=2.0e-4)
    assert redshift[0] / coverage == pytest.approx(1.0)


def test_disk_interpolation_does_not_bridge_missing_image_order():
    valid_transfer = np.array([6.0, 0.0, 1.0, 1.0])
    valid_redshift = np.array([1.0, 0.0, 0.0, 0.0])
    transfer, redshift, valid = interpolate_disk_sample(
        valid_transfer, valid_redshift, np.zeros(4), np.zeros(4), 0.5
    )
    assert valid is False
    assert not np.any(transfer)
    assert not np.any(redshift)
