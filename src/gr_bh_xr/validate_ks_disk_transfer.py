"""Compare BL and Kerr-Schild CPU thin-disk transfer buffers."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import math
import sys
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from .camera import initial_ray_state
from .disk import isco_radius, redshift_factor
from .geodesic import trace_ray
from .geodesic_ks import bl_state_to_ks_state, trace_state_ks
from .types import CameraConfig, MetricParams, TraceConfig


SCHEMA = "gr-bh-xr.tier2.ks_disk_transfer_compare.v1"


def validate_ks_disk_transfer(
    *,
    params: MetricParams,
    inclination_deg: float,
    grid: int,
    alpha_max: float,
    beta_max: float,
    r_obs: float,
    max_lambda: float,
    r_escape: float,
    horizon_eps: float,
    max_step: float,
    r_out: float,
    max_order: int,
    out: Path | str | None = None,
    h5: Path | str | None = None,
    command: str = "",
    verbose: bool = False,
    workers: int = 1,
) -> dict[str, Any]:
    """Run a matched BL-vs-KS disk-transfer comparison on a screen grid."""

    if grid < 2:
        raise ValueError("grid must contain at least two samples per axis.")
    if max_order < 1:
        raise ValueError("max_order must be at least one.")
    if workers < 1:
        raise ValueError("workers must be at least one.")

    theta_obs = math.radians(inclination_deg)
    alpha = np.linspace(-alpha_max, alpha_max, grid, dtype=np.float64)
    beta = np.linspace(-beta_max, beta_max, grid, dtype=np.float64)
    shape = (max_order, grid, grid)
    bl_r = np.full(shape, np.nan, dtype=np.float64)
    bl_phi = np.full(shape, np.nan, dtype=np.float64)
    bl_t = np.full(shape, np.nan, dtype=np.float64)
    bl_g = np.full(shape, np.nan, dtype=np.float64)
    ks_r = np.full(shape, np.nan, dtype=np.float64)
    ks_phi = np.full(shape, np.nan, dtype=np.float64)
    ks_t = np.full(shape, np.nan, dtype=np.float64)
    ks_g = np.full(shape, np.nan, dtype=np.float64)
    bl_event = np.empty((grid, grid), dtype=object)
    ks_event = np.empty((grid, grid), dtype=object)
    ks_h = np.full((grid, grid), np.nan, dtype=np.float64)

    cfg = TraceConfig(
        max_lambda=max_lambda,
        r_escape=r_escape,
        horizon_eps=horizon_eps,
        max_step=max_step,
        rtol=1.0e-9,
        atol=1.0e-11,
        stop_on_disk=False,
    )
    r_in = isco_radius(params)

    jobs = [
        (
            params,
            theta_obs,
            float(alpha_value),
            float(beta_value),
            r_obs,
            cfg,
            r_in,
            r_out,
            max_order,
            row,
            col,
        )
        for row, beta_value in enumerate(beta)
        for col, alpha_value in enumerate(alpha)
    ]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            iterator = executor.map(_trace_disk_pixel, jobs, chunksize=max(1, len(jobs) // (workers * 8)))
            for result in iterator:
                _store_pixel_result(result, bl_event, ks_event, ks_h, bl_r, bl_phi, bl_t, bl_g, ks_r, ks_phi, ks_t, ks_g)
    else:
        for index, job in enumerate(jobs):
            _store_pixel_result(
                _trace_disk_pixel(job),
                bl_event,
                ks_event,
                ks_h,
                bl_r,
                bl_phi,
                bl_t,
                bl_g,
                ks_r,
                ks_phi,
                ks_t,
                ks_g,
            )
            if verbose and (index + 1) % grid == 0:
                print(f"completed row {(index + 1) // grid}/{grid}", flush=True)

    bl_valid = np.isfinite(bl_r)
    ks_valid = np.isfinite(ks_r)
    both = bl_valid & ks_valid
    validity_mismatch = bl_valid != ks_valid
    r_error = np.full(shape, np.nan, dtype=np.float64)
    phi_error = np.full(shape, np.nan, dtype=np.float64)
    t_error = np.full(shape, np.nan, dtype=np.float64)
    g_error = np.full(shape, np.nan, dtype=np.float64)
    r_error[both] = np.abs(ks_r[both] - bl_r[both])
    phi_error[both] = np.abs(np.arctan2(np.sin(ks_phi[both] - bl_phi[both]), np.cos(ks_phi[both] - bl_phi[both])))
    t_error[both] = np.abs(ks_t[both] - bl_t[both])
    g_error[both] = np.abs(ks_g[both] - bl_g[both])

    event_mismatch = bl_event != ks_event
    summary: dict[str, Any] = {
        "schema": SCHEMA,
        "generationCommand": command,
        "metric": {"M": params.M, "a": params.a},
        "inclination_deg": inclination_deg,
        "grid": grid,
        "alpha_max": alpha_max,
        "beta_max": beta_max,
        "r_obs": r_obs,
        "r_escape": r_escape,
        "horizon_eps": horizon_eps,
        "max_step": max_step,
        "r_in": r_in,
        "r_out": r_out,
        "max_order": max_order,
        "workers": workers,
        "event_mismatch_count": int(np.count_nonzero(event_mismatch)),
        "disk_validity_mismatch_count": int(np.count_nonzero(validity_mismatch)),
        "compare_sample_count": int(np.count_nonzero(both)),
        "bl_valid_by_order": [int(np.count_nonzero(bl_valid[order])) for order in range(max_order)],
        "ks_valid_by_order": [int(np.count_nonzero(ks_valid[order])) for order in range(max_order)],
        "disk_r_max_abs_error": _nanmax_or_nan(r_error),
        "disk_r_rms_error": _rms_or_nan(r_error),
        "disk_phi_max_error_rad": _nanmax_or_nan(phi_error),
        "disk_phi_rms_error_rad": _rms_or_nan(phi_error),
        "disk_t_max_abs_error": _nanmax_or_nan(t_error),
        "disk_t_rms_error": _rms_or_nan(t_error),
        "disk_g_max_abs_error": _nanmax_or_nan(g_error),
        "disk_g_rms_error": _rms_or_nan(g_error),
        "ks_h_max_abs": _nanmax_or_nan(ks_h),
    }
    if out is not None:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
    if h5 is not None:
        _write_h5(
            Path(h5),
            summary=summary,
            alpha=alpha,
            beta=beta,
            bl_r=bl_r,
            bl_phi=bl_phi,
            bl_t=bl_t,
            bl_g=bl_g,
            ks_r=ks_r,
            ks_phi=ks_phi,
            ks_t=ks_t,
            ks_g=ks_g,
            validity_mismatch=validity_mismatch,
            r_error=r_error,
            phi_error=phi_error,
            t_error=t_error,
            g_error=g_error,
            ks_h=ks_h,
        )
    return summary


def _fill_transfer_arrays(
    params: MetricParams,
    diagnostics,
    r_in: float,
    r_out: float,
    max_order: int,
    row: int,
    col: int,
    disk_r: np.ndarray,
    disk_phi: np.ndarray,
    disk_t: np.ndarray,
    disk_g: np.ndarray,
) -> None:
    for idx, r_cross in enumerate(diagnostics.disk_crossing_r):
        true_order = diagnostics.disk_crossing_order[idx] if diagnostics.disk_crossing_order else idx
        if true_order >= max_order:
            break
        if not math.isfinite(r_cross) or not (r_in <= r_cross <= r_out):
            continue
        if np.isfinite(disk_r[true_order, row, col]):
            continue
        disk_r[true_order, row, col] = r_cross
        disk_phi[true_order, row, col] = diagnostics.disk_crossing_phi[idx]
        disk_t[true_order, row, col] = diagnostics.disk_crossing_t[idx]
        disk_g[true_order, row, col] = redshift_factor(
            params,
            r=r_cross,
            p_t=diagnostics.disk_crossing_p_t[idx],
            p_phi=diagnostics.disk_crossing_p_phi[idx],
        )


def _trace_disk_pixel(args: tuple[Any, ...]) -> dict[str, Any]:
    (
        params,
        theta_obs,
        alpha_value,
        beta_value,
        r_obs,
        cfg,
        r_in,
        r_out,
        max_order,
        row,
        col,
    ) = args
    camera = CameraConfig(
        r_obs=r_obs,
        theta_obs=theta_obs,
        alpha=alpha_value,
        beta=beta_value,
    )
    bl_state = initial_ray_state(params, camera)
    bl = trace_ray(params, camera, cfg)
    ks = trace_state_ks(params, bl_state_to_ks_state(params, bl_state), cfg, r_obs=r_obs)
    shape = (max_order, 1, 1)
    bl_r = np.full(shape, np.nan, dtype=np.float64)
    bl_phi = np.full(shape, np.nan, dtype=np.float64)
    bl_t = np.full(shape, np.nan, dtype=np.float64)
    bl_g = np.full(shape, np.nan, dtype=np.float64)
    ks_r = np.full(shape, np.nan, dtype=np.float64)
    ks_phi = np.full(shape, np.nan, dtype=np.float64)
    ks_t = np.full(shape, np.nan, dtype=np.float64)
    ks_g = np.full(shape, np.nan, dtype=np.float64)
    _fill_transfer_arrays(params, bl, r_in, r_out, max_order, 0, 0, bl_r, bl_phi, bl_t, bl_g)
    _fill_transfer_arrays(params, ks, r_in, r_out, max_order, 0, 0, ks_r, ks_phi, ks_t, ks_g)
    return {
        "row": row,
        "col": col,
        "bl_event": bl.event,
        "ks_event": ks.event,
        "ks_h": ks.h_max_abs,
        "bl_r": bl_r[:, 0, 0],
        "bl_phi": bl_phi[:, 0, 0],
        "bl_t": bl_t[:, 0, 0],
        "bl_g": bl_g[:, 0, 0],
        "ks_r": ks_r[:, 0, 0],
        "ks_phi": ks_phi[:, 0, 0],
        "ks_t": ks_t[:, 0, 0],
        "ks_g": ks_g[:, 0, 0],
    }


def _store_pixel_result(
    result: dict[str, Any],
    bl_event: np.ndarray,
    ks_event: np.ndarray,
    ks_h: np.ndarray,
    bl_r: np.ndarray,
    bl_phi: np.ndarray,
    bl_t: np.ndarray,
    bl_g: np.ndarray,
    ks_r: np.ndarray,
    ks_phi: np.ndarray,
    ks_t: np.ndarray,
    ks_g: np.ndarray,
) -> None:
    row = int(result["row"])
    col = int(result["col"])
    bl_event[row, col] = result["bl_event"]
    ks_event[row, col] = result["ks_event"]
    ks_h[row, col] = result["ks_h"]
    bl_r[:, row, col] = result["bl_r"]
    bl_phi[:, row, col] = result["bl_phi"]
    bl_t[:, row, col] = result["bl_t"]
    bl_g[:, row, col] = result["bl_g"]
    ks_r[:, row, col] = result["ks_r"]
    ks_phi[:, row, col] = result["ks_phi"]
    ks_t[:, row, col] = result["ks_t"]
    ks_g[:, row, col] = result["ks_g"]


def _write_h5(
    out: Path,
    *,
    summary: dict[str, Any],
    alpha: np.ndarray,
    beta: np.ndarray,
    bl_r: np.ndarray,
    bl_phi: np.ndarray,
    bl_t: np.ndarray,
    bl_g: np.ndarray,
    ks_r: np.ndarray,
    ks_phi: np.ndarray,
    ks_t: np.ndarray,
    ks_g: np.ndarray,
    validity_mismatch: np.ndarray,
    r_error: np.ndarray,
    phi_error: np.ndarray,
    t_error: np.ndarray,
    g_error: np.ndarray,
    ks_h: np.ndarray,
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(out, "w") as handle:
        for key, value in summary.items():
            if key in {"generationCommand", "schema"}:
                handle.attrs[key] = value
            elif isinstance(value, (int, float, str)):
                handle.attrs[key] = value
        handle.create_dataset("alpha", data=alpha)
        handle.create_dataset("beta", data=beta)
        handle.create_dataset("bl_disk_r_m", data=bl_r, compression="gzip", shuffle=True)
        handle.create_dataset("bl_disk_phi_m", data=bl_phi, compression="gzip", shuffle=True)
        handle.create_dataset("bl_disk_t_m", data=bl_t, compression="gzip", shuffle=True)
        handle.create_dataset("bl_disk_g_m", data=bl_g, compression="gzip", shuffle=True)
        handle.create_dataset("ks_disk_r_m", data=ks_r, compression="gzip", shuffle=True)
        handle.create_dataset("ks_disk_phi_m", data=ks_phi, compression="gzip", shuffle=True)
        handle.create_dataset("ks_disk_t_m", data=ks_t, compression="gzip", shuffle=True)
        handle.create_dataset("ks_disk_g_m", data=ks_g, compression="gzip", shuffle=True)
        handle.create_dataset(
            "disk_validity_mismatch_mask", data=validity_mismatch.astype(np.uint8), compression="gzip", shuffle=True
        )
        handle.create_dataset("disk_r_abs_error", data=r_error, compression="gzip", shuffle=True)
        handle.create_dataset("disk_phi_error_rad", data=phi_error, compression="gzip", shuffle=True)
        handle.create_dataset("disk_t_abs_error", data=t_error, compression="gzip", shuffle=True)
        handle.create_dataset("disk_g_abs_error", data=g_error, compression="gzip", shuffle=True)
        handle.create_dataset("ks_h_max_abs", data=ks_h, compression="gzip", shuffle=True)


def _nanmax_or_nan(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.max(finite)) if finite.size else math.nan


def _rms_or_nan(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.sqrt(np.mean(finite * finite))) if finite.size else math.nan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True)
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, required=True)
    parser.add_argument("--grid", type=int, default=64)
    parser.add_argument("--alpha-max", type=float, default=30.0)
    parser.add_argument("--beta-max", type=float, default=30.0)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--max-lambda", type=float, default=1400.0)
    parser.add_argument("--r-escape", type=float, default=200.0)
    parser.add_argument("--horizon-eps", type=float, default=0.05)
    parser.add_argument("--max-step", type=float, default=1.0)
    parser.add_argument("--r-out", type=float, default=30.0)
    parser.add_argument("--max-order", type=int, default=2)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--h5", type=Path, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = validate_ks_disk_transfer(
        params=MetricParams(M=args.mass, a=args.spin * args.mass),
        inclination_deg=args.inclination_deg,
        grid=args.grid,
        alpha_max=args.alpha_max,
        beta_max=args.beta_max,
        r_obs=args.r_obs,
        max_lambda=args.max_lambda,
        r_escape=args.r_escape,
        horizon_eps=args.horizon_eps,
        max_step=args.max_step,
        r_out=args.r_out,
        max_order=args.max_order,
        out=args.out,
        h5=args.h5,
        command=" ".join(sys.argv),
        verbose=not args.quiet,
        workers=args.workers,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
