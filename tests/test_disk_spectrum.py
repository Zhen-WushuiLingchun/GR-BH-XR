import math

import pytest

from gr_bh_xr.disk import isco_radius
from gr_bh_xr.disk_spectrum import (
    blackbody_linear_srgb,
    blackbody_xyz,
    circular_orbit_energy_lz,
    effective_temperature_shape,
    page_thorne_flux_shape,
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


def test_blackbody_cie_chromaticity_anchors() -> None:
    d65_like = blackbody_xyz(6504.0)
    assert d65_like[0] == pytest.approx(0.313, abs=0.015)
    assert d65_like[1] == pytest.approx(0.329, abs=0.015)

    warm = blackbody_linear_srgb(3000.0)
    hot = blackbody_linear_srgb(10000.0)
    assert warm[0] > warm[2]
    assert hot[2] == pytest.approx(1.0, abs=1.0e-12)
    assert hot[2] > hot[0]
