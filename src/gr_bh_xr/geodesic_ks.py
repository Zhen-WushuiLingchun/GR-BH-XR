"""CPU Kerr-Schild reference null-geodesic tracing.

This module is the first Stage A horizon-penetrating tracer. It is deliberately
kept separate from the Boyer-Lindquist tracer until BL-vs-KS cross-validation is
complete enough to promote it into the shared validation pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.integrate import solve_ivp

from .metric import delta, hamiltonian as bl_hamiltonian, horizon_radius
from .metric_ks import (
    bl_to_ks_cartesian,
    ks_hamiltonian,
    ks_inverse_metric,
    ks_inverse_metric_derivatives,
    ks_radius,
)
from .types import FloatArray, MetricParams, RayState, TraceConfig


@dataclass(frozen=True)
class KSRayDiagnostics:
    """Minimal diagnostics for the Stage A Kerr-Schild tracer."""

    event: str
    h_max_abs: float
    e_drift_abs: float
    lz_drift_abs: float
    lambda_end: float
    steps: int
    min_r: float
    final_r: float
    message: str = ""


def hamiltonian_rhs_ks(params: MetricParams, _lam: float, y: np.ndarray) -> np.ndarray:
    """Hamiltonian equations for canonical Kerr-Schild state `(x^mu, p_mu)`."""

    x = y[:4]
    p = y[4:]
    xyz = x[1:4]

    g_inv = ks_inverse_metric(params, xyz)
    dx = g_inv @ p
    d_g_x, d_g_y, d_g_z = ks_inverse_metric_derivatives(params, xyz)
    dp = np.zeros(4, dtype=np.float64)
    dp[1] = -0.5 * float(p @ d_g_x @ p)
    dp[2] = -0.5 * float(p @ d_g_y @ p)
    dp[3] = -0.5 * float(p @ d_g_z @ p)
    return np.concatenate([dx, dp])


def trace_state_ks(
    params: MetricParams,
    state: RayState,
    config: TraceConfig | None = None,
    *,
    r_obs: float | None = None,
    inner_horizon_eps: float | None = None,
) -> KSRayDiagnostics:
    """Trace an explicitly initialized Kerr-Schild ray state.

    `TraceConfig.horizon_eps` remains the BL safety-margin convention. For this
    horizon-penetrating path it is interpreted as the default depth inside
    `r_+` before classifying a captured ray, unless `inner_horizon_eps` is
    provided explicitly.
    """

    cfg = config or TraceConfig()
    y0 = np.concatenate([state.x, state.p])
    observer_r = float(r_obs) if r_obs is not None else ks_radius(params, state.x[1:4])
    r_escape = cfg.r_escape if cfg.r_escape is not None else max(2.0 * observer_r, observer_r + 50.0)
    inner_eps = cfg.horizon_eps if inner_horizon_eps is None else inner_horizon_eps
    capture_r = max(1.0e-4, horizon_radius(params) - inner_eps)
    rhs_history = [y0.copy()]
    last_lam = 0.0

    def capture_event(_lam: float, y: np.ndarray) -> float:
        return ks_radius(params, y[1:4]) - capture_r

    capture_event.terminal = True  # type: ignore[attr-defined]
    capture_event.direction = -1.0  # type: ignore[attr-defined]

    def escape_event(_lam: float, y: np.ndarray) -> float:
        return ks_radius(params, y[1:4]) - r_escape

    escape_event.terminal = True  # type: ignore[attr-defined]
    escape_event.direction = 1.0  # type: ignore[attr-defined]

    def rhs(lam: float, y: np.ndarray) -> np.ndarray:
        nonlocal last_lam
        last_lam = float(lam)
        rhs_history.append(y.copy())
        return hamiltonian_rhs_ks(params, lam, y)

    try:
        sol = solve_ivp(
            rhs,
            (0.0, cfg.max_lambda),
            y0,
            method="DOP853",
            rtol=cfg.rtol,
            atol=cfg.atol,
            max_step=cfg.max_step,
            events=[capture_event, escape_event],
        )
    except Exception as exc:  # pragma: no cover - defensive path
        y_values = np.array(rhs_history[:-1] if len(rhs_history) > 1 else rhs_history, dtype=np.float64)
        return _diagnostics_ks(params, y_values, last_lam, "invalid", str(exc))

    event = "invalid"
    message = sol.message
    if sol.success:
        if sol.t_events[0].size:
            event = "capture"
        elif sol.t_events[1].size:
            event = "escape"
        else:
            message = "Kerr-Schild trace reached max_lambda without capture or escape."
    return _diagnostics_ks(params, sol.y.T, float(sol.t[-1]), event, message)


def bl_state_to_ks_state(params: MetricParams, state: RayState) -> RayState:
    """Transform a BL canonical state to ingoing Cartesian Kerr-Schild coordinates.

    The spatial part uses the ingoing azimuth `phi_ks = phi_bl + integral a/Delta dr`.
    Covectors are transformed with the inverse-transpose Jacobian so that
    `p_mu dx^mu` is preserved.
    """

    t_bl, r, theta, phi_bl = (float(value) for value in state.x)
    phi_ks = phi_bl + _phi_shift(params, r)
    xyz = bl_to_ks_cartesian(r, theta, phi_ks, params.a)
    x_ks = np.array([t_bl + _time_shift(params, r), xyz[0], xyz[1], xyz[2]], dtype=np.float64)
    jac = _bl_to_ks_jacobian(params, r, theta, phi_bl)
    p_ks = np.linalg.solve(jac.T, state.p)

    h_bl = abs(bl_hamiltonian(params, state.x, state.p))
    h_ks = abs(ks_hamiltonian(params, x_ks, p_ks))
    if h_bl < 1.0e-7 and h_ks > 1.0e-6:
        raise ValueError(f"BL->KS state transform did not preserve null Hamiltonian: H_KS={h_ks}")
    return RayState(x=x_ks, p=p_ks)


def _diagnostics_ks(
    params: MetricParams, y_values: np.ndarray, lambda_end: float, event: str, message: str
) -> KSRayDiagnostics:
    xs = y_values[:, :4]
    ps = y_values[:, 4:]
    h_values = np.array([ks_hamiltonian(params, x, p) for x, p in zip(xs, ps)], dtype=np.float64)
    e_values = -ps[:, 0]
    lz_values = xs[:, 1] * ps[:, 2] - xs[:, 2] * ps[:, 1]
    radii = np.array([ks_radius(params, x[1:4]) for x in xs], dtype=np.float64)
    return KSRayDiagnostics(
        event=event,
        h_max_abs=_nanmax_abs(h_values),
        e_drift_abs=float(np.max(e_values) - np.min(e_values)),
        lz_drift_abs=float(np.max(lz_values) - np.min(lz_values)),
        lambda_end=float(lambda_end),
        steps=int(y_values.shape[0]),
        min_r=float(np.min(radii)),
        final_r=float(radii[-1]),
        message=message,
    )


def _bl_to_ks_jacobian(params: MetricParams, r: float, theta: float, phi_bl: float) -> FloatArray:
    a = params.a
    dlt = delta(params, r)
    if abs(dlt) <= 1.0e-14:
        raise ValueError("BL->KS Jacobian is singular at the Boyer-Lindquist horizon.")
    psi = phi_bl + _phi_shift(params, r)
    sin_t = math.sin(theta)
    cos_t = math.cos(theta)
    sin_p = math.sin(psi)
    cos_p = math.cos(psi)
    dpsi_dr = a / dlt
    dt_dr = 2.0 * params.M * r / dlt

    dx_dr = sin_t * (cos_p + (-r * sin_p - a * cos_p) * dpsi_dr)
    dx_dtheta = (r * cos_p - a * sin_p) * cos_t
    dx_dphi = (-r * sin_p - a * cos_p) * sin_t

    dy_dr = sin_t * (sin_p + (r * cos_p - a * sin_p) * dpsi_dr)
    dy_dtheta = (r * sin_p + a * cos_p) * cos_t
    dy_dphi = (r * cos_p - a * sin_p) * sin_t

    dz_dr = cos_t
    dz_dtheta = -r * sin_t

    return np.array(
        [
            [1.0, dt_dr, 0.0, 0.0],
            [0.0, dx_dr, dx_dtheta, dx_dphi],
            [0.0, dy_dr, dy_dtheta, dy_dphi],
            [0.0, dz_dr, dz_dtheta, 0.0],
        ],
        dtype=np.float64,
    )


def _time_shift(params: MetricParams, r: float) -> float:
    rp = horizon_radius(params)
    rm = params.M - math.sqrt(params.M * params.M - params.a * params.a)
    gap = rp - rm
    return (2.0 * params.M / gap) * (rp * math.log(abs(r - rp)) - rm * math.log(abs(r - rm)))


def _phi_shift(params: MetricParams, r: float) -> float:
    if abs(params.a) <= 1.0e-14:
        return 0.0
    rp = horizon_radius(params)
    rm = params.M - math.sqrt(params.M * params.M - params.a * params.a)
    gap = rp - rm
    return params.a / gap * (math.log(abs(r - rp)) - math.log(abs(r - rm)))


def _nanmax_abs(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.max(np.abs(finite))) if finite.size else math.nan
