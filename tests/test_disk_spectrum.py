import math
import json

import numpy as np
import pytest

from gr_bh_xr.disk import isco_radius
from gr_bh_xr.disk_spectrum import (
    blackbody_linear_srgb,
    blackbody_locus_inverse,
    blackbody_lut,
    blackbody_xyz,
    circular_orbit_energy_lz,
    effective_temperature_shape,
    intensity_redshift_weight,
    observed_temperature,
    page_thorne_flux_shape,
    page_thorne_flux_shape_closed_form,
    page_thorne_radial_lut,
    planck_locus_rb_coordinate,
    write_blackbody_lut_npz,
    write_blackbody_lut_unity_raw,
    write_page_thorne_radial_lut_unity_raw,
)
from gr_bh_xr.types import MetricParams


def test_schwarzschild_circular_orbit_energy_and_lz_at_isco() -> None:
    params = MetricParams(M=1.0, a=0.0)

    energy, lz = circular_orbit_energy_lz(params, 6.0)

    assert energy == pytest.approx(math.sqrt(8.0 / 9.0), abs=1.0e-14)
    assert lz == pytest.approx(math.sqrt(12.0), abs=1.0e-14)


def test_page_thorne_flux_has_zero_torque_inner_edge() -> None:
    params = MetricParams(M=1.0, a=0.0)
    r_isco = isco_radius(params)

    assert page_thorne_flux_shape(params, r_isco) == 0.0
    assert page_thorne_flux_shape(params, r_isco + 0.1) > 0.0
    assert page_thorne_flux_shape(params, 10.0) > 0.0


def test_page_thorne_flux_is_positive_for_kerr_outside_isco() -> None:
    params = MetricParams(M=1.0, a=0.9)
    r_isco = isco_radius(params)

    assert page_thorne_flux_shape(params, r_isco) == 0.0
    assert page_thorne_flux_shape(params, 3.0) > 0.0
    assert effective_temperature_shape(page_thorne_flux_shape(params, 3.0)) > 0.0


def test_page_thorne_closed_form_matches_integral_gate() -> None:
    params = MetricParams(M=1.0, a=0.9)
    r_isco = isco_radius(params)

    for radius in [r_isco + 0.1, 3.0, 5.0, 10.0, 20.0]:
        integral = page_thorne_flux_shape(params, radius, integration_samples=4096)
        closed = page_thorne_flux_shape_closed_form(params, radius)
        assert integral == pytest.approx(closed, rel=3.0e-6, abs=1.0e-12)


def test_page_thorne_closed_form_keeps_mass_scaling() -> None:
    base = MetricParams(M=1.0, a=0.9)
    scaled = MetricParams(M=2.0, a=1.8)

    for radius_over_m in [3.0, 5.0, 10.0, 20.0]:
        base_closed = page_thorne_flux_shape_closed_form(base, radius_over_m)
        scaled_integral = page_thorne_flux_shape(scaled, 2.0 * radius_over_m, integration_samples=4096)
        scaled_closed = page_thorne_flux_shape_closed_form(scaled, 2.0 * radius_over_m)
        assert scaled_integral == pytest.approx(scaled_closed, rel=3.0e-6, abs=1.0e-12)
        assert scaled_closed == pytest.approx(base_closed / 4.0, rel=2.0e-15)


def test_near_extremal_isco_efficiency_anchor() -> None:
    params = MetricParams(M=1.0, a=0.998)
    energy_isco, _ = circular_orbit_energy_lz(params, isco_radius(params))

    assert 1.0 - energy_isco == pytest.approx(0.320994, rel=1.0e-5)


def test_blackbody_cie_chromaticity_anchors() -> None:
    d65_like = blackbody_xyz(6504.0)
    assert d65_like[0] == pytest.approx(0.313, abs=0.015)
    assert d65_like[1] == pytest.approx(0.329, abs=0.015)

    warm = blackbody_linear_srgb(3000.0)
    hot = blackbody_linear_srgb(10000.0)
    assert warm[0] > warm[2]
    assert hot[2] == pytest.approx(1.0, abs=1.0e-12)
    assert hot[2] > hot[0]


