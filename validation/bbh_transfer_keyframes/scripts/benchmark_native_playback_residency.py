"""Benchmark native NPGS transfer-keyframe prefetch and Vulkan uploads."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any

import numpy as np

try:
    from .build_native_playback_fixture import build_fixture
except ImportError:  # Direct script execution.
    from build_native_playback_fixture import build_fixture


SUMMARY_SCHEMA = "gr-bh-xr.validation.npgs-transfer-residency.v2"
RESIDENT_RE = re.compile(
    r"NPGS_TRANSFER_RESIDENT slot=(?P<slot>\d+) frame=(?P<frame>\d+) "
    r"metric_time_M=(?P<time>[-+0-9.eE]+) bytes=(?P<bytes>\d+) "
    r"io_hash_ms=(?P<io_hash>[-+0-9.eE]+) "
    r"upload_ms=(?P<upload>[-+0-9.eE]+) total_ms=(?P<total>[-+0-9.eE]+)"
)
PREFETCH_RE = re.compile(
    r"NPGS_TRANSFER_PREFETCH frame=(?P<frame>\d+) bytes=(?P<bytes>\d+) "
    r"io_hash_ms=(?P<io_hash>[-+0-9.eE]+)"
)
READY_RE = re.compile(
    r"NPGS_TRANSFER_PLAYBACK_READY face_size=(?P<face>\d+) "
    r"resident_frames=(?P<frames>\d+) resident_bytes=(?P<bytes>\d+)"
)
OK_RE = re.compile(
    r"NPGS_TRANSFER_PLAYBACK_OK left=(?P<left>\d+) right=(?P<right>\d+) "
    r"alpha=(?P<alpha>[-+0-9.eE]+) resident_frames=(?P<frames>\d+) "
    r"resident_bytes=(?P<bytes>\d+)"
)


def parse_native_output(output: str) -> dict[str, Any]:
    uploads = [
        {
            "slot": int(match.group("slot")),
            "frame": int(match.group("frame")),
            "metric_time_M": float(match.group("time")),
            "bytes": int(match.group("bytes")),
            "io_hash_ms": float(match.group("io_hash")),
            "upload_ms": float(match.group("upload")),
            "total_ms": float(match.group("total")),
        }
        for match in RESIDENT_RE.finditer(output)
    ]
    ready_match = READY_RE.search(output)
    ok_match = OK_RE.search(output)
    if ready_match is None or ok_match is None:
        raise ValueError("native playback output is missing READY or OK markers")
    prefetches = [
        {
            "frame": int(match.group("frame")),
            "bytes": int(match.group("bytes")),
            "io_hash_ms": float(match.group("io_hash")),
        }
        for match in PREFETCH_RE.finditer(output)
    ]
    return {
        "uploads": uploads,
        "prefetches": prefetches,
        "ready": {
            "face_size": int(ready_match.group("face")),
            "resident_frames": int(ready_match.group("frames")),
            "resident_bytes": int(ready_match.group("bytes")),
        },
        "final": {
            "left": int(ok_match.group("left")),
            "right": int(ok_match.group("right")),
            "alpha": float(ok_match.group("alpha")),
            "resident_frames": int(ok_match.group("frames")),
            "resident_bytes": int(ok_match.group("bytes")),
        },
    }


def _frame_bytes(metadata_path: Path) -> int:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    sizes = metadata["bytes"]
    return int(
        sizes["eventCubeRgba8"]
        + sizes["escapeDirUnityCubeRgba32f"]
        + sum(sizes["diskTransferCubesRgba16f"])
        + sum(sizes["diskRedshiftCubesRgba16f"])
    )


def _percentile(values: list[float], percentile: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))


def run_benchmark(
    *,
    repo_root: Path,
    npgs_exe: Path,
    output_dir: Path,
    face_sizes: list[int],
    iterations: int,
) -> dict[str, Any]:
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    data_root = repo_root / "runtime" / "NPGS" / "NPGS"
    cases: list[dict[str, Any]] = []

    for face_size in face_sizes:
        if face_size <= 0:
            raise ValueError("face sizes must be positive")
        case_dir = output_dir / f"face_{face_size}"
        manifest = build_fixture(case_dir / "fixture", face_size=face_size)
        frame_bytes = _frame_bytes(
            case_dir / "fixture" / "frame_0" / "full_sky_transfer_metadata.json"
        )
        expected_ready_bytes = 2 * frame_bytes
        expected_final_bytes = 3 * frame_bytes
        runs: list[dict[str, Any]] = []

        for iteration in range(iterations):
            command = [
                str(npgs_exe),
                "--windowed",
                "--width",
                "64",
                "--height",
                "64",
                "--transfer-keyframes",
                str(manifest.resolve()),
                "--transfer-time-M",
                "0.5",
                "--transfer-keyframe-smoke",
            ]
            start = time.perf_counter()
            completed = subprocess.run(
                command,
                cwd=data_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            wall_ms = (time.perf_counter() - start) * 1000.0
            combined = completed.stdout + "\n" + completed.stderr
            (case_dir / f"native_iteration_{iteration}.log").write_text(
                combined, encoding="utf-8"
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    f"NPGS benchmark failed for face {face_size}, iteration "
                    f"{iteration}, exit {completed.returncode}"
                )
            parsed = parse_native_output(combined)
            uploads = parsed["uploads"]
            if [(entry["slot"], entry["frame"]) for entry in uploads] != [
                (0, 0),
                (1, 1),
                (2, 2),
            ]:
                raise RuntimeError(f"unexpected upload sequence for face {face_size}: {uploads}")
            if any(entry["bytes"] != frame_bytes for entry in uploads):
                raise RuntimeError(f"native byte count disagrees with manifest for face {face_size}")
            if parsed["ready"] != {
                "face_size": face_size,
                "resident_frames": 2,
                "resident_bytes": expected_ready_bytes,
            }:
                raise RuntimeError(f"unexpected READY marker for face {face_size}: {parsed['ready']}")
            if parsed["final"] != {
                "left": 1,
                "right": 2,
                "alpha": 0.5,
                "resident_frames": 3,
                "resident_bytes": expected_final_bytes,
            }:
                raise RuntimeError(f"unexpected final bracket for face {face_size}: {parsed['final']}")
            runs.append(
                {
                    "iteration": iteration,
                    "wall_ms": wall_ms,
                    "uploads": uploads,
                    "prefetches": parsed["prefetches"],
                    "transition_io_hash_ms": uploads[2]["io_hash_ms"],
                    "transition_upload_ms": uploads[2]["upload_ms"],
                    "transition_total_ms": uploads[2]["total_ms"],
                }
            )

        upload_values = [
            entry["upload_ms"] for run in runs for entry in run["uploads"]
        ]
        transition_values = [run["transition_upload_ms"] for run in runs]
        transition_p95 = _percentile(transition_values, 95.0)
        cases.append(
            {
                "face_size": face_size,
                "frame_bytes": frame_bytes,
                "ready_resident_bytes": expected_ready_bytes,
                "peak_resident_bytes": expected_final_bytes,
                "peak_resident_mib": expected_final_bytes / (1024.0 * 1024.0),
                "iterations": iterations,
                "upload_ms": {
                    "p50": _percentile(upload_values, 50.0),
                    "p95": _percentile(upload_values, 95.0),
                    "max": max(upload_values),
                },
                "transition_upload_ms": {
                    "p50": _percentile(transition_values, 50.0),
                    "p95": transition_p95,
                    "max": max(transition_values),
                },
                "transition_io_hash_ms": {
                    "p50": _percentile(
                        [run["transition_io_hash_ms"] for run in runs], 50.0
                    ),
                    "p95": _percentile(
                        [run["transition_io_hash_ms"] for run in runs], 95.0
                    ),
                },
                "process_wall_ms": {
                    "p50": _percentile([run["wall_ms"] for run in runs], 50.0),
                    "p95": _percentile([run["wall_ms"] for run in runs], 95.0),
                },
                "hitch_free_candidate": {
                    "72_hz_physics_budget_11ms": transition_p95 < 11.0,
                    "90_hz_physics_budget_9ms": transition_p95 < 9.0,
                },
                "runs": runs,
            }
        )

    passes_72_hz = all(
        case["hitch_free_candidate"]["72_hz_physics_budget_11ms"] for case in cases
    )
    passes_90_hz = all(
        case["hitch_free_candidate"]["90_hz_physics_budget_9ms"] for case in cases
    )
    return {
        "schema": SUMMARY_SCHEMA,
        "passed": passes_72_hz and passes_90_hz,
        "correctness_passed": True,
        "production_hitch_free_passed": {
            "72_hz": passes_72_hz,
            "90_hz": passes_90_hz,
        },
        "npgs_executable": str(npgs_exe.resolve()),
        "gpu_evidence": "Read the Renderer line in each persisted native log.",
        "cases": cases,
        "claim_boundary": (
            "Asset bytes are read and hashed by the CPU prefetch worker. The measured "
            "transition upload remains synchronous Vulkan image creation on the render "
            "thread; it is not a render GPU timestamp and does not establish OpenXR "
            "frame rate. A false hitch-free candidate still requires asynchronous GPU "
            "staging before production playback."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    default_exe = (
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "GRBHXR"
        / "native-build-root"
        / "runtime"
        / "NPGS"
        / "x64"
        / "Release"
        / "NPGS.exe"
    )
    parser.add_argument("--npgs-exe", type=Path, default=default_exe)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--face-sizes", type=int, nargs="+", default=[256, 512, 1024])
    parser.add_argument("--iterations", type=int, default=3)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    if not args.npgs_exe.is_file():
        raise FileNotFoundError(f"NPGS executable is missing: {args.npgs_exe}")
    summary = run_benchmark(
        repo_root=repo_root,
        npgs_exe=args.npgs_exe,
        output_dir=args.out_dir.resolve(),
        face_sizes=args.face_sizes,
        iterations=args.iterations,
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    output = args.out_dir / "native_residency_benchmark.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
