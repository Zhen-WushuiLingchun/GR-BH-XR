import math

import numpy as np
import pytest

from gr_bh_xr.metric import horizon_radius
from gr_bh_xr.observers import (
    analytic_kerr_frame_dragging_omega,
    analytic_zamo_lapse,
    gram_matrix,
    ks_gram_matrix,
    push_bl_tetrad_to_ks,
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


def test_zamo_horizon_limit_probe():
    params = MetricParams(M=1.0, a=0.9)
    r_plus = horizon_radius(params)
    omega_h = params.a / (2.0 * params.M * r_plus)
    theta = math.pi / 2.0

    eps_values = [1.0e-3, 1.0e-4, 1.0e-5]
    omega_errors = []
    lapse_scaled = []
    for eps in eps_values:
        r = r_plus + eps
        omega_errors.append(abs(zamo_angular_velocity(params, r, theta) / omega_h - 1.0))
        lapse_scaled.append(zamo_lapse(params, r, theta) / math.sqrt(eps))

    assert omega_errors[1] < 0.12 * omega_errors[0]
    assert omega_errors[2] < 0.12 * omega_errors[1]
    assert lapse_scaled[2] == pytest.approx(lapse_scaled[1], rel=5.0e-4)


def test_pushed_zamo_tetrad_is_orthonormal_in_ks_chart():
    params = MetricParams(M=1.0, a=0.9)
    bl_tetrad = zamo_tetrad(params, r=3.2, theta=1.1, phi=0.4)

    ks_tetrad = push_bl_tetrad_to_ks(params, bl_tetrad)
    gram = ks_gram_matrix(params, ks_tetrad)

    assert ks_tetrad.kind == "zamo_pushed_to_ks"
    np.testing.assert_allclose(gram, np.diag([-1.0, 1.0, 1.0, 1.0]), atol=2.0e-10)
