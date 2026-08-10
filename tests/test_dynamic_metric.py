import numpy as np

from gr_bh_xr.dynamic_metric import (
    finite_difference_inverse_metric_derivatives,
    IsotropicScaleFactorProvider,
    MinkowskiMetricProvider,
    StationaryKerrSchildProvider,
)
from gr_bh_xr.geodesic_dynamic import dynamic_hamiltonian_rhs
from gr_bh_xr.geodesic_ks import hamiltonian_rhs_ks
from gr_bh_xr.types import MetricParams


def test_stationary_ks_provider_reproduces_existing_rhs() -> None:
    params = MetricParams(M=1.0, a=0.9)
    provider = StationaryKerrSchildProvider(params)
    y = np.array([0.4, 8.0, -1.2, 2.5, -1.0, -0.7, 0.03, 0.2])

    expected = hamiltonian_rhs_ks(params, 0.0, y)
    actual = dynamic_hamiltonian_rhs(provider, 0.0, y)
    np.testing.assert_allclose(actual, expected, rtol=2.0e-14, atol=2.0e-14)
    assert actual[4] == 0.0


def test_time_derivative_matches_finite_difference_and_changes_p_t() -> None:
    provider = IsotropicScaleFactorProvider(scale0=1.2, rate=0.04)
    t = 0.7
    xyz = np.array([0.2, -0.5, 1.1])
    sample = provider.sample(t, xyz)
    step = 1.0e-6
    finite = (
        provider.sample(t + step, xyz).g_inv - provider.sample(t - step, xyz).g_inv
    ) / (2.0 * step)
    np.testing.assert_allclose(sample.d_g_inv[0], finite, rtol=2.0e-9, atol=2.0e-10)

    scale = provider.scale0 + provider.rate * t
    p = np.array([-1.0 / scale, 1.0, 0.0, 0.0])
    rhs = dynamic_hamiltonian_rhs(provider, 0.0, np.concatenate([[t], xyz, p]))
    assert rhs[4] > 0.0


def test_all_stationary_ks_provider_derivatives_match_independent_finite_difference() -> None:
    provider = StationaryKerrSchildProvider(MetricParams(M=1.0, a=0.7))
    point = np.array([6.0, -1.5, 2.2])
    sample = provider.sample(0.8, point)
    finite = finite_difference_inverse_metric_derivatives(provider, 0.8, point)
    np.testing.assert_allclose(sample.d_g_inv, finite, rtol=2.0e-8, atol=2.0e-9)


def test_minkowski_provider_has_exact_adm_split() -> None:
    sample = MinkowskiMetricProvider().sample(2.0, np.array([1.0, 2.0, 3.0]))
    np.testing.assert_array_equal(sample.g_cov @ sample.g_inv, np.eye(4))
    np.testing.assert_array_equal(sample.gamma_cov, np.eye(3))
    np.testing.assert_array_equal(sample.gamma_inv, np.eye(3))
    assert sample.lapse == 1.0
    assert np.count_nonzero(sample.shift) == 0
