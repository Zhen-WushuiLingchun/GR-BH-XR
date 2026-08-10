"""Central scientific and runtime contract for the native NPGS integration."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "gr-bh-xr.npgs.integration.v1"
MR_FRAME_SCHEMA = "gr-bh-xr.npgs.mr-frame.v1"
DYNAMIC_XR_SCHEMA = "gr-bh-xr.npgs.dynamic-xr-frame.v1"


class GateStatus(StrEnum):
    ACCEPTED = "accepted"
    CANDIDATE = "candidate"
    BLOCKED = "blocked"
    VISUAL_ONLY = "visual_only"


class Feature(StrEnum):
    NEUTRAL_KERR_RAYS = "neutral_kerr_rays"
    NEUTRAL_KERR_NEWMAN_RAYS = "neutral_kerr_newman_rays"
    KERR_DISK_TRANSFER = "kerr_disk_transfer"
    WALKER_PENROSE_GEOMETRY = "walker_penrose_geometry"
    PAGE_THORNE_NATIVE_VISUAL = "page_thorne_native_visual"
    STOKES_TRANSPORT = "stokes_transport"
    CHARGED_DISK_PHYSICS = "charged_disk_physics"
    MAXIMAL_EXTENSION_ASTROPHYSICS = "maximal_extension_astrophysics"
    NATIVE_OPENXR = "native_openxr"
    MR_CAMERA_PIXELS = "mr_camera_pixels"
    MR_ENVIRONMENT_DEPTH = "mr_environment_depth"
    BBH_GRAVITATIONAL_WAVES = "bbh_gravitational_waves"


@dataclass(frozen=True)
class FeatureGate:
    status: GateStatus
    evidence: str


FEATURE_GATES: Mapping[Feature, FeatureGate] = {
    Feature.NEUTRAL_KERR_RAYS: FeatureGate(
        GateStatus.ACCEPTED, "quality-2 native event/direction CPU-f64 gate"
    ),
    Feature.NEUTRAL_KERR_NEWMAN_RAYS: FeatureGate(
        GateStatus.ACCEPTED, "neutral KN and RN-limit CPU-f64 gates"
    ),
    Feature.KERR_DISK_TRANSFER: FeatureGate(
        GateStatus.ACCEPTED, "Q=0 m=0/1 disk-transfer CPU-f64 gate"
    ),
    Feature.WALKER_PENROSE_GEOMETRY: FeatureGate(
        GateStatus.ACCEPTED, "native basis and Walker-Penrose geometry gate"
    ),
    Feature.PAGE_THORNE_NATIVE_VISUAL: FeatureGate(
        GateStatus.CANDIDATE, "validated Python LUT exists but is not bound in native NPGS"
    ),
    Feature.STOKES_TRANSPORT: FeatureGate(
        GateStatus.BLOCKED, "geometric polarization is not polarized emission or Stokes transport"
    ),
    Feature.CHARGED_DISK_PHYSICS: FeatureGate(
        GateStatus.BLOCKED, "charged-spacetime ray geometry does not validate charged disk matter"
    ),
    Feature.MAXIMAL_EXTENSION_ASTROPHYSICS: FeatureGate(
        GateStatus.VISUAL_ONLY, "exact stationary extension is not a collapse-interior prediction"
    ),
    Feature.NATIVE_OPENXR: FeatureGate(
        GateStatus.CANDIDATE, "render-input contract compiles; no OpenXR session/device gate"
    ),
    Feature.MR_CAMERA_PIXELS: FeatureGate(
        GateStatus.BLOCKED, "requires a fresh calibrated native camera frame record"
    ),
    Feature.MR_ENVIRONMENT_DEPTH: FeatureGate(
        GateStatus.CANDIDATE, "depth acquisition alone does not validate RGB registration"
    ),
    Feature.BBH_GRAVITATIONAL_WAVES: FeatureGate(
        GateStatus.CANDIDATE,
        "a locally implemented fixed-orbit approximate BBH tracer is audited; NR/GW and dynamic XR claims remain open",
    ),
}


@dataclass(frozen=True)
class CoordinateContract:
    chart: str = "ingoing Cartesian Kerr-Schild"
    component_order: tuple[str, ...] = ("x", "y", "z", "t")
    momentum_variance: str = "covariant"
    spin_axis: str = "+y"
    affine_direction: str = "negative in native NPGS trace"
    native_mass: float = 0.5
    normalized_mass: float = 1.0


COORDINATES = CoordinateContract()


_OVERCLAIM_KEYS: Mapping[str, Feature] = {
    "stokes_transport_valid": Feature.STOKES_TRANSPORT,
    "polarized_emission_valid": Feature.STOKES_TRANSPORT,
    "charged_disk_physics_valid": Feature.CHARGED_DISK_PHYSICS,
    "maximal_extension_astrophysics_valid": Feature.MAXIMAL_EXTENSION_ASTROPHYSICS,
    "native_openxr_valid": Feature.NATIVE_OPENXR,
    "mr_passthrough_camera_pixels_valid": Feature.MR_CAMERA_PIXELS,
    "bbh_gravitational_waves_valid": Feature.BBH_GRAVITATIONAL_WAVES,
}


def feature_status(feature: Feature | str) -> FeatureGate:
    """Return the reviewed status for one integration feature."""

    return FEATURE_GATES[Feature(feature)]


def accepted_features(metadata: Mapping[str, Any]) -> tuple[Feature, ...]:
    """Derive only features accepted by both metadata and independent gates."""

    claims = _mapping(metadata, "claims")
    parameters = _mapping(metadata, "parameters")
    accepted: list[Feature] = []
    charge = float(parameters.get("charge_Q_over_M", 0.0))

    if claims.get("shared_trace_ray") is True:
        accepted.append(
            Feature.NEUTRAL_KERR_RAYS
            if abs(charge) <= 1.0e-12
            else Feature.NEUTRAL_KERR_NEWMAN_RAYS
        )
    if claims.get("disk_transfer_slots_valid") is True:
        if abs(charge) > 1.0e-12:
            raise ValueError("Native charged-disk transfer is not an accepted integration feature.")
        accepted.append(Feature.KERR_DISK_TRANSFER)
    if claims.get("camera_polarization_evidence_emitted") is True:
        model = str(claims.get("camera_polarization_model", "")).lower()
        if "emission/stokes model not validated" not in model:
            raise ValueError(
                "Polarization evidence must explicitly exclude unvalidated emission/Stokes claims."
            )
        accepted.append(Feature.WALKER_PENROSE_GEOMETRY)

    for claim_key, feature in _OVERCLAIM_KEYS.items():
        if claims.get(claim_key) is True and FEATURE_GATES[feature].status != GateStatus.ACCEPTED:
            raise ValueError(
                f"Native metadata overclaims {feature.value}: {FEATURE_GATES[feature].evidence}."
            )
    return tuple(accepted)


def validate_native_integration_metadata(metadata: Mapping[str, Any]) -> None:
    """Fail closed on coordinate drift or claims beyond the reviewed gates."""

    parameters = _mapping(metadata, "parameters")
    mass = float(parameters.get("M_internal", float("nan")))
    if not isfinite(mass) or abs(mass - COORDINATES.native_mass) > 1.0e-12:
        raise ValueError("Native NPGS metadata must use M_internal=0.5 (Rs=1).")

    contract = metadata.get("canonical_state_contract")
    if contract is not None:
        if not isinstance(contract, Mapping):
            raise ValueError("canonical_state_contract must be an object.")
        expected = {
            "chart": COORDINATES.chart,
            "component_order": list(COORDINATES.component_order),
            "momentum_variance": COORDINATES.momentum_variance,
            "spin_axis": COORDINATES.spin_axis,
        }
        for key, value in expected.items():
            if contract.get(key) != value:
                raise ValueError(f"Native coordinate contract mismatch for {key!r}.")

    accepted_features(metadata)


def validate_mr_frame_record(record: Mapping[str, Any]) -> str:
    """Validate MR evidence and return its bounded scientific claim scope."""

    if record.get("schema") != MR_FRAME_SCHEMA:
        raise ValueError(f"MR frame schema must be {MR_FRAME_SCHEMA!r}.")
    if record.get("fresh") is not True or record.get("calibrated") is not True:
        raise ValueError("MR camera frame must be fresh and calibrated.")
    for key in ("sequence", "capture_time_ns", "native_image"):
        if int(record.get(key, 0)) <= 0:
            raise ValueError(f"MR camera frame requires positive {key}.")
    receive_time = int(record.get("receive_time_ns", 0))
    if receive_time < int(record["capture_time_ns"]):
        raise ValueError("MR receive timestamp precedes capture timestamp.")

    intrinsics = _mapping(record, "intrinsics")
    width = int(intrinsics.get("width", 0))
    height = int(intrinsics.get("height", 0))
    fx = float(intrinsics.get("fx", float("nan")))
    fy = float(intrinsics.get("fy", float("nan")))
    cx = float(intrinsics.get("cx", float("nan")))
    cy = float(intrinsics.get("cy", float("nan")))
    if (
        width <= 0
        or height <= 0
        or not all(isfinite(value) for value in (fx, fy, cx, cy))
        or fx <= 0.0
        or fy <= 0.0
        or not (0.0 <= cx <= width and 0.0 <= cy <= height)
    ):
        raise ValueError("MR camera intrinsics are invalid.")
    if record.get("color_encoding") not in {"linear_rgb", "srgb", "rec709"}:
        raise ValueError("MR camera color encoding is missing or unsupported.")
    _validate_pose(_mapping(record, "camera_pose"), name="MR camera")
    if record.get("has_depth") is True:
        depth = _mapping(record, "depth")
        _validate_depth_record(depth)
        if int(depth.get("registered_color_sequence", 0)) != int(record["sequence"]):
            raise ValueError("MR environment depth is not registered to the selected color frame.")
        if abs(int(depth["capture_time_ns"]) - int(record["capture_time_ns"])) > 50_000_000:
            raise ValueError("MR environment depth and color capture times are inconsistent.")

    coverage = str(record.get("radiance_coverage", ""))
    if coverage == "calibrated_full_sphere":
        return coverage
    if coverage in {"forward_camera_only", "forward_camera_plus_cached_environment"}:
        return "forward_camera_only"
    raise ValueError("MR frame has no measured radiance coverage.")


def metric_time_at_predicted_display(
    mapping: Mapping[str, Any], predicted_display_time_ns: int
) -> tuple[float, float, float]:
    """Return metric time, binary phase, and display GW signal.

    OpenXR time is a monotonic runtime clock. The mapping therefore needs an
    explicit epoch and physical seconds-per-M scale rather than treating the
    integer timestamp as a coordinate time directly.
    """

    epoch_ns = int(mapping.get("epoch_display_time_ns", 0))
    epoch_metric_time = float(mapping.get("epoch_metric_time_M", float("nan")))
    seconds_per_M = float(mapping.get("seconds_per_M", float("nan")))
    omega = float(mapping.get("binary_angular_frequency_per_M", float("nan")))
    phase0 = float(mapping.get("initial_binary_phase_rad", float("nan")))
    physical_gw = float(mapping.get("physical_gw_signal", float("nan")))
    visual_gain = float(mapping.get("visual_gain", float("nan")))
    if (
        epoch_ns <= 0
        or predicted_display_time_ns <= 0
        or not all(
            isfinite(value)
            for value in (epoch_metric_time, seconds_per_M, omega, phase0, physical_gw, visual_gain)
        )
        or seconds_per_M <= 0.0
        or visual_gain < 0.0
    ):
        raise ValueError("Dynamic metric display-time mapping is invalid.")
    metric_time = epoch_metric_time + (
        1.0e-9 * (predicted_display_time_ns - epoch_ns) / seconds_per_M
    )
    phase = phase0 + omega * metric_time
    return metric_time, phase, physical_gw * visual_gain


def validate_dynamic_xr_frame(record: Mapping[str, Any]) -> dict[str, float]:
    """Validate per-eye poses and the metric/display-time mapping."""

    if record.get("schema") != DYNAMIC_XR_SCHEMA:
        raise ValueError(f"Dynamic XR frame schema must be {DYNAMIC_XR_SCHEMA!r}.")
    predicted = int(record.get("predicted_display_time_ns", 0))
    metric_time, phase, display_gw = metric_time_at_predicted_display(
        _mapping(record, "metric_time_mapping"), predicted
    )
    eyes = record.get("views")
    if not isinstance(eyes, Sequence) or isinstance(eyes, (str, bytes)) or len(eyes) != 2:
        raise ValueError("Dynamic XR frame requires exactly two views.")
    positions = []
    for index, eye in enumerate(eyes):
        if not isinstance(eye, Mapping) or int(eye.get("view_index", -1)) != index:
            raise ValueError("Dynamic XR views must be ordered left then right.")
        pose = _mapping(eye, "predicted_pose")
        _validate_pose(pose, name=f"dynamic XR view {index}")
        positions.append(tuple(float(value) for value in pose["position_m"]))
    if positions[0] == positions[1]:
        raise ValueError("Dynamic XR eye origins must remain distinct.")
    return {
        "metric_time_M": metric_time,
        "binary_phase_rad": phase,
        "physical_gw_signal": float(
            _mapping(record, "metric_time_mapping")["physical_gw_signal"]
        ),
        "display_gw_signal": display_gw,
    }


def select_retarded_camera_frame(
    frames: Sequence[Mapping[str, Any]],
    *,
    observer_time_ns: int,
    retarded_delay_ns: int,
    maximum_age_ns: int,
    require_full_sphere: bool = False,
    require_depth: bool = False,
) -> Mapping[str, Any]:
    """Select the latest causal camera frame at a retarded source time."""

    if (
        observer_time_ns <= 0
        or retarded_delay_ns < 0
        or maximum_age_ns < 0
        or retarded_delay_ns > observer_time_ns
    ):
        raise ValueError("Retarded camera-history request has invalid timing.")
    requested = observer_time_ns - retarded_delay_ns
    candidates = []
    seen_sequences: dict[int, tuple[int, int, tuple[float, ...], tuple[float, ...]]] = {}
    for frame in frames:
        validate_mr_frame_record(frame)
        sequence = int(frame["sequence"])
        pose = _mapping(frame, "camera_pose")
        provenance = (
            int(frame["capture_time_ns"]),
            int(frame["native_image"]),
            tuple(float(value) for value in pose["position_m"]),
            tuple(float(value) for value in pose["orientation_xyzw"]),
        )
        if sequence in seen_sequences and seen_sequences[sequence] != provenance:
            raise ValueError("Camera history contains inconsistent provenance for one sequence.")
        seen_sequences[sequence] = provenance
        if int(frame["capture_time_ns"]) <= requested:
            candidates.append(frame)
    if not candidates:
        raise ValueError("No causal camera frame covers the requested retarded time.")
    selected = max(candidates, key=lambda frame: int(frame["capture_time_ns"]))
    age = requested - int(selected["capture_time_ns"])
    if age > maximum_age_ns:
        raise ValueError("Camera history is stale at the requested retarded time.")
    coverage = str(selected["radiance_coverage"])
    if require_full_sphere and coverage != "calibrated_full_sphere":
        raise ValueError("Requested rear/side radiance is outside measured camera coverage.")
    if require_depth and selected.get("has_depth") is not True:
        raise ValueError("Finite-distance room ray requires registered environment depth.")
    return selected


def validate_finite_scene_intersection(record: Mapping[str, Any]) -> None:
    """Reject room radiance that has no measured finite-distance scene hit."""

    if record.get("hit") is not True:
        raise ValueError("Finite-distance room radiance requires an explicit scene hit.")
    position = record.get("position_m")
    normal = record.get("normal")
    uv = record.get("color_uv")
    if not all(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes))
        for value in (position, normal, uv)
    ) or len(position) != 3 or len(normal) != 3 or len(uv) != 2:
        raise ValueError("Finite-distance scene intersection has invalid component counts.")
    values = tuple(float(value) for value in (*position, *normal, *uv))
    distance = float(record.get("distance_m", float("nan")))
    if (
        not all(isfinite(value) for value in values)
        or not isfinite(distance)
        or distance <= 0.0
        or int(record.get("source_frame_sequence", 0)) <= 0
    ):
        raise ValueError("Finite-distance scene intersection is incomplete.")
    if not (0.0 <= values[-2] <= 1.0 and 0.0 <= values[-1] <= 1.0):
        raise ValueError("Finite-distance scene intersection UV lies outside the camera image.")
    normal_squared = sum(value * value for value in values[3:6])
    if abs(normal_squared - 1.0) > 1.0e-5:
        raise ValueError("Finite-distance scene normal is not unit normalized.")


def integration_manifest() -> dict[str, Any]:
    """Return a serializable reviewed feature and coordinate manifest."""

    return {
        "schema": SCHEMA,
        "coordinates": {
            "chart": COORDINATES.chart,
            "component_order": list(COORDINATES.component_order),
            "momentum_variance": COORDINATES.momentum_variance,
            "spin_axis": COORDINATES.spin_axis,
            "affine_direction": COORDINATES.affine_direction,
            "native_mass": COORDINATES.native_mass,
            "normalized_mass": COORDINATES.normalized_mass,
        },
        "features": {
            feature.value: {"status": gate.status.value, "evidence": gate.evidence}
            for feature, gate in FEATURE_GATES.items()
        },
    }


def _mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"Integration metadata is missing object {key!r}.")
    return value


def _validate_pose(pose: Mapping[str, Any], *, name: str) -> None:
    position = pose.get("position_m")
    orientation = pose.get("orientation_xyzw")
    if not isinstance(position, Sequence) or isinstance(position, (str, bytes)):
        raise ValueError(f"{name} pose requires position_m[3].")
    if not isinstance(orientation, Sequence) or isinstance(orientation, (str, bytes)):
        raise ValueError(f"{name} pose requires orientation_xyzw[4].")
    if len(position) != 3 or len(orientation) != 4:
        raise ValueError(f"{name} pose has the wrong component count.")
    position_values = tuple(float(value) for value in position)
    orientation_values = tuple(float(value) for value in orientation)
    if not all(isfinite(value) for value in (*position_values, *orientation_values)):
        raise ValueError(f"{name} pose contains a non-finite component.")
    norm_squared = sum(value * value for value in orientation_values)
    if abs(norm_squared - 1.0) > 1.0e-6:
        raise ValueError(f"{name} pose orientation is not unit normalized.")


def _validate_depth_record(depth: Mapping[str, Any]) -> None:
    if depth.get("fresh") is not True or depth.get("calibrated") is not True:
        raise ValueError("MR environment depth must be fresh and calibrated.")
    for key in ("sequence", "capture_time_ns", "native_image", "width", "height"):
        if int(depth.get(key, 0)) <= 0:
            raise ValueError(f"MR environment depth requires positive {key}.")
    if depth.get("registered_to_color") is not True or int(
        depth.get("registered_color_sequence", 0)
    ) <= 0:
        raise ValueError("MR environment depth requires explicit color-frame registration.")
    near_m = float(depth.get("near_m", float("nan")))
    far_m = float(depth.get("far_m", float("nan")))
    if not isfinite(near_m) or not isfinite(far_m) or near_m <= 0.0 or far_m <= near_m:
        raise ValueError("MR environment depth range is invalid.")
    _validate_pose(_mapping(depth, "depth_pose"), name="MR environment depth")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="Optional JSON manifest output path")
    args = parser.parse_args(argv)
    payload = integration_manifest()
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.out is None:
        print(rendered)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
