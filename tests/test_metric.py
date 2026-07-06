import math

import numpy as np

from gr_bh_xr.metric import (
    covariant_metric,
    inverse_metric,
    inverse_metric_derivatives,
    inverse_metric_derivatives_finite_difference,
)
from gr_bh_xr.types import MetricParams


def test_kerr_metric_inverse_matches_covariant_metric():
    params = MetricParams(M=1.0, a=0.5)
    r = 8.0
    theta = 1.1

    ident = covariant_metric(params, r, theta) @ inverse_metric(params, r, theta)

    assert np.allclose(ident, np.eye(4), atol=1.0e-12)


def test_schwarzschild_horizon_radius_is_two_m():
    from gr_bh_xr.metric import horizon_radius

    assert math.isclose(horizon_radius(MetricParams(M=1.0, a=0.0)), 2.0)


def test_analytic_inverse_metric_derivatives_match_finite_difference():
    params = MetricParams(M=1.0, a=0.6)
    r = 7.3
    theta = 1.2

    analytic_r, analytic_theta = inverse_metric_derivatives(params, r, theta)
    numeric_r, numeric_theta = inverse_metric_derivatives_finite_difference(params, r, theta)

    assert np.allclose(analytic_r, numeric_r, rtol=3.0e-5, atol=3.0e-7)
    assert np.allclose(analytic_theta, numeric_theta, rtol=3.0e-5, atol=3.0e-7)
