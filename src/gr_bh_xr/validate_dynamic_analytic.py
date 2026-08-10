"""Validate analytic dynamic metrics before introducing a BBH approximation."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from .dynamic_metric import finite_difference_inverse_metric_derivatives
from .dynamic_types import DynamicEventSpec, DynamicTraceConfig
from .geodesic_dynamic import trace_dynamic_state
from .metrics import (
    MinkowskiMetricProvider,
    PlaneGWMetricProvider,
    PlaneGWParameters,
    plane_gw_first_order_time_delay,
    plane_gw_initial_state,
)


def _trace_arrival(
    parameters: PlaneGWParameters,
    ray_direction: np.ndarray,
    distance: float,
) -> dict[str, float | str]:
    provider = PlaneGWMetricProvider(parameters)
    state = plane_gw_initial_state(provider, ray_direction)

    def arrival_plane(_lam: float, x: np.ndarray, _p: np.ndarray) -> float:
        return float(np.dot(ray_direction, x[1:4]) - distance)

    result = trace_dynamic_state(
        provider,
        state,
        DynamicTraceConfig(
            max_lambda=2.0 * distance,
            rtol=2.0e-12,
            atol=2.0e-14,
            max_step=min(0.05, distance / 50.0),
            events=(DynamicEventSpec("arrival", arrival_plane, direction=1.0),),
        ),
    )
    final_sample = provider.sample(result.final_x[0], result.final_x[1:4])
    final_tangent = final_sample.g_inv @ result.final_p
    final_direction = final_tangent[1:4] / np.linalg.norm(final_tangent[1:4])
    angular_displacement = math.acos(
        float(np.clip(np.dot(ray_direction, final_direction), -1.0, 1.0))
    )
    numerical_delay = float(result.final_x[0] - distance)
    analytic_delay = plane_gw_first_order_time_delay(parameters, ray_direction, distance)
    return {
        "event": result.event,
        "numerical_delay": numerical_delay,
        "first_order_delay": analytic_delay,
        "absolute_residual": abs(numerical_delay - analytic_delay),
        "physical_angular_displacement_rad": angular_displacement,
        "h_max_abs": result.h_max_abs,
        "p_t_change": result.p_t_final - result.p_t_initial,
    }


def run_validation(
    *,
    amplitude: float = 1.0e-3,
    angular_frequency: float = 0.7,
    distance: float = 7.0,
    visual_gain: float = 1.0,
) -> dict[str, object]:
    """Run zero-limit, derivative, and perturbative plane-GW gates."""

    if amplitude <= 0.0:
        raise ValueError("amplitude must be positive for the convergence gate.")
    if not math.isfinite(visual_gain) or visual_gain < 0.0:
        raise ValueError("visual_gain must be finite and nonnegative.")

    ray_direction = np.array([0.6, 0.3, math.sqrt(0.55)], dtype=np.float64)
    common = dict(
        angular_frequency=angular_frequency,
        polarization_angle=0.31,
        phase=0.23,
    )
    full_parameters = PlaneGWParameters(amplitude=amplitude, **common)
    half_parameters = PlaneGWParameters(amplitude=0.5 * amplitude, **common)
    full = _trace_arrival(full_parameters, ray_direction, distance)
    half = _trace_arrival(half_parameters, ray_direction, distance)

    zero = PlaneGWMetricProvider(PlaneGWParameters(amplitude=0.0, **common))
    flat = MinkowskiMetricProvider()
    sample_event = (0.9, np.array([0.7, -1.2, 2.5], dtype=np.float64))
    zero_sample = zero.sample(*sample_event)
    flat_sample = flat.sample(*sample_event)
    zero_max_abs = max(
        float(np.max(np.abs(zero_sample.g_cov - flat_sample.g_cov))),
        float(np.max(np.abs(zero_sample.g_inv - flat_sample.g_inv))),
        float(np.max(np.abs(zero_sample.d_g_inv - flat_sample.d_g_inv))),
    )

    derivative_provider = PlaneGWMetricProvider(
        PlaneGWParameters(
            amplitude=2.0 * amplitude,
            angular_frequency=0.8,
            propagation_direction=(0.2, -0.3, 1.0),
            polarization_angle=0.2,
            phase=0.4,
        )
    )
    derivative_sample = derivative_provider.sample(*sample_event)
    derivative_fd = finite_difference_inverse_metric_derivatives(
        derivative_provider, *sample_event, relative_step=2.0e-6
    )
    derivative_max_abs = float(
        np.max(np.abs(derivative_sample.d_g_inv - derivative_fd))
    )

    full_residual = float(full["absolute_residual"])
    half_residual = float(half["absolute_residual"])
    residual_ratio = full_residual / half_residual
    observed_order = math.log(residual_ratio, 2.0)
    physical_angle = float(full["physical_angular_displacement_rad"])
    displayed_angle = visual_gain * physical_angle

    gates = {
        "zero_amplitude_exact_minkowski": zero_max_abs == 0.0,
        "analytic_derivative_max_abs_lt_1e_9": derivative_max_abs < 1.0e-9,
        "arrival_events_resolved": full["event"] == half["event"] == "arrival",
        "null_hamiltonian_lt_2e_12": max(
            float(full["h_max_abs"]), float(half["h_max_abs"])
        ) < 2.0e-12,
        "first_order_residual_is_quadratic": 1.8 < observed_order < 2.2,
        "visual_gain_one_identity": visual_gain != 1.0 or displayed_angle == physical_angle,
    }
    return {
        "schema": "gr-bh-xr.dynamic-analytic.v1",
        "metric": {
            "provider": "plane_gw_tt",
            "source_revision": "gr-bh-xr.plane-gw-tt.v1",
            "evidence_label": "validated_dynamic_analytic",
            "vacuum_claim": "linear order in physical strain amplitude",
            "reference": "angelil2015gwOptics Eq. 2 and Eq. 14",
            "signature": "(-,+,+,+)",
        },
        "configuration": {
            "amplitude": amplitude,
            "angular_frequency": angular_frequency,
            "distance": distance,
            "ray_direction": ray_direction.tolist(),
            "polarization_angle": full_parameters.polarization_angle,
            "phase": full_parameters.phase,
            "visual_gain": visual_gain,
        },
        "zero_amplitude_max_abs_difference": zero_max_abs,
        "analytic_derivative_max_abs_difference": derivative_max_abs,
        "full_amplitude": full,
        "half_amplitude": half,
        "residual_ratio_full_over_half": residual_ratio,
        "observed_residual_order": observed_order,
        "physical_angular_displacement_rad": physical_angle,
        "display_angular_displacement_rad": displayed_angle,
        "gates": gates,
        "pass": all(gates.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amplitude", type=float, default=1.0e-3)
    parser.add_argument("--angular-frequency", type=float, default=0.7)
    parser.add_argument("--distance", type=float, default=7.0)
    parser.add_argument("--visual-gain", type=float, default=1.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run_validation(
        amplitude=args.amplitude,
        angular_frequency=args.angular_frequency,
        distance=args.distance,
        visual_gain=args.visual_gain,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
