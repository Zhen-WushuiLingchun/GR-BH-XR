"""Generate Phase 1 lens-map diagnostic buffers as HDF5."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import h5py
import numpy as np

from .geodesic import trace_ray
from .types import CameraConfig, MetricParams, TraceConfig

EVENT_CODES = {
    "capture": 0,
    "escape": 1,
    "disk_crossing": 2,
    "invalid": 3,
}


def _validate_grid_args(grid: int, alpha_max: float, beta_max: float) -> None:
    if grid < 2:
        raise ValueError("Lens-map grid must contain at least two samples per axis.")
    if alpha_max <= 0.0 or beta_max <= 0.0:
        raise ValueError("Screen half-widths alpha_max and beta_max must be positive.")


def _write_lens_map(
    *,
    out: Path,
    params: MetricParams,
    inclination_deg: float,
    r_obs: float,
    grid: int,
    alpha_max: float,
    beta_max: float,
    max_lambda: float,
    horizon_eps: float,
    max_step: float,
    command: str,
    alpha: np.ndarray,
    beta: np.ndarray,
    event_code: np.ndarray,
    min_r: np.ndarray,
    h_max_abs: np.ndarray,
    e_drift_abs: np.ndarray,
    lz_drift_abs: np.ndarray,
    q_drift_abs: np.ndarray,
    disk_crossings: np.ndarray,
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(out, "w") as handle:
        handle.attrs["schema"] = "gr-bh-xr.phase1.lens_map.v1"
        handle.attrs["M"] = params.M
        handle.attrs["a"] = params.a
        handle.attrs["inclination_deg"] = inclination_deg
        handle.attrs["r_obs"] = r_obs
        handle.attrs["grid"] = grid
        handle.attrs["alpha_max"] = alpha_max
        handle.attrs["beta_max"] = beta_max
        handle.attrs["max_lambda"] = max_lambda
        handle.attrs["horizon_eps"] = horizon_eps
        handle.attrs["max_step"] = max_step
        handle.attrs["generation_command"] = command
        handle.attrs["coordinate_system"] = "Boyer-Lindquist exterior"
        handle.attrs["units"] = "G = c = M = 1 unless attrs[M] differs"

        handle.create_dataset("alpha", data=alpha)
        handle.create_dataset("beta", data=beta)
        event_ds = handle.create_dataset(
            "event_code", data=event_code, compression="gzip", shuffle=True
        )
        for event, code in EVENT_CODES.items():
            event_ds.attrs[f"code_{event}"] = code
        handle.create_dataset("min_r", data=min_r, compression="gzip", shuffle=True)
        handle.create_dataset("h_max_abs", data=h_max_abs, compression="gzip", shuffle=True)
        handle.create_dataset("e_drift_abs", data=e_drift_abs, compression="gzip", shuffle=True)
        handle.create_dataset("lz_drift_abs", data=lz_drift_abs, compression="gzip", shuffle=True)
        handle.create_dataset("q_drift_abs", data=q_drift_abs, compression="gzip", shuffle=True)
        handle.create_dataset(
            "disk_crossings", data=disk_crossings, compression="gzip", shuffle=True
        )


def generate_lens_map(
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
    out: Path,
    command: str = "",
    verbose: bool = True,
) -> dict[str, object]:
    """Trace a rectangular screen grid and persist diagnostic buffers."""

    _validate_grid_args(grid, alpha_max, beta_max)
    theta_obs = math.radians(inclination_deg)
    alpha = np.linspace(-alpha_max, alpha_max, grid, dtype=np.float64)
    beta = np.linspace(-beta_max, beta_max, grid, dtype=np.float64)

    shape = (grid, grid)
    event_code = np.full(shape, EVENT_CODES["invalid"], dtype=np.int16)
    min_r = np.full(shape, np.nan, dtype=np.float64)
    h_max_abs = np.full(shape, np.nan, dtype=np.float64)
    e_drift_abs = np.full(shape, np.nan, dtype=np.float64)
    lz_drift_abs = np.full(shape, np.nan, dtype=np.float64)
    q_drift_abs = np.full(shape, np.nan, dtype=np.float64)
    disk_crossings = np.zeros(shape, dtype=np.int16)

    trace_config = TraceConfig(
        max_lambda=max_lambda,
        r_escape=2.0 * r_obs,
        horizon_eps=horizon_eps,
        max_step=max_step,
    )

    for row, beta_value in enumerate(beta):
        for col, alpha_value in enumerate(alpha):
            try:
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
            except Exception:
                continue
            event_code[row, col] = EVENT_CODES[diag.event]
            min_r[row, col] = diag.min_r
            h_max_abs[row, col] = diag.h_max_abs
            e_drift_abs[row, col] = diag.e_drift_abs
            lz_drift_abs[row, col] = diag.lz_drift_abs
            q_drift_abs[row, col] = diag.q_drift_abs
            disk_crossings[row, col] = diag.disk_crossings

        if verbose:
            print(f"completed row {row + 1}/{grid}", flush=True)

    _write_lens_map(
        out=out,
        params=params,
        inclination_deg=inclination_deg,
        r_obs=r_obs,
        grid=grid,
        alpha_max=alpha_max,
        beta_max=beta_max,
        max_lambda=max_lambda,
        horizon_eps=horizon_eps,
        max_step=max_step,
        command=command,
        alpha=alpha,
        beta=beta,
        event_code=event_code,
        min_r=min_r,
        h_max_abs=h_max_abs,
        e_drift_abs=e_drift_abs,
        lz_drift_abs=lz_drift_abs,
        q_drift_abs=q_drift_abs,
        disk_crossings=disk_crossings,
    )

    counts = {
        event: int(np.count_nonzero(event_code == code)) for event, code in EVENT_CODES.items()
    }
    finite_h = h_max_abs[np.isfinite(h_max_abs)]
    summary = {
        "out": str(out),
        "metric": {"M": params.M, "a": params.a},
        "inclination_deg": inclination_deg,
        "r_obs": r_obs,
        "grid": grid,
        "event_counts": counts,
        "h_max_abs": float(np.max(finite_h)) if finite_h.size else None,
    }
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True, help="Dimensionless spin a/M.")
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, required=True)
    parser.add_argument("--grid", type=int, default=129)
    parser.add_argument("--alpha-max", type=float, required=True)
    parser.add_argument("--beta-max", type=float, required=True)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--max-lambda", type=float, default=1200.0)
    parser.add_argument("--horizon-eps", type=float, default=TraceConfig.horizon_eps)
    parser.add_argument("--max-step", type=float, default=TraceConfig.max_step)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    params = MetricParams(M=args.mass, a=args.spin * args.mass)
    result = generate_lens_map(
        params=params,
        inclination_deg=args.inclination_deg,
        grid=args.grid,
        alpha_max=args.alpha_max,
        beta_max=args.beta_max,
        r_obs=args.r_obs,
        max_lambda=args.max_lambda,
        horizon_eps=args.horizon_eps,
        max_step=args.max_step,
        out=args.out,
        command=" ".join(sys.argv),
        verbose=not args.quiet,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
