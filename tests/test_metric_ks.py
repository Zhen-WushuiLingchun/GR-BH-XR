import math

import numpy as np

from gr_bh_xr.metric import horizon_radius
from gr_bh_xr.metric_ks import (
    MINKOWSKI_INVERSE,
    bl_to_ks_cartesian,
    ks_cartesian_to_bl,
    ks_h_l_cov,
    ks_inverse_metric,
    ks_inverse_metric_derivatives,
    ks_inverse_metric_derivatives_finite_difference,
    ks_metric,
)
from gr_bh_xr.types import MetricParams


def test_ks_schwarzschild_limit_on_x_axis():
    params = MetricParams(M=1.0, a=0.0)
    xyz = np.array([10.0, 0.0, 0.0], dtype=np.float64)

    cov = ks_metric(params, xyz)
    inv = ks_inverse_metric(params, xyz)
    h, l_cov = ks_h_l_cov(params, xyz)

    assert math.isclose(h, 0.1, rel_tol=0.0, abs_tol=1.0e-15)
    assert np.allclose(l_cov, np.array([1.0, 1.0, 0.0, 0.0]), atol=1.0e-15)
    assert math.isclose(cov[0, 0], -0.8, abs_tol=1.0e-15)
    assert math.isclose(cov[0, 1], 0.2, abs_tol=1.0e-15)
    assert math.isclose(cov[1, 1], 1.2, abs_tol=1.0e-15)
    assert np.allclose(cov @ inv, np.eye(4), atol=1.0e-13)


def test_ks_null_vector_is_minkowski_null():
    params = MetricParams(M=1.0, a=0.7)
    xyz = bl_to_ks_cartesian(6.0, 1.1, 0.8, params.a)
    _h, l_cov = ks_h_l_cov(params, xyz)
    l_contra = MINKOWSKI_INVERSE @ l_cov

    assert abs(float(l_cov @ MINKOWSKI_INVERSE @ l_cov)) < 1.0e-13
    assert abs(float(l_cov @ l_contra)) < 1.0e-13


def test_ks_metric_inverse_matches_covariant_metric():
    params = MetricParams(M=1.0, a=0.8)
    xyz = bl_to_ks_cartesian(4.5, 0.9, -1.2, params.a)

    cov = ks_metric(params, xyz)
    inv = ks_inverse_metric(params, xyz)

    assert np.allclose(cov @ inv, np.eye(4), atol=2.0e-13)


def test_ks_cartesian_bl_roundtrip():
    for spin in (0.0, 0.4, 0.9):
        xyz = bl_to_ks_cartesian(8.0, 1.2, -0.7, spin)
        r, theta, phi = ks_cartesian_to_bl(xyz, spin)

        assert math.isclose(r, 8.0, rel_tol=0.0, abs_tol=2.0e-14)
        assert math.isclose(theta, 1.2, rel_tol=0.0, abs_tol=2.0e-14)
        assert math.isclose(math.atan2(math.sin(phi + 0.7), math.cos(phi + 0.7)), 0.0, abs_tol=2.0e-14)


def test_ks_inverse_metric_derivatives_match_finite_difference():
    params = MetricParams(M=1.0, a=0.65)
    xyz = bl_to_ks_cartesian(7.3, 1.15, 0.4, params.a)

    analytic = ks_inverse_metric_derivatives(params, xyz)
    numeric = ks_inverse_metric_derivatives_finite_difference(params, xyz)

    for actual, expected in zip(analytic, numeric):
        assert np.allclose(actual, expected, rtol=3.0e-5, atol=3.0e-7)


def test_ks_metric_is_finite_at_outer_horizon():
    params = MetricParams(M=1.0, a=0.9)
    xyz = bl_to_ks_cartesian(horizon_radius(params), math.pi / 2.0, 0.3, params.a)

    cov = ks_metric(params, xyz)
    inv = ks_inverse_metric(params, xyz)

    assert np.all(np.isfinite(cov))
    assert np.all(np.isfinite(inv))
    assert np.allclose(cov @ inv, np.eye(4), atol=3.0e-13)
