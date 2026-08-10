import copy
from pathlib import Path

import pytest

from gr_bh_xr.npgs_contract import (
    DYNAMIC_XR_SCHEMA,
    MR_FRAME_SCHEMA,
    select_retarded_camera_frame,
    validate_dynamic_xr_frame,
    validate_finite_scene_intersection,
)


ROOT = Path(__file__).resolve().parents[1]


def _frame(sequence: int, capture_time_ns: int, *, coverage="forward_camera_only"):
    return {
        "schema": MR_FRAME_SCHEMA,
        "sequence": sequence,
        "capture_time_ns": capture_time_ns,
        "receive_time_ns": capture_time_ns + 2_000_000,
        "native_image": 100 + sequence,
        "fresh": True,
        "calibrated": True,
        "color_encoding": "linear_rgb",
        "radiance_coverage": coverage,
        "camera_pose": {
            "position_m": [0.01 * sequence, 1.6, 0.0],
            "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
        "intrinsics": {
            "fx": 900.0,
            "fy": 900.0,
            "cx": 640.0,
            "cy": 480.0,
            "width": 1280,
            "height": 960,
        },
    }


def _dynamic_record():
    epoch = 10_000_000_000
    predicted = epoch + 20_000_000
    return {
        "schema": DYNAMIC_XR_SCHEMA,
        "predicted_display_time_ns": predicted,
        "metric_time_mapping": {
            "epoch_display_time_ns": epoch,
            "epoch_metric_time_M": 12.0,
            "seconds_per_M": 0.002,
            "binary_angular_frequency_per_M": 0.025,
            "initial_binary_phase_rad": 0.3,
            "physical_gw_signal": 2.0e-21,
            "visual_gain": 1.0e18,
        },
        "views": [
            {
                "view_index": 0,
                "predicted_pose": {
                    "position_m": [-0.032, 1.6, 0.0],
                    "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
                },
            },
            {
                "view_index": 1,
                "predicted_pose": {
                    "position_m": [0.032, 1.6, 0.0],
                    "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
                },
            },
        ],
    }


def test_dynamic_metric_time_uses_predicted_display_clock_and_separates_gw_gain() -> None:
    values = validate_dynamic_xr_frame(_dynamic_record())
    assert values["metric_time_M"] == pytest.approx(22.0)
    assert values["binary_phase_rad"] == pytest.approx(0.85)
    assert values["physical_gw_signal"] == pytest.approx(2.0e-21)
    assert values["display_gw_signal"] == pytest.approx(2.0e-3)


def test_dynamic_xr_requires_distinct_predicted_eye_origins() -> None:
    record = _dynamic_record()
    record["views"][1]["predicted_pose"]["position_m"] = [-0.032, 1.6, 0.0]
    with pytest.raises(ValueError, match="distinct"):
        validate_dynamic_xr_frame(record)


def test_retarded_history_selects_causal_frame_not_current_frame() -> None:
    frames = [_frame(1, 1_000_000_000), _frame(2, 1_020_000_000), _frame(3, 1_040_000_000)]
    selected = select_retarded_camera_frame(
        frames,
        observer_time_ns=1_050_000_000,
        retarded_delay_ns=25_000_000,
        maximum_age_ns=10_000_000,
    )
    assert selected["sequence"] == 2
    assert selected["sequence"] != 3


def test_stale_current_frame_cannot_satisfy_delayed_ray() -> None:
    with pytest.raises(ValueError, match="No causal"):
        select_retarded_camera_frame(
            [_frame(9, 2_000_000_000)],
            observer_time_ns=2_010_000_000,
            retarded_delay_ns=50_000_000,
            maximum_age_ns=100_000_000,
        )


def test_history_rejects_unknown_rear_radiance_and_inconsistent_pose() -> None:
    frames = [_frame(1, 1_000_000_000)]
    with pytest.raises(ValueError, match="rear/side"):
        select_retarded_camera_frame(
            frames,
            observer_time_ns=1_005_000_000,
            retarded_delay_ns=0,
            maximum_age_ns=10_000_000,
            require_full_sphere=True,
        )
    duplicate = copy.deepcopy(frames[0])
    duplicate["camera_pose"]["position_m"][0] = 0.5
    with pytest.raises(ValueError, match="inconsistent provenance"):
        select_retarded_camera_frame(
            [frames[0], duplicate],
            observer_time_ns=1_005_000_000,
            retarded_delay_ns=0,
            maximum_age_ns=10_000_000,
        )


def test_finite_room_radiance_requires_depth_scene_hit() -> None:
    hit = {
        "hit": True,
        "position_m": [0.2, 1.0, -1.3],
        "normal": [0.0, 0.0, 1.0],
        "color_uv": [0.3, 0.7],
        "distance_m": 1.8,
        "source_frame_sequence": 4,
    }
    validate_finite_scene_intersection(hit)
    hit["hit"] = False
    with pytest.raises(ValueError, match="explicit scene hit"):
        validate_finite_scene_intersection(hit)


def test_native_sources_encode_causal_history_and_metric_time_contract() -> None:
    xr = ROOT / "runtime" / "NPGS" / "NPGS" / "Sources" / "Engine" / "Core" / "Runtime" / "XR"
    render_header = (xr / "RenderContract.h").read_text(encoding="utf8")
    history_source = (xr / "CameraHistory.cpp").read_text(encoding="utf8")
    scene_source = (xr / "MixedRealityContract.cpp").read_text(encoding="utf8")
    assert "FDynamicMetricTimeMapping" in render_header
    assert "PhysicalGwSignal * VisualGain" in (xr / "RenderContract.cpp").read_text(encoding="utf8")
    assert "CaptureTimeNanoseconds <= Requested" in history_source
    assert "outside measured camera coverage" in history_source
    assert "finite-distance room radiance requires an explicit scene hit" in scene_source
