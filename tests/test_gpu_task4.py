from __future__ import annotations

import math

import h5py
import numpy as np
import pytest

from gr_bh_xr.generate_lens_map import EVENT_CODES, FAILURE_CODES
from gr_bh_xr.geodesic import trace_ray
from gr_bh_xr.gpu.backend import backend_info, select_vulkan_adapter
from gr_bh_xr.gpu.benchmark_latency import _case_summary, build_parser
from gr_bh_xr.gpu.generate_lens_map import generate_gpu_lens_map
from gr_bh_xr.gpu.generate_transfer_cubemap import generate_transfer_cubemap
from gr_bh_xr.gpu.preview import preview_envelope_warning
from gr_bh_xr.gpu.trace import GpuTraceConfig, trace_screen_points, trace_unity_direction_points
from gr_bh_xr.gpu.trace_ks import KsGpuTraceConfig, ks_states_from_screen_points, trace_ks_states
from gr_bh_xr.gpu.validate import validate_cpu_vs_gpu
from gr_bh_xr.gpu.validate_disk_transfer import validate_disk_transfer_cpu_vs_gpu
from gr_bh_xr.gpu.validate_full_sky_transfer import validate_full_sky_transfer
from gr_bh_xr.gpu.validate_ks import validate_ks_gpu
from gr_bh_xr.types import CameraConfig, MetricParams, TraceConfig


def _require_vulkan_adapter():
    pytest.importorskip("wgpu")
    try:
        return select_vulkan_adapter()
    except RuntimeError as exc:
        pytest.skip(str(exc))


def test_gpu_backend_finds_vulkan_adapter():
    adapter = _require_vulkan_adapter()
    info = backend_info(adapter)

    assert info.ready
    assert info.backend == "wgpu"
    assert info.requested_backend == "vulkan"
    assert info.backend_type.lower() == "vulkan"
    assert info.adapter_name


def test_gpu_preview_warns_outside_documented_envelope():
    assert preview_envelope_warning(0.5, 60.0) == ""
    assert "outside f32 preview envelope" in preview_envelope_warning(0.95, 5.0)
    assert "outside f32 preview envelope" in preview_envelope_warning(0.99, 60.0)


def test_gpu_latency_case_summary_reports_pixels_per_second():
    summary = _case_summary(
        16,
        2,
        [10.0, 20.0],
        {"event_counts": {"capture": 1}, "failure_counts": {"none": 256}},
    )

    assert summary["grid"] == 16
    assert summary["pixels"] == 256
    assert summary["elapsed_ms_median"] == 15.0
    assert summary["pixels_per_second_median"] == pytest.approx(256.0 / 0.015)
    assert summary["event_counts"]["capture"] == 1


def test_gpu_latency_parser_accepts_grid_list():
    args = build_parser().parse_args(
        [
            "--spin",
            "0.9",
            "--inclination-deg",
            "60",
            "--grids",
            "256",
            "512",
            "--iterations",
            "2",
        ]
    )

    assert args.spin == pytest.approx(0.9)
    assert args.inclination_deg == pytest.approx(60.0)
    assert args.grids == [256, 512]
    assert args.iterations == 2


def test_gpu_unity_direction_points_capture_and_escape():
    _require_vulkan_adapter()
    config = GpuTraceConfig(
        params=MetricParams(M=1.0, a=0.0),
        inclination_deg=60.0,
        grid=2,
        alpha_max=8.0,
        beta_max=8.0,
        r_obs=80.0,
        step_size=0.05,
        steps=4000,
        critical_refine_band=0.0,
    )
    result = trace_unity_direction_points(
        config,
        np.asarray(
            [
                [0.0, 0.0, 1.0],
                [0.0, 0.0, -1.0],
            ],
            dtype=np.float32,
        ),
    )

    assert result["event_code"][0] == EVENT_CODES["capture"]
    assert result["event_code"][1] == EVENT_CODES["escape"]
    assert np.all(result["failure_code"] == FAILURE_CODES["none"])


