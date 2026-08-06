import numpy as np

from gr_bh_xr.geodesic_ks import bl_state_to_ks_state
from gr_bh_xr.metric import carter_constant
from gr_bh_xr.metric_ks import ks_inverse_metric
from gr_bh_xr.types import MetricParams, RayState
from gr_bh_xr.validate_npgs_kerr import (
    NpgsKerrThresholds,
    NPGS_TO_PYTHON_SPATIAL,
    _event_boundary_mask,
    _sample_indices,
    native_initial_state_to_python_ks,
    python_direction_to_npgs,
    python_ks_invariants,
    python_ks_momentum_direction_to_npgs,
)


def test_native_state_rotation_and_affine_reversal_are_exact() -> None:
    x_native = np.array([2.0, 3.0, 5.0, 7.0])
    p_native = np.array([11.0, 13.0, 17.0, -19.0])

    state = native_initial_state_to_python_ks(x_native, p_native)

    np.testing.assert_allclose(state.x, [7.0, 2.0, -5.0, 3.0])
    np.testing.assert_allclose(state.p, [19.0, -11.0, 17.0, -13.0])
    np.testing.assert_allclose(
        python_direction_to_npgs(NPGS_TO_PYTHON_SPATIAL @ [0.2, -0.3, 0.9]),
        [0.2, -0.3, 0.9],
    )
    assert np.linalg.det(NPGS_TO_PYTHON_SPATIAL) == 1.0


def test_event_boundary_mask_expands_around_capture_escape_transition() -> None:
    events = np.ones((5, 5), dtype=np.int8)
    events[2, 2] = 0

    boundary = _event_boundary_mask(events, radius=1)

    assert boundary[2, 2]
    assert boundary[0, 0] == 0
    assert np.count_nonzero(boundary) == 13


def test_ks_momentum_direction_uses_raised_cartesian_momentum() -> None:
    params = MetricParams(M=0.5, a=0.45)
    x = np.array([0.0, 12.0, -3.0, 8.0])
    p_cov = np.array([-1.0, 0.2, -0.4, 0.8])

    p_contra = ks_inverse_metric(params, x[1:4]) @ p_cov
    expected_python = p_contra[1:4] / np.linalg.norm(p_contra[1:4])
    expected_native = NPGS_TO_PYTHON_SPATIAL.T @ expected_python

    np.testing.assert_allclose(
        python_ks_momentum_direction_to_npgs(params, x, p_cov),
        expected_native,
        rtol=0.0,
        atol=1.0e-15,
    )
    np.testing.assert_allclose(np.linalg.norm(expected_native), 1.0, atol=1.0e-15)


def test_ks_invariants_match_boyer_lindquist_carter_definition() -> None:
    params = MetricParams(M=1.0, a=0.7)
    state_bl = RayState(
        x=np.array([0.0, 8.0, 1.1, 0.3]),
        p=np.array([-1.0, 0.2, 0.7, 2.0]),
    )
    state_ks = bl_state_to_ks_state(params, state_bl)

    invariants = python_ks_invariants(params, state_ks.x, state_ks.p)

    np.testing.assert_allclose(invariants.energy, 1.0, rtol=0.0, atol=1.0e-14)
    np.testing.assert_allclose(
        invariants.angular_momentum_z, 2.0, rtol=0.0, atol=1.0e-14
    )
    np.testing.assert_allclose(
        invariants.carter_q,
        carter_constant(params, state_bl.x, state_bl.p),
        rtol=0.0,
        atol=2.0e-13,
    )


def test_native_scientific_gate_requires_quality_two() -> None:
    thresholds = NpgsKerrThresholds()

    assert thresholds.minimum_native_quality == 2.0
    assert 1.0 < thresholds.minimum_native_quality <= 2.0


def test_sample_indices_are_deterministic_unique_and_cover_domain() -> None:
    indices = _sample_indices(100, 9)

    np.testing.assert_array_equal(indices, _sample_indices(100, 9))
    assert indices.size == 9
    assert np.all(np.diff(indices) > 0)
    assert indices[0] < 10
    assert indices[-1] > 90
    np.testing.assert_array_equal(_sample_indices(4, 0), np.arange(4))
