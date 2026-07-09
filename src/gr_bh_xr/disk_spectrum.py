"""Thin-disk emission and blackbody color helpers.

This module is CPU-side validation/asset-generation support.  It does not
replace the current Unity visual proxy yet; it provides the physically stronger
Page-Thorne flux profile and blackbody-to-sRGB lookup path needed before that
shader is upgraded.
"""

from __future__ import annotations

import math

import numpy as np

from .disk import isco_radius, keplerian_omega
from .types import FloatArray, MetricParams

_PLANCK_H = 6.62607015e-34
_LIGHT_C = 299792458.0
_BOLTZMANN_K = 1.380649e-23


def circular_orbit_energy_lz(
    params: MetricParams, r: float, *, prograde: bool = True
) -> tuple[float, float]:
    """Return specific `(E, L_z)` for an equatorial circular Kerr orbit.

    The expression follows the standard Bardeen-Press-Teukolsky convention in
    geometric units.  It is used by the Page-Thorne flux integral; stable disk
    calls should keep `r >= r_ISCO`.
    """

    if r <= 0.0:
        raise ValueError("Circular orbit radius must be positive.")
    spin_sign = 1.0 if params.a >= 0.0 else -1.0
    orbit_direction = spin_sign if prograde else -spin_sign
    a = abs(params.a)
    m = params.M
    sqrt_m = math.sqrt(m)
    sqrt_r = math.sqrt(r)
    r32 = r * sqrt_r
    denominator_term = r32 - 3.0 * m * sqrt_r + (2.0 if prograde else -2.0) * a * sqrt_m
    if denominator_term <= 0.0:
        raise ValueError("Circular orbit normalization is not real at this radius.")
    denominator = r ** 0.75 * math.sqrt(denominator_term)
    energy = (r32 - 2.0 * m * sqrt_r + (a * sqrt_m if prograde else -a * sqrt_m)) / denominator
    lz_magnitude = sqrt_m * (
        r * r - (2.0 if prograde else -2.0) * a * math.sqrt(m * r) + a * a
    ) / denominator
    return float(energy), float(orbit_direction * lz_magnitude)


def page_thorne_flux_shape(
    params: MetricParams,
    r: float,
    *,
    prograde: bool = True,
    r_in: float | None = None,
    integration_samples: int = 512,
) -> float:
    """Return dimensionless Page-Thorne thin-disk flux shape at radius `r`.

    The accretion-rate and `4 pi` normalization are intentionally omitted; the
    result is a shape function suitable for validation and color-LUT asset
    generation.  The zero-torque inner boundary makes the flux exactly zero at
    `r_in = r_ISCO`.
    """

    inner = isco_radius(params, prograde=prograde) if r_in is None else float(r_in)
    if r <= inner:
        return 0.0
    if integration_samples < 16:
        raise ValueError("integration_samples must be at least 16.")

    radii = np.linspace(inner, float(r), integration_samples, dtype=np.float64)
    energy = np.empty_like(radii)
    lz = np.empty_like(radii)
    omega = np.empty_like(radii)
    for idx, radius in enumerate(radii):
        energy[idx], lz[idx] = circular_orbit_energy_lz(params, float(radius), prograde=prograde)
        omega[idx] = keplerian_omega(params, float(radius), prograde=prograde)

    dl_dr = np.gradient(lz, radii, edge_order=2)
    integrand = (energy - omega * lz) * dl_dr
    integral = float(np.trapezoid(integrand, radii))
    omega_prime = _omega_derivative(params, float(r), prograde=prograde)
    energy_r = float(energy[-1])
    lz_r = float(lz[-1])
    omega_r = float(omega[-1])
    denom = float(r) * (energy_r - omega_r * lz_r) ** 2
    if denom <= 0.0 or not math.isfinite(denom):
        return math.nan
    flux = -omega_prime * integral / denom
    return max(0.0, float(flux))


def page_thorne_flux_shape_closed_form(
    params: MetricParams,
    r: float,
    *,
    prograde: bool = True,
    r_in: float | None = None,
) -> float:
    """Return the Page-Thorne flux shape using the root/log closed form.

    This is the independent analytic reference for the numerical integral in
    `page_thorne_flux_shape`.  It follows the standard `x = sqrt(r / M)` form
    with the three roots of `x^3 - 3 x + 2 a = 0`; the Schwarzschild limit is
    intentionally left to the numerical integral until its separate limiting
    expression is needed.
    """

    spin = abs(params.a) / params.M
    signed_spin = spin if prograde else -spin
    if abs(signed_spin) <= 1.0e-12:
        raise ValueError("Closed-form Page-Thorne root expression is used for nonzero Kerr spin.")
    if abs(signed_spin) >= 1.0:
        raise ValueError("Closed-form Page-Thorne root expression requires |a| < M.")

    inner = isco_radius(params, prograde=prograde) if r_in is None else float(r_in)
    if r <= inner:
        return 0.0

    x = math.sqrt(float(r) / params.M)
    x0 = math.sqrt(inner / params.M)
    roots = _page_thorne_roots(signed_spin)
    bracket = x - x0 - 1.5 * signed_spin * math.log(x / x0)
    for idx, root in enumerate(roots):
        other = [roots[j] for j in range(3) if j != idx]
        coefficient = (root - signed_spin) ** 2 / (root * (root - other[0]) * (root - other[1]))
        bracket -= 3.0 * coefficient * math.log((x - root) / (x0 - root))
    denominator = x**4 * (x**3 - 3.0 * x + 2.0 * signed_spin)
    if denominator <= 0.0 or not math.isfinite(denominator):
        return math.nan
    return float(1.5 * bracket / (params.M * denominator))


