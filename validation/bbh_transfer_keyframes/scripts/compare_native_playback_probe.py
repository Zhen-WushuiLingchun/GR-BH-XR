"""Compare native Vulkan transfer interpolation against the Python contract."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from gr_bh_xr.transfer_keyframes import (
    interpolate_disk_sample,
    interpolate_escape_direction,
)


PROBE_SCHEMA = "gr-bh-xr.npgs.transfer-probe.raw.v1"
SUMMARY_SCHEMA = "gr-bh-xr.validation.npgs-transfer-probe.v1"
CAPTURE_RGBA = np.array([0, 0, 0, 255], dtype=np.uint8)
ESCAPE_RGBA = np.array([48, 132, 255, 255], dtype=np.uint8)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_cube(path: Path, dtype: str, face_size: int) -> np.ndarray:
    values = np.fromfile(path, dtype=np.dtype(dtype))
    expected = 6 * face_size * face_size * 4
    if values.size != expected:
        raise ValueError(f"{path} contains {values.size} scalars, expected {expected}")
    return values.reshape(6, face_size, face_size, 4)


def _event_codes(event: np.ndarray) -> np.ndarray:
    capture = np.all(event == CAPTURE_RGBA, axis=-1)
    escape = np.all(event == ESCAPE_RGBA, axis=-1)
    return np.where(capture, 0.0, np.where(escape, 1.0, 3.0)).astype(np.float64)


def _screen_layout(cube: np.ndarray) -> np.ndarray:
    return np.concatenate([cube[face] for face in range(6)], axis=1)


def _load_frame(manifest_path: Path, frame: dict[str, Any], face_size: int) -> dict[str, np.ndarray]:
    base = manifest_path.parent
    roles = {
        "event": ("u1", "event"),
        "escape_direction": ("<f4", "escape_direction"),
        "disk_order0_transfer": ("<f2", "disk_order0_transfer"),
        "disk_order0_redshift": ("<f2", "disk_order0_redshift"),
        "disk_order1_transfer": ("<f2", "disk_order1_transfer"),
        "disk_order1_redshift": ("<f2", "disk_order1_redshift"),
    }
    return {
        name: _load_cube(base / frame["buffers"][key]["path"], dtype, face_size)
        for name, (dtype, key) in roles.items()
    }


def expected_probe_records(manifest_path: Path, probe_metadata: dict[str, Any]) -> np.ndarray:
    manifest = _read_json(manifest_path)
    face_size = int(probe_metadata["face_size"])
    bracket = probe_metadata["bracket"]
    left = _load_frame(manifest_path, manifest["frames"][int(bracket["left_index"])], face_size)
    right = _load_frame(manifest_path, manifest["frames"][int(bracket["right_index"])], face_size)
    alpha = float(bracket["alpha"])
    height = face_size
    width = 6 * face_size
    records = np.zeros((height, width, int(probe_metadata["record_float_count"])), dtype=np.float64)

    event_a_cube = _event_codes(left["event"])
    event_b_cube = _event_codes(right["event"])
    event_a = _screen_layout(event_a_cube)
    event_b = _screen_layout(event_b_cube)
    matching = (event_a == event_b) & np.isin(event_a, (0.0, 1.0))

    for face in range(6):
        for y in range(face_size):
            for x in range(face_size):
                screen_x = face * face_size + x
                record = records[y, screen_x]
                record[0:4] = (face, x, y, alpha)
                record[4:8] = (event_a[y, screen_x], event_b[y, screen_x], matching[y, screen_x], alpha)
                if not matching[y, screen_x]:
                    continue

                packed_a = left["escape_direction"][face, y, x].astype(np.float64)
                packed_b = right["escape_direction"][face, y, x].astype(np.float64)
                coverage_a = float(np.clip(packed_a[3], 0.0, 1.0))
                coverage_b = float(np.clip(packed_b[3], 0.0, 1.0))
                valid_a = coverage_a > 1.0e-4 and np.linalg.norm(packed_a[:3] / coverage_a) > 1.0e-5
                valid_b = coverage_b > 1.0e-4 and np.linalg.norm(packed_b[:3] / coverage_b) > 1.0e-5
                endpoint_a = packed_a[:3] / coverage_a if valid_a else np.zeros(3)
                endpoint_b = packed_b[:3] / coverage_b if valid_b else np.zeros(3)
                endpoint_dot = (
                    float(np.dot(endpoint_a / np.linalg.norm(endpoint_a), endpoint_b / np.linalg.norm(endpoint_b)))
                    if valid_a and valid_b
                    else -2.0
                )
                record[13:16] = (coverage_a, coverage_b, endpoint_dot)
                direction, escape_valid = interpolate_escape_direction(
                    endpoint_a,
                    endpoint_b,
                    alpha,
                    left_valid=valid_a and event_a[y, screen_x] == 1.0,
                    right_valid=valid_b and event_b[y, screen_x] == 1.0,
                )
                if escape_valid:
                    record[8:12] = (*direction, (1.0 - alpha) * coverage_a + alpha * coverage_b)
                    record[12] = 1.0

                for order, value_offset, meta_offset in ((0, 16, 20), (1, 24, 28)):
                    left_t = left[f"disk_order{order}_transfer"][face, y, x].astype(np.float64)
                    left_g = left[f"disk_order{order}_redshift"][face, y, x].astype(np.float64)
                    right_t = right[f"disk_order{order}_transfer"][face, y, x].astype(np.float64)
                    right_g = right[f"disk_order{order}_redshift"][face, y, x].astype(np.float64)
                    transfer, redshift, valid = interpolate_disk_sample(
                        left_t, left_g, right_t, right_g, alpha, min_coverage=1.0e-4
                    )
                    record[meta_offset + 2 : meta_offset + 4] = (
                        np.clip(left_t[3], 0.0, 1.0),
                        np.clip(right_t[3], 0.0, 1.0),
                    )
                    if valid:
                        coverage = float(transfer[3])
                        record[value_offset : value_offset + 4] = (
                            transfer[0] / coverage,
                            transfer[1] / coverage,
                            transfer[2] / coverage,
                            redshift[0] / coverage,
                        )
                        record[meta_offset : meta_offset + 2] = (1.0, coverage)
    return records


def _max_abs(actual: np.ndarray, expected: np.ndarray, mask: np.ndarray | None = None) -> float:
    values = np.abs(actual - expected)
    if mask is not None:
        values = values[mask]
    return float(np.max(values)) if values.size else 0.0


def compare_probe(raw_path: Path, manifest_path: Path) -> dict[str, Any]:
    metadata_path = Path(str(raw_path) + ".json")
    metadata = _read_json(metadata_path)
    if metadata.get("schema") != PROBE_SCHEMA:
        raise ValueError(f"unsupported transfer probe schema: {metadata.get('schema')!r}")
    height = int(metadata["height"])
    width = int(metadata["width"])
    record_count = int(metadata["record_float_count"])
    actual = np.fromfile(raw_path, dtype="<f4")
    expected_scalars = height * width * record_count
    if actual.size != expected_scalars:
        raise ValueError(f"probe raw has {actual.size} floats, expected {expected_scalars}")
    actual = actual.reshape(height, width, record_count).astype(np.float64)
    expected = expected_probe_records(manifest_path, metadata)

    texel_mismatch = int(np.count_nonzero(np.any(np.abs(actual[..., 0:4] - expected[..., 0:4]) > 1.0e-6, axis=-1)))
    event_mismatch = int(np.count_nonzero(np.any(np.abs(actual[..., 4:8] - expected[..., 4:8]) > 1.0e-6, axis=-1)))
    escape_valid_mismatch = int(np.count_nonzero(actual[..., 12] != expected[..., 12]))
    disk0_valid_mismatch = int(np.count_nonzero(actual[..., 20] != expected[..., 20]))
    disk1_valid_mismatch = int(np.count_nonzero(actual[..., 28] != expected[..., 28]))

    escape_mask = expected[..., 12] > 0.5
    if np.any(escape_mask):
        actual_direction = actual[..., 8:11][escape_mask].copy()
        expected_direction = expected[..., 8:11][escape_mask].copy()
        actual_direction /= np.linalg.norm(actual_direction, axis=-1, keepdims=True)
        expected_direction /= np.linalg.norm(expected_direction, axis=-1, keepdims=True)
        dot = np.sum(actual_direction * expected_direction, axis=-1)
        escape_angle = np.arccos(np.clip(dot, -1.0, 1.0))
        escape_max_angle = float(np.max(escape_angle))
    else:
        escape_max_angle = 0.0
    disk0_mask = np.broadcast_to((expected[..., 20] > 0.5)[..., None], expected[..., 16:20].shape)
    disk1_mask = np.broadcast_to((expected[..., 28] > 0.5)[..., None], expected[..., 24:28].shape)

    metrics = {
        "texel_identity_mismatches": texel_mismatch,
        "event_mismatches": event_mismatch,
        "escape_validity_mismatches": escape_valid_mismatch,
        "disk0_validity_mismatches": disk0_valid_mismatch,
        "disk1_validity_mismatches": disk1_valid_mismatch,
        "escape_direction_max_angle_rad": escape_max_angle,
        "escape_coverage_max_abs": _max_abs(actual[..., 11], expected[..., 11], escape_mask),
        "escape_endpoint_meta_max_abs": _max_abs(actual[..., 13:16], expected[..., 13:16]),
        "disk0_physical_max_abs": _max_abs(actual[..., 16:20], expected[..., 16:20], disk0_mask),
        "disk0_meta_max_abs": _max_abs(actual[..., 21:24], expected[..., 21:24]),
        "disk1_physical_max_abs": _max_abs(actual[..., 24:28], expected[..., 24:28], disk1_mask),
        "disk1_meta_max_abs": _max_abs(actual[..., 29:32], expected[..., 29:32]),
        "nonfinite_actual": int(np.count_nonzero(~np.isfinite(actual))),
    }
    thresholds = {
        "escape_direction_max_angle_rad": 5.0e-4,
        "continuous_max_abs": 5.0e-4,
    }
    passed = (
        all(metrics[key] == 0 for key in (
            "texel_identity_mismatches",
            "event_mismatches",
            "escape_validity_mismatches",
            "disk0_validity_mismatches",
            "disk1_validity_mismatches",
            "nonfinite_actual",
        ))
        and escape_max_angle < thresholds["escape_direction_max_angle_rad"]
        and max(
            metrics["escape_coverage_max_abs"],
            metrics["escape_endpoint_meta_max_abs"],
            metrics["disk0_physical_max_abs"],
            metrics["disk0_meta_max_abs"],
            metrics["disk1_physical_max_abs"],
            metrics["disk1_meta_max_abs"],
        ) < thresholds["continuous_max_abs"]
    )
    return {
        "schema": SUMMARY_SCHEMA,
        "passed": passed,
        "probe": str(raw_path),
        "manifest": str(manifest_path),
        "face_size": int(metadata["face_size"]),
        "bracket": metadata["bracket"],
        "samples": height * width,
        "metrics": metrics,
        "thresholds": thresholds,
        "claim_boundary": (
            "This validates the native Vulkan playback/interpolation implementation on a "
            "synthetic spatial fixture; it does not certify a production BBH keyframe sequence."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    summary = compare_probe(args.raw.resolve(), args.manifest.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
