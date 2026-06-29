import math

from gr_bh_xr.camera import initial_ray_state, screen_constants
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
