"""Select a BBH XR runtime architecture from measured timing evidence.

The tool deliberately separates measured GPU timings from pixel-fraction and
update-cadence estimates. It never turns a synthetic stereo measurement into
an OpenXR device claim, and it will not enable surrogate training without an
accepted two-resolution NR pilot manifest.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA = "gr-bh-xr.bbh.runtime-decision.v1"
PHYSICS_72HZ_BUDGET_MS = 11.0
PHYSICS_90HZ_BUDGET_MS = 9.0
TOTAL_72HZ_BUDGET_MS = 1000.0 / 72.0
TOTAL_90HZ_BUDGET_MS = 1000.0 / 90.0
DEFAULT_PROGRESSIVE_UPDATE_FRAMES = 30
DEFAULT_FOVEATED_PIXEL_FRACTION = 0.08


@dataclass(frozen=True)
class TimingEvidence:
    path: str
    eye_width: int
    eye_height: int
    pair_p95_ms: float
    valid_timestamp_ratio: float
    dynamic_metric: bool
    measured: bool = True


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_timing(path: Path, *, expect_dynamic: bool) -> TimingEvidence:
    payload = _load_json(path)
    if payload.get("schema") != "gr-bh-xr.npgs.stereo-performance.v1":
        raise ValueError(f"Unsupported timing schema in {path}.")
    config = payload["config"]
    evidence = payload.get("evidence", {})
    dynamic = bool(config.get("bbh", evidence.get("dynamicMetric", False)))
    if dynamic != expect_dynamic:
        expected = "dynamic" if expect_dynamic else "stationary"
        raise ValueError(f"{path} is not {expected} timing evidence.")
    ratio = float(payload["valid_timestamp_ratio"])
    if ratio < float(payload.get("minimum_valid_timestamp_ratio", 0.99)):
        raise ValueError(f"{path} has insufficient valid GPU timestamps.")
    return TimingEvidence(
        path=str(path.resolve()),
        eye_width=int(config["eye_width"]),
        eye_height=int(config["eye_height"]),
        pair_p95_ms=float(payload["timing_ms"]["stereo_pair_gpu"]["p95"]),
        valid_timestamp_ratio=ratio,
        dynamic_metric=dynamic,
    )


def load_nr_gate(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "provided": False,
            "accepted": False,
            "reason": "No Task 8 two-resolution NR manifest was supplied.",
        }
    payload = _load_json(path)
    if payload.get("schema") != "gr-bh-xr.bbh.nr-pilot-manifest.v1":
        raise ValueError(f"Unsupported NR pilot schema in {path}.")
    claims = payload.get("claims", {})
    validation = payload.get("validation", {})
    accepted = bool(payload.get("accepted", False))
    accepted &= bool(validation.get("accepted", False))
    accepted &= bool(claims.get("bounded_two_resolution_nr_pipeline_pilot", False))
    accepted &= payload.get("full_nr_merger_claim") is False
    accepted &= claims.get("full_nr_merger") is False
    return {
        "provided": True,
        "accepted": accepted,
        "keyframe_asset_ready": bool(
            accepted and claims.get("time_indexed_keyframe_asset", False)
        ),
        "surrogate_dataset_ready": bool(
            accepted and claims.get("surrogate_training_dataset", False)
        ),
        "path": str(path.resolve()),
        "claim": payload.get("claim"),
        "reason": (
            "Two-resolution constraints, horizon, waveform, and ray gate accepted."
            if accepted
            else "The supplied NR manifest does not close every bounded-pilot gate."
        ),
    }


def build_runtime_decision(
    stationary: TimingEvidence,
    dynamic: TimingEvidence,
    nr_gate: dict[str, Any],
    *,
    foveated_fraction: float = DEFAULT_FOVEATED_PIXEL_FRACTION,
    progressive_update_frames: int = DEFAULT_PROGRESSIVE_UPDATE_FRAMES,
) -> dict[str, Any]:
    if (stationary.eye_width, stationary.eye_height) != (
        dynamic.eye_width,
        dynamic.eye_height,
    ):
        raise ValueError("Stationary and dynamic timings must use the same eye extent.")
    if not (0.0 < foveated_fraction <= 1.0):
        raise ValueError("foveated_fraction must be in (0, 1].")
    if progressive_update_frames < 1:
        raise ValueError("progressive_update_frames must be positive.")

    stationary_ms = stationary.pair_p95_ms
    dynamic_ms = dynamic.pair_p95_ms
    dynamic_increment_ms = max(0.0, dynamic_ms - stationary_ms)
    headroom_72_ms = max(0.0, PHYSICS_72HZ_BUDGET_MS - stationary_ms)
    required_fraction_72 = (
        headroom_72_ms / dynamic_increment_ms
        if dynamic_increment_ms > 0.0
        else 1.0
    )
    foveated_estimate_ms = stationary_ms + dynamic_increment_ms * foveated_fraction
    progressive_amortized_ms = (
        stationary_ms + dynamic_increment_ms / progressive_update_frames
    )
    progressive_latency_ms = dynamic_ms

    nr_accepted = bool(nr_gate.get("accepted", False))
    keyframe_architecture_qualified = (
        nr_accepted and stationary_ms < PHYSICS_72HZ_BUDGET_MS
    )
    keyframe_runtime_ready = bool(
        keyframe_architecture_qualified
        and nr_gate.get("keyframe_asset_ready", False)
    )
    surrogate_training_ready = bool(
        nr_accepted and nr_gate.get("surrogate_dataset_ready", False)
    )
    default_path = (
        "time_indexed_nr_keyframes"
        if keyframe_architecture_qualified
        else "stationary_preview_with_exact_dynamic_offline"
    )

    strategies = {
        "full_resolution_dynamic": {
            "evidence": "measured",
            "pair_p95_ms": dynamic_ms,
            "physics_72hz": dynamic_ms < PHYSICS_72HZ_BUDGET_MS,
            "physics_90hz": dynamic_ms < PHYSICS_90HZ_BUDGET_MS,
            "selected": False,
        },
        "foveated_dynamic": {
            "evidence": "linear_pixel_cost_estimate_not_measured",
            "pixel_fraction": foveated_fraction,
            "estimated_pair_p95_ms": foveated_estimate_ms,
            "required_pixel_fraction_for_72hz": required_fraction_72,
            "physics_72hz_estimate": foveated_estimate_ms < PHYSICS_72HZ_BUDGET_MS,
            "selected": False,
        },
        "progressive_exact_updates": {
            "evidence": "amortized_estimate_not_measured",
            "update_frames": progressive_update_frames,
            "estimated_amortized_pair_p95_ms": progressive_amortized_ms,
            "full_update_latency_ms": progressive_latency_ms,
            "physics_72hz_estimate": progressive_amortized_ms < PHYSICS_72HZ_BUDGET_MS,
            "selected": False,
            "use": "optional asynchronous refinement; never relabel stale texels as current",
        },
        "time_indexed_nr_keyframes": {
            "evidence": (
                "measured stationary fast-path upper-bound proxy plus Task 8 "
                "pipeline gate; keyframe playback is not measured"
            ),
            "estimated_pair_p95_ms": stationary_ms,
            "nr_gate_accepted": nr_accepted,
            "architecture_qualified": keyframe_architecture_qualified,
            "runtime_asset_ready": keyframe_runtime_ready,
            "physics_72hz_estimate": keyframe_architecture_qualified,
            "physics_90hz_estimate": (
                nr_accepted and stationary_ms < PHYSICS_90HZ_BUDGET_MS
            ),
            "physics_72hz_measured": None,
            "physics_90hz_measured": None,
            "selected": default_path == "time_indexed_nr_keyframes",
            "claim_boundary": (
                "The bounded Task 8 pilot qualifies the architecture only. A complete, "
                "time-indexed keyframe asset remains a separate production gate."
            ),
        },
        "hybrid_keyframes_plus_progressive_tiles": {
            "evidence": "architecture candidate; tile schedule not measured",
            "base_pair_p95_ms": stationary_ms,
            "selected": False,
            "condition": "Task 8 accepted and tiled update p95 measured within remaining headroom",
        },
        "surrogate": {
            "evidence": "not selected",
            "selected": False,
            "training_allowed": surrogate_training_ready,
            "nr_pipeline_qualified": nr_accepted,
            "exact_training_dataset_ready": bool(
                nr_gate.get("surrogate_dataset_ready", False)
            ),
            "required_targets": [
                "event_code",
                "escape_direction",
                "redshift",
                "time_delay",
                "image_order",
                "uncertainty",
            ],
            "forbidden_target": "final RGB as the sole target",
            "ood_policy": "fail closed to exact tracing or accepted keyframes",
        },
    }

    return {
        "schema": SCHEMA,
        "budgets_ms": {
            "physics_72hz": PHYSICS_72HZ_BUDGET_MS,
            "physics_90hz": PHYSICS_90HZ_BUDGET_MS,
            "total_72hz": TOTAL_72HZ_BUDGET_MS,
            "total_90hz": TOTAL_90HZ_BUDGET_MS,
        },
        "eye_extent": [stationary.eye_width, stationary.eye_height],
        "evidence": {
            "stationary": stationary.__dict__,
            "dynamic": dynamic.__dict__,
            "nr_gate": nr_gate,
        },
        "derived": {
            "dynamic_increment_ms": dynamic_increment_ms,
            "stationary_headroom_72hz_ms": headroom_72_ms,
            "required_dynamic_pixel_fraction_for_72hz": required_fraction_72,
            "full_dynamic_slowdown": (
                dynamic_ms / stationary_ms if stationary_ms > 0.0 else math.inf
            ),
        },
        "strategies": strategies,
        "defaults": {
            "high_end_pcvr": default_path,
            "desktop_interactive": "progressive_exact_updates",
            "offline_audit": "full_resolution_dynamic",
            "quest_android": "not_evaluated",
        },
        "gates": {
            "full_dynamic_72hz": dynamic_ms < PHYSICS_72HZ_BUDGET_MS,
            "keyframe_architecture_qualified": keyframe_architecture_qualified,
            "keyframe_runtime_ready": keyframe_runtime_ready,
            "surrogate_training_prerequisites": surrogate_training_ready,
            "openxr_device_refresh_claim": None,
        },
        "claim_boundary": (
            "The timing evidence is synthetic sequential stereo, not an OpenXR total-frame "
            "measurement. Foveated and progressive costs are explicit linear estimates. "
            "Keyframe selection requires the independent Task 8 two-resolution NR gate; "
            "the stationary timing is only a fast-path proxy until playback is measured."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stationary", type=Path, required=True)
    parser.add_argument("--dynamic", type=Path, required=True)
    parser.add_argument("--nr-manifest", type=Path)
    parser.add_argument("--foveated-fraction", type=float, default=DEFAULT_FOVEATED_PIXEL_FRACTION)
    parser.add_argument("--progressive-update-frames", type=int, default=DEFAULT_PROGRESSIVE_UPDATE_FRAMES)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    decision = build_runtime_decision(
        load_timing(args.stationary, expect_dynamic=False),
        load_timing(args.dynamic, expect_dynamic=True),
        load_nr_gate(args.nr_manifest),
        foveated_fraction=args.foveated_fraction,
        progressive_update_frames=args.progressive_update_frames,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision["defaults"], indent=2))


if __name__ == "__main__":
    main()
