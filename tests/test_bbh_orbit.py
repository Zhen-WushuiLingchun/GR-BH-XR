import math

import numpy as np
import pytest

from gr_bh_xr.metrics import (
    QuasiCircularInspiralOrbit,
    SuperposedKerrSchildBBHProvider,
)
from gr_bh_xr.validate_bbh_orbit import run_validation


def test_inspiral_mass_convention_and_center_of_mass() -> None:
    orbit = QuasiCircularInspiralOrbit(total_mass=3.0, mass_ratio=0.5)
    assert orbit.masses == pytest.approx((1.0, 2.0))
    assert orbit.symmetric_mass_ratio == pytest.approx(2.0 / 9.0)
    first, second = orbit.states(10.0)
    np.testing.assert_allclose(
        first.mass * first.position + second.mass * second.position, 0.0, atol=2e-15
    )
    np.testing.assert_allclose(
        first.mass * first.velocity + second.mass * second.velocity, 0.0, atol=2e-15
    )


def test_inspiral_separation_obeys_quadrupole_flux_law() -> None:
    orbit = QuasiCircularInspiralOrbit(initial_separation=20.0, mass_ratio=0.7)
    t = 50.0
    step = 1.0e-3
    numerical_rate = (
        orbit.separation_at(t + step) - orbit.separation_at(t - step)
    ) / (2.0 * step)
    separation = orbit.separation_at(t)
    expected = -orbit.radiation_reaction_coefficient / separation**3
    assert numerical_rate == pytest.approx(expected, rel=2e-8)


def test_inspiral_phase_derivative_is_keplerian() -> None:
    orbit = QuasiCircularInspiralOrbit(initial_separation=20.0)
    t = 100.0
    step = 1.0e-3
    numerical_omega = (orbit.phase_at(t + step) - orbit.phase_at(t - step)) / (
        2.0 * step
    )
    expected = math.sqrt(orbit.total_mass / orbit.separation_at(t) ** 3)
    assert numerical_omega == pytest.approx(expected, rel=2e-8)


def test_inspiral_fails_closed_at_minimum_separation() -> None:
    orbit = QuasiCircularInspiralOrbit(initial_separation=12.0, minimum_separation=6.0)
    assert orbit.separation_at(orbit.valid_until - 1.0e-6) > orbit.minimum_separation
    with pytest.raises(ValueError, match="validity domain"):
        orbit.separation_at(orbit.valid_until)


def test_inspiral_provider_has_nonzero_time_derivative_and_approximation_label() -> None:
    orbit = QuasiCircularInspiralOrbit(initial_separation=20.0, mass_ratio=0.8)
    provider = SuperposedKerrSchildBBHProvider(orbit=orbit)
    sample = provider.sample(40.0, np.array([2.0, 5.0, 1.0]))
    assert sample.evidence_label == "physics_approximation"
    assert sample.source_revision.endswith("quadrupole-inspiral-v1")
    assert np.max(np.abs(sample.d_g_inv[0])) > 1.0e-7
    np.testing.assert_allclose(sample.g_cov @ sample.g_inv, np.eye(4), atol=4e-15)


def test_inspiral_validation_smoke_passes() -> None:
    result = run_validation()
    assert result["pass"] is True
    assert result["evidence_label"] == "physics_approximation"
    assert result["scope"].endswith("not full 4PN")
