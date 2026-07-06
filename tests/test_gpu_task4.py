from __future__ import annotations

import h5py
import pytest

from gr_bh_xr.gpu.backend import backend_info, select_vulkan_adapter
from gr_bh_xr.gpu.generate_lens_map import generate_gpu_lens_map
from gr_bh_xr.gpu.validate import validate_cpu_vs_gpu
from gr_bh_xr.types import MetricParams


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
        assert handle.attrs["schema"] == "gr-bh-xr.phase2.gpu_lens_map.v1"
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
            "event_rgba8",
            "debug_rgba8",
        ):
            assert dataset in handle
        assert handle["gpu_event_code"].shape == (17, 17)
        assert handle["gpu_refinement_level"].shape == (17, 17)
        assert handle["event_rgba8"].shape == (17, 17, 4)
        assert handle["gpu_failure_code"].attrs["code_polar_step_overshoot"] == 5


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
            "gpu_refinement_level",
            "gpu_subpixel_capture_fraction",
            "gpu_subpixel_invalid_fraction",
            "stable_comparison_mask",
            "full_grid_event_agreement_mask",
            "excluded_critical_band",
            "excluded_near_capture",
        ):
            assert dataset in handle
