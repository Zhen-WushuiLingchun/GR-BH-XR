"""Benchmark WGPU full-map tracing latency for Tier 1 planning."""

from __future__ import annotations

import argparse
import gc
import json
import math
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from gr_bh_xr.gpu.trace import GpuTraceConfig, trace_lens_map
from gr_bh_xr.gpu.trace_ks import KsGpuTraceConfig, ks_states_from_unity_directions, trace_ks_states
from gr_bh_xr.types import MetricParams, TraceConfig


def benchmark_latency(
    *,
    params: MetricParams,
    inclination_deg: float,
    grids: list[int],
    alpha_max: float,
    beta_max: float,
    r_obs: float,
    step_size: float,
    steps: int,
    horizon_eps: float,
    iterations: int,
    critical_refine_band: float,
    critical_refine_factor: int,
    warmup_grid: int | None,
    command: str,
) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations must be at least one.")
    if not grids:
        raise ValueError("At least one grid must be requested.")

    warmup: dict[str, Any] | None = None
    if warmup_grid is not None and warmup_grid > 1:
        config = _config(
            params=params,
            inclination_deg=inclination_deg,
            grid=warmup_grid,
            alpha_max=alpha_max,
            beta_max=beta_max,
            r_obs=r_obs,
            step_size=step_size,
            steps=steps,
            horizon_eps=horizon_eps,
            critical_refine_band=0.0,
            critical_refine_factor=1,
        )
        t0 = time.perf_counter()
        lens_map = trace_lens_map(config)
        warmup = {
            "grid": warmup_grid,
            "elapsed_ms": (time.perf_counter() - t0) * 1000.0,
            "backend": lens_map.backend,
        }
        del lens_map
        gc.collect()

    cases = []
    backend: dict[str, Any] | None = None
    for grid in grids:
        config = _config(
            params=params,
            inclination_deg=inclination_deg,
            grid=grid,
            alpha_max=alpha_max,
            beta_max=beta_max,
            r_obs=r_obs,
            step_size=step_size,
            steps=steps,
            horizon_eps=horizon_eps,
            critical_refine_band=critical_refine_band,
            critical_refine_factor=critical_refine_factor,
        )
        samples_ms: list[float] = []
        last_summary: dict[str, Any] | None = None
        for _ in range(iterations):
            t0 = time.perf_counter()
            lens_map = trace_lens_map(config)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            samples_ms.append(elapsed_ms)
            backend = lens_map.backend
            last_summary = {
                "event_counts": lens_map.event_counts,
                "failure_counts": lens_map.failure_counts,
                "refined_pixels": int(np.count_nonzero(lens_map.refinement_level > 1)),
                "disk_valid_by_order": [
                    int(np.count_nonzero(np.isfinite(lens_map.disk_r_m[order])))
                    for order in range(lens_map.disk_r_m.shape[0])
                ],
            }
            del lens_map
            gc.collect()
        cases.append(_case_summary(grid, iterations, samples_ms, last_summary or {}))

    return {
        "schema": "gr-bh-xr.phase2.gpu_latency.v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "command": command,
        "benchmark_scope": (
            "warm pipeline full-map trace_lens_map latency, including GPU dispatch, "
            "readback, escape-direction postprocess, event/debug texture assembly, "
            "and optional critical-band refinement; excludes HDF5 writes and Unity upload"
        ),
        "metric": {"M": params.M, "a": params.a},
        "inclination_deg": inclination_deg,
        "screen": {"alpha_max": alpha_max, "beta_max": beta_max, "r_obs": r_obs},
        "integration": {
            "step_size": step_size,
            "steps": steps,
            "lambda_budget": step_size * steps,
            "horizon_eps": horizon_eps,
            "critical_refine_band": critical_refine_band,
            "critical_refine_factor": critical_refine_factor,
        },
        "warmup": warmup,
        "backend": backend or (warmup or {}).get("backend"),
        "cases": cases,
    }


