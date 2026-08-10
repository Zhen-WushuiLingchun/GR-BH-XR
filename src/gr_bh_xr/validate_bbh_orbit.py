"""Validate the leading-quadrupole BBH inspiral trajectory provider."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from .metrics import QuasiCircularInspiralOrbit


def run_validation() -> dict[str, object]:
    cases = []
    max_center_of_mass = 0.0
    max_rate_relative_error = 0.0
    max_frequency_relative_error = 0.0
    max_balance_relative_error = 0.0
    for mass_ratio in (1.0, 0.5):
        orbit = QuasiCircularInspiralOrbit(
            total_mass=1.0,
            initial_separation=20.0,
            mass_ratio=mass_ratio,
            minimum_separation=6.0,
        )
        samples = []
        for fraction in (0.0, 0.25, 0.5, 0.75):
            time = orbit.t0 + fraction * (orbit.valid_until - orbit.t0)
            step = 1.0e-3
            numerical_rate = (
                orbit.separation_at(time + step)
                - orbit.separation_at(time - step)
            ) / (2.0 * step)
            numerical_frequency = (
                orbit.phase_at(time + step) - orbit.phase_at(time - step)
            ) / (2.0 * step)
            separation = float(orbit.separation_at(time))
            expected_rate = -orbit.radiation_reaction_coefficient / separation**3
            expected_frequency = math.sqrt(orbit.total_mass / separation**3)
            rate_error = abs(float(numerical_rate) - expected_rate) / abs(expected_rate)
            frequency_error = abs(float(numerical_frequency) - expected_frequency) / abs(
                expected_frequency
            )

            first, second = orbit.states(time)
            center = (
                first.mass * first.position + second.mass * second.position
            ) / orbit.total_mass
            center_norm = float(np.linalg.norm(center))

            eta = orbit.symmetric_mass_ratio
            d_energy_dt = (
                eta * orbit.total_mass**2 / (2.0 * separation**2) * expected_rate
            )
            quadrupole_flux = -32.0 / 5.0 * eta**2 * orbit.total_mass**5 / separation**5
            balance_error = abs(d_energy_dt - quadrupole_flux) / abs(quadrupole_flux)

            max_center_of_mass = max(max_center_of_mass, center_norm)
            max_rate_relative_error = max(max_rate_relative_error, rate_error)
            max_frequency_relative_error = max(
                max_frequency_relative_error, frequency_error
            )
            max_balance_relative_error = max(max_balance_relative_error, balance_error)
            samples.append(
                {
                    "fraction_of_valid_interval": fraction,
                    "time": time,
                    "separation": separation,
                    "radial_rate": expected_rate,
                    "angular_frequency": expected_frequency,
                    "center_of_mass_norm": center_norm,
                    "rate_relative_error": rate_error,
                    "frequency_relative_error": frequency_error,
                    "energy_balance_relative_error": balance_error,
                }
            )
        cases.append(
            {
                "mass_ratio_q_m1_over_m2": mass_ratio,
                "symmetric_mass_ratio": orbit.symmetric_mass_ratio,
                "valid_until": orbit.valid_until,
                "samples": samples,
            }
        )

    gates = {
        "center_of_mass_lt_1e_13": max_center_of_mass < 1.0e-13,
        "radial_rate_relative_error_lt_2e_6": max_rate_relative_error < 2.0e-6,
        "frequency_relative_error_lt_2e_6": max_frequency_relative_error < 2.0e-6,
        "newtonian_energy_balance_lt_1e_13": max_balance_relative_error < 1.0e-13,
    }
    return {
        "schema": "gr-bh-xr.bbh.orbit.v1",
        "provider": "leading_quadrupole_quasicircular_inspiral",
        "source_revision": "gr-bh-xr.peters-circular-inspiral.v1",
        "evidence_label": "physics_approximation",
        "reference": "peters1964grMotionTwoPointMasses",
        "scope": "nonspinning adiabatic circular inspiral; not full 4PN",
        "max_center_of_mass_norm": max_center_of_mass,
        "max_radial_rate_relative_error": max_rate_relative_error,
        "max_frequency_relative_error": max_frequency_relative_error,
        "max_energy_balance_relative_error": max_balance_relative_error,
        "cases": cases,
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
