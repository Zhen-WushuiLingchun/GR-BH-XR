from __future__ import annotations

import math

import h5py
import numpy as np
import pytest

from gr_bh_xr.generate_lens_map import EVENT_CODES, FAILURE_CODES
from gr_bh_xr.geodesic import trace_ray
from gr_bh_xr.gpu.backend import backend_info, select_vulkan_adapter
from gr_bh_xr.gpu.generate_lens_map import generate_gpu_lens_map
from gr_bh_xr.gpu.trace import GpuTraceConfig, trace_screen_points
from gr_bh_xr.gpu.validate import validate_cpu_vs_gpu
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
        assert handle.attrs["schema"] == "gr-bh-xr.phase2.gpu_lens_map.v2"
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
            "event_rgba8",
            "debug_rgba8",
        ):
            assert dataset in handle
        assert handle["gpu_event_code"].shape == (17, 17)
        assert handle["gpu_refinement_level"].shape == (17, 17)
        assert handle["event_rgba8"].shape == (17, 17, 4)
        assert handle["gpu_failure_code"].attrs["code_polar_step_overshoot"] == 5
        escape_mask = handle["gpu_event_code"][...] == EVENT_CODES["escape"]
        assert np.all(np.isfinite(handle["gpu_escape_theta"][...][escape_mask]))
        assert np.all(np.isfinite(handle["gpu_escape_phi"][...][escape_mask]))


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
