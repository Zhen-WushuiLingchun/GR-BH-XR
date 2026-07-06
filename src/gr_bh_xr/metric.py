"""Boyer-Lindquist Kerr metric helpers.

References:
- Carter constant: `carter1968kerr`.
- Kerr screen/geodesic conventions: `bardeen1973kerrGeodesics`,
  `gralla2020nullGeodesicsKerr`.
"""

from __future__ import annotations

import math

import numpy as np

from .types import FloatArray, MetricParams


def sigma(params: MetricParams, r: float, theta: float) -> float:
    return r * r + params.a * params.a * math.cos(theta) ** 2


def delta(params: MetricParams, r: float) -> float:
    return r * r - 2.0 * params.M * r + params.a * params.a


def horizon_radius(params: MetricParams) -> float:
    return params.M + math.sqrt(params.M * params.M - params.a * params.a)


def covariant_metric(params: MetricParams, r: float, theta: float) -> FloatArray:
    """Return `g_{mu nu}` for signature (-,+,+,+)."""

    s2 = math.sin(theta) ** 2
    sig = sigma(params, r, theta)
    dlt = delta(params, r)
    a = params.a
    M = params.M

    g = np.zeros((4, 4), dtype=np.float64)
    g[0, 0] = -(1.0 - 2.0 * M * r / sig)
    g[0, 3] = g[3, 0] = -2.0 * M * a * r * s2 / sig
    g[1, 1] = sig / dlt
    g[2, 2] = sig
    g[3, 3] = ((r * r + a * a) ** 2 - a * a * dlt * s2) * s2 / sig
    return g


def inverse_metric(params: MetricParams, r: float, theta: float) -> FloatArray:
    """Return analytic `g^{mu nu}` in Boyer-Lindquist coordinates."""

    s = math.sin(theta)
    s2 = s * s
    if s2 <= 1.0e-14:
        raise ValueError("Boyer-Lindquist inverse metric is singular at the axis.")

    sig = sigma(params, r, theta)
    dlt = delta(params, r)
    a = params.a
    M = params.M

    g = np.zeros((4, 4), dtype=np.float64)
    g[0, 0] = -(((r * r + a * a) ** 2 - a * a * dlt * s2) / (sig * dlt))
    g[0, 3] = g[3, 0] = -2.0 * M * a * r / (sig * dlt)
    g[1, 1] = dlt / sig
    g[2, 2] = 1.0 / sig
    g[3, 3] = (dlt - a * a * s2) / (sig * dlt * s2)
    return g


def hamiltonian(params: MetricParams, x: FloatArray, p: FloatArray) -> float:
    """Compute `H = 1/2 g^{mu nu} p_mu p_nu`."""

    g_inv = inverse_metric(params, float(x[1]), float(x[2]))
    return float(0.5 * p @ g_inv @ p)


def carter_constant(params: MetricParams, x: FloatArray, p: FloatArray) -> float:
    """Compute the null-geodesic Carter constant `Q`.

    For null geodesics:
    Q = p_theta^2 + cos(theta)^2 * (L_z^2 / sin(theta)^2 - a^2 E^2).
    """

    theta = float(x[2])
    sin2 = math.sin(theta) ** 2
    if sin2 <= 1.0e-14:
        raise ValueError("Carter constant is singular at the axis.")
    E = -float(p[0])
    Lz = float(p[3])
    cos2 = math.cos(theta) ** 2
    return float(p[2] * p[2] + cos2 * (Lz * Lz / sin2 - params.a * params.a * E * E))


def inverse_metric_derivatives(
    params: MetricParams, r: float, theta: float
) -> tuple[FloatArray, FloatArray]:
    """Analytically differentiate `g^{mu nu}` with respect to `(r, theta)`."""

    s = math.sin(theta)
    c = math.cos(theta)
    s2 = s * s
    if s2 <= 1.0e-14:
        raise ValueError("Boyer-Lindquist inverse metric derivatives are singular at the axis.")

    a = params.a
    a2 = a * a
    M = params.M
    r2 = r * r
    rp = r2 + a2
    sig = sigma(params, r, theta)
    dlt = delta(params, r)

    sig_r = 2.0 * r
    sig_t = -2.0 * a2 * s * c
    dlt_r = 2.0 * (r - M)
    s2_t = 2.0 * s * c

    den = sig * dlt
    den_r = sig_r * dlt + sig * dlt_r
    den_t = sig_t * dlt

    shell = rp * rp - a2 * dlt * s2
    shell_r = 4.0 * r * rp - a2 * dlt_r * s2
    shell_t = -a2 * dlt * s2_t

    d_r = np.zeros((4, 4), dtype=np.float64)
    d_theta = np.zeros((4, 4), dtype=np.float64)

    d_r[0, 0] = -_quotient_derivative(shell, shell_r, den, den_r)
    d_theta[0, 0] = -_quotient_derivative(shell, shell_t, den, den_t)

    gtphi_num = -2.0 * M * a * r
    gtphi_num_r = -2.0 * M * a
    d_r[0, 3] = d_r[3, 0] = _quotient_derivative(gtphi_num, gtphi_num_r, den, den_r)
    d_theta[0, 3] = d_theta[3, 0] = _quotient_derivative(gtphi_num, 0.0, den, den_t)

    d_r[1, 1] = _quotient_derivative(dlt, dlt_r, sig, sig_r)
    d_theta[1, 1] = _quotient_derivative(dlt, 0.0, sig, sig_t)

    d_r[2, 2] = -sig_r / (sig * sig)
    d_theta[2, 2] = -sig_t / (sig * sig)

    gphiphi_num = dlt - a2 * s2
    gphiphi_num_r = dlt_r
    gphiphi_num_t = -a2 * s2_t
    gphiphi_den = sig * dlt * s2
    gphiphi_den_r = den_r * s2
    gphiphi_den_t = den_t * s2 + den * s2_t
    d_r[3, 3] = _quotient_derivative(
        gphiphi_num, gphiphi_num_r, gphiphi_den, gphiphi_den_r
    )
    d_theta[3, 3] = _quotient_derivative(
        gphiphi_num, gphiphi_num_t, gphiphi_den, gphiphi_den_t
    )
    return d_r, d_theta


def _quotient_derivative(value: float, derivative: float, denom: float, denom_derivative: float) -> float:
    return (derivative * denom - value * denom_derivative) / (denom * denom)


def inverse_metric_derivatives_finite_difference(
    params: MetricParams, r: float, theta: float
) -> tuple[FloatArray, FloatArray]:
    """Finite-difference derivative retained for analytic-derivative tests.

    This is not used by the integrator. It is kept only as an independent
    numerical cross-check for the closed-form derivatives above.
    """

    hr = max(1.0e-5, 1.0e-5 * abs(r))
    ht = 1.0e-5
    theta_low = max(theta - ht, 1.0e-7)
    theta_high = min(theta + ht, math.pi - 1.0e-7)
    if theta_high == theta_low:
        raise ValueError("Cannot differentiate near Boyer-Lindquist axis.")

    d_r = (inverse_metric(params, r + hr, theta) - inverse_metric(params, r - hr, theta)) / (
        2.0 * hr
    )
    d_theta = (inverse_metric(params, r, theta_high) - inverse_metric(params, r, theta_low)) / (
        theta_high - theta_low
    )
    return d_r, d_theta
