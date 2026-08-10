import math

import numpy as np

from gr_bh_xr.dynamic_metric import finite_difference_inverse_metric_derivatives
from gr_bh_xr.metric_ks import MINKOWSKI_COVARIANT, ks_metric
from gr_bh_xr.metrics import (
    BinaryHoleState,
    FixedCircularBinaryOrbit,
    SuperposedKerrSchildBBHProvider,
    boosted_kerr_ks_perturbation,
    boosted_schwarzschild_ks_perturbation,
    lorentz_boost_covector_jacobian,
)
from gr_bh_xr.types import MetricParams


def test_fixed_circular_orbit_center_of_mass_and_half_period_exchange() -> None:
    orbit = FixedCircularBinaryOrbit(total_mass=1.0, separation=20.0, phase0=0.2)
    first, second = orbit.states(1.3)
    later_first, later_second = orbit.states(1.3 + 0.5 * orbit.period)
    np.testing.assert_allclose(first.position + second.position, 0.0, atol=1e-15)
    np.testing.assert_allclose(first.velocity + second.velocity, 0.0, atol=1e-15)
    np.testing.assert_allclose(later_first.position, second.position, atol=2e-14)
    np.testing.assert_allclose(later_second.velocity, first.velocity, atol=2e-14)


def test_zero_velocity_boost_is_identity_and_single_term_is_schwarzschild_ks() -> None:
    velocity = np.zeros(3)
    np.testing.assert_array_equal(lorentz_boost_covector_jacobian(velocity), np.eye(4))
    hole = BinaryHoleState(0.5, np.zeros(3), velocity, np.zeros(3))
    event = np.array([0.0, 3.0, 4.0, 0.0])
    perturbation, radius = boosted_schwarzschild_ks_perturbation(event, hole)
    assert radius == 5.0
    expected_l = np.array([1.0, 0.6, 0.8, 0.0])
    np.testing.assert_allclose(
        perturbation, 2.0 * hole.mass / radius * np.outer(expected_l, expected_l)
    )


def test_z_aligned_single_kerr_term_matches_existing_ks_metric() -> None:
    mass = 0.7
    spin = 0.4
    hole = BinaryHoleState(
        mass,
        np.zeros(3),
        np.zeros(3),
        np.zeros(3),
        np.array([0.0, 0.0, spin]),
    )
    xyz = np.array([2.3, -1.7, 0.8])
    perturbation, _radius = boosted_kerr_ks_perturbation(
        np.concatenate([[0.0], xyz]), hole
    )
    expected = ks_metric(MetricParams(M=mass, a=spin), xyz)
    np.testing.assert_allclose(
        MINKOWSKI_COVARIANT + perturbation, expected, atol=3.0e-15
    )


