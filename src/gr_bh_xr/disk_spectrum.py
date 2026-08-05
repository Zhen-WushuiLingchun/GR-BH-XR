"""Thin-disk emission and blackbody color helpers.

This module is CPU-side validation/asset-generation support.  It does not
replace the current Unity visual proxy yet; it provides the physically stronger
Page-Thorne flux profile and blackbody-to-sRGB lookup path needed before that
shader is upgraded.
"""

from __future__ import annotations

import math
import json
from pathlib import Path

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
    return float(1.5 * bracket / (params.M * params.M * denominator))


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


def observed_temperature(emit_temperature_k: float, redshift_g: float) -> float:
    """Return `T_obs = g T_emit` for a thermal emitter."""

    if emit_temperature_k <= 0.0:
        raise ValueError("emit_temperature_k must be positive.")
    if redshift_g <= 0.0 or not math.isfinite(redshift_g):
        return math.nan
    return float(redshift_g * emit_temperature_k)


def intensity_redshift_weight(redshift_g: float, *, bolometric: bool = True) -> float:
    """Return the invariant-intensity redshift weight.

    For specific intensity, `I_nu / nu^3` gives a `g^3` factor.  For a
    bolometric/blackbody-integrated proxy, the additional frequency integration
    gives `g^4`.
    """

    if redshift_g < 0.0 or not math.isfinite(redshift_g):
        return math.nan
    power = 4 if bolometric else 3
    return float(redshift_g**power)


