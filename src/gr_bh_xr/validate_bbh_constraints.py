"""Validate the equal-mass superposed Kerr-Schild BBH approximation."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import h5py
import numpy as np

from .bbh_constraints import adm_constraint_sample
from .dynamic_metric import finite_difference_inverse_metric_derivatives
from .metric_ks import MINKOWSKI_COVARIANT
from .metrics import (
    FixedCircularBinaryOrbit,
    SuperposedKerrSchildBBHProvider,
    boosted_schwarzschild_ks_perturbation,
)


_REGION_CODE = {"near_hole": 0, "bridge": 1, "far": 2}


def _constraint_rows(
    *, separations: tuple[float, ...], phases: tuple[float, ...], stencil_step: float
) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for separation in separations:
        orbit = FixedCircularBinaryOrbit(separation=separation)
        provider = SuperposedKerrSchildBBHProvider(orbit)
        for phase in phases:
            t = (phase - orbit.phase0) / orbit.omega
            holes = provider.hole_states(t)
            points: list[tuple[str, np.ndarray]] = []
            for hole in holes:
                near_radius = 3.0 * hole.mass
                points.extend(
                    [
                        ("near_hole", hole.position + np.array([0.0, 0.0, near_radius])),
                        ("near_hole", hole.position + np.array([0.0, near_radius, 0.0])),
                    ]
                )
            points.extend(
                ("bridge", np.array([0.0, 0.0, height]))
                for height in (0.5, 1.0, 2.0)
            )
            for region, point in points:
                sample = adm_constraint_sample(
                    provider, t, point, stencil_step=stencil_step
                )
                rows.append(
                    {
                        "separation": separation,
                        "phase": phase,
                        "time": t,
                        "region": region,
                        "x": float(point[0]),
                        "y": float(point[1]),
                        "z": float(point[2]),
                        "hamiltonian": sample.hamiltonian,
                        "momentum_x": float(sample.momentum[0]),
                        "momentum_y": float(sample.momentum[1]),
                        "momentum_z": float(sample.momentum[2]),
                        "momentum_norm": sample.momentum_norm,
                    }
                )

    far_provider = SuperposedKerrSchildBBHProvider(
        FixedCircularBinaryOrbit(separation=20.0)
    )
    for radius in (30.0, 60.0, 120.0):
        point = np.array([0.0, radius, 0.5 * radius])
        sample = adm_constraint_sample(
            far_provider, 0.0, point, stencil_step=stencil_step
        )
        rows.append(
            {
                "separation": 20.0,
                "phase": 0.0,
                "time": 0.0,
                "region": "far",
                "x": float(point[0]),
                "y": float(point[1]),
                "z": float(point[2]),
                "hamiltonian": sample.hamiltonian,
                "momentum_x": float(sample.momentum[0]),
                "momentum_y": float(sample.momentum[1]),
                "momentum_z": float(sample.momentum[2]),
                "momentum_norm": sample.momentum_norm,
            }
        )
    return rows


def _region_summary(rows: list[dict[str, float | int | str]]) -> dict[str, object]:
    summary: dict[str, object] = {}
    for region in _REGION_CODE:
        selected = [row for row in rows if row["region"] == region]
        h_values = np.abs([float(row["hamiltonian"]) for row in selected])
        m_values = np.asarray([float(row["momentum_norm"]) for row in selected])
        summary[region] = {
            "count": len(selected),
            "hamiltonian_l1": float(np.mean(h_values)),
            "hamiltonian_l2": float(np.sqrt(np.mean(h_values * h_values))),
            "hamiltonian_max_abs": float(np.max(h_values)),
            "momentum_l2": float(np.sqrt(np.mean(m_values * m_values))),
            "momentum_max": float(np.max(m_values)),
        }
    return summary


def run_validation(*, stencil_step: float = 0.04) -> dict[str, object]:
    separations = (10.0, 20.0, 40.0)
    phases = (0.0, 0.25 * math.pi)
    rows = _constraint_rows(
        separations=separations, phases=phases, stencil_step=stencil_step
    )
    regions = _region_summary(rows)

    provider = SuperposedKerrSchildBBHProvider()
    derivative_point = np.array([2.0, 5.0, 1.7])
    derivative_time = 3.4
    derivative_complex = provider.sample(derivative_time, derivative_point).d_g_inv
    derivative_finite = finite_difference_inverse_metric_derivatives(
        provider, derivative_time, derivative_point, relative_step=2.0e-5
    )
    derivative_max_abs = float(np.max(np.abs(derivative_complex - derivative_finite)))

    exchange_time = 0.37 * provider.orbit.period
    exchange_point = np.array([3.0, -5.0, 1.2])
    exchange_metric = provider.covariant_metric(exchange_time, exchange_point)
    exchanged = provider.covariant_metric(
        exchange_time + 0.5 * provider.orbit.period, -exchange_point
    )
    parity = np.diag([1.0, -1.0, -1.0, -1.0])
    exchange_max_abs = float(np.max(np.abs(exchanged - parity @ exchange_metric @ parity)))

    companion_norms = []
    for separation in (40.0, 80.0, 160.0):
        local_provider = SuperposedKerrSchildBBHProvider(
            FixedCircularBinaryOrbit(separation=separation)
        )
        holes = local_provider.hole_states(0.0)
        point = holes[0].position + np.array([0.0, 0.0, 2.0])
        perturbation, _ = boosted_schwarzschild_ks_perturbation(
            np.concatenate([[0.0], point]), holes[1]
        )
        companion_norms.append(float(np.linalg.norm(perturbation)))
    isolated_ratios = [
        companion_norms[index] / companion_norms[index + 1]
        for index in range(len(companion_norms) - 1)
    ]

    convergence_point = np.array([0.0, 3.0, 1.0])
    coarse = adm_constraint_sample(provider, 0.0, convergence_point, stencil_step=0.08)
    fine = adm_constraint_sample(provider, 0.0, convergence_point, stencil_step=0.04)
    convergence_relative_change = abs(fine.hamiltonian - coarse.hamiltonian) / abs(
        fine.hamiltonian
    )

    far_rows = [row for row in rows if row["region"] == "far"]
    far_h = np.abs([float(row["hamiltonian"]) for row in far_rows])
    far_slopes = [
        float(math.log(far_h[index + 1] / far_h[index], 2.0))
        for index in range(len(far_h) - 1)
    ]

    gates = {
        "inverse_derivatives_lt_2e_8": derivative_max_abs < 2.0e-8,
        "exchange_symmetry_lt_1e_12": exchange_max_abs < 1.0e-12,
        "isolated_companion_scales_inverse_distance": all(
            1.8 < ratio < 2.2 for ratio in isolated_ratios
        ),
        "constraint_stencil_converged": convergence_relative_change < 0.1,
        "near_hole_hamiltonian_below_source_scale": (
            regions["near_hole"]["hamiltonian_max_abs"] < 0.2  # type: ignore[index]
        ),
        "bridge_hamiltonian_below_source_scale": (
            regions["bridge"]["hamiltonian_max_abs"] < 1.0e-2  # type: ignore[index]
        ),
        "far_hamiltonian_below_1e_4": (
            regions["far"]["hamiltonian_max_abs"] < 1.0e-4  # type: ignore[index]
        ),
        "far_hamiltonian_falls_at_least_r_cubed": all(
            slope < -3.0 for slope in far_slopes
        ),
    }
    return {
        "schema": "gr-bh-xr.bbh.constraints.v1",
        "provider": {
            "source_revision": provider.source_revision,
            "evidence_label": provider.evidence_label,
            "coordinates": "global Cartesian superposed Kerr-Schild",
            "signature": "(-,+,+,+)",
            "metric_equation": "Combi-Ressler 2024 Eq. 11",
            "orbit": "equal-mass nonspinning fixed-separation Newtonian circular",
            "worldtube_factor_per_hole_mass": provider.worldtube_factor,
        },
        "configuration": {
            "separations": list(separations),
            "phases": list(phases),
            "stencil_step": stencil_step,
        },
        "threshold_provenance": {
            "source": "Combi-Ressler 2024 Sec. III.A.3 and Fig. 2",
            "near_hole_reported_scale": "1e-1 to 1e-2",
            "bridge_reported_scale": "about 1e-3",
            "far_reported_falloff": "about r^-4",
            "note": "Broad gates were preregistered from source scales; numerical values remain approximation diagnostics.",
        },
        "inverse_derivative_max_abs_difference": derivative_max_abs,
        "exchange_symmetry_max_abs_difference": exchange_max_abs,
        "isolated_companion_norms": companion_norms,
        "isolated_companion_doubling_ratios": isolated_ratios,
        "constraint_convergence_relative_change": convergence_relative_change,
        "far_hamiltonian_log2_slopes": far_slopes,
        "regions": regions,
        "samples": rows,
        "gates": gates,
        "pass": all(gates.values()),
    }


def write_hdf5(path: Path, result: dict[str, object]) -> None:
    samples = result["samples"]
    assert isinstance(samples, list)
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as handle:
        handle.attrs["schema"] = result["schema"]
        provider = result["provider"]
        assert isinstance(provider, dict)
        for key, value in provider.items():
            handle.attrs[key] = value
        for key in (
            "separation",
            "phase",
            "time",
            "x",
            "y",
            "z",
            "hamiltonian",
            "momentum_x",
            "momentum_y",
            "momentum_z",
            "momentum_norm",
        ):
            handle.create_dataset(key, data=[float(row[key]) for row in samples])
        handle.create_dataset(
            "region_code", data=[_REGION_CODE[str(row["region"])] for row in samples]
        )
        for name, code in _REGION_CODE.items():
            handle["region_code"].attrs[name] = code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stencil-step", type=float, default=0.04)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--h5", type=Path)
    args = parser.parse_args()
    result = run_validation(stencil_step=args.stencil_step)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.h5 is not None:
        write_hdf5(args.h5, result)
    print(json.dumps(result, indent=2))
    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

