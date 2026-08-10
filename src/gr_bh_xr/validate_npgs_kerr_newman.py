"""Cross-check native NPGS Kerr-Newman rays against the CPU f64 oracle."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from .geodesic_kn import momentum_direction_kn, trace_state_kn
from .metric_kn import KerrNewmanParams, ks_hamiltonian, ks_invariants
from .npgs_audit import RAW_SCHEMA_V2, RAW_SCHEMA_V3, RAW_SCHEMA_V4, load_native_audit
from .types import TraceConfig
from .validate_npgs_kerr import (
    CPU_EVENT_CODES,
    _event_boundary_mask,
    _fraction,
    _optional_stat,
    _sample_indices,
    native_initial_state_to_python_ks,
    python_direction_to_npgs,
)


@dataclass(frozen=True)
class NpgsKerrNewmanThresholds:
    """Fail-closed thresholds inherited from the native Kerr migration gate."""

    event_agreement: float = 0.98
    direction_median_rad: float = 1.0e-4
    direction_rms_rad: float = 5.0e-4
    minimum_native_quality: float = 2.0


def validate_npgs_kerr_newman_capture(
    raw_path: Path | str,
    *,
    metadata_path: Path | str | None = None,
    samples: int = 257,
    critical_band_pixels: int = 1,
    max_lambda: float = 1400.0,
    max_step: float = 2.0,
    horizon_eps_m: float = 0.02,
    out_json: Path | str | None = None,
    out_h5: Path | str | None = None,
    thresholds: NpgsKerrNewmanThresholds = NpgsKerrNewmanThresholds(),
    command: str = "",
) -> dict[str, Any]:
    """Replay exact native nonzero-charge states with the independent f64 oracle.

    The CPU capture surface is deliberately placed ``horizon_eps_m`` outside
    ``r_+``.  NPGS's past-directed camera rays are serialized in ingoing
    Kerr-Schild coordinates; their canonical covectors become ill-conditioned
    at the future horizon even though exterior event classification remains
    well defined.  This gate therefore validates exterior capture/escape and
    escaped directions, not maximal extension or horizon crossing.
    """

    capture = load_native_audit(raw_path, metadata_path=metadata_path)
    metadata = capture.metadata
    if metadata["schema"] not in (RAW_SCHEMA_V2, RAW_SCHEMA_V3, RAW_SCHEMA_V4) or capture.initial_ingoing_x is None:
        raise ValueError("The Kerr-Newman gate requires raw-v2 canonical states.")
    parameters = metadata["parameters"]
    charge_ratio = float(parameters["charge_Q_over_M"])
    if abs(charge_ratio) <= 1.0e-12:
        raise ValueError("Use validate_npgs_kerr for the Q_charge=0 limit.")
    if str(parameters.get("observer_mode")) != "static":
        raise ValueError("The first Kerr-Newman gate requires observer_mode=static.")
    if horizon_eps_m <= 0.0:
        raise ValueError("horizon_eps_m must be positive for the exterior gate.")

    mass = float(parameters["M_internal"])
    params = KerrNewmanParams(
        M=mass,
        a=mass * float(parameters["spin_a_over_M"]),
        charge=mass * charge_ratio,
    )
    native_quality = float(parameters.get("quality", 0.0))
    raymarch_boundary = float(
        metadata.get("integrator_contract", {}).get("raymarch_boundary_internal", 501.0)
    )
    config = TraceConfig(
        max_lambda=float(max_lambda),
        r_escape=raymarch_boundary,
        horizon_eps=float(horizon_eps_m) * mass,
        rtol=1.0e-9,
        atol=1.0e-11,
        max_step=float(max_step),
    )

    flat_indices = _sample_indices(capture.event_code.size, samples)
    rows, cols = np.unravel_index(flat_indices, capture.event_code.shape)
    boundary = _event_boundary_mask(capture.event_code, critical_band_pixels)
    native_failure_none = int(metadata["failure_codes"]["none"])
    native_invalid_code = int(metadata["event_codes"]["invalid"])

    count = flat_indices.size
    cpu_event = np.full(count, CPU_EVENT_CODES["invalid"], dtype=np.int8)
    cpu_min_r = np.full(count, np.nan, dtype=np.float64)
    cpu_steps = np.zeros(count, dtype=np.uint32)
    cpu_h_max = np.full(count, np.nan, dtype=np.float64)
    cpu_e_drift = np.full(count, np.nan, dtype=np.float64)
    cpu_lz_drift = np.full(count, np.nan, dtype=np.float64)
    cpu_q_drift = np.full(count, np.nan, dtype=np.float64)
    initial_h_abs = np.full(count, np.nan, dtype=np.float64)
    direction_error = np.full(count, np.nan, dtype=np.float64)
    endpoint_h_initial = np.full(count, np.nan, dtype=np.float64)
    endpoint_h_final = np.full(count, np.nan, dtype=np.float64)
    endpoint_e_drift = np.full(count, np.nan, dtype=np.float64)
    endpoint_lz_drift = np.full(count, np.nan, dtype=np.float64)
    endpoint_q_drift = np.full(count, np.nan, dtype=np.float64)
    messages: list[str] = []

    for sample_index, (row, col) in enumerate(zip(rows, cols)):
        state = native_initial_state_to_python_ks(
            capture.initial_ingoing_x[row, col],
            capture.initial_ingoing_p_cov[row, col],
        )
        initial_h_abs[sample_index] = abs(ks_hamiltonian(params, state.x, state.p))
        _record_native_endpoint(
            capture,
            params,
            row,
            col,
            sample_index,
            endpoint_h_initial,
            endpoint_h_final,
            endpoint_e_drift,
            endpoint_lz_drift,
            endpoint_q_drift,
        )
        try:
            diagnostics = trace_state_kn(
                params,
                state,
                config,
                r_obs=float(parameters["r_obs_internal"]),
            )
        except Exception as exc:  # pragma: no cover - defensive evidence path
            messages.append(f"row={row}, col={col}: {type(exc).__name__}: {exc}")
            continue

        cpu_event[sample_index] = CPU_EVENT_CODES.get(diagnostics.event, 3)
        cpu_min_r[sample_index] = diagnostics.min_r
        cpu_steps[sample_index] = diagnostics.steps
        cpu_h_max[sample_index] = diagnostics.h_max_abs
        cpu_e_drift[sample_index] = diagnostics.e_drift_abs
        cpu_lz_drift[sample_index] = diagnostics.lz_drift_abs
        cpu_q_drift[sample_index] = diagnostics.q_drift_abs
        if diagnostics.event == "escape" and capture.escape_valid[row, col]:
            cpu_direction = python_direction_to_npgs(
                momentum_direction_kn(params, diagnostics.final_x, diagnostics.final_p)
            )
            native_direction = capture.escape_dir[row, col].astype(np.float64)
            native_direction /= np.linalg.norm(native_direction)
            direction_error[sample_index] = math.acos(
                float(np.clip(np.dot(cpu_direction, native_direction), -1.0, 1.0))
            )

    native_event = capture.event_code[rows, cols]
    native_failure = capture.failure_code[rows, cols]
    native_event_valid = native_event != native_invalid_code
    native_resolved = native_event_valid & (native_failure == native_failure_none)
    cpu_resolved = cpu_event != CPU_EVENT_CODES["invalid"]
    compared = native_resolved & cpu_resolved
    stable_screen = native_event_valid & ~boundary[rows, cols]
    stable = native_resolved & ~boundary[rows, cols]
    stable_compared = stable & cpu_resolved
    stable_matches = stable_compared & (native_event == cpu_event)
    stable_escape = stable_matches & (native_event == int(metadata["event_codes"]["escape"]))
    finite_direction = stable_escape & np.isfinite(direction_error)

    all_agreement = _fraction(native_event[compared] == cpu_event[compared])
    stable_agreement = _fraction(stable_matches[stable_compared])
    direction_values = direction_error[finite_direction]
    direction_median = _optional_stat(direction_values, np.median)
    direction_rms = _optional_stat(
        direction_values, lambda values: np.sqrt(np.mean(values * values))
    )
    direction_max = _optional_stat(direction_values, np.max)
    unexpected_native_failures = int(
        np.count_nonzero(stable_screen & (native_failure != native_failure_none))
    )
    cpu_invalid_stable = int(np.count_nonzero(stable & ~cpu_resolved))
    event_conflicts_stable = int(
        np.count_nonzero(stable_compared & (native_event != cpu_event))
    )
    missing_direction = int(np.count_nonzero(stable_escape & ~np.isfinite(direction_error)))

    passed = bool(
        stable_agreement is not None
        and stable_agreement >= thresholds.event_agreement
        and direction_median is not None
        and direction_median < thresholds.direction_median_rad
        and direction_rms is not None
        and direction_rms < thresholds.direction_rms_rad
        and unexpected_native_failures == 0
        and cpu_invalid_stable == 0
        and missing_direction == 0
        and native_quality >= thresholds.minimum_native_quality
    )
    capture_mask = cpu_event == CPU_EVENT_CODES["capture"]
    escape_mask = cpu_event == CPU_EVENT_CODES["escape"]
    summary: dict[str, Any] = {
        "schema": "gr-bh-xr.npgs.kerr_newman_crosscheck.v1",
        "source_raw": str(capture.raw_path),
        "command": command,
        "parameters": parameters,
        "samples_requested": int(samples),
        "samples_compared": int(count),
        "critical_band_pixels": int(critical_band_pixels),
        "cpu_capture_offset_M": float(horizon_eps_m),
        "event_agreement_all_resolved": all_agreement,
        "event_agreement_stable": stable_agreement,
        "event_conflicts_stable": event_conflicts_stable,
        "cpu_invalid_stable": cpu_invalid_stable,
        "native_failures_stable": unexpected_native_failures,
        "direction_samples_stable": int(direction_values.size),
        "direction_reference_missing_stable": missing_direction,
        "direction_error_median_rad": direction_median,
        "direction_error_rms_rad": direction_rms,
        "direction_error_max_rad": direction_max,
        "initial_h_max_abs": _finite_stat(initial_h_abs, np.max),
        "cpu_diagnostics": {
            "capture": _cpu_group(capture_mask, cpu_h_max, cpu_e_drift, cpu_lz_drift, cpu_q_drift),
            "escape": _cpu_group(escape_mask, cpu_h_max, cpu_e_drift, cpu_lz_drift, cpu_q_drift),
        },
        "native_endpoint_diagnostics": {
            "capture": _endpoint_group(capture_mask, endpoint_h_initial, endpoint_h_final, endpoint_e_drift, endpoint_lz_drift, endpoint_q_drift),
            "escape": _endpoint_group(escape_mask, endpoint_h_initial, endpoint_h_final, endpoint_e_drift, endpoint_lz_drift, endpoint_q_drift),
        },
        "native_quality": native_quality,
        "thresholds": {
            "event_agreement_stable_min": thresholds.event_agreement,
            "direction_error_median_rad_max": thresholds.direction_median_rad,
            "direction_error_rms_rad_max": thresholds.direction_rms_rad,
            "native_quality_min": thresholds.minimum_native_quality,
        },
        "passed": passed,
        "exceptions": messages,
        "claim_boundary": (
            "This gate validates neutral null rays in the sub-extremal, exterior "
            "Kerr-Newman geometry from exact NPGS raw-v2 launch states. It does "
            "not validate charged particles, polarization transport, disk/jet "
            "emission, Cauchy-horizon continuation, or maximal extension."
        ),
        "capture_residual_interpretation": (
            "Past-directed camera rays represented in ingoing Kerr-Schild "
            "canonical variables become cancellation-conditioned at the future "
            "horizon. Capture H is recorded at r_plus + horizon_eps and is not a "
            "horizon-penetration gate; escaped-ray residuals retain that role."
        ),
    }

    if out_h5 is not None:
        out_h5_path = Path(out_h5).resolve()
        out_h5_path.parent.mkdir(parents=True, exist_ok=True)
        with h5py.File(out_h5_path, "w") as handle:
            handle.attrs["schema"] = summary["schema"]
            handle.attrs["summary_json"] = json.dumps(summary, sort_keys=True)
            datasets = {
                "row": rows.astype(np.uint32),
                "col": cols.astype(np.uint32),
                "native_event_code": native_event.astype(np.int8),
                "cpu_event_code": cpu_event,
                "native_failure_code": native_failure.astype(np.int16),
                "critical_boundary_excluded": boundary[rows, cols].astype(np.uint8),
                "stable_mask": stable.astype(np.uint8),
                "initial_h_abs": initial_h_abs,
                "native_min_r_internal": capture.records[rows, cols, 2],
                "native_steps": capture.records[rows, cols, 3],
                "cpu_min_r_internal": cpu_min_r,
                "cpu_steps": cpu_steps,
                "direction_error_rad": direction_error,
                "cpu_h_max_abs": cpu_h_max,
                "cpu_e_drift_abs": cpu_e_drift,
                "cpu_lz_drift_abs": cpu_lz_drift,
                "cpu_q_drift_abs": cpu_q_drift,
                "native_endpoint_h_initial_abs": endpoint_h_initial,
                "native_endpoint_h_final_abs": endpoint_h_final,
                "native_endpoint_e_drift_abs": endpoint_e_drift,
                "native_endpoint_lz_drift_abs": endpoint_lz_drift,
                "native_endpoint_q_drift_abs": endpoint_q_drift,
            }
            for name, values in datasets.items():
                handle.create_dataset(name, data=values, compression="gzip", shuffle=True)
        summary["out_h5"] = str(out_h5_path)

    if out_json is not None:
        out_json_path = Path(out_json).resolve()
        out_json_path.parent.mkdir(parents=True, exist_ok=True)
        out_json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
    return summary


def _record_native_endpoint(
    capture,
    params: KerrNewmanParams,
    row: int,
    col: int,
    index: int,
    h_initial: np.ndarray,
    h_final: np.ndarray,
    e_drift: np.ndarray,
    lz_drift: np.ndarray,
    q_drift: np.ndarray,
) -> None:
    initial = native_initial_state_to_python_ks(
        capture.initial_ingoing_x[row, col], capture.initial_ingoing_p_cov[row, col]
    )
    final = native_initial_state_to_python_ks(
        capture.final_ingoing_x[row, col], capture.final_ingoing_p_cov[row, col]
    )
    first = ks_invariants(params, initial.x, initial.p)
    last = ks_invariants(params, final.x, final.p)
    h_initial[index] = abs(first.hamiltonian)
    h_final[index] = abs(last.hamiltonian)
    e_drift[index] = abs(last.energy - first.energy)
    lz_drift[index] = abs(last.angular_momentum_z - first.angular_momentum_z)
    if math.isfinite(first.carter_q) and math.isfinite(last.carter_q):
        q_drift[index] = abs(last.carter_q - first.carter_q)


def _cpu_group(
    mask: np.ndarray,
    h: np.ndarray,
    e: np.ndarray,
    lz: np.ndarray,
    q: np.ndarray,
) -> dict[str, Any]:
    return {
        "count": int(np.count_nonzero(mask)),
        "h_max_abs": _finite_stat(h[mask], np.max),
        "e_drift_max_abs": _finite_stat(e[mask], np.max),
        "lz_drift_max_abs": _finite_stat(lz[mask], np.max),
        "q_drift_max_abs": _finite_stat(q[mask], np.max),
    }


def _endpoint_group(
    mask: np.ndarray,
    h_initial: np.ndarray,
    h_final: np.ndarray,
    e: np.ndarray,
    lz: np.ndarray,
    q: np.ndarray,
) -> dict[str, Any]:
    return {
        "count": int(np.count_nonzero(mask)),
        "h_initial_max_abs": _finite_stat(h_initial[mask], np.max),
        "h_final_max_abs": _finite_stat(h_final[mask], np.max),
        "e_drift_max_abs": _finite_stat(e[mask], np.max),
        "lz_drift_max_abs": _finite_stat(lz[mask], np.max),
        "q_drift_max_abs": _finite_stat(q[mask], np.max),
    }


def _finite_stat(values: np.ndarray, function) -> float | None:
    finite = np.asarray(values)[np.isfinite(values)]
    return float(function(finite)) if finite.size else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--samples", type=int, default=257)
    parser.add_argument("--critical-band-pixels", type=int, default=1)
    parser.add_argument("--max-lambda", type=float, default=1400.0)
    parser.add_argument("--max-step", type=float, default=2.0)
    parser.add_argument("--horizon-eps-m", type=float, default=0.02)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--h5", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = validate_npgs_kerr_newman_capture(
        args.raw,
        metadata_path=args.metadata,
        samples=args.samples,
        critical_band_pixels=args.critical_band_pixels,
        max_lambda=args.max_lambda,
        max_step=args.max_step,
        horizon_eps_m=args.horizon_eps_m,
        out_json=args.out,
        out_h5=args.h5,
        command=" ".join(sys.argv),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