def test_redshift_temperature_and_intensity_weights() -> None:
    assert observed_temperature(6000.0, 0.5) == pytest.approx(3000.0)
    assert intensity_redshift_weight(0.5, bolometric=False) == pytest.approx(0.125)
    assert intensity_redshift_weight(0.5, bolometric=True) == pytest.approx(0.0625)


def test_blackbody_lut_and_npz_writer(tmp_path) -> None:
    temperatures, xyz, rgb = blackbody_lut(temperature_min_k=1000.0, temperature_max_k=10000.0, samples=8)

    assert temperatures.shape == (8,)
    assert xyz.shape == (8, 3)
    assert rgb.shape == (8, 3)
    assert np.all(np.diff(temperatures) > 0.0)
    assert np.all(np.isfinite(rgb))
    assert rgb[0, 0] > rgb[0, 2]
    assert rgb[-1, 2] >= rgb[-1, 0]

    out = tmp_path / "disk_color_lut.npz"
    summary = write_blackbody_lut_npz(out, temperature_min_k=1000.0, temperature_max_k=10000.0, samples=8)
    loaded = np.load(out)
    assert summary["samples"] == 8
    assert loaded["linear_srgb"].shape == (8, 3)


def test_unity_blackbody_lut_raw_writer(tmp_path) -> None:
    raw = tmp_path / "disk_color_lut_rgba32f.bytes"
    meta = tmp_path / "disk_color_lut_metadata.json"

    summary = write_blackbody_lut_unity_raw(
        raw,
        metadata_out=meta,
        temperature_min_k=1000.0,
        temperature_max_k=40000.0,
        samples=16,
    )
    rgba = np.frombuffer(raw.read_bytes(), dtype=np.float32).reshape(16, 4)
    metadata = json.loads(meta.read_text(encoding="utf8"))

    assert summary["bytes"] == 16 * 4 * 4
    assert metadata["schema"] == "gr-bh-xr.task6.disk_color_lut.v2"
    assert metadata["temperatureSpacing"] == "log"
    assert metadata["alphaChannel"] == "planck-locus-inverse"
    assert rgba[0, 0] > rgba[0, 2]
    assert rgba[-1, 2] == pytest.approx(1.0, abs=1.0e-6)
    # Alpha is the inverse Planck locus: high u = red chromaticity = low
    # temperature, so it decreases with u and stays in [0, 1].
    assert np.all((rgba[:, 3] >= 0.0) & (rgba[:, 3] <= 1.0))
    assert np.all(np.diff(rgba[:, 3]) <= 0.0)
    assert rgba[0, 3] > rgba[-1, 3]


def test_planck_locus_rb_coordinate_decreases_with_temperature() -> None:
    """`u = R/(R+B)` must be a usable one-parameter handle on the locus."""

    _, _, rgb = blackbody_lut(temperature_min_k=1000.0, temperature_max_k=40000.0, samples=256)
    u = planck_locus_rb_coordinate(rgb)

    assert np.all((u >= 0.0) & (u <= 1.0))
    assert u[0] == pytest.approx(1.0, abs=1.0e-12)  # sub-2000 K plateau: blue clipped to 0
    assert u[-1] < u[0]
    # Monotone only after plateau removal; the plateau itself is the reason
    # the raw coordinate cannot be inverted directly.
    assert not np.all(np.diff(u) < 0.0)

    inverse, dropped, first_kept = blackbody_locus_inverse(rgb, 256)
    assert dropped > 0
    assert first_kept == dropped  # the dropped rows are the leading plateau
    assert inverse.shape == (256,)
    assert np.all((inverse >= 0.0) & (inverse <= 1.0))
    assert np.all(np.diff(inverse) <= 0.0)
    # The plateau is exactly the region where the clipped blue channel is zero.
    assert rgb[first_kept - 1, 2] == 0.0
    assert rgb[first_kept + 1, 2] > 0.0


def test_blackbody_locus_inverse_rejects_bad_input() -> None:
    _, _, rgb = blackbody_lut(temperature_min_k=1000.0, temperature_max_k=40000.0, samples=32)

    with pytest.raises(ValueError):
        blackbody_locus_inverse(rgb[:, :2], 32)
    with pytest.raises(ValueError):
        blackbody_locus_inverse(rgb, 1)
    with pytest.raises(ValueError, match="at least two rows above"):
        blackbody_locus_inverse(np.ones((8, 3), dtype=np.float64), 8)


