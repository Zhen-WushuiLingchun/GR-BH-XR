"""Cross-check a native NPGS Q=0 audit capture against the CPU f64 Kerr solver."""

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

from .geodesic import trace_state
from .geodesic_ks import ks_state_to_bl_state, trace_state_ks
from .metric_ks import ks_hamiltonian, ks_inverse_metric, ks_radius
from .npgs_audit import RAW_SCHEMA_V2, RAW_SCHEMA_V3, RAW_SCHEMA_V4, load_native_audit
from .types import MetricParams, RayState, TraceConfig


NPGS_TO_PYTHON_SPATIAL = np.array(
    [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]], dtype=np.float64
)
CPU_EVENT_CODES = {"capture": 0, "escape": 1, "invalid": 3}


@dataclass(frozen=True)
class NpgsKerrThresholds:
    """Acceptance thresholds inherited from the native migration plan."""

    event_agreement: float = 0.98
    direction_median_rad: float = 1.0e-4
    direction_rms_rad: float = 5.0e-4
    minimum_native_quality: float = 2.0


@dataclass(frozen=True)
class KerrSchildInvariants:
    """Kerr null-geodesic invariants evaluated in Cartesian KS coordinates."""

    hamiltonian: float
    energy: float
    angular_momentum_z: float
    carter_q: float


def native_initial_state_to_python_ks(
    initial_x_native: np.ndarray,
    initial_p_cov_native: np.ndarray,
) -> RayState:
    """Convert an NPGS backward-ray state to the CPU positive-affine KS convention.

    NPGS stores `(x, y, z, t)` with spin along `+y` and advances its visual
    backward ray with a negative affine step.  The CPU reference stores
    `(t, x, y, z)` with spin along `+z` and advances positive affine parameter.
    The proper spatial rotation is `(x, y, z)_N -> (x, -z, y)_P`; the complete
    covector is negated to reverse NPGS's affine orientation without changing
    the null geodesic.
    """

    x_native = np.asarray(initial_x_native, dtype=np.float64)
    p_native = np.asarray(initial_p_cov_native, dtype=np.float64)
    if x_native.shape != (4,) or p_native.shape != (4,):
        raise ValueError("Native canonical position and momentum must each contain four values.")
    x_python = np.concatenate(([x_native[3]], NPGS_TO_PYTHON_SPATIAL @ x_native[:3]))
    p_python = -np.concatenate(([p_native[3]], NPGS_TO_PYTHON_SPATIAL @ p_native[:3]))
    return RayState(x=x_python, p=p_python)


def python_direction_to_npgs(direction: np.ndarray) -> np.ndarray:
    """Rotate a Python `+z`-spin Cartesian direction into NPGS `+y` coordinates."""

    values = np.asarray(direction, dtype=np.float64)
    if values.shape != (3,):
        raise ValueError("Direction must contain three Cartesian components.")
    return NPGS_TO_PYTHON_SPATIAL.T @ values


def python_ks_momentum_direction_to_npgs(
    params: MetricParams,
    x_python_ks: np.ndarray,
    p_cov_python_ks: np.ndarray,
) -> np.ndarray:
    """Return the outgoing spatial momentum in NPGS Cartesian coordinates.

    Both inputs use the Python `(t, x, y, z)` ingoing Kerr-Schild chart.  The
    native NPGS escape buffer is computed from the raised Cartesian momentum,
    so this helper keeps the direction comparison in the same regular chart
    instead of mixing in the asymptotic Boyer-Lindquist spherical projection.
    """

    x = np.asarray(x_python_ks, dtype=np.float64)
    p_cov = np.asarray(p_cov_python_ks, dtype=np.float64)
    if x.shape != (4,) or p_cov.shape != (4,):
        raise ValueError("Kerr-Schild position and momentum must each contain four values.")
    p_contra = ks_inverse_metric(params, x[1:4]) @ p_cov
    spatial = p_contra[1:4]
    norm = float(np.linalg.norm(spatial))
    if not math.isfinite(norm) or norm <= 0.0:
        raise ValueError("Kerr-Schild contravariant spatial momentum is not finite.")
    return python_direction_to_npgs(spatial / norm)


