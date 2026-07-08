"""Exterior Boyer-Lindquist vs Kerr-Schild cross-chart validation."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np

from .camera import initial_ray_state
from .geodesic import trace_ray
from .geodesic_ks import bl_state_to_ks_state, ks_state_to_bl_state, trace_state_ks
from .sky import momentum_direction_from_state
from .types import CameraConfig, MetricParams, RayState, TraceConfig


def validate_ks_bl_crosscheck(
    *,
    params: MetricParams,
    inclination_deg: float,
    alpha_min: float,
    alpha_max: float,
    beta: float,
    samples: int,
    r_obs: float,
    max_lambda: float,
    r_escape: float,
    horizon_eps: float,
    max_step: float,
    out: Path | str | None = None,
    command: str = "",
) -> dict[str, Any]:
    """Compare BL and KS tracing on a deterministic screen-coordinate fan."""

    theta_obs = math.radians(inclination_deg)
    alphas = np.linspace(alpha_min, alpha_max, samples, dtype=np.float64)
    cfg = TraceConfig(
        max_lambda=max_lambda,
        r_escape=r_escape,
        horizon_eps=horizon_eps,
        max_step=max_step,
        rtol=1.0e-9,
        atol=1.0e-11,
    )

    rows: list[dict[str, Any]] = []
    direction_errors: list[float] = []
    event_mismatches = 0
    both_invalid_count = 0
    both_valid_event_mismatches = 0
    bl_invalid_ks_valid = 0
    ks_invalid_bl_valid = 0
    bl_invalid_ks_valid_h_values: list[float] = []
    for alpha in alphas:
        camera = CameraConfig(r_obs=r_obs, theta_obs=theta_obs, alpha=float(alpha), beta=beta)
        bl = trace_ray(params, camera, cfg)
        ks = trace_state_ks(params, bl_state_to_ks_state(params, initial_ray_state(params, camera)), cfg, r_obs=r_obs)
        direction_error = math.nan
        if bl.event == "escape" and ks.event == "escape":
            ks_bl = ks_state_to_bl_state(params, RayState(ks.final_x, ks.final_p))
            ks_dir = momentum_direction_from_state(
                params,
                r=float(ks_bl.x[1]),
                theta=float(ks_bl.x[2]),
                phi=float(ks_bl.x[3]),
                p_t=float(ks_bl.p[0]),
                p_r=float(ks_bl.p[1]),
                p_theta=float(ks_bl.p[2]),
                p_phi=float(ks_bl.p[3]),
            )[2:]
            bl_dir = (bl.escape_dir_x, bl.escape_dir_y, bl.escape_dir_z)
            direction_error = _angular_error(ks_dir, bl_dir)
            if math.isfinite(direction_error):
                direction_errors.append(direction_error)
        classification = "same"
        if bl.event == "invalid" and ks.event == "invalid":
            both_invalid_count += 1
            classification = "both_invalid_same"
        elif bl.event != ks.event:
            event_mismatches += 1
            if bl.event != "invalid" and ks.event != "invalid":
                both_valid_event_mismatches += 1
                classification = "both_valid_mismatch"
            elif bl.event == "invalid" and ks.event != "invalid":
                bl_invalid_ks_valid += 1
                bl_invalid_ks_valid_h_values.append(ks.h_max_abs)
                classification = "bl_invalid_ks_valid"
            elif bl.event != "invalid" and ks.event == "invalid":
                ks_invalid_bl_valid += 1
                classification = "ks_invalid_bl_valid"
            else:
                classification = "both_invalid_different"
        rows.append(
            {
                "alpha": float(alpha),
                "beta": float(beta),
                "bl_event": bl.event,
                "ks_event": ks.event,
                "event_comparison": classification,
                "direction_error_rad": direction_error,
                "bl_min_r": bl.min_r,
                "ks_min_r": ks.min_r,
                "ks_h_max_abs": ks.h_max_abs,
                "ks_e_drift_abs": ks.e_drift_abs,
                "ks_lz_drift_abs": ks.lz_drift_abs,
            }
        )

    finite = np.asarray(direction_errors, dtype=np.float64)
    bl_invalid_ks_valid_h = np.asarray(bl_invalid_ks_valid_h_values, dtype=np.float64)
    summary: dict[str, Any] = {
        "schema": "gr-bh-xr.tier2.ks_bl_crosscheck.v2",
        "generationCommand": command,
        "metric": {"M": params.M, "a": params.a},
        "inclination_deg": inclination_deg,
        "beta": beta,
        "alpha_min": alpha_min,
        "alpha_max": alpha_max,
        "samples": samples,
        "r_obs": r_obs,
        "r_escape": r_escape,
        "horizon_eps": horizon_eps,
        "event_mismatches": event_mismatches,
        "both_invalid_count": both_invalid_count,
        "both_valid_event_mismatches": both_valid_event_mismatches,
        "bl_invalid_ks_valid": bl_invalid_ks_valid,
        "ks_invalid_bl_valid": ks_invalid_bl_valid,
        "bl_invalid_ks_valid_max_h": float(np.max(bl_invalid_ks_valid_h))
        if bl_invalid_ks_valid_h.size
        else math.nan,
        "escape_direction_sample_count": int(finite.size),
        "escape_direction_max_error_rad": float(np.max(finite)) if finite.size else math.nan,
        "escape_direction_rms_error_rad": float(np.sqrt(np.mean(finite * finite))) if finite.size else math.nan,
        "escape_direction_median_error_rad": float(median(finite)) if finite.size else math.nan,
        "samples_detail": rows,
    }
    if out is not None:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
    return summary


def _angular_error(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    if not all(math.isfinite(value) for value in (*a, *b)):
        return math.nan
    dot = sum(left * right for left, right in zip(a, b))
    return math.acos(max(-1.0, min(1.0, dot)))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, default=0.9)
    parser.add_argument("--inclination-deg", type=float, default=60.0)
    parser.add_argument("--alpha-min", type=float, default=-8.0)
    parser.add_argument("--alpha-max", type=float, default=8.0)
    parser.add_argument("--beta", type=float, default=0.0)
    parser.add_argument("--samples", type=int, default=55)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--max-lambda", type=float, default=1200.0)
    parser.add_argument("--r-escape", type=float, default=200.0)
    parser.add_argument("--horizon-eps", type=float, default=0.05)
    parser.add_argument("--max-step", type=float, default=1.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    summary = validate_ks_bl_crosscheck(
        params=MetricParams(M=1.0, a=args.spin),
        inclination_deg=args.inclination_deg,
        alpha_min=args.alpha_min,
        alpha_max=args.alpha_max,
        beta=args.beta,
        samples=args.samples,
        r_obs=args.r_obs,
        max_lambda=args.max_lambda,
        r_escape=args.r_escape,
        horizon_eps=args.horizon_eps,
        max_step=args.max_step,
        out=args.out,
        command=" ".join(["python -m gr_bh_xr.validate_ks_bl_crosscheck", *(__import__("sys").argv[1:])]),
    )
    print(json.dumps({key: value for key, value in summary.items() if key != "samples_detail"}, indent=2))


if __name__ == "__main__":
    main()
