import math

from gr_bh_xr.camera import initial_ray_state
from gr_bh_xr.disk import redshift_factor
from gr_bh_xr.geodesic import trace_ray
from gr_bh_xr.geodesic_ks import _inner_capture_radius, bl_state_to_ks_state, ks_state_to_bl_state, trace_state_ks
from gr_bh_xr.metric import hamiltonian as bl_hamiltonian, horizon_radius
from gr_bh_xr.metric_ks import ks_hamiltonian
from gr_bh_xr.sky import momentum_direction_from_state
from gr_bh_xr.types import CameraConfig, MetricParams, RayState, TraceConfig


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


def test_ks_escape_direction_matches_bl_reference():
    params = MetricParams(M=1.0, a=0.9)
    camera = CameraConfig(r_obs=100.0, theta_obs=math.radians(60.0), alpha=8.0, beta=2.0)
    cfg = TraceConfig(max_lambda=1200.0, r_escape=200.0, horizon_eps=0.05, max_step=1.0)

    bl = trace_ray(params, camera, cfg)
    ks = trace_state_ks(params, bl_state_to_ks_state(params, initial_ray_state(params, camera)), cfg, r_obs=100.0)
    ks_bl_final = ks_state_to_bl_state(params, RayState(ks.final_x, ks.final_p))

    assert bl.event == "escape"
    assert ks.event == "escape"
    ks_dir = momentum_direction_from_state(
        params,
        r=float(ks_bl_final.x[1]),
        theta=float(ks_bl_final.x[2]),
        phi=float(ks_bl_final.x[3]),
        p_t=float(ks_bl_final.p[0]),
        p_r=float(ks_bl_final.p[1]),
        p_theta=float(ks_bl_final.p[2]),
        p_phi=float(ks_bl_final.p[3]),
    )[2:]
    bl_dir = (bl.escape_dir_x, bl.escape_dir_y, bl.escape_dir_z)
    dot = sum(a * b for a, b in zip(ks_dir, bl_dir))
    angular_error = math.acos(max(-1.0, min(1.0, dot)))
    assert angular_error < 2.0e-6


def test_ks_disk_crossing_matches_bl_reference():
    params = MetricParams(M=1.0, a=0.0)
    camera = CameraConfig(r_obs=100.0, theta_obs=math.radians(60.0), alpha=3.0, beta=3.0)
    cfg = TraceConfig(max_lambda=900.0, r_escape=200.0, horizon_eps=0.3, max_step=1.0)

    bl = trace_ray(params, camera, cfg)
    ks = trace_state_ks(params, bl_state_to_ks_state(params, initial_ray_state(params, camera)), cfg, r_obs=100.0)

    assert bl.disk_crossings >= 1
    assert ks.disk_crossings >= 1
    assert ks.disk_crossing_order[0] == 0
    assert abs(ks.disk_crossing_r[0] - bl.disk_crossing_r[0]) < 1.0e-8
    assert abs(math.atan2(
        math.sin(ks.disk_crossing_phi[0] - bl.disk_crossing_phi[0]),
        math.cos(ks.disk_crossing_phi[0] - bl.disk_crossing_phi[0]),
    )) < 1.0e-8
    assert abs(ks.disk_crossing_t[0] - bl.disk_crossing_t[0]) < 1.0e-8
    bl_g = redshift_factor(
        params,
        r=bl.disk_crossing_r[0],
        p_t=bl.disk_crossing_p_t[0],
        p_phi=bl.disk_crossing_p_phi[0],
    )
    ks_g = redshift_factor(
        params,
        r=ks.disk_crossing_r[0],
        p_t=ks.disk_crossing_p_t[0],
        p_phi=ks.disk_crossing_p_phi[0],
    )
    assert abs(ks_g - bl_g) < 1.0e-10


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


def test_ks_inner_capture_radius_stays_outside_cauchy_horizon_near_extremal_spin():
    params = MetricParams(M=1.0, a=0.995)
    r_plus = horizon_radius(params)
    r_minus = params.M - math.sqrt(params.M * params.M - params.a * params.a)
    capture_r = _inner_capture_radius(params, inner_eps=0.3)

    assert r_minus < capture_r < r_plus
