"""Bardeen asymptotic screen-coordinate initialization."""

from __future__ import annotations

import math

import numpy as np

from .metric import hamiltonian, inverse_metric
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
