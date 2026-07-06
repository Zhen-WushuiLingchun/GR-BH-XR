"""CPU reference null-geodesic tracing."""

from __future__ import annotations

import math

import numpy as np
from scipy.integrate import solve_ivp

from .camera import initial_ray_state
from .metric import carter_constant, hamiltonian, horizon_radius, inverse_metric, inverse_metric_derivatives
from .sky import escape_direction_or_nan
from .types import CameraConfig, FailureReason, MetricParams, RayDiagnostics, TraceConfig


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
    failure_reason: FailureReason = "none",
    disk_crossing_lambda: np.ndarray | None = None,
    disk_crossing_states: np.ndarray | None = None,
) -> RayDiagnostics:
    xs = y_values[:, :4]
    ps = y_values[:, 4:]
    h_values = np.array(
        [_safe_scalar(lambda x=x, p=p: hamiltonian(params, x, p)) for x, p in zip(xs, ps)],
        dtype=np.float64,
    )
    q_values = np.array(
        [_safe_scalar(lambda x=x, p=p: carter_constant(params, x, p)) for x, p in zip(xs, ps)],
        dtype=np.float64,
    )
    e_values = -ps[:, 0]
    lz_values = ps[:, 3]
    delta_phi = float(xs[-1, 3] - xs[0, 3])
    azimuthal_winding = abs(delta_phi) / (2.0 * math.pi)
    image_order = max(0, int(math.floor(2.0 * azimuthal_winding + 1.0e-12)))
    crossing_lam_tuple: tuple[float, ...] = ()
    crossing_t_tuple: tuple[float, ...] = ()
    crossing_r_tuple: tuple[float, ...] = ()
    crossing_phi_tuple: tuple[float, ...] = ()
    crossing_p_t_tuple: tuple[float, ...] = ()
    crossing_p_phi_tuple: tuple[float, ...] = ()
    if (
        disk_crossing_lambda is not None
        and disk_crossing_states is not None
        and disk_crossing_lambda.size
        and disk_crossing_states.ndim == 2
    ):
        crossing_lam_tuple = tuple(float(value) for value in disk_crossing_lambda)
        crossing_t_tuple = tuple(float(value) for value in disk_crossing_states[:, 0])
        crossing_r_tuple = tuple(float(value) for value in disk_crossing_states[:, 1])
        crossing_phi_tuple = tuple(float(value) for value in disk_crossing_states[:, 3])
        crossing_p_t_tuple = tuple(float(value) for value in disk_crossing_states[:, 4])
        crossing_p_phi_tuple = tuple(float(value) for value in disk_crossing_states[:, 7])
    escape_theta, escape_phi, escape_dir_x, escape_dir_y, escape_dir_z = escape_direction_or_nan(
        params, event, xs[-1], ps[-1]
    )

    return RayDiagnostics(
        event=event,  # type: ignore[arg-type]
        h_max_abs=_nanmax_abs(h_values),
        e_drift_abs=float(np.max(e_values) - np.min(e_values)),
        lz_drift_abs=float(np.max(lz_values) - np.min(lz_values)),
        q_drift_abs=_nan_drift(q_values),
        lambda_end=float(lambda_end),
        steps=int(y_values.shape[0]),
        min_r=float(np.min(xs[:, 1])),
        disk_crossings=int(disk_crossings),
        azimuthal_winding=float(azimuthal_winding),
        image_order=int(image_order),
        q_initial=float(q_values[0]),
        q_final=float(q_values[-1]),
        disk_crossing_lambda=crossing_lam_tuple,
        disk_crossing_t=crossing_t_tuple,
        disk_crossing_r=crossing_r_tuple,
        disk_crossing_phi=crossing_phi_tuple,
        disk_crossing_p_t=crossing_p_t_tuple,
        disk_crossing_p_phi=crossing_p_phi_tuple,
        escape_theta=escape_theta,
        escape_phi=escape_phi,
        escape_dir_x=escape_dir_x,
        escape_dir_y=escape_dir_y,
        escape_dir_z=escape_dir_z,
        failure_reason=failure_reason,
        message=message,
    )


def _safe_scalar(func) -> float:
    try:
        return float(func())
    except Exception:
        return math.nan


