"""Generate a full-sky GPU transfer cubemap for Unity lookup."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np

from gr_bh_xr.gpu.codes import SCHEMA_EVENT_CODES
from gr_bh_xr.gpu.trace import GpuTraceConfig, event_to_rgba8, trace_unity_direction_points
from gr_bh_xr.sky import escape_direction_arrays
from gr_bh_xr.types import MetricParams, TraceConfig
from gr_bh_xr.xr.export_unity_textures import unity_basis_from_inclination


FULL_SKY_PACKAGE_SCHEMA = "gr-bh-xr.task5.full_sky_transfer_cubemap.v1"
UNITY_CUBE_FACES = ("PositiveX", "NegativeX", "PositiveY", "NegativeY", "PositiveZ", "NegativeZ")


def generate_transfer_cubemap(
    *,
    params: MetricParams,
    inclination_deg: float,
    face_size: int,
    out_dir: Path | str,
    r_obs: float,
    step_size: float,
    steps: int,
    horizon_eps: float,
    chunk_size: int,
    command: str = "",
) -> dict[str, Any]:
    """Generate raw Unity cubemap bytes for all view directions."""

    if face_size < 2:
        raise ValueError("face_size must be at least 2.")
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive.")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    config = GpuTraceConfig(
        params=params,
        inclination_deg=inclination_deg,
        grid=2,
        alpha_max=1.0,
        beta_max=1.0,
        r_obs=r_obs,
        step_size=step_size,
        steps=steps,
        horizon_eps=horizon_eps,
        critical_refine_band=0.0,
        critical_refine_factor=1,
    )
    basis = unity_basis_from_inclination(inclination_deg)
    pixels_per_face = face_size * face_size
    total_pixels = pixels_per_face * len(UNITY_CUBE_FACES)
    event_cube = np.zeros((len(UNITY_CUBE_FACES), face_size, face_size, 4), dtype=np.uint8)
    dir_cube = np.zeros((len(UNITY_CUBE_FACES), face_size, face_size, 4), dtype=np.float32)

    backend: dict[str, Any] | None = None
    event_counts = {name: 0 for name in SCHEMA_EVENT_CODES}
    failure_counts: dict[str, int] = {}
    for face_index, face_name in enumerate(UNITY_CUBE_FACES):
        directions = _face_directions(face_name, face_size)
        face_event = np.zeros((pixels_per_face,), dtype=np.int16)
        face_failure = np.zeros((pixels_per_face,), dtype=np.int16)
        face_dir = np.zeros((pixels_per_face, 4), dtype=np.float32)
        for start in range(0, pixels_per_face, chunk_size):
            end = min(start + chunk_size, pixels_per_face)
            result = trace_unity_direction_points(config, directions[start:end])
            backend = result["backend"]
            event_code = result["event_code"].astype(np.int16)
            failure_code = result["failure_code"].astype(np.int16)
            escape = escape_direction_arrays(
                params=params,
                event_code=event_code,
                r=result["final_r"],
                theta=result["final_theta"],
                phi=result["final_phi"],
                p_t=result["final_p_t"],
                p_r=result["final_p_r"],
                p_theta=result["final_p_theta"],
                p_phi=result["final_p_phi"],
                escape_code=SCHEMA_EVENT_CODES["escape"],
            )
            dir_bh = np.stack(escape[2:], axis=-1)
            valid = (event_code == SCHEMA_EVENT_CODES["escape"]) & np.all(np.isfinite(dir_bh), axis=-1)
            dir_unity = _bh_to_unity(dir_bh, valid, basis)
            packed = np.zeros((end - start, 4), dtype=np.float32)
            packed[valid, :3] = dir_unity[valid]
            packed[valid, 3] = 1.0
            face_event[start:end] = event_code
            face_failure[start:end] = failure_code
            face_dir[start:end] = packed
            for name, code in SCHEMA_EVENT_CODES.items():
                event_counts[name] += int(np.count_nonzero(event_code == code))
            for code in np.unique(failure_code):
                failure_counts[str(int(code))] = failure_counts.get(str(int(code)), 0) + int(
                    np.count_nonzero(failure_code == code)
                )
        event_cube[face_index] = event_to_rgba8(
            face_event.reshape((face_size, face_size)),
            face_failure.reshape((face_size, face_size)),
        )
        dir_cube[face_index] = face_dir.reshape((face_size, face_size, 4))

    event_path = out_dir / "event_cube_rgba8.bytes"
    dir_path = out_dir / "escape_dir_unity_cube_rgba32f.bytes"
    metadata_path = out_dir / "full_sky_transfer_metadata.json"
    event_cube.tofile(event_path)
    dir_cube.astype("<f4", copy=False).tofile(dir_path)
    metadata = {
        "schema": FULL_SKY_PACKAGE_SCHEMA,
        "generationCommand": command,
        "faceSize": face_size,
        "faceOrder": list(UNITY_CUBE_FACES),
        "eventCubeRgba8": event_path.name,
        "escapeDirUnityCubeRgba32f": dir_path.name,
        "bytes": {
            "eventCubeRgba8": int(event_cube.nbytes),
            "escapeDirUnityCubeRgba32f": int(dir_cube.nbytes),
        },
        "metric": {"M": params.M, "a": params.a},
        "observer": {
            "r_obs": r_obs,
            "inclination_deg": inclination_deg,
            "theta_obs_rad": math.radians(inclination_deg),
            "tetrad": "finite-radius static observer; Unity +z is radially inward",
        },
        "integration": {
            "step_size": step_size,
            "steps": steps,
            "lambda_budget": step_size * steps,
            "horizon_eps": horizon_eps,
        },
        "backend": backend,
        "eventCounts": event_counts,
        "failureCountsByCode": failure_counts,
        "totalPixels": total_pixels,
        "validEscapePixels": int(np.count_nonzero(dir_cube[..., 3] >= 0.5)),
        "boundaryNote": (
            "Full-sky cubemap has no alpha/beta window fallback. Every cubemap texel is traced "
            "from the same finite observer tetrad, so there is no square hard boundary."
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf8")
    return metadata


def _face_directions(face_name: str, face_size: int) -> np.ndarray:
    coords = (np.arange(face_size, dtype=np.float32) + 0.5) / float(face_size)
    u = 2.0 * coords - 1.0
    v = 2.0 * coords - 1.0
    uu, vv = np.meshgrid(u, v)
    if face_name == "PositiveX":
        dirs = np.stack([np.ones_like(uu), -vv, -uu], axis=-1)
    elif face_name == "NegativeX":
        dirs = np.stack([-np.ones_like(uu), -vv, uu], axis=-1)
    elif face_name == "PositiveY":
        dirs = np.stack([uu, np.ones_like(uu), vv], axis=-1)
    elif face_name == "NegativeY":
        dirs = np.stack([uu, -np.ones_like(uu), -vv], axis=-1)
    elif face_name == "PositiveZ":
        dirs = np.stack([uu, -vv, np.ones_like(uu)], axis=-1)
    elif face_name == "NegativeZ":
        dirs = np.stack([-uu, -vv, -np.ones_like(uu)], axis=-1)
    else:
        raise ValueError(f"Unknown Unity cubemap face: {face_name}")
    norm = np.linalg.norm(dirs, axis=-1, keepdims=True)
    return (dirs / norm).reshape((-1, 3)).astype(np.float32)


def _bh_to_unity(dir_bh: np.ndarray, valid: np.ndarray, basis: Any) -> np.ndarray:
    dir_unity = np.zeros(dir_bh.shape, dtype=np.float32)
    if not np.any(valid):
        return dir_unity
    vectors = dir_bh[valid].astype(np.float64)
    mapped = np.stack(
        [
            vectors @ basis.right_bh,
            vectors @ basis.up_bh,
            vectors @ basis.forward_bh,
        ],
        axis=-1,
    )
    norm = np.linalg.norm(mapped, axis=-1)
    good = np.isfinite(norm) & (norm > 0.0)
    local = np.flatnonzero(valid)
    if np.any(good):
        dir_unity.reshape((-1, 3))[local[good]] = (
            mapped[good] / norm[good, np.newaxis]
        ).astype(np.float32)
    return dir_unity


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True)
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, required=True)
    parser.add_argument("--face-size", type=int, default=256)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--step-size", type=float, default=GpuTraceConfig.step_size)
    parser.add_argument("--steps", type=int, default=GpuTraceConfig.steps)
    parser.add_argument("--horizon-eps", type=float, default=TraceConfig.horizon_eps)
    parser.add_argument("--chunk-size", type=int, default=262144)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = generate_transfer_cubemap(
        params=MetricParams(M=args.mass, a=args.spin * args.mass),
        inclination_deg=args.inclination_deg,
        face_size=args.face_size,
        out_dir=args.out_dir,
        r_obs=args.r_obs,
        step_size=args.step_size,
        steps=args.steps,
        horizon_eps=args.horizon_eps,
        chunk_size=args.chunk_size,
        command=" ".join(sys.argv),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