def test_gpu_kerr_schild_states_capture_and_escape():
    _require_vulkan_adapter()
    params = MetricParams(M=1.0, a=0.0)
    states = ks_states_from_screen_points(
        params=params,
        inclination_deg=90.0,
        r_obs=100.0,
        alpha=np.asarray([0.0, 8.0], dtype=np.float64),
        beta=np.asarray([0.0, 0.0], dtype=np.float64),
    )
    result = trace_ks_states(
        KsGpuTraceConfig(
            params=params,
            step_size=0.05,
            steps=8000,
            r_escape=200.0,
            horizon_eps=0.3,
        ),
        states,
    )

    assert result["event_code"].tolist() == [EVENT_CODES["capture"], EVENT_CODES["escape"]]
    assert np.all(result["failure_code"] == FAILURE_CODES["none"])
    assert float(result["h_max_abs"][1]) < 1.0e-4


def test_gpu_kerr_schild_validator_writes_summary_and_h5(tmp_path):
    _require_vulkan_adapter()
    out = tmp_path / "ks_gpu_compare.json"
    h5 = tmp_path / "ks_gpu_compare.h5"

    summary = validate_ks_gpu(
        params=MetricParams(M=1.0, a=0.9),
        inclination_deg=60.0,
        r_obs=100.0,
        fan_samples=5,
        fan_alpha_max=8.0,
        fan_betas=(0.0,),
        full_sky_samples=6,
        step_size=0.05,
        steps=4000,
        horizon_eps=0.3,
        out=out,
        h5=h5,
        command="pytest ks gpu validator",
    )

    assert summary["schema"] == "gr-bh-xr.tier2.ks_gpu_validation.v1"
    assert summary["stable_event_agreement"] >= 0.98
    assert summary["gpu_failure_outside_exclusions"] == 0
    assert out.exists()
    with h5py.File(h5, "r") as handle:
        assert handle.attrs["schema"] == "gr-bh-xr.tier2.ks_gpu_validation.v1"
        assert handle["gpu_final_x"].shape[1] == 4
        assert handle["gpu_final_p"].shape[1] == 4
        assert "gpu_h_max_abs" in handle


def test_gpu_full_sky_transfer_cubemap_writes_boundary_free_package(tmp_path):
    _require_vulkan_adapter()
    out_dir = tmp_path / "full_sky_cube"

    summary = generate_transfer_cubemap(
        params=MetricParams(M=1.0, a=0.0),
        inclination_deg=90.0,
        face_size=4,
        out_dir=out_dir,
        r_obs=80.0,
        step_size=0.05,
        steps=8000,
        horizon_eps=0.3,
        chunk_size=32,
        command="pytest full sky cubemap",
    )

    assert summary["schema"] == "gr-bh-xr.task5.full_sky_transfer_cubemap.v1"
    assert summary["faceSize"] == 4
    assert summary["totalPixels"] == 6 * 4 * 4
    assert summary["validEscapePixels"] > 0
    assert summary["diskTransfer"]["orderCount"] == 2
    assert summary["diskTransfer"]["channels"] == "r_m, sin(phi_m), cos(phi_m), g_m"
    assert "no alpha/beta window fallback" in summary["boundaryNote"]
    assert (out_dir / "full_sky_transfer_metadata.json").exists()
    assert (out_dir / "event_cube_rgba8.bytes").stat().st_size == 6 * 4 * 4 * 4
    assert (out_dir / "escape_dir_unity_cube_rgba32f.bytes").stat().st_size == 6 * 4 * 4 * 16
    assert (out_dir / "disk_order0_transfer_cube_rgba16f.bytes").stat().st_size == 6 * 4 * 4 * 4 * 2
    assert (out_dir / "disk_order1_transfer_cube_rgba16f.bytes").stat().st_size == 6 * 4 * 4 * 4 * 2


