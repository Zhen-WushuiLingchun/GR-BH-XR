"""Minimal f64 Kerr-Newman reference geometry.

This module is an independent audit oracle for the native NPGS runtime.  It is
not a second renderer.  Neutral photons follow the Kerr-Newman metric in
geometric units ``G = c = 1`` with signature ``(-,+,+,+)``.  The Boyer-
Lindquist expressions follow Eq. (2.1)-(2.2) of
``li2026kerrNewmanPolarizedTransfer``; the Cartesian Kerr-Schild form uses

    g_mn = eta_mn + 2 H l_m l_n,
    H = (M r^3 - Q^2 r^2 / 2) / (r^4 + a^2 z^2).

Only the sub-extremal black-hole domain is accepted here.  Naked singularities
and maximal-extension display modes remain NPGS visual candidates until they
receive separate validation.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .types import FloatArray

MINKOWSKI_COVARIANT = np.diag([-1.0, 1.0, 1.0, 1.0]).astype(np.float64)
MINKOWSKI_INVERSE = MINKOWSKI_COVARIANT.copy()
_R_EPS = 1.0e-14


@dataclass(frozen=True)
class KerrNewmanParams:
    """Sub-extremal Kerr-Newman parameters in geometric units."""

    M: float = 1.0
    a: float = 0.0
    charge: float = 0.0

    def __post_init__(self) -> None:
        if self.M <= 0.0:
            raise ValueError("Kerr-Newman mass M must be positive.")
        if self.a * self.a + self.charge * self.charge >= self.M * self.M:
            raise ValueError("The f64 Kerr-Newman oracle supports only a^2 + Q^2 < M^2.")


@dataclass(frozen=True)
class KerrNewmanInvariants:
    hamiltonian: float
    energy: float
    angular_momentum_z: float
    carter_q: float


def sigma(params: KerrNewmanParams, r: float, theta: float) -> float:
    return r * r + params.a * params.a * math.cos(theta) ** 2


def delta(params: KerrNewmanParams, r: float) -> float:
    return r * r - 2.0 * params.M * r + params.a * params.a + params.charge**2


def horizon_radii(params: KerrNewmanParams) -> tuple[float, float]:
    root = math.sqrt(params.M * params.M - params.a * params.a - params.charge**2)
    return params.M + root, params.M - root


def horizon_radius(params: KerrNewmanParams) -> float:
    return horizon_radii(params)[0]


def covariant_metric_bl(params: KerrNewmanParams, r: float, theta: float) -> FloatArray:
    """Return the Boyer-Lindquist covariant Kerr-Newman metric."""

    s2 = math.sin(theta) ** 2
    sig = sigma(params, r, theta)
    dlt = delta(params, r)
    a = params.a
    shell = 2.0 * params.M * r - params.charge**2

    g = np.zeros((4, 4), dtype=np.float64)
    g[0, 0] = -(1.0 - shell / sig)
    g[0, 3] = g[3, 0] = -a * shell * s2 / sig
    g[1, 1] = sig / dlt
    g[2, 2] = sig
    g[3, 3] = (r * r + a * a + a * a * shell * s2 / sig) * s2
    return g


def inverse_metric_bl(params: KerrNewmanParams, r: float, theta: float) -> FloatArray:
    """Return the analytic Boyer-Lindquist inverse Kerr-Newman metric."""

    s = math.sin(theta)
    s2 = s * s
    if s2 <= 1.0e-14:
        raise ValueError("Boyer-Lindquist inverse metric is singular at the axis.")
    a = params.a
    a2 = a * a
    sig = sigma(params, r, theta)
    dlt = delta(params, r)
    rp = r * r + a2
    shell = rp * rp - a2 * dlt * s2

    g = np.zeros((4, 4), dtype=np.float64)
    g[0, 0] = -shell / (sig * dlt)
    g[0, 3] = g[3, 0] = -a * (2.0 * params.M * r - params.charge**2) / (sig * dlt)
    g[1, 1] = dlt / sig
    g[2, 2] = 1.0 / sig
    g[3, 3] = (dlt - a2 * s2) / (sig * dlt * s2)
    return g


def inverse_metric_bl_derivatives(
    params: KerrNewmanParams, r: float, theta: float
) -> tuple[FloatArray, FloatArray]:
    """Analytically differentiate ``g^mn`` with respect to ``r, theta``."""

    s = math.sin(theta)
    c = math.cos(theta)
    s2 = s * s
    if s2 <= 1.0e-14:
        raise ValueError("Boyer-Lindquist derivatives are singular at the axis.")
    a = params.a
    a2 = a * a
    r2 = r * r
    rp = r2 + a2
    sig = sigma(params, r, theta)
    dlt = delta(params, r)
    sig_r = 2.0 * r
    sig_t = -2.0 * a2 * s * c
    dlt_r = 2.0 * (r - params.M)
    s2_t = 2.0 * s * c
    den = sig * dlt
    den_r = sig_r * dlt + sig * dlt_r
    den_t = sig_t * dlt

    shell = rp * rp - a2 * dlt * s2
    shell_r = 4.0 * r * rp - a2 * dlt_r * s2
    shell_t = -a2 * dlt * s2_t
    d_r = np.zeros((4, 4), dtype=np.float64)
    d_t = np.zeros((4, 4), dtype=np.float64)
    d_r[0, 0] = -_quotient_derivative(shell, shell_r, den, den_r)
    d_t[0, 0] = -_quotient_derivative(shell, shell_t, den, den_t)

    gtphi_num = -a * (2.0 * params.M * r - params.charge**2)
    gtphi_num_r = -2.0 * params.M * a
    d_r[0, 3] = d_r[3, 0] = _quotient_derivative(gtphi_num, gtphi_num_r, den, den_r)
    d_t[0, 3] = d_t[3, 0] = _quotient_derivative(gtphi_num, 0.0, den, den_t)
    d_r[1, 1] = _quotient_derivative(dlt, dlt_r, sig, sig_r)
    d_t[1, 1] = _quotient_derivative(dlt, 0.0, sig, sig_t)
    d_r[2, 2] = -sig_r / (sig * sig)
    d_t[2, 2] = -sig_t / (sig * sig)

    num = dlt - a2 * s2
    num_r = dlt_r
    num_t = -a2 * s2_t
    phi_den = den * s2
    phi_den_r = den_r * s2
    phi_den_t = den_t * s2 + den * s2_t
    d_r[3, 3] = _quotient_derivative(num, num_r, phi_den, phi_den_r)
    d_t[3, 3] = _quotient_derivative(num, num_t, phi_den, phi_den_t)
    return d_r, d_t


def ks_radius(params: KerrNewmanParams, xyz: FloatArray) -> float:
    """Return the oblate-spheroidal radius; charge does not alter this map."""

    x, y, z = _xyz(xyz)
    a2 = params.a * params.a
    rho2 = x * x + y * y + z * z
    q = rho2 - a2
    root = math.sqrt(q * q + 4.0 * a2 * z * z)
    if q < 0.0:
        denom = root - q
        r2 = 2.0 * a2 * z * z / denom if denom > _R_EPS else 0.0
    else:
        r2 = 0.5 * (q + root)
    return math.sqrt(max(0.0, r2))


def ks_h_l_cov(params: KerrNewmanParams, xyz: FloatArray) -> tuple[float, FloatArray]:
    x, y, z = _xyz(xyz)
    a = params.a
    a2 = a * a
    r = ks_radius(params, xyz)
    if r <= _R_EPS:
        raise ValueError("Kerr-Newman Kerr-Schild radius is singular at the ring/origin.")
    den = r * r + a2
    h_den = r**4 + a2 * z * z
    if den <= _R_EPS or h_den <= _R_EPS:
        raise ValueError("Kerr-Newman Kerr-Schild metric is singular at the ring.")
    numerator = params.M * r**3 - 0.5 * params.charge**2 * r * r
    h = numerator / h_den
    l_cov = np.array(
        [1.0, (r * x + a * y) / den, (r * y - a * x) / den, z / r],
        dtype=np.float64,
    )
    return float(h), l_cov


def ks_metric(params: KerrNewmanParams, xyz: FloatArray) -> FloatArray:
    h, l_cov = ks_h_l_cov(params, xyz)
    return MINKOWSKI_COVARIANT + 2.0 * h * np.outer(l_cov, l_cov)


def ks_inverse_metric(params: KerrNewmanParams, xyz: FloatArray) -> FloatArray:
    h, l_cov = ks_h_l_cov(params, xyz)
    l_contra = MINKOWSKI_INVERSE @ l_cov
    return MINKOWSKI_INVERSE - 2.0 * h * np.outer(l_contra, l_contra)


def ks_radius_gradient(params: KerrNewmanParams, xyz: FloatArray) -> FloatArray:
    x, y, z = _xyz(xyz)
    a2 = params.a * params.a
    r = ks_radius(params, xyz)
    if r <= _R_EPS:
        raise ValueError("Kerr-Newman radius gradient is undefined at the ring/origin.")
    rho2 = x * x + y * y + z * z
    radius_den = 2.0 * r * r - rho2 + a2
    if abs(radius_den) <= _R_EPS:
        raise ValueError("Kerr-Newman radius derivative is singular at the ring.")
    return np.array(
        [x * r / radius_den, y * r / radius_den, z * (r * r + a2) / (r * radius_den)],
        dtype=np.float64,
    )


def ks_inverse_metric_derivatives(
    params: KerrNewmanParams, xyz: FloatArray
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Analytic Cartesian derivatives of the inverse Kerr-Schild metric."""

    x, y, z = _xyz(xyz)
    r = ks_radius(params, xyz)
    if r <= _R_EPS:
        raise ValueError("Cannot differentiate Kerr-Newman metric at the ring/origin.")
    dr = ks_radius_gradient(params, xyz)
    h, l_cov = ks_h_l_cov(params, xyz)
    l_contra = MINKOWSKI_INVERSE @ l_cov
    derivatives: list[FloatArray] = []
    for axis in range(3):
        d_xyz = np.zeros(3, dtype=np.float64)
        d_xyz[axis] = 1.0
        dh = _ks_h_derivative(params, r, z, dr[axis], d_xyz[2])
        dl_cov = _ks_l_cov_derivative(params, np.array([x, y, z]), r, dr[axis], d_xyz)
        dl_contra = MINKOWSKI_INVERSE @ dl_cov
        derivatives.append(
            -2.0 * dh * np.outer(l_contra, l_contra)
            - 2.0 * h * (np.outer(dl_contra, l_contra) + np.outer(l_contra, dl_contra))
        )
    return derivatives[0], derivatives[1], derivatives[2]


