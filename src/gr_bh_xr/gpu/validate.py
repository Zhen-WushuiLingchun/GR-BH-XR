"""Compare WGPU fixed-step RK4 lens maps against the CPU DOP853 reference."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import tempfile

import h5py
import numpy as np

from gr_bh_xr.generate_lens_map import EVENT_CODES, FAILURE_CODES, generate_lens_map
from gr_bh_xr.gpu.codes import SCHEMA_EVENT_CODES, SCHEMA_FAILURE_CODES
from gr_bh_xr.gpu.generate_lens_map import write_gpu_lens_map
from gr_bh_xr.gpu.trace import GpuLensMap, GpuTraceConfig, critical_band_mask, trace_lens_map
from gr_bh_xr.metric import horizon_radius
from gr_bh_xr.sky import angular_error_from_dirs
from gr_bh_xr.types import MetricParams


def validate_cpu_vs_gpu(
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
    critical_band: float,
    out: Path | str,
    critical_refine_band: float = GpuTraceConfig.critical_refine_band,
    critical_refine_factor: int = GpuTraceConfig.critical_refine_factor,
    command: str = "",
) -> dict[str, object]:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    gpu_config = GpuTraceConfig(
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
    gpu_map = trace_lens_map(gpu_config)
    cpu = _generate_cpu_reference(
        params=params,
        inclination_deg=inclination_deg,
        grid=grid,
        alpha_max=alpha_max,
        beta_max=beta_max,
        r_obs=r_obs,
        horizon_eps=horizon_eps,
    )
    comparison = _compare(
        params=params,
        inclination_deg=inclination_deg,
        alpha=cpu["alpha"],
        beta=cpu["beta"],
        cpu_event=cpu["event_code"],
        cpu_failure=cpu["failure_code"],
        cpu_min_r=cpu["min_r"],
        cpu_escape_dir_x=cpu["escape_dir_x"],
        cpu_escape_dir_y=cpu["escape_dir_y"],
        cpu_escape_dir_z=cpu["escape_dir_z"],
        gpu_map=gpu_map,
        horizon_eps=horizon_eps,
        critical_band=critical_band,
    )
    _write_compare_file(
        out=out,
        gpu_map=gpu_map,
        cpu=cpu,
        comparison=comparison,
        critical_band=critical_band,
        command=command,
    )
    summary = {
        "out": str(out),
        "summary_json": str(out.with_suffix(".json")),
        "metric": {"M": params.M, "a": params.a},
        "inclination_deg": inclination_deg,
        "grid": grid,
        "critical_band": critical_band,
        "critical_refine_band": critical_refine_band,
        "critical_refine_factor": critical_refine_factor,
        "refined_pixels": int(np.count_nonzero(gpu_map.refinement_level > 1)),
        "backend": gpu_map.backend,
        "cpu_event_counts": _counts(cpu["event_code"], EVENT_CODES),
        "cpu_failure_counts": _counts(cpu["failure_code"], FAILURE_CODES),
        "gpu_event_counts": gpu_map.event_counts,
        "gpu_failure_counts": gpu_map.failure_counts,
        **comparison["summary"],
    }
    out.with_suffix(".json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
    return summary


def _generate_cpu_reference(
    *,
    params: MetricParams,
    inclination_deg: float,
    grid: int,
    alpha_max: float,
    beta_max: float,
    r_obs: float,
    horizon_eps: float,
) -> dict[str, np.ndarray]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir) / "cpu_reference.h5"
        generate_lens_map(
            params=params,
            inclination_deg=inclination_deg,
            grid=grid,
            alpha_max=alpha_max,
            beta_max=beta_max,
            r_obs=r_obs,
            max_lambda=1200.0,
            horizon_eps=horizon_eps,
            max_step=2.0,
            out=tmp,
            command="gpu.validate cpu reference",
            verbose=False,
        )
        with h5py.File(tmp, "r") as handle:
            return {
                "alpha": handle["alpha"][...],
                "beta": handle["beta"][...],
                "event_code": handle["event_code"][...],
                "failure_code": handle["failure_code"][...],
                "min_r": handle["min_r"][...],
                "escape_theta": handle["escape_theta"][...],
                "escape_phi": handle["escape_phi"][...],
                "escape_dir_x": handle["escape_dir_x"][...],
                "escape_dir_y": handle["escape_dir_y"][...],
                "escape_dir_z": handle["escape_dir_z"][...],
            }


def _compare(
    *,
    params: MetricParams,
    inclination_deg: float,
    alpha: np.ndarray,
    beta: np.ndarray,
    cpu_event: np.ndarray,
    cpu_failure: np.ndarray,
    cpu_min_r: np.ndarray,
    cpu_escape_dir_x: np.ndarray,
    cpu_escape_dir_y: np.ndarray,
    cpu_escape_dir_z: np.ndarray,
    gpu_map: GpuLensMap,
    horizon_eps: float,
    critical_band: float,
) -> dict[str, object]:
    critical_mask = critical_band_mask(
        params, math.radians(inclination_deg), alpha, beta, critical_band
    )
    near_capture_radius = horizon_radius(params) + max(0.1 * params.M, 2.0 * horizon_eps)
    near_capture = cpu_min_r <= near_capture_radius
    cpu_ok = cpu_failure == FAILURE_CODES["none"]
    stable = cpu_ok & ~critical_mask & ~near_capture
    agreement = (cpu_event == gpu_map.event_code) & stable
    stable_count = int(np.count_nonzero(stable))
    agreement_count = int(np.count_nonzero(agreement))
    stable_agreement = float(agreement_count / stable_count) if stable_count else math.nan
    full_grid_agreement_mask = cpu_event == gpu_map.event_code
    full_grid_agreement_count = int(np.count_nonzero(full_grid_agreement_mask))
    total = int(cpu_event.size)
    full_grid_agreement = float(full_grid_agreement_count / total) if total else math.nan
    cpu_capture_fraction = float(np.count_nonzero(cpu_event == EVENT_CODES["capture"]) / total)
    gpu_capture_fraction = float(
        np.count_nonzero(gpu_map.event_code == SCHEMA_EVENT_CODES["capture"]) / total
    )
    gpu_failure_outside_exclusions = (gpu_map.failure_code != SCHEMA_FAILURE_CODES["none"]) & stable
    escape_direction_error = _escape_direction_error(
        cpu_event=cpu_event,
        cpu_escape_dir_x=cpu_escape_dir_x,
        cpu_escape_dir_y=cpu_escape_dir_y,
        cpu_escape_dir_z=cpu_escape_dir_z,
        gpu_map=gpu_map,
        stable=stable,
    )
    finite_direction_error = escape_direction_error[np.isfinite(escape_direction_error)]
    summary = {
        "stable_event_agreement": stable_agreement,
        "stable_sample_count": stable_count,
        "stable_agreement_count": agreement_count,
        "full_grid_event_agreement": full_grid_agreement,
        "full_grid_sample_count": total,
        "full_grid_agreement_count": full_grid_agreement_count,
        "cpu_capture_fraction": cpu_capture_fraction,
        "gpu_capture_fraction": gpu_capture_fraction,
        "capture_fraction_abs_diff": abs(cpu_capture_fraction - gpu_capture_fraction),
        "gpu_failure_outside_exclusions": int(np.count_nonzero(gpu_failure_outside_exclusions)),
        "excluded_cpu_failure": int(np.count_nonzero(~cpu_ok)),
        "excluded_critical_band": int(np.count_nonzero(critical_mask)),
        "excluded_near_capture": int(np.count_nonzero(near_capture)),
        "near_capture_radius": near_capture_radius,
        "escape_direction_sample_count": int(finite_direction_error.size),
        "escape_direction_max_error_rad": float(np.max(finite_direction_error))
        if finite_direction_error.size
        else math.nan,
        "escape_direction_rms_error_rad": float(
            np.sqrt(np.mean(finite_direction_error * finite_direction_error))
        )
        if finite_direction_error.size
        else math.nan,
        "escape_direction_median_error_rad": float(np.median(finite_direction_error))
        if finite_direction_error.size
        else math.nan,
    }
    return {
        "stable_mask": stable.astype(np.uint8),
        "full_grid_agreement_mask": full_grid_agreement_mask.astype(np.uint8),
        "critical_mask": critical_mask.astype(np.uint8),
        "near_capture_mask": near_capture.astype(np.uint8),
        "escape_direction_error": escape_direction_error.astype(np.float32),
        "summary": summary,
    }


def _escape_direction_error(
    *,
    cpu_event: np.ndarray,
    cpu_escape_dir_x: np.ndarray,
    cpu_escape_dir_y: np.ndarray,
    cpu_escape_dir_z: np.ndarray,
    gpu_map: GpuLensMap,
    stable: np.ndarray,
) -> np.ndarray:
    mask = (
        stable
        & (cpu_event == EVENT_CODES["escape"])
        & (gpu_map.event_code == SCHEMA_EVENT_CODES["escape"])
    )
    error = np.full(gpu_map.event_code.shape, np.nan, dtype=np.float64)
    finite = (
        mask
        & np.isfinite(cpu_escape_dir_x)
        & np.isfinite(cpu_escape_dir_y)
        & np.isfinite(cpu_escape_dir_z)
        & np.isfinite(gpu_map.escape_dir_x)
        & np.isfinite(gpu_map.escape_dir_y)
        & np.isfinite(gpu_map.escape_dir_z)
    )
    if np.any(finite):
        error[finite] = angular_error_from_dirs(
            cpu_escape_dir_x[finite],
            cpu_escape_dir_y[finite],
            cpu_escape_dir_z[finite],
            gpu_map.escape_dir_x[finite],
            gpu_map.escape_dir_y[finite],
            gpu_map.escape_dir_z[finite],
        )
    return error


def _write_compare_file(
    *,
    out: Path,
    gpu_map: GpuLensMap,
    cpu: dict[str, np.ndarray],
    comparison: dict[str, object],
    critical_band: float,
    command: str,
) -> None:
    write_gpu_lens_map(out, gpu_map, command=command)
    with h5py.File(out, "a") as handle:
        handle.attrs["critical_band"] = critical_band
        for key, value in comparison["summary"].items():  # type: ignore[union-attr]
            handle.attrs[key] = value
        cpu_event = handle.create_dataset(
            "cpu_event_code", data=cpu["event_code"], compression="gzip", shuffle=True
        )
        for event, code in EVENT_CODES.items():
            cpu_event.attrs[f"code_{event}"] = code
        cpu_failure = handle.create_dataset(
            "cpu_failure_code", data=cpu["failure_code"], compression="gzip", shuffle=True
        )
        for failure, code in FAILURE_CODES.items():
            cpu_failure.attrs[f"code_{failure}"] = code
        handle.create_dataset("cpu_min_r", data=cpu["min_r"], compression="gzip", shuffle=True)
        handle.create_dataset(
            "cpu_escape_theta", data=cpu["escape_theta"], compression="gzip", shuffle=True
        )
        handle.create_dataset(
            "cpu_escape_phi", data=cpu["escape_phi"], compression="gzip", shuffle=True
        )
        handle.create_dataset(
            "cpu_escape_dir_x", data=cpu["escape_dir_x"], compression="gzip", shuffle=True
        )
        handle.create_dataset(
            "cpu_escape_dir_y", data=cpu["escape_dir_y"], compression="gzip", shuffle=True
        )
        handle.create_dataset(
            "cpu_escape_dir_z", data=cpu["escape_dir_z"], compression="gzip", shuffle=True
        )
        handle.create_dataset(
            "stable_comparison_mask",
            data=comparison["stable_mask"],
            compression="gzip",
            shuffle=True,
        )
        handle.create_dataset(
            "full_grid_event_agreement_mask",
            data=comparison["full_grid_agreement_mask"],
            compression="gzip",
            shuffle=True,
        )
        handle.create_dataset(
            "excluded_critical_band",
            data=comparison["critical_mask"],
            compression="gzip",
            shuffle=True,
        )
        handle.create_dataset(
            "excluded_near_capture",
            data=comparison["near_capture_mask"],
            compression="gzip",
            shuffle=True,
        )
        handle.create_dataset(
            "escape_direction_error_rad",
            data=comparison["escape_direction_error"],
            compression="gzip",
            shuffle=True,
        )


def _counts(values: np.ndarray, mapping: dict[str, int]) -> dict[str, int]:
    return {key: int(np.count_nonzero(values == value)) for key, value in mapping.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True, help="Dimensionless spin a/M.")
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, required=True)
    parser.add_argument("--grid", type=int, default=65)
    parser.add_argument("--alpha-max", type=float, required=True)
    parser.add_argument("--beta-max", type=float, required=True)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--step-size", type=float, default=GpuTraceConfig.step_size)
    parser.add_argument("--steps", type=int, default=GpuTraceConfig.steps)
    parser.add_argument("--horizon-eps", type=float, default=GpuTraceConfig.horizon_eps)
    parser.add_argument("--critical-band", type=float, default=0.25)
    parser.add_argument("--critical-refine-band", type=float, default=GpuTraceConfig.critical_refine_band)
    parser.add_argument(
        "--critical-refine-factor", type=int, default=GpuTraceConfig.critical_refine_factor
    )
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    params = MetricParams(M=args.mass, a=args.spin * args.mass)
    summary = validate_cpu_vs_gpu(
        params=params,
        inclination_deg=args.inclination_deg,
        grid=args.grid,
        alpha_max=args.alpha_max,
        beta_max=args.beta_max,
        r_obs=args.r_obs,
        step_size=args.step_size,
        steps=args.steps,
        horizon_eps=args.horizon_eps,
        critical_band=args.critical_band,
        critical_refine_band=args.critical_refine_band,
        critical_refine_factor=args.critical_refine_factor,
        out=args.out,
        command=" ".join(sys.argv),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
