import math
from dataclasses import replace

import numpy as np

from gr_bh_xr.camera import initial_ray_state
from gr_bh_xr.dynamic_metric import (
    IsotropicScaleFactorProvider,
    MinkowskiMetricProvider,
    StationaryKerrSchildProvider,
)
from gr_bh_xr.dynamic_types import DynamicTraceConfig
from gr_bh_xr.geodesic_dynamic import kerr_schild_radius_events, trace_dynamic_state
from gr_bh_xr.geodesic_ks import (
    _inner_capture_radius,
    bl_state_to_ks_state,
    ks_state_to_bl_state,
    trace_state_ks,
)
from gr_bh_xr.sky import momentum_direction_from_state
from gr_bh_xr.types import CameraConfig, MetricParams, RayState, TraceConfig


def test_minkowski_ray_is_straight_to_f64_tolerance() -> None:
    state = RayState(
        x=np.array([0.0, 1.0, -2.0, 0.5]),
        p=np.array([-1.0, 0.6, 0.0, 0.8]),
    )
    result = trace_dynamic_state(
        MinkowskiMetricProvider(),
        state,
        DynamicTraceConfig(max_lambda=12.5, max_step=0.7),
    )
    expected_x = state.x + 12.5 * np.array([1.0, 0.6, 0.0, 0.8])
    assert result.event == "budget_exhaustion"
    np.testing.assert_allclose(result.final_x, expected_x, rtol=0.0, atol=2.0e-13)
    np.testing.assert_allclose(result.final_p, state.p, rtol=0.0, atol=0.0)
    assert result.h_max_abs < 1.0e-14


def test_stationary_adapter_matches_ks_event_and_escape_direction() -> None:
    params = MetricParams(M=1.0, a=0.5)
    camera = CameraConfig(r_obs=60.0, theta_obs=math.radians(60.0), alpha=8.0, beta=1.2)
    state = bl_state_to_ks_state(params, initial_ray_state(params, camera))
    legacy_cfg = TraceConfig(
        max_lambda=300.0,
        r_escape=120.0,
        horizon_eps=0.3,
        rtol=1.0e-10,
        atol=1.0e-12,
        max_step=1.0,
    )
    legacy = trace_state_ks(params, state, legacy_cfg, r_obs=camera.r_obs)
    events = kerr_schild_radius_events(
        params,
        capture_radius=_inner_capture_radius(params, legacy_cfg.horizon_eps),
        escape_radius=legacy_cfg.r_escape,
    )
    dynamic = trace_dynamic_state(
        StationaryKerrSchildProvider(params),
        state,
        DynamicTraceConfig(
            max_lambda=legacy_cfg.max_lambda,
            rtol=legacy_cfg.rtol,
            atol=legacy_cfg.atol,
            max_step=legacy_cfg.max_step,
            events=events,
        ),
    )
    assert legacy.event == dynamic.event == "escape"
    legacy_bl = ks_state_to_bl_state(params, RayState(legacy.final_x, legacy.final_p))
    dynamic_bl = ks_state_to_bl_state(params, RayState(dynamic.final_x, dynamic.final_p))
    legacy_dir = momentum_direction_from_state(
        params,
        r=legacy_bl.x[1], theta=legacy_bl.x[2], phi=legacy_bl.x[3],
        p_t=legacy_bl.p[0], p_r=legacy_bl.p[1], p_theta=legacy_bl.p[2], p_phi=legacy_bl.p[3],
    )[2:]
    dynamic_dir = momentum_direction_from_state(
        params,
        r=dynamic_bl.x[1], theta=dynamic_bl.x[2], phi=dynamic_bl.x[3],
        p_t=dynamic_bl.p[0], p_r=dynamic_bl.p[1], p_theta=dynamic_bl.p[2], p_phi=dynamic_bl.p[3],
    )[2:]
    angle = math.acos(float(np.clip(np.dot(legacy_dir, dynamic_dir), -1.0, 1.0)))
    assert angle < 3.0e-8
    assert dynamic.h_max_abs < 1.0e-9


def test_stationary_adapter_matches_ks_capture_classification() -> None:
    params = MetricParams(M=1.0, a=0.5)
    camera = CameraConfig(r_obs=40.0, theta_obs=math.radians(70.0), alpha=0.7, beta=0.4)
    state = bl_state_to_ks_state(params, initial_ray_state(params, camera))
    legacy_cfg = TraceConfig(
        max_lambda=150.0, r_escape=80.0, horizon_eps=0.3,
        rtol=1.0e-10, atol=1.0e-12, max_step=0.5,
    )
    legacy = trace_state_ks(params, state, legacy_cfg, r_obs=camera.r_obs)
    dynamic = trace_dynamic_state(
        StationaryKerrSchildProvider(params),
        state,
        DynamicTraceConfig(
            max_lambda=legacy_cfg.max_lambda,
            rtol=legacy_cfg.rtol,
            atol=legacy_cfg.atol,
            max_step=legacy_cfg.max_step,
            events=kerr_schild_radius_events(
                params,
                capture_radius=_inner_capture_radius(params, legacy_cfg.horizon_eps),
                escape_radius=legacy_cfg.r_escape,
            ),
        ),
    )
    assert legacy.event == dynamic.event == "capture"
    assert dynamic.h_max_abs < 1.0e-8


def test_time_dependent_trace_updates_p_t_without_energy_claim() -> None:
    provider = IsotropicScaleFactorProvider(scale0=1.0, rate=0.01)
    state = RayState(
        x=np.zeros(4, dtype=np.float64),
        p=np.array([-1.0, 1.0, 0.0, 0.0]),
    )
    result = trace_dynamic_state(
        provider, state, DynamicTraceConfig(max_lambda=5.0, max_step=0.1)
    )
    assert result.event == "budget_exhaustion"
    assert result.p_t_final > result.p_t_initial
    assert not hasattr(result, "e_drift_abs")
    assert result.h_max_abs < 1.0e-10
    assert result.metric_evidence_label == "analytic_exact"


def test_provider_domain_failure_is_reported_fail_closed() -> None:
    flat = MinkowskiMetricProvider()

    class BoundedProvider:
        def sample(self, t: float, x: np.ndarray):
            sample = flat.sample(t, x)
            return replace(sample, validity="outside_domain") if t > 0.5 else sample

    state = RayState(x=np.zeros(4), p=np.array([-1.0, 1.0, 0.0, 0.0]))
    result = trace_dynamic_state(
        BoundedProvider(), state, DynamicTraceConfig(max_lambda=2.0, max_step=0.05)
    )
    assert result.event == "invalid"
    assert result.failure_reason == "metric_or_solver_exception"
    assert result.event_provenance == "metric_provider"
    assert result.provider_invalid_samples == 1
    assert result.lambda_end > 0.0