def python_ks_invariants(
    params: MetricParams,
    x_python_ks: np.ndarray,
    p_cov_python_ks: np.ndarray,
) -> KerrSchildInvariants:
    """Evaluate `H`, `E`, `L_z`, and Carter `Q` without a BL chart change.

    The angular expression for `Q` is algebraically identical to the BL
    definition, but reconstructs `p_theta` from the Cartesian covector and the
    oblate-spheroidal coordinate basis.  This remains usable at the outer
    horizon where the full Boyer-Lindquist canonical transform is singular.
    `Q` is reported as NaN on the rotation axis, where this chart expression is
    ill-conditioned even though the geodesic itself can be regular.
    """

    x = np.asarray(x_python_ks, dtype=np.float64)
    p_cov = np.asarray(p_cov_python_ks, dtype=np.float64)
    if x.shape != (4,) or p_cov.shape != (4,):
        raise ValueError("Kerr-Schild position and momentum must each contain four values.")

    xyz = x[1:4]
    r = ks_radius(params, xyz)
    if not math.isfinite(r) or r <= 0.0:
        raise ValueError("Kerr-Schild invariants are undefined at non-positive radius.")
    cos_theta = float(np.clip(xyz[2] / r, -1.0, 1.0))
    sin2_theta = max(0.0, 1.0 - cos_theta * cos_theta)
    energy = -float(p_cov[0])
    angular_momentum_z = float(xyz[0] * p_cov[2] - xyz[1] * p_cov[1])

    carter_q = math.nan
    if sin2_theta > 1.0e-10:
        sin_theta = math.sqrt(sin2_theta)
        p_theta = (
            p_cov[1] * xyz[0] * cos_theta / sin_theta
            + p_cov[2] * xyz[1] * cos_theta / sin_theta
            - p_cov[3] * r * sin_theta
        )
        carter_q = float(
            p_theta * p_theta
            + cos_theta
            * cos_theta
            * (
                angular_momentum_z * angular_momentum_z / sin2_theta
                - params.a * params.a * energy * energy
            )
        )

    return KerrSchildInvariants(
        hamiltonian=ks_hamiltonian(params, x, p_cov),
        energy=energy,
        angular_momentum_z=angular_momentum_z,
        carter_q=carter_q,
    )


