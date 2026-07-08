"""Validate the WGPU Kerr-Schild tracer against the CPU f64 KS reference."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import h5py
import numpy as np

from gr_bh_xr.geodesic_ks import trace_state_ks, ks_state_to_bl_state
from gr_bh_xr.gpu.codes import SCHEMA_EVENT_CODES, SCHEMA_FAILURE_CODES
from gr_bh_xr.gpu.trace_ks import (
    KsGpuTraceConfig,
    ks_gpu_escape_directions,
    ks_states_from_screen_points,
    ks_states_from_unity_directions,
    trace_ks_states,
)
from gr_bh_xr.gpu.validate_full_sky_transfer import sample_full_sky_directions
from gr_bh_xr.metric import horizon_radius
from gr_bh_xr.sky import angular_error_from_dirs, escape_direction_or_nan
from gr_bh_xr.types import MetricParams, RayState, TraceConfig


def validate_ks_gpu(
    *,
    params: MetricParams,
    inclination_deg: float,
    r_obs: float,
    fan_samples: int,
    fan_alpha_max: float,
    fan_betas: tuple[float, ...],
    full_sky_samples: int,
    step_size: float,
    steps: int,
    max_lambda: float,
    max_step: float,
    step_r_ref: float,
    adaptive_step: bool,
    horizon_eps: float,
    out: Path | str,
    h5: Path | str | None = None,
    command: str = "",
) -> dict[str, Any]:
    """Run matched CPU f64 and GPU f32 KS traces and persist a summary."""

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    states, sample_kind = _build_samples(
        params=params,
        inclination_deg=inclination_deg,
        r_obs=r_obs,
        fan_samples=fan_samples,
        fan_alpha_max=fan_alpha_max,
        fan_betas=fan_betas,
        full_sky_samples=full_sky_samples,
    )
    config = KsGpuTraceConfig(
        params=params,
        step_size=step_size,
        steps=steps,
        max_lambda=max_lambda,
        max_step=max_step,
        step_r_ref=step_r_ref,
        adaptive_step=adaptive_step,
        r_escape=2.0 * r_obs,
        horizon_eps=horizon_eps,
    )
    gpu = trace_ks_states(config, states)
    cpu = _trace_cpu(
        params=params,
        states=states,
        step_size=step_size,
        steps=steps,
        max_lambda=max_lambda,
        max_step=max_step,
        r_obs=r_obs,
        horizon_eps=horizon_eps,
    )
    comparison = _compare(params=params, cpu=cpu, gpu=gpu, horizon_eps=horizon_eps)
    summary = {
        "schema": "gr-bh-xr.tier2.ks_gpu_validation.v1",
        "generationCommand": command,
        "metric": {"M": params.M, "a": params.a},
        "inclination_deg": inclination_deg,
        "r_obs": r_obs,
        "fan_samples": fan_samples,
        "fan_alpha_max": fan_alpha_max,
        "fan_betas": list(fan_betas),
        "full_sky_samples_requested": full_sky_samples,
        "sample_count": int(len(states)),
        "step_size": step_size,
        "steps": steps,
        "max_lambda": max_lambda,
        "max_step": max_step,
        "step_r_ref": step_r_ref,
        "adaptive_step": adaptive_step,
        "horizon_eps": horizon_eps,
        "capture_r": config.capture_r,
        "r_escape": config.r_escape,
        "backend": gpu["backend"],
        "cpu_event_counts": _counts(cpu["event_code"], SCHEMA_EVENT_CODES),
        "gpu_event_counts": _counts(gpu["event_code"], SCHEMA_EVENT_CODES),
        "gpu_failure_counts": _counts(gpu["failure_code"], SCHEMA_FAILURE_CODES),
        **comparison["summary"],
    }
    out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
    if h5 is not None:
        _write_h5(Path(h5), sample_kind, cpu, gpu, comparison, summary)
    return summary


def _build_samples(
    *,
    params: MetricParams,
    inclination_deg: float,
    r_obs: float,
    fan_samples: int,
    fan_alpha_max: float,
    fan_betas: tuple[float, ...],
    full_sky_samples: int,
) -> tuple[list[RayState], np.ndarray]:
    states: list[RayState] = []
    kinds: list[int] = []
    if fan_samples > 0:
        alpha = np.linspace(-fan_alpha_max, fan_alpha_max, fan_samples, dtype=np.float64)
        for beta_value in fan_betas:
            beta = np.full_like(alpha, beta_value)
            fan_states = ks_states_from_screen_points(
                params=params,
                inclination_deg=inclination_deg,
                r_obs=r_obs,
                alpha=alpha,
                beta=beta,
            )
            states.extend(fan_states)
            kinds.extend([0] * len(fan_states))
    if full_sky_samples > 0:
        directions = sample_full_sky_directions(full_sky_samples)
        full_sky_states = ks_states_from_unity_directions(
            params=params,
            inclination_deg=inclination_deg,
            r_obs=r_obs,
            directions_unity=directions,
        )
        states.extend(full_sky_states)
        kinds.extend([1] * len(full_sky_states))
    if not states:
        raise ValueError("At least one fan or full-sky sample is required.")
    return states, np.asarray(kinds, dtype=np.int16)


def _trace_cpu(
    *,
    params: MetricParams,
    states: list[RayState],
    step_size: float,
    steps: int,
    max_lambda: float,
    max_step: float,
    r_obs: float,
    horizon_eps: float,
) -> dict[str, np.ndarray]:
    config = TraceConfig(
        max_lambda=max_lambda,
        r_escape=2.0 * r_obs,
        horizon_eps=horizon_eps,
        max_step=max_step,
    )
    event_code = np.full(len(states), SCHEMA_EVENT_CODES["invalid"], dtype=np.int16)
    failure_code = np.full(len(states), SCHEMA_FAILURE_CODES["none"], dtype=np.int16)
    min_r = np.full(len(states), np.nan, dtype=np.float64)
    h_max_abs = np.full(len(states), np.nan, dtype=np.float64)
    lambda_end = np.full(len(states), np.nan, dtype=np.float64)
    escape_dir = np.full((len(states), 3), np.nan, dtype=np.float64)
    final_x = np.full((len(states), 4), np.nan, dtype=np.float64)
    final_p = np.full((len(states), 4), np.nan, dtype=np.float64)
    for idx, state in enumerate(states):
        diag = trace_state_ks(params, state, config, r_obs=r_obs, inner_horizon_eps=horizon_eps)
        event_code[idx] = SCHEMA_EVENT_CODES[diag.event]
        if diag.event == "invalid":
            failure_code[idx] = (
                SCHEMA_FAILURE_CODES["unclassified_max_lambda"]
                if "max_lambda" in diag.message
                else SCHEMA_FAILURE_CODES["solver_failure"]
            )
        min_r[idx] = diag.min_r
        h_max_abs[idx] = diag.h_max_abs
        lambda_end[idx] = diag.lambda_end
        final_x[idx] = diag.final_x
        final_p[idx] = diag.final_p
        if diag.event == "escape":
            try:
                bl_state = ks_state_to_bl_state(params, RayState(x=diag.final_x, p=diag.final_p))
                _theta, _phi, dx, dy, dz = escape_direction_or_nan(
                    params, "escape", bl_state.x, bl_state.p
                )
                escape_dir[idx] = (dx, dy, dz)
            except Exception:
                pass
    return {
        "event_code": event_code,
        "failure_code": failure_code,
        "min_r": min_r,
        "h_max_abs": h_max_abs,
        "lambda_end": lambda_end,
        "escape_dir": escape_dir,
        "final_x": final_x,
        "final_p": final_p,
    }


def _compare(
    *,
    params: MetricParams,
    cpu: dict[str, np.ndarray],
    gpu: dict[str, Any],
    horizon_eps: float,
) -> dict[str, Any]:
    near_capture_radius = horizon_radius(params) + max(0.1 * params.M, 2.0 * horizon_eps)
    cpu_resolved = cpu["event_code"] != SCHEMA_EVENT_CODES["invalid"]
    gpu_resolved = gpu["event_code"] != SCHEMA_EVENT_CODES["invalid"]
    both_unclassified = (
        (cpu["failure_code"] == SCHEMA_FAILURE_CODES["unclassified_max_lambda"])
        & (gpu["failure_code"] == SCHEMA_FAILURE_CODES["unclassified_max_lambda"])
    )
    resolved = ~both_unclassified
    near_capture = cpu["min_r"] <= near_capture_radius
    event_agreement = cpu["event_code"] == gpu["event_code"]
    stable = resolved & ~near_capture
    stable_count = int(np.count_nonzero(stable))
    stable_agree_count = int(np.count_nonzero(event_agreement & stable))
    gpu_unexpected_failure = (gpu["failure_code"] != SCHEMA_FAILURE_CODES["none"]) & stable
    gpu_escape_dir = ks_gpu_escape_directions(params, gpu)
    direction_error = np.full(cpu["event_code"].shape, np.nan, dtype=np.float64)
    escape_mask = (
        stable
        & (cpu["event_code"] == SCHEMA_EVENT_CODES["escape"])
        & (gpu["event_code"] == SCHEMA_EVENT_CODES["escape"])
        & np.all(np.isfinite(cpu["escape_dir"]), axis=1)
        & np.all(np.isfinite(gpu_escape_dir), axis=1)
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
    h_bands = _h_residual_bands(params, cpu["min_r"], gpu["h_max_abs"], horizon_eps)
    summary = {
        "stable_event_agreement": float(stable_agree_count / stable_count)
        if stable_count
        else math.nan,
        "stable_sample_count": stable_count,
        "stable_agreement_count": stable_agree_count,
        "full_event_agreement": float(np.count_nonzero(event_agreement) / event_agreement.size)
        if event_agreement.size
        else math.nan,
        "full_agreement_count": int(np.count_nonzero(event_agreement)),
        "resolved_event_agreement": float(np.count_nonzero(event_agreement & resolved) / np.count_nonzero(resolved))
        if np.count_nonzero(resolved)
        else math.nan,
        "resolved_sample_count": int(np.count_nonzero(resolved)),
        "both_unclassified_max_lambda": int(np.count_nonzero(both_unclassified)),
        "cpu_unclassified_max_lambda": int(
            np.count_nonzero(cpu["failure_code"] == SCHEMA_FAILURE_CODES["unclassified_max_lambda"])
        ),
        "gpu_unclassified_max_lambda": int(
            np.count_nonzero(gpu["failure_code"] == SCHEMA_FAILURE_CODES["unclassified_max_lambda"])
        ),
        "excluded_cpu_invalid": int(np.count_nonzero(~cpu_resolved)),
        "excluded_near_capture": int(np.count_nonzero(near_capture)),
        "near_capture_radius": near_capture_radius,
        "photon_shell_proxy_outer_radius": 5.5 * params.M,
        "gpu_failure_outside_exclusions": int(np.count_nonzero(gpu_unexpected_failure)),
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
        "gpu_h_max_abs_by_min_r_band": h_bands,
        "escape_direction_error_by_min_r_band": _direction_error_bands(
            params, cpu["min_r"], direction_error, horizon_eps
        ),
    }
    return {
        "stable_mask": stable.astype(np.uint8),
        "resolved_mask": resolved.astype(np.uint8),
        "both_unclassified_mask": both_unclassified.astype(np.uint8),
        "event_agreement_mask": event_agreement.astype(np.uint8),
        "near_capture_mask": near_capture.astype(np.uint8),
        "gpu_escape_dir": gpu_escape_dir.astype(np.float32),
        "escape_direction_error_rad": direction_error.astype(np.float32),
        "summary": summary,
    }


def _h_residual_bands(
    params: MetricParams, cpu_min_r: np.ndarray, gpu_h_max_abs: np.ndarray, horizon_eps: float
) -> dict[str, dict[str, float | int]]:
    rp = horizon_radius(params)
    near_capture_radius = rp + max(0.1 * params.M, 2.0 * horizon_eps)
    photon_shell_proxy_outer = 5.5 * params.M
    bands = {
        "outer": cpu_min_r > rp + max(1.0 * params.M, 2.0 * horizon_eps),
        "near_horizon_exterior": (cpu_min_r > rp) & (cpu_min_r <= rp + max(1.0 * params.M, 2.0 * horizon_eps)),
        "horizon_crossing": cpu_min_r <= rp,
        "weak_outer": cpu_min_r > photon_shell_proxy_outer,
        "photon_shell_proxy": (cpu_min_r > near_capture_radius)
        & (cpu_min_r <= photon_shell_proxy_outer),
    }
    out: dict[str, dict[str, float | int]] = {}
    for name, mask in bands.items():
        values = gpu_h_max_abs[mask & np.isfinite(gpu_h_max_abs)]
        out[name] = {
            "count": int(values.size),
            "max": float(np.max(values)) if values.size else math.nan,
            "median": float(np.median(values)) if values.size else math.nan,
        }
    return out


def _direction_error_bands(
    params: MetricParams, cpu_min_r: np.ndarray, direction_error: np.ndarray, horizon_eps: float
) -> dict[str, dict[str, float | int]]:
    rp = horizon_radius(params)
    near_capture_radius = rp + max(0.1 * params.M, 2.0 * horizon_eps)
    photon_shell_proxy_outer = 5.5 * params.M
    bands = {
        "outer": cpu_min_r > rp + max(1.0 * params.M, 2.0 * horizon_eps),
        "near_horizon_exterior": (cpu_min_r > rp)
        & (cpu_min_r <= rp + max(1.0 * params.M, 2.0 * horizon_eps)),
        "horizon_crossing": cpu_min_r <= rp,
        "weak_outer": cpu_min_r > photon_shell_proxy_outer,
        "photon_shell_proxy": (cpu_min_r > near_capture_radius)
        & (cpu_min_r <= photon_shell_proxy_outer),
    }
    out: dict[str, dict[str, float | int]] = {}
    for name, mask in bands.items():
        values = direction_error[mask & np.isfinite(direction_error)]
        out[name] = {
            "count": int(values.size),
            "max": float(np.max(values)) if values.size else math.nan,
            "median": float(np.median(values)) if values.size else math.nan,
            "rms": float(np.sqrt(np.mean(values * values))) if values.size else math.nan,
        }
    return out


def _write_h5(
    out: Path,
    sample_kind: np.ndarray,
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
        handle.attrs["sample_kind_code_0"] = "screen_fan"
        handle.attrs["sample_kind_code_1"] = "full_sky_direction"
        handle.create_dataset("sample_kind", data=sample_kind)
        handle.create_dataset("cpu_event_code", data=cpu["event_code"])
        handle.create_dataset("cpu_failure_code", data=cpu["failure_code"])
        handle.create_dataset("cpu_min_r", data=cpu["min_r"])
        handle.create_dataset("cpu_h_max_abs", data=cpu["h_max_abs"])
        handle.create_dataset("cpu_escape_dir", data=cpu["escape_dir"])
        handle.create_dataset("gpu_event_code", data=gpu["event_code"])
        handle.create_dataset("gpu_failure_code", data=gpu["failure_code"])
        handle.create_dataset("gpu_steps", data=gpu["steps"])
        handle.create_dataset("gpu_lambda_end", data=gpu["lambda_end"])
        handle.create_dataset("gpu_min_r", data=gpu["min_r"])
        handle.create_dataset("gpu_h_max_abs", data=gpu["h_max_abs"])
        handle.create_dataset("gpu_final_x", data=gpu["final_x"])
        handle.create_dataset("gpu_final_p", data=gpu["final_p"])
        handle.create_dataset("gpu_escape_dir", data=comparison["gpu_escape_dir"])
        handle.create_dataset("stable_comparison_mask", data=comparison["stable_mask"])
        handle.create_dataset("resolved_comparison_mask", data=comparison["resolved_mask"])
        handle.create_dataset("both_unclassified_max_lambda_mask", data=comparison["both_unclassified_mask"])
        handle.create_dataset("event_agreement_mask", data=comparison["event_agreement_mask"])
        handle.create_dataset("excluded_near_capture", data=comparison["near_capture_mask"])
        handle.create_dataset(
            "escape_direction_error_rad", data=comparison["escape_direction_error_rad"]
        )


def _counts(values: np.ndarray, mapping: dict[str, int]) -> dict[str, int]:
    return {key: int(np.count_nonzero(values == value)) for key, value in mapping.items()}


def _parse_betas(text: str) -> tuple[float, ...]:
    values = tuple(float(part.strip()) for part in text.split(",") if part.strip())
    if not values:
        raise argparse.ArgumentTypeError("at least one beta value is required")
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True)
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, default=60.0)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--fan-samples", type=int, default=55)
    parser.add_argument("--fan-alpha-max", type=float, default=8.0)
    parser.add_argument("--fan-betas", type=_parse_betas, default=(0.0, 4.0, -4.0))
    parser.add_argument("--full-sky-samples", type=int, default=512)
    parser.add_argument("--step-size", type=float, default=KsGpuTraceConfig.step_size)
    parser.add_argument("--steps", type=int, default=KsGpuTraceConfig.steps)
    parser.add_argument("--max-lambda", type=float, default=KsGpuTraceConfig.max_lambda)
    parser.add_argument("--max-step", type=float, default=KsGpuTraceConfig.max_step)
    parser.add_argument("--step-r-ref", type=float, default=KsGpuTraceConfig.step_r_ref)
    parser.add_argument("--fixed-step", action="store_true")
    parser.add_argument("--horizon-eps", type=float, default=TraceConfig.horizon_eps)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--h5", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    params = MetricParams(M=args.mass, a=args.spin * args.mass)
    summary = validate_ks_gpu(
        params=params,
        inclination_deg=args.inclination_deg,
        r_obs=args.r_obs,
        fan_samples=args.fan_samples,
        fan_alpha_max=args.fan_alpha_max,
        fan_betas=args.fan_betas,
        full_sky_samples=args.full_sky_samples,
        step_size=args.step_size,
        steps=args.steps,
        max_lambda=args.max_lambda,
        max_step=args.max_step,
        step_r_ref=args.step_r_ref,
        adaptive_step=not args.fixed_step,
        horizon_eps=args.horizon_eps,
        out=args.out,
        h5=args.h5,
        command=" ".join(sys.argv),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
