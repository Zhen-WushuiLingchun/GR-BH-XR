"""Build a small, physically meaningful native Vulkan playback fixture."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from gr_bh_xr.transfer_keyframes import (
    TIME_INDEXED_TRANSFER_SOURCE_SCHEMA,
    TRANSFER_FRAME_GATE_SCHEMA,
    TRANSFER_SEQUENCE_GATE_SCHEMA,
    build_time_indexed_manifest,
)


FACE_ORDER = (
    "PositiveX",
    "NegativeX",
    "PositiveY",
    "NegativeY",
    "PositiveZ",
    "NegativeZ",
)
REQUIRED_ROLES = (
    "event",
    "escape_direction",
    "disk_order0_transfer",
    "disk_order0_redshift",
    "disk_order1_transfer",
    "disk_order1_redshift",
)


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def _constant_cube(face_size: int, value: np.ndarray, dtype: str) -> np.ndarray:
    shape = (6, face_size, face_size, 4)
    cube = np.empty(shape, dtype=np.dtype(dtype))
    cube[...] = np.asarray(value, dtype=np.dtype(dtype))
    return cube


def _spatial_probe_cubes(index: int, face_size: int) -> dict[str, np.ndarray]:
    face = np.arange(6, dtype=np.float32)[:, None, None]
    yy, xx = np.indices((face_size, face_size), dtype=np.float32)
    xx = xx[None, ...]
    yy = yy[None, ...]
    linear = (
        np.arange(6, dtype=np.int32)[:, None, None] * face_size * face_size
        + np.arange(face_size, dtype=np.int32)[None, :, None] * face_size
        + np.arange(face_size, dtype=np.int32)[None, None, :]
    )

    raw_direction = np.stack(
        [
            np.broadcast_to(0.45 + 0.11 * face + 0.03 * xx, linear.shape),
            np.broadcast_to(-0.55 + 0.07 * yy - 0.02 * face, linear.shape),
            np.broadcast_to(0.95 + 0.025 * xx + 0.015 * yy, linear.shape),
        ],
        axis=-1,
    ).astype(np.float64)
    angle = 0.37 * index
    cos_angle = math.cos(angle)
    sin_angle = math.sin(angle)
    rotated = raw_direction.copy()
    rotated[..., 0] = cos_angle * raw_direction[..., 0] - sin_angle * raw_direction[..., 1]
    rotated[..., 1] = sin_angle * raw_direction[..., 0] + cos_angle * raw_direction[..., 1]
    rotated /= np.linalg.norm(rotated, axis=-1, keepdims=True)

    event = np.empty((*linear.shape, 4), dtype="u1")
    event[...] = np.array([48, 132, 255, 255], dtype="u1")
    event[linear % 7 == 0] = np.array([0, 0, 0, 255], dtype="u1")
    if index == 1:
        event[linear % 7 == 1] = np.array([0, 0, 0, 255], dtype="u1")

    escape_coverage = np.clip(
        0.35 + 0.1 * index + 0.04 * ((linear + index) % 5), 0.0, 0.95
    ).astype(np.float32)
    escape = np.zeros((*linear.shape, 4), dtype="<f4")
    is_escape = np.all(event == np.array([48, 132, 255, 255], dtype="u1"), axis=-1)
    escape[..., :3] = rotated.astype(np.float32) * escape_coverage[..., None]
    escape[..., 3] = escape_coverage
    escape[~is_escape] = 0.0

    base_phi = math.radians(174.0 if index == 0 else -174.0 + 8.0 * (index - 1))
    phi = base_phi + 0.005 * linear.astype(np.float64)
    radius0 = 5.5 + 3.0 * index + 0.2 * face + 0.025 * xx + 0.015 * yy
    redshift0_value = 0.7 + 0.35 * index + 0.01 * face + 0.002 * xx
    coverage0 = np.clip(
        0.45 + 0.08 * index + 0.03 * ((linear + 2) % 4), 0.0, 0.95
    ).astype(np.float32)
    valid0 = linear % 5 != 2
    coverage0 = np.where(valid0, coverage0, 0.0)
    disk0 = np.zeros((*linear.shape, 4), dtype="<f2")
    disk0[..., 0] = radius0 * coverage0
    disk0[..., 1] = np.sin(phi) * coverage0
    disk0[..., 2] = np.cos(phi) * coverage0
    disk0[..., 3] = coverage0
    redshift0 = np.zeros_like(disk0)
    redshift0[..., 0] = redshift0_value * coverage0

    phi1 = -0.8 + 0.19 * index + 0.011 * linear.astype(np.float64)
    radius1 = 9.0 + 2.0 * index + 0.15 * face + 0.02 * yy
    redshift1_value = 0.55 + 0.25 * index + 0.008 * face
    coverage1 = np.clip(
        0.3 + 0.1 * index + 0.025 * ((linear + 1) % 6), 0.0, 0.9
    ).astype(np.float32)
    valid1 = linear % 4 == 0
    coverage1 = np.where(valid1, coverage1, 0.0)
    disk1 = np.zeros((*linear.shape, 4), dtype="<f2")
    disk1[..., 0] = radius1 * coverage1
    disk1[..., 1] = np.sin(phi1) * coverage1
    disk1[..., 2] = np.cos(phi1) * coverage1
    disk1[..., 3] = coverage1
    redshift1 = np.zeros_like(disk1)
    redshift1[..., 0] = redshift1_value * coverage1

    return {
        "event_cube_rgba8.bytes": event,
        "escape_dir_unity_cube_rgba32f.bytes": escape,
        "disk_order0_transfer_cube_rgba16f.bytes": disk0,
        "disk_order0_redshift_cube_rgba16f.bytes": redshift0,
        "disk_order1_transfer_cube_rgba16f.bytes": disk1,
        "disk_order1_redshift_cube_rgba16f.bytes": redshift1,
    }


def _write_frame(
    root: Path, index: int, *, face_size: int, spatial_probe: bool = False
) -> None:
    frame_dir = root / f"frame_{index}"
    frame_dir.mkdir(parents=True, exist_ok=True)
    directions = (
        (1.0, 0.0, 0.0, 1.0),
        (0.0, 1.0, 0.0, 1.0),
        (0.0, 0.0, 1.0, 1.0),
    )
    coverages = (0.5, 1.0, 0.75)
    radii = (6.0, 10.0, 14.0)
    redshifts = (0.8, 1.2, 0.9)
    phis = tuple(math.radians(value) for value in (179.0, -179.0, -150.0))
    direction = np.array(directions[index], dtype="<f4")
    event = _constant_cube(face_size, np.array([48, 132, 255, 255]), "u1")
    escape = _constant_cube(face_size, direction, "<f4")

    coverage = coverages[index]
    radius = radii[index]
    redshift = redshifts[index]
    phi = phis[index]
    disk0 = _constant_cube(
        face_size,
        np.array(
            [radius * coverage, math.sin(phi) * coverage, math.cos(phi) * coverage, coverage]
        ),
        "<f2",
    )
    redshift0 = _constant_cube(
        face_size, np.array([redshift * coverage, 0.0, 0.0, 0.0]), "<f2"
    )
    disk1 = np.zeros((6, face_size, face_size, 4), dtype="<f2")
    redshift1 = np.zeros_like(disk1)

    files = (
        _spatial_probe_cubes(index, face_size)
        if spatial_probe
        else {
            "event_cube_rgba8.bytes": event,
            "escape_dir_unity_cube_rgba32f.bytes": escape,
            "disk_order0_transfer_cube_rgba16f.bytes": disk0,
            "disk_order0_redshift_cube_rgba16f.bytes": redshift0,
            "disk_order1_transfer_cube_rgba16f.bytes": disk1,
            "disk_order1_redshift_cube_rgba16f.bytes": redshift1,
        }
    )
    for filename, array in files.items():
        array.tofile(frame_dir / filename)

    sizes = {
        "eventCubeRgba8": int(files["event_cube_rgba8.bytes"].nbytes),
        "escapeDirUnityCubeRgba32f": int(
            files["escape_dir_unity_cube_rgba32f.bytes"].nbytes
        ),
        "diskTransferCubesRgba16f": [
            int(files["disk_order0_transfer_cube_rgba16f.bytes"].nbytes),
            int(files["disk_order1_transfer_cube_rgba16f.bytes"].nbytes),
        ],
        "diskRedshiftCubesRgba16f": [
            int(files["disk_order0_redshift_cube_rgba16f.bytes"].nbytes),
            int(files["disk_order1_redshift_cube_rgba16f.bytes"].nbytes),
        ],
    }
    _write_json(
        frame_dir / "full_sky_transfer_metadata.json",
        {
            "schema": "gr-bh-xr.task5.full_sky_transfer_cubemap.v3",
            "faceSize": face_size,
            "faceOrder": list(FACE_ORDER),
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
            "fixturePhysics": {
                "spatialProbe": spatial_probe,
                "escapeDirection": direction.tolist(),
                "diskOrder0": {
                    "radiusM": radius,
                    "phiRadians": phi,
                    "redshift": redshift,
                    "coverage": coverage,
                },
            },
        },
    )
    _write_json(
        root / f"frame_{index}_gate.json",
        {"schema": TRANSFER_FRAME_GATE_SCHEMA, "passed": True, "fixtureOnly": True},
    )


def build_fixture(
    output_dir: Path, *, face_size: int = 4, spatial_probe: bool = False
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    frame_count = 3
    for index in range(frame_count):
        _write_frame(
            output_dir, index, face_size=face_size, spatial_probe=spatial_probe
        )
    _write_json(
        output_dir / "sequence_gate.json",
        {"schema": TRANSFER_SEQUENCE_GATE_SCHEMA, "passed": True, "fixtureOnly": True},
    )
    source = output_dir / "sequence_source.json"
    _write_json(
        source,
        {
            "schema": TIME_INDEXED_TRANSFER_SOURCE_SCHEMA,
            "metricSource": {
                "providerSchema": "gr-bh-xr.fixture.interpolation.v1",
                "evidenceLabel": "native_vulkan_playback_fixture",
                "sourceRevision": "fixture-v1",
            },
            "coverage": {
                "expectedStartMetricTimeM": 0.0,
                "expectedEndMetricTimeM": float(frame_count - 1),
                "maxGapM": 1.0,
            },
            "requiredBufferRoles": list(REQUIRED_ROLES),
            "sequenceGateEvidence": "sequence_gate.json",
            "frames": [
                {
                    "metricTimeM": float(index),
                    "directory": f"frame_{index}",
                    "gateEvidence": f"frame_{index}_gate.json",
                }
                for index in range(frame_count)
            ],
        },
    )
    manifest = output_dir / "manifest.json"
    build_time_indexed_manifest(source, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--face-size", type=int, default=4)
    parser.add_argument(
        "--spatial-probe",
        action="store_true",
        help="write per-face/per-texel values for exact Vulkan readback validation",
    )
    args = parser.parse_args()
    if args.face_size <= 0:
        raise ValueError("--face-size must be positive")
    print(
        build_fixture(
            args.out_dir,
            face_size=args.face_size,
            spatial_probe=args.spatial_probe,
        )
    )


if __name__ == "__main__":
    main()
