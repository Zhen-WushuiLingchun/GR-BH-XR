"""Validate NPGS camera polarization evidence against direct f64 transport."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from .metric_kn import KerrNewmanParams, ks_inverse_metric
from .npgs_audit import RAW_SCHEMA_V3, RAW_SCHEMA_V4, load_native_audit
from .polarization_kn import (
    project_null_covector_time,
    reproject_screen_basis,
    trace_polarization_basis_kn,
    walker_penrose_bl_reference,
)
from .types import TraceConfig
from .validate_npgs_kerr import NPGS_TO_PYTHON_SPATIAL, native_initial_state_to_python_ks


@dataclass(frozen=True)
class NpgsPolarizationThresholds:
    basis_norm_max_abs: float = 5.0e-6
    basis_orthogonality_max_abs: float = 5.0e-6
    native_wp_relative_median: float = 5.0e-6
    native_wp_relative_max: float = 1.0e-4
    transported_wp_relative_max: float = 1.0e-7
    transported_norm_drift_max: float = 1.0e-8
    transported_transverse_max: float = 1.0e-8


def validate_npgs_polarization(
    raw_path: Path | str,
    *,
    metadata_path: Path | str | None = None,
    samples: int = 16,
    out_json: Path | str | None = None,
    out_h5: Path | str | None = None,
    thresholds: NpgsPolarizationThresholds = NpgsPolarizationThresholds(),
    command: str = "",
) -> dict[str, Any]:
    """Run the camera-basis, native formula, and f64 transport gates."""

    if samples <= 0:
        raise ValueError("samples must be positive.")
    capture = load_native_audit(raw_path, metadata_path=metadata_path)
    if capture.metadata["schema"] not in (RAW_SCHEMA_V3, RAW_SCHEMA_V4):
        raise ValueError("Polarization validation requires native audit raw schema v3.")
    required = (
        capture.initial_ingoing_x,
        capture.initial_ingoing_p_cov,
        capture.camera_fx_cov_native,
        capture.camera_fy_cov_native,
        capture.camera_walker_penrose,
        capture.camera_basis_diagnostics,
    )
    if any(value is None for value in required):
        raise ValueError("Native audit v3 is missing camera polarization evidence.")

    parameters = capture.metadata["parameters"]
    mass = float(parameters["M_internal"])
    params = KerrNewmanParams(
        M=mass,
        a=mass * float(parameters["spin_a_over_M"]),
        charge=mass * float(parameters["charge_Q_over_M"]),
    )
    basis_diag = np.asarray(capture.camera_basis_diagnostics, dtype=np.float64)
    basis_valid = basis_diag[..., 3] > 0.5
    if not np.all(basis_valid):
        raise ValueError("Native audit contains an invalid camera polarization basis.")
    norm_error = np.abs(basis_diag[..., :2] - 1.0)
    orthogonality_error = np.abs(basis_diag[..., 2])

    native_relative_errors: list[float] = []
    for row, col in np.ndindex(capture.event_code.shape):
        state = native_initial_state_to_python_ks(
            capture.initial_ingoing_x[row, col],
            capture.initial_ingoing_p_cov[row, col],
        )
        inverse = ks_inverse_metric(params, state.x[1:4])
        for basis_index, native_cov in enumerate(
            (capture.camera_fx_cov_native[row, col], capture.camera_fy_cov_native[row, col])
        ):
            python_cov = _native_covector_to_python(native_cov)
            reference = walker_penrose_bl_reference(
                params, state.x, state.p, inverse @ python_cov
            )
            native_wp = complex(
                float(capture.camera_walker_penrose[row, col, 2 * basis_index]),
                float(capture.camera_walker_penrose[row, col, 2 * basis_index + 1]),
            )
            # The CPU state reverses the native affine orientation, hence -K.
            native_relative_errors.append(
                abs(native_wp + reference) / max(abs(reference), 1.0e-15)
            )

    sample_rows, sample_cols = _escape_samples(capture, samples)
    ray_h = np.full(sample_rows.size, np.nan)
    ray_norm = np.full(sample_rows.size, np.nan)
    ray_transverse = np.full(sample_rows.size, np.nan)
    ray_wp = np.full(sample_rows.size, np.nan)
    ray_shortcut = np.full(sample_rows.size, np.nan)
    ray_events: list[str] = []
    exact_boundary = float(
        capture.metadata.get("integrator_contract", {}).get(
            "exact_geometry_end_internal", 501.0
        )
    )
    cfg = TraceConfig(
        max_lambda=max(2000.0, 4.0 * exact_boundary),
        r_escape=exact_boundary,
        horizon_eps=0.02 * mass,
        rtol=1.0e-9,
        atol=1.0e-11,
        max_step=1.0,
    )
    for index, (row, col) in enumerate(zip(sample_rows, sample_cols)):
        state = native_initial_state_to_python_ks(
            capture.initial_ingoing_x[row, col],
            capture.initial_ingoing_p_cov[row, col],
        )
        state = project_null_covector_time(params, state)
        seed_covectors = np.asarray(
            [
                _native_covector_to_python(capture.camera_fx_cov_native[row, col]),
                _native_covector_to_python(capture.camera_fy_cov_native[row, col]),
            ]
        )
        basis_covectors = reproject_screen_basis(params, state, seed_covectors)
        diagnostics = trace_polarization_basis_kn(
            params,
            state,
            basis_covectors,
            cfg,
            r_obs=float(parameters["r_obs_internal"]),
        )
        ray_events.append(diagnostics.event)
        ray_h[index] = diagnostics.h_max_abs
        ray_norm[index] = float(np.max(diagnostics.norm_drift_abs))
        ray_transverse[index] = float(np.max(diagnostics.transverse_max_abs))
        ray_wp[index] = float(np.max(diagnostics.wp_relative_drift))
        ray_shortcut[index] = float(np.max(diagnostics.shortcut_relative_drift))

    native_relative = np.asarray(native_relative_errors)
    escaped = np.asarray([event == "escape" for event in ray_events])
    passed = bool(
        np.all(escaped)
        and float(np.max(norm_error)) < thresholds.basis_norm_max_abs
        and float(np.max(orthogonality_error)) < thresholds.basis_orthogonality_max_abs
        and float(np.median(native_relative)) < thresholds.native_wp_relative_median
        and float(np.max(native_relative)) < thresholds.native_wp_relative_max
        and float(np.max(ray_wp)) < thresholds.transported_wp_relative_max
        and float(np.max(ray_norm)) < thresholds.transported_norm_drift_max
        and float(np.max(ray_transverse)) < thresholds.transported_transverse_max
    )
    summary: dict[str, Any] = {
        "schema": "gr-bh-xr.npgs.polarization_crosscheck.v1",
        "source_raw": str(capture.raw_path),
        "command": command,
        "parameters": parameters,
        "camera_basis": {
            "valid": int(np.count_nonzero(basis_valid)),
            "total": int(basis_valid.size),
            "norm_error_max_abs": float(np.max(norm_error)),
            "orthogonality_error_max_abs": float(np.max(orthogonality_error)),
        },
        "native_formula_vs_f64": {
            "basis_samples": int(native_relative.size),
            "relative_error_median": float(np.median(native_relative)),
            "relative_error_p99": float(np.quantile(native_relative, 0.99)),
            "relative_error_max": float(np.max(native_relative)),
        },
        "direct_parallel_transport": {
            "rays": int(sample_rows.size),
            "escape": int(np.count_nonzero(escaped)),
            "h_max_abs": float(np.max(ray_h)),
            "norm_drift_max_abs": float(np.max(ray_norm)),
            "transverse_max_abs": float(np.max(ray_transverse)),
            "walker_penrose_relative_drift_max": float(np.max(ray_wp)),
            "rejected_shortcut_relative_drift_median": float(np.median(ray_shortcut)),
            "rejected_shortcut_relative_drift_max": float(np.max(ray_shortcut)),
        },
        "thresholds": thresholds.__dict__,
        "passed": passed,
        "claim_boundary": (
            "This gate validates the NPGS camera screen basis and complete "
            "Walker-Penrose geometric transport against direct f64 parallel "
            "transport. It does not validate the magnetic-field emission "
            "model, polarized radiative transfer, Faraday terms, or final Stokes imagery."
        ),
    }
    if out_h5 is not None:
        _write_h5(
            Path(out_h5),
            summary,
            sample_rows,
            sample_cols,
            ray_h,
            ray_norm,
            ray_transverse,
            ray_wp,
            ray_shortcut,
            native_relative,
        )
    if out_json is not None:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
    return summary


def _native_covector_to_python(values: np.ndarray) -> np.ndarray:
    native = np.asarray(values, dtype=np.float64)
    if native.shape != (4,):
        raise ValueError("Native polarization covector must contain four values.")
    return np.concatenate(([native[3]], NPGS_TO_PYTHON_SPATIAL @ native[:3]))


def _escape_samples(capture: Any, count: int) -> tuple[np.ndarray, np.ndarray]:
    escape_code = int(capture.metadata["event_codes"]["escape"])
    indices = np.argwhere(capture.event_code == escape_code)
    if indices.size == 0:
        raise ValueError("Polarization transport gate requires escaped native rays.")
    radii = capture.min_r_m[capture.event_code == escape_code]
    ordered = indices[np.argsort(radii)]
    selected = ordered[np.unique(np.linspace(0, len(ordered) - 1, min(count, len(ordered))).round().astype(int))]
    return selected[:, 0].astype(int), selected[:, 1].astype(int)


def _write_h5(
    path: Path,
    summary: dict[str, Any],
    rows: np.ndarray,
    cols: np.ndarray,
    h: np.ndarray,
    norm: np.ndarray,
    transverse: np.ndarray,
    wp: np.ndarray,
    shortcut: np.ndarray,
    native_relative: np.ndarray,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as handle:
        handle.attrs["schema"] = summary["schema"]
        handle.attrs["source_raw"] = summary["source_raw"]
        handle.attrs["passed"] = summary["passed"]
        handle.create_dataset("sample_row", data=rows)
        handle.create_dataset("sample_col", data=cols)
        handle.create_dataset("h_max_abs", data=h)
        handle.create_dataset("norm_drift_max_abs", data=norm)
        handle.create_dataset("transverse_max_abs", data=transverse)
        handle.create_dataset("walker_penrose_relative_drift", data=wp)
        handle.create_dataset("rejected_shortcut_relative_drift", data=shortcut)
        handle.create_dataset("native_formula_relative_error", data=native_relative)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--h5", type=Path)
    args = parser.parse_args()
    command = " ".join(str(value) for value in ["python", "-m", __package__ + ".validate_npgs_polarization"])
    summary = validate_npgs_polarization(
        args.raw,
        metadata_path=args.metadata,
        samples=args.samples,
        out_json=args.out,
        out_h5=args.h5,
        command=command,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
