import math

import numpy as np
import pytest

from gr_bh_xr.metric import horizon_radius
from gr_bh_xr.observers import (
    analytic_kerr_frame_dragging_omega,
    analytic_zamo_lapse,
    gram_matrix,
    static_observer_tetrad,
    zamo_angular_velocity,
    zamo_lapse,
    zamo_tetrad,
)
from gr_bh_xr.types import MetricParams


def test_zamo_angular_velocity_and_lapse_match_analytic_kerr_formulae():
    params = MetricParams(M=1.0, a=0.9)
    r = 3.2
    theta = math.radians(63.0)

    assert zamo_angular_velocity(params, r, theta) == pytest.approx(
        analytic_kerr_frame_dragging_omega(params, r, theta), rel=2.0e-15
    )
    assert zamo_lapse(params, r, theta) == pytest.approx(
        analytic_zamo_lapse(params, r, theta), rel=2.0e-15
    )


def test_zamo_tetrad_is_orthonormal_outside_horizon():
    params = MetricParams(M=1.0, a=0.9)
    tetrad = zamo_tetrad(params, r=2.1, theta=math.pi / 2.0)
    gram = gram_matrix(params, tetrad)

    np.testing.assert_allclose(gram, np.diag([-1.0, 1.0, 1.0, 1.0]), atol=4.0e-15)


def test_static_observer_fails_inside_ergoregion_but_zamo_remains_defined():
    params = MetricParams(M=1.0, a=0.9)
    r = 1.8
    theta = math.pi / 2.0

    assert horizon_radius(params) < r < 2.0
    with pytest.raises(ValueError, match="ergoregion"):
        static_observer_tetrad(params, r=r, theta=theta)

    tetrad = zamo_tetrad(params, r=r, theta=theta)
    np.testing.assert_allclose(gram_matrix(params, tetrad), np.diag([-1.0, 1.0, 1.0, 1.0]), atol=1.0e-14)


def test_zamo_converges_to_static_observer_in_far_field():
    params = MetricParams(M=1.0, a=0.9)
    r = 1.0e4
    theta = math.radians(71.0)
    zamo = zamo_tetrad(params, r=r, theta=theta)
    static = static_observer_tetrad(params, r=r, theta=theta)

    assert abs(zamo_angular_velocity(params, r, theta)) < 2.0e-12
    np.testing.assert_allclose(zamo.e_time, static.e_time, atol=2.0e-12)
    np.testing.assert_allclose(zamo.e_r, static.e_r, atol=1.0e-15)
    np.testing.assert_allclose(zamo.e_theta, static.e_theta, atol=1.0e-15)
    np.testing.assert_allclose(zamo.e_phi, static.e_phi, atol=2.0e-8)
