"""Thin equatorial disk helper formulae for Task 6 transfer maps."""

from __future__ import annotations

import math

from .metric import inverse_metric
from .types import MetricParams


def isco_radius(params: MetricParams, *, prograde: bool = True) -> float:
    """Return the Kerr ISCO radius for an equatorial circular orbit.

    The default is a disk co-rotating with the black-hole spin. For
    Schwarzschild this reduces to `6M`.
    """

    chi = abs(params.a) / params.M
    z1 = 1.0 + (1.0 - chi * chi) ** (1.0 / 3.0) * (
        (1.0 + chi) ** (1.0 / 3.0) + (1.0 - chi) ** (1.0 / 3.0)
    )
    z2 = math.sqrt(3.0 * chi * chi + z1 * z1)
    sign = -1.0 if prograde else 1.0
    return params.M * (3.0 + z2 + sign * math.sqrt((3.0 - z1) * (3.0 + z1 + 2.0 * z2)))


def keplerian_omega(params: MetricParams, r: float, *, prograde: bool = True) -> float:
    """Return equatorial circular-orbit angular velocity `dphi/dt`."""

    orbit_sign = 1.0 if prograde else -1.0
    if params.a < 0.0:
        orbit_sign *= -1.0
    sqrt_m = math.sqrt(params.M)
    return orbit_sign * sqrt_m / (r ** 1.5 + orbit_sign * params.a * sqrt_m)


def keplerian_u_t(params: MetricParams, r: float, *, prograde: bool = True) -> float:
    """Return `u^t` for a Keplerian equatorial circular emitter."""

    theta = math.pi / 2.0
    omega = keplerian_omega(params, r, prograde=prograde)
    g_inv = inverse_metric(params, r, theta)
    # Invert the t-phi block of g^{mu nu}; the metric module exposes the
    # inverse metric because the Hamiltonian uses covariant momenta.
    gtt_inv = g_inv[0, 0]
    gtphi_inv = g_inv[0, 3]
    gphiphi_inv = g_inv[3, 3]
    det_inv = gtt_inv * gphiphi_inv - gtphi_inv * gtphi_inv
    g_tt = gphiphi_inv / det_inv
    g_tphi = -gtphi_inv / det_inv
    g_phiphi = gtt_inv / det_inv
    norm = -(g_tt + 2.0 * omega * g_tphi + omega * omega * g_phiphi)
    if norm <= 0.0 or not math.isfinite(norm):
        raise ValueError("Keplerian circular orbit normalization is not timelike.")
    return 1.0 / math.sqrt(norm)


def redshift_factor(
    params: MetricParams,
    *,
    r: float,
    p_t: float,
    p_phi: float,
    prograde: bool = True,
) -> float:
    """Return `g = nu_obs / nu_emit` for an asymptotic static observer.

    The current camera is asymptotic and initializes `E = -p_t = 1`, so this is
    the Cunningham-style thin-disk redshift factor for a Keplerian emitter.
    """

    energy = -p_t
    omega = keplerian_omega(params, r, prograde=prograde)
    u_t = keplerian_u_t(params, r, prograde=prograde)
    denominator = u_t * (energy - omega * p_phi)
    if denominator <= 0.0 or not math.isfinite(denominator):
        return math.nan
    return energy / denominator
