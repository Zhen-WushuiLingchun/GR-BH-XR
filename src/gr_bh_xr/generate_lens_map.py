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

FAILURE_CODES = {
    "none": 0,
    "trace_exception": 1,
    "unclassified_max_lambda": 2,
    "solver_failure": 3,
    "axis_coordinate_singularity": 4,
    "polar_step_overshoot": 5,
}


def _validate_grid_args(grid: int, alpha_min: float, alpha_max: float, beta_min: float, beta_max: float) -> None:
    if grid < 2:
        raise ValueError("Lens-map grid must contain at least two samples per axis.")
    if alpha_max <= alpha_min:
        raise ValueError("alpha_max must be greater than alpha_min.")
    if beta_max <= beta_min:
        raise ValueError("beta_max must be greater than beta_min.")


def _failure_code(failure_reason: str) -> int:
    if failure_reason == "none":
        return FAILURE_CODES["none"]
    return FAILURE_CODES.get(failure_reason, FAILURE_CODES["solver_failure"])


def _write_lens_map(
    *,
    out: Path,
    params: MetricParams,
    inclination_deg: float,
    r_obs: float,
    grid: int,
    alpha_min: float,
    alpha_max: float,
    beta_min: float,
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
    azimuthal_winding: np.ndarray,
    image_order: np.ndarray,
    failure_code: np.ndarray,
    escape_theta: np.ndarray,
    escape_phi: np.ndarray,
    escape_dir_x: np.ndarray,
    escape_dir_y: np.ndarray,
    escape_dir_z: np.ndarray,
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(out, "w") as handle:
        handle.attrs["schema"] = "gr-bh-xr.phase1.lens_map.v6"
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
        handle.create_dataset(
            "azimuthal_winding",
            data=azimuthal_winding,
            compression="gzip",
            shuffle=True,
        )
        handle.create_dataset("image_order", data=image_order, compression="gzip", shuffle=True)
        failure_ds = handle.create_dataset(
            "failure_code", data=failure_code, compression="gzip", shuffle=True
        )
        for failure, code in FAILURE_CODES.items():
            failure_ds.attrs[f"code_{failure}"] = code
        handle.create_dataset("escape_theta", data=escape_theta, compression="gzip", shuffle=True)
        handle.create_dataset("escape_phi", data=escape_phi, compression="gzip", shuffle=True)
        handle.create_dataset("escape_dir_x", data=escape_dir_x, compression="gzip", shuffle=True)
        handle.create_dataset("escape_dir_y", data=escape_dir_y, compression="gzip", shuffle=True)
        handle.create_dataset("escape_dir_z", data=escape_dir_z, compression="gzip", shuffle=True)


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
    out: Path | str,
    alpha_min: float | None = None,
    beta_min: float | None = None,
    command: str = "",
    verbose: bool = True,
) -> dict[str, object]:
    """Trace a rectangular screen grid and persist diagnostic buffers."""

    out = Path(out)
    alpha_lo = -alpha_max if alpha_min is None else float(alpha_min)
    beta_lo = -beta_max if beta_min is None else float(beta_min)
    alpha_hi = float(alpha_max)
    beta_hi = float(beta_max)
    _validate_grid_args(grid, alpha_lo, alpha_hi, beta_lo, beta_hi)
    theta_obs = math.radians(inclination_deg)
    alpha = np.linspace(alpha_lo, alpha_hi, grid, dtype=np.float64)
    beta = np.linspace(beta_lo, beta_hi, grid, dtype=np.float64)

    shape = (grid, grid)
    event_code = np.full(shape, EVENT_CODES["invalid"], dtype=np.int16)
    min_r = np.full(shape, np.nan, dtype=np.float64)
    h_max_abs = np.full(shape, np.nan, dtype=np.float64)
    e_drift_abs = np.full(shape, np.nan, dtype=np.float64)
    lz_drift_abs = np.full(shape, np.nan, dtype=np.float64)
    q_drift_abs = np.full(shape, np.nan, dtype=np.float64)
    disk_crossings = np.zeros(shape, dtype=np.int16)
    azimuthal_winding = np.full(shape, np.nan, dtype=np.float64)
    image_order = np.zeros(shape, dtype=np.int16)
    failure_code = np.zeros(shape, dtype=np.int16)
    escape_theta = np.full(shape, np.nan, dtype=np.float64)
    escape_phi = np.full(shape, np.nan, dtype=np.float64)
    escape_dir_x = np.full(shape, np.nan, dtype=np.float64)
    escape_dir_y = np.full(shape, np.nan, dtype=np.float64)
    escape_dir_z = np.full(shape, np.nan, dtype=np.float64)

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
                failure_code[row, col] = FAILURE_CODES["trace_exception"]
                continue
            event_code[row, col] = EVENT_CODES[diag.event]
            failure_code[row, col] = _failure_code(diag.failure_reason)
            min_r[row, col] = diag.min_r
            h_max_abs[row, col] = diag.h_max_abs
            e_drift_abs[row, col] = diag.e_drift_abs
            lz_drift_abs[row, col] = diag.lz_drift_abs
            q_drift_abs[row, col] = diag.q_drift_abs
            disk_crossings[row, col] = diag.disk_crossings
            azimuthal_winding[row, col] = diag.azimuthal_winding
            image_order[row, col] = diag.image_order
            escape_theta[row, col] = diag.escape_theta
            escape_phi[row, col] = diag.escape_phi
            escape_dir_x[row, col] = diag.escape_dir_x
            escape_dir_y[row, col] = diag.escape_dir_y
            escape_dir_z[row, col] = diag.escape_dir_z

        if verbose:
            print(f"completed row {row + 1}/{grid}", flush=True)

    _write_lens_map(
        out=out,
        params=params,
        inclination_deg=inclination_deg,
        r_obs=r_obs,
        grid=grid,
        alpha_min=alpha_lo,
        alpha_max=alpha_hi,
        beta_min=beta_lo,
        beta_max=beta_hi,
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
        azimuthal_winding=azimuthal_winding,
        image_order=image_order,
        failure_code=failure_code,
        escape_theta=escape_theta,
        escape_phi=escape_phi,
        escape_dir_x=escape_dir_x,
        escape_dir_y=escape_dir_y,
        escape_dir_z=escape_dir_z,
    )

    counts = {
        event: int(np.count_nonzero(event_code == code)) for event, code in EVENT_CODES.items()
    }
    failure_counts = {
        failure: int(np.count_nonzero(failure_code == code))
        for failure, code in FAILURE_CODES.items()
    }
    finite_h = h_max_abs[np.isfinite(h_max_abs)]
    finite_order = image_order[event_code != EVENT_CODES["invalid"]]
    summary = {
        "out": str(out),
        "metric": {"M": params.M, "a": params.a},
        "inclination_deg": inclination_deg,
        "r_obs": r_obs,
        "grid": grid,
        "alpha_range": [alpha_lo, alpha_hi],
        "beta_range": [beta_lo, beta_hi],
        "event_counts": counts,
        "failure_counts": failure_counts,
        "max_image_order": int(np.max(finite_order)) if finite_order.size else None,
        "h_max_abs": float(np.max(finite_h)) if finite_h.size else None,
    }
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True, help="Dimensionless spin a/M.")
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, required=True)
    parser.add_argument("--grid", type=int, default=129)
    parser.add_argument(
        "--alpha-min",
        type=float,
        default=None,
        help="Optional lower alpha bound. Defaults to -alpha-max for symmetric maps.",
    )
    parser.add_argument("--alpha-max", type=float, required=True)
    parser.add_argument(
        "--beta-min",
        type=float,
        default=None,
        help="Optional lower beta bound. Defaults to -beta-max for symmetric maps.",
    )
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
        alpha_min=args.alpha_min,
        alpha_max=args.alpha_max,
        beta_min=args.beta_min,
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
