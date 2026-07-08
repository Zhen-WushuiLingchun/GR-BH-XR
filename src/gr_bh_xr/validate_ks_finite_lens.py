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


SCHEMA = "gr-bh-xr.tier2.ks_finite_lens_weak_field.v1"


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

    theta_e = einstein_angle_point_lens(params.M, D_l, D_ls)
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

    hit_thetas: list[float] = []
    hit_redshifts: list[float] = []
    event_counts: dict[str, int] = {}
    for theta in theta_values:
        direction = np.array([math.sin(float(theta)), 0.0, math.cos(float(theta))], dtype=np.float64)
        bl_state = initial_ray_state_from_unity_direction(
            params,
            r_obs=D_l,
            theta_obs=math.pi / 2.0,
            direction_unity=direction,
        )
        diag = trace_state_ks(
            params,
            bl_state_to_ks_state(params, bl_state),
            cfg,
            r_obs=D_l,
            sphere_target=target,
        )
        event_counts[diag.event] = event_counts.get(diag.event, 0) + 1
        if diag.event == "object_hit":
            hit_thetas.append(float(theta))
            hit_redshifts.append(float(diag.object_hit_redshift_g))

    if hit_thetas:
        hit_min = min(hit_thetas)
        hit_max = max(hit_thetas)
        measured_center = 0.5 * (hit_min + hit_max)
        abs_error = abs(measured_center - theta_e)
        rel_error = abs_error / theta_e
    else:
        hit_min = math.nan
        hit_max = math.nan
        measured_center = math.nan
        abs_error = math.nan
        rel_error = math.nan

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
        "theta_e_weak_field": theta_e,
        "measured_hit_theta_min": hit_min,
        "measured_hit_theta_max": hit_max,
        "measured_hit_theta_center": measured_center,
        "theta_center_abs_error": abs_error,
        "theta_center_rel_error": rel_error,
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--D-l", type=float, default=10000.0)
    parser.add_argument("--D-ls", type=float, default=5000.0)
    parser.add_argument("--target-radius", type=float, default=5.0)
    parser.add_argument("--samples", type=int, default=81)
    parser.add_argument("--scan-half-width-frac", type=float, default=0.035)
    parser.add_argument("--max-step", type=float, default=50.0)
    parser.add_argument("--r-escape-margin", type=float, default=1000.0)
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
        out=args.out,
        command="python -m gr_bh_xr.validate_ks_finite_lens " + " ".join(argv if argv is not None else sys.argv[1:]),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
