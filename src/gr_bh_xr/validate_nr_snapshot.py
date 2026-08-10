"""Generate and validate synthetic ADM-snapshot schema gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from .dynamic_metric import MinkowskiMetricProvider, StationaryKerrSchildProvider
from .metrics import ADMMetricSnapshotProvider, PlaneGWMetricProvider, PlaneGWParameters
from .nr_snapshot import (
    NRADMSnapshot,
    default_synthetic_metadata,
    inspect_nr_asset,
    load_nr_snapshot,
    sample_provider_level,
    write_nr_snapshot,
)
from .types import MetricParams


SCHEMA = "gr-bh-xr.bbh.adm-snapshot-validation.v1"


def validate_nr_snapshot_gate(
    output_dir: Path | str,
    *,
    out: Path | str | None = None,
    producer_commit: str = "working-tree",
) -> dict[str, Any]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260810)

    minkowski = MinkowskiMetricProvider()
    minkowski_snapshot = _snapshot(
        minkowski,
        axes=np.linspace(-2.0, 2.0, 5),
        times=np.array([-1.0, 1.0]),
        error=0.0,
        case="minkowski",
        producer_commit=producer_commit,
    )
    minkowski_path = write_nr_snapshot(directory / "minkowski.h5", minkowski_snapshot)
    minkowski_loaded = ADMMetricSnapshotProvider.from_hdf5(minkowski_path)
    minkowski_metric_error = 0.0
    minkowski_derivative_error = 0.0
    for event in rng.uniform(-0.8, 0.8, size=(24, 4)):
        sample = minkowski_loaded.sample(float(event[0]), event[1:4])
        minkowski_metric_error = max(
            minkowski_metric_error,
            float(np.max(np.abs(sample.g_inv - np.diag([-1.0, 1.0, 1.0, 1.0])))),
        )
        minkowski_derivative_error = max(
            minkowski_derivative_error, float(np.max(np.abs(sample.d_g_inv)))
        )

    plane = PlaneGWMetricProvider(
        PlaneGWParameters(
            amplitude=0.02,
            angular_frequency=1.1,
            polarization_angle=0.23,
        )
    )
    plane_probes = rng.uniform(-0.8, 0.8, size=(32, 4))
    plane_probes[:, 0] *= 0.5
    plane_metrics: list[float] = []
    plane_derivatives: list[float] = []
    plane_reported_bounds: list[float] = []
    plane_paths: list[str] = []
    for count in (7, 13):
        path = write_nr_snapshot(
            directory / f"plane_gw_{count}.h5",
            _snapshot(
                plane,
                axes=np.linspace(-1.0, 1.0, count),
                times=np.linspace(-0.5, 0.5, count),
                error=0.1,
                case=f"plane_gw_{count}",
                producer_commit=producer_commit,
            ),
        )
        plane_paths.append(str(path.resolve()))
        provider = ADMMetricSnapshotProvider.from_hdf5(path)
        metric_errors = []
        derivative_errors = []
        reported = []
        for probe in plane_probes:
            exact = plane.sample(float(probe[0]), probe[1:4])
            sampled = provider.sample(float(probe[0]), probe[1:4])
            metric_errors.append(float(np.max(np.abs(sampled.g_inv - exact.g_inv))))
            derivative_errors.append(
                float(np.max(np.abs(sampled.d_g_inv - exact.d_g_inv)))
            )
            reported.append(sampled.interpolation_error)
        plane_metrics.append(float(np.sqrt(np.mean(np.square(metric_errors)))))
        plane_derivatives.append(
            float(np.sqrt(np.mean(np.square(derivative_errors))))
        )
        plane_reported_bounds.append(float(min(reported)))

    kerr_params = MetricParams(M=1.0, a=0.5)
    kerr = StationaryKerrSchildProvider(kerr_params)
    kerr_level = sample_provider_level(
        kerr,
        times=(-1.0, 1.0),
        axes=(np.linspace(4.0, 8.0, 5), np.linspace(-1.0, 1.0, 5), np.linspace(-1.0, 1.0, 5)),
        spatial_error_bound=(0.1, 0.1),
    )
    kerr_snapshot = NRADMSnapshot(
        times=np.array([-1.0, 1.0]),
        levels=(kerr_level,),
        temporal_error_bound=np.array([0.0]),
        metadata=_metadata("kerr", producer_commit),
    )
    kerr_path = write_nr_snapshot(directory / "kerr.h5", kerr_snapshot)
    kerr_loaded = ADMMetricSnapshotProvider.from_hdf5(kerr_path)
    kerr_metric_error = 0.0
    kerr_inverse_identity_error = 0.0
    for point in (
        np.array([5.0, -0.5, 0.5]),
        np.array([6.0, 0.0, 0.0]),
        np.array([7.0, 0.5, -0.5]),
    ):
        exact = kerr.sample(0.0, point)
        sampled = kerr_loaded.sample(0.37, point)
        kerr_metric_error = max(
            kerr_metric_error, float(np.max(np.abs(sampled.g_inv - exact.g_inv)))
        )
        kerr_inverse_identity_error = max(
            kerr_inverse_identity_error,
            float(np.max(np.abs(sampled.g_cov @ sampled.g_inv - np.eye(4)))),
        )

    amr_snapshot = _amr_snapshot(producer_commit)
    amr_provider = ADMMetricSnapshotProvider(amr_snapshot)
    amr_levels = [
        amr_provider.sample_with_provenance(0.5, np.zeros(3)).level_id,
        amr_provider.sample_with_provenance(0.5, np.array([0.9, 0.0, 0.0])).level_id,
        amr_provider.sample_with_provenance(0.5, np.array([2.1, 0.0, 0.0])).level_id,
    ]

    waveform_path = directory / "waveform_only.h5"
    with h5py.File(waveform_path, "w") as handle:
        group = handle.create_group("Extrapolated_N2.dir")
        group.create_dataset("Y_l2_m2.dat", data=np.zeros((4, 3)))
    waveform_inspection = inspect_nr_asset(waveform_path)

    metric_order = plane_metrics[0] / plane_metrics[1]
    derivative_order = plane_derivatives[0] / plane_derivatives[1]
    max_observed_plane_error = max(plane_metrics + plane_derivatives)
    minimum_declared_bound = min(plane_reported_bounds)
    passed = bool(
        minkowski_metric_error < 1.0e-14
        and minkowski_derivative_error < 1.0e-14
        and metric_order > 3.0
        and derivative_order > 1.7
        and max_observed_plane_error < minimum_declared_bound
        and kerr_metric_error < 1.0e-12
        and kerr_inverse_identity_error < 1.0e-12
        and amr_levels == [1, 0, None]
        and not waveform_inspection.compatible
        and waveform_inspection.reason_code == "waveform_only_asset"
    )
    summary: dict[str, Any] = {
        "schema": SCHEMA,
        "producer_commit": producer_commit,
        "artifacts": {
            "minkowski": str(minkowski_path.resolve()),
            "plane_gw": plane_paths,
            "kerr": str(kerr_path.resolve()),
            "waveform_only_probe": str(waveform_path.resolve()),
        },
        "minkowski_metric_max_abs_error": minkowski_metric_error,
        "minkowski_derivative_max_abs_error": minkowski_derivative_error,
        "plane_gw_metric_rms_errors": plane_metrics,
        "plane_gw_derivative_rms_errors": plane_derivatives,
        "plane_gw_metric_convergence_ratio": metric_order,
        "plane_gw_derivative_convergence_ratio": derivative_order,
        "plane_gw_minimum_reported_error_bound": minimum_declared_bound,
        "kerr_node_metric_max_abs_error": kerr_metric_error,
        "kerr_inverse_identity_max_abs_error": kerr_inverse_identity_error,
        "amr_selected_levels": amr_levels,
        "waveform_only_rejection": waveform_inspection.as_dict(),
        "thresholds": {
            "minkowski_metric_max_abs_error": 1.0e-14,
            "minkowski_derivative_max_abs_error": 1.0e-14,
            "plane_gw_metric_convergence_ratio_min": 3.0,
            "plane_gw_derivative_convergence_ratio_min": 1.7,
            "kerr_node_metric_max_abs_error": 1.0e-12,
            "kerr_inverse_identity_max_abs_error": 1.0e-12,
        },
        "passed": passed,
    }
    if out is not None:
        output = Path(out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
        summary["out_json"] = str(output.resolve())
    return summary


def _snapshot(provider, *, axes, times, error, case, producer_commit):
    level = sample_provider_level(
        provider,
        times=times,
        axes=(axes, axes, axes),
        spatial_error_bound=np.full(len(times), error),
    )
    return NRADMSnapshot(
        times=np.asarray(times),
        levels=(level,),
        temporal_error_bound=np.full(len(times) - 1, error),
        metadata=_metadata(case, producer_commit),
    )


def _metadata(case: str, producer_commit: str) -> dict[str, Any]:
    metadata = default_synthetic_metadata(producer_commit=producer_commit)
    metadata["validation_case"] = case
    return metadata


def _amr_snapshot(producer_commit: str) -> NRADMSnapshot:
    provider = MinkowskiMetricProvider()
    times = np.array([0.0, 1.0])
    coarse = sample_provider_level(
        provider, times=times, axes=(np.linspace(-2, 2, 5),) * 3, level_id=0
    )
    fine = sample_provider_level(
        provider,
        times=times,
        axes=(np.linspace(-1, 1, 5),) * 3,
        level_id=1,
        parent_level=0,
        valid_lower=(-0.75, -0.75, -0.75),
        valid_upper=(0.75, 0.75, 0.75),
    )
    return NRADMSnapshot(
        times=times,
        levels=(coarse, fine),
        temporal_error_bound=np.array([0.0]),
        metadata=_metadata("amr_selection", producer_commit),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--producer-commit", default="working-tree")
    args = parser.parse_args()
    summary = validate_nr_snapshot_gate(
        args.output_dir, out=args.out, producer_commit=args.producer_commit
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
