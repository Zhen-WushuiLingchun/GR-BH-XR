"""Weak-field finite-distance lensing anchor for the KS sphere target."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np

from .camera import initial_ray_state_from_unity_direction
from .geodesic_ks import KSSphereTarget, bl_state_to_ks_state, trace_state_ks
from .types import MetricParams, TraceConfig


SCHEMA = "gr-bh-xr.tier2.ks_finite_lens_weak_field.v2"


def einstein_angle_point_lens(M: float, D_l: float, D_ls: float) -> float:
    """Return the weak-field point-mass Einstein angle in geometric units.

    `D_l` is observer-to-lens distance, `D_ls` is lens-to-source distance, and
    `D_s = D_l + D_ls` for the nearly flat finite-distance anchor used here.
    """

    if M <= 0.0:
        raise ValueError("M must be positive.")
    if D_l <= 0.0 or D_ls <= 0.0:
        raise ValueError("D_l and D_ls must be positive.")
    D_s = D_l + D_ls
    return math.sqrt(4.0 * M * D_ls / (D_l * D_s))


def schwarzschild_second_order_ring_angle(M: float, D_l: float, D_ls: float) -> float:
    """Return the aligned weak-field ring angle including the GR second term.

    The Schwarzschild bending angle is expanded as
    `4M / b + 15 pi M^2 / (4 b^2)`.  Solving the aligned thin-lens equation to
    first order in `M / b_E` gives
    `theta = theta_E * (1 + 15 pi M / (32 b_E))`, with `b_E = D_l theta_E`.
    """

    theta_e = einstein_angle_point_lens(M, D_l, D_ls)
    b_e = D_l * theta_e
    return theta_e * (1.0 + (15.0 * math.pi / 32.0) * M / b_e)


def validate_ks_finite_lens(
    *,
    params: MetricParams,
    D_l: float,
    D_ls: float,
    target_radius: float,
    samples: int,
    scan_half_width_frac: float,
    max_step: float,
    r_escape_margin: float,
    boundary_refine_iterations: int = 40,
    out: Path | str | None = None,
    command: str = "",
) -> dict[str, Any]:
    """Scan image angle through an aligned finite sphere and compare theta_E."""

    if abs(params.a) > 0.0:
        raise ValueError("The weak-field point-lens anchor is Schwarzschild-only.")
    if samples < 5:
        raise ValueError("samples must be at least 5.")
    if scan_half_width_frac <= 0.0:
        raise ValueError("scan_half_width_frac must be positive.")
    if target_radius <= 0.0:
        raise ValueError("target_radius must be positive.")
    if boundary_refine_iterations < 0:
        raise ValueError("boundary_refine_iterations must be non-negative.")

    theta_e = einstein_angle_point_lens(params.M, D_l, D_ls)
    theta_second_order = schwarzschild_second_order_ring_angle(params.M, D_l, D_ls)
    theta_values = np.linspace(
        theta_e * (1.0 - scan_half_width_frac),
        theta_e * (1.0 + scan_half_width_frac),
        samples,
        dtype=np.float64,
    )
    target = KSSphereTarget(center_xyz=(-D_ls, 0.0, 0.0), radius=target_radius)
    cfg = TraceConfig(
        max_lambda=2.0 * (D_l + D_ls) + r_escape_margin,
        r_escape=D_l + D_ls + r_escape_margin,
        horizon_eps=0.3,
        max_step=max_step,
        rtol=1.0e-8,
        atol=1.0e-10,
    )

    def trace_theta(theta: float):
        direction = np.array([math.sin(float(theta)), 0.0, math.cos(float(theta))], dtype=np.float64)
        bl_state = initial_ray_state_from_unity_direction(
            params,
            r_obs=D_l,
            theta_obs=math.pi / 2.0,
            direction_unity=direction,
        )
        return trace_state_ks(
            params,
            bl_state_to_ks_state(params, bl_state),
            cfg,
            r_obs=D_l,
            sphere_target=target,
        )

    hit_thetas: list[float] = []
    hit_redshifts: list[float] = []
    event_by_theta: list[str] = []
    event_counts: dict[str, int] = {}
    for theta in theta_values:
        diag = trace_theta(float(theta))
        event_by_theta.append(diag.event)
        event_counts[diag.event] = event_counts.get(diag.event, 0) + 1
        if diag.event == "object_hit":
            hit_thetas.append(float(theta))
            hit_redshifts.append(float(diag.object_hit_redshift_g))

    refined_edges = _refine_hit_edges(
        theta_values=theta_values,
        event_by_theta=event_by_theta,
        trace_theta=trace_theta,
        iterations=boundary_refine_iterations,
    )
    if hit_thetas:
        sampled_hit_min = min(hit_thetas)
        sampled_hit_max = max(hit_thetas)
        hit_min = refined_edges[0] if len(refined_edges) >= 2 else sampled_hit_min
        hit_max = refined_edges[-1] if len(refined_edges) >= 2 else sampled_hit_max
        measured_center = 0.5 * (hit_min + hit_max)
        first_order_abs_error = abs(measured_center - theta_e)
        first_order_rel_error = first_order_abs_error / theta_e
        second_order_abs_error = abs(measured_center - theta_second_order)
        second_order_rel_error = second_order_abs_error / theta_e
    else:
        sampled_hit_min = math.nan
        sampled_hit_max = math.nan
        hit_min = math.nan
        hit_max = math.nan
        measured_center = math.nan
        first_order_abs_error = math.nan
        first_order_rel_error = math.nan
        second_order_abs_error = math.nan
        second_order_rel_error = math.nan

    summary: dict[str, Any] = {
        "schema": SCHEMA,
        "generationCommand": command,
        "metric": {"M": params.M, "a": params.a},
        "D_l": D_l,
        "D_ls": D_ls,
        "D_s": D_l + D_ls,
        "target_radius": target_radius,
        "samples": samples,
        "scan_half_width_frac": scan_half_width_frac,
        "max_step": max_step,
        "boundary_refine_iterations": boundary_refine_iterations,
        "theta_e_weak_field": theta_e,
        "theta_second_order_schwarzschild": theta_second_order,
        "theta_second_order_rel_correction": (theta_second_order - theta_e) / theta_e,
        "second_order_impact_parameter_b_e": D_l * theta_e,
        "sampled_hit_theta_min": sampled_hit_min,
        "sampled_hit_theta_max": sampled_hit_max,
        "measured_hit_theta_min": hit_min,
        "measured_hit_theta_max": hit_max,
        "measured_hit_theta_center": measured_center,
        "theta_center_abs_error": second_order_abs_error,
        "theta_center_rel_error": second_order_rel_error,
        "theta_center_abs_error_first_order": first_order_abs_error,
        "theta_center_rel_error_first_order": first_order_rel_error,
        "theta_center_abs_error_second_order": second_order_abs_error,
        "theta_center_rel_error_second_order": second_order_rel_error,
        "hit_count": len(hit_thetas),
        "event_counts": event_counts,
        "hit_redshift_min": float(np.nanmin(hit_redshifts)) if hit_redshifts else math.nan,
        "hit_redshift_max": float(np.nanmax(hit_redshifts)) if hit_redshifts else math.nan,
    }

    if out is not None:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
    return summary


def _refine_hit_edges(
    *,
    theta_values: np.ndarray,
    event_by_theta: list[str],
    trace_theta,
    iterations: int,
) -> list[float]:
    edges: list[float] = []
    hit_flags = [event == "object_hit" for event in event_by_theta]
    for idx, (left_hit, right_hit) in enumerate(zip(hit_flags[:-1], hit_flags[1:])):
        if left_hit == right_hit:
            continue
        left = float(theta_values[idx])
        right = float(theta_values[idx + 1])
        left_flag = left_hit
        right_flag = right_hit
        for _ in range(iterations):
            mid = 0.5 * (left + right)
            mid_flag = trace_theta(mid).event == "object_hit"
            if mid_flag == left_flag:
                left = mid
                left_flag = mid_flag
            else:
                right = mid
                right_flag = mid_flag
        edges.append(0.5 * (left + right))
    return edges


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--D-l", type=float, default=10000.0)
    parser.add_argument("--D-ls", type=float, default=5000.0)
    parser.add_argument("--target-radius", type=float, default=5.0)
    parser.add_argument("--samples", type=int, default=81)
    parser.add_argument("--scan-half-width-frac", type=float, default=0.035)
    parser.add_argument("--max-step", type=float, default=50.0)
    parser.add_argument("--r-escape-margin", type=float, default=1000.0)
    parser.add_argument("--boundary-refine-iterations", type=int, default=40)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    summary = validate_ks_finite_lens(
        params=MetricParams(M=1.0, a=0.0),
        D_l=args.D_l,
        D_ls=args.D_ls,
        target_radius=args.target_radius,
        samples=args.samples,
        scan_half_width_frac=args.scan_half_width_frac,
        max_step=args.max_step,
        r_escape_margin=args.r_escape_margin,
        boundary_refine_iterations=args.boundary_refine_iterations,
        out=args.out,
        command="python -m gr_bh_xr.validate_ks_finite_lens " + " ".join(argv if argv is not None else sys.argv[1:]),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
