from types import SimpleNamespace

import numpy as np

from gr_bh_xr.disk import keplerian_omega, keplerian_u_t
from gr_bh_xr.types import MetricParams
from gr_bh_xr.validate_npgs_disk_transfer import (
    NpgsDiskThresholds,
    _disk_sample_indices,
    _native_crossing_presence,
    finite_observer_disk_redshift,
)


def test_finite_observer_disk_redshift_uses_local_launch_normalization() -> None:
    params = MetricParams(M=1.0, a=0.5)
    radius = 8.0
    p_t_cpu = 0.97
    p_phi_cpu = -2.2
    expected = 1.0 / (
        keplerian_u_t(params, radius)
        * (p_t_cpu - keplerian_omega(params, radius) * (-p_phi_cpu))
    )

    actual = finite_observer_disk_redshift(
        params,
        r=radius,
        p_t_positive_affine=p_t_cpu,
        p_phi_positive_affine=p_phi_cpu,
    )

    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=1.0e-15)


def test_native_crossing_presence_distinguishes_empty_second_slot() -> None:
    validity = np.zeros((2, 2, 2), dtype=bool)
    flags = np.zeros((2, 2, 2), dtype=np.int16)
    order = np.zeros((2, 2, 2), dtype=np.int16)
    validity[0, 0, 0] = True
    flags[0, 1, 0] = 1
    order[1, 0, 1] = 1

    present = _native_crossing_presence(validity, flags, order)

    np.testing.assert_array_equal(
        present[0], [[True, False], [True, False]]
    )
    np.testing.assert_array_equal(
        present[1], [[False, True], [False, False]]
    )


def test_disk_sampling_always_includes_recorded_second_crossings() -> None:
    capture = SimpleNamespace(
        event_code=np.ones((5, 5), dtype=np.int8),
        disk_validity=np.zeros((2, 5, 5), dtype=bool),
        disk_flags=np.zeros((2, 5, 5), dtype=np.int16),
        disk_order=np.zeros((2, 5, 5), dtype=np.int16),
    )
    capture.disk_order[1, 1, 3] = 1
    capture.disk_flags[1, 4, 0] = 1

    indices = _disk_sample_indices(capture, samples=3)

    assert np.ravel_multi_index((1, 3), (5, 5)) in indices
    assert np.ravel_multi_index((4, 0), (5, 5)) in indices
    assert np.all(np.diff(indices) > 0)


def test_native_disk_gate_requires_quality_two() -> None:
    assert NpgsDiskThresholds().minimum_native_quality == 2.0
