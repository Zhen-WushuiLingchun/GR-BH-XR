"""Kerr-Schild Cartesian metric helpers for horizon-penetrating work.

The functions here are the Stage A building blocks for the future near-horizon
reference solver. They do not replace the Boyer-Lindquist Phase 1/2 validators;
they provide a coordinate-regular metric representation that can be cross-
checked against those validators in the exterior domain.
"""

from __future__ import annotations

import math

import numpy as np

from .types import FloatArray, MetricParams

MINKOWSKI_COVARIANT = np.diag([-1.0, 1.0, 1.0, 1.0]).astype(np.float64)
MINKOWSKI_INVERSE = MINKOWSKI_COVARIANT.copy()
_R_EPS = 1.0e-14


def ks_radius(params: MetricParams, xyz: FloatArray) -> float:
    """Return oblate spheroidal Kerr radius from Cartesian Kerr-Schild `(x,y,z)`."""

    return _ks_radius_from_spin(params.a, xyz)


def _ks_radius_from_spin(a: float, xyz: FloatArray) -> float:
    x, y, z = _xyz(xyz)
    a2 = a * a
    rho2 = x * x + y * y + z * z
    q = rho2 - a2
    r2 = 0.5 * (q + math.sqrt(q * q + 4.0 * a2 * z * z))
    return math.sqrt(max(0.0, r2))


def ks_h_l_cov(params: MetricParams, xyz: FloatArray) -> tuple[float, FloatArray]:
    """Return Kerr-Schild scalar `H` and null covector `l_mu`.

    Coordinates use signature `(-,+,+,+)` and ingoing Kerr-Schild Cartesian
    spatial coordinates. The metric is `g_mu nu = eta_mu nu + 2 H l_mu l_nu`.
    """

    x, y, z = _xyz(xyz)
    a = params.a
    a2 = a * a
    r = ks_radius(params, xyz)
    if r <= _R_EPS:
        raise ValueError("Kerr-Schild radius is singular at the ring/origin.")

    den = r * r + a2
    h_den = r**4 + a2 * z * z
    if den <= _R_EPS or h_den <= _R_EPS:
        raise ValueError("Kerr-Schild metric is singular at the ring.")

    h = params.M * r**3 / h_den
    l_cov = np.array(
        [
            1.0,
            (r * x + a * y) / den,
            (r * y - a * x) / den,
            z / r,
        ],
        dtype=np.float64,
    )
    return float(h), l_cov


def ks_metric(params: MetricParams, xyz: FloatArray) -> FloatArray:
    """Return covariant Kerr-Schild Cartesian metric `g_mu nu`."""

    h, l_cov = ks_h_l_cov(params, xyz)
    return MINKOWSKI_COVARIANT + 2.0 * h * np.outer(l_cov, l_cov)


def ks_inverse_metric(params: MetricParams, xyz: FloatArray) -> FloatArray:
    """Return inverse Kerr-Schild Cartesian metric `g^mu nu`."""

    h, l_cov = ks_h_l_cov(params, xyz)
    l_contra = MINKOWSKI_INVERSE @ l_cov
    return MINKOWSKI_INVERSE - 2.0 * h * np.outer(l_contra, l_contra)


def ks_radius_gradient(params: MetricParams, xyz: FloatArray) -> FloatArray:
    """Return the spatial gradient of the Kerr-Schild radius `r(x, y, z)`.

    `r` is defined implicitly by `(x^2 + y^2) / (r^2 + a^2) + z^2 / r^2 = 1`,
    equivalently `r^4 - (rho^2 - a^2) r^2 - a^2 z^2 = 0`.  Implicit
    differentiation gives

        grad r = (x r, y r, z (r^2 + a^2) / r) / D,
        D = 2 r^2 - rho^2 + a^2 = sqrt((rho^2 - a^2)^2 + 4 a^2 z^2),

    so `D` vanishes only on the ring singularity.  On the symmetry axis
    `r = |z|` and the gradient is exactly `(0, 0, 1)`.
    """

    x, y, z = _xyz(xyz)
    a2 = params.a * params.a
    r = ks_radius(params, xyz)
    if r <= _R_EPS:
        raise ValueError("Kerr-Schild radius gradient is undefined at the ring/origin.")
    rho2 = x * x + y * y + z * z
    radius_den = 2.0 * r * r - rho2 + a2
    if abs(radius_den) <= _R_EPS:
        raise ValueError("Kerr-Schild radius derivative is singular at the ring.")
    return np.array(
        [
            x * r / radius_den,
            y * r / radius_den,
            z * (r * r + a2) / (r * radius_den),
        ],
        dtype=np.float64,
    )


