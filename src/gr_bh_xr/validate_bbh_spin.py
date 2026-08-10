"""Validate aligned and generic-spin superposed Kerr-Schild BBH terms."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .bbh_constraints import adm_constraint_sample
from .dynamic_metric import finite_difference_inverse_metric_derivatives
from .metric_ks import MINKOWSKI_COVARIANT, ks_metric
from .metrics import (
    BinaryHoleState,
    FixedCircularBinaryOrbit,
    SuperposedKerrSchildBBHProvider,
    boosted_kerr_ks_perturbation,
)
from .types import MetricParams


def run_validation() -> dict[str, object]:
    mass = 0.7
    spin = 0.4
    xyz = np.array([2.3, -1.7, 0.8])
    hole = BinaryHoleState(
        mass,
        np.zeros(3),
        np.zeros(3),
        np.zeros(3),
        np.array([0.0, 0.0, spin]),
    )
    perturbation, _ = boosted_kerr_ks_perturbation(
        np.concatenate([[0.0], xyz]), hole
    )
    single_kerr_error = float(
        np.max(
            np.abs(
                MINKOWSKI_COVARIANT
                + perturbation
                - ks_metric(MetricParams(M=mass, a=spin), xyz)
            )
        )
    )

    rotation = np.array(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    generic_spin = np.array([0.12, -0.18, 0.31])
    generic_hole = BinaryHoleState(
        0.8, np.zeros(3), np.zeros(3), np.zeros(3), generic_spin
    )
    rotated_hole = BinaryHoleState(
        0.8, np.zeros(3), np.zeros(3), np.zeros(3), rotation @ generic_spin
    )
    generic_term, _ = boosted_kerr_ks_perturbation(
        np.concatenate([[0.0], xyz]), generic_hole
    )
    rotated_term, _ = boosted_kerr_ks_perturbation(
        np.concatenate([[0.0], rotation @ xyz]), rotated_hole
    )
    transform = np.eye(4)
    transform[1:4, 1:4] = rotation
    rotation_error = float(
        np.max(np.abs(rotated_term - transform @ generic_term @ transform.T))
    )

    orbit = FixedCircularBinaryOrbit(
        separation=20.0,
        dimensionless_spin1=(0.0, 0.0, 0.6),
        dimensionless_spin2=(0.2, -0.1, 0.3),
    )
    provider = SuperposedKerrSchildBBHProvider(orbit)
    derivative_point = np.array([2.0, 5.0, 1.7])
    analytic = provider.sample(3.4, derivative_point).d_g_inv
    finite = finite_difference_inverse_metric_derivatives(
        provider, 3.4, derivative_point, relative_step=2.0e-5
    )
    derivative_error = float(np.max(np.abs(analytic - finite)))

    constraint_points = {
        "near": np.array([0.0, 3.0, 1.0]),
        "bridge": np.array([0.0, 12.0, 4.0]),
        "far": np.array([0.0, 80.0, 30.0]),
    }
    constraints: dict[str, dict[str, float]] = {}
    for region, point in constraint_points.items():
        sample = adm_constraint_sample(provider, 0.0, point, stencil_step=0.04)
        constraints[region] = {
            "hamiltonian_abs": abs(sample.hamiltonian),
            "momentum_norm": sample.momentum_norm,
        }

    gates = {
        "z_aligned_single_kerr_error_lt_1e_13": single_kerr_error < 1.0e-13,
        "generic_spin_rotation_error_lt_1e_13": rotation_error < 1.0e-13,
        "inverse_derivative_error_lt_2e_8": derivative_error < 2.0e-8,
        "near_constraint_inside_source_envelope": max(
            constraints["near"].values()
        ) < 1.0e-1,
        "bridge_constraint_inside_source_envelope": max(
            constraints["bridge"].values()
        ) < 1.0e-3,
        "far_constraint_lt_1e_6": max(constraints["far"].values()) < 1.0e-6,
    }
    return {
        "schema": "gr-bh-xr.bbh.spin-gate.v1",
        "provider": provider.source_revision,
        "evidence_label": provider.evidence_label,
        "reference": "combi2026bbhMetricApproximation",
        "single_kerr_max_abs_error": single_kerr_error,
        "generic_spin_rotation_max_abs_error": rotation_error,
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