def blackbody_lut(
    *,
    temperature_min_k: float = 1000.0,
    temperature_max_k: float = 40000.0,
    samples: int = 256,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Return `(temperature_k, xyz_chromaticity, linear_srgb)` LUT arrays."""

    if temperature_min_k <= 0.0 or temperature_max_k <= temperature_min_k:
        raise ValueError("Invalid blackbody LUT temperature range.")
    if samples < 2:
        raise ValueError("blackbody LUT requires at least two samples.")
    temperatures = np.geomspace(temperature_min_k, temperature_max_k, samples, dtype=np.float64)
    xyz = np.array([blackbody_xyz(float(value)) for value in temperatures], dtype=np.float64)
    rgb = np.array([blackbody_linear_srgb(float(value)) for value in temperatures], dtype=np.float64)
    return temperatures, xyz, rgb


def write_blackbody_lut_npz(
    out: str | Path,
    *,
    temperature_min_k: float = 1000.0,
    temperature_max_k: float = 40000.0,
    samples: int = 256,
) -> dict[str, float | int | str]:
    """Write a compressed CPU blackbody color LUT for later texture packaging."""

    temperatures, xyz, rgb = blackbody_lut(
        temperature_min_k=temperature_min_k,
        temperature_max_k=temperature_max_k,
        samples=samples,
    )
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        temperature_k=temperatures,
        xyz_chromaticity=xyz,
        linear_srgb=rgb,
    )
    return {
        "path": str(path),
        "samples": int(samples),
        "temperature_min_k": float(temperature_min_k),
        "temperature_max_k": float(temperature_max_k),
        "color_space": "max-normalized linear sRGB chromaticity",
    }


def planck_locus_rb_coordinate(rgb: FloatArray) -> FloatArray:
    """Return the chromaticity coordinate `u = R / (R + B)` of linear sRGB rows.

    `u` is dimensionless and scale invariant, so a source pixel need not be
    max-normalized.  Along the Planck locus it decreases monotonically with
    temperature once the sub-plateau region is removed (see
    `blackbody_locus_inverse`), so it serves as a one-parameter inverse: a
    pixel's chromaticity maps back to the blackbody temperature with the same
    red-to-blue ratio.  This is a ratio match, not a fit: the green channel is
    ignored and no residual is minimized, so for an off-locus pixel the
    returned temperature has no goodness-of-fit interpretation.  `u` is also
    not gamma invariant, so the caller must supply linear values.
    """

    rows = np.asarray(rgb, dtype=np.float64)
    red = rows[..., 0]
    blue = rows[..., 2]
    return red / np.maximum(red + blue, 1.0e-12)


def blackbody_locus_inverse(rgb: FloatArray, samples: int) -> tuple[FloatArray, int, int]:
    """Return the texel-sampled inverse Planck locus for a chromaticity LUT.

    Input is the `(N, 3)` max-normalized linear sRGB table produced by
    `blackbody_lut`; `samples` is the output texel count.  The result is
    resampled at texel centers `(i + 0.5) / samples` of the dimensionless
    chromaticity coordinate `u = R / (R + B)`, and its value is the
    dimensionless log-normalized temperature

        s = log(T / T_min) / log(T_max / T_min) in [0, 1],

    so a consumer recovers `T = T_min * (T_max / T_min)**s`.

    Below the point where the clipped linear-sRGB blue channel reaches exactly
    zero (about `1.9e3 K`) `u` sits on a plateau at 1 and chromaticity carries
    no temperature information.  Only the hottest member of a plateau is kept,
    so a fully red pixel maps to the hottest temperature consistent with its
    chromaticity, up to the LUT's own temperature resolution.  Consequently the
    inverse SATURATES: it can never return a temperature below the kept anchor
    row, which is far above `T_min`.

    Returns `(inverse, plateau_rows_dropped, first_kept_index)`; the last two
    are recorded in the asset metadata for audit.
    """

    rows = np.asarray(rgb, dtype=np.float64)
    if rows.ndim != 2 or rows.shape[1] != 3:
        raise ValueError("blackbody_locus_inverse expects an (N, 3) linear sRGB table.")
    if rows.shape[0] < 2:
        raise ValueError("blackbody_locus_inverse needs at least two locus rows.")
    if samples < 2:
        raise ValueError("blackbody_locus_inverse needs at least two output texels.")

    locus_rb = planck_locus_rb_coordinate(rows)
    # geomspace temperatures are exactly log-even, so the normalized log
    # temperature coordinate is a plain linspace on [0, 1].
    temperature_norm = np.linspace(0.0, 1.0, rows.shape[0], dtype=np.float64)
    # `locus_rb` decreases with index, so `diff < 0` marks a row that is
    # strictly hotter-than-its-successor in chromaticity; the final row is
    # always the hottest sample and is kept unconditionally.  On a leading
    # plateau this keeps the last (hottest) member.
    keep = np.concatenate((np.diff(locus_rb) < 0.0, [True]))
    kept_indices = np.flatnonzero(keep)
    locus_valid = locus_rb[keep]
    norm_valid = temperature_norm[keep]
    if locus_valid.size < 2:
        # Guard the vacuous case: `np.all` over an empty diff is True, so a
        # single surviving row would otherwise emit a constant-alpha LUT.
        raise ValueError(
            "Planck locus inversion needs at least two rows above the "
            "chromaticity plateau; widen the temperature range or add samples."
        )
    if not np.all(np.diff(locus_valid) < 0.0):
        raise ValueError("Planck locus R/(R+B) must be strictly monotone after plateau removal.")
    texel_centers = (np.arange(samples, dtype=np.float64) + 0.5) / samples
    inverse = np.interp(texel_centers, locus_valid[::-1], norm_valid[::-1])
    return inverse, int(rows.shape[0] - locus_valid.size), int(kept_indices[0])


def write_blackbody_lut_unity_raw(
    out: str | Path,
    *,
    metadata_out: str | Path | None = None,
    temperature_min_k: float = 1000.0,
    temperature_max_k: float = 40000.0,
    samples: int = 256,
) -> dict[str, float | int | str]:
    """Write a Unity-friendly 1D RGBA32F blackbody chromaticity LUT (schema v2).

    The RGB channels are max-normalized linear sRGB chromaticity sampled by the
    log-temperature coordinate (a consumer samples with `log(T_obs)`).  The
    alpha channel is the INVERSE Planck locus: sampled by the dimensionless
    chromaticity coordinate `u = R / (R + B)` of a source pixel, it returns the
    log-normalized temperature whose locus chromaticity equals `u`.  One
    texture therefore carries both directions of the blackbody color map.
    Alpha in the v1 schema was the constant 1 and unused, so the change is the
    reason for the version bump.
    """

    temperatures, _, rgb = blackbody_lut(
        temperature_min_k=temperature_min_k,
        temperature_max_k=temperature_max_k,
        samples=samples,
    )
    inverse_locus, plateau_dropped, first_kept = blackbody_locus_inverse(rgb, samples)
    anchor_temperature_k = float(temperatures[first_kept])
    # Every channel is written below; unlike v1 there is no "alpha = valid = 1"
    # fill to preserve.
    rgba = np.empty((samples, 4), dtype=np.float32)
    rgba[:, :3] = rgb.astype(np.float32)
    rgba[:, 3] = inverse_locus.astype(np.float32)
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(rgba.tobytes(order="C"))
    summary: dict[str, float | int | str] = {
        "path": str(path),
        "schema": "gr-bh-xr.task6.disk_color_lut.v2",
        "samples": int(samples),
        "temperature_min_k": float(temperature_min_k),
        "temperature_max_k": float(temperature_max_k),
        "temperature_spacing": "log",
        "texture_format": "rgba32f",
        "color_space": "max-normalized linear sRGB chromaticity",
        "alpha_channel": "planck-locus-inverse",
        "plateau_rows_dropped": int(plateau_dropped),
        "alpha_anchor_temperature_k": anchor_temperature_k,
        "bytes": int(rgba.nbytes),
    }
    if metadata_out is not None:
        meta_path = Path(metadata_out)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        metadata = {
            "schema": summary["schema"],
            "samples": int(samples),
            "temperatureMinK": float(temperatures[0]),
            "temperatureMaxK": float(temperatures[-1]),
            "temperatureSpacing": "log",
            "textureFormat": "rgba32f",
            "colorSpace": summary["color_space"],
            "alphaChannel": "planck-locus-inverse",
            "plateauRowsDropped": int(plateau_dropped),
            "alphaAnchorTemperatureK": anchor_temperature_k,
            "units": {
                "samples": "count (dimensionless)",
                "plateauRowsDropped": "count (dimensionless)",
                "temperatureMinK": "K",
                "temperatureMaxK": "K",
                "alphaAnchorTemperatureK": (
                    "K; coldest row the inverse is built from. Chromaticity "
                    "carries no temperature information below roughly 1.9e3 K, "
                    "where the clipped linear-sRGB blue channel reaches exactly "
                    "zero, so the inverse saturates here and can never return "
                    "temperatureMinK"
                ),
                "rgbChannels": "dimensionless chromaticity in [0, 1]",
                "alphaChannel": "dimensionless log-normalized temperature in [0, 1]",
                "lookupCoordinate": "dimensionless u = R/(R+B) in [0, 1]",
            },
            "sampling": {
                "rowTemperature": (
                    "row i holds T_i = temperatureMinK * "
                    "(temperatureMaxK / temperatureMinK)**(i / (samples - 1))"
                ),
                "rgbCoordinateExact": (
                    "s = log(T_obs / temperatureMinK) / "
                    "log(temperatureMaxK / temperatureMinK); the texture "
                    "coordinate that lands exactly on row i is "
                    "u = (s * (samples - 1) + 0.5) / samples"
                ),
                "rgbCoordinateConsumerNote": (
                    "the current Unity consumer samples with u = s, which is a "
                    "half-texel offset: measured bias at samples = 256 is 0.72 "
                    "percent in effective temperature and 0.0021 per linear "
                    "sRGB channel. Reconciling the shader is Task 9-10 work and "
                    "is not owned by this producer"
                ),
                "alphaCoordinate": (
                    "alpha is resampled at texel centers of u = R / (R + B), so "
                    "the source pixel's u IS the texture coordinate; no "
                    "endpoint correction is needed and the consumer is correct "
                    "as written"
                ),
                "alphaInverse": (
                    "T = temperatureMinK * (temperatureMaxK / temperatureMinK)**alpha"
                ),
                "addressing": "clamp",
                "filtering": "bilinear",
            },
            "channels": {
                "r": "max-normalized linear sRGB red chromaticity",
                "g": "max-normalized linear sRGB green chromaticity",
                "b": "max-normalized linear sRGB blue chromaticity",
                "a": "inverse Planck locus: u = R/(R+B) -> log-normalized temperature",
            },
        }
        meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf8")
        summary["metadata_path"] = str(meta_path)
    return summary


def page_thorne_radial_lut(
    params: MetricParams,
    *,
    r_min: float | None = None,
    r_max: float = 30.0,
    samples: int = 512,
    prograde: bool = True,
) -> tuple[FloatArray, FloatArray, FloatArray, float, float]:
    """Return a normalized Page-Thorne radial flux/temperature table.

    The returned flux is normalized by its maximum over the sampled disk.  This
    keeps the Unity texture dimensionless; absolute luminosity still requires
    an accretion-rate normalization outside this project stage.
    """

    if samples < 2:
        raise ValueError("Page-Thorne radial LUT requires at least two samples.")
    inner = isco_radius(params, prograde=prograde) if r_min is None else float(r_min)
    if r_max <= inner:
        raise ValueError("r_max must be larger than the inner disk radius.")

    radii = np.linspace(inner, float(r_max), samples, dtype=np.float64)
    flux = np.empty_like(radii)
    for idx, radius in enumerate(radii):
        if abs(params.a) > 1.0e-12:
            flux[idx] = page_thorne_flux_shape_closed_form(
                params,
                float(radius),
                prograde=prograde,
                r_in=inner,
            )
        else:
            flux[idx] = page_thorne_flux_shape(
                params,
                float(radius),
                prograde=prograde,
                r_in=inner,
                integration_samples=1024,
            )
    flux = np.nan_to_num(flux, nan=0.0, posinf=0.0, neginf=0.0)
    flux = np.clip(flux, 0.0, None)
    peak = float(np.max(flux))
    if peak <= 0.0 or not math.isfinite(peak):
        raise ValueError("Page-Thorne radial LUT has no positive flux samples.")
    normalized_flux = flux / peak
    temperature_shape = np.zeros_like(normalized_flux)
    np.power(normalized_flux, 0.25, out=temperature_shape, where=normalized_flux > 0.0)
    return radii, normalized_flux, temperature_shape, peak, inner


def write_page_thorne_radial_lut_unity_raw(
    out: str | Path,
    *,
    metadata_out: str | Path | None = None,
    params: MetricParams = MetricParams(),
    r_min: float | None = None,
    r_max: float = 30.0,
    samples: int = 512,
    prograde: bool = True,
    temperature_scale_k: float = 6500.0,
) -> dict[str, float | int | str | bool]:
    """Write a Unity RGBA32F radial Page-Thorne flux/temperature LUT.

    Channels are `(F_norm, T_shape, 0, valid)`, where `T_shape = F_norm^(1/4)`.
    Unity combines this with the disk-transfer redshift as
    `T_obs = g T_scale T_shape` and bolometric brightness `F_norm g^4`.
    """

    if temperature_scale_k <= 0.0:
        raise ValueError("temperature_scale_k must be positive.")
    radii, flux, temperature_shape, peak, inner = page_thorne_radial_lut(
        params,
        r_min=r_min,
        r_max=r_max,
        samples=samples,
        prograde=prograde,
    )
    rgba = np.zeros((samples, 4), dtype=np.float32)
    rgba[:, 0] = flux.astype(np.float32)
    rgba[:, 1] = temperature_shape.astype(np.float32)
    rgba[:, 3] = 1.0
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(rgba.tobytes(order="C"))
    summary: dict[str, float | int | str | bool] = {
        "path": str(path),
        "schema": "gr-bh-xr.task6.disk_radial_lut.v1",
        "samples": int(samples),
        "r_min": float(radii[0]),
        "r_max": float(radii[-1]),
        "radius_spacing": "linear",
        "M": float(params.M),
        "a": float(params.a),
        "prograde": bool(prograde),
        "r_isco": float(inner),
        "flux_peak_shape": float(peak),
        "temperature_scale_k": float(temperature_scale_k),
        "texture_format": "rgba32f",
        "bytes": int(rgba.nbytes),
    }
    if metadata_out is not None:
        meta_path = Path(metadata_out)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        metadata = {
            "schema": summary["schema"],
            "samples": int(samples),
            "rMin": float(radii[0]),
            "rMax": float(radii[-1]),
            "radiusSpacing": "linear",
            "M": float(params.M),
            "a": float(params.a),
            "prograde": bool(prograde),
            "rISCO": float(inner),
            "aOverM": float(params.a / params.M),
            "rIscoOverM": float(inner / params.M),
            "fluxPeakShape": float(peak),
            "temperatureScaleK": float(temperature_scale_k),
            "textureFormat": "rgba32f",
            "units": {
                "system": (
                    "geometric G = c = 1; r, M and a are code lengths, so "
                    "divide by M to get r/M and a/M"
                ),
                "samples": "count (dimensionless)",
                "rMin": "geometric length (same unit as M)",
                "rMax": "geometric length (same unit as M)",
                "rISCO": "geometric length (same unit as M)",
                "M": "geometric mass length unit GM/c^2",
                "a": (
                    "geometric length J/M, NOT the dimensionless spin; "
                    "|a| <= M and a/M is published as aOverM"
                ),
                "aOverM": "dimensionless spin",
                "rIscoOverM": "dimensionless",
                "temperatureScaleK": (
                    "K; the observed temperature at the flux peak for g = 1, a "
                    "display parameter rather than a derived disk temperature"
                ),
                "fluxPeakShape": (
                    "max(F) of the Page-Thorne flux shape, in geometric units "
                    "of length^-2: it scales as M^-2 at fixed r/M and is NOT "
                    "dimensionless. The omitted Mdot / (4 pi) factor is itself "
                    "dimensionless in G = c = 1, so dropping it cannot remove "
                    "the length^-2 dimension. It is not W/m^2"
                ),
                "channelR": "dimensionless F(r) / max(F)",
                "channelG": "dimensionless [F(r) / max(F)]^(1/4)",
                "channelB": "unused, reserved = 0",
                "channelA": "dimensionless validity flag",
            },
            "sampling": {
                "rowRadius": "row i holds r_i = rMin + i * (rMax - rMin) / (samples - 1)",
                "radiusCoordinateExact": (
                    "s = (r - rMin) / (rMax - rMin); the texture coordinate "
                    "that lands exactly on row i is "
                    "u = (s * (samples - 1) + 0.5) / samples"
                ),
                "radiusCoordinateConsumerNote": (
                    "the current Unity consumer samples with u = s, a half-texel "
                    "offset of 0.027 M at samples = 512 over rMin..rMax = "
                    "2.32..30 M; on the steep inner rise that reaches 0.048 in "
                    "normalized flux. Reconciling the shader is Task 9-10 work "
                    "and is not owned by this producer"
                ),
                "addressing": "clamp",
                "filtering": "bilinear",
            },
            "channels": {
                "r": "normalized Page-Thorne flux shape F(r) / max(F)",
                "g": "normalized effective-temperature shape [F(r) / max(F)]^(1/4)",
                "b": "reserved = 0",
                "a": "valid sample = 1",
            },
            "unityUse": "T_obs = g * temperatureScaleK * channel_g; brightness = channel_r * g^4",
        }
        meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf8")
        summary["metadata_path"] = str(meta_path)
    return summary


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
