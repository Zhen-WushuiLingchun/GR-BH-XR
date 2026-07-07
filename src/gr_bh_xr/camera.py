"""Bardeen asymptotic screen-coordinate initialization."""

from __future__ import annotations

import math

import numpy as np

from .metric import covariant_metric, hamiltonian, inverse_metric
from .types import CameraConfig, MetricParams, RayState


def screen_constants(params: MetricParams, camera: CameraConfig) -> tuple[float, float, float]:
    """Return `(E, L_z, Q)` from asymptotic screen coordinates.

    The convention follows the Bardeen screen map used in the Phase 0 analytic
    references: `xi = L_z / E = -alpha sin(theta_obs)` and
    `eta = Q / E^2 = beta^2 + cos(theta_obs)^2 (alpha^2 - a^2)`.
    """

    sin_t = math.sin(camera.theta_obs)
    cos_t = math.cos(camera.theta_obs)
    if abs(sin_t) <= 1.0e-8:
        raise ValueError("Screen map is ill-conditioned at the rotation axis.")

    E = 1.0
    Lz = -camera.alpha * sin_t
    Q = camera.beta * camera.beta + cos_t * cos_t * (camera.alpha * camera.alpha - params.a * params.a)
    return E, Lz, Q


def initial_ray_state(params: MetricParams, camera: CameraConfig) -> RayState:
    """Initialize an inward null ray at the observer screen."""

    E, Lz, Q = screen_constants(params, camera)
    theta = camera.theta_obs
    sin_t = math.sin(theta)
    cos_t = math.cos(theta)

    p_theta_sq = Q - cos_t * cos_t * (Lz * Lz / (sin_t * sin_t) - params.a * params.a * E * E)
    if p_theta_sq < -1.0e-10:
        raise ValueError(f"Screen coordinates produce negative p_theta^2: {p_theta_sq}")
    p_theta = math.copysign(math.sqrt(max(p_theta_sq, 0.0)), camera.beta if camera.beta != 0 else 1.0)

    x = np.array([0.0, camera.r_obs, theta, 0.0], dtype=np.float64)
    p = np.array([-E, 0.0, p_theta, Lz], dtype=np.float64)

    g_inv = inverse_metric(params, camera.r_obs, theta)
    other = (
        g_inv[0, 0] * p[0] * p[0]
        + 2.0 * g_inv[0, 3] * p[0] * p[3]
        + g_inv[2, 2] * p[2] * p[2]
        + g_inv[3, 3] * p[3] * p[3]
    )
    pr_sq = -other / g_inv[1, 1]
    if pr_sq < -1.0e-10:
        raise ValueError(f"Screen coordinates produce negative p_r^2: {pr_sq}")
    p[1] = -math.sqrt(max(pr_sq, 0.0))

    H = abs(hamiltonian(params, x, p))
    if H > 1.0e-8:
        raise ValueError(f"Initialized ray is not null within tolerance: H={H}")
    return RayState(x=x, p=p)


def initial_ray_state_from_unity_direction(
    params: MetricParams,
    *,
    r_obs: float,
    theta_obs: float,
    direction_unity: np.ndarray,
) -> RayState:
    """Initialize a null ray from a finite-radius static observer tetrad.

    Unity local `+z` looks toward the black hole, `+x` is positive-alpha screen
    right, and `+y` is visual up. The static observer is located at
    `(r_obs, theta_obs, phi=0)` in Boyer-Lindquist coordinates. This finite
    tetrad is the correct starting point for full-sky transfer maps; Bardeen
    `(alpha,beta)` screen constants are only the asymptotic/small-angle path.
    """

    direction = np.asarray(direction_unity, dtype=np.float64)
    if direction.shape != (3,):
        raise ValueError("direction_unity must be a 3-vector.")
    norm = np.linalg.norm(direction)
    if not math.isfinite(float(norm)) or norm <= 0.0:
        raise ValueError("direction_unity must be finite and non-zero.")
    direction = direction / norm

    # Unity basis relative to the local static tetrad:
    # +z is radially inward, +y is decreasing theta, +x is decreasing phi.
    n_r = -float(direction[2])
    n_theta = -float(direction[1])
    n_phi = -float(direction[0])

    g_cov = covariant_metric(params, r_obs, theta_obs)
    g_tt = float(g_cov[0, 0])
    g_tphi = float(g_cov[0, 3])
    g_rr = float(g_cov[1, 1])
    g_thetatheta = float(g_cov[2, 2])
    g_phiphi = float(g_cov[3, 3])
    if g_tt >= 0.0:
        raise ValueError("Static observer tetrad is unavailable inside the ergoregion.")

    u_t = 1.0 / math.sqrt(-g_tt)
    e_r = 1.0 / math.sqrt(g_rr)
    e_theta = 1.0 / math.sqrt(g_thetatheta)
    phi_norm_sq = g_phiphi - g_tphi * g_tphi / g_tt
    if phi_norm_sq <= 0.0:
        raise ValueError("Static observer phi tetrad normalization is not spacelike.")
    e_phi_phi = 1.0 / math.sqrt(phi_norm_sq)
    e_phi_t = (-g_tphi / g_tt) * e_phi_phi

    p_con = np.zeros(4, dtype=np.float64)
    p_con[0] = u_t + n_phi * e_phi_t
    p_con[1] = n_r * e_r
    p_con[2] = n_theta * e_theta
    p_con[3] = n_phi * e_phi_phi
    p = g_cov @ p_con
    x = np.array([0.0, r_obs, theta_obs, 0.0], dtype=np.float64)

    H = abs(hamiltonian(params, x, p))
    if H > 1.0e-8:
        raise ValueError(f"Initialized finite-observer ray is not null within tolerance: H={H}")
    if p[0] >= 0.0:
        raise ValueError("Initialized finite-observer ray is not future-directed.")
    return RayState(x=x, p=p)
