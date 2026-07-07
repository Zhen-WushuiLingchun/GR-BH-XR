"""Benchmark WGPU full-map tracing latency for Tier 1 planning."""

from __future__ import annotations

import argparse
import gc
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from gr_bh_xr.gpu.trace import GpuTraceConfig, trace_lens_map
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
    parser.add_argument("--spin", type=float, required=True, help="Dimensionless spin a/M.")
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, required=True)
    parser.add_argument("--grids", type=int, nargs="+", default=[256, 512, 1024])
    parser.add_argument("--alpha-max", type=float, default=8.0)
    parser.add_argument("--beta-max", type=float, default=8.0)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--step-size", type=float, default=GpuTraceConfig.step_size)
    parser.add_argument("--steps", type=int, default=GpuTraceConfig.steps)
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
    summary = benchmark_latency(
        params=MetricParams(M=args.mass, a=args.spin * args.mass),
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