def test_gpu_full_sky_tetrad_validator_matches_cpu_reference(tmp_path):
    _require_vulkan_adapter()
    out = tmp_path / "fullsky_compare.json"
    h5_path = tmp_path / "fullsky_compare.h5"

    summary = validate_full_sky_transfer(
        params=MetricParams(M=1.0, a=0.0),
        inclination_deg=90.0,
        samples=24,
        r_obs=80.0,
        step_size=0.05,
        steps=8000,
        horizon_eps=0.3,
        out=out,
        h5=h5_path,
        command="pytest full-sky cpu gpu",
    )

    assert out.exists()
    assert h5_path.exists()
    assert summary["cpu_event_counts"]["capture"] > 0
    assert summary["cpu_event_counts"]["escape"] > 0
    assert summary["gpu_event_counts"]["capture"] > 0
    assert summary["gpu_event_counts"]["escape"] > 0
    assert summary["stable_event_agreement"] >= 0.98
    assert summary["gpu_failure_outside_exclusions"] == 0
    assert summary["escape_direction_median_error_rad"] < 1.0e-4

    with h5py.File(h5_path, "r") as handle:
        assert handle.attrs["schema"] == "gr-bh-xr.task5.full_sky_cpu_gpu_validation.v1"
        for dataset in (
            "direction_unity",
            "cpu_event_code",
            "cpu_failure_code",
            "cpu_min_r",
            "cpu_escape_dir",
            "gpu_event_code",
            "gpu_failure_code",
            "gpu_final_r",
            "gpu_escape_dir",
            "stable_comparison_mask",
            "full_grid_event_agreement_mask",
            "excluded_near_capture",
            "escape_direction_error_rad",
        ):
            assert dataset in handle


def test_gpu_schwarzschild_lens_map_schema_and_events(tmp_path):
    _require_vulkan_adapter()
    out = tmp_path / "gpu_lensmap_schwarzschild.h5"

    summary = generate_gpu_lens_map(
        params=MetricParams(M=1.0, a=0.0),
        inclination_deg=90.0,
        grid=17,
        alpha_max=8.0,
        beta_max=8.0,
        r_obs=50.0,
        step_size=0.05,
        steps=8000,
        horizon_eps=0.3,
        out=out,
        command="pytest gpu smoke",
    )

    assert summary["event_counts"]["capture"] > 0
    assert summary["event_counts"]["escape"] > 0
    assert summary["failure_counts"]["solver_failure"] == 0
    with h5py.File(out, "r") as handle:
        assert handle.attrs["schema"] == "gr-bh-xr.phase2.gpu_lens_map.v3"
        assert handle.attrs["backend"] == "wgpu"
        assert handle.attrs["requested_backend"] == "vulkan"
        assert handle.attrs["precision"] == "f32"
        assert handle.attrs["rk_method"] == "fixed_step_rk4"
        for dataset in (
            "alpha",
            "beta",
            "gpu_event_code",
            "gpu_failure_code",
            "gpu_min_r",
            "gpu_h_max_abs",
            "gpu_q_drift_abs",
            "gpu_steps",
            "gpu_refinement_level",
            "gpu_subpixel_capture_fraction",
            "gpu_subpixel_invalid_fraction",
            "gpu_escape_theta",
            "gpu_escape_phi",
            "gpu_escape_dir_x",
            "gpu_escape_dir_y",
            "gpu_escape_dir_z",
            "gpu_disk_r_m",
            "gpu_disk_phi_m",
            "gpu_disk_sin_phi_m",
            "gpu_disk_cos_phi_m",
            "gpu_disk_t_m",
            "gpu_disk_g_m",
            "event_rgba8",
            "debug_rgba8",
        ):
            assert dataset in handle
        assert handle["gpu_event_code"].shape == (17, 17)
        assert handle["gpu_refinement_level"].shape == (17, 17)
        assert handle["event_rgba8"].shape == (17, 17, 4)
        assert handle["gpu_disk_r_m"].shape == (2, 17, 17)
        assert handle["gpu_failure_code"].attrs["code_polar_step_overshoot"] == 5
        escape_mask = handle["gpu_event_code"][...] == EVENT_CODES["escape"]
        assert np.all(np.isfinite(handle["gpu_escape_theta"][...][escape_mask]))
        assert np.all(np.isfinite(handle["gpu_escape_phi"][...][escape_mask]))


