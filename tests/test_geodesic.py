import math

from gr_bh_xr.camera import initial_ray_state
from gr_bh_xr.geodesic import trace_ray, trace_state
from gr_bh_xr.types import CameraConfig, MetricParams, TraceConfig


def test_schwarzschild_rays_bracket_critical_impact_parameter():
    params = MetricParams(M=1.0, a=0.0)
    cfg = TraceConfig(max_lambda=700.0, r_escape=120.0, max_step=2.0)

    capture = trace_ray(params, CameraConfig(60.0, math.pi / 2.0, 5.0, 0.0), cfg)
    escape = trace_ray(params, CameraConfig(60.0, math.pi / 2.0, 5.5, 0.0), cfg)

    assert capture.event == "capture"
    assert escape.event == "escape"
    assert capture.h_max_abs < 1.0e-7
    assert escape.h_max_abs < 1.0e-7


def test_conserved_quantities_are_stable_for_noncritical_kerr_ray():
    params = MetricParams(M=1.0, a=0.4)
    camera = CameraConfig(r_obs=80.0, theta_obs=math.radians(70.0), alpha=7.0, beta=1.0)
    diagnostics = trace_ray(
        params,
        camera,
        TraceConfig(max_lambda=800.0, r_escape=130.0, max_step=2.0),
    )

    assert diagnostics.event in {"capture", "escape"}
    assert diagnostics.h_max_abs < 1.0e-6
    assert diagnostics.e_drift_abs < 1.0e-12
    assert diagnostics.lz_drift_abs < 1.0e-12
    assert diagnostics.q_drift_abs < 1.0e-4


def test_trace_state_matches_trace_ray_for_bardeen_initial_state():
    params = MetricParams(M=1.0, a=0.4)
    camera = CameraConfig(r_obs=80.0, theta_obs=math.radians(70.0), alpha=7.0, beta=1.0)
    cfg = TraceConfig(max_lambda=800.0, r_escape=130.0, max_step=2.0)

    from_trace_ray = trace_ray(params, camera, cfg)
    from_state = trace_state(params, initial_ray_state(params, camera), cfg, r_obs=camera.r_obs)

    assert from_state.event == from_trace_ray.event
    assert from_state.failure_reason == from_trace_ray.failure_reason
    assert from_state.steps == from_trace_ray.steps
    assert from_state.min_r == from_trace_ray.min_r
    assert from_state.lambda_end == from_trace_ray.lambda_end
    assert from_state.h_max_abs == from_trace_ray.h_max_abs
    assert from_state.q_drift_abs == from_trace_ray.q_drift_abs


def test_axis_coordinate_singularity_is_structured_invalid_reason():
    params = MetricParams(M=1.0, a=0.0)
    diagnostics = trace_ray(
        params,
        CameraConfig(r_obs=50.0, theta_obs=math.pi / 2.0, alpha=0.0, beta=8.0),
        TraceConfig(max_lambda=700.0, r_escape=100.0, max_step=2.0),
    )

    assert diagnostics.event == "invalid"
    assert diagnostics.failure_reason == "axis_coordinate_singularity"
    assert diagnostics.lambda_end > 0.0
    assert diagnostics.min_r < 50.0


def test_escape_direction_uses_momentum_not_escape_sphere_position():
    params = MetricParams(M=1.0, a=0.0)
    camera = CameraConfig(r_obs=100.0, theta_obs=math.pi / 2.0, alpha=8.0, beta=0.0)
    near = trace_ray(
        params,
        camera,
        TraceConfig(max_lambda=2000.0, r_escape=200.0, max_step=1.0, rtol=1.0e-10, atol=1.0e-12),
    )
    far = trace_ray(
        params,
        camera,
        TraceConfig(max_lambda=2000.0, r_escape=400.0, max_step=1.0, rtol=1.0e-10, atol=1.0e-12),
    )

    assert near.event == "escape"
    assert far.event == "escape"
    near_dir = (near.escape_dir_x, near.escape_dir_y, near.escape_dir_z)
    far_dir = (far.escape_dir_x, far.escape_dir_y, far.escape_dir_z)
    dot = sum(a * b for a, b in zip(near_dir, far_dir))
    angular_error = math.acos(max(-1.0, min(1.0, dot)))
    assert angular_error < 1.0e-5