def test_blackbody_lut_writer_fails_closed_on_all_plateau_range(tmp_path) -> None:
    """A range entirely below the blue-clip point cannot be inverted at all.

    Without the guard this emitted a silently constant alpha channel, and the
    range is reachable from the CLI's --temperature-max-k flag.
    """

    with pytest.raises(ValueError, match="at least two rows above"):
        write_blackbody_lut_unity_raw(
            tmp_path / "bad.bytes",
            temperature_min_k=1000.0,
            temperature_max_k=1800.0,
            samples=32,
        )


def _lut_round_trip(rgba: np.ndarray, temperature_k: float, t_min: float, t_max: float) -> float:
    """Chromaticity -> alpha -> temperature through an emulated texture fetch.

    Mirrors the consumer's `tex2D(lut, float2(u, 0.5)).a` with bilinear
    filtering and clamp addressing, which is how the raw LUT is imported.
    """

    samples = rgba.shape[0]
    red, _, blue = blackbody_linear_srgb(temperature_k)
    u = red / (red + blue)
    position = float(np.clip(u * samples - 0.5, 0.0, samples - 1.0))
    low = int(np.floor(position))
    high = min(low + 1, samples - 1)
    frac = position - low
    t_norm = (1.0 - frac) * rgba[low, 3] + frac * rgba[high, 3]
    return float(np.exp(np.log(t_min) + t_norm * (np.log(t_max) - np.log(t_min))))


def test_blackbody_lut_alpha_inverse_round_trip(tmp_path) -> None:
    """Chromaticity -> alpha lookup must recover the emitting temperature."""

    samples = 256
    t_min, t_max = 1000.0, 40000.0
    raw = tmp_path / "lut.bytes"
    write_blackbody_lut_unity_raw(
        raw, temperature_min_k=t_min, temperature_max_k=t_max, samples=samples
    )
    rgba = np.frombuffer(raw.read_bytes(), dtype=np.float32).reshape(samples, 4)

    worst = 0.0
    for temperature in (2500.0, 4000.0, 6500.0, 12000.0, 25000.0):
        recovered = _lut_round_trip(rgba, temperature, t_min, t_max)
        worst = max(worst, abs(recovered - temperature) / temperature)
        assert recovered == pytest.approx(temperature, rel=0.03)
    # Deterministic float64 math into float32 storage, so this is a real
    # regression bound rather than a loose sanity gate. Measured worst case on
    # this five-point set is 2.53e-4; the gate keeps ~4x headroom.
    assert worst < 1.0e-3


def test_blackbody_lut_alpha_inverse_boundary_behaviour(tmp_path) -> None:
    """The two error maxima and the cold saturation sit outside the mid-range.

    The round-trip test above probes the flat middle. Accuracy is worst just
    above the chromaticity plateau and at the hot end, where `du/dlnT` is 17x
    smaller than at its peak, so both ends are pinned here.
    """

    samples = 256
    t_min, t_max = 1000.0, 40000.0
    raw = tmp_path / "lut.bytes"
    summary = write_blackbody_lut_unity_raw(
        raw, temperature_min_k=t_min, temperature_max_k=t_max, samples=samples
    )
    rgba = np.frombuffer(raw.read_bytes(), dtype=np.float32).reshape(samples, 4)

    # Hot end: the locus flattens, so the tolerance is looser than mid-range.
    assert _lut_round_trip(rgba, t_max, t_min, t_max) == pytest.approx(t_max, rel=0.01)

    # Cold end saturates by design: below the blue-clip point chromaticity
    # carries no temperature information, so distinct cold temperatures are
    # indistinguishable and both map to the same saturated value.
    cold = _lut_round_trip(rgba, 1000.0, t_min, t_max)
    assert cold == _lut_round_trip(rgba, 1500.0, t_min, t_max)
    assert cold > 1.5 * t_min
    # The fetched saturation is NOT the anchor row itself: the top texel centre
    # sits inside the interpolation range, so it overshoots the anchor by about
    # 1.6 LUT texels (measured 1933.06 K against an anchor of 1889.88 K at
    # samples = 256). The "hottest temperature consistent with the
    # chromaticity" statement therefore holds only to the LUT's temperature
    # resolution, and this bound pins that.
    anchor = float(summary["alpha_anchor_temperature_k"])
    texel_ratio = (t_max / t_min) ** (1.0 / (samples - 1))
    assert anchor < cold < anchor * texel_ratio**2
    assert anchor > t_min


