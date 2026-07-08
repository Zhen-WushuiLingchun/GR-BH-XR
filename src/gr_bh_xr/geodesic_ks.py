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

from .metric import carter_constant, delta, hamiltonian as bl_hamiltonian, horizon_radius
from .metric_ks import (
    bl_to_ks_cartesian,
    ks_cartesian_to_bl,
    ks_hamiltonian,
    ks_inverse_metric,
    ks_inverse_metric_derivatives,
    ks_metric,
    ks_radius,
)
from .types import FloatArray, MetricParams, RayState, TraceConfig


@dataclass(frozen=True)
class KSSphereTarget:
    """Finite-distance spherical target in Cartesian Kerr-Schild coordinates."""

    center_xyz: FloatArray
    radius: float

    def __post_init__(self) -> None:
        center = np.asarray(self.center_xyz, dtype=np.float64)
        if center.shape != (3,):
            raise ValueError("center_xyz must be a 3-vector.")
        if self.radius <= 0.0:
            raise ValueError("sphere target radius must be positive.")
        object.__setattr__(self, "center_xyz", center)


@dataclass(frozen=True)
class KSRayDiagnostics:
    """Minimal diagnostics for the Stage A Kerr-Schild tracer."""

    event: str
    h_max_abs: float
    e_drift_abs: float
    lz_drift_abs: float
    q_drift_abs: float
    q_sample_count: int
    q_skipped_count: int
    lambda_end: float
    steps: int
    min_r: float
    final_r: float
    final_x: FloatArray
    final_p: FloatArray
    disk_crossings: int = 0
    disk_crossing_lambda: tuple[float, ...] = ()
    disk_crossing_order: tuple[int, ...] = ()
    disk_crossing_t: tuple[float, ...] = ()
    disk_crossing_r: tuple[float, ...] = ()
    disk_crossing_phi: tuple[float, ...] = ()
    disk_crossing_p_t: tuple[float, ...] = ()
    disk_crossing_p_phi: tuple[float, ...] = ()
    object_hit_lambda: float = math.nan
    object_hit_t: float = math.nan
    object_hit_x: float = math.nan
    object_hit_y: float = math.nan
    object_hit_z: float = math.nan
    object_hit_p_t: float = math.nan
    object_hit_redshift_g: float = math.nan
    message: str = ""


KS_DISK_EVENT_GUARD_LAMBDA = 1.0e-6
KS_DISK_COPLANAR_TOL = 1.0e-12


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
    sphere_target: KSSphereTarget | None = None,
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
    capture_r = _inner_capture_radius(params, inner_eps)
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

    events = [capture_event, escape_event]
    disk_event_index: int | None = None
    sphere_event_index: int | None = None
    initial_z = float(y0[3])
    initial_dx = ks_inverse_metric(params, y0[1:4]) @ y0[4:]
    initial_dz = float(initial_dx[3])
    is_coplanar_ray = (
        abs(initial_z) <= KS_DISK_COPLANAR_TOL
        and abs(initial_dz) <= KS_DISK_COPLANAR_TOL
    )
    if not is_coplanar_ray:
        guard_source = initial_z
        if abs(guard_source) <= KS_DISK_COPLANAR_TOL:
            guard_source = initial_dz
        guard_value = math.copysign(1.0, guard_source)

        def disk_event(lam: float, y: np.ndarray) -> float:
            if lam < KS_DISK_EVENT_GUARD_LAMBDA:
                return guard_value
            return float(y[3])

        disk_event.terminal = bool(cfg.stop_on_disk)  # type: ignore[attr-defined]
        disk_event.direction = 0.0  # type: ignore[attr-defined]
        disk_event_index = len(events)
        events.append(disk_event)

    if sphere_target is not None:
        center = np.asarray(sphere_target.center_xyz, dtype=np.float64)
        radius = float(sphere_target.radius)

        def sphere_event(_lam: float, y: np.ndarray) -> float:
            return float(np.linalg.norm(y[1:4] - center) - radius)

        sphere_event.terminal = True  # type: ignore[attr-defined]
        sphere_event.direction = -1.0  # type: ignore[attr-defined]
        sphere_event_index = len(events)
        events.append(sphere_event)

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
            events=events,
        )
    except Exception as exc:  # pragma: no cover - defensive path
        y_values = np.array(rhs_history[:-1] if len(rhs_history) > 1 else rhs_history, dtype=np.float64)
        return _diagnostics_ks(params, y_values, last_lam, "invalid", str(exc))

    if disk_event_index is None:
        disk_crossing_lambda = np.array([], dtype=np.float64)
        disk_crossing_states = np.empty((0, y0.size), dtype=np.float64)
    else:
        disk_crossing_lambda = sol.t_events[disk_event_index]
        disk_crossing_states = sol.y_events[disk_event_index]
    if sphere_event_index is None:
        sphere_hit_lambda = np.array([], dtype=np.float64)
        sphere_hit_states = np.empty((0, y0.size), dtype=np.float64)
    else:
        sphere_hit_lambda = sol.t_events[sphere_event_index]
        sphere_hit_states = sol.y_events[sphere_event_index]

    event = "invalid"
    message = sol.message
    if sol.success:
        if sol.t_events[0].size:
            event = "capture"
        elif sol.t_events[1].size:
            event = "escape"
        elif sphere_hit_lambda.size:
            event = "object_hit"
        elif cfg.stop_on_disk and disk_crossing_lambda.size:
            event = "disk_crossing"
        else:
            message = "Kerr-Schild trace reached max_lambda without capture or escape."
    return _diagnostics_ks(
        params,
        sol.y.T,
        float(sol.t[-1]),
        event,
        message,
        disk_crossing_lambda=disk_crossing_lambda,
        disk_crossing_states=disk_crossing_states,
        object_hit_lambda=sphere_hit_lambda,
        object_hit_states=sphere_hit_states,
    )


