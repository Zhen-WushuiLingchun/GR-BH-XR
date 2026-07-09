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
    schwarzschild_radial_freefall_initial_state,
    schwarzschild_radial_freefall_initial_tetrad,
    static_observer_tetrad,
    transport_schwarzschild_radial_freefall_tetrad,
    transported_gram_matrices,
    zamo_angular_velocity,
    zamo_lapse,
    zamo_tetrad,
)
from gr_bh_xr.geodesic_ks import ks_state_to_bl_state
from gr_bh_xr.metric import inverse_metric
from gr_bh_xr.metric_ks import ks_inverse_metric, ks_radius
from gr_bh_xr.types import MetricParams, RayState


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


def test_schwarzschild_freefall_initial_tetrad_matches_worldline_velocity():
    params = MetricParams(M=1.0, a=0.0)
    r = 12.0
    theta = math.radians(65.0)
    state = schwarzschild_radial_freefall_initial_state(params, r=r, theta=theta)
    tetrad = schwarzschild_radial_freefall_initial_tetrad(params, r=r, theta=theta)

    u_ks = ks_inverse_metric(params, state.x[1:4]) @ state.p

    np.testing.assert_allclose(tetrad.e_time, u_ks, atol=2.0e-12)
    np.testing.assert_allclose(ks_gram_matrix(params, tetrad), np.diag([-1.0, 1.0, 1.0, 1.0]), atol=2.0e-12)


def test_transported_schwarzschild_freefall_tetrad_preserves_gram_and_velocity():
    params = MetricParams(M=1.0, a=0.0)
    path = transport_schwarzschild_radial_freefall_tetrad(
        params,
        r_start=12.0,
        theta=math.radians(72.0),
        r_stop=3.0,
        tau_max=30.0,
        max_step=0.08,
    )

    grams = transported_gram_matrices(params, path)
    target = np.diag([-1.0, 1.0, 1.0, 1.0])
    assert float(np.max(np.abs(grams - target))) < 5.0e-7

    velocity_errors = []
    radial_errors = []
    for state_values, frame in zip(path.states[:: max(1, path.states.shape[0] // 12)], path.frames[:: max(1, path.states.shape[0] // 12)]):
        x = state_values[:4]
        p = state_values[4:8]
        u_ks = ks_inverse_metric(params, x[1:4]) @ p
        velocity_errors.append(float(np.max(np.abs(frame[0] - u_ks))))

        bl_state = ks_state_to_bl_state(params, RayState(x=x, p=p))
        u_bl = inverse_metric(params, float(bl_state.x[1]), float(bl_state.x[2])) @ bl_state.p
        r_bl = float(bl_state.x[1])
        radial_errors.append(abs(float(u_bl[1]) + math.sqrt(2.0 * params.M / r_bl)))

    assert max(velocity_errors) < 5.0e-7
    assert max(radial_errors) < 5.0e-7
    assert ks_radius(params, path.states[-1, 1:4]) == pytest.approx(3.0, abs=2.0e-6)