def ks_inverse_metric_derivatives_finite_difference(
    params: KerrNewmanParams, xyz: FloatArray
) -> tuple[FloatArray, FloatArray, FloatArray]:
    base = np.asarray(xyz, dtype=np.float64)
    result: list[FloatArray] = []
    for axis in range(3):
        step = max(1.0e-5, 1.0e-5 * abs(float(base[axis])))
        offset = np.zeros(3, dtype=np.float64)
        offset[axis] = step
        result.append(
            (ks_inverse_metric(params, base + offset) - ks_inverse_metric(params, base - offset))
            / (2.0 * step)
        )
    return result[0], result[1], result[2]


def ks_hamiltonian(params: KerrNewmanParams, x: FloatArray, p: FloatArray) -> float:
    return float(0.5 * p @ ks_inverse_metric(params, np.asarray(x)[1:4]) @ p)


def ks_invariants(
    params: KerrNewmanParams, x: FloatArray, p_cov: FloatArray
) -> KerrNewmanInvariants:
    """Evaluate neutral-photon ``H, E, L_z, Q`` in Cartesian KS coordinates."""

    x = np.asarray(x, dtype=np.float64)
    p = np.asarray(p_cov, dtype=np.float64)
    xyz = x[1:4]
    r = ks_radius(params, xyz)
    cos_theta = float(np.clip(xyz[2] / r, -1.0, 1.0))
    sin2 = max(0.0, 1.0 - cos_theta * cos_theta)
    energy = -float(p[0])
    lz = float(xyz[0] * p[2] - xyz[1] * p[1])
    carter_q = math.nan
    if sin2 > 1.0e-10:
        sin_theta = math.sqrt(sin2)
        p_theta = (
            p[1] * xyz[0] * cos_theta / sin_theta
            + p[2] * xyz[1] * cos_theta / sin_theta
            - p[3] * r * sin_theta
        )
        carter_q = float(
            p_theta * p_theta
            + cos_theta * cos_theta * (lz * lz / sin2 - params.a * params.a * energy * energy)
        )
    return KerrNewmanInvariants(ks_hamiltonian(params, x, p), energy, lz, carter_q)


