"""Validate the Schwarzschild shadow critical impact parameter."""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
from pathlib import Path

from .geodesic import trace_ray
from .types import CameraConfig, MetricParams, TraceConfig


def _trace_b(params: MetricParams, r_obs: float, theta_obs: float, b: float, max_lambda: float) -> str:
    diagnostics = trace_ray(
        params,
        CameraConfig(r_obs=r_obs, theta_obs=theta_obs, alpha=b, beta=0.0),
        TraceConfig(max_lambda=max_lambda, r_escape=2.0 * r_obs, max_step=2.0),
    )
    return diagnostics.event


def estimate_schwarzschild_bc(
    params: MetricParams,
    r_obs: float,
    theta_obs: float,
    grid: int,
    max_lambda: float,
    refine_steps: int,
) -> dict[str, object]:
    expected = 3.0 * math.sqrt(3.0) * params.M
    b_min = 0.5 * expected
    b_max = 1.5 * expected
    samples = []
    capture_high = None
    escape_low = None

    for i in range(grid):
        b = b_min + (b_max - b_min) * i / max(grid - 1, 1)
        event = _trace_b(params, r_obs, theta_obs, b, max_lambda)
        samples.append({"b": b, "event": event})
        if event == "capture":
            capture_high = b if capture_high is None else max(capture_high, b)
        elif event == "escape" and capture_high is not None:
            escape_low = b if escape_low is None else min(escape_low, b)

    if capture_high is None or escape_low is None:
        raise RuntimeError("Could not bracket Schwarzschild critical impact parameter.")

    low = capture_high
    high = escape_low
    for _ in range(refine_steps):
        mid = 0.5 * (low + high)
        event = _trace_b(params, r_obs, theta_obs, mid, max_lambda)
        if event == "capture":
            low = mid
        elif event == "escape":
            high = mid
        else:
            break

    estimated = 0.5 * (low + high)
    counts = {
        "capture": sum(1 for sample in samples if sample["event"] == "capture"),
        "escape": sum(1 for sample in samples if sample["event"] == "escape"),
        "invalid": sum(1 for sample in samples if sample["event"] == "invalid"),
        "disk_crossing": sum(1 for sample in samples if sample["event"] == "disk_crossing"),
    }
    return {
        "metric": dataclasses.asdict(params),
        "r_obs": r_obs,
        "theta_obs": theta_obs,
        "expected_bc": expected,
        "estimated_bc": estimated,
        "abs_error": abs(estimated - expected),
        "rel_error": abs(estimated - expected) / expected,
        "grid": grid,
        "refine_steps": refine_steps,
        "sample_counts": counts,
        "bracket": {"capture_high": low, "escape_low": high},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, default=0.0, help="Dimensionless spin a/M.")
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--grid", type=int, default=129)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--inclination-deg", type=float, default=90.0)
    parser.add_argument("--max-lambda", type=float, default=1200.0)
    parser.add_argument("--refine-steps", type=int, default=12)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.spin != 0.0:
        raise SystemExit("Schwarzschild shadow validation currently requires --spin 0.")
    params = MetricParams(M=args.mass, a=args.spin * args.mass)
    result = estimate_schwarzschild_bc(
        params=params,
        r_obs=args.r_obs,
        theta_obs=math.radians(args.inclination_deg),
        grid=args.grid,
        max_lambda=args.max_lambda,
        refine_steps=args.refine_steps,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