def validate_npgs_kerr_capture(
    raw_path: Path | str,
    *,
    metadata_path: Path | str | None = None,
    samples: int = 257,
    critical_band_pixels: int = 1,
    max_lambda: float = 1400.0,
    max_step: float = 2.0,
    out_json: Path | str | None = None,
    out_h5: Path | str | None = None,
    thresholds: NpgsKerrThresholds = NpgsKerrThresholds(),
    command: str = "",
) -> dict[str, Any]:
    """Run the independent Q=0 CPU comparison and persist its evidence."""

    capture = load_native_audit(raw_path, metadata_path=metadata_path)
    metadata = capture.metadata
    if metadata["schema"] not in (RAW_SCHEMA_V2, RAW_SCHEMA_V3, RAW_SCHEMA_V4) or capture.initial_ingoing_x is None:
        raise ValueError("The Q=0 cross-check requires native audit raw schema v2 canonical states.")
    parameters = metadata["parameters"]
    charge = float(parameters["charge_Q_over_M"])
    if abs(charge) > 1.0e-12:
        raise ValueError("This validator is intentionally restricted to Q_charge=0 Kerr captures.")
    if str(parameters.get("observer_mode")) != "static":
        raise ValueError("The initial native Kerr gate currently requires observer_mode=static.")

    mass = float(parameters["M_internal"])
    params = MetricParams(M=mass, a=mass * float(parameters["spin_a_over_M"]))
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
    )

    flat_indices = _sample_indices(capture.event_code.size, samples)
    rows, cols = np.unravel_index(flat_indices, capture.event_code.shape)
    boundary = _event_boundary_mask(capture.event_code, critical_band_pixels)
    native_failure_none = int(metadata["failure_codes"]["none"])
    native_invalid_code = int(metadata["event_codes"]["invalid"])

    count = flat_indices.size
    cpu_event = np.full(count, CPU_EVENT_CODES["invalid"], dtype=np.int8)
    cpu_min_r = np.full(count, np.nan, dtype=np.float64)
    cpu_h_max = np.full(count, np.nan, dtype=np.float64)
    cpu_q_drift = np.full(count, np.nan, dtype=np.float64)
    cpu_ks_h_max = np.full(count, np.nan, dtype=np.float64)
    initial_h_abs = np.full(count, np.nan, dtype=np.float64)
    direction_error = np.full(count, np.nan, dtype=np.float64)
    messages: list[str] = []

    for sample_index, (row, col) in enumerate(zip(rows, cols)):
        state_ks = native_initial_state_to_python_ks(
            capture.initial_ingoing_x[row, col], capture.initial_ingoing_p_cov[row, col]
        )
        initial_h_abs[sample_index] = abs(ks_hamiltonian(params, state_ks.x, state_ks.p))
        try:
            state_bl = ks_state_to_bl_state(params, state_ks)
            diagnostics = trace_state(
                params,
                state_bl,
                cfg,
                r_obs=float(parameters["r_obs_internal"]),
            )
        except Exception as exc:  # pragma: no cover - defensive evidence path
            messages.append(f"row={row}, col={col}: {type(exc).__name__}: {exc}")
            continue

        cpu_event[sample_index] = CPU_EVENT_CODES.get(diagnostics.event, 3)
        cpu_min_r[sample_index] = diagnostics.min_r
        cpu_h_max[sample_index] = diagnostics.h_max_abs
        cpu_q_drift[sample_index] = diagnostics.q_drift_abs
        if diagnostics.event == "escape":
            # The BL reference remains the trusted event classifier, including
            # captures.  Escaped-ray directions are retraced in f64 KS so the
            # comparison uses the same regular Cartesian direction definition
            # as NPGS rather than a finite-radius BL spherical projection.
            try:
                ks_diagnostics = trace_state_ks(
                    params,
                    state_ks,
                    cfg,
                    r_obs=float(parameters["r_obs_internal"]),
                )
                cpu_ks_h_max[sample_index] = ks_diagnostics.h_max_abs
                if ks_diagnostics.event != "escape":
                    messages.append(
                        f"row={row}, col={col}: KS direction reference ended as "
                        f"{ks_diagnostics.event}"
                    )
                    continue
                cpu_direction = python_ks_momentum_direction_to_npgs(
                    params,
                    ks_diagnostics.final_x,
                    ks_diagnostics.final_p,
                )
                native_direction = capture.escape_dir[row, col].astype(np.float64)
                native_direction /= np.linalg.norm(native_direction)
                direction_error[sample_index] = math.acos(
                    float(np.clip(np.dot(cpu_direction, native_direction), -1.0, 1.0))
                )
            except Exception as exc:  # pragma: no cover - defensive evidence path
                messages.append(
                    f"row={row}, col={col}: KS direction reference: "
                    f"{type(exc).__name__}: {exc}"
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
    stable_event_matches = stable_compared & (native_event == cpu_event)
    stable_escape = stable_event_matches & (native_event == int(metadata["event_codes"]["escape"]))
    finite_direction = stable_escape & np.isfinite(direction_error)
    missing_direction_reference = int(np.count_nonzero(stable_escape & ~np.isfinite(direction_error)))

    all_agreement = _fraction(native_event[compared] == cpu_event[compared])
    stable_agreement = _fraction(stable_event_matches[stable_compared])
    direction_values = direction_error[finite_direction]
    direction_median = _optional_stat(direction_values, np.median)
    direction_rms = _optional_stat(direction_values, lambda value: np.sqrt(np.mean(value * value)))
    direction_max = _optional_stat(direction_values, np.max)
    unexpected_native_failures = int(
        np.count_nonzero(stable_screen & (native_failure != native_failure_none))
    )
    cpu_invalid_stable = int(np.count_nonzero(stable & ~cpu_resolved))
    event_conflicts_stable = int(
        np.count_nonzero(stable_compared & (native_event != cpu_event))
    )
    integrator_contract = metadata.get("integrator_contract", {})
    fade_enabled = bool(integrator_contract.get("gravity_fade_enabled", True))
    endpoint = _native_endpoint_diagnostics(capture, params)

    passed = bool(
        stable_agreement is not None
        and stable_agreement >= thresholds.event_agreement
        and direction_median is not None
        and direction_median < thresholds.direction_median_rad
        and direction_rms is not None
        and direction_rms < thresholds.direction_rms_rad
        and unexpected_native_failures == 0
        and cpu_invalid_stable == 0
        and missing_direction_reference == 0
        and native_quality >= thresholds.minimum_native_quality
    )
    summary: dict[str, Any] = {
        "schema": "gr-bh-xr.npgs.kerr_crosscheck.v1",
        "source_raw": str(capture.raw_path),
        "command": command,
        "parameters": parameters,
        "samples_requested": int(samples),
        "samples_compared": int(count),
        "critical_band_pixels": int(critical_band_pixels),
        "event_agreement_all_resolved": all_agreement,
        "event_agreement_stable": stable_agreement,
        "event_conflicts_stable": event_conflicts_stable,
        "cpu_invalid_stable": cpu_invalid_stable,
        "native_failures_stable": unexpected_native_failures,
        "direction_samples_stable": int(direction_values.size),
        "direction_reference_missing_stable": missing_direction_reference,
        "direction_error_median_rad": direction_median,
        "direction_error_rms_rad": direction_rms,
        "direction_error_max_rad": direction_max,
        "initial_h_max_abs": _optional_stat(initial_h_abs[np.isfinite(initial_h_abs)], np.max),
        "cpu_h_max_abs": _optional_stat(cpu_h_max[np.isfinite(cpu_h_max)], np.max),
        "cpu_q_drift_max_abs": _optional_stat(
            cpu_q_drift[np.isfinite(cpu_q_drift)], np.max
        ),
        "cpu_ks_direction_trace_h_max_abs": _optional_stat(
            cpu_ks_h_max[np.isfinite(cpu_ks_h_max)], np.max
        ),
        "native_quality": native_quality,
        "native_endpoint_diagnostics": _endpoint_summary(
            endpoint,
            capture.event_code,
            metadata["event_codes"],
        ),
        "native_endpoint_interpretation": (
            "Escaped-ray endpoint H is a same-chart residual. Captured endpoint "
            "covectors can reach O(1e4) at the horizon, so re-evaluating H from "
            "serialized f32 components is cancellation-conditioned and is recorded "
            "but not gated. Endpoint E/L_z/Q drift remains an independent invariant "
            "diagnostic."
        ),
        "native_stepwise_diagnostics": {
            "q_drift_max_abs": _optional_stat(
                capture.q_drift_abs[np.isfinite(capture.q_drift_abs)], np.max
            ),
            "q_drift_p99_abs": _optional_stat(
                capture.q_drift_abs[np.isfinite(capture.q_drift_abs)],
                lambda values: np.percentile(values, 99.0),
            ),
            "interpretation": (
                "The native per-step maximum can include transient chart/turning-point "
                "spikes. Endpoint drift from the canonical raw-v2 states is the "
                "independent invariant gate; both values remain recorded."
            ),
        },
        "native_integrator_contract": integrator_contract,
        "thresholds": {
            "event_agreement_stable_min": thresholds.event_agreement,
            "direction_error_median_rad_max": thresholds.direction_median_rad,
            "direction_error_rms_rad_max": thresholds.direction_rms_rad,
            "native_quality_min": thresholds.minimum_native_quality,
        },
        "passed": passed,
        "exceptions": messages,
        "claim_boundary": (
            "This Q=0 gate validates NPGS's Kerr path from exact native launch states. "
            "BL f64 supplies exterior event classification; ingoing Cartesian KS f64 "
            "supplies the same-chart escaped-ray direction. "
            + (
                "Direction error includes the native visual gravity-fade approximation."
                if fade_enabled
                else "Native and CPU paths use exact Kerr geometry through the same finite escape boundary."
            )
        ),
    }

    if out_h5 is not None:
        out_h5_path = Path(out_h5).resolve()
        out_h5_path.parent.mkdir(parents=True, exist_ok=True)
        with h5py.File(out_h5_path, "w") as handle:
            for key, value in summary.items():
                if isinstance(value, (str, int, float, bool)) or value is None:
                    handle.attrs[key] = "null" if value is None else value
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
                "direction_error_rad": direction_error,
                "cpu_h_max_abs": cpu_h_max,
                "cpu_q_drift_abs": cpu_q_drift,
                "cpu_ks_direction_trace_h_max_abs": cpu_ks_h_max,
            }
            for name, values in datasets.items():
                handle.create_dataset(name, data=values, compression="gzip", shuffle=True)
            endpoint_group = handle.create_group("native_endpoint")
            for name, values in endpoint.items():
                endpoint_group.create_dataset(
                    name,
                    data=values,
                    compression="gzip",
                    shuffle=True,
                )
        summary["out_h5"] = str(out_h5_path)

    if out_json is not None:
        out_json_path = Path(out_json).resolve()
        out_json_path.parent.mkdir(parents=True, exist_ok=True)
        out_json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
    return summary


