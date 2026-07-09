"""CPU/GPU comparison for Kerr-Schild finite-distance sphere targets."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np

from gr_bh_xr.camera import initial_ray_state_from_unity_direction
from gr_bh_xr.geodesic_ks import KSSphereTarget, bl_state_to_ks_state, trace_state_ks
from gr_bh_xr.gpu.codes import SCHEMA_EVENT_CODES, SCHEMA_FAILURE_CODES
from gr_bh_xr.gpu.trace_ks import KsGpuTraceConfig, trace_ks_states
from gr_bh_xr.types import MetricParams, RayState, TraceConfig
from gr_bh_xr.validate_ks_finite_lens import einstein_angle_point_lens


SCHEMA = "gr-bh-xr.tier2.ks_finite_object_gpu_compare.v2"


def validate_ks_finite_object_gpu(
    *,
    params: MetricParams,
    D_l: float,
    D_ls: float,
    target_radius: float,
    samples: int,
    scan_half_width_frac: float,
    cpu_max_step: float,
    gpu_step_size: float,
    gpu_max_step: float,
    gpu_steps: int,
    out: Path | str,
    command: str = "",
) -> dict[str, Any]:
    if abs(params.a) > 0.0:
        raise ValueError("The current finite-object GPU gate is Schwarzschild-only.")
    theta_e = einstein_angle_point_lens(params.M, D_l, D_ls)
    theta_values = np.linspace(
        theta_e * (1.0 - scan_half_width_frac),
        theta_e * (1.0 + scan_half_width_frac),
        samples,
        dtype=np.float64,
    )
    target = KSSphereTarget(center_xyz=(-D_ls, 0.0, 0.0), radius=target_radius)
    states = _states_from_angles(params=params, D_l=D_l, theta_values=theta_values)
    max_lambda = 2.0 * (D_l + D_ls) + 100.0
    r_escape = D_l + D_ls + 100.0
    cpu = _trace_cpu(
        params=params,
        states=states,
        target=target,
        max_lambda=max_lambda,
        r_escape=r_escape,
        max_step=cpu_max_step,
        r_obs=D_l,
    )
    gpu_config = KsGpuTraceConfig(
        params=params,
        step_size=gpu_step_size,
        steps=gpu_steps,
        max_lambda=max_lambda,
        max_step=gpu_max_step,
        step_r_ref=5.0,
        adaptive_step=True,
        r_escape=r_escape,
        horizon_eps=0.3,
        sphere_center_xyz=tuple(float(v) for v in target.center_xyz),
        sphere_radius=target.radius,
    )
    gpu = trace_ks_states(gpu_config, states)
    event_match = cpu["event_code"] == gpu["event_code"]
    mismatch = ~event_match
    object_edge_band = _object_edge_band(cpu["event_code"])
    stable = ~object_edge_band
    object_code = SCHEMA_EVENT_CODES["object_hit"]
    escape_code = SCHEMA_EVENT_CODES["escape"]
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
        "theta_e_weak_field": theta_e,
        "cpu_event_counts": _counts(cpu["event_code"], SCHEMA_EVENT_CODES),
        "gpu_event_counts": _counts(gpu["event_code"], SCHEMA_EVENT_CODES),
        "gpu_failure_counts": _counts(gpu["failure_code"], SCHEMA_FAILURE_CODES),
        "event_mismatch_count": int(np.count_nonzero(mismatch)),
        "event_agreement": float(np.count_nonzero(event_match) / max(1, samples)),
        "object_edge_band_count": int(np.count_nonzero(object_edge_band)),
        "edge_band_event_mismatch_count": int(np.count_nonzero(mismatch & object_edge_band)),
        "stable_event_mismatch_count": int(np.count_nonzero(mismatch & stable)),
        "stable_event_agreement": float(np.count_nonzero(event_match & stable) / max(1, np.count_nonzero(stable))),
        "object_hit_agreement_count": int(
            np.count_nonzero((cpu["event_code"] == object_code) & (gpu["event_code"] == object_code))
        ),
        "escape_agreement_count": int(
            np.count_nonzero((cpu["event_code"] == escape_code) & (gpu["event_code"] == escape_code))
        ),
        "gpu_failure_outside_none": int(np.count_nonzero(gpu["failure_code"] != SCHEMA_FAILURE_CODES["none"])),
        "gpu_h_max_abs": _nanmax_or_nan(gpu["h_max_abs"]),
        "gpu_steps_max": int(np.max(gpu["steps"])) if gpu["steps"].size else 0,
    }
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
    return summary


def _states_from_angles(*, params: MetricParams, D_l: float, theta_values: np.ndarray) -> list[RayState]:
    states: list[RayState] = []
    for theta in theta_values:
        direction = np.array([math.sin(float(theta)), 0.0, math.cos(float(theta))], dtype=np.float64)
        bl_state = initial_ray_state_from_unity_direction(
            params,
            r_obs=D_l,
            theta_obs=math.pi / 2.0,
            direction_unity=direction,
        )
        states.append(bl_state_to_ks_state(params, bl_state))
    return states


def _trace_cpu(
    *,
    params: MetricParams,
    states: list[RayState],
    target: KSSphereTarget,
    max_lambda: float,
    r_escape: float,
    max_step: float,
    r_obs: float,
) -> dict[str, np.ndarray]:
    cfg = TraceConfig(max_lambda=max_lambda, r_escape=r_escape, horizon_eps=0.3, max_step=max_step)
    event_code = np.full(len(states), SCHEMA_EVENT_CODES["invalid"], dtype=np.int16)
    for idx, state in enumerate(states):
        diag = trace_state_ks(params, state, cfg, r_obs=r_obs, sphere_target=target)
        event_code[idx] = SCHEMA_EVENT_CODES[diag.event]
    return {"event_code": event_code}


def _counts(values: np.ndarray, code_map: dict[str, int]) -> dict[str, int]:
    return {name: int(np.count_nonzero(values == code)) for name, code in code_map.items()}


def _object_edge_band(event_code: np.ndarray) -> np.ndarray:
    edge = np.zeros(event_code.shape, dtype=bool)
    if event_code.size < 2:
        return edge
    transitions = np.nonzero(event_code[1:] != event_code[:-1])[0]
    for idx in transitions:
        lo = max(0, int(idx) - 1)
        hi = min(event_code.size, int(idx) + 3)
        edge[lo:hi] = True
    return edge


def _nanmax_or_nan(values: np.ndarray) -> float:
    finite = np.asarray(values)[np.isfinite(values)]
    return float(np.max(finite)) if finite.size else math.nan


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--D-l", type=float, default=1000.0)
    parser.add_argument("--D-ls", type=float, default=500.0)
    parser.add_argument("--target-radius", type=float, default=10.0)
    parser.add_argument("--samples", type=int, default=81)
    parser.add_argument("--scan-half-width-frac", type=float, default=0.2)
    parser.add_argument("--cpu-max-step", type=float, default=10.0)
    parser.add_argument("--gpu-step-size", type=float, default=0.05)
    parser.add_argument("--gpu-max-step", type=float, default=0.5)
    parser.add_argument("--gpu-steps", type=int, default=8000)
    parser.add_argument("--out", type=Path, default=Path("outputs/tier2/ks_finite_object_gpu_compare.json"))
    args = parser.parse_args(argv)
    summary = validate_ks_finite_object_gpu(
        params=MetricParams(M=1.0, a=0.0),
        D_l=args.D_l,
        D_ls=args.D_ls,
        target_radius=args.target_radius,
        samples=args.samples,
        scan_half_width_frac=args.scan_half_width_frac,
        cpu_max_step=args.cpu_max_step,
        gpu_step_size=args.gpu_step_size,
        gpu_max_step=args.gpu_max_step,
        gpu_steps=args.gpu_steps,
        out=args.out,
        command="python -m gr_bh_xr.gpu.validate_ks_finite_object "
        + " ".join(argv if argv is not None else sys.argv[1:]),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
