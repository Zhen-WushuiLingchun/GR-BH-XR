"""CPU reference null-geodesic tracing."""

from __future__ import annotations

import math

import numpy as np
from scipy.integrate import solve_ivp

from .camera import initial_ray_state
from .metric import carter_constant, hamiltonian, horizon_radius, inverse_metric, inverse_metric_derivatives
from .types import CameraConfig, MetricParams, RayDiagnostics, TraceConfig


def hamiltonian_rhs(params: MetricParams, _lam: float, y: np.ndarray) -> np.ndarray:
    """Hamiltonian equations for canonical state `(x^mu, p_mu)`."""

    x = y[:4]
    p = y[4:]
    r = float(x[1])
    theta = float(x[2])

    g_inv = inverse_metric(params, r, theta)
    dx = g_inv @ p

    d_g_r, d_g_theta = inverse_metric_derivatives(params, r, theta)
    dp = np.zeros(4, dtype=np.float64)
    dp[1] = -0.5 * float(p @ d_g_r @ p)
    dp[2] = -0.5 * float(p @ d_g_theta @ p)
    return np.concatenate([dx, dp])


def _count_disk_crossings(theta_values: np.ndarray) -> int:
    centered = theta_values - math.pi / 2.0
    crossings = 0
    last = centered[0]
    for value in centered[1:]:
        if abs(last) < 1.0e-8:
            last = value
            continue
        if abs(value) < 1.0e-8 or last * value < 0.0:
            crossings += 1
        last = value
    return crossings


def _diagnostics(
    params: MetricParams,
    y_values: np.ndarray,
    lambda_end: float,
    event: str,
    message: str,
    disk_crossings: int,
) -> RayDiagnostics:
    xs = y_values[:, :4]
    ps = y_values[:, 4:]
    h_values = np.array([hamiltonian(params, x, p) for x, p in zip(xs, ps)], dtype=np.float64)
    q_values = np.array([carter_constant(params, x, p) for x, p in zip(xs, ps)], dtype=np.float64)
    e_values = -ps[:, 0]
    lz_values = ps[:, 3]

    return RayDiagnostics(
        event=event,  # type: ignore[arg-type]
        h_max_abs=float(np.max(np.abs(h_values))),
        e_drift_abs=float(np.max(e_values) - np.min(e_values)),
        lz_drift_abs=float(np.max(lz_values) - np.min(lz_values)),
        q_drift_abs=float(np.max(q_values) - np.min(q_values)),
        lambda_end=float(lambda_end),
        steps=int(y_values.shape[0]),
        min_r=float(np.min(xs[:, 1])),
        disk_crossings=int(disk_crossings),
        q_initial=float(q_values[0]),
        q_final=float(q_values[-1]),
        message=message,
    )


def trace_ray(
    params: MetricParams, camera: CameraConfig, config: TraceConfig | None = None
) -> RayDiagnostics:
    """Trace one inward screen ray until capture, escape, disk crossing, or failure."""

    cfg = config or TraceConfig()
    state = initial_ray_state(params, camera)
    y0 = np.concatenate([state.x, state.p])
    capture_r = horizon_radius(params) + cfg.horizon_eps
    r_escape = cfg.r_escape if cfg.r_escape is not None else max(2.0 * camera.r_obs, camera.r_obs + 50.0)

    def capture_event(_lam: float, y: np.ndarray) -> float:
        return float(y[1] - capture_r)

    capture_event.terminal = True  # type: ignore[attr-defined]
    capture_event.direction = -1.0  # type: ignore[attr-defined]

    def escape_event(_lam: float, y: np.ndarray) -> float:
        return float(y[1] - r_escape)

    escape_event.terminal = True  # type: ignore[attr-defined]
    escape_event.direction = 1.0  # type: ignore[attr-defined]

    events = [capture_event, escape_event]
    if cfg.stop_on_disk:

        def disk_event(lam: float, y: np.ndarray) -> float:
            if lam < 1.0e-6:
                return 1.0
            return float(y[2] - math.pi / 2.0)

        disk_event.terminal = True  # type: ignore[attr-defined]
        disk_event.direction = 0.0  # type: ignore[attr-defined]
        events.append(disk_event)

    try:
        sol = solve_ivp(
            lambda lam, y: hamiltonian_rhs(params, lam, y),
            (0.0, cfg.max_lambda),
            y0,
            method="DOP853",
            rtol=cfg.rtol,
            atol=cfg.atol,
            max_step=cfg.max_step,
            events=events,
        )
    except Exception as exc:  # pragma: no cover - defensive failure path
        y_values = np.array([y0], dtype=np.float64)
        return _diagnostics(params, y_values, 0.0, "invalid", str(exc), 0)

    y_values = sol.y.T
    disk_crossings = _count_disk_crossings(y_values[:, 2])
    event = "invalid"
    if sol.success:
        if len(sol.t_events) > 0 and sol.t_events[0].size:
            event = "capture"
        elif len(sol.t_events) > 1 and sol.t_events[1].size:
            event = "escape"
        elif len(sol.t_events) > 2 and sol.t_events[2].size:
            event = "disk_crossing"

    return _diagnostics(
        params,
        y_values,
        float(sol.t[-1]),
        event,
        sol.message,
        disk_crossings,
    )