def _sample_indices(pixel_count: int, samples: int) -> np.ndarray:
    if pixel_count <= 0:
        raise ValueError("pixel_count must be positive.")
    if samples <= 0 or samples >= pixel_count:
        return np.arange(pixel_count, dtype=np.int64)
    centers = (np.arange(samples, dtype=np.float64) + 0.5) * pixel_count / samples
    return np.unique(np.minimum(centers.astype(np.int64), pixel_count - 1))


def _native_endpoint_diagnostics(
    capture,
    params: MetricParams,
) -> dict[str, np.ndarray]:
    """Evaluate native raw-v2 endpoint invariants over the complete image."""

    if (
        capture.initial_ingoing_x is None
        or capture.initial_ingoing_p_cov is None
        or capture.final_ingoing_x is None
        or capture.final_ingoing_p_cov is None
    ):
        raise ValueError("Native endpoint diagnostics require raw schema v2 canonical states.")

    shape = capture.event_code.shape
    initial_h = np.full(shape, np.nan, dtype=np.float64)
    final_h = np.full(shape, np.nan, dtype=np.float64)
    energy_drift = np.full(shape, np.nan, dtype=np.float64)
    lz_drift = np.full(shape, np.nan, dtype=np.float64)
    q_drift = np.full(shape, np.nan, dtype=np.float64)
    for row, col in np.ndindex(shape):
        initial_state = native_initial_state_to_python_ks(
            capture.initial_ingoing_x[row, col],
            capture.initial_ingoing_p_cov[row, col],
        )
        final_state = native_initial_state_to_python_ks(
            capture.final_ingoing_x[row, col],
            capture.final_ingoing_p_cov[row, col],
        )
        initial = python_ks_invariants(params, initial_state.x, initial_state.p)
        final = python_ks_invariants(params, final_state.x, final_state.p)
        initial_h[row, col] = abs(initial.hamiltonian)
        final_h[row, col] = abs(final.hamiltonian)
        energy_drift[row, col] = abs(final.energy - initial.energy)
        lz_drift[row, col] = abs(
            final.angular_momentum_z - initial.angular_momentum_z
        )
        if math.isfinite(initial.carter_q) and math.isfinite(final.carter_q):
            q_drift[row, col] = abs(final.carter_q - initial.carter_q)

    return {
        "h_initial_abs": initial_h,
        "h_final_abs": final_h,
        "energy_drift_abs": energy_drift,
        "lz_drift_abs": lz_drift,
        "q_drift_abs": q_drift,
    }


