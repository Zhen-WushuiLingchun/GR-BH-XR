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


def _write_frame(root: Path, index: int, *, face_size: int) -> None:
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

    files = {
        "event_cube_rgba8.bytes": event,
        "escape_dir_unity_cube_rgba32f.bytes": escape,
        "disk_order0_transfer_cube_rgba16f.bytes": disk0,
        "disk_order0_redshift_cube_rgba16f.bytes": redshift0,
        "disk_order1_transfer_cube_rgba16f.bytes": disk1,
        "disk_order1_redshift_cube_rgba16f.bytes": redshift1,
    }
    for filename, array in files.items():
        array.tofile(frame_dir / filename)

    sizes = {
        "eventCubeRgba8": int(event.nbytes),
        "escapeDirUnityCubeRgba32f": int(escape.nbytes),
        "diskTransferCubesRgba16f": [int(disk0.nbytes), int(disk1.nbytes)],
        "diskRedshiftCubesRgba16f": [int(redshift0.nbytes), int(redshift1.nbytes)],
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


def build_fixture(output_dir: Path, *, face_size: int = 4) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    frame_count = 3
    for index in range(frame_count):
        _write_frame(output_dir, index, face_size=face_size)
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
    args = parser.parse_args()
    if args.face_size <= 0:
        raise ValueError("--face-size must be positive")
    print(build_fixture(args.out_dir, face_size=args.face_size))


if __name__ == "__main__":
    main()
