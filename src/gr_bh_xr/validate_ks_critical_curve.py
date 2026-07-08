"""Validate the KS tracer against the analytic Kerr critical curve."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np

from .camera import initial_ray_state
from .critical_curve import critical_curve_polygon, curve_center, ray_polygon_intersection_radius
from .geodesic_ks import KSRayDiagnostics, bl_state_to_ks_state, trace_state_ks
from .types import CameraConfig, MetricParams, TraceConfig


SCHEMA = "gr-bh-xr.tier2.ks_critical_curve.v1"


def validate_ks_critical_curve(
    *,
    params: MetricParams,
    theta_obs: float,
    angles: int,
    r_obs: float,
    max_lambda: float,
    horizon_eps: float,
    curve_samples: int,
    refine_steps: int,
    out: Path | str | None = None,
    command: str = "",
) -> dict[str, Any]:
    """Compare the KS capture/escape boundary with the analytic curve."""

    polygon = critical_curve_polygon(params, theta_obs, samples=curve_samples)
    center = curve_center(polygon)
    samples: list[dict[str, float]] = []
    all_diags: list[KSRayDiagnostics] = []
    errors: list[float] = []

    for index in range(angles):
        angle = 2.0 * math.pi * index / angles
        direction = np.array([math.cos(angle), math.sin(angle)], dtype=np.float64)
        analytic_radius = ray_polygon_intersection_radius(center, direction, polygon)
        low, high, low_diag, high_diag = _bracket_boundary(
            params,
            theta_obs,
            center,
            direction,
            analytic_radius,
            r_obs,
            max_lambda,
            horizon_eps,
        )
        all_diags.extend([low_diag, high_diag])
        for _ in range(refine_steps):
            mid = 0.5 * (low + high)
            diag = _event_at(params, theta_obs, center + mid * direction, r_obs, max_lambda, horizon_eps)
            all_diags.append(diag)
            if diag.event == "capture":
                low = mid
            elif diag.event == "escape":
                high = mid
            else:
                raise RuntimeError(f"Unexpected KS event during boundary bisection: {diag.event}")
        numeric_radius = 0.5 * (low + high)
        abs_error = abs(numeric_radius - analytic_radius)
        errors.append(abs_error)
        samples.append(
            {
                "angle": angle,
                "analytic_radius": analytic_radius,
                "numeric_radius": numeric_radius,
                "abs_error": abs_error,
                "capture_radius": low,
                "escape_radius": high,
            }
        )

    finite = np.asarray(errors, dtype=np.float64)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "generationCommand": command,
        "metric": {"M": params.M, "a": params.a},
        "theta_obs": theta_obs,
        "r_obs": r_obs,
        "angles": angles,
        "curve_samples": curve_samples,
        "horizon_eps": horizon_eps,
        "refine_steps": refine_steps,
        "center": {"alpha": float(center[0]), "beta": float(center[1])},
        "max_abs_error": float(np.max(finite)),
        "rms_error": float(math.sqrt(float(np.mean(finite * finite)))),
        "median_abs_error": float(median(finite)),
        "event_counts": {
            "capture": sum(1 for diag in all_diags if diag.event == "capture"),
            "escape": sum(1 for diag in all_diags if diag.event == "escape"),
            "invalid": sum(1 for diag in all_diags if diag.event == "invalid"),
            "disk_crossing": sum(1 for diag in all_diags if diag.event == "disk_crossing"),
        },
        "worst_diagnostics": {
            "h_max_abs": float(max(diag.h_max_abs for diag in all_diags)),
            "e_drift_abs": float(max(diag.e_drift_abs for diag in all_diags)),
            "lz_drift_abs": float(max(diag.lz_drift_abs for diag in all_diags)),
            "q_drift_abs": float(max(diag.q_drift_abs for diag in all_diags)),
            "min_r": float(min(diag.min_r for diag in all_diags)),
            "q_skipped_count": int(sum(diag.q_skipped_count for diag in all_diags)),
        },
        "samples": samples,
    }
    if out is not None:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf8")
    return result


def _event_at(
    params: MetricParams,
    theta_obs: float,
    point: np.ndarray,
    r_obs: float,
    max_lambda: float,
    horizon_eps: float,
) -> KSRayDiagnostics:
    camera = CameraConfig(r_obs=r_obs, theta_obs=theta_obs, alpha=float(point[0]), beta=float(point[1]))
    state = bl_state_to_ks_state(params, initial_ray_state(params, camera))
    return trace_state_ks(
        params,
        state,
        TraceConfig(
            max_lambda=max_lambda,
            r_escape=2.0 * r_obs,
            horizon_eps=horizon_eps,
            max_step=1.0,
        ),
        r_obs=r_obs,
        inner_horizon_eps=horizon_eps,
    )


def _bracket_boundary(
    params: MetricParams,
    theta_obs: float,
    center: np.ndarray,
    direction: np.ndarray,
    analytic_radius: float,
    r_obs: float,
    max_lambda: float,
    horizon_eps: float,
) -> tuple[float, float, KSRayDiagnostics, KSRayDiagnostics]:
    low_radius = 0.0
    low_diag = _event_at(params, theta_obs, center, r_obs, max_lambda, horizon_eps)
    if low_diag.event != "capture":
        for factor in (0.25, 0.5, 0.75, 0.9):
            low_radius = analytic_radius * factor
            low_diag = _event_at(params, theta_obs, center + low_radius * direction, r_obs, max_lambda, horizon_eps)
            if low_diag.event == "capture":
                break
        else:
            raise RuntimeError(f"Could not find KS capture side; last event={low_diag.event}")

    high_radius = analytic_radius * 1.2
    high_diag = _event_at(params, theta_obs, center + high_radius * direction, r_obs, max_lambda, horizon_eps)
    for _ in range(8):
        if high_diag.event == "escape":
            break
        high_radius *= 1.4
        high_diag = _event_at(params, theta_obs, center + high_radius * direction, r_obs, max_lambda, horizon_eps)
    else:
        raise RuntimeError(f"Could not find KS escape side; last event={high_diag.event}")
    return low_radius, high_radius, low_diag, high_diag


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True)
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, required=True)
    parser.add_argument("--angles", type=int, default=48)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--max-lambda", type=float, default=1200.0)
    parser.add_argument("--horizon-eps", type=float, default=2.0e-2)
    parser.add_argument("--curve-samples", type=int, default=2048)
    parser.add_argument("--refine-steps", type=int, default=14)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not (0.0 < args.spin < 1.0):
        raise SystemExit("KS critical-curve validation requires 0 < --spin < 1.")
    result = validate_ks_critical_curve(
        params=MetricParams(M=args.mass, a=args.spin * args.mass),
        theta_obs=math.radians(args.inclination_deg),
        angles=args.angles,
        r_obs=args.r_obs,
        max_lambda=args.max_lambda,
        horizon_eps=args.horizon_eps,
        curve_samples=args.curve_samples,
        refine_steps=args.refine_steps,
        out=args.out,
        command=" ".join(sys.argv),
    )
    print(json.dumps({key: value for key, value in result.items() if key != "samples"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
