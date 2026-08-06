import math

import numpy as np
import pytest

from gr_bh_xr.metric import covariant_metric as kerr_covariant_metric
from gr_bh_xr.metric_ks import ks_inverse_metric as kerr_ks_inverse_metric
from gr_bh_xr.metric_ks import ks_metric as kerr_ks_metric
from gr_bh_xr.types import MetricParams
from gr_bh_xr.metric_kn import (
    KerrNewmanParams,
    bl_to_ks_cartesian,
    bl_to_ks_jacobian,
    covariant_metric_bl,
    horizon_radii,
    inverse_metric_bl,
    ks_inverse_metric,
    ks_inverse_metric_derivatives,
    ks_inverse_metric_derivatives_finite_difference,
    ks_metric,
)


def test_kn_parameter_domain_and_horizons() -> None:
    params = KerrNewmanParams(M=2.0, a=0.8, charge=0.6)
    rp, rm = horizon_radii(params)
    root = math.sqrt(4.0 - 0.64 - 0.36)

    assert math.isclose(rp, 2.0 + root, abs_tol=1.0e-15)
    assert math.isclose(rm, 2.0 - root, abs_tol=1.0e-15)
    with pytest.raises(ValueError, match=r"a\^2 \+ Q\^2"):
        KerrNewmanParams(M=1.0, a=0.8, charge=0.6)


def test_kn_q_zero_reduces_to_existing_kerr_metrics() -> None:
    kn = KerrNewmanParams(M=1.0, a=0.7, charge=0.0)
    kerr = MetricParams(M=1.0, a=0.7)
    r, theta, phi = 6.3, 1.1, -0.4
    xyz = bl_to_ks_cartesian(r, theta, phi, kn.a)

    np.testing.assert_allclose(covariant_metric_bl(kn, r, theta), kerr_covariant_metric(kerr, r, theta), atol=2e-14)
    np.testing.assert_allclose(ks_metric(kn, xyz), kerr_ks_metric(kerr, xyz), atol=2e-14)
    np.testing.assert_allclose(ks_inverse_metric(kn, xyz), kerr_ks_inverse_metric(kerr, xyz), atol=2e-14)


def test_reissner_nordstrom_limit_is_exact() -> None:
    params = KerrNewmanParams(M=1.0, a=0.0, charge=0.6)
    r, theta = 8.0, 1.2
    f = 1.0 - 2.0 / r + 0.36 / (r * r)
    expected = np.diag([-f, 1.0 / f, r * r, r * r * math.sin(theta) ** 2])

    np.testing.assert_allclose(covariant_metric_bl(params, r, theta), expected, atol=2e-14)
    np.testing.assert_allclose(inverse_metric_bl(params, r, theta), np.linalg.inv(expected), atol=2e-14)


def test_kn_bl_and_ks_metrics_are_the_same_geometry() -> None:
    params = KerrNewmanParams(M=1.0, a=0.6, charge=0.45)
    r, theta, phi_ks = 5.7, 1.0, 0.8
    xyz = bl_to_ks_cartesian(r, theta, phi_ks, params.a)
    jac = bl_to_ks_jacobian(params, r, theta, phi_ks)

    transformed = jac.T @ ks_metric(params, xyz) @ jac
    np.testing.assert_allclose(transformed, covariant_metric_bl(params, r, theta), rtol=0.0, atol=2e-12)


def test_kn_ks_inverse_and_determinant_are_regular_at_horizon() -> None:
    params = KerrNewmanParams(M=1.0, a=0.6, charge=0.5)
    rp, _ = horizon_radii(params)
    xyz = bl_to_ks_cartesian(rp, 1.2, -0.2, params.a)
    cov = ks_metric(params, xyz)
    inv = ks_inverse_metric(params, xyz)

    np.testing.assert_allclose(cov @ inv, np.eye(4), atol=4e-13)
    assert math.isclose(float(np.linalg.det(cov)), -1.0, abs_tol=4e-13)


def test_kn_ks_analytic_derivatives_match_finite_difference() -> None:
    params = KerrNewmanParams(M=1.0, a=0.55, charge=0.5)
    xyz = bl_to_ks_cartesian(4.2, 1.15, 0.3, params.a)
    analytic = ks_inverse_metric_derivatives(params, xyz)
    numeric = ks_inverse_metric_derivatives_finite_difference(params, xyz)

    for actual, expected in zip(analytic, numeric):
        np.testing.assert_allclose(actual, expected, rtol=4e-5, atol=4e-7)
