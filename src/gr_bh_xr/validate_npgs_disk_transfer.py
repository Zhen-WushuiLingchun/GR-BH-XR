"""Cross-check NPGS native thin-disk transfer records against CPU f64 Kerr."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys
from typing import Any

import h5py
import numpy as np

from .disk import keplerian_omega, keplerian_u_t
from .geodesic_ks import ks_state_to_bl_state, trace_state_ks
from .npgs_audit import DISK_ORDERS, RAW_SCHEMA_V2, RAW_SCHEMA_V3, RAW_SCHEMA_V4, load_native_audit
from .types import MetricParams, TraceConfig
from .validate_npgs_kerr import _sample_indices, native_initial_state_to_python_ks


SCHEMA = "gr-bh-xr.npgs.disk-transfer-compare.v1"


@dataclass(frozen=True)
class NpgsDiskThresholds:
    """Acceptance thresholds for NPGS's quality-2 native disk records."""

    r_max_abs_error_m: float = 3.0e-2
    phi_max_error_rad: float = 5.0e-4
    delta_t_max_abs_error_m: float = 3.0e-2
    g_max_abs_error: float = 5.0e-4
    minimum_native_quality: float = 2.0


def finite_observer_disk_redshift(
    params: MetricParams,
    *,
    r: float,
    p_t_positive_affine: float,
    p_phi_positive_affine: float,
) -> float:
    """Return NPGS's local-observer disk redshift from the CPU replay covector.

    NPGS launches each camera ray with local frequency one and integrates it
    with a negative affine step.  The CPU replay negates the entire covector so
    it can advance the same path with positive affine parameter.  Undoing that
    sign gives ``E_native=p_t_cpu`` and ``L_native=-p_phi_cpu``.  Therefore
    ``g=1/[u^t(E_native-Omega L_native)]``.  This is a finite-observer ratio;
    it is intentionally not the asymptotic helper ``E/[u^t(E-Omega L)]``.
    """

    energy = float(p_t_positive_affine)
    angular_momentum = -float(p_phi_positive_affine)
    omega = keplerian_omega(params, r)
    u_t = keplerian_u_t(params, r)
    denominator = u_t * (energy - omega * angular_momentum)
    if not math.isfinite(denominator) or denominator <= 0.0:
        return math.nan
    return 1.0 / denominator


