"""Validate full-sky finite-observer GPU tracing against the CPU reference."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import h5py
import numpy as np

from gr_bh_xr.camera import initial_ray_state_from_unity_direction
from gr_bh_xr.generate_lens_map import EVENT_CODES, FAILURE_CODES
from gr_bh_xr.geodesic import trace_state
from gr_bh_xr.gpu.generate_transfer_cubemap import UNITY_CUBE_FACES, _face_directions
from gr_bh_xr.gpu.trace import GpuTraceConfig, trace_unity_direction_points
from gr_bh_xr.metric import horizon_radius
from gr_bh_xr.sky import angular_error_from_dirs, escape_direction_arrays
from gr_bh_xr.types import MetricParams, TraceConfig


def validate_full_sky_transfer(
    *,
    params: MetricParams,
    inclination_deg: float,
    samples: int,
    r_obs: float,
    step_size: float,
    steps: int,
    horizon_eps: float,
    out: Path | str,
    h5: Path | str | None = None,
    command: str = "",
) -> dict[str, Any]:
    """Compare CPU and GPU finite-observer tracing on deterministic sky samples."""

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    directions = sample_full_sky_directions(samples)
    gpu_config = GpuTraceConfig(
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
    gpu = trace_unity_direction_points(gpu_config, directions.astype(np.float32))
    cpu = _trace_cpu_directions(
        params=params,
        inclination_deg=inclination_deg,
        directions=directions,
        r_obs=r_obs,
        step_size=step_size,
        steps=steps,
        horizon_eps=horizon_eps,
    )
    comparison = _compare_full_sky(
        params=params,
        cpu=cpu,
        gpu=gpu,
        horizon_eps=horizon_eps,
    )
    summary: dict[str, Any] = {
        "schema": "gr-bh-xr.task5.full_sky_cpu_gpu_validation.v1",
        "generationCommand": command,
        "metric": {"M": params.M, "a": params.a},
        "inclination_deg": inclination_deg,
        "samples": int(directions.shape[0]),
        "r_obs": r_obs,
        "step_size": step_size,
        "steps": steps,
        "horizon_eps": horizon_eps,
        "backend": gpu["backend"],
        "cpu_event_counts": _counts(cpu["event_code"], EVENT_CODES),
        "cpu_failure_counts": _counts(cpu["failure_code"], FAILURE_CODES),
        "gpu_event_counts": _counts(gpu["event_code"], EVENT_CODES),
        "gpu_failure_counts": _counts(gpu["failure_code"], FAILURE_CODES),
        **comparison["summary"],
    }
    out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
    if h5 is not None:
        _write_h5(Path(h5), directions, cpu, gpu, comparison, summary)
    return summary


def sample_full_sky_directions(samples: int) -> np.ndarray:
    """Return deterministic Unity local directions sampled from cubemap faces."""

    if samples < len(UNITY_CUBE_FACES):
        raise ValueError(f"samples must be at least {len(UNITY_CUBE_FACES)}.")
    axes = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, -1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, 0.0, -1.0],
        ],
        dtype=np.float64,
    )
    if samples == len(UNITY_CUBE_FACES):
        return axes
    face_size = max(2, int(math.ceil(math.sqrt(samples / len(UNITY_CUBE_FACES)))))
    grid = np.concatenate(
        [_face_directions(face_name, face_size) for face_name in UNITY_CUBE_FACES], axis=0
    ).astype(np.float64)
    needed = samples - axes.shape[0]
    if grid.shape[0] > needed:
        indices = np.linspace(0, grid.shape[0] - 1, needed, dtype=np.int64)
        grid = grid[indices]
    directions = np.concatenate([axes, grid], axis=0)
    return directions.astype(np.float64)


def _trace_cpu_directions(
    *,
    params: MetricParams,
    inclination_deg: float,
    directions: np.ndarray,
    r_obs: float,
    step_size: float,
    steps: int,
    horizon_eps: float,
) -> dict[str, np.ndarray]:
    theta_obs = math.radians(inclination_deg)
    config = TraceConfig(
        max_lambda=step_size * steps,
        r_escape=2.0 * r_obs,
        horizon_eps=horizon_eps,
        max_step=2.0,
    )
    event_code = np.zeros(directions.shape[0], dtype=np.int16)
    failure_code = np.zeros(directions.shape[0], dtype=np.int16)
    min_r = np.full(directions.shape[0], np.nan, dtype=np.float64)
    escape_dir = np.full((directions.shape[0], 3), np.nan, dtype=np.float64)
    h_max_abs = np.full(directions.shape[0], np.nan, dtype=np.float64)
    q_drift_abs = np.full(directions.shape[0], np.nan, dtype=np.float64)
    lambda_end = np.full(directions.shape[0], np.nan, dtype=np.float64)
    for idx, direction in enumerate(directions):
        state = initial_ray_state_from_unity_direction(
            params,
            r_obs=r_obs,
            theta_obs=theta_obs,
            direction_unity=direction,
        )
        diag = trace_state(params, state, config, r_obs=r_obs)
        event_code[idx] = EVENT_CODES[diag.event]
        failure_code[idx] = FAILURE_CODES[diag.failure_reason]
        min_r[idx] = diag.min_r
        escape_dir[idx] = (diag.escape_dir_x, diag.escape_dir_y, diag.escape_dir_z)
        h_max_abs[idx] = diag.h_max_abs
        q_drift_abs[idx] = diag.q_drift_abs
        lambda_end[idx] = diag.lambda_end
    return {
        "event_code": event_code,
        "failure_code": failure_code,
        "min_r": min_r,
        "escape_dir": escape_dir,
        "h_max_abs": h_max_abs,
        "q_drift_abs": q_drift_abs,
        "lambda_end": lambda_end,
    }


def _compare_full_sky(
    *,
    params: MetricParams,
    cpu: dict[str, np.ndarray],
    gpu: dict[str, Any],
    horizon_eps: float,
) -> dict[str, Any]:
    near_capture_radius = horizon_radius(params) + max(0.1 * params.M, 2.0 * horizon_eps)
    cpu_ok = cpu["failure_code"] == FAILURE_CODES["none"]
    near_capture = cpu["min_r"] <= near_capture_radius
    stable = cpu_ok & ~near_capture
    event_agreement_mask = cpu["event_code"] == gpu["event_code"]
    stable_count = int(np.count_nonzero(stable))
    stable_agreement_count = int(np.count_nonzero(event_agreement_mask & stable))
    full_count = int(cpu["event_code"].size)
    full_agreement_count = int(np.count_nonzero(event_agreement_mask))
    gpu_failure_outside_exclusions = (gpu["failure_code"] != FAILURE_CODES["none"]) & stable
    gpu_escape = escape_direction_arrays(
        params=params,
        event_code=gpu["event_code"],
        r=gpu["final_r"],
        theta=gpu["final_theta"],
        phi=gpu["final_phi"],
        p_t=gpu["final_p_t"],
        p_r=gpu["final_p_r"],
        p_theta=gpu["final_p_theta"],
        p_phi=gpu["final_p_phi"],
        escape_code=EVENT_CODES["escape"],
    )
    gpu_escape_dir = np.stack(gpu_escape[2:], axis=-1)
    direction_error = np.full(cpu["event_code"].shape, np.nan, dtype=np.float64)
    escape_mask = (
        stable
        & (cpu["event_code"] == EVENT_CODES["escape"])
        & (gpu["event_code"] == EVENT_CODES["escape"])
        & np.all(np.isfinite(cpu["escape_dir"]), axis=-1)
        & np.all(np.isfinite(gpu_escape_dir), axis=-1)
    )
    if np.any(escape_mask):
        direction_error[escape_mask] = angular_error_from_dirs(
            cpu["escape_dir"][escape_mask, 0],
            cpu["escape_dir"][escape_mask, 1],
            cpu["escape_dir"][escape_mask, 2],
            gpu_escape_dir[escape_mask, 0],
            gpu_escape_dir[escape_mask, 1],
            gpu_escape_dir[escape_mask, 2],
        )
    finite_error = direction_error[np.isfinite(direction_error)]
    summary = {
        "stable_event_agreement": float(stable_agreement_count / stable_count)
        if stable_count
        else math.nan,
        "stable_sample_count": stable_count,
        "stable_agreement_count": stable_agreement_count,
        "full_grid_event_agreement": float(full_agreement_count / full_count)
        if full_count
        else math.nan,
        "full_grid_sample_count": full_count,
        "full_grid_agreement_count": full_agreement_count,
        "excluded_cpu_failure": int(np.count_nonzero(~cpu_ok)),
        "excluded_near_capture": int(np.count_nonzero(near_capture)),
        "near_capture_radius": float(near_capture_radius),
        "gpu_failure_outside_exclusions": int(np.count_nonzero(gpu_failure_outside_exclusions)),
        "escape_direction_sample_count": int(finite_error.size),
        "escape_direction_max_error_rad": float(np.max(finite_error))
        if finite_error.size
        else math.nan,
        "escape_direction_rms_error_rad": float(np.sqrt(np.mean(finite_error * finite_error)))
        if finite_error.size
        else math.nan,
        "escape_direction_median_error_rad": float(np.median(finite_error))
        if finite_error.size
        else math.nan,
    }
    return {
        "stable_mask": stable.astype(np.uint8),
        "event_agreement_mask": event_agreement_mask.astype(np.uint8),
        "near_capture_mask": near_capture.astype(np.uint8),
        "gpu_escape_dir": gpu_escape_dir.astype(np.float32),
        "escape_direction_error": direction_error.astype(np.float32),
        "summary": summary,
    }


def _write_h5(
    out: Path,
    directions: np.ndarray,
    cpu: dict[str, np.ndarray],
    gpu: dict[str, Any],
    comparison: dict[str, Any],
    summary: dict[str, Any],
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(out, "w") as handle:
        for key, value in summary.items():
            if isinstance(value, (str, int, float, bool)):
                handle.attrs[key] = value
        handle.attrs["schema"] = summary["schema"]
        handle.create_dataset("direction_unity", data=directions.astype(np.float32))
        handle.create_dataset("cpu_event_code", data=cpu["event_code"])
        handle.create_dataset("cpu_failure_code", data=cpu["failure_code"])
        handle.create_dataset("cpu_min_r", data=cpu["min_r"])
        handle.create_dataset("cpu_escape_dir", data=cpu["escape_dir"])
        handle.create_dataset("cpu_h_max_abs", data=cpu["h_max_abs"])
        handle.create_dataset("cpu_q_drift_abs", data=cpu["q_drift_abs"])
        handle.create_dataset("gpu_event_code", data=gpu["event_code"])
        handle.create_dataset("gpu_failure_code", data=gpu["failure_code"])
        handle.create_dataset("gpu_final_r", data=gpu["final_r"])
        handle.create_dataset("gpu_escape_dir", data=comparison["gpu_escape_dir"])
        handle.create_dataset("stable_comparison_mask", data=comparison["stable_mask"])
        handle.create_dataset("full_grid_event_agreement_mask", data=comparison["event_agreement_mask"])
        handle.create_dataset("excluded_near_capture", data=comparison["near_capture_mask"])
        handle.create_dataset("escape_direction_error_rad", data=comparison["escape_direction_error"])


def _counts(values: np.ndarray, mapping: dict[str, int]) -> dict[str, int]:
    return {key: int(np.count_nonzero(values == value)) for key, value in mapping.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True)
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, required=True)
    parser.add_argument("--samples", type=int, default=4096)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--step-size", type=float, default=GpuTraceConfig.step_size)
    parser.add_argument("--steps", type=int, default=GpuTraceConfig.steps)
    parser.add_argument("--horizon-eps", type=float, default=TraceConfig.horizon_eps)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--h5", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    params = MetricParams(M=args.mass, a=args.spin * args.mass)
    summary = validate_full_sky_transfer(
        params=params,
        inclination_deg=args.inclination_deg,
        samples=args.samples,
        r_obs=args.r_obs,
        step_size=args.step_size,
        steps=args.steps,
        horizon_eps=args.horizon_eps,
        out=args.out,
        h5=args.h5,
        command=" ".join(sys.argv),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
