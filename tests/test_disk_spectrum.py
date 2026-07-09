import math

import numpy as np
import pytest

from gr_bh_xr.disk import isco_radius
from gr_bh_xr.disk_spectrum import (
    blackbody_linear_srgb,
    blackbody_lut,
    blackbody_xyz,
    circular_orbit_energy_lz,
    effective_temperature_shape,
    intensity_redshift_weight,
    observed_temperature,
    page_thorne_flux_shape,
    page_thorne_flux_shape_closed_form,
    write_blackbody_lut_npz,
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
