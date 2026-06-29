"""Analytic Kerr critical-curve helpers.

The formulas follow the spherical photon orbit constants in
`gralla2020nullGeodesicsKerr` / `gralla2020lensingKerr` and the Bardeen screen
map recorded in `docs/equations.md`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .metric import delta, horizon_radius
from .types import FloatArray, MetricParams


@dataclass(frozen=True)
class CriticalCurvePoint:
    r_photon: float
    lambda_tilde: float
    eta_tilde: float
    alpha: float
    beta: float


def photon_shell_bounds(params: MetricParams) -> tuple[float, float]:
    """Return the prograde/retrograde equatorial spherical-orbit radii."""

    if abs(params.a) <= 0.0:
        raise ValueError("Kerr photon-shell bounds require nonzero spin.")
    spin = params.a / params.M
    if spin <= 0.0:
        raise ValueError("Phase 1 critical-curve validation expects 0 < a < M.")
    r_minus = 2.0 * params.M * (1.0 + math.cos((2.0 / 3.0) * math.acos(-spin)))
    r_plus = 2.0 * params.M * (1.0 + math.cos((2.0 / 3.0) * math.acos(spin)))
    if r_minus <= horizon_radius(params):
        raise ValueError("Photon-shell lower bound must be outside the event horizon.")
    return r_minus, r_plus


def spherical_photon_constants(params: MetricParams, r_photon: float) -> tuple[float, float]:
    """Return critical `(lambda, eta)` for a spherical photon orbit."""

    a = params.a
    M = params.M
    if abs(a) <= 0.0:
        raise ValueError("Spherical photon constants require nonzero Kerr spin.")
    dlt = delta(params, r_photon)
    lambda_tilde = a + (r_photon / a) * (r_photon - 2.0 * dlt / (r_photon - M))
    eta_tilde = (r_photon**3 / (a * a)) * (
        4.0 * M * dlt / ((r_photon - M) ** 2) - r_photon
    )
    return lambda_tilde, eta_tilde


def screen_beta_squared(
    params: MetricParams, theta_obs: float, lambda_tilde: float, eta_tilde: float
) -> float:
    sin_t = math.sin(theta_obs)
    cos_t = math.cos(theta_obs)
    if abs(sin_t) <= 1.0e-8:
        raise ValueError("Off-axis critical curve requires nonzero observer inclination.")
    cot2 = (cos_t / sin_t) ** 2
    return eta_tilde + params.a * params.a * cos_t * cos_t - lambda_tilde * lambda_tilde * cot2


def screen_coordinates(
    params: MetricParams,
    theta_obs: float,
    lambda_tilde: float,
    eta_tilde: float,
    beta_sign: float,
) -> tuple[float, float] | None:
    sin_t = math.sin(theta_obs)
    if abs(sin_t) <= 1.0e-8:
        raise ValueError("Off-axis critical curve requires nonzero observer inclination.")
    beta2 = screen_beta_squared(params, theta_obs, lambda_tilde, eta_tilde)
    if beta2 < -1.0e-10:
        return None
    alpha = -lambda_tilde / sin_t
    beta = math.copysign(math.sqrt(max(beta2, 0.0)), beta_sign)
    return alpha, beta


def visible_critical_points(
    params: MetricParams, theta_obs: float, samples: int = 2048
) -> tuple[list[CriticalCurvePoint], list[CriticalCurvePoint]]:
    """Return upper and lower visible critical-curve branches."""

    if samples < 16:
        raise ValueError("At least 16 samples are required for a useful curve.")
    r_min, r_max = photon_shell_bounds(params)
    upper: list[CriticalCurvePoint] = []
    lower: list[CriticalCurvePoint] = []
    for r_photon in np.linspace(r_min, r_max, samples):
        lam, eta = spherical_photon_constants(params, float(r_photon))
        upper_xy = screen_coordinates(params, theta_obs, lam, eta, beta_sign=1.0)
        if upper_xy is None:
            continue
        lower_xy = screen_coordinates(params, theta_obs, lam, eta, beta_sign=-1.0)
        assert lower_xy is not None
        upper.append(CriticalCurvePoint(float(r_photon), lam, eta, upper_xy[0], upper_xy[1]))
        lower.append(CriticalCurvePoint(float(r_photon), lam, eta, lower_xy[0], lower_xy[1]))
    if len(upper) < 3:
        raise ValueError("No visible critical-curve branch could be generated.")
    return upper, lower


def critical_curve_polygon(
    params: MetricParams, theta_obs: float, samples: int = 2048
) -> FloatArray:
    upper, lower = visible_critical_points(params, theta_obs, samples)
    points = [(p.alpha, p.beta) for p in upper] + [(p.alpha, p.beta) for p in reversed(lower)]
    return np.asarray(points, dtype=np.float64)


def curve_center(polygon: FloatArray) -> FloatArray:
    """Return the radial-scan center used by Phase 1 validation."""

    return np.array([float(np.mean(polygon[:, 0])), 0.0], dtype=np.float64)


def ray_polygon_intersection_radius(center: FloatArray, direction: FloatArray, polygon: FloatArray) -> float:
    """Return the first positive intersection radius from `center` to polygon."""

    direction = direction / np.linalg.norm(direction)
    hits: list[float] = []
    n = polygon.shape[0]
    for i in range(n):
        p = polygon[i]
        q = polygon[(i + 1) % n]
        segment = q - p
        matrix = np.array([[direction[0], -segment[0]], [direction[1], -segment[1]]], dtype=np.float64)
        det = float(np.linalg.det(matrix))
        if abs(det) < 1.0e-12:
            continue
        rhs = p - center
        t, u = np.linalg.solve(matrix, rhs)
        if t > 1.0e-9 and -1.0e-9 <= u <= 1.0 + 1.0e-9:
            hits.append(float(t))
    if not hits:
        raise ValueError("Ray from scan center did not intersect critical-curve polygon.")
    return min(hits)
