"""Small f64 Kerr-Newman geodesic oracle for NPGS audit replay.

The native renderer remains NPGS.  This module integrates only explicit
canonical states emitted by its raw-v2 audit pass, using an independently
implemented Cartesian Kerr-Schild metric and SciPy DOP853.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.integrate import solve_ivp

from .metric_kn import (
    KerrNewmanParams,
    horizon_radius,
    ks_hamiltonian,
    ks_invariants,
    ks_inverse_metric,
    ks_inverse_metric_derivatives,
    ks_radius,
)
from .types import FloatArray, RayState, TraceConfig


@dataclass(frozen=True)
class KerrNewmanRayDiagnostics:
    event: str
    h_max_abs: float
    e_drift_abs: float
    lz_drift_abs: float
    q_drift_abs: float
    lambda_end: float
    steps: int
    min_r: float
    final_x: FloatArray
    final_p: FloatArray
    message: str = ""


def hamiltonian_rhs_kn(
    params: KerrNewmanParams, _lam: float, y: np.ndarray
) -> np.ndarray:
    x = y[:4]
    p = y[4:]
    xyz = x[1:4]
    dx = ks_inverse_metric(params, xyz) @ p
    derivatives = ks_inverse_metric_derivatives(params, xyz)
    dp = np.zeros(4, dtype=np.float64)
    for axis, derivative in enumerate(derivatives, start=1):
        dp[axis] = -0.5 * float(p @ derivative @ p)
    return np.concatenate([dx, dp])


def trace_state_kn(
    params: KerrNewmanParams,
    state: RayState,
    config: TraceConfig | None = None,
    *,
    r_obs: float | None = None,
) -> KerrNewmanRayDiagnostics:
    """Trace one explicit neutral-photon state to the horizon or escape sphere."""

    cfg = config or TraceConfig()
    y0 = np.concatenate([np.asarray(state.x, dtype=np.float64), np.asarray(state.p, dtype=np.float64)])
    observer_r = float(r_obs) if r_obs is not None else ks_radius(params, state.x[1:4])
    r_escape = cfg.r_escape if cfg.r_escape is not None else max(2.0 * observer_r, observer_r + 50.0)
    # This exterior audit gate classifies capture just before the horizon.  The
    # ingoing metric itself is regular there, but the exact event root can make
    # canonical covector components cancellation-conditioned for DOP853.
    capture_r = horizon_radius(params) + float(cfg.horizon_eps)

    def capture_event(_lam: float, y: np.ndarray) -> float:
        return ks_radius(params, y[1:4]) - capture_r

    capture_event.terminal = True  # type: ignore[attr-defined]
    capture_event.direction = -1.0  # type: ignore[attr-defined]

    def escape_event(_lam: float, y: np.ndarray) -> float:
        return ks_radius(params, y[1:4]) - r_escape

    escape_event.terminal = True  # type: ignore[attr-defined]
    escape_event.direction = 1.0  # type: ignore[attr-defined]

    try:
        solution = solve_ivp(
            lambda lam, y: hamiltonian_rhs_kn(params, lam, y),
            (0.0, cfg.max_lambda),
            y0,
            method="DOP853",
            rtol=cfg.rtol,
            atol=cfg.atol,
            max_step=cfg.max_step,
            events=(capture_event, escape_event),
        )
    except Exception as exc:  # pragma: no cover - defensive evidence path
        return _diagnostics(params, np.asarray([y0]), 0.0, "invalid", str(exc))

    event = "invalid"
    if solution.success and solution.t_events[0].size:
        event = "capture"
    elif solution.success and solution.t_events[1].size:
        event = "escape"
    message = solution.message if event != "invalid" else (
        solution.message if not solution.success else "Reached max_lambda without capture or escape."
    )
    return _diagnostics(params, solution.y.T, float(solution.t[-1]), event, message)


def momentum_direction_kn(
    params: KerrNewmanParams, x: FloatArray, p_cov: FloatArray
) -> FloatArray:
    """Return the unit outgoing Cartesian contravariant momentum direction."""

    p_contra = ks_inverse_metric(params, np.asarray(x, dtype=np.float64)[1:4]) @ np.asarray(
        p_cov, dtype=np.float64
    )
    direction = p_contra[1:4]
    norm = float(np.linalg.norm(direction))
    if not math.isfinite(norm) or norm <= 0.0:
        raise ValueError("Kerr-Newman outgoing momentum direction is not finite.")
    return direction / norm


def _diagnostics(
    params: KerrNewmanParams,
    y_values: np.ndarray,
    lambda_end: float,
    event: str,
    message: str,
) -> KerrNewmanRayDiagnostics:
    xs = y_values[:, :4]
    ps = y_values[:, 4:]
    invariants = [ks_invariants(params, x, p) for x, p in zip(xs, ps)]
    h = np.asarray([value.hamiltonian for value in invariants], dtype=np.float64)
    energy = np.asarray([value.energy for value in invariants], dtype=np.float64)
    lz = np.asarray([value.angular_momentum_z for value in invariants], dtype=np.float64)
    q = np.asarray([value.carter_q for value in invariants], dtype=np.float64)
    radii = np.asarray([ks_radius(params, x[1:4]) for x in xs], dtype=np.float64)
    return KerrNewmanRayDiagnostics(
        event=event,
        h_max_abs=_nanmax_abs(h),
        e_drift_abs=_nan_drift(energy),
        lz_drift_abs=_nan_drift(lz),
        q_drift_abs=_nan_drift(q),
        lambda_end=float(lambda_end),
        steps=int(y_values.shape[0]),
        min_r=float(np.min(radii)),
        final_x=xs[-1].copy(),
        final_p=ps[-1].copy(),
        message=message,
    )


def _nanmax_abs(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.max(np.abs(finite))) if finite.size else math.nan


def _nan_drift(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.max(finite) - np.min(finite)) if finite.size else math.nan