def bl_to_ks_cartesian(r: float, theta: float, phi_ks: float, a: float) -> FloatArray:
    sin_t = math.sin(theta)
    return np.array(
        [
            (r * math.cos(phi_ks) - a * math.sin(phi_ks)) * sin_t,
            (r * math.sin(phi_ks) + a * math.cos(phi_ks)) * sin_t,
            r * math.cos(theta),
        ],
        dtype=np.float64,
    )


def bl_to_ks_jacobian(
    params: KerrNewmanParams, r: float, theta: float, phi_ks: float
) -> FloatArray:
    """Return ``d(t_KS,x,y,z)/d(t_BL,r,theta,phi_BL)`` at fixed KS azimuth."""

    a = params.a
    dlt = delta(params, r)
    if abs(dlt) <= 1.0e-14:
        raise ValueError("BL-to-KS Jacobian is singular at a BL horizon.")
    sin_t = math.sin(theta)
    cos_t = math.cos(theta)
    sin_p = math.sin(phi_ks)
    cos_p = math.cos(phi_ks)
    dpsi_dr = a / dlt
    dt_dr = (2.0 * params.M * r - params.charge**2) / dlt
    dx_dr = sin_t * (cos_p + (-r * sin_p - a * cos_p) * dpsi_dr)
    dx_dt = (r * cos_p - a * sin_p) * cos_t
    dx_dp = (-r * sin_p - a * cos_p) * sin_t
    dy_dr = sin_t * (sin_p + (r * cos_p - a * sin_p) * dpsi_dr)
    dy_dt = (r * sin_p + a * cos_p) * cos_t
    dy_dp = (r * cos_p - a * sin_p) * sin_t
    return np.array(
        [
            [1.0, dt_dr, 0.0, 0.0],
            [0.0, dx_dr, dx_dt, dx_dp],
            [0.0, dy_dr, dy_dt, dy_dp],
            [0.0, cos_t, -r * sin_t, 0.0],
        ],
        dtype=np.float64,
    )


