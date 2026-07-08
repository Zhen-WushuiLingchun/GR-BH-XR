"""Run low-observer-radius Kerr-Schild CPU-vs-GPU validation cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from gr_bh_xr.gpu.trace_ks import KsGpuTraceConfig
from gr_bh_xr.gpu.validate_ks import validate_ks_gpu
from gr_bh_xr.types import MetricParams, TraceConfig


def validate_near_horizon_ks_gpu(
    *,
    params: MetricParams,
    inclination_deg: float,
    r_obs_values: tuple[float, ...],
    samples: int,
    r_escape: float,
    step_size: float,
    steps: int,
    max_lambda: float,
    max_step: float,
    step_r_ref: float,
    adaptive_step: bool,
    horizon_eps: float,
    out: Path | str,
    command: str = "",
) -> dict[str, Any]:
    """Validate the KS GPU kernel for finite observers close to the hole.

    The base Task 2 gate mostly samples an observer at ``r_obs = 100M``.  This
    wrapper keeps the same comparison machinery but moves the observer inward
    and keeps the escape sphere fixed in the far zone, so the samples exercise
    the near-horizon finite-observer tetrad path before realtime-cost claims.
    """

    if not r_obs_values:
        raise ValueError("at least one r_obs value is required")
    if samples <= 0:
        raise ValueError("samples must be positive")
    if r_escape <= max(r_obs_values):
        raise ValueError("r_escape must be larger than every r_obs value")

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    case_summaries: list[dict[str, Any]] = []
    for r_obs in r_obs_values:
        case_out = out.with_name(f"{out.stem}_r{_format_r_obs(r_obs)}{out.suffix}")
        case = validate_ks_gpu(
            params=params,
            inclination_deg=inclination_deg,
            r_obs=r_obs,
            r_escape=r_escape,
            fan_samples=0,
            fan_alpha_max=0.0,
            fan_betas=(0.0,),
            full_sky_samples=samples,
            step_size=step_size,
            steps=steps,
            max_lambda=max_lambda,
            max_step=max_step,
            step_r_ref=step_r_ref,
            adaptive_step=adaptive_step,
            horizon_eps=horizon_eps,
            out=case_out,
            h5=None,
            command=f"{command} --case-r-obs {r_obs}".strip(),
        )
        case_summaries.append(case)

    resolved_values = [float(case["resolved_event_agreement"]) for case in case_summaries]
    stable_values = [float(case["stable_event_agreement"]) for case in case_summaries]
    summary = {
        "schema": "gr-bh-xr.tier2.ks_gpu_near_horizon_validation.v1",
        "generationCommand": command,
        "metric": {"M": params.M, "a": params.a},
        "inclination_deg": inclination_deg,
        "r_obs_values": list(r_obs_values),
        "samples_per_r_obs": samples,
        "r_escape": r_escape,
        "step_size": step_size,
        "steps": steps,
        "max_lambda": max_lambda,
        "max_step": max_step,
        "step_r_ref": step_r_ref,
        "adaptive_step": adaptive_step,
        "horizon_eps": horizon_eps,
        "min_resolved_event_agreement": min(resolved_values) if resolved_values else None,
        "min_stable_event_agreement": min(stable_values) if stable_values else None,
        "total_both_unclassified_max_lambda": int(
            sum(int(case["both_unclassified_max_lambda"]) for case in case_summaries)
        ),
        "total_gpu_failure_outside_exclusions": int(
            sum(int(case["gpu_failure_outside_exclusions"]) for case in case_summaries)
        ),
        "total_near_horizon_exterior_direction_samples": int(
            sum(
                int(
                    case["escape_direction_error_by_min_r_band"]["near_horizon_exterior"][
                        "count"
                    ]
                )
                for case in case_summaries
            )
        ),
        "cases": case_summaries,
    }
    out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
    return summary


def _format_r_obs(value: float) -> str:
    return f"{value:g}".replace(".", "p")


def _parse_float_list(text: str) -> tuple[float, ...]:
    values = tuple(float(part.strip()) for part in text.split(",") if part.strip())
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True)
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, default=60.0)
    parser.add_argument("--r-obs-values", type=_parse_float_list, default=(10.0, 5.0, 3.0))
    parser.add_argument("--samples", type=int, default=256)
    parser.add_argument("--r-escape", type=float, default=200.0)
    parser.add_argument("--step-size", type=float, default=KsGpuTraceConfig.step_size)
    parser.add_argument("--steps", type=int, default=KsGpuTraceConfig.steps)
    parser.add_argument("--max-lambda", type=float, default=KsGpuTraceConfig.max_lambda)
    parser.add_argument("--max-step", type=float, default=KsGpuTraceConfig.max_step)
    parser.add_argument("--step-r-ref", type=float, default=KsGpuTraceConfig.step_r_ref)
    parser.add_argument("--fixed-step", action="store_true")
    parser.add_argument("--horizon-eps", type=float, default=TraceConfig.horizon_eps)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    params = MetricParams(M=args.mass, a=args.spin * args.mass)
    summary = validate_near_horizon_ks_gpu(
        params=params,
        inclination_deg=args.inclination_deg,
        r_obs_values=args.r_obs_values,
        samples=args.samples,
        r_escape=args.r_escape,
        step_size=args.step_size,
        steps=args.steps,
        max_lambda=args.max_lambda,
        max_step=args.max_step,
        step_r_ref=args.step_r_ref,
        adaptive_step=not args.fixed_step,
        horizon_eps=args.horizon_eps,
        out=args.out,
        command=" ".join(sys.argv),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