def ks_inverse_metric_derivatives(params: MetricParams, xyz: FloatArray) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Analytically differentiate `g^mu nu` with respect to Cartesian `(x,y,z)`."""

    x, y, z = _xyz(xyz)
    a = params.a
    a2 = a * a
    r = ks_radius(params, xyz)
    if r <= _R_EPS:
        raise ValueError("Cannot differentiate Kerr-Schild metric at the ring/origin.")

    r2 = r * r
    r4 = r2 * r2
    dr = ks_radius_gradient(params, xyz)

    h_den = r4 + a2 * z * z
    if h_den <= _R_EPS:
        raise ValueError("Cannot differentiate Kerr-Schild H at the ring.")
    h = params.M * r**3 / h_den
    l_cov = np.array(
        [
            1.0,
            (r * x + a * y) / (r2 + a2),
            (r * y - a * x) / (r2 + a2),
            z / r,
        ],
        dtype=np.float64,
    )
    l_contra = MINKOWSKI_INVERSE @ l_cov

    derivatives: list[FloatArray] = []
    for axis in range(3):
        d_coord = np.zeros(3, dtype=np.float64)
        d_coord[axis] = 1.0
        dh = _ks_h_derivative(params, r, z, dr[axis], d_coord[2])
        dl_cov = _ks_l_cov_derivative(params, xyz, r, dr[axis], d_coord)
        dl_contra = MINKOWSKI_INVERSE @ dl_cov
        derivatives.append(
            -2.0 * dh * np.outer(l_contra, l_contra)
            - 2.0 * h * (np.outer(dl_contra, l_contra) + np.outer(l_contra, dl_contra))
        )
    return derivatives[0], derivatives[1], derivatives[2]


def ks_inverse_metric_derivatives_finite_difference(
    params: MetricParams, xyz: FloatArray
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Finite-difference derivative retained as an oracle for analytic tests."""

    base = np.asarray(xyz, dtype=np.float64)
    derivatives: list[FloatArray] = []
    for axis in range(3):
        step = max(1.0e-5, 1.0e-5 * abs(float(base[axis])))
        delta = np.zeros(3, dtype=np.float64)
        delta[axis] = step
        derivatives.append(
            (ks_inverse_metric(params, base + delta) - ks_inverse_metric(params, base - delta))
            / (2.0 * step)
        )
    return derivatives[0], derivatives[1], derivatives[2]


def ks_hamiltonian(params: MetricParams, x: FloatArray, p: FloatArray) -> float:
    """Compute `H = 1/2 g^mu nu p_mu p_nu` in Cartesian Kerr-Schild coordinates."""

    g_inv = ks_inverse_metric(params, np.asarray(x, dtype=np.float64)[1:4])
    return float(0.5 * p @ g_inv @ p)


def bl_to_ks_cartesian(r: float, theta: float, phi: float, a: float) -> FloatArray:
    """Map Boyer-Lindquist spatial coordinates to Kerr-Schild Cartesian space."""

    sin_theta = math.sin(theta)
    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)
    return np.array(
        [
            (r * cos_phi - a * sin_phi) * sin_theta,
            (r * sin_phi + a * cos_phi) * sin_theta,
            r * math.cos(theta),
        ],
        dtype=np.float64,
    )


def ks_cartesian_to_bl(xyz: FloatArray, a: float) -> tuple[float, float, float]:
    """Map Kerr-Schild Cartesian space to `(r, theta, phi)`.

    This is a spatial-coordinate conversion. It intentionally does not apply the
    time and azimuth shifts needed to transform full BL coordinates into
    ingoing Kerr-Schild coordinates.
    """

    x, y, z = _xyz(xyz)
    r = _ks_radius_from_spin(a, xyz)
    if r <= _R_EPS:
        raise ValueError("Cannot invert Kerr-Schild Cartesian coordinates at r=0.")
    theta = math.acos(max(-1.0, min(1.0, z / r)))
    phi = math.atan2(y * r - a * x, r * x + a * y)
    return float(r), float(theta), float(phi)


def _ks_h_derivative(params: MetricParams, r: float, z: float, dr: float, dz: float) -> float:
    a2 = params.a * params.a
    h_den = r**4 + a2 * z * z
    h_den_derivative = 4.0 * r**3 * dr + 2.0 * a2 * z * dz
    numerator = params.M * r**3
    numerator_derivative = 3.0 * params.M * r * r * dr
    return (numerator_derivative * h_den - numerator * h_den_derivative) / (h_den * h_den)


def _ks_l_cov_derivative(
    params: MetricParams, xyz: FloatArray, r: float, dr: float, d_xyz: FloatArray
) -> FloatArray:
    x, y, z = _xyz(xyz)
    dx, dy, dz = _xyz(d_xyz)
    a = params.a
    den = r * r + a * a
    den_derivative = 2.0 * r * dr

    lx_num = r * x + a * y
    lx_num_derivative = dr * x + r * dx + a * dy
    ly_num = r * y - a * x
    ly_num_derivative = dr * y + r * dy - a * dx

    return np.array(
        [
            0.0,
            _quotient_derivative(lx_num, lx_num_derivative, den, den_derivative),
            _quotient_derivative(ly_num, ly_num_derivative, den, den_derivative),
            (dz * r - z * dr) / (r * r),
        ],
        dtype=np.float64,
    )


def _quotient_derivative(value: float, derivative: float, denom: float, denom_derivative: float) -> float:
    return (derivative * denom - value * denom_derivative) / (denom * denom)


def _xyz(values: FloatArray) -> tuple[float, float, float]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.shape[0] < 3:
        raise ValueError("Expected at least three Cartesian coordinates.")
    return float(arr[0]), float(arr[1]), float(arr[2])
