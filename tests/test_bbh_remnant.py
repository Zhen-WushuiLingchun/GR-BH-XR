import numpy as np

from gr_bh_xr.metric_ks import MINKOWSKI_COVARIANT
from gr_bh_xr.metrics import (
    BinaryHoleState,
    MergerRemnantTrajectory,
    QuasiCircularInspiralOrbit,
    SuperposedKerrSchildBBHProvider,
    boosted_kerr_ks_perturbation,
    smooth_transition_weight,
)
from gr_bh_xr.validate_bbh_remnant import run_validation


def _trajectory() -> MergerRemnantTrajectory:
    return MergerRemnantTrajectory(
        inspiral=QuasiCircularInspiralOrbit(
            initial_separation=12.0,
            minimum_separation=5.0,
            dimensionless_spin1=(0.0, 0.0, 0.2),
            dimensionless_spin2=(0.0, 0.0, -0.1),
        ),
        transition_start=100.0,
        transition_duration=20.0,
        remnant_mass=0.95,
        remnant_spin=(0.0, 0.0, 0.65),
    )


def test_appendix_b_weight_has_exact_endpoints_and_midpoint_symmetry() -> None:
    assert smooth_transition_weight(-0.2) == 0.0
    assert smooth_transition_weight(0.0) == 0.0
    assert smooth_transition_weight(0.5) == 0.5
    assert smooth_transition_weight(1.0) == 1.0
    assert smooth_transition_weight(1.2) == 1.0
    for value in (0.1, 0.25, 0.7):
        assert abs(smooth_transition_weight(value) + smooth_transition_weight(1-value) - 1.0) < 2e-15


def test_remnant_trajectory_is_continuous_through_transition_boundaries() -> None:
    trajectory = _trajectory()
    epsilon = 1.0e-5
    for boundary in (trajectory.transition_start, trajectory.transition_end):
        left = trajectory.states(boundary - epsilon)[0]
        right = trajectory.states(boundary + epsilon)[0]
        np.testing.assert_allclose(left.position, right.position, atol=2.0e-5)
        np.testing.assert_allclose(left.velocity, right.velocity, atol=2.0e-5)


def test_post_transition_two_terms_equal_one_physical_kerr_remnant() -> None:
    trajectory = _trajectory()
    provider = SuperposedKerrSchildBBHProvider(trajectory)
    t = trajectory.transition_end + 3.0
    point = np.array([2.3, -1.7, 0.8])
    actual = provider.covariant_metric(t, point)
    position = np.asarray(trajectory.remnant_position_at_end)
    full_hole = BinaryHoleState(
        trajectory.remnant_mass,
        position,
        np.asarray(trajectory.remnant_velocity),
        np.zeros(3),
        np.asarray(trajectory.remnant_spin),
    )
    expected_term, _ = boosted_kerr_ks_perturbation(
        np.concatenate([[t], point]), full_hole
    )
    np.testing.assert_allclose(
        actual, MINKOWSKI_COVARIANT + expected_term, atol=3.0e-15
    )


def test_remnant_validation_smoke_passes() -> None:
    result = run_validation()
    assert result["pass"] is True
    assert result["evidence_label"] == "physics_approximation"
