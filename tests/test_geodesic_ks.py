import math

from gr_bh_xr.camera import initial_ray_state
from gr_bh_xr.geodesic import trace_ray
from gr_bh_xr.geodesic_ks import bl_state_to_ks_state, trace_state_ks
from gr_bh_xr.metric import hamiltonian as bl_hamiltonian
from gr_bh_xr.metric_ks import ks_hamiltonian
from gr_bh_xr.types import CameraConfig, MetricParams, TraceConfig


def test_bl_to_ks_state_preserves_null_hamiltonian():
    params = MetricParams(M=1.0, a=0.5)
    camera = CameraConfig(r_obs=80.0, theta_obs=math.radians(70.0), alpha=7.0, beta=1.0)
    bl_state = initial_ray_state(params, camera)
    ks_state = bl_state_to_ks_state(params, bl_state)

    assert abs(bl_hamiltonian(params, bl_state.x, bl_state.p)) < 1.0e-10
    assert abs(ks_hamiltonian(params, ks_state.x, ks_state.p)) < 1.0e-10


def test_ks_trace_matches_bl_escape_classification_and_min_radius():
    params = MetricParams(M=1.0, a=0.0)
    camera = CameraConfig(r_obs=80.0, theta_obs=math.pi / 2.0, alpha=7.0, beta=0.0)
    cfg = TraceConfig(max_lambda=900.0, r_escape=140.0, horizon_eps=0.3, max_step=1.0)

    bl = trace_ray(params, camera, cfg)
    ks = trace_state_ks(params, bl_state_to_ks_state(params, initial_ray_state(params, camera)), cfg, r_obs=80.0)

    assert bl.event == "escape"
    assert ks.event == "escape"
    # Both diagnostics use stored solver samples rather than a radial turning
    # point root solve, so the chart-dependent adaptive step sequence sets the
    # comparison floor here.
    assert abs(ks.min_r - bl.min_r) < 2.0e-2
    assert ks.h_max_abs < 1.0e-8
    assert ks.e_drift_abs < 1.0e-11
    assert ks.lz_drift_abs < 1.0e-8


def test_ks_schwarzschild_capture_continues_inside_outer_horizon():
    params = MetricParams(M=1.0, a=0.0)
    camera = CameraConfig(r_obs=60.0, theta_obs=math.pi / 2.0, alpha=4.0, beta=0.0)
    cfg = TraceConfig(max_lambda=300.0, r_escape=120.0, horizon_eps=0.3, max_step=0.5)
    ks = trace_state_ks(params, bl_state_to_ks_state(params, initial_ray_state(params, camera)), cfg, r_obs=60.0)

    assert ks.event == "capture"
    assert ks.final_r < 2.0
    assert ks.min_r < 2.0
    assert ks.h_max_abs < 1.0e-8
    assert ks.e_drift_abs < 1.0e-11