def effective_temperature_shape(flux_shape: float) -> float:
    """Return dimensionless `T_eff` shape from dimensionless flux."""

    if flux_shape <= 0.0 or not math.isfinite(flux_shape):
        return 0.0
    return float(flux_shape ** 0.25)


def planck_lambda(wavelength_m: FloatArray, temperature_k: float) -> FloatArray:
    """Return spectral radiance per wavelength for a blackbody."""

    wavelengths = np.asarray(wavelength_m, dtype=np.float64)
    if temperature_k <= 0.0:
        raise ValueError("temperature_k must be positive.")
    exponent = _PLANCK_H * _LIGHT_C / (wavelengths * _BOLTZMANN_K * temperature_k)
    return (2.0 * _PLANCK_H * _LIGHT_C * _LIGHT_C) / (
        wavelengths**5 * np.expm1(np.clip(exponent, 1.0e-12, 700.0))
    )


def cie_xyz_1931_wyman(wavelength_nm: FloatArray) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Approximate CIE 1931 2-degree XYZ matching functions.

    Uses the Wyman, Sloan & Shirley analytic fits to the CIE 1931 color-matching
    curves.  This avoids committing a large tabulated CMF asset while keeping a
    deterministic CPU-side color pipeline.
    """

    wave = np.asarray(wavelength_nm, dtype=np.float64)
    x = (
        0.362 * _piecewise_gaussian(wave, 442.0, 0.0624, 0.0374)
        + 1.056 * _piecewise_gaussian(wave, 599.8, 0.0264, 0.0323)
        - 0.065 * _piecewise_gaussian(wave, 501.1, 0.0490, 0.0382)
    )
    y = (
        0.821 * _piecewise_gaussian(wave, 568.8, 0.0213, 0.0247)
        + 0.286 * _piecewise_gaussian(wave, 530.9, 0.0613, 0.0322)
    )
    z = (
        1.217 * _piecewise_gaussian(wave, 437.0, 0.0845, 0.0278)
        + 0.681 * _piecewise_gaussian(wave, 459.0, 0.0385, 0.0725)
    )
    return x, y, z


def blackbody_xyz(
    temperature_k: float,
    *,
    wavelength_min_nm: float = 380.0,
    wavelength_max_nm: float = 780.0,
    step_nm: float = 5.0,
) -> tuple[float, float, float]:
    """Integrate a blackbody spectrum against approximate CIE XYZ curves."""

    wavelengths_nm = np.arange(wavelength_min_nm, wavelength_max_nm + 0.5 * step_nm, step_nm)
    wavelengths_m = wavelengths_nm * 1.0e-9
    spectrum = planck_lambda(wavelengths_m, temperature_k)
    x_bar, y_bar, z_bar = cie_xyz_1931_wyman(wavelengths_nm)
    x = float(np.trapezoid(spectrum * x_bar, wavelengths_nm))
    y = float(np.trapezoid(spectrum * y_bar, wavelengths_nm))
    z = float(np.trapezoid(spectrum * z_bar, wavelengths_nm))
    total = x + y + z
    if total <= 0.0 or not math.isfinite(total):
        return math.nan, math.nan, math.nan
    return x / total, y / total, z / total


def blackbody_linear_srgb(temperature_k: float) -> tuple[float, float, float]:
    """Return max-normalized linear sRGB chromaticity for a blackbody."""

    x, y, z = blackbody_xyz(temperature_k)
    xyz = np.array([x, y, z], dtype=np.float64)
    rgb = np.array(
        [
            [3.2406, -1.5372, -0.4986],
            [-0.9689, 1.8758, 0.0415],
            [0.0557, -0.2040, 1.0570],
        ],
        dtype=np.float64,
    ) @ xyz
    rgb = np.clip(rgb, 0.0, None)
    max_channel = float(np.max(rgb))
    if max_channel <= 0.0 or not math.isfinite(max_channel):
        return math.nan, math.nan, math.nan
    rgb = rgb / max_channel
    return float(rgb[0]), float(rgb[1]), float(rgb[2])


def _omega_derivative(params: MetricParams, r: float, *, prograde: bool) -> float:
    step = max(1.0e-5, abs(r) * 1.0e-5)
    return (
        keplerian_omega(params, r + step, prograde=prograde)
        - keplerian_omega(params, r - step, prograde=prograde)
    ) / (2.0 * step)


def _page_thorne_roots(signed_spin: float) -> tuple[float, float, float]:
    angle = math.acos(max(-1.0, min(1.0, -signed_spin))) / 3.0
    roots = (
        2.0 * math.cos(angle),
        2.0 * math.cos(angle - 2.0 * math.pi / 3.0),
        2.0 * math.cos(angle + 2.0 * math.pi / 3.0),
    )
    return tuple(sorted(roots))


def _piecewise_gaussian(wave: np.ndarray, center: float, left_tau: float, right_tau: float) -> np.ndarray:
    tau = np.where(wave < center, left_tau, right_tau)
    t = tau * (wave - center)
    return np.exp(-0.5 * t * t)