def _nanmax_abs(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.max(np.abs(finite))) if finite.size else math.nan


def _nan_drift(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.max(finite) - np.min(finite)) if finite.size else math.nan


def trace_ray(
    params: MetricParams, camera: CameraConfig, config: TraceConfig | None = None
) -> RayDiagnostics:
    """Trace one inward screen ray until capture, escape, disk crossing, or failure."""

    cfg = config or TraceConfig()
    state = initial_ray_state(params, camera)
    y0 = np.concatenate([state.x, state.p])
    capture_r = horizon_radius(params) + cfg.horizon_eps
    r_escape = cfg.r_escape if cfg.r_escape is not None else max(2.0 * camera.r_obs, camera.r_obs + 50.0)
    rhs_history = [y0.copy()]
    last_lam = 0.0

    def capture_event(_lam: float, y: np.ndarray) -> float:
        return float(y[1] - capture_r)

    capture_event.terminal = True  # type: ignore[attr-defined]
    capture_event.direction = -1.0  # type: ignore[attr-defined]

    def escape_event(_lam: float, y: np.ndarray) -> float:
        return float(y[1] - r_escape)

    escape_event.terminal = True  # type: ignore[attr-defined]
    escape_event.direction = 1.0  # type: ignore[attr-defined]

    events = [capture_event, escape_event]
    axis_event_index: int | None = None

    def disk_event(lam: float, y: np.ndarray) -> float:
        if lam < 1.0e-6:
            return 1.0
        return float(y[2] - math.pi / 2.0)

    disk_event.terminal = bool(cfg.stop_on_disk)  # type: ignore[attr-defined]
    disk_event.direction = 0.0  # type: ignore[attr-defined]
    disk_event_index = len(events)
    events.append(disk_event)

    use_axis_event = abs(y0[7]) <= cfg.axis_lz_tol
    if use_axis_event:

        def axis_event(_lam: float, y: np.ndarray) -> float:
            return float(min(y[2], math.pi - y[2]) - cfg.axis_eps)

        axis_event.terminal = True  # type: ignore[attr-defined]
        axis_event.direction = -1.0  # type: ignore[attr-defined]
        axis_event_index = len(events)
        events.append(axis_event)

    def rhs(lam: float, y: np.ndarray) -> np.ndarray:
        nonlocal last_lam
        last_lam = float(lam)
        rhs_history.append(y.copy())
        return hamiltonian_rhs(params, lam, y)

    try:
        sol = solve_ivp(
            rhs,
            (0.0, cfg.max_lambda),
            y0,
            method="DOP853",
            rtol=cfg.rtol,
            atol=cfg.atol,
            max_step=cfg.max_step,
            events=events,
        )
    except Exception as exc:  # pragma: no cover - defensive failure path
        history = rhs_history[:-1] if len(rhs_history) > 1 else rhs_history
        y_values = np.array(history, dtype=np.float64)
        return _diagnostics(
            params,
            y_values,
            last_lam,
            "invalid",
            str(exc),
            _count_disk_crossings(y_values[:, 2]),
            "trace_exception",
        )

    y_values = sol.y.T
    disk_crossing_lambda = sol.t_events[disk_event_index]
    disk_crossing_states = sol.y_events[disk_event_index]
    disk_crossings = int(disk_crossing_lambda.size)
    event = "invalid"
    failure_reason: FailureReason = "none"
    message = sol.message
    if sol.success:
        if len(sol.t_events) > 0 and sol.t_events[0].size:
            event = "capture"
        elif len(sol.t_events) > 1 and sol.t_events[1].size:
            event = "escape"
        elif cfg.stop_on_disk and disk_crossing_lambda.size:
            event = "disk_crossing"
        elif axis_event_index is not None and sol.t_events[axis_event_index].size:
            failure_reason = "axis_coordinate_singularity"
            message = "Boyer-Lindquist axis coordinate singularity reached."
        else:
            failure_reason = "unclassified_max_lambda"
    else:
        failure_reason = "solver_failure"

    return _diagnostics(
        params,
        y_values,
        float(sol.t[-1]),
        event,
        message,
        disk_crossings,
        failure_reason,
        disk_crossing_lambda=disk_crossing_lambda,
        disk_crossing_states=disk_crossing_states,
    )
