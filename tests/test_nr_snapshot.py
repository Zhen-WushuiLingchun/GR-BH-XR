import json
import importlib.util
from pathlib import Path

import h5py
import numpy as np
import pytest

from gr_bh_xr.convert_carpetx_snapshot import convert_carpetx_snapshot
from gr_bh_xr.dynamic_metric import MinkowskiMetricProvider, StationaryKerrSchildProvider
from gr_bh_xr.metric_ks import ks_inverse_metric, ks_metric
from gr_bh_xr.metrics import ADMMetricSnapshotProvider, PlaneGWMetricProvider, PlaneGWParameters
from gr_bh_xr.nr_snapshot import (
    ADMSnapshotLevel,
    NRADMSnapshot,
    SCHEMA,
    SnapshotCompatibilityError,
    default_synthetic_metadata,
    inspect_nr_asset,
    load_nr_snapshot,
    sample_provider_level,
    write_nr_snapshot,
)
from gr_bh_xr.types import MetricParams


NR_RAY_SCRIPT = (
    Path(__file__).parents[1]
    / "nr"
    / "einstein_toolkit"
    / "validate_nr_pilot_rays.py"
)
NR_RAY_SPEC = importlib.util.spec_from_file_location(
    "validate_nr_pilot_rays", NR_RAY_SCRIPT
)
assert NR_RAY_SPEC is not None and NR_RAY_SPEC.loader is not None
NR_RAY_MODULE = importlib.util.module_from_spec(NR_RAY_SPEC)
NR_RAY_SPEC.loader.exec_module(NR_RAY_MODULE)


def _single_level_snapshot(provider, axes, *, times=(-0.5, 0.5), error=0.0):
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
        metadata=default_synthetic_metadata(),
    )


def test_minkowski_snapshot_round_trip_and_checksums(tmp_path: Path) -> None:
    snapshot = _single_level_snapshot(MinkowskiMetricProvider(), np.linspace(-1, 1, 3))
    path = write_nr_snapshot(tmp_path / "minkowski.h5", snapshot)
    loaded = load_nr_snapshot(path)
    sample = ADMMetricSnapshotProvider(loaded).sample(0.2, np.array([0.2, -0.3, 0.4]))

    assert sample.validity == "valid"
    np.testing.assert_array_equal(sample.g_cov, np.diag([-1.0, 1.0, 1.0, 1.0]))
    np.testing.assert_array_equal(sample.g_inv, sample.g_cov)
    np.testing.assert_array_equal(sample.d_g_inv, np.zeros((4, 4, 4)))
    with h5py.File(path, "r+") as handle:
        handle["levels/0/lapse"][0, 0, 0, 0] = 1.25
    with pytest.raises(SnapshotCompatibilityError, match="Checksum mismatch") as error:
        load_nr_snapshot(path)
    assert error.value.reason_code == "checksum_mismatch"


def test_plane_wave_interpolation_converges_at_expected_order(tmp_path: Path) -> None:
    analytic = PlaneGWMetricProvider(
        PlaneGWParameters(amplitude=0.02, angular_frequency=1.1, polarization_angle=0.23)
    )
    probes = np.random.default_rng(20260810).uniform(-0.8, 0.8, size=(24, 4))
    probes[:, 0] *= 0.5
    errors = []
    derivative_errors = []
    for count in (7, 13):
        axes = np.linspace(-1.0, 1.0, count)
        times = np.linspace(-0.5, 0.5, count)
        path = write_nr_snapshot(
            tmp_path / f"plane_{count}.h5",
            _single_level_snapshot(analytic, axes, times=times, error=0.1),
        )
        provider = ADMMetricSnapshotProvider.from_hdf5(path)
        metric_probe_errors = []
        derivative_probe_errors = []
        for probe in probes:
            exact = analytic.sample(float(probe[0]), probe[1:4])
            sample = provider.sample(float(probe[0]), probe[1:4])
            metric_probe_errors.append(float(np.max(np.abs(sample.g_inv - exact.g_inv))))
            derivative_probe_errors.append(
                float(np.max(np.abs(sample.d_g_inv - exact.d_g_inv)))
            )
            assert sample.interpolation_error == pytest.approx(0.2)
        errors.append(float(np.sqrt(np.mean(np.square(metric_probe_errors)))))
        derivative_errors.append(
            float(np.sqrt(np.mean(np.square(derivative_probe_errors))))
        )

    assert errors[0] / errors[1] > 3.0
    assert derivative_errors[0] / derivative_errors[1] > 1.7


