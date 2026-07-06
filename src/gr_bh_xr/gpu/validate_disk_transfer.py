"""Compare GPU f32 disk-transfer buffers against the CPU DOP853 reference."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import tempfile

import h5py
import numpy as np

from gr_bh_xr.generate_disk_transfer import generate_disk_transfer
from gr_bh_xr.generate_lens_map import FAILURE_CODES, generate_lens_map
from gr_bh_xr.gpu.codes import SCHEMA_FAILURE_CODES
from gr_bh_xr.gpu.generate_lens_map import write_gpu_lens_map
from gr_bh_xr.gpu.trace import GpuTraceConfig, critical_band_mask, trace_lens_map
from gr_bh_xr.metric import horizon_radius
from gr_bh_xr.types import MetricParams


def validate_disk_transfer_cpu_vs_gpu(
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
    disk_edge_band: float,
    r_out: float,
    max_order: int,
    out: Path | str,
    command: str = "",
) -> dict[str, object]:
    """Generate matched CPU/GPU disk-transfer maps and write a comparison file."""

    if max_order < 1 or max_order > GpuTraceConfig.disk_max_order:
        raise ValueError(f"max_order must be in [1, {GpuTraceConfig.disk_max_order}]")
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
        critical_refine_band=critical_band,
        disk_r_out=r_out,
        disk_max_order=max_order,
    )
    gpu_map = trace_lens_map(gpu_config)
    cpu = _generate_cpu_disk_reference(
        params=params,
        inclination_deg=inclination_deg,
        grid=grid,
        alpha_max=alpha_max,
        beta_max=beta_max,
        r_obs=r_obs,
        horizon_eps=horizon_eps,
        r_out=r_out,
        max_order=max_order,
    )
    comparison = _compare_disk_transfer(
        params=params,
        inclination_deg=inclination_deg,
        alpha=cpu["alpha"],
        beta=cpu["beta"],
        cpu_failure=cpu["failure_code"],
        cpu_min_r=cpu["min_r"],
        cpu_disk_r=cpu["disk_r_m"],
        cpu_disk_phi=cpu["disk_phi_m"],
        cpu_disk_t=cpu["disk_t_m"],
        cpu_disk_g=cpu["disk_g_m"],
        gpu_map=gpu_map,
        horizon_eps=horizon_eps,
        critical_band=critical_band,
        disk_edge_band=disk_edge_band,
        max_order=max_order,
    )
    _write_disk_compare_file(
        out=out,
        gpu_map=gpu_map,
        cpu=cpu,
        comparison=comparison,
        critical_band=critical_band,
        disk_edge_band=disk_edge_band,
        command=command,
    )
    summary = {
        "out": str(out),
        "summary_json": str(out.with_suffix(".json")),
        "metric": {"M": params.M, "a": params.a},
        "inclination_deg": inclination_deg,
        "grid": grid,
        "alpha_max": alpha_max,
        "beta_max": beta_max,
        "r_obs": r_obs,
        "step_size": step_size,
        "steps": steps,
        "critical_band": critical_band,
        "disk_edge_band": disk_edge_band,
        "r_out": r_out,
        "max_order": max_order,
        "cpu_valid_by_order": [
            int(np.count_nonzero(np.isfinite(cpu["disk_r_m"][order])))
            for order in range(max_order)
        ],
        "gpu_valid_by_order": [
            int(np.count_nonzero(np.isfinite(gpu_map.disk_r_m[order])))
            for order in range(max_order)
        ],
        **comparison["summary"],
    }
    out.with_suffix(".json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
    return summary


def _generate_cpu_disk_reference(
    *,
    params: MetricParams,
    inclination_deg: float,
    grid: int,
    alpha_max: float,
    beta_max: float,
    r_obs: float,
    horizon_eps: float,
    r_out: float,
    max_order: int,
) -> dict[str, np.ndarray]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        lens_path = tmpdir_path / "cpu_lens_map.h5"
        disk_path = tmpdir_path / "cpu_disk_transfer.h5"
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
            out=lens_path,
            command="gpu.validate_disk_transfer cpu lens reference",
            verbose=False,
        )
        generate_disk_transfer(
            params=params,
            inclination_deg=inclination_deg,
            grid=grid,
            alpha_max=alpha_max,
            beta_max=beta_max,
            r_obs=r_obs,
            max_lambda=1200.0,
            horizon_eps=horizon_eps,
            max_step=2.0,
            r_out=r_out,
            max_order=max_order,
            out=disk_path,
            command="gpu.validate_disk_transfer cpu disk reference",
            verbose=False,
        )
        with h5py.File(lens_path, "r") as lens, h5py.File(disk_path, "r") as disk:
            return {
                "alpha": disk["alpha"][...],
                "beta": disk["beta"][...],
                "event_code": lens["event_code"][...],
                "failure_code": lens["failure_code"][...],
                "min_r": lens["min_r"][...],
                "disk_r_m": disk["disk_r_m"][...],
                "disk_phi_m": disk["disk_phi_m"][...],
                "disk_t_m": disk["disk_t_m"][...],
                "disk_g_m": disk["disk_g_m"][...],
            }


def _compare_disk_transfer(
    *,
    params: MetricParams,
    inclination_deg: float,
    alpha: np.ndarray,
    beta: np.ndarray,
    cpu_failure: np.ndarray,
    cpu_min_r: np.ndarray,
    cpu_disk_r: np.ndarray,
    cpu_disk_phi: np.ndarray,
    cpu_disk_t: np.ndarray,
    cpu_disk_g: np.ndarray,
    gpu_map,
    horizon_eps: float,
    critical_band: float,
    disk_edge_band: float,
    max_order: int,
) -> dict[str, object]:
    critical_mask = critical_band_mask(
        params, math.radians(inclination_deg), alpha, beta, critical_band
    )
    near_capture_radius = horizon_radius(params) + max(0.1 * params.M, 2.0 * horizon_eps)
    near_capture = cpu_min_r <= near_capture_radius
    cpu_ok = cpu_failure == FAILURE_CODES["none"]
    gpu_ok = gpu_map.failure_code == SCHEMA_FAILURE_CODES["none"]
    stable = cpu_ok & gpu_ok & ~critical_mask & ~near_capture

    shape = cpu_disk_r[:max_order].shape
    disk_edge = np.zeros(shape, dtype=bool)
    compare_mask = np.zeros(shape, dtype=bool)
    mismatch_mask = np.zeros(shape, dtype=bool)
    r_error = np.full(shape, np.nan, dtype=np.float64)
    phi_error = np.full(shape, np.nan, dtype=np.float64)
    t_error = np.full(shape, np.nan, dtype=np.float64)
    g_error = np.full(shape, np.nan, dtype=np.float64)

    for order in range(max_order):
        cpu_valid = np.isfinite(cpu_disk_r[order])
        gpu_valid = np.isfinite(gpu_map.disk_r_m[order])
        if disk_edge_band > 0.0:
            r_in = float(gpu_map.config.attrs()["disk_r_in"])
            r_out = float(gpu_map.config.attrs()["disk_r_out"])
            disk_edge[order] = cpu_valid & (
                (np.abs(cpu_disk_r[order] - r_in) <= disk_edge_band)
                | (np.abs(cpu_disk_r[order] - r_out) <= disk_edge_band)
            )
        stable_order = stable & ~disk_edge[order]
        mismatch_mask[order] = stable_order & (cpu_valid != gpu_valid)
        both = stable_order & cpu_valid & gpu_valid
        compare_mask[order] = both
        r_error[order, both] = np.abs(gpu_map.disk_r_m[order, both] - cpu_disk_r[order, both])
        phi_error[order, both] = np.abs(
            np.arctan2(
                np.sin(gpu_map.disk_phi_m[order, both] - cpu_disk_phi[order, both]),
                np.cos(gpu_map.disk_phi_m[order, both] - cpu_disk_phi[order, both]),
            )
        )
        t_error[order, both] = np.abs(gpu_map.disk_t_m[order, both] - cpu_disk_t[order, both])
        g_error[order, both] = np.abs(gpu_map.disk_g_m[order, both] - cpu_disk_g[order, both])

    summary = {
        "stable_pixel_count": int(np.count_nonzero(stable)),
        "excluded_cpu_failure": int(np.count_nonzero(~cpu_ok)),
        "excluded_gpu_failure": int(np.count_nonzero(~gpu_ok)),
        "excluded_critical_band": int(np.count_nonzero(critical_mask)),
        "excluded_near_capture": int(np.count_nonzero(near_capture)),
        "excluded_disk_edge_samples": int(np.count_nonzero(disk_edge)),
        "disk_compare_sample_count": int(np.count_nonzero(compare_mask)),
        "disk_validity_mismatch_count": int(np.count_nonzero(mismatch_mask)),
        "disk_r_max_abs_error": _nanmax_or_nan(r_error),
        "disk_r_rms_error": _rms_or_nan(r_error),
        "disk_phi_max_error_rad": _nanmax_or_nan(phi_error),
        "disk_phi_rms_error_rad": _rms_or_nan(phi_error),
        "disk_t_max_abs_error": _nanmax_or_nan(t_error),
        "disk_t_rms_error": _rms_or_nan(t_error),
        "disk_g_max_abs_error": _nanmax_or_nan(g_error),
        "disk_g_rms_error": _rms_or_nan(g_error),
    }
    return {
        "stable_mask": stable.astype(np.uint8),
        "critical_mask": critical_mask.astype(np.uint8),
        "near_capture_mask": near_capture.astype(np.uint8),
        "disk_edge_mask": disk_edge.astype(np.uint8),
        "compare_mask": compare_mask.astype(np.uint8),
        "mismatch_mask": mismatch_mask.astype(np.uint8),
        "r_error": r_error.astype(np.float32),
        "phi_error": phi_error.astype(np.float32),
        "t_error": t_error.astype(np.float32),
        "g_error": g_error.astype(np.float32),
        "summary": summary,
    }


def _write_disk_compare_file(
    *,
    out: Path,
    gpu_map,
    cpu: dict[str, np.ndarray],
    comparison: dict[str, object],
    critical_band: float,
    disk_edge_band: float,
    command: str,
) -> None:
    write_gpu_lens_map(out, gpu_map, command=command)
    with h5py.File(out, "a") as handle:
        handle.attrs["disk_transfer_comparison"] = "cpu_dop853_vs_gpu_f32_rk4"
        handle.attrs["critical_band"] = critical_band
        handle.attrs["disk_edge_band"] = disk_edge_band
        for key, value in comparison["summary"].items():  # type: ignore[union-attr]
            handle.attrs[key] = value
        for name in ("event_code", "failure_code", "min_r", "disk_r_m", "disk_phi_m", "disk_t_m", "disk_g_m"):
            handle.create_dataset(f"cpu_{name}", data=cpu[name], compression="gzip", shuffle=True)
        handle.create_dataset(
            "disk_stable_mask", data=comparison["stable_mask"], compression="gzip", shuffle=True
        )
        handle.create_dataset(
            "disk_excluded_critical_band",
            data=comparison["critical_mask"],
            compression="gzip",
            shuffle=True,
        )
        handle.create_dataset(
            "disk_excluded_near_capture",
            data=comparison["near_capture_mask"],
            compression="gzip",
            shuffle=True,
        )
        handle.create_dataset(
            "disk_excluded_annulus_edge",
            data=comparison["disk_edge_mask"],
            compression="gzip",
            shuffle=True,
        )
        handle.create_dataset(
            "disk_compare_mask", data=comparison["compare_mask"], compression="gzip", shuffle=True
        )
        handle.create_dataset(
            "disk_validity_mismatch_mask",
            data=comparison["mismatch_mask"],
            compression="gzip",
            shuffle=True,
        )
        handle.create_dataset(
            "disk_r_abs_error", data=comparison["r_error"], compression="gzip", shuffle=True
        )
        handle.create_dataset(
            "disk_phi_error_rad", data=comparison["phi_error"], compression="gzip", shuffle=True
        )
        handle.create_dataset(
            "disk_t_abs_error", data=comparison["t_error"], compression="gzip", shuffle=True
        )
        handle.create_dataset(
            "disk_g_abs_error", data=comparison["g_error"], compression="gzip", shuffle=True
        )


def _nanmax_or_nan(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.max(finite)) if finite.size else math.nan


def _rms_or_nan(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.sqrt(np.mean(finite * finite))) if finite.size else math.nan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True, help="Dimensionless spin a/M.")
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, required=True)
    parser.add_argument("--grid", type=int, default=64)
    parser.add_argument("--alpha-max", type=float, default=30.0)
    parser.add_argument("--beta-max", type=float, default=30.0)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--step-size", type=float, default=GpuTraceConfig.step_size)
    parser.add_argument("--steps", type=int, default=GpuTraceConfig.steps)
    parser.add_argument("--horizon-eps", type=float, default=GpuTraceConfig.horizon_eps)
    parser.add_argument("--critical-band", type=float, default=0.25)
    parser.add_argument("--disk-edge-band", type=float, default=0.25)
    parser.add_argument("--r-out", type=float, default=30.0)
    parser.add_argument("--max-order", type=int, default=2)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    params = MetricParams(M=args.mass, a=args.spin * args.mass)
    summary = validate_disk_transfer_cpu_vs_gpu(
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
        disk_edge_band=args.disk_edge_band,
        r_out=args.r_out,
        max_order=args.max_order,
        out=args.out,
        command=" ".join(sys.argv),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
