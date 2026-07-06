"""Generate a WGPU Vulkan fixed-step RK4 lens map as HDF5."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import h5py
import numpy as np

from gr_bh_xr.gpu.codes import SCHEMA_EVENT_CODES, SCHEMA_FAILURE_CODES
from gr_bh_xr.gpu.trace import GpuLensMap, GpuTraceConfig, trace_lens_map
from gr_bh_xr.types import MetricParams


def write_gpu_lens_map(out: Path | str, lens_map: GpuLensMap, command: str = "") -> None:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(out, "w") as handle:
        for key, value in lens_map.config.attrs().items():
            handle.attrs[key] = value
        for key, value in lens_map.backend.items():
            handle.attrs[key] = value
        handle.attrs["generation_command"] = command
        handle.create_dataset("alpha", data=lens_map.alpha)
        handle.create_dataset("beta", data=lens_map.beta)
        event_ds = handle.create_dataset(
            "gpu_event_code", data=lens_map.event_code, compression="gzip", shuffle=True
        )
        for event, code in SCHEMA_EVENT_CODES.items():
            event_ds.attrs[f"code_{event}"] = code
        failure_ds = handle.create_dataset(
            "gpu_failure_code", data=lens_map.failure_code, compression="gzip", shuffle=True
        )
        for failure, code in SCHEMA_FAILURE_CODES.items():
            failure_ds.attrs[f"code_{failure}"] = code
        handle.create_dataset("gpu_min_r", data=lens_map.min_r, compression="gzip", shuffle=True)
        handle.create_dataset(
            "gpu_h_max_abs", data=lens_map.h_max_abs, compression="gzip", shuffle=True
        )
        handle.create_dataset(
            "gpu_q_drift_abs", data=lens_map.q_drift_abs, compression="gzip", shuffle=True
        )
        handle.create_dataset("gpu_steps", data=lens_map.steps, compression="gzip", shuffle=True)
        handle.create_dataset(
            "gpu_refinement_level",
            data=lens_map.refinement_level,
            compression="gzip",
            shuffle=True,
        )
        handle.create_dataset(
            "gpu_subpixel_capture_fraction",
            data=lens_map.subpixel_capture_fraction,
            compression="gzip",
            shuffle=True,
        )
        handle.create_dataset(
            "gpu_subpixel_invalid_fraction",
            data=lens_map.subpixel_invalid_fraction,
            compression="gzip",
            shuffle=True,
        )
        handle.create_dataset(
            "event_rgba8", data=lens_map.event_rgba8, compression="gzip", shuffle=True
        )
        handle.create_dataset(
            "debug_rgba8", data=lens_map.debug_rgba8, compression="gzip", shuffle=True
        )


def generate_gpu_lens_map(
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
    out: Path | str,
    critical_refine_band: float = GpuTraceConfig.critical_refine_band,
    critical_refine_factor: int = GpuTraceConfig.critical_refine_factor,
    command: str = "",
) -> dict[str, object]:
    config = GpuTraceConfig(
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
    lens_map = trace_lens_map(config)
    write_gpu_lens_map(out, lens_map, command=command)
    finite_h = lens_map.h_max_abs[np.isfinite(lens_map.h_max_abs)]
    return {
        "out": str(out),
        "schema": config.attrs()["schema"],
        "backend": lens_map.backend,
        "metric": {"M": params.M, "a": params.a},
        "inclination_deg": inclination_deg,
        "r_obs": r_obs,
        "grid": grid,
        "step_size": step_size,
        "steps": steps,
        "critical_refine_band": critical_refine_band,
        "critical_refine_factor": critical_refine_factor,
        "refined_pixels": int(np.count_nonzero(lens_map.refinement_level > 1)),
        "event_counts": lens_map.event_counts,
        "failure_counts": lens_map.failure_counts,
        "h_max_abs": float(np.max(finite_h)) if finite_h.size else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True, help="Dimensionless spin a/M.")
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, required=True)
    parser.add_argument("--grid", type=int, default=256)
    parser.add_argument("--alpha-max", type=float, required=True)
    parser.add_argument("--beta-max", type=float, required=True)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--step-size", type=float, default=GpuTraceConfig.step_size)
    parser.add_argument("--steps", type=int, default=GpuTraceConfig.steps)
    parser.add_argument("--horizon-eps", type=float, default=GpuTraceConfig.horizon_eps)
    parser.add_argument("--critical-refine-band", type=float, default=GpuTraceConfig.critical_refine_band)
    parser.add_argument(
        "--critical-refine-factor", type=int, default=GpuTraceConfig.critical_refine_factor
    )
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    params = MetricParams(M=args.mass, a=args.spin * args.mass)
    summary = generate_gpu_lens_map(
        params=params,
        inclination_deg=args.inclination_deg,
        grid=args.grid,
        alpha_max=args.alpha_max,
        beta_max=args.beta_max,
        r_obs=args.r_obs,
        step_size=args.step_size,
        steps=args.steps,
        horizon_eps=args.horizon_eps,
        critical_refine_band=args.critical_refine_band,
        critical_refine_factor=args.critical_refine_factor,
        out=args.out,
        command=" ".join(sys.argv),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
