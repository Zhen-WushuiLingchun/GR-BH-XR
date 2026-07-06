import math

from gr_bh_xr.geodesic import trace_ray
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