def static_observer_redshift_ks(params: MetricParams, xyz: FloatArray, p_t: float) -> float:
    """Return `g = E / (-p_mu u_static^mu)` for a static emitter/observer.

    The static worldline is only timelike where `g_tt < 0`.  Inside the
    ergoregion the helper returns NaN so callers cannot accidentally treat an
    impossible static object as a physical emitter.
    """

    cov = ks_metric(params, xyz)
    g_tt = float(cov[0, 0])
    if g_tt >= 0.0:
        return math.nan
    u_t = 1.0 / math.sqrt(-g_tt)
    energy = -float(p_t)
    denom = energy * u_t
    if denom <= 0.0:
        return math.nan
    return energy / denom


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


def ks_state_to_bl_state(params: MetricParams, state: RayState) -> RayState:
    """Transform an ingoing Cartesian Kerr-Schild canonical state to BL coordinates.

    This inverse is intended for exterior validation and escape-direction
    diagnostics. Near the BL horizon the coordinate transform is logarithmically
    singular; horizon-crossing claims must use the native Kerr-Schild state.
    """

    t_ks = float(state.x[0])
    r, theta, phi_ks = ks_cartesian_to_bl(state.x[1:4], params.a)
    phi_bl = phi_ks - _phi_shift(params, r)
    x_bl = np.array([t_ks - _time_shift(params, r), r, theta, phi_bl], dtype=np.float64)
    jac = _bl_to_ks_jacobian(params, r, theta, phi_bl)
    p_bl = jac.T @ state.p
    return RayState(x=x_bl, p=p_bl)