def test_disk_color_lut_metadata_is_dimensionally_explicit(tmp_path) -> None:
    raw = tmp_path / "disk_color_lut_rgba32f.bytes"
    meta = tmp_path / "disk_color_lut_metadata.json"
    write_blackbody_lut_unity_raw(raw, metadata_out=meta, samples=32)
    metadata = json.loads(meta.read_text(encoding="utf8"))

    units = metadata["units"]
    assert units["temperatureMinK"] == "K"
    assert units["temperatureMaxK"] == "K"
    assert units["samples"].startswith("count")
    assert "dimensionless" in units["rgbChannels"]
    assert "dimensionless" in units["alphaChannel"]
    assert "dimensionless" in units["lookupCoordinate"]
    assert units["alphaAnchorTemperatureK"].startswith("K;")
    assert "saturates" in units["alphaAnchorTemperatureK"]
    sampling = metadata["sampling"]
    assert "samples - 1" in sampling["rgbCoordinateExact"]
    assert "R / (R + B)" in sampling["alphaCoordinate"]
    assert "temperatureMinK" in sampling["alphaInverse"]
    assert sampling["addressing"] == "clamp"
    assert sampling["filtering"] == "bilinear"
    # The half-texel mismatch with the current Unity sampler is recorded, not
    # asserted away: this producer does not own the shader.
    assert "u = s" in sampling["rgbCoordinateConsumerNote"]
    assert metadata["plateauRowsDropped"] >= 0
    assert metadata["alphaAnchorTemperatureK"] > metadata["temperatureMinK"]