def test_arbitrary_spin_kerr_term_is_rotation_covariant() -> None:
    rotation = np.array(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    position = np.array([2.7, -1.3, 0.9])
    spin = np.array([0.12, -0.18, 0.31])
    hole = BinaryHoleState(0.8, np.zeros(3), np.zeros(3), np.zeros(3), spin)
    rotated_hole = BinaryHoleState(
        0.8, np.zeros(3), np.zeros(3), np.zeros(3), rotation @ spin
    )
    perturbation, _ = boosted_kerr_ks_perturbation(
        np.concatenate([[0.0], position]), hole
    )
    rotated, _ = boosted_kerr_ks_perturbation(
        np.concatenate([[0.0], rotation @ position]), rotated_hole
    )
    transform = np.eye(4)
    transform[1:4, 1:4] = rotation
    np.testing.assert_allclose(
        rotated, transform @ perturbation @ transform.T, atol=3.0e-15
    )


def test_spinning_binary_provider_reports_spin_revision_and_null_ks_terms() -> None:
    orbit = FixedCircularBinaryOrbit(
        separation=20.0,
        dimensionless_spin1=(0.0, 0.0, 0.6),
        dimensionless_spin2=(0.2, -0.1, 0.3),
    )
    provider = SuperposedKerrSchildBBHProvider(orbit)
    sample = provider.sample(0.4, np.array([2.0, 5.0, 1.0]))
    assert sample.source_revision.endswith("spinning-circular-v1")
    event = np.array([0.4, 2.0, 5.0, 1.0])
    for hole in provider.hole_states(0.4):
        perturbation, _ = boosted_kerr_ks_perturbation(event, hole)
        eigenvalues, eigenvectors = np.linalg.eigh(perturbation)
        direction = eigenvectors[:, int(np.argmax(np.abs(eigenvalues)))]
        assert abs(float(direction @ MINKOWSKI_COVARIANT @ direction)) < 3.0e-15


def test_binary_orbit_rejects_superextremal_dimensionless_spin() -> None:
    with np.testing.assert_raises_regex(ValueError, "chi"):
        FixedCircularBinaryOrbit(dimensionless_spin1=(0.0, 0.0, 1.01))


def test_boosted_ks_covector_remains_null_on_flat_background() -> None:
    hole = BinaryHoleState(
        0.5,
        np.array([1.0, -2.0, 0.5]),
        np.array([0.08, 0.11, -0.03]),
        np.zeros(3),
    )
    event = np.array([0.4, 4.0, 3.0, 2.0])
    perturbation, _radius = boosted_schwarzschild_ks_perturbation(event, hole)
    eigenvalues, eigenvectors = np.linalg.eigh(perturbation)
    l_direction = eigenvectors[:, int(np.argmax(eigenvalues))]
    minkowski_inverse = MINKOWSKI_COVARIANT
    assert abs(float(l_direction @ minkowski_inverse @ l_direction)) < 2.0e-15


def test_superposed_metric_inverse_and_evidence_contract() -> None:
    provider = SuperposedKerrSchildBBHProvider()
    sample = provider.sample(2.0, np.array([1.5, 4.0, 2.0]))
    np.testing.assert_allclose(sample.g_cov @ sample.g_inv, np.eye(4), atol=3e-15)
    assert sample.evidence_label == "physics_approximation"
    assert sample.validity == "valid"
    assert sample.source_revision.endswith("equal-mass-v1")


def test_complex_step_derivatives_match_independent_finite_difference() -> None:
    provider = SuperposedKerrSchildBBHProvider()
    t = 3.4
    point = np.array([2.0, 5.0, 1.7])
    analytic = provider.sample(t, point).d_g_inv
    finite = finite_difference_inverse_metric_derivatives(
        provider, t, point, relative_step=2.0e-5
    )
    assert np.max(np.abs(analytic - finite)) < 2.0e-8
    assert np.max(np.abs(analytic[0])) > 1.0e-7


def test_equal_mass_exchange_symmetry_is_exact() -> None:
    provider = SuperposedKerrSchildBBHProvider()
    t = 0.37 * provider.orbit.period
    point = np.array([3.0, -5.0, 1.2])
    half_period = t + 0.5 * provider.orbit.period
    metric = provider.covariant_metric(t, point)
    exchanged = provider.covariant_metric(half_period, -point)
    parity = np.diag([1.0, -1.0, -1.0, -1.0])
    np.testing.assert_allclose(exchanged, parity @ metric @ parity, atol=3e-14)


def test_companion_perturbation_decays_in_large_separation_limit() -> None:
    offsets = np.array([0.0, 0.0, 2.0])
    norms = []
    for separation in (40.0, 80.0, 160.0):
        orbit = FixedCircularBinaryOrbit(separation=separation)
        provider = SuperposedKerrSchildBBHProvider(orbit)
        holes = provider.hole_states(0.0)
        point = holes[0].position + offsets
        event = np.concatenate([[0.0], point])
        companion, _ = boosted_schwarzschild_ks_perturbation(event, holes[1])
        norms.append(np.linalg.norm(companion))
        full = provider.covariant_metric(0.0, point)
        primary, _ = boosted_schwarzschild_ks_perturbation(event, holes[0])
        np.testing.assert_allclose(full - (MINKOWSKI_COVARIANT + primary), companion)
    ratios = np.asarray(norms[:-1]) / np.asarray(norms[1:])
    assert np.all((ratios > 1.8) & (ratios < 2.2))


def test_worldtube_is_explicit_provider_domain_not_event_horizon_claim() -> None:
    provider = SuperposedKerrSchildBBHProvider()
    first, _second = provider.hole_states(0.0)
    sample = provider.sample(0.0, first.position + np.array([0.5, 0.0, 0.0]))
    assert sample.validity == "outside_domain"
    assert math.isfinite(sample.lapse)
