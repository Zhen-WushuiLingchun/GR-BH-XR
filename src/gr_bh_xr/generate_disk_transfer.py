"""Generate CPU thin-disk transfer-function buffers."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import h5py
import numpy as np

from .disk import isco_radius, redshift_factor
from .generate_lens_map import EVENT_CODES, FAILURE_CODES
from .geodesic import trace_ray
from .types import CameraConfig, MetricParams, TraceConfig


SCHEMA = "gr-bh-xr.task6.thin_disk_transfer.v1"


def generate_disk_transfer(
    *,
    params: MetricParams,
    inclination_deg: float,
    grid: int,
    alpha_max: float,
    beta_max: float,
    r_obs: float,
    max_lambda: float,
    horizon_eps: float,
    max_step: float,
    out: Path | str,
    alpha_min: float | None = None,
    beta_min: float | None = None,
    r_out: float = 30.0,
    max_order: int = 3,
    command: str = "",
    verbose: bool = True,
) -> dict[str, object]:
    """Trace a screen grid and persist per-crossing thin-disk transfer data."""

    if grid < 2:
        raise ValueError("Disk-transfer grid must contain at least two samples per axis.")
    if max_order < 1:
        raise ValueError("max_order must be at least one.")
    alpha_lo = -alpha_max if alpha_min is None else float(alpha_min)
    beta_lo = -beta_max if beta_min is None else float(beta_min)
    alpha_hi = float(alpha_max)
    beta_hi = float(beta_max)
    if alpha_hi <= alpha_lo:
        raise ValueError("alpha_max must be greater than alpha_min.")
    if beta_hi <= beta_lo:
        raise ValueError("beta_max must be greater than beta_min.")

    out = Path(out)
    theta_obs = math.radians(inclination_deg)
    alpha = np.linspace(alpha_lo, alpha_hi, grid, dtype=np.float64)
    beta = np.linspace(beta_lo, beta_hi, grid, dtype=np.float64)
    shape = (grid, grid)
    transfer_shape = (max_order, grid, grid)
    event_code = np.full(shape, EVENT_CODES["invalid"], dtype=np.int16)
    failure_code = np.zeros(shape, dtype=np.int16)
    crossing_count = np.zeros(shape, dtype=np.int16)
    disk_r = np.full(transfer_shape, np.nan, dtype=np.float64)
    disk_phi = np.full(transfer_shape, np.nan, dtype=np.float64)
    disk_time = np.full(transfer_shape, np.nan, dtype=np.float64)
    disk_g = np.full(transfer_shape, np.nan, dtype=np.float64)

    r_in = isco_radius(params)
    trace_config = TraceConfig(
        max_lambda=max_lambda,
        r_escape=2.0 * r_obs,
        horizon_eps=horizon_eps,
        max_step=max_step,
        stop_on_disk=False,
    )

    for row, beta_value in enumerate(beta):
        for col, alpha_value in enumerate(alpha):
            diag = trace_ray(
                params,
                CameraConfig(
                    r_obs=r_obs,
                    theta_obs=theta_obs,
                    alpha=float(alpha_value),
                    beta=float(beta_value),
                ),
                trace_config,
            )
            event_code[row, col] = EVENT_CODES[diag.event]
            failure_code[row, col] = FAILURE_CODES.get(
                diag.failure_reason, FAILURE_CODES["solver_failure"]
            )
            stored = 0
            for idx, r_cross in enumerate(diag.disk_crossing_r):
                if not (r_in <= r_cross <= r_out):
                    continue
                if stored >= max_order:
                    break
                disk_r[stored, row, col] = r_cross
                disk_phi[stored, row, col] = diag.disk_crossing_phi[idx]
                disk_time[stored, row, col] = diag.disk_crossing_t[idx]
                disk_g[stored, row, col] = redshift_factor(
                    params,
                    r=r_cross,
                    p_t=diag.disk_crossing_p_t[idx],
                    p_phi=diag.disk_crossing_p_phi[idx],
                )
                stored += 1
            crossing_count[row, col] = stored
        if verbose:
            print(f"completed row {row + 1}/{grid}", flush=True)

    _write_disk_transfer(
        out=out,
        params=params,
        inclination_deg=inclination_deg,
        r_obs=r_obs,
        grid=grid,
        alpha=alpha,
        beta=beta,
        alpha_min=alpha_lo,
        alpha_max=alpha_hi,
        beta_min=beta_lo,
        beta_max=beta_hi,
        max_lambda=max_lambda,
        horizon_eps=horizon_eps,
        max_step=max_step,
        r_in=r_in,
        r_out=r_out,
        max_order=max_order,
        command=command,
        event_code=event_code,
        failure_code=failure_code,
        crossing_count=crossing_count,
        disk_r=disk_r,
        disk_phi=disk_phi,
        disk_time=disk_time,
        disk_g=disk_g,
    )

    valid_by_order = [
        int(np.count_nonzero(np.isfinite(disk_r[order]))) for order in range(max_order)
    ]
    return {
        "out": str(out),
        "schema": SCHEMA,
        "metric": {"M": params.M, "a": params.a},
        "inclination_deg": inclination_deg,
        "grid": grid,
        "alpha_range": [alpha_lo, alpha_hi],
        "beta_range": [beta_lo, beta_hi],
        "r_in": r_in,
        "r_out": r_out,
        "max_order": max_order,
        "valid_by_order": valid_by_order,
        "pixels_with_disk_hit": int(np.count_nonzero(crossing_count > 0)),
    }


def _write_disk_transfer(
    *,
    out: Path,
    params: MetricParams,
    inclination_deg: float,
    r_obs: float,
    grid: int,
    alpha: np.ndarray,
    beta: np.ndarray,
    alpha_min: float,
    alpha_max: float,
    beta_min: float,
    beta_max: float,
    max_lambda: float,
    horizon_eps: float,
    max_step: float,
    r_in: float,
    r_out: float,
    max_order: int,
    command: str,
    event_code: np.ndarray,
    failure_code: np.ndarray,
    crossing_count: np.ndarray,
    disk_r: np.ndarray,
    disk_phi: np.ndarray,
    disk_time: np.ndarray,
    disk_g: np.ndarray,
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(out, "w") as handle:
        handle.attrs["schema"] = SCHEMA
        handle.attrs["M"] = params.M
        handle.attrs["a"] = params.a
        handle.attrs["inclination_deg"] = inclination_deg
        handle.attrs["r_obs"] = r_obs
        handle.attrs["grid"] = grid
        handle.attrs["alpha_min"] = alpha_min
        handle.attrs["alpha_max"] = alpha_max
        handle.attrs["beta_min"] = beta_min
        handle.attrs["beta_max"] = beta_max
        handle.attrs["max_lambda"] = max_lambda
        handle.attrs["horizon_eps"] = horizon_eps
        handle.attrs["max_step"] = max_step
        handle.attrs["r_in"] = r_in
        handle.attrs["r_out"] = r_out
        handle.attrs["max_order"] = max_order
        handle.attrs["generation_command"] = command
        handle.attrs["coordinate_system"] = "Boyer-Lindquist exterior"
        handle.attrs["disk_model"] = "equatorial geometrically thin Keplerian disk"
        handle.attrs["units"] = "G = c = M = 1 unless attrs[M] differs"
        handle.create_dataset("alpha", data=alpha)
        handle.create_dataset("beta", data=beta)
        handle.create_dataset("disk_m", data=np.arange(max_order, dtype=np.int16))
        event_ds = handle.create_dataset(
            "event_code", data=event_code, compression="gzip", shuffle=True
        )
        for event, code in EVENT_CODES.items():
            event_ds.attrs[f"code_{event}"] = code
        failure_ds = handle.create_dataset(
            "failure_code", data=failure_code, compression="gzip", shuffle=True
        )
        for failure, code in FAILURE_CODES.items():
            failure_ds.attrs[f"code_{failure}"] = code
        handle.create_dataset(
            "disk_crossing_count", data=crossing_count, compression="gzip", shuffle=True
        )
        handle.create_dataset("disk_r_m", data=disk_r, compression="gzip", shuffle=True)
        handle.create_dataset("disk_phi_m", data=disk_phi, compression="gzip", shuffle=True)
        handle.create_dataset("disk_t_m", data=disk_time, compression="gzip", shuffle=True)
        handle.create_dataset("disk_g_m", data=disk_g, compression="gzip", shuffle=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True, help="Dimensionless spin a/M.")
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, required=True)
    parser.add_argument("--grid", type=int, default=129)
    parser.add_argument("--alpha-min", type=float, default=None)
    parser.add_argument("--alpha-max", type=float, required=True)
    parser.add_argument("--beta-min", type=float, default=None)
    parser.add_argument("--beta-max", type=float, required=True)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--max-lambda", type=float, default=1200.0)
    parser.add_argument("--horizon-eps", type=float, default=TraceConfig.horizon_eps)
    parser.add_argument("--max-step", type=float, default=TraceConfig.max_step)
    parser.add_argument("--r-out", type=float, default=30.0)
    parser.add_argument("--max-order", type=int, default=3)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    params = MetricParams(M=args.mass, a=args.spin * args.mass)
    summary = generate_disk_transfer(
        params=params,
        inclination_deg=args.inclination_deg,
        grid=args.grid,
        alpha_min=args.alpha_min,
        alpha_max=args.alpha_max,
        beta_min=args.beta_min,
        beta_max=args.beta_max,
        r_obs=args.r_obs,
        max_lambda=args.max_lambda,
        horizon_eps=args.horizon_eps,
        max_step=args.max_step,
        r_out=args.r_out,
        max_order=args.max_order,
        out=args.out,
        command=" ".join(sys.argv),
        verbose=not args.quiet,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
