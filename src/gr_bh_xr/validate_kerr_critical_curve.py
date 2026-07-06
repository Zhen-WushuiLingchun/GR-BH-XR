"""Validate Kerr capture/escape boundary against the analytic critical curve."""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
from pathlib import Path
from statistics import median

import numpy as np

from .critical_curve import critical_curve_polygon, curve_center, ray_polygon_intersection_radius
from .geodesic import trace_ray
from .metric import horizon_radius
from .types import CameraConfig, MetricParams, RayDiagnostics, TraceConfig


def _event_at(
    params: MetricParams,
    theta_obs: float,
    point: np.ndarray,
    r_obs: float,
    max_lambda: float,
    horizon_eps: float,
) -> RayDiagnostics:
    return trace_ray(
        params,
        CameraConfig(
            r_obs=r_obs,
            theta_obs=theta_obs,
            alpha=float(point[0]),
            beta=float(point[1]),
        ),
        TraceConfig(
            max_lambda=max_lambda,
            r_escape=2.0 * r_obs,
            horizon_eps=horizon_eps,
            max_step=2.0,
        ),
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
) -> tuple[float, float, RayDiagnostics, RayDiagnostics]:
    low_radius = 0.0
    low_diag = _event_at(params, theta_obs, center, r_obs, max_lambda, horizon_eps)
    if low_diag.event != "capture":
        # Move inward from the analytic curve toward the center; this should
        # only be needed if the centroid is too close to the true boundary.
        for factor in (0.25, 0.5, 0.75, 0.9):
            low_radius = analytic_radius * factor
            low_diag = _event_at(
                params,
                theta_obs,
                center + low_radius * direction,
                r_obs,
                max_lambda,
                horizon_eps,
            )
            if low_diag.event == "capture":
                break
        else:
            raise RuntimeError(f"Could not find capture side; last event={low_diag.event}")

    high_radius = analytic_radius * 1.2
    high_diag = _event_at(
        params,
        theta_obs,
        center + high_radius * direction,
        r_obs,
        max_lambda,
        horizon_eps,
    )
    for _ in range(8):
        if high_diag.event == "escape":
            break
        high_radius *= 1.4
        high_diag = _event_at(
            params,
            theta_obs,
            center + high_radius * direction,
            r_obs,
            max_lambda,
            horizon_eps,
        )
    else:
        raise RuntimeError(f"Could not find escape side; last event={high_diag.event}")

    return low_radius, high_radius, low_diag, high_diag


def _summarize_diagnostics(diags: list[RayDiagnostics]) -> dict[str, float | int | None]:
    if not diags:
        return {
            "count": 0,
            "h_max_abs": None,
            "e_drift_abs": None,
            "lz_drift_abs": None,
            "q_drift_abs": None,
            "min_r": None,
        }
    return {
        "count": len(diags),
        "h_max_abs": float(max(diag.h_max_abs for diag in diags)),
        "e_drift_abs": float(max(diag.e_drift_abs for diag in diags)),
        "lz_drift_abs": float(max(diag.lz_drift_abs for diag in diags)),
        "q_drift_abs": float(max(diag.q_drift_abs for diag in diags)),
        "min_r": float(min(diag.min_r for diag in diags)),
    }


def _near_capture_radius(params: MetricParams, horizon_eps: float) -> float:
    return horizon_radius(params) + max(0.1 * params.M, 2.0 * horizon_eps)


def validate_kerr_critical_curve(
    *,
    params: MetricParams,
    theta_obs: float,
    angles: int,
    r_obs: float,
    max_lambda: float,
    horizon_eps: float,
    curve_samples: int,
    refine_steps: int,
) -> dict[str, object]:
    polygon = critical_curve_polygon(params, theta_obs, samples=curve_samples)
    center = curve_center(polygon)

    samples: list[dict[str, object]] = []
    all_diags: list[RayDiagnostics] = []
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
            diag = _event_at(
                params,
                theta_obs,
                center + mid * direction,
                r_obs,
                max_lambda,
                horizon_eps,
            )
            all_diags.append(diag)
            if diag.event == "capture":
                low = mid
            elif diag.event == "escape":
                high = mid
            else:
                raise RuntimeError(f"Unexpected event during boundary bisection: {diag.event}")

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

    event_counts = {
        "capture": sum(1 for diag in all_diags if diag.event == "capture"),
        "escape": sum(1 for diag in all_diags if diag.event == "escape"),
        "invalid": sum(1 for diag in all_diags if diag.event == "invalid"),
        "disk_crossing": sum(1 for diag in all_diags if diag.event == "disk_crossing"),
    }
    near_capture_radius = _near_capture_radius(params, horizon_eps)
    near_capture_diags = [diag for diag in all_diags if diag.min_r <= near_capture_radius]
    outer_diags = [diag for diag in all_diags if diag.min_r > near_capture_radius]
    return {
        "metric": dataclasses.asdict(params),
        "theta_obs": theta_obs,
        "r_obs": r_obs,
        "angles": angles,
        "curve_samples": curve_samples,
        "horizon_eps": horizon_eps,
        "refine_steps": refine_steps,
        "center": {"alpha": float(center[0]), "beta": float(center[1])},
        "max_abs_error": float(max(errors)),
        "rms_error": float(math.sqrt(sum(error * error for error in errors) / len(errors))),
        "median_abs_error": float(median(errors)),
        "event_counts": event_counts,
        "worst_diagnostics": {
            "h_max_abs": float(max(diag.h_max_abs for diag in all_diags)),
            "e_drift_abs": float(max(diag.e_drift_abs for diag in all_diags)),
            "lz_drift_abs": float(max(diag.lz_drift_abs for diag in all_diags)),
            "q_drift_abs": float(max(diag.q_drift_abs for diag in all_diags)),
            "min_r": float(min(diag.min_r for diag in all_diags)),
        },
        "diagnostic_groups": {
            "near_capture_radius": float(near_capture_radius),
            "outer": _summarize_diagnostics(outer_diags),
            "near_capture": _summarize_diagnostics(near_capture_diags),
        },
        "samples": samples,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True, help="Dimensionless spin a/M, with 0 < spin < 1.")
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
        raise SystemExit("Kerr critical-curve validation requires 0 < --spin < 1.")
    params = MetricParams(M=args.mass, a=args.spin * args.mass)
    result = validate_kerr_critical_curve(
        params=params,
        theta_obs=math.radians(args.inclination_deg),
        angles=args.angles,
        r_obs=args.r_obs,
        max_lambda=args.max_lambda,
        horizon_eps=args.horizon_eps,
        curve_samples=args.curve_samples,
        refine_steps=args.refine_steps,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "samples"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