def test_sampled_kerr_metric_round_trip(tmp_path: Path) -> None:
    params = MetricParams(M=1.0, a=0.5)
    analytic = StationaryKerrSchildProvider(params)
    axes_x = np.linspace(4.0, 8.0, 5)
    axes_yz = np.linspace(-1.0, 1.0, 5)
    level = sample_provider_level(
        analytic,
        times=(-1.0, 1.0),
        axes=(axes_x, axes_yz, axes_yz),
        spatial_error_bound=(0.1, 0.1),
    )
    snapshot = NRADMSnapshot(
        times=np.array([-1.0, 1.0]),
        levels=(level,),
        temporal_error_bound=np.array([0.0]),
        metadata=default_synthetic_metadata(),
    )
    path = write_nr_snapshot(tmp_path / "kerr.h5", snapshot)
    point = np.array([6.0, 0.0, 0.0])
    sample = ADMMetricSnapshotProvider.from_hdf5(path).sample(0.3, point)

    np.testing.assert_allclose(sample.g_cov, ks_metric(params, point), rtol=0.0, atol=3e-15)
    np.testing.assert_allclose(
        sample.g_inv, ks_inverse_metric(params, point), rtol=0.0, atol=3e-15
    )
    np.testing.assert_allclose(sample.g_cov @ sample.g_inv, np.eye(4), atol=3e-15)