def validate_npgs_disk_transfer(
    raw_path: Path | str,
    *,
    metadata_path: Path | str | None = None,
    samples: int = 257,
    max_lambda: float = 1400.0,
    max_step: float = 0.5,
    out_json: Path | str | None = None,
    out_h5: Path | str | None = None,
    thresholds: NpgsDiskThresholds = NpgsDiskThresholds(),
    command: str = "",
) -> dict[str, Any]:
    """Replay exact native launch states and compare the first two crossings."""

    capture = load_native_audit(raw_path, metadata_path=metadata_path)
    metadata = capture.metadata
    parameters = metadata["parameters"]
    if metadata["schema"] not in (RAW_SCHEMA_V2, RAW_SCHEMA_V3, RAW_SCHEMA_V4) or capture.initial_ingoing_x is None:
        raise ValueError("NPGS disk validation requires raw-v2 canonical launch states.")
    if not bool(metadata["claims"]["disk_transfer_slots_valid"]):
        raise ValueError("The native capture does not claim valid disk-transfer slots.")
    if abs(float(parameters["charge_Q_over_M"])) > 1.0e-12:
        raise ValueError("The first native disk gate is intentionally restricted to Kerr Q=0.")
    if str(parameters.get("observer_mode")) != "static":
        raise ValueError("The first native disk gate requires a static finite-radius observer.")

    mass = float(parameters["M_internal"])
    params = MetricParams(M=mass, a=mass * float(parameters["spin_a_over_M"]))
    r_in = mass * float(parameters["disk_inner_radius_M"])
    r_out = mass * float(parameters["disk_outer_radius_M"])
    native_quality = float(parameters.get("quality", 0.0))
    raymarch_boundary = float(
        metadata.get("integrator_contract", {}).get("raymarch_boundary_internal", 501.0)
    )
    cfg = TraceConfig(
        max_lambda=float(max_lambda),
        r_escape=raymarch_boundary,
        horizon_eps=max(1.0e-4 * mass, 1.0e-7),
        rtol=1.0e-9,
        atol=1.0e-11,
        max_step=float(max_step),
        stop_on_disk=False,
    )

    flat_indices = _disk_sample_indices(capture, samples)
    rows, cols = np.unravel_index(flat_indices, capture.event_code.shape)
    count = flat_indices.size
    shape = (DISK_ORDERS, count)
    cpu_has_crossing = np.zeros(shape, dtype=bool)
    cpu_validity = np.zeros(shape, dtype=bool)
    cpu_flags = np.zeros(shape, dtype=np.int16)
    cpu_r = np.full(shape, np.nan, dtype=np.float64)
    cpu_phi = np.full(shape, np.nan, dtype=np.float64)
    cpu_delta_t = np.full(shape, np.nan, dtype=np.float64)
    cpu_g = np.full(shape, np.nan, dtype=np.float64)
    cpu_event = np.full(count, "invalid", dtype=object)
    cpu_h_max = np.full(count, np.nan, dtype=np.float64)
    messages: list[str] = []

    for sample_index, (row, col) in enumerate(zip(rows, cols)):
        state = native_initial_state_to_python_ks(
            capture.initial_ingoing_x[row, col],
            capture.initial_ingoing_p_cov[row, col],
        )
        try:
            observer_bl = ks_state_to_bl_state(params, state)
            # NPGS switches dynamically between ingoing and outgoing KS
            # charts.  A camera-backtraced captured ray is past-directed and
            # becomes ill-conditioned at the future-horizon boundary in the
            # CPU oracle's single ingoing chart.  Stop 0.01 M outside r_+;
            # every disk crossing under comparison occurs before this guard.
            diagnostics = trace_state_ks(
                params,
                state,
                cfg,
                r_obs=float(parameters["r_obs_internal"]),
                inner_horizon_eps=-1.0e-2 * mass,
            )
        except Exception as exc:  # pragma: no cover - defensive evidence path
            messages.append(f"row={row}, col={col}: {type(exc).__name__}: {exc}")
            continue
        cpu_event[sample_index] = diagnostics.event
        cpu_h_max[sample_index] = diagnostics.h_max_abs
        crossing_by_order = {
            int(order): index for index, order in enumerate(diagnostics.disk_crossing_order)
        }
        for order in range(DISK_ORDERS):
            crossing_index = crossing_by_order.get(order)
            if crossing_index is None:
                continue
            cpu_has_crossing[order, sample_index] = True
            radius = float(diagnostics.disk_crossing_r[crossing_index])
            phi = float(diagnostics.disk_crossing_phi[crossing_index])
            delay = float(observer_bl.x[0] - diagnostics.disk_crossing_t[crossing_index])
            redshift = finite_observer_disk_redshift(
                params,
                r=radius,
                p_t_positive_affine=diagnostics.disk_crossing_p_t[crossing_index],
                p_phi_positive_affine=diagnostics.disk_crossing_p_phi[crossing_index],
            )
            in_annulus = r_in <= radius <= r_out
            finite_transfer = all(math.isfinite(value) for value in (radius, phi, delay, redshift))
            flags = 0
            if not in_annulus:
                flags |= 1
            if not (math.isfinite(redshift) and redshift > 0.0):
                flags |= 2
            if not finite_transfer:
                flags |= 4
            cpu_flags[order, sample_index] = flags
            cpu_validity[order, sample_index] = flags == 0
            if flags == 0:
                cpu_r[order, sample_index] = radius / mass
                cpu_phi[order, sample_index] = phi
                cpu_delta_t[order, sample_index] = delay / mass
                cpu_g[order, sample_index] = redshift

    native_validity = capture.disk_validity[:, rows, cols]
    native_flags = capture.disk_flags[:, rows, cols]
    native_order = capture.disk_order[:, rows, cols]
    native_has_crossing = _native_crossing_presence(
        native_validity, native_flags, native_order
    )
    native_r = capture.disk_r_m[:, rows, cols].astype(np.float64)
    native_phi = np.arctan2(
        capture.disk_sin_phi_m[:, rows, cols].astype(np.float64),
        capture.disk_cos_phi_m[:, rows, cols].astype(np.float64),
    )
    native_delta_t = capture.disk_delta_t_m[:, rows, cols].astype(np.float64)
    native_g = capture.disk_g_m[:, rows, cols].astype(np.float64)

    both_valid = native_validity & cpu_validity
    crossing_presence_mismatch = native_has_crossing != cpu_has_crossing
    validity_mismatch = native_validity != cpu_validity
    flags_mismatch = native_flags != cpu_flags
    expected_orders = np.broadcast_to(np.arange(DISK_ORDERS)[:, None], shape)
    order_mismatch = native_has_crossing & (native_order != expected_orders)
    r_error = _masked_abs_error(native_r, cpu_r, both_valid)
    phi_error = np.full(shape, np.nan, dtype=np.float64)
    phi_error[both_valid] = np.abs(
        np.arctan2(
            np.sin(native_phi[both_valid] - cpu_phi[both_valid]),
            np.cos(native_phi[both_valid] - cpu_phi[both_valid]),
        )
    )
    delta_t_error = _masked_abs_error(native_delta_t, cpu_delta_t, both_valid)
    g_error = _masked_abs_error(native_g, cpu_g, both_valid)
    cpu_failure_count = int(np.count_nonzero(cpu_event == "invalid"))

    metrics = {
        "disk_r_max_abs_error_M": _nanmax_or_none(r_error),
        "disk_r_rms_error_M": _rms_or_none(r_error),
        "disk_phi_max_error_rad": _nanmax_or_none(phi_error),
        "disk_phi_rms_error_rad": _rms_or_none(phi_error),
        "disk_delta_t_max_abs_error_M": _nanmax_or_none(delta_t_error),
        "disk_delta_t_rms_error_M": _rms_or_none(delta_t_error),
        "disk_g_max_abs_error": _nanmax_or_none(g_error),
        "disk_g_rms_error": _rms_or_none(g_error),
    }
    passed = (
        int(np.count_nonzero(crossing_presence_mismatch)) == 0
        and int(np.count_nonzero(validity_mismatch)) == 0
        and int(np.count_nonzero(flags_mismatch)) == 0
        and int(np.count_nonzero(order_mismatch)) == 0
        and cpu_failure_count == 0
        and int(np.count_nonzero(both_valid)) > 0
        and metrics["disk_r_max_abs_error_M"] is not None
        and metrics["disk_r_max_abs_error_M"] < thresholds.r_max_abs_error_m
        and metrics["disk_phi_max_error_rad"] < thresholds.phi_max_error_rad
        and metrics["disk_delta_t_max_abs_error_M"] < thresholds.delta_t_max_abs_error_m
        and metrics["disk_g_max_abs_error"] < thresholds.g_max_abs_error
        and native_quality >= thresholds.minimum_native_quality
    )
    summary: dict[str, Any] = {
        "schema": SCHEMA,
        "passed": bool(passed),
        "source_raw": str(Path(raw_path).resolve()),
        "generation_command": command,
        "parameters": parameters,
        "sample_count": int(count),
        "native_valid_by_order": [
            int(np.count_nonzero(native_validity[order])) for order in range(DISK_ORDERS)
        ],
        "cpu_valid_by_order": [
            int(np.count_nonzero(cpu_validity[order])) for order in range(DISK_ORDERS)
        ],
        "compared_valid_by_order": [
            int(np.count_nonzero(both_valid[order])) for order in range(DISK_ORDERS)
        ],
        "crossing_presence_mismatch_count": int(
            np.count_nonzero(crossing_presence_mismatch)
        ),
        "validity_mismatch_count": int(np.count_nonzero(validity_mismatch)),
        "flags_mismatch_count": int(np.count_nonzero(flags_mismatch)),
        "order_mismatch_count": int(np.count_nonzero(order_mismatch)),
        "cpu_failure_count": cpu_failure_count,
        "cpu_h_max_abs": _nanmax_or_none(cpu_h_max),
        **metrics,
        "thresholds": {
            "disk_r_max_abs_error_M": thresholds.r_max_abs_error_m,
            "disk_phi_max_error_rad": thresholds.phi_max_error_rad,
            "disk_delta_t_max_abs_error_M": thresholds.delta_t_max_abs_error_m,
            "disk_g_max_abs_error": thresholds.g_max_abs_error,
            "native_quality_min": thresholds.minimum_native_quality,
        },
        "redshift_definition": metadata["claims"]["disk_redshift_definition"],
        "interpretation": (
            "The native runtime is the production implementation. CPU f64 only replays "
            "sampled exact launch states to validate true crossing order, BL coordinates, "
            "finite-observer redshift, and coordinate delay."
        ),
        "messages": messages,
    }
    if out_json is not None:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
    if out_h5 is not None:
        _write_h5(
            Path(out_h5),
            summary=summary,
            rows=rows,
            cols=cols,
            native_has_crossing=native_has_crossing,
            cpu_has_crossing=cpu_has_crossing,
            native_validity=native_validity,
            cpu_validity=cpu_validity,
            native_flags=native_flags,
            cpu_flags=cpu_flags,
            native_r=native_r,
            cpu_r=cpu_r,
            native_phi=native_phi,
            cpu_phi=cpu_phi,
            native_delta_t=native_delta_t,
            cpu_delta_t=cpu_delta_t,
            native_g=native_g,
            cpu_g=cpu_g,
            r_error=r_error,
            phi_error=phi_error,
            delta_t_error=delta_t_error,
            g_error=g_error,
            cpu_h_max=cpu_h_max,
        )
    return summary