def test_gpu_lens_map_records_first_two_disk_transfer_layers(tmp_path):
    _require_vulkan_adapter()
    out = tmp_path / "gpu_lensmap_disk_transfer.h5"

    summary = generate_gpu_lens_map(
        params=MetricParams(M=1.0, a=0.0),
        inclination_deg=80.0,
        grid=17,
        alpha_max=12.0,
        beta_max=12.0,
        r_obs=80.0,
        step_size=0.05,
        steps=12000,
        horizon_eps=0.3,
        out=out,
        command="pytest gpu disk transfer",
    )
    assert sum(summary["disk_valid_by_order"]) > 0

    with h5py.File(out, "r") as handle:
        assert handle.attrs["disk_r_in"] == pytest.approx(6.0)
        assert handle.attrs["disk_r_out"] == pytest.approx(30.0)
        disk_r = handle["gpu_disk_r_m"][...]
        disk_g = handle["gpu_disk_g_m"][...]
        finite = np.isfinite(disk_r)
        assert np.count_nonzero(finite) > 0
        assert np.nanmin(disk_r) >= 6.0
        assert np.nanmax(disk_r) <= 30.0
        assert np.all(np.isfinite(disk_g[finite]))
        assert np.nanmin(disk_g) > 0.0
        sin_phi = handle["gpu_disk_sin_phi_m"][...]
        cos_phi = handle["gpu_disk_cos_phi_m"][...]
        np.testing.assert_allclose(
            sin_phi[finite] * sin_phi[finite] + cos_phi[finite] * cos_phi[finite],
            1.0,
            atol=2.0e-6,
        )


def test_gpu_cpu_validator_writes_compare_hdf5_and_summary(tmp_path):
    _require_vulkan_adapter()
    out = tmp_path / "gpu_compare_schwarzschild.h5"

    summary = validate_cpu_vs_gpu(
        params=MetricParams(M=1.0, a=0.0),
        inclination_deg=90.0,
        grid=17,
        alpha_max=8.0,
        beta_max=8.0,
        r_obs=50.0,
        step_size=0.05,
        steps=8000,
        horizon_eps=0.3,
        critical_band=0.25,
        out=out,
        command="pytest gpu validator",
    )

    assert out.exists()
    assert out.with_suffix(".json").exists()
    assert summary["stable_event_agreement"] >= 0.98
    assert summary["full_grid_event_agreement"] >= 0.98
    assert summary["gpu_failure_outside_exclusions"] == 0
    assert summary["refined_pixels"] > 0
    with h5py.File(out, "r") as handle:
        for dataset in (
            "cpu_event_code",
            "cpu_failure_code",
            "cpu_min_r",
            "cpu_escape_theta",
            "cpu_escape_phi",
            "cpu_escape_dir_x",
            "cpu_escape_dir_y",
            "cpu_escape_dir_z",
            "gpu_refinement_level",
            "gpu_subpixel_capture_fraction",
            "gpu_subpixel_invalid_fraction",
            "gpu_escape_theta",
            "gpu_escape_phi",
            "gpu_escape_dir_x",
            "gpu_escape_dir_y",
            "gpu_escape_dir_z",
            "escape_direction_error_rad",
            "stable_comparison_mask",
            "full_grid_event_agreement_mask",
            "excluded_critical_band",
            "excluded_near_capture",
        ):
            assert dataset in handle