def test_amr_level_selection_respects_declared_valid_bounds() -> None:
    provider = MinkowskiMetricProvider()
    times = (0.0, 1.0)
    coarse = sample_provider_level(
        provider,
        times=times,
        axes=(np.linspace(-2, 2, 5),) * 3,
        level_id=0,
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
    snapshot = NRADMSnapshot(
        times=np.array(times),
        levels=(coarse, fine),
        temporal_error_bound=np.array([0.0]),
        metadata=default_synthetic_metadata(),
    )
    provider_snapshot = ADMMetricSnapshotProvider(snapshot)

    assert provider_snapshot.sample_with_provenance(0.5, np.zeros(3)).level_id == 1
    assert provider_snapshot.sample_with_provenance(0.5, np.array([0.9, 0, 0])).level_id == 0
    outside = provider_snapshot.sample_with_provenance(0.5, np.array([2.1, 0, 0]))
    assert outside.level_id is None
    assert outside.metric_sample.validity == "outside_domain"


def test_waveform_only_asset_is_rejected_structurally(tmp_path: Path) -> None:
    path = tmp_path / "sxs_waveform.h5"
    with h5py.File(path, "w") as handle:
        group = handle.create_group("Extrapolated_N2.dir")
        group.create_dataset("Y_l2_m2.dat", data=np.zeros((4, 3)))
    inspection = inspect_nr_asset(path)
    assert not inspection.compatible
    assert inspection.reason_code == "waveform_only_asset"
    with pytest.raises(SnapshotCompatibilityError) as error:
        load_nr_snapshot(path)
    assert error.value.reason_code == "waveform_only_asset"


def test_schema_without_provenance_or_checksums_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "unprovenanced.h5"
    with h5py.File(path, "w") as handle:
        handle.attrs["schema"] = SCHEMA
        handle.create_dataset("times", data=[0.0, 1.0])
        handle.create_dataset("temporal_error_bound", data=[0.0])
        handle.create_group("levels")
    inspection = inspect_nr_asset(path)
    assert not inspection.compatible
    assert inspection.reason_code == "missing_provenance"


def test_explicit_carpetx_field_map_conversion(tmp_path: Path) -> None:
    source = tmp_path / "producer.h5"
    shape = (2, 2, 2, 2)
    with h5py.File(source, "w") as handle:
        handle.create_dataset("time", data=[0.0, 1.0])
        handle.create_dataset("alpha", data=np.ones(shape))
        for axis in "xyz":
            handle.create_dataset(f"beta_{axis}", data=np.zeros(shape))
        for i in range(3):
            for j in range(3):
                handle.create_dataset(
                    f"gamma_{i}{j}", data=np.full(shape, 1.0 if i == j else 0.0)
                )
                handle.create_dataset(
                    f"extrinsic_{i}{j}", data=np.full(shape, 0.1 * (i + j + 1))
                )
    field_map = {
        "times": "/time",
        "temporal_error_bound": [0.0],
        "levels": [
            {
                "level_id": 0,
                "parent_level": None,
                "origin": [-1.0, -1.0, -1.0],
                "spacing": [2.0, 2.0, 2.0],
                "valid_lower": [-1.0, -1.0, -1.0],
                "valid_upper": [1.0, 1.0, 1.0],
                "lapse": "/alpha",
                "shift": ["/beta_x", "/beta_y", "/beta_z"],
                "gamma_cov": [
                    [f"/gamma_{i}{j}" for j in range(3)] for i in range(3)
                ],
                "extrinsic_curvature": [
                    [f"/extrinsic_{i}{j}" for j in range(3)] for i in range(3)
                ],
                "spatial_error_bound": [0.0, 0.0],
            }
        ],
    }
    out = convert_carpetx_snapshot(
        source,
        tmp_path / "converted.h5",
        field_map=field_map,
        metadata=default_synthetic_metadata(producer_commit="carpetx-test"),
    )
    with h5py.File(out, "r") as handle:
        assert handle.attrs["schema"] == SCHEMA
        metadata = json.loads(handle.attrs["metadata_json"])
        assert metadata["conversion"]["tool"] == "gr_bh_xr.convert_carpetx_snapshot"
        assert len(metadata["conversion"]["input_sha256"]) == 64
        assert "levels/0/extrinsic_curvature" in handle
    loaded = load_nr_snapshot(out)
    assert loaded.levels[0].extrinsic_curvature is not None
    assert loaded.levels[0].extrinsic_curvature.shape == shape + (3, 3)
    sample = ADMMetricSnapshotProvider.from_hdf5(out).sample(0.5, np.zeros(3))
    assert sample.validity == "valid"
    np.testing.assert_array_equal(sample.g_cov, np.diag([-1.0, 1.0, 1.0, 1.0]))


def test_frozen_nr_slice_camera_and_ray_gate_match_identical_flat_snapshots(
    tmp_path: Path,
) -> None:
    snapshot = _single_level_snapshot(
        MinkowskiMetricProvider(), np.linspace(-2.0, 2.0, 5), times=(0.0, 1.0)
    )
    low = write_nr_snapshot(tmp_path / "low.h5", snapshot)
    high = write_nr_snapshot(tmp_path / "high.h5", snapshot)
    report, buffers = NR_RAY_MODULE.validate_nr_pilot_rays(
        low,
        high,
        grid=3,
        screen_half_width=0.1,
        observer_radius_M=0.5,
        capture_radius_M=0.1,
        escape_radius_M=1.5,
        max_lambda=5.0,
    )

    assert report["accepted"]
    assert report["event_agreement"] == 1.0
    assert report["counts"]["invalid_or_budget_pairs"] == 0
    assert report["escape_direction_error_rad"]["max"] < 3.0e-8
    assert buffers["ray_coordinates"].shape == (18, 3)
