import math

import numpy as np

from gr_bh_xr.dynamic_metric import finite_difference_inverse_metric_derivatives
from gr_bh_xr.dynamic_types import DynamicEventSpec, DynamicTraceConfig
from gr_bh_xr.geodesic_dynamic import dynamic_hamiltonian, trace_dynamic_state
from gr_bh_xr.metrics import (
    MinkowskiMetricProvider,
    PlaneGWMetricProvider,
    PlaneGWParameters,
    plane_gw_first_order_time_delay,
    plane_gw_initial_state,
)
from gr_bh_xr.validate_dynamic_analytic import run_validation


def _arrival_delay(amplitude: float) -> tuple[float, float]:
    params = PlaneGWParameters(
        amplitude=amplitude,
        angular_frequency=0.7,
        polarization_angle=0.31,
        phase=0.23,
    )
    provider = PlaneGWMetricProvider(params)
    direction = np.array([0.6, 0.3, math.sqrt(0.55)])
    distance = 7.0
    state = plane_gw_initial_state(provider, direction)

    def arrival_plane(_lam: float, x: np.ndarray, _p: np.ndarray) -> float:
        return float(np.dot(direction, x[1:4]) - distance)

    result = trace_dynamic_state(
        provider,
        state,
        DynamicTraceConfig(
            max_lambda=14.0,
            rtol=2.0e-12,
            atol=2.0e-14,
            max_step=0.05,
            events=(DynamicEventSpec("arrival", arrival_plane, direction=1.0),),
        ),
    )
    assert result.event == "arrival"
    assert result.h_max_abs < 2.0e-12
    return result.final_x[0] - distance, plane_gw_first_order_time_delay(
        params, direction, distance
    )


def test_zero_amplitude_plane_wave_is_exact_minkowski() -> None:
    wave = PlaneGWMetricProvider(PlaneGWParameters(amplitude=0.0))
    flat = MinkowskiMetricProvider()
    for t, point in ((0.0, np.zeros(3)), (1.7, np.array([2.0, -3.0, 4.0]))):
        actual = wave.sample(t, point)
        expected = flat.sample(t, point)
        np.testing.assert_array_equal(actual.g_cov, expected.g_cov)
        np.testing.assert_array_equal(actual.g_inv, expected.g_inv)
        np.testing.assert_array_equal(actual.d_g_inv, expected.d_g_inv)


def test_plane_wave_is_transverse_traceless_with_explicit_polarization() -> None:
    provider = PlaneGWMetricProvider(
        PlaneGWParameters(
            propagation_direction=(1.0, 2.0, 3.0), polarization_angle=0.47
        )
    )
    tensor = provider.polarization_tensor
    np.testing.assert_allclose(tensor, tensor.T, atol=1.0e-15)
    assert abs(float(np.trace(tensor))) < 1.0e-15
    np.testing.assert_allclose(tensor @ provider.propagation_direction, 0.0, atol=1.0e-15)
    np.testing.assert_allclose(np.sum(tensor * tensor), 2.0, atol=2.0e-15)


def test_plane_wave_analytic_derivatives_match_independent_finite_difference() -> None:
    provider = PlaneGWMetricProvider(
        PlaneGWParameters(
            amplitude=2.0e-3,
            angular_frequency=0.8,
            propagation_direction=(0.2, -0.3, 1.0),
            polarization_angle=0.2,
            phase=0.4,
        )
    )
    sample = provider.sample(0.9, np.array([0.7, -1.2, 2.5]))
    finite = finite_difference_inverse_metric_derivatives(
        provider, sample.t, sample.x, relative_step=2.0e-6
    )
    np.testing.assert_allclose(sample.g_cov @ sample.g_inv, np.eye(4), atol=2.0e-15)
    np.testing.assert_allclose(sample.d_g_inv, finite, rtol=2.0e-7, atol=2.0e-10)


def test_plane_wave_initial_state_is_exactly_null() -> None:
    provider = PlaneGWMetricProvider(PlaneGWParameters(amplitude=0.02, phase=0.4))
    state = plane_gw_initial_state(provider, (0.4, -0.2, 0.9))
    sample = provider.sample(state.x[0], state.x[1:4])
    assert abs(dynamic_hamiltonian(sample, state.p)) < 2.0e-16


def test_first_order_arrival_time_residual_scales_quadratically() -> None:
    observed, analytic = _arrival_delay(1.0e-3)
    observed_half, analytic_half = _arrival_delay(5.0e-4)
    residual = abs(observed - analytic)
    residual_half = abs(observed_half - analytic_half)
    assert abs(observed - analytic) < 2.0e-5
    assert 3.4 < residual / residual_half < 4.6


def test_visual_gain_one_is_exact_identity() -> None:
    physical_displacement = 1.23456789e-7
    visual_gain = 1.0
    displayed_displacement = visual_gain * physical_displacement
    assert displayed_displacement == physical_displacement


def test_dynamic_analytic_validation_smoke() -> None:
    result = run_validation(amplitude=1.0e-3, visual_gain=1.0)
    assert result["pass"] is True
    assert result["metric"]["evidence_label"] == "validated_dynamic_analytic"
    assert result["physical_angular_displacement_rad"] == result[
        "display_angular_displacement_rad"
    ]
