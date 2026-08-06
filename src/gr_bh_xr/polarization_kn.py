"""Minimal f64 polarization-transport oracle for the native NPGS runtime.

NPGS remains the production renderer.  This module integrates the parallel-
transport equation from Li et al. 2026 Eq. (2.5) alongside one audited photon
ray so the native Walker-Penrose shortcut is not used to validate itself.
Coordinates are ingoing Cartesian Kerr-Schild ``(t,x,y,z)`` with spin along
``+z``, signature ``(-,+,+,+)``, and geometric units ``G=c=1``.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.integrate import solve_ivp

from .geodesic_kn import hamiltonian_rhs_kn
from .metric_kn import (
    KerrNewmanParams,
    bl_to_ks_jacobian,
    horizon_radius,
    ks_hamiltonian,
    ks_inverse_metric,
    ks_metric,
    ks_metric_derivatives,
    ks_radius,
)
from .types import FloatArray, RayState, TraceConfig


@dataclass(frozen=True)
class PolarizationTransportDiagnostics:
    event: str
    h_max_abs: float
    norm_drift_abs: FloatArray
    transverse_max_abs: FloatArray
    wp_drift_abs: FloatArray
    wp_relative_drift: FloatArray
    shortcut_drift_abs: FloatArray
    shortcut_relative_drift: FloatArray
    lambda_end: float
    steps: int
    final_x: FloatArray
    final_p_cov: FloatArray
    final_f_up: FloatArray
    message: str = ""


def christoffel_symbols_ks(params: KerrNewmanParams, xyz: FloatArray) -> FloatArray:
    """Return ``Gamma^mu_(alpha beta)`` in Cartesian Kerr-Schild coordinates."""

    metric_inv = ks_inverse_metric(params, xyz)
    derivatives = np.zeros((4, 4, 4), dtype=np.float64)
    derivatives[1:4] = np.asarray(ks_metric_derivatives(params, xyz))
    gamma = np.zeros((4, 4, 4), dtype=np.float64)
    for mu in range(4):
        for alpha in range(4):
            for beta in range(4):
                gamma[mu, alpha, beta] = 0.5 * sum(
                    metric_inv[mu, nu]
                    * (
                        derivatives[alpha, nu, beta]
                        + derivatives[beta, nu, alpha]
                        - derivatives[nu, alpha, beta]
                    )
                    for nu in range(4)
                )
    return gamma


def rejected_cartesian_wp_shortcut(
    params: KerrNewmanParams,
    x: FloatArray,
    p_cov: FloatArray,
    f_cov: FloatArray,
) -> complex:
    """Evaluate the historical NPGS Cartesian shortcut as a negative control.

    Direct parallel transport proves that this expression is not conserved,
    even for uncharged Kerr.  It remains here only so the rejected definition
    and its measured drift stay reproducible.
    """

    xyz = np.asarray(x, dtype=np.float64)[1:4]
    p = np.asarray(p_cov, dtype=np.float64)
    f = np.asarray(f_cov, dtype=np.float64)
    if xyz.shape != (3,) or p.shape != (4,) or f.shape != (4,):
        raise ValueError("Walker-Penrose inputs have incompatible shapes.")
    electric = f[0] * p[1:4] - p[0] * f[1:4]
    magnetic = np.cross(p[1:4], f[1:4])
    real = -(params.a * electric[2] + float(np.dot(xyz, magnetic)))
    imag = -(float(np.dot(xyz, electric)) + params.a * magnetic[2])
    return complex(real, imag)


def ks_to_bl_coordinates(params: KerrNewmanParams, xyz: FloatArray) -> tuple[float, float, float]:
    """Recover ``(r, theta, phi_KS)`` from a +z Cartesian KS point."""

    values = np.asarray(xyz, dtype=np.float64)
    if values.shape != (3,):
        raise ValueError("Cartesian Kerr-Schild position must contain three values.")
    r = ks_radius(params, values)
    if not math.isfinite(r) or r <= 0.0:
        raise ValueError("Walker-Penrose evaluation requires a positive finite KS radius.")
    cos_theta = float(np.clip(values[2] / r, -1.0, 1.0))
    theta = math.acos(cos_theta)
    x, y = float(values[0]), float(values[1])
    phi_ks = math.atan2(r * y - params.a * x, r * x + params.a * y)
    return r, theta, phi_ks


def walker_penrose_bl_reference(
    params: KerrNewmanParams,
    x: FloatArray,
    p_cov: FloatArray,
    f_up: FloatArray,
) -> complex:
    """Evaluate the standard BL Walker-Penrose scalar from a KS state.

    This is the complete ``(A - i B) (r - i a cos(theta))`` expression used
    as an independent oracle for NPGS's Cartesian shortcut.  The coordinate
    conversion is restricted to the regular BL exterior and must not be used
    as a horizon-crossing transport equation.
    """

    position = np.asarray(x, dtype=np.float64)
    momentum_cov = np.asarray(p_cov, dtype=np.float64)
    polarization_up = np.asarray(f_up, dtype=np.float64)
    if position.shape != (4,) or momentum_cov.shape != (4,) or polarization_up.shape != (4,):
        raise ValueError("Walker-Penrose state fields must each contain four values.")
    r, theta, phi_ks = ks_to_bl_coordinates(params, position[1:4])
    jacobian = bl_to_ks_jacobian(params, r, theta, phi_ks)
    momentum_up_ks = ks_inverse_metric(params, position[1:4]) @ momentum_cov
    momentum_up_bl = np.linalg.solve(jacobian, momentum_up_ks)
    polarization_up_bl = np.linalg.solve(jacobian, polarization_up)

    sin_theta = math.sin(theta)
    cos_theta = math.cos(theta)
    pt, pr, ptheta, pphi = momentum_up_bl
    ft, fr, ftheta, fphi = polarization_up_bl
    a_term = (pt * fr - pr * ft) + params.a * sin_theta**2 * (pr * fphi - pphi * fr)
    b_term = sin_theta * (
        (r * r + params.a * params.a) * (pphi * ftheta - ptheta * fphi)
        - params.a * (pt * ftheta - ptheta * ft)
    )
    return complex(a_term, -b_term) * complex(r, -params.a * cos_theta)


def static_observer_four_velocity_kn(
    params: KerrNewmanParams, xyz: FloatArray
) -> FloatArray:
    """Return the static observer four-velocity where the Killing field is timelike."""

    metric = ks_metric(params, xyz)
    if metric[0, 0] >= 0.0:
        raise ValueError("A static Kerr-Newman observer is invalid inside the ergoregion.")
    return np.array([1.0 / math.sqrt(-metric[0, 0]), 0.0, 0.0, 0.0])


def screen_polarization_from_seed(
    params: KerrNewmanParams,
    state: RayState,
    seed_up: FloatArray,
) -> FloatArray:
    """Project a seed into the observer screen and return normalized ``f^mu``."""

    x = np.asarray(state.x, dtype=np.float64)
    p_cov = np.asarray(state.p, dtype=np.float64)
    seed = np.asarray(seed_up, dtype=np.float64)
    if seed.shape != (4,):
        raise ValueError("Polarization seed must contain four contravariant components.")
    metric = ks_metric(params, x[1:4])
    k_up = ks_inverse_metric(params, x[1:4]) @ p_cov
    observer = static_observer_four_velocity_kn(params, x[1:4])
    energy = -float(observer @ metric @ k_up)
    if not math.isfinite(energy) or abs(energy) <= 1.0e-14:
        raise ValueError("Photon energy in the static observer frame must be nonzero.")
    direction = k_up / energy - observer
    projected = (
        seed
        + float(seed @ metric @ observer) * observer
        - float(seed @ metric @ direction) * direction
    )
    norm_sq = float(projected @ metric @ projected)
    if not math.isfinite(norm_sq) or norm_sq <= 1.0e-14:
        raise ValueError("Polarization seed is degenerate after screen projection.")
    return projected / math.sqrt(norm_sq)


def project_null_covector_time(
    params: KerrNewmanParams, state: RayState
) -> RayState:
    """Project a serialized f32 state onto the nearest null ``p_t`` root."""

    x = np.asarray(state.x, dtype=np.float64)
    p = np.asarray(state.p, dtype=np.float64)
    inverse = ks_inverse_metric(params, x[1:4])
    spatial = p[1:]
    coefficients = np.array(
        [
            inverse[0, 0],
            2.0 * float(inverse[0, 1:] @ spatial),
            float(spatial @ inverse[1:, 1:] @ spatial),
        ]
    )
    roots = np.roots(coefficients)
    real_roots = roots[np.abs(roots.imag) <= 1.0e-10]
    if real_roots.size == 0:
        raise ValueError("Serialized momentum has no real null p_t projection.")
    p_t = float(real_roots[np.argmin(np.abs(real_roots.real - p[0]))].real)
    return RayState(x=x.copy(), p=np.concatenate(([p_t], spatial)))


def reproject_screen_basis(
    params: KerrNewmanParams,
    state: RayState,
    seed_covectors: FloatArray,
) -> FloatArray:
    """Reproject and Gram-Schmidt one or more covectors on the photon screen."""

    seeds = np.asarray(seed_covectors, dtype=np.float64)
    if seeds.ndim != 2 or seeds.shape[1] != 4 or seeds.shape[0] == 0:
        raise ValueError("Screen seeds must have shape (basis, 4).")
    inverse = ks_inverse_metric(params, state.x[1:4])
    metric = ks_metric(params, state.x[1:4])
    basis: list[np.ndarray] = []
    for seed_cov in seeds:
        projected = screen_polarization_from_seed(params, state, inverse @ seed_cov)
        for previous in basis:
            projected -= float(projected @ metric @ previous) * previous
        norm_sq = float(projected @ metric @ projected)
        if not math.isfinite(norm_sq) or norm_sq <= 1.0e-14:
            raise ValueError("Polarization basis is degenerate after Gram-Schmidt.")
        basis.append(projected / math.sqrt(norm_sq))
    return np.asarray([metric @ value for value in basis])


def trace_polarization_basis_kn(
    params: KerrNewmanParams,
    state: RayState,
    f_covectors: FloatArray,
    config: TraceConfig | None = None,
    *,
    r_obs: float | None = None,
) -> PolarizationTransportDiagnostics:
    """Trace one photon and one or more polarization basis covectors."""

    cfg = config or TraceConfig()
    x0 = np.asarray(state.x, dtype=np.float64)
    p0 = np.asarray(state.p, dtype=np.float64)
    f_cov = np.asarray(f_covectors, dtype=np.float64)
    if f_cov.ndim == 1:
        f_cov = f_cov[np.newaxis, :]
    if f_cov.ndim != 2 or f_cov.shape[1] != 4:
        raise ValueError("Polarization covectors must have shape (basis, 4).")
    metric_inv0 = ks_inverse_metric(params, x0[1:4])
    f_up0 = np.einsum("ij,bj->bi", metric_inv0, f_cov)
    y0 = np.concatenate([x0, p0, f_up0.reshape(-1)])
    observer_r = float(r_obs) if r_obs is not None else ks_radius(params, x0[1:4])
    r_escape = cfg.r_escape if cfg.r_escape is not None else max(2.0 * observer_r, observer_r + 50.0)
    capture_r = horizon_radius(params) + float(cfg.horizon_eps)

    def rhs(lam: float, y: np.ndarray) -> np.ndarray:
        geodesic = hamiltonian_rhs_kn(params, lam, y[:8])
        k_up = geodesic[:4]
        gamma = christoffel_symbols_ks(params, y[1:4])
        basis = y[8:].reshape(-1, 4)
        transported = -np.einsum("mab,a,nb->nm", gamma, k_up, basis)
        return np.concatenate([geodesic, transported.reshape(-1)])

    def capture_event(_lam: float, y: np.ndarray) -> float:
        return ks_radius(params, y[1:4]) - capture_r

    capture_event.terminal = True  # type: ignore[attr-defined]
    capture_event.direction = -1.0  # type: ignore[attr-defined]

    def escape_event(_lam: float, y: np.ndarray) -> float:
        return ks_radius(params, y[1:4]) - r_escape

    escape_event.terminal = True  # type: ignore[attr-defined]
    escape_event.direction = 1.0  # type: ignore[attr-defined]

    solution = solve_ivp(
        rhs,
        (0.0, cfg.max_lambda),
        y0,
        method="DOP853",
        rtol=cfg.rtol,
        atol=cfg.atol,
        max_step=cfg.max_step,
        events=(capture_event, escape_event),
    )
    event = "invalid"
    if solution.success and solution.t_events[0].size:
        event = "capture"
    elif solution.success and solution.t_events[1].size:
        event = "escape"
    message = solution.message if event != "invalid" else (
        solution.message if not solution.success else "Reached max_lambda without capture or escape."
    )
    return _transport_diagnostics(params, solution.y.T, float(solution.t[-1]), event, message)


def _transport_diagnostics(
    params: KerrNewmanParams,
    values: np.ndarray,
    lambda_end: float,
    event: str,
    message: str,
) -> PolarizationTransportDiagnostics:
    basis_count = (values.shape[1] - 8) // 4
    h_values: list[float] = []
    norms: list[np.ndarray] = []
    transverse: list[np.ndarray] = []
    shortcut_values: list[np.ndarray] = []
    wp_values: list[np.ndarray] = []
    for row in values:
        x = row[:4]
        p_cov = row[4:8]
        basis_up = row[8:].reshape(basis_count, 4)
        metric = ks_metric(params, x[1:4])
        f_cov = np.einsum("ij,bj->bi", metric, basis_up)
        k_up = ks_inverse_metric(params, x[1:4]) @ p_cov
        h_values.append(abs(ks_hamiltonian(params, x, p_cov)))
        norms.append(np.einsum("bi,bi->b", basis_up, f_cov))
        transverse.append(np.einsum("i,bi->b", k_up, f_cov))
        shortcut_values.append(
            np.asarray(
                [rejected_cartesian_wp_shortcut(params, x, p_cov, cov) for cov in f_cov]
            )
        )
        wp_values.append(
            np.asarray(
                [walker_penrose_bl_reference(params, x, p_cov, up) for up in basis_up]
            )
        )
    norm_array = np.asarray(norms)
    transverse_array = np.asarray(transverse)
    shortcut_array = np.asarray(shortcut_values)
    shortcut_initial = shortcut_array[0]
    shortcut_drift = np.max(np.abs(shortcut_array - shortcut_initial), axis=0)
    shortcut_scale = np.maximum(np.abs(shortcut_initial), 1.0e-15)
    wp_array = np.asarray(wp_values)
    wp_initial = wp_array[0]
    wp_drift = np.max(np.abs(wp_array - wp_initial), axis=0)
    wp_scale = np.maximum(np.abs(wp_initial), 1.0e-15)
    final = values[-1]
    return PolarizationTransportDiagnostics(
        event=event,
        h_max_abs=float(np.max(h_values)),
        norm_drift_abs=np.max(np.abs(norm_array - norm_array[0]), axis=0),
        transverse_max_abs=np.max(np.abs(transverse_array), axis=0),
        wp_drift_abs=wp_drift,
        wp_relative_drift=wp_drift / wp_scale,
        shortcut_drift_abs=shortcut_drift,
        shortcut_relative_drift=shortcut_drift / shortcut_scale,
        lambda_end=lambda_end,
        steps=int(values.shape[0]),
        final_x=final[:4].copy(),
        final_p_cov=final[4:8].copy(),
        final_f_up=final[8:].reshape(basis_count, 4).copy(),
        message=message,
    )