def benchmark_ks_frustum_latency(
    *,
    params: MetricParams,
    inclination_deg: float,
    grids: list[int],
    r_obs_values: list[float],
    fov_deg: float,
    step_size: float,
    steps: int,
    max_lambda: float,
    max_step: float,
    step_r_ref: float,
    horizon_eps: float,
    r_escape: float,
    iterations: int,
    include_sphere: bool,
    sphere_center_xyz: tuple[float, float, float],
    sphere_radius: float,
    warmup_grid: int | None,
    command: str,
) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations must be at least one.")
    if not grids:
        raise ValueError("At least one grid must be requested.")
    if not r_obs_values:
        raise ValueError("At least one r_obs value must be requested.")

    warmup: dict[str, Any] | None = None
    if warmup_grid is not None and warmup_grid > 1:
        warm_dirs = _frustum_directions(warmup_grid, fov_deg)
        warm_states = ks_states_from_unity_directions(
            params=params,
            inclination_deg=inclination_deg,
            r_obs=r_obs_values[0],
            directions_unity=warm_dirs,
        )
        warm_config = KsGpuTraceConfig(
            params=params,
            step_size=step_size,
            steps=steps,
            max_lambda=max_lambda,
            max_step=max_step,
            step_r_ref=step_r_ref,
            adaptive_step=True,
            r_escape=r_escape,
            horizon_eps=horizon_eps,
            sphere_center_xyz=sphere_center_xyz if include_sphere else None,
            sphere_radius=sphere_radius if include_sphere else 0.0,
        )
        t0 = time.perf_counter()
        warm_gpu = trace_ks_states(warm_config, warm_states)
        warmup = {
            "grid": warmup_grid,
            "r_obs": r_obs_values[0],
            "elapsed_ms": (time.perf_counter() - t0) * 1000.0,
            "backend": warm_gpu["backend"],
        }
        del warm_gpu
        gc.collect()

    directions_by_grid = {grid: _frustum_directions(grid, fov_deg) for grid in grids}
    cases = []
    backend: dict[str, Any] | None = None
    for r_obs in r_obs_values:
        for grid in grids:
            directions = directions_by_grid[grid]
            states = ks_states_from_unity_directions(
                params=params,
                inclination_deg=inclination_deg,
                r_obs=r_obs,
                directions_unity=directions,
            )
            config = KsGpuTraceConfig(
                params=params,
                step_size=step_size,
                steps=steps,
                max_lambda=max_lambda,
                max_step=max_step,
                step_r_ref=step_r_ref,
                adaptive_step=True,
                r_escape=r_escape,
                horizon_eps=horizon_eps,
                sphere_center_xyz=sphere_center_xyz if include_sphere else None,
                sphere_radius=sphere_radius if include_sphere else 0.0,
            )
            samples_ms: list[float] = []
            last_summary: dict[str, Any] | None = None
            for _ in range(iterations):
                t0 = time.perf_counter()
                gpu = trace_ks_states(config, states)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                samples_ms.append(elapsed_ms)
                backend = gpu["backend"]
                last_summary = _ks_frustum_case_payload(gpu)
                del gpu
                gc.collect()
            case = _case_summary(grid, iterations, samples_ms, last_summary or {})
            case["r_obs"] = r_obs
            case["fov_deg"] = fov_deg
            case["single_eye_hz_median"] = 1000.0 / max(case["elapsed_ms_median"], 1.0e-12)
            case["meets_90hz_11ms_single_eye"] = case["elapsed_ms_median"] < 11.0
            cases.append(case)

    return {
        "schema": "gr-bh-xr.tier2.ks_frustum_latency.v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "command": command,
        "benchmark_scope": (
            "KS frustum-only WGPU trace_ks_states latency, including GPU dispatch, "
            "readback, and event summary; excludes Python finite-observer initial-state "
            "construction and Unity upload. Disk crossings are not yet in the KS shader "
            "and are reported as disabled."
        ),
        "metric": {"M": params.M, "a": params.a},
        "inclination_deg": inclination_deg,
        "frustum": {"fov_deg": fov_deg, "r_obs_values": r_obs_values},
        "integration": {
            "step_size": step_size,
            "steps": steps,
            "max_lambda": max_lambda,
            "max_step": max_step,
            "step_r_ref": step_r_ref,
            "horizon_eps": horizon_eps,
            "r_escape": r_escape,
        },
        "features": {
            "ks_horizon_penetrating": True,
            "sphere_target_enabled": include_sphere,
            "disk_crossings_enabled": False,
        },
        "sphere_target": {
            "center_xyz": list(sphere_center_xyz),
            "radius": sphere_radius,
        }
        if include_sphere
        else None,
        "backend": backend,
        "decision_rule": "single-eye median < 11 ms is required before claiming low-resolution 90 Hz realtime tracing",
        "warmup": warmup,
        "cases": cases,
    }


def _frustum_directions(grid: int, fov_deg: float) -> np.ndarray:
    if grid < 2:
        raise ValueError("grid must be at least 2.")
    half = math.tan(math.radians(fov_deg) * 0.5)
    axis = np.linspace(-half, half, grid, dtype=np.float64)
    xx, yy = np.meshgrid(axis, axis)
    dirs = np.stack([xx, yy, np.ones_like(xx)], axis=-1).reshape((-1, 3))
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    return dirs


def _ks_frustum_case_payload(gpu: dict[str, Any]) -> dict[str, Any]:
    steps = np.asarray(gpu["steps"], dtype=np.float64)
    h = np.asarray(gpu["h_max_abs"], dtype=np.float64)
    min_r = np.asarray(gpu["min_r"], dtype=np.float64)
    event_codes = {0: "capture", 1: "escape", 2: "disk_crossing", 3: "invalid", 4: "object_hit"}
    failure_codes = {
        0: "none",
        1: "trace_exception",
        2: "unclassified_max_lambda",
        3: "solver_failure",
        4: "axis_coordinate_singularity",
        5: "polar_step_overshoot",
    }
    return {
        "event_counts": {
            name: int(np.count_nonzero(gpu["event_code"] == code)) for code, name in event_codes.items()
        },
        "failure_counts": {
            name: int(np.count_nonzero(gpu["failure_code"] == code)) for code, name in failure_codes.items()
        },
        "steps_min": float(np.min(steps)) if steps.size else math.nan,
        "steps_median": float(np.median(steps)) if steps.size else math.nan,
        "steps_p95": float(np.percentile(steps, 95)) if steps.size else math.nan,
        "steps_max": float(np.max(steps)) if steps.size else math.nan,
        "min_r_min": float(np.nanmin(min_r)) if np.any(np.isfinite(min_r)) else math.nan,
        "h_max_abs": float(np.nanmax(h)) if np.any(np.isfinite(h)) else math.nan,
    }


