"""Observer tetrads for finite-radius Kerr camera work.

The Stage B near-horizon path needs observer frames that remain meaningful
where the static tetrad fails.  This module starts with Boyer-Lindquist ZAMO /
LNRF frames in the exterior domain; Kerr-Schild worldline transport remains a
later Stage B task.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.integrate import solve_ivp

from .geodesic_ks import (
    bl_state_to_ks_state,
    bl_to_ks_jacobian,
    bl_to_ks_phi_shift,
    bl_to_ks_time_shift,
    hamiltonian_rhs_ks,
    ks_state_to_bl_state,
)
from .metric import covariant_metric, delta, horizon_radius, sigma
from .metric_ks import bl_to_ks_cartesian, ks_inverse_metric, ks_metric, ks_radius
from .types import FloatArray, MetricParams, RayState


@dataclass(frozen=True)
class BLObserverTetrad:
    """Contravariant orthonormal tetrad in Boyer-Lindquist coordinates."""

    x: FloatArray
    e_time: FloatArray
    e_r: FloatArray
    e_theta: FloatArray
    e_phi: FloatArray
    kind: str

    def vectors(self) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
        return self.e_time, self.e_r, self.e_theta, self.e_phi


@dataclass(frozen=True)
class KSObserverTetrad:
    """Contravariant orthonormal tetrad in Cartesian Kerr-Schild coordinates."""

    x: FloatArray
    e_time: FloatArray
    e_r: FloatArray
    e_theta: FloatArray
    e_phi: FloatArray
    kind: str

    def vectors(self) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
        return self.e_time, self.e_r, self.e_theta, self.e_phi


@dataclass(frozen=True)
class KSTransportedTetradPath:
    """A transported KS observer tetrad sampled along a timelike worldline."""

    tau: FloatArray
    states: FloatArray
    frames: FloatArray
    kind: str

    def tetrad_at(self, index: int) -> KSObserverTetrad:
        frame = self.frames[index]
        return KSObserverTetrad(
            x=self.states[index, :4].copy(),
            e_time=frame[0].copy(),
            e_r=frame[1].copy(),
            e_theta=frame[2].copy(),
            e_phi=frame[3].copy(),
            kind=self.kind,
        )


def frame_inner_product(params: MetricParams, x: FloatArray, u: FloatArray, v: FloatArray) -> float:
    """Return `g_mu nu u^mu v^nu` for BL-coordinate contravariant vectors."""

    r = float(x[1])
    theta = float(x[2])
    g = covariant_metric(params, r, theta)
    return float(np.asarray(u, dtype=np.float64) @ g @ np.asarray(v, dtype=np.float64))


def ks_frame_inner_product(params: MetricParams, x: FloatArray, u: FloatArray, v: FloatArray) -> float:
    """Return `g_mu nu u^mu v^nu` for KS-coordinate contravariant vectors."""

    g = ks_metric(params, np.asarray(x, dtype=np.float64)[1:4])
    return float(np.asarray(u, dtype=np.float64) @ g @ np.asarray(v, dtype=np.float64))


def gram_matrix(params: MetricParams, tetrad: BLObserverTetrad) -> FloatArray:
    """Return the tetrad Gram matrix, expected to be diag(-1, 1, 1, 1)."""

    vectors = tetrad.vectors()
    return np.array(
        [[frame_inner_product(params, tetrad.x, left, right) for right in vectors] for left in vectors],
        dtype=np.float64,
    )


def ks_gram_matrix(params: MetricParams, tetrad: KSObserverTetrad) -> FloatArray:
    """Return the KS tetrad Gram matrix, expected to be diag(-1, 1, 1, 1)."""

    vectors = tetrad.vectors()
    return np.array(
        [[ks_frame_inner_product(params, tetrad.x, left, right) for right in vectors] for left in vectors],
        dtype=np.float64,
    )


def transported_gram_matrices(params: MetricParams, path: KSTransportedTetradPath) -> FloatArray:
    """Return tetrad Gram matrices for every sampled point in a transported path."""

    matrices = []
    for idx in range(path.states.shape[0]):
        matrices.append(ks_gram_matrix(params, path.tetrad_at(idx)))
    return np.asarray(matrices, dtype=np.float64)


def zamo_angular_velocity(params: MetricParams, r: float, theta: float) -> float:
    """Return the ZAMO / LNRF frame-dragging angular velocity `omega`.

    This is `omega = -g_tphi / g_phiphi`, equal to `2 M a r / A` in the usual
    Kerr notation of Bardeen, Press & Teukolsky.
    """

    g = covariant_metric(params, r, theta)
    g_phiphi = float(g[3, 3])
    if g_phiphi <= 0.0 or not math.isfinite(g_phiphi):
        raise ValueError("ZAMO angular velocity requires spacelike phi coordinate.")
    return -float(g[0, 3]) / g_phiphi


def zamo_lapse(params: MetricParams, r: float, theta: float) -> float:
    """Return the BL ZAMO lapse `alpha = sqrt(Sigma Delta / A)`."""

    dlt = delta(params, r)
    if dlt <= 0.0:
        raise ValueError("ZAMO lapse is defined only outside the outer horizon.")
    g = covariant_metric(params, r, theta)
    g_tt = float(g[0, 0])
    g_tphi = float(g[0, 3])
    g_phiphi = float(g[3, 3])
    value = (g_tphi * g_tphi - g_tt * g_phiphi) / g_phiphi
    if value <= 0.0 or not math.isfinite(value):
        raise ValueError("ZAMO lapse normalization is not timelike.")
    return math.sqrt(value)


def zamo_tetrad(params: MetricParams, *, r: float, theta: float, phi: float = 0.0) -> BLObserverTetrad:
    """Return an exterior Boyer-Lindquist ZAMO / LNRF orthonormal tetrad."""

    if r <= horizon_radius(params):
        raise ValueError("ZAMO tetrad is exterior-only in Boyer-Lindquist coordinates.")
    g = covariant_metric(params, r, theta)
    g_rr = float(g[1, 1])
    g_thetatheta = float(g[2, 2])
    g_phiphi = float(g[3, 3])
    if min(g_rr, g_thetatheta, g_phiphi) <= 0.0:
        raise ValueError("ZAMO spatial tetrad normalization is not spacelike.")

    omega = zamo_angular_velocity(params, r, theta)
    lapse = zamo_lapse(params, r, theta)
    e_time = np.array([1.0 / lapse, 0.0, 0.0, omega / lapse], dtype=np.float64)
    e_r = np.array([0.0, 1.0 / math.sqrt(g_rr), 0.0, 0.0], dtype=np.float64)
    e_theta = np.array([0.0, 0.0, 1.0 / math.sqrt(g_thetatheta), 0.0], dtype=np.float64)
    e_phi = np.array([0.0, 0.0, 0.0, 1.0 / math.sqrt(g_phiphi)], dtype=np.float64)
    return BLObserverTetrad(
        x=np.array([0.0, r, theta, phi], dtype=np.float64),
        e_time=e_time,
        e_r=e_r,
        e_theta=e_theta,
        e_phi=e_phi,
        kind="zamo",
    )


def static_observer_tetrad(
    params: MetricParams, *, r: float, theta: float, phi: float = 0.0
) -> BLObserverTetrad:
    """Return a static-observer tetrad where `partial_t` is timelike."""

    g = covariant_metric(params, r, theta)
    g_tt = float(g[0, 0])
    g_tphi = float(g[0, 3])
    g_rr = float(g[1, 1])
    g_thetatheta = float(g[2, 2])
    g_phiphi = float(g[3, 3])
    if g_tt >= 0.0:
        raise ValueError("Static observer tetrad is unavailable inside the ergoregion.")
    if min(g_rr, g_thetatheta) <= 0.0:
        raise ValueError("Static observer spatial tetrad is exterior-only in BL coordinates.")

    e_time = np.array([1.0 / math.sqrt(-g_tt), 0.0, 0.0, 0.0], dtype=np.float64)
    e_r = np.array([0.0, 1.0 / math.sqrt(g_rr), 0.0, 0.0], dtype=np.float64)
    e_theta = np.array([0.0, 0.0, 1.0 / math.sqrt(g_thetatheta), 0.0], dtype=np.float64)
    phi_norm_sq = g_phiphi - g_tphi * g_tphi / g_tt
    if phi_norm_sq <= 0.0:
        raise ValueError("Static observer phi tetrad normalization is not spacelike.")
    e_phi_phi = 1.0 / math.sqrt(phi_norm_sq)
    e_phi_t = (-g_tphi / g_tt) * e_phi_phi
    e_phi = np.array([e_phi_t, 0.0, 0.0, e_phi_phi], dtype=np.float64)
    return BLObserverTetrad(
        x=np.array([0.0, r, theta, phi], dtype=np.float64),
        e_time=e_time,
        e_r=e_r,
        e_theta=e_theta,
        e_phi=e_phi,
        kind="static",
    )


def push_bl_tetrad_to_ks(params: MetricParams, tetrad: BLObserverTetrad) -> KSObserverTetrad:
    """Push an exterior BL tetrad into ingoing Cartesian Kerr-Schild coordinates.

    This is a chart transform for existing exterior observer frames, not a
    transported near-horizon worldline frame. It is used as the first Stage B-2
    bridge so the already validated ZAMO/LNRF basis can initialize future
    Kerr-Schild rays without changing its physical observer definition.
    """

    r = float(tetrad.x[1])
    theta = float(tetrad.x[2])
    phi_bl = float(tetrad.x[3])
    jac = bl_to_ks_jacobian(params, r, theta, phi_bl)
    xyz = bl_to_ks_cartesian(r, theta, phi_bl + bl_to_ks_phi_shift(params, r), params.a)
    x_ks = np.array([float(tetrad.x[0]) + bl_to_ks_time_shift(params, r), *xyz], dtype=np.float64)
    return KSObserverTetrad(
        x=x_ks,
        e_time=jac @ tetrad.e_time,
        e_r=jac @ tetrad.e_r,
        e_theta=jac @ tetrad.e_theta,
        e_phi=jac @ tetrad.e_phi,
        kind=f"{tetrad.kind}_pushed_to_ks",
    )


def schwarzschild_radial_freefall_initial_state(
    params: MetricParams, *, r: float, theta: float, phi: float = 0.0
) -> RayState:
    """Return a Schwarzschild radial infall state from rest at infinity.

    The canonical BL covector uses `E = -p_t = 1`, `L_z = 0`, and
    `u^r = -sqrt(2M/r)`.  It is then transformed to ingoing Cartesian
    Kerr-Schild coordinates for horizon-regular integration.
    """

    if abs(params.a) > 1.0e-14:
        raise ValueError("This analytic free-fall seed is Schwarzschild-only.")
    if r <= 2.0 * params.M:
        raise ValueError("Initial BL free-fall seed must start outside the Schwarzschild horizon.")
    f = 1.0 - 2.0 * params.M / r
    u_r_contra = -math.sqrt(2.0 * params.M / r)
    p_bl = np.array([-1.0, u_r_contra / f, 0.0, 0.0], dtype=np.float64)
    x_bl = np.array([0.0, r, theta, phi], dtype=np.float64)
    return bl_state_to_ks_state(params, RayState(x=x_bl, p=p_bl))


def schwarzschild_radial_freefall_initial_tetrad(
    params: MetricParams, *, r: float, theta: float, phi: float = 0.0
) -> KSObserverTetrad:
    """Return the analytic static-frame boost tetrad for radial infall.

    In Schwarzschild, an observer dropped from rest at infinity has local
    velocity `v = -sqrt(2M/r)` relative to the static tetrad.  A radial Lorentz
    boost of the static tetrad gives `e_time = u_ff`, and the pushed KS frame is
    the starting frame for numerical parallel transport.
    """

    if abs(params.a) > 1.0e-14:
        raise ValueError("This analytic free-fall tetrad seed is Schwarzschild-only.")
    static = static_observer_tetrad(params, r=r, theta=theta, phi=phi)
    velocity = -math.sqrt(2.0 * params.M / r)
    gamma = 1.0 / math.sqrt(1.0 - velocity * velocity)
    e_time = gamma * (static.e_time + velocity * static.e_r)
    e_r = gamma * (velocity * static.e_time + static.e_r)
    boosted = BLObserverTetrad(
        x=static.x,
        e_time=e_time,
        e_r=e_r,
        e_theta=static.e_theta,
        e_phi=static.e_phi,
        kind="schwarzschild_radial_freefall",
    )
    return push_bl_tetrad_to_ks(params, boosted)


def transport_schwarzschild_radial_freefall_tetrad(
    params: MetricParams,
    *,
    r_start: float,
    theta: float = math.pi / 2.0,
    phi: float = 0.0,
    r_stop: float | None = None,
    tau_max: float = 30.0,
    max_step: float = 0.05,
    rtol: float = 1.0e-9,
    atol: float = 1.0e-11,
) -> KSTransportedTetradPath:
    """Integrate a Schwarzschild infall worldline and parallel-transport frame.

    This is the first Stage B-2 worldline-tetrad gate. It deliberately starts
    with the Schwarzschild radial free-fall case because both the observer
    velocity and tetrad boost have compact analytic forms.
    """

    state = schwarzschild_radial_freefall_initial_state(params, r=r_start, theta=theta, phi=phi)
    tetrad = schwarzschild_radial_freefall_initial_tetrad(params, r=r_start, theta=theta, phi=phi)
    y0 = np.concatenate([state.x, state.p, np.stack(tetrad.vectors()).reshape(-1)])
    stop_radius = float(r_stop) if r_stop is not None else horizon_radius(params) + 0.05 * params.M

    def rhs(tau: float, y: np.ndarray) -> np.ndarray:
        del tau
        state_rhs = hamiltonian_rhs_ks(params, 0.0, y[:8])
        x = y[:4]
        p = y[4:8]
        u = ks_inverse_metric(params, x[1:4]) @ p
        gamma = _ks_christoffel_finite_difference(params, x[1:4])
        frame = y[8:].reshape((4, 4))
        frame_rhs = np.zeros_like(frame)
        for vec_index in range(4):
            vec = frame[vec_index]
            frame_rhs[vec_index] = -np.einsum("mnr,n,r->m", gamma, u, vec)
        return np.concatenate([state_rhs, frame_rhs.reshape(-1)])

    def stop_event(_tau: float, y: np.ndarray) -> float:
        return ks_radius(params, y[1:4]) - stop_radius

    stop_event.terminal = True  # type: ignore[attr-defined]
    stop_event.direction = -1.0  # type: ignore[attr-defined]

    sol = solve_ivp(
        rhs,
        (0.0, tau_max),
        y0,
        method="DOP853",
        rtol=rtol,
        atol=atol,
        max_step=max_step,
        events=[stop_event],
    )
    if not sol.success and not sol.t_events[0].size:
        raise RuntimeError(f"Transported tetrad integration failed: {sol.message}")
    values = sol.y.T
    return KSTransportedTetradPath(
        tau=sol.t.copy(),
        states=values[:, :8].copy(),
        frames=values[:, 8:].reshape((-1, 4, 4)).copy(),
        kind="schwarzschild_radial_freefall_parallel_transport",
    )


def _ks_christoffel_finite_difference(params: MetricParams, xyz: FloatArray) -> FloatArray:
    """Return KS Christoffel symbols from finite-difference metric derivatives."""

    xyz = np.asarray(xyz, dtype=np.float64)
    g_inv = ks_inverse_metric(params, xyz)
    dg = np.zeros((4, 4, 4), dtype=np.float64)
    for axis in range(3):
        step = max(1.0e-5, 1.0e-5 * abs(float(xyz[axis])))
        delta_xyz = np.zeros(3, dtype=np.float64)
        delta_xyz[axis] = step
        dg[axis + 1] = (ks_metric(params, xyz + delta_xyz) - ks_metric(params, xyz - delta_xyz)) / (
            2.0 * step
        )
    gamma = np.zeros((4, 4, 4), dtype=np.float64)
    for mu in range(4):
        for nu in range(4):
            for rho in range(4):
                gamma[mu, nu, rho] = 0.5 * float(
                    np.sum(g_inv[mu, :] * (dg[nu, :, rho] + dg[rho, :, nu] - dg[:, nu, rho]))
                )
    return gamma


def analytic_kerr_frame_dragging_omega(params: MetricParams, r: float, theta: float) -> float:
    """Return `2 M a r / A`, used as an independent ZAMO omega check."""

    s = math.sin(theta)
    a = params.a
    dlt = delta(params, r)
    a_term = (r * r + a * a) ** 2 - a * a * dlt * s * s
    return 2.0 * params.M * a * r / a_term


def analytic_zamo_lapse(params: MetricParams, r: float, theta: float) -> float:
    """Return `sqrt(Sigma Delta / A)`, used as an independent lapse check."""

    s = math.sin(theta)
    a = params.a
    dlt = delta(params, r)
    a_term = (r * r + a * a) ** 2 - a * a * dlt * s * s
    return math.sqrt(sigma(params, r, theta) * dlt / a_term)
