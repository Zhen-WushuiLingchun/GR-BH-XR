import math

import numpy as np
import pytest

from gr_bh_xr.camera import initial_ray_state, initial_ray_state_from_unity_direction, screen_constants
from gr_bh_xr.metric import carter_constant, hamiltonian
from gr_bh_xr.types import CameraConfig, MetricParams


def test_screen_initialization_is_null():
    params = MetricParams(M=1.0, a=0.0)
    camera = CameraConfig(r_obs=80.0, theta_obs=math.pi / 2.0, alpha=6.0, beta=0.0)

    state = initial_ray_state(params, camera)

    assert abs(hamiltonian(params, state.x, state.p)) < 1.0e-10


def test_carter_constant_matches_screen_constant_at_initialization():
    params = MetricParams(M=1.0, a=0.5)
    camera = CameraConfig(r_obs=80.0, theta_obs=math.radians(60.0), alpha=4.0, beta=1.5)

    _E, _Lz, expected_q = screen_constants(params, camera)
    state = initial_ray_state(params, camera)

    assert abs(carter_constant(params, state.x, state.p) - expected_q) < 1.0e-10


def test_finite_static_observer_direction_initialization_is_null_and_radial_signs():
    params = MetricParams(M=1.0, a=0.5)
    kwargs = {"r_obs": 100.0, "theta_obs": math.radians(60.0)}

    inward = initial_ray_state_from_unity_direction(
        params, direction_unity=np.array([0.0, 0.0, 1.0]), **kwargs
    )
    outward = initial_ray_state_from_unity_direction(
        params, direction_unity=np.array([0.0, 0.0, -1.0]), **kwargs
    )

    assert abs(hamiltonian(params, inward.x, inward.p)) < 1.0e-10
    assert abs(hamiltonian(params, outward.x, outward.p)) < 1.0e-10
    assert inward.p[1] < 0.0
    assert outward.p[1] > 0.0


def test_finite_static_observer_small_angle_matches_bardeen_sign_convention():
    params = MetricParams(M=1.0, a=0.0)
    r_obs = 1.0e6
    theta_obs = math.radians(60.0)
    eps = 1.0e-4

    right = initial_ray_state_from_unity_direction(
        params,
        r_obs=r_obs,
        theta_obs=theta_obs,
        direction_unity=np.array([eps, 0.0, 1.0]),
    )
    up = initial_ray_state_from_unity_direction(
        params,
        r_obs=r_obs,
        theta_obs=theta_obs,
        direction_unity=np.array([0.0, eps, 1.0]),
    )

    alpha_equiv = -right.p[3] / math.sin(theta_obs)
    beta_equiv = up.p[2]
    assert alpha_equiv == pytest.approx(r_obs * eps, rel=2.0e-5)
    assert beta_equiv == pytest.approx(-r_obs * eps, rel=2.0e-5)
