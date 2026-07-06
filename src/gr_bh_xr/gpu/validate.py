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

from gr_bh_xr.critical_curve import critical_curve_polygon
from gr_bh_xr.generate_lens_map import EVENT_CODES, FAILURE_CODES, generate_lens_map
from gr_bh_xr.gpu.codes import SCHEMA_EVENT_CODES, SCHEMA_FAILURE_CODES
from gr_bh_xr.gpu.generate_lens_map import write_gpu_lens_map
from gr_bh_xr.gpu.trace import GpuLensMap, GpuTraceConfig, trace_lens_map
from gr_bh_xr.metric import horizon_radius
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
    gpu_map: GpuLensMap,
    horizon_eps: float,
    critical_band: float,
) -> dict[str, object]:
    aa, bb = np.meshgrid(alpha, beta)
    critical_mask = _critical_band_mask(params, math.radians(inclination_deg), aa, bb, critical_band)
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
    }
    return {
        "stable_mask": stable.astype(np.uint8),
        "full_grid_agreement_mask": full_grid_agreement_mask.astype(np.uint8),
        "critical_mask": critical_mask.astype(np.uint8),
        "near_capture_mask": near_capture.astype(np.uint8),
        "summary": summary,
    }


def _critical_band_mask(
    params: MetricParams, theta_obs: float, alpha: np.ndarray, beta: np.ndarray, band: float
) -> np.ndarray:
    if band <= 0.0:
        return np.zeros(alpha.shape, dtype=bool)
    if abs(params.a) <= 1.0e-12:
        radius = np.sqrt(alpha * alpha + beta * beta)
        return np.abs(radius - 3.0 * math.sqrt(3.0) * params.M) <= band
    polygon = critical_curve_polygon(params, theta_obs, samples=1024)
    points = np.stack([alpha.ravel(), beta.ravel()], axis=1)
    dist = np.full(points.shape[0], np.inf, dtype=np.float64)
    for idx in range(polygon.shape[0]):
        p = polygon[idx]
        q = polygon[(idx + 1) % polygon.shape[0]]
        segment = q - p
        seg_len2 = float(segment @ segment)
        if seg_len2 <= 0.0:
            continue
        rel = points - p
        t = np.clip((rel @ segment) / seg_len2, 0.0, 1.0)
        closest = p + t[:, None] * segment
        dist = np.minimum(dist, np.linalg.norm(points - closest, axis=1))
    return dist.reshape(alpha.shape) <= band


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
        out=args.out,
        command=" ".join(sys.argv),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
