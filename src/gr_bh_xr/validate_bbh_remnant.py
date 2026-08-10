"""Validate the smooth BBH inspiral-to-Kerr-remnant transition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .bbh_constraints import adm_constraint_sample
from .dynamic_metric import finite_difference_inverse_metric_derivatives
from .metric_ks import MINKOWSKI_COVARIANT
from .metrics import (
    BinaryHoleState,
    MergerRemnantTrajectory,
    QuasiCircularInspiralOrbit,
    SuperposedKerrSchildBBHProvider,
    boosted_kerr_ks_perturbation,
    smooth_transition_weight,
)


def _trajectory() -> MergerRemnantTrajectory:
    return MergerRemnantTrajectory(
        inspiral=QuasiCircularInspiralOrbit(
            initial_separation=12.0,
            minimum_separation=5.0,
            dimensionless_spin1=(0.0, 0.0, 0.2),
            dimensionless_spin2=(0.0, 0.0, -0.1),
        ),
        transition_start=100.0,
        transition_duration=20.0,
        remnant_mass=0.95,
        remnant_spin=(0.0, 0.0, 0.65),
    )


def run_validation() -> dict[str, object]:
    trajectory = _trajectory()
    provider = SuperposedKerrSchildBBHProvider(trajectory)
    source_provider = SuperposedKerrSchildBBHProvider(trajectory.inspiral)
    point = np.array([2.3, -1.7, 0.8])

    pre_time = trajectory.transition_start - 1.0
    pre_error = float(
        np.max(
            np.abs(
                provider.covariant_metric(pre_time, point)
                - source_provider.covariant_metric(pre_time, point)
            )
        )
    )

    post_time = trajectory.transition_end + 1.0
    post_metric = provider.covariant_metric(post_time, point)
    full_hole = BinaryHoleState(
        trajectory.remnant_mass,
        np.asarray(trajectory.remnant_position_at_end),
        np.asarray(trajectory.remnant_velocity),
        np.zeros(3),
        np.asarray(trajectory.remnant_spin),
    )
    full_term, _ = boosted_kerr_ks_perturbation(
        np.concatenate([[post_time], point]), full_hole
    )
    post_error = float(
        np.max(np.abs(post_metric - (MINKOWSKI_COVARIANT + full_term)))
    )

    symmetry_error = max(
        abs(
            float(smooth_transition_weight(value))
            + float(smooth_transition_weight(1.0 - value))
            - 1.0
        )
        for value in np.linspace(0.05, 0.95, 19)
    )
    continuity: dict[str, dict[str, float]] = {}
    epsilon = 1.0e-6
    for name, boundary in (
        ("start", trajectory.transition_start),
        ("end", trajectory.transition_end),
    ):
        left = trajectory.states(boundary - epsilon)[0]
        right = trajectory.states(boundary + epsilon)[0]
        continuity[name] = {
            "position_jump_norm": float(np.linalg.norm(right.position - left.position)),
            "velocity_jump_norm": float(np.linalg.norm(right.velocity - left.velocity)),
        }

    mid_time = trajectory.transition_start + 0.5 * trajectory.transition_duration
    analytic = provider.sample(mid_time, np.array([3.0, 4.0, 1.2])).d_g_inv
    finite = finite_difference_inverse_metric_derivatives(
        provider, mid_time, np.array([3.0, 4.0, 1.2]), relative_step=2.0e-5
    )
    derivative_error = float(np.max(np.abs(analytic - finite)))

    constraints = {}
    for name, time in (
        ("pre", pre_time),
        ("mid", mid_time),
        ("post", post_time),
    ):
        sample = adm_constraint_sample(
            provider, time, np.array([0.0, 8.0, 3.0]), stencil_step=0.04
        )
        constraints[name] = {
            "hamiltonian_abs": abs(sample.hamiltonian),
            "momentum_norm": sample.momentum_norm,
        }

    gates = {
        "pre_transition_exact_inspiral": pre_error < 1.0e-14,
        "post_transition_exact_single_kerr": post_error < 1.0e-13,
        "weight_symmetry_lt_1e_14": symmetry_error < 1.0e-14,
        "boundary_position_jump_lt_1e_5": max(
            item["position_jump_norm"] for item in continuity.values()
        ) < 1.0e-5,
        "boundary_velocity_jump_lt_1e_5": max(
            item["velocity_jump_norm"] for item in continuity.values()
        ) < 1.0e-5,
        "inverse_derivative_error_lt_2e_8": derivative_error < 2.0e-8,
        "post_constraint_lt_2e_5": max(constraints["post"].values()) < 2.0e-5,
    }
    return {
        "schema": "gr-bh-xr.bbh.remnant-transition.v1",
        "provider": provider.source_revision,
        "evidence_label": provider.evidence_label,
        "reference": "combi2026bbhMetricApproximation",
        "remnant_fit_policy": "explicit supplied parameters; no inferred NR fit",
        "pre_transition_max_abs_error": pre_error,
        "post_transition_single_kerr_max_abs_error": post_error,
        "weight_symmetry_max_abs_error": symmetry_error,
        "boundary_continuity": continuity,
        "inverse_derivative_max_abs_error": derivative_error,
        "constraint_residuals": constraints,
        "gates": gates,
        "pass": all(gates.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run_validation()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