def test_color_lut_exact_row_coordinate_is_the_producer_contract(tmp_path) -> None:
    """The documented exact coordinate must actually return its own row.

    This is the producer-side half of the contract. The consumer-side half
    (the Unity shader currently sampling with `u = s`) is recorded in the
    metadata note and is owned by the Unity worktree.
    """

    samples = 64
    t_min, t_max = 1000.0, 40000.0
    raw = tmp_path / "lut.bytes"
    write_blackbody_lut_unity_raw(
        raw, temperature_min_k=t_min, temperature_max_k=t_max, samples=samples
    )
    rgba = np.frombuffer(raw.read_bytes(), dtype=np.float32).reshape(samples, 4)

    def fetch_rgb(u: float) -> np.ndarray:
        position = float(np.clip(u * samples - 0.5, 0.0, samples - 1.0))
        low = int(np.floor(position))
        high = min(low + 1, samples - 1)
        frac = position - low
        return (1.0 - frac) * rgba[low, :3] + frac * rgba[high, :3]

    for index in (0, 1, samples // 2, samples - 1):
        s = index / (samples - 1)
        u_exact = (s * (samples - 1) + 0.5) / samples
        np.testing.assert_allclose(fetch_rgb(u_exact), rgba[index, :3], atol=1.0e-6)


def test_page_thorne_radial_lut_and_unity_writer(tmp_path) -> None:
    params = MetricParams(M=1.0, a=0.9)
    radii, flux, temperature, peak, inner = page_thorne_radial_lut(
        params,
        r_max=30.0,
        samples=64,
    )

    assert radii[0] == pytest.approx(isco_radius(params), abs=1.0e-12)
    assert inner == pytest.approx(radii[0], abs=1.0e-12)
    assert peak > 0.0
    assert flux[0] == 0.0
    assert np.max(flux) == pytest.approx(1.0, abs=1.0e-12)
    positive = flux > 0.0
    assert np.allclose(temperature[positive] ** 4, flux[positive], rtol=1.0e-12, atol=1.0e-12)

    raw = tmp_path / "disk_radial_lut_rgba32f.bytes"
    meta = tmp_path / "disk_radial_lut_metadata.json"
    summary = write_page_thorne_radial_lut_unity_raw(
        raw,
        metadata_out=meta,
        params=params,
        r_max=30.0,
        samples=64,
        temperature_scale_k=7000.0,
    )
    rgba = np.frombuffer(raw.read_bytes(), dtype=np.float32).reshape(64, 4)
    metadata = json.loads(meta.read_text(encoding="utf8"))

    assert summary["bytes"] == 64 * 4 * 4
    assert metadata["schema"] == "gr-bh-xr.task6.disk_radial_lut.v1"
    assert metadata["radiusSpacing"] == "linear"
    assert metadata["temperatureScaleK"] == 7000.0
    assert rgba[:, 0].max() == pytest.approx(1.0, abs=1.0e-6)
    assert rgba[0, 0] == 0.0
    assert np.all(rgba[:, 3] == 1.0)


def test_page_thorne_radial_lut_metadata_is_dimensionally_explicit(tmp_path) -> None:
    """The radial LUT is a dimensionless shape; the metadata must say so."""

    params = MetricParams(M=1.0, a=0.9)
    raw = tmp_path / "disk_radial_lut_rgba32f.bytes"
    meta = tmp_path / "disk_radial_lut_metadata.json"
    write_page_thorne_radial_lut_unity_raw(
        raw, metadata_out=meta, params=params, r_max=30.0, samples=32
    )
    metadata = json.loads(meta.read_text(encoding="utf8"))

    units = metadata["units"]
    assert "G = c = 1" in units["system"]
    for key in ("rMin", "rMax", "rISCO"):
        assert "geometric length" in units[key]
    assert units["temperatureScaleK"].startswith("K;")
    # The texture CHANNELS are dimensionless ratios; the peak normalization is
    # not. Saying otherwise would contradict the M^-2 scaling gate below.
    assert "dimensionless" in units["channelR"]
    assert "dimensionless" in units["channelG"]
    assert "length^-2" in units["fluxPeakShape"]
    assert "M^-2" in units["fluxPeakShape"]
    assert "not W/m^2" in units["fluxPeakShape"]
    assert "NOT dimensionless" in units["fluxPeakShape"]
    # `a` is a length, not the dimensionless spin; both must be published.
    assert "NOT the dimensionless spin" in units["a"]
    assert metadata["aOverM"] == pytest.approx(0.9)
    assert metadata["rIscoOverM"] == pytest.approx(metadata["rISCO"] / metadata["M"])
    sampling = metadata["sampling"]
    assert "samples - 1" in sampling["radiusCoordinateExact"]
    assert "u = s" in sampling["radiusCoordinateConsumerNote"]
    assert sampling["addressing"] == "clamp"


def test_page_thorne_flux_peak_shape_scales_as_inverse_mass_squared(tmp_path) -> None:
    """`fluxPeakShape` carries geometric dimension length^-2, so it is not dimensionless.

    The omitted `Mdot / (4 pi)` factor is itself dimensionless in `G = c = 1`,
    so dropping it cannot remove the `length^-2` dimension. This mirrors the
    closed-form `M^-2` gate in
    `test_page_thorne_closed_form_keeps_mass_scaling` and exists so the asset
    metadata cannot drift back to claiming the peak is dimensionless.
    """

    base = write_page_thorne_radial_lut_unity_raw(
        tmp_path / "m1.bytes",
        metadata_out=tmp_path / "m1.json",
        params=MetricParams(M=1.0, a=0.9),
        r_max=30.0,
        samples=128,
    )
    scaled = write_page_thorne_radial_lut_unity_raw(
        tmp_path / "m2.bytes",
        metadata_out=tmp_path / "m2.json",
        params=MetricParams(M=2.0, a=1.8),
        r_max=60.0,
        samples=128,
    )

    assert scaled["flux_peak_shape"] == pytest.approx(base["flux_peak_shape"] / 4.0, rel=1.0e-12)

    base_meta = json.loads((tmp_path / "m1.json").read_text(encoding="utf8"))
    scaled_meta = json.loads((tmp_path / "m2.json").read_text(encoding="utf8"))
    # Radii are code lengths, so they double with M rather than staying at r/M.
    assert scaled_meta["rISCO"] == pytest.approx(2.0 * base_meta["rISCO"], rel=1.0e-12)
    assert scaled_meta["rMax"] == pytest.approx(60.0)
    assert scaled_meta["aOverM"] == pytest.approx(base_meta["aOverM"], rel=1.0e-12)
    assert scaled_meta["rIscoOverM"] == pytest.approx(base_meta["rIscoOverM"], rel=1.0e-12)