def _case_summary(
    grid: int, iterations: int, samples_ms: list[float], last_summary: dict[str, Any]
) -> dict[str, Any]:
    pixels = grid * grid
    median_ms = statistics.median(samples_ms)
    return {
        "grid": grid,
        "pixels": pixels,
        "iterations": iterations,
        "elapsed_ms_samples": samples_ms,
        "elapsed_ms_min": min(samples_ms),
        "elapsed_ms_median": median_ms,
        "elapsed_ms_mean": statistics.fmean(samples_ms),
        "elapsed_ms_max": max(samples_ms),
        "pixels_per_second_median": pixels / max(median_ms / 1000.0, 1.0e-12),
        **last_summary,
    }


def _config(
    *,
    params: MetricParams,
    inclination_deg: float,
    grid: int,
    alpha_max: float,
    beta_max: float,
    r_obs: float,
    step_size: float,
    steps: int,
    horizon_eps: float,
    critical_refine_band: float,
    critical_refine_factor: int,
) -> GpuTraceConfig:
    return GpuTraceConfig(
        params=params,
        inclination_deg=inclination_deg,
        grid=grid,
        alpha_max=alpha_max,
        beta_max=beta_max,
        r_obs=r_obs,
        step_size=step_size,
        steps=steps,
        horizon_eps=horizon_eps,
        critical_refine_band=critical_refine_band,
        critical_refine_factor=critical_refine_factor,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["full-map", "ks-frustum"], default="full-map")
    parser.add_argument("--spin", type=float, required=True, help="Dimensionless spin a/M.")
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, required=True)
    parser.add_argument("--grids", type=int, nargs="+", default=[256, 512, 1024])
    parser.add_argument("--r-obs-values", type=float, nargs="+", default=[20.0, 10.0, 5.0, 3.0, 2.0])
    parser.add_argument("--fov-deg", type=float, default=100.0)
    parser.add_argument("--alpha-max", type=float, default=8.0)
    parser.add_argument("--beta-max", type=float, default=8.0)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--step-size", type=float, default=GpuTraceConfig.step_size)
    parser.add_argument("--steps", type=int, default=GpuTraceConfig.steps)
    parser.add_argument("--max-lambda", type=float, default=800.0)
    parser.add_argument("--max-step", type=float, default=1.0)
    parser.add_argument("--step-r-ref", type=float, default=5.0)
    parser.add_argument("--r-escape", type=float, default=200.0)
    parser.add_argument("--include-sphere", action="store_true")
    parser.add_argument("--sphere-center", type=float, nargs=3, default=[12.0, 0.0, 0.0])
    parser.add_argument("--sphere-radius", type=float, default=1.0)
    parser.add_argument("--horizon-eps", type=float, default=TraceConfig.horizon_eps)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument(
        "--critical-refine-band",
        type=float,
        default=0.0,
        help="Default is 0 to measure raw full-map update latency.",
    )
    parser.add_argument("--critical-refine-factor", type=int, default=1)
    parser.add_argument("--warmup-grid", type=int, default=17)
    parser.add_argument("--no-warmup", action="store_true")
    parser.add_argument("--out", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    params = MetricParams(M=args.mass, a=args.spin * args.mass)
    if args.mode == "ks-frustum":
        summary = benchmark_ks_frustum_latency(
            params=params,
            inclination_deg=args.inclination_deg,
            grids=args.grids,
            r_obs_values=args.r_obs_values,
            fov_deg=args.fov_deg,
            step_size=args.step_size,
            steps=args.steps,
            max_lambda=args.max_lambda,
            max_step=args.max_step,
            step_r_ref=args.step_r_ref,
            horizon_eps=args.horizon_eps,
            r_escape=args.r_escape,
            iterations=args.iterations,
            include_sphere=args.include_sphere,
            sphere_center_xyz=tuple(float(v) for v in args.sphere_center),
            sphere_radius=args.sphere_radius,
            warmup_grid=None if args.no_warmup else args.warmup_grid,
            command=" ".join(sys.argv),
        )
    else:
        summary = benchmark_latency(
            params=params,
            inclination_deg=args.inclination_deg,
            grids=args.grids,
            alpha_max=args.alpha_max,
            beta_max=args.beta_max,
            r_obs=args.r_obs,
            step_size=args.step_size,
            steps=args.steps,
            horizon_eps=args.horizon_eps,
            iterations=args.iterations,
            critical_refine_band=args.critical_refine_band,
            critical_refine_factor=args.critical_refine_factor,
            warmup_grid=None if args.no_warmup else args.warmup_grid,
            command=" ".join(sys.argv),
        )
    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