def _ks_h_derivative(
    params: KerrNewmanParams, r: float, z: float, dr: float, dz: float
) -> float:
    a2 = params.a * params.a
    den = r**4 + a2 * z * z
    den_d = 4.0 * r**3 * dr + 2.0 * a2 * z * dz
    num = params.M * r**3 - 0.5 * params.charge**2 * r * r
    num_d = (3.0 * params.M * r * r - params.charge**2 * r) * dr
    return _quotient_derivative(num, num_d, den, den_d)


def _ks_l_cov_derivative(
    params: KerrNewmanParams, xyz: FloatArray, r: float, dr: float, d_xyz: FloatArray
) -> FloatArray:
    x, y, z = _xyz(xyz)
    dx, dy, dz = _xyz(d_xyz)
    a = params.a
    den = r * r + a * a
    den_d = 2.0 * r * dr
    lx = r * x + a * y
    ly = r * y - a * x
    return np.array(
        [
            0.0,
            _quotient_derivative(lx, dr * x + r * dx + a * dy, den, den_d),
            _quotient_derivative(ly, dr * y + r * dy - a * dx, den, den_d),
            (dz * r - z * dr) / (r * r),
        ],
        dtype=np.float64,
    )


def _quotient_derivative(value: float, derivative: float, denom: float, denom_d: float) -> float:
    return (derivative * denom - value * denom_d) / (denom * denom)


def _xyz(values: FloatArray) -> tuple[float, float, float]:
    array = np.asarray(values, dtype=np.float64)
    if array.shape[0] < 3:
        raise ValueError("Expected three Cartesian coordinates.")
    return float(array[0]), float(array[1]), float(array[2])
