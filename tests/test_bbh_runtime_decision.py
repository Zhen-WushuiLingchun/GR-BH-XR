import json
from pathlib import Path

import pytest

from gr_bh_xr.benchmark_bbh_runtime import (
    SCHEMA,
    build_runtime_decision,
    load_nr_gate,
    load_timing,
)


def _timing(path: Path, *, dynamic: bool, p95: float) -> Path:
    payload = {
        "schema": "gr-bh-xr.npgs.stereo-performance.v1",
        "config": {"eye_width": 1832, "eye_height": 1920, "bbh": dynamic},
        "valid_timestamp_ratio": 1.0,
        "minimum_valid_timestamp_ratio": 0.99,
        "timing_ms": {"stereo_pair_gpu": {"p95": p95}},
        "evidence": {"dynamicMetric": dynamic},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _nr(path: Path, *, passed: bool) -> Path:
    payload = {
        "schema": "gr-bh-xr.bbh.nr-pilot-manifest.v1",
        "claim": "bounded_two_resolution_nr_pipeline_pilot",
        "accepted": passed,
        "full_nr_merger_claim": False,
        "claims": {
            "bounded_two_resolution_nr_pipeline_pilot": passed,
            "full_nr_merger": False,
        },
        "validation": {"accepted": passed},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_measured_data_selects_keyframes_only_after_nr_gate(tmp_path: Path):
    stationary = load_timing(_timing(tmp_path / "s.json", dynamic=False, p95=10.188), expect_dynamic=False)
    dynamic = load_timing(_timing(tmp_path / "d.json", dynamic=True, p95=2655.53), expect_dynamic=True)

    closed = build_runtime_decision(stationary, dynamic, load_nr_gate(None))
    assert closed["schema"] == SCHEMA
    assert closed["defaults"]["high_end_pcvr"] == "stationary_preview_with_exact_dynamic_offline"
    assert closed["gates"]["keyframe_runtime_ready"] is False
    assert closed["gates"]["keyframe_architecture_qualified"] is False
    assert closed["gates"]["surrogate_training_prerequisites"] is False

    accepted = build_runtime_decision(
        stationary,
        dynamic,
        load_nr_gate(_nr(tmp_path / "nr.json", passed=True)),
    )
    assert accepted["defaults"]["high_end_pcvr"] == "time_indexed_nr_keyframes"
    assert accepted["gates"]["keyframe_architecture_qualified"] is True
    assert accepted["gates"]["keyframe_runtime_ready"] is False
    assert accepted["strategies"]["time_indexed_nr_keyframes"]["selected"]
    keyframes = accepted["strategies"]["time_indexed_nr_keyframes"]
    assert keyframes["physics_72hz_estimate"] is True
    assert keyframes["physics_72hz_measured"] is None
    assert "not measured" in keyframes["evidence"]
    assert accepted["gates"]["openxr_device_refresh_claim"] is None


def test_foveation_is_labeled_as_estimate_and_cannot_hide_measured_failure(tmp_path: Path):
    stationary = load_timing(_timing(tmp_path / "s.json", dynamic=False, p95=10.0), expect_dynamic=False)
    dynamic = load_timing(_timing(tmp_path / "d.json", dynamic=True, p95=2010.0), expect_dynamic=True)
    result = build_runtime_decision(stationary, dynamic, load_nr_gate(None), foveated_fraction=0.08)

    assert result["gates"]["full_dynamic_72hz"] is False
    foveated = result["strategies"]["foveated_dynamic"]
    assert foveated["evidence"] == "linear_pixel_cost_estimate_not_measured"
    assert foveated["required_pixel_fraction_for_72hz"] == pytest.approx(0.0005)
    assert foveated["selected"] is False


def test_surrogate_contract_preserves_audit_quantities(tmp_path: Path):
    stationary = load_timing(_timing(tmp_path / "s.json", dynamic=False, p95=8.0), expect_dynamic=False)
    dynamic = load_timing(_timing(tmp_path / "d.json", dynamic=True, p95=1200.0), expect_dynamic=True)
    result = build_runtime_decision(
        stationary,
        dynamic,
        load_nr_gate(_nr(tmp_path / "nr.json", passed=True)),
    )
    surrogate = result["strategies"]["surrogate"]
    assert set(surrogate["required_targets"]) == {
        "event_code",
        "escape_direction",
        "redshift",
        "time_delay",
        "image_order",
        "uncertainty",
    }
    assert surrogate["selected"] is False
    assert surrogate["nr_pipeline_qualified"] is True
    assert surrogate["exact_training_dataset_ready"] is False
    assert surrogate["training_allowed"] is False
    assert "exact" in surrogate["ood_policy"]


def test_mismatched_extents_fail_closed(tmp_path: Path):
    stationary_path = _timing(tmp_path / "s.json", dynamic=False, p95=8.0)
    dynamic_path = _timing(tmp_path / "d.json", dynamic=True, p95=1200.0)
    payload = json.loads(dynamic_path.read_text(encoding="utf-8"))
    payload["config"]["eye_width"] = 1600
    dynamic_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="same eye extent"):
        build_runtime_decision(
            load_timing(stationary_path, expect_dynamic=False),
            load_timing(dynamic_path, expect_dynamic=True),
            load_nr_gate(None),
        )


def test_nr_gate_rejects_legacy_or_partial_acceptance_fields(tmp_path: Path):
    path = _nr(tmp_path / "nr.json", passed=True)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["accepted"] = False
    payload["validation"]["two_resolution_gate_passed"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")

    gate = load_nr_gate(path)
    assert gate["provided"]
    assert not gate["accepted"]
    assert "every bounded-pilot gate" in gate["reason"]