def _endpoint_summary(
    endpoint: dict[str, np.ndarray],
    event_code: np.ndarray,
    event_codes: dict[str, Any],
) -> dict[str, Any]:
    def summarize(mask: np.ndarray) -> dict[str, Any]:
        result: dict[str, Any] = {"count": int(np.count_nonzero(mask))}
        for name, values in endpoint.items():
            selected = values[mask & np.isfinite(values)]
            result[f"{name}_samples"] = int(selected.size)
            result[f"{name}_max"] = _optional_stat(selected, np.max)
            result[f"{name}_median"] = _optional_stat(selected, np.median)
        return result

    groups = {"all": summarize(np.ones(event_code.shape, dtype=bool))}
    for name in ("capture", "escape", "invalid"):
        if name in event_codes:
            groups[name] = summarize(event_code == int(event_codes[name]))
    return groups


def _event_boundary_mask(event_code: np.ndarray, radius: int) -> np.ndarray:
    if radius < 0:
        raise ValueError("critical_band_pixels must be non-negative.")
    event = np.asarray(event_code)
    boundary = np.zeros(event.shape, dtype=bool)
    boundary[1:, :] |= event[1:, :] != event[:-1, :]
    boundary[:-1, :] |= event[:-1, :] != event[1:, :]
    boundary[:, 1:] |= event[:, 1:] != event[:, :-1]
    boundary[:, :-1] |= event[:, :-1] != event[:, 1:]
    for _ in range(radius):
        expanded = boundary.copy()
        expanded[1:, :] |= boundary[:-1, :]
        expanded[:-1, :] |= boundary[1:, :]
        expanded[:, 1:] |= boundary[:, :-1]
        expanded[:, :-1] |= boundary[:, 1:]
        boundary = expanded
    return boundary


def _fraction(values: np.ndarray) -> float | None:
    return float(np.mean(values)) if values.size else None


def _optional_stat(values: np.ndarray, function) -> float | None:
    return float(function(values)) if values.size else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--samples", type=int, default=257)
    parser.add_argument("--critical-band-pixels", type=int, default=1)
    parser.add_argument("--max-lambda", type=float, default=1400.0)
    parser.add_argument("--max-step", type=float, default=2.0)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--h5", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = validate_npgs_kerr_capture(
        args.raw,
        metadata_path=args.metadata,
        samples=args.samples,
        critical_band_pixels=args.critical_band_pixels,
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