def _disk_sample_indices(capture, samples: int) -> np.ndarray:
    base = _sample_indices(capture.event_code.size, samples)
    second_crossing = np.flatnonzero(
        _native_crossing_presence(
            capture.disk_validity,
            capture.disk_flags,
            capture.disk_order,
        )[1].ravel()
    )
    return np.unique(np.concatenate([base, second_crossing])).astype(np.int64)


def _native_crossing_presence(
    validity: np.ndarray, flags: np.ndarray, order: np.ndarray
) -> np.ndarray:
    present = validity | (flags != 0)
    present = present.copy()
    present[1] |= order[1] == 1
    return present


def _masked_abs_error(native: np.ndarray, cpu: np.ndarray, mask: np.ndarray) -> np.ndarray:
    result = np.full(native.shape, np.nan, dtype=np.float64)
    result[mask] = np.abs(native[mask] - cpu[mask])
    return result


def _nanmax_or_none(values: np.ndarray) -> float | None:
    finite = values[np.isfinite(values)]
    return float(np.max(finite)) if finite.size else None


def _rms_or_none(values: np.ndarray) -> float | None:
    finite = values[np.isfinite(values)]
    return float(np.sqrt(np.mean(finite * finite))) if finite.size else None


def _write_h5(out: Path, *, summary: dict[str, Any], **datasets: np.ndarray) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(out, "w") as handle:
        handle.attrs["schema"] = SCHEMA
        handle.attrs["summary_json"] = json.dumps(summary, sort_keys=True)
        for name, values in datasets.items():
            data = values.astype(np.uint8) if values.dtype == bool else values
            handle.create_dataset(name, data=data, compression="gzip", shuffle=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--samples", type=int, default=257)
    parser.add_argument("--max-lambda", type=float, default=1400.0)
    parser.add_argument("--max-step", type=float, default=0.5)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--h5", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = validate_npgs_disk_transfer(
        args.raw,
        metadata_path=args.metadata,
        samples=args.samples,
        max_lambda=args.max_lambda,
        max_step=args.max_step,
        out_json=args.out,
        out_h5=args.h5,
        command=" ".join(sys.argv),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