def _diagnostics_ks(
    params: MetricParams,
    y_values: np.ndarray,
    lambda_end: float,
    event: str,
    message: str,
    disk_crossing_lambda: np.ndarray | None = None,
    disk_crossing_states: np.ndarray | None = None,
    object_hit_lambda: np.ndarray | None = None,
    object_hit_states: np.ndarray | None = None,
) -> KSRayDiagnostics:
    xs = y_values[:, :4]
    ps = y_values[:, 4:]
    h_values = np.array([ks_hamiltonian(params, x, p) for x, p in zip(xs, ps)], dtype=np.float64)
    e_values = -ps[:, 0]
    lz_values = xs[:, 1] * ps[:, 2] - xs[:, 2] * ps[:, 1]
    radii = np.array([ks_radius(params, x[1:4]) for x in xs], dtype=np.float64)
    q_values = np.array([_safe_ks_carter_constant(params, x, p) for x, p in zip(xs, ps)], dtype=np.float64)
    q_sample_count = int(np.count_nonzero(np.isfinite(q_values)))
    crossing_lam_tuple: tuple[float, ...] = ()
    crossing_order_tuple: tuple[int, ...] = ()
    crossing_t_tuple: tuple[float, ...] = ()
    crossing_r_tuple: tuple[float, ...] = ()
    crossing_phi_tuple: tuple[float, ...] = ()
    crossing_p_t_tuple: tuple[float, ...] = ()
    crossing_p_phi_tuple: tuple[float, ...] = ()
    object_lambda = math.nan
    object_t = math.nan
    object_x = math.nan
    object_y = math.nan
    object_z = math.nan
    object_p_t = math.nan
    object_g = math.nan
    if (
        disk_crossing_lambda is not None
        and disk_crossing_states is not None
        and disk_crossing_lambda.size
        and disk_crossing_states.ndim == 2
    ):
        crossing_lam_tuple = tuple(float(value) for value in disk_crossing_lambda)
        crossing_order_tuple = tuple(range(len(crossing_lam_tuple)))
        converted = [_safe_ks_crossing_to_bl(params, row[:4], row[4:]) for row in disk_crossing_states]
        crossing_t_tuple = tuple(value[0] for value in converted)
        crossing_r_tuple = tuple(value[1] for value in converted)
        crossing_phi_tuple = tuple(value[3] for value in converted)
        crossing_p_t_tuple = tuple(value[4] for value in converted)
        crossing_p_phi_tuple = tuple(value[7] for value in converted)
    if (
        object_hit_lambda is not None
        and object_hit_states is not None
        and object_hit_lambda.size
        and object_hit_states.ndim == 2
    ):
        row = object_hit_states[0]
        object_lambda = float(object_hit_lambda[0])
        object_t = float(row[0])
        object_x = float(row[1])
        object_y = float(row[2])
        object_z = float(row[3])
        object_p_t = float(row[4])
        object_g = static_observer_redshift_ks(params, row[1:4], object_p_t)
    return KSRayDiagnostics(
        event=event,
        h_max_abs=_nanmax_abs(h_values),
        e_drift_abs=float(np.max(e_values) - np.min(e_values)),
        lz_drift_abs=float(np.max(lz_values) - np.min(lz_values)),
        q_drift_abs=_nan_drift(q_values),
        q_sample_count=q_sample_count,
        q_skipped_count=int(q_values.size - q_sample_count),
        lambda_end=float(lambda_end),
        steps=int(y_values.shape[0]),
        min_r=float(np.min(radii)),
        final_r=float(radii[-1]),
        final_x=xs[-1].copy(),
        final_p=ps[-1].copy(),
        disk_crossings=len(crossing_lam_tuple),
        disk_crossing_lambda=crossing_lam_tuple,
        disk_crossing_order=crossing_order_tuple,
        disk_crossing_t=crossing_t_tuple,
        disk_crossing_r=crossing_r_tuple,
        disk_crossing_phi=crossing_phi_tuple,
        disk_crossing_p_t=crossing_p_t_tuple,
        disk_crossing_p_phi=crossing_p_phi_tuple,
        object_hit_lambda=object_lambda,
        object_hit_t=object_t,
        object_hit_x=object_x,
        object_hit_y=object_y,
        object_hit_z=object_z,
        object_hit_p_t=object_p_t,
        object_hit_redshift_g=object_g,
        message=message,
    )


def _safe_ks_carter_constant(params: MetricParams, x_ks: np.ndarray, p_ks: np.ndarray) -> float:
    try:
        radius = ks_radius(params, x_ks[1:4])
        if radius <= horizon_radius(params) + 1.0e-5 * params.M:
            return math.nan
        bl_state = ks_state_to_bl_state(params, RayState(x=np.array(x_ks), p=np.array(p_ks)))
        theta = float(bl_state.x[2])
        if math.sin(theta) ** 2 <= 1.0e-10:
            return math.nan
        return carter_constant(params, bl_state.x, bl_state.p)
    except Exception:
        return math.nan


def _safe_ks_crossing_to_bl(params: MetricParams, x_ks: np.ndarray, p_ks: np.ndarray) -> tuple[float, ...]:
    try:
        state = ks_state_to_bl_state(params, RayState(x=np.array(x_ks), p=np.array(p_ks)))
    except Exception:
        return (math.nan, math.nan, math.nan, math.nan, math.nan, math.nan, math.nan, math.nan)
    return (
        float(state.x[0]),
        float(state.x[1]),
        float(state.x[2]),
        float(state.x[3]),
        float(state.p[0]),
        float(state.p[1]),
        float(state.p[2]),
        float(state.p[3]),
    )


def _inner_capture_radius(params: MetricParams, inner_eps: float) -> float:
    rp = horizon_radius(params)
    rm = params.M - math.sqrt(params.M * params.M - params.a * params.a)
    gap = rp - rm
    margin = min(0.05 * params.M, 0.25 * gap)
    return max(1.0e-4, rm + margin, rp - inner_eps)


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


def _nan_drift(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.max(finite) - np.min(finite)) if finite.size else math.nan