def test_gpu_disk_transfer_validator_matches_cpu_reference(tmp_path):
    _require_vulkan_adapter()
    out = tmp_path / "gpu_disk_compare_schwarzschild.h5"

    summary = validate_disk_transfer_cpu_vs_gpu(
        params=MetricParams(M=1.0, a=0.0),
        inclination_deg=80.0,
        grid=16,
        alpha_max=30.0,
        beta_max=30.0,
        r_obs=100.0,
        step_size=0.05,
        steps=12000,
        horizon_eps=0.3,
        critical_band=0.25,
        disk_edge_band=0.25,
        r_out=30.0,
        max_order=2,
        out=out,
        command="pytest gpu disk compare",
    )

    assert out.exists()
    assert out.with_suffix(".json").exists()
    assert summary["disk_compare_sample_count"] > 0
    assert summary["disk_validity_mismatch_count"] == 0
    assert summary["disk_r_max_abs_error"] < 1.0e-2
    assert summary["disk_g_max_abs_error"] < 1.0e-3
    assert summary["disk_phi_max_error_rad"] < 1.0e-3
    with h5py.File(out, "r") as handle:
        for dataset in (
            "cpu_disk_r_m",
            "cpu_disk_phi_m",
            "cpu_disk_t_m",
            "cpu_disk_g_m",
            "disk_compare_mask",
            "disk_validity_mismatch_mask",
            "disk_r_abs_error",
            "disk_phi_error_rad",
            "disk_t_abs_error",
            "disk_g_abs_error",
        ):
            assert dataset in handle
        assert handle.attrs["disk_transfer_comparison"] == "cpu_dop853_vs_gpu_f32_rk4"


def test_gpu_near_axis_points_match_cpu_arbitration():
    _require_vulkan_adapter()
    params = MetricParams(M=1.0, a=0.5)
    alpha_values = [
        0.0313725508749485,
        -0.0313725508749485,
        0.0313725508749485,
        0.0313725508749485,
        -0.0313725508749485,
        0.0313725508749485,
        -0.0313725508749485,
        0.0313725508749485,
        -0.0313725508749485,
        0.0313725508749485,
        -0.0313725508749485,
        0.0313725508749485,
        0.0313725508749485,
        -0.0313725508749485,
        -0.0313725508749485,
        0.0313725508749485,
        0.0313725508749485,
        -0.0313725508749485,
        -0.0313725508749485,
        0.0313725508749485,
        -0.0313725508749485,
        0.0313725508749485,
        -0.0313725508749485,
        0.0313725508749485,
        -0.0313725508749485,
        0.0313725508749485,
        -0.0313725508749485,
        -0.0313725508749485,
        0.0313725508749485,
    ]
    beta_values = [
        -5.615686416625977,
        -5.427451133728027,
        -5.427451133728027,
        -4.611764907836914,
        -3.7333333492279053,
        3.7333333492279053,
        3.9215686321258545,
        3.9215686321258545,
        4.047059059143066,
        4.047059059143066,
        4.172549247741699,
        4.172549247741699,
        4.298039436340332,
        4.360784530639648,
        4.486274719238281,
        4.486274719238281,
        4.611764907836914,
        4.737255096435547,
        4.800000190734863,
        4.800000190734863,
        5.113725662231445,
        5.113725662231445,
        5.3019609451293945,
        5.3019609451293945,
        5.490196228027344,
        6.117647171020508,
        6.745098114013672,
        7.184313774108887,
        7.184313774108887,
    ]
    gpu_config = GpuTraceConfig(
        params=params,
        inclination_deg=60.0,
        grid=2,
        alpha_max=8.0,
        beta_max=8.0,
        r_obs=100.0,
        critical_refine_band=0.0,
    )
    gpu = trace_screen_points(
        gpu_config,
        np.asarray(alpha_values, dtype=np.float32),
        np.asarray(beta_values, dtype=np.float32),
    )
    cpu_config = TraceConfig(max_lambda=1200.0, r_escape=200.0, horizon_eps=0.3, max_step=2.0)
    theta_obs = math.radians(60.0)
    for idx, (alpha, beta) in enumerate(zip(alpha_values, beta_values)):
        diag = trace_ray(
            params,
            CameraConfig(r_obs=100.0, theta_obs=theta_obs, alpha=alpha, beta=beta),
            cpu_config,
        )
        assert gpu["event_code"][idx] == EVENT_CODES[diag.event]
        assert gpu["failure_code"][idx] == FAILURE_CODES["none"]
