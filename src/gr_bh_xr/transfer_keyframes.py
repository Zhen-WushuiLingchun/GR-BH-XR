"""Auditable time-indexed transfer-map asset contracts.

This module deliberately sits above the ray tracers.  A frame remains a
versioned full-sky transfer cubemap; this layer adds metric time, provenance,
content hashes, acceptance evidence, and fail-closed interpolation rules.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


TIME_INDEXED_TRANSFER_SOURCE_SCHEMA = "gr-bh-xr.bbh.time-indexed-transfer.source.v1"
TIME_INDEXED_TRANSFER_SCHEMA = "gr-bh-xr.bbh.time-indexed-transfer.v1"
TRANSFER_FRAME_GATE_SCHEMA = "gr-bh-xr.validation.transfer-frame.v1"
TRANSFER_SEQUENCE_GATE_SCHEMA = "gr-bh-xr.validation.transfer-sequence.v1"
SUPPORTED_FRAME_SCHEMAS = ("gr-bh-xr.task5.full_sky_transfer_cubemap.v3",)
UNITY_CUBE_FACE_ORDER = (
    "PositiveX",
    "NegativeX",
    "PositiveY",
    "NegativeY",
    "PositiveZ",
    "NegativeZ",
)
DEFAULT_REQUIRED_BUFFER_ROLES = ("event", "escape_direction")


@dataclass(frozen=True)
class ManifestValidation:
    valid: bool
    runtime_asset_ready: bool
    errors: tuple[str, ...]


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_child(base: Path, relative: str, *, label: str) -> Path:
    candidate = (base / relative).resolve()
    resolved_base = base.resolve()
    if candidate != resolved_base and resolved_base not in candidate.parents:
        raise ValueError(f"{label} escapes its frame directory: {relative}")
    if not candidate.is_file():
        raise ValueError(f"{label} does not exist: {candidate}")
    return candidate


def _expected_size(metadata: Mapping[str, Any], key: str, index: int | None = None) -> int:
    sizes = metadata.get("bytes")
    if not isinstance(sizes, Mapping) or key not in sizes:
        raise ValueError(f"frame metadata is missing bytes.{key}")
    value = sizes[key]
    if index is not None:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise ValueError(f"frame metadata bytes.{key} must be a list")
        try:
            value = value[index]
        except IndexError as exc:
            raise ValueError(f"frame metadata bytes.{key} is too short") from exc
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"frame metadata bytes.{key} must be a positive integer")
    return value


def _declared_buffers(metadata: Mapping[str, Any]) -> dict[str, tuple[str, int]]:
    buffers: dict[str, tuple[str, int]] = {}

    def add(role: str, filename: Any, byte_key: str, index: int | None = None) -> None:
        if not isinstance(filename, str) or not filename:
            raise ValueError(f"frame metadata is missing buffer path for {role}")
        buffers[role] = (filename, _expected_size(metadata, byte_key, index))

    add("event", metadata.get("eventCubeRgba8"), "eventCubeRgba8")
    add(
        "escape_direction",
        metadata.get("escapeDirUnityCubeRgba32f"),
        "escapeDirUnityCubeRgba32f",
    )

    disk_transfers = metadata.get("diskTransferCubesRgba16f", [])
    disk_redshifts = metadata.get("diskRedshiftCubesRgba16f", [])
    if not isinstance(disk_transfers, list) or not isinstance(disk_redshifts, list):
        raise ValueError("disk transfer and redshift buffer declarations must be lists")
    if disk_transfers or disk_redshifts:
        if len(disk_transfers) != len(disk_redshifts):
            raise ValueError("disk transfer and redshift order counts differ")
        for order, filename in enumerate(disk_transfers):
            add(
                f"disk_order{order}_transfer",
                filename,
                "diskTransferCubesRgba16f",
                order,
            )
            add(
                f"disk_order{order}_redshift",
                disk_redshifts[order],
                "diskRedshiftCubesRgba16f",
                order,
            )
    return buffers


def _validated_evidence(path: Path, schema: str) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, f"acceptance evidence is missing: {path}"
    evidence = _read_json(path)
    if evidence.get("schema") != schema:
        return None, f"acceptance evidence has wrong schema: {path}"
    if evidence.get("passed") is not True:
        return None, f"acceptance evidence did not pass: {path}"
    return evidence, None


def _relative(path: Path, base: Path) -> str:
    return Path(os.path.relpath(path.resolve(), base.resolve())).as_posix()


def build_time_indexed_manifest(
    source_spec_path: Path | str,
    output_path: Path | str,
) -> dict[str, Any]:
    """Build a content-addressed time sequence from accepted v3 transfer frames.

    Malformed physics assets raise immediately.  Missing or failed independent
    gate evidence produces a manifest with ``runtimeAssetReady = false``.
    """

    source_path = Path(source_spec_path).resolve()
    output = Path(output_path).resolve()
    source = _read_json(source_path)
    if source.get("schema") != TIME_INDEXED_TRANSFER_SOURCE_SCHEMA:
        raise ValueError("unsupported time-indexed transfer source schema")

    metric_source = source.get("metricSource")
    if not isinstance(metric_source, Mapping):
        raise ValueError("metricSource must be an object")
    for key in ("providerSchema", "evidenceLabel", "sourceRevision"):
        if not isinstance(metric_source.get(key), str) or not metric_source[key].strip():
            raise ValueError(f"metricSource.{key} is required")

    coverage = source.get("coverage")
    if not isinstance(coverage, Mapping):
        raise ValueError("coverage must be an object")
    expected_start = float(coverage.get("expectedStartMetricTimeM", math.nan))
    expected_end = float(coverage.get("expectedEndMetricTimeM", math.nan))
    max_gap = float(coverage.get("maxGapM", math.nan))
    if not all(map(math.isfinite, (expected_start, expected_end, max_gap))):
        raise ValueError("coverage times must be finite")
    if expected_end <= expected_start or max_gap <= 0.0:
        raise ValueError("coverage requires end > start and maxGapM > 0")

    required_roles = source.get("requiredBufferRoles", list(DEFAULT_REQUIRED_BUFFER_ROLES))
    if not isinstance(required_roles, list) or not required_roles or not all(
        isinstance(role, str) and role for role in required_roles
    ):
        raise ValueError("requiredBufferRoles must be a non-empty string list")
    if len(set(required_roles)) != len(required_roles):
        raise ValueError("requiredBufferRoles contains duplicates")

    source_frames = source.get("frames")
    if not isinstance(source_frames, list) or len(source_frames) < 2:
        raise ValueError("at least two time-indexed frames are required")

    output.parent.mkdir(parents=True, exist_ok=True)
    source_base = source_path.parent
    output_base = output.parent
    frames: list[dict[str, Any]] = []
    readiness_reasons: list[str] = []
    reference_inventory: tuple[str, ...] | None = None
    reference_face_size: int | None = None
    reference_face_order: tuple[str, ...] | None = None

    for index, frame_spec in enumerate(source_frames):
        if not isinstance(frame_spec, Mapping):
            raise ValueError(f"frame {index} must be an object")
        metric_time = float(frame_spec.get("metricTimeM", math.nan))
        if not math.isfinite(metric_time):
            raise ValueError(f"frame {index} metricTimeM must be finite")
        directory_value = frame_spec.get("directory")
        if not isinstance(directory_value, str) or not directory_value:
            raise ValueError(f"frame {index} directory is required")
        frame_dir = (source_base / directory_value).resolve()
        if not frame_dir.is_dir():
            raise ValueError(f"frame {index} directory does not exist: {frame_dir}")

        metadata_path = frame_dir / "full_sky_transfer_metadata.json"
        metadata = _read_json(metadata_path)
        if metadata.get("schema") not in SUPPORTED_FRAME_SCHEMAS:
            raise ValueError(
                f"frame {index} uses unsupported schema {metadata.get('schema')!r}; "
                "static roam grids and legacy binary-validity cubes are not BBH time frames"
            )
        face_size = metadata.get("faceSize")
        face_order = metadata.get("faceOrder")
        if not isinstance(face_size, int) or face_size <= 0:
            raise ValueError(f"frame {index} has invalid faceSize")
        if tuple(face_order or ()) != UNITY_CUBE_FACE_ORDER:
            raise ValueError(f"frame {index} has incompatible cubemap face order")

        declared = _declared_buffers(metadata)
        inventory = tuple(sorted(declared))
        missing_roles = sorted(set(required_roles) - set(inventory))
        if missing_roles:
            raise ValueError(f"frame {index} is missing required buffers: {missing_roles}")
        if reference_inventory is None:
            reference_inventory = inventory
            reference_face_size = face_size
            reference_face_order = tuple(face_order)
        elif (
            inventory != reference_inventory
            or face_size != reference_face_size
            or tuple(face_order) != reference_face_order
        ):
            raise ValueError(f"frame {index} is not layout-compatible with frame 0")

        buffers: dict[str, Any] = {}
        for role, (filename, expected_bytes) in declared.items():
            buffer_path = _safe_child(frame_dir, filename, label=f"frame {index} {role}")
            actual_bytes = buffer_path.stat().st_size
            if actual_bytes != expected_bytes:
                raise ValueError(
                    f"frame {index} {role} size mismatch: {actual_bytes} != {expected_bytes}"
                )
            buffers[role] = {
                "path": _relative(buffer_path, source_base),
                "bytes": actual_bytes,
                "sha256": _sha256(buffer_path),
            }

        gate_value = frame_spec.get("gateEvidence")
        gate_path = (
            (source_base / gate_value).resolve()
            if isinstance(gate_value, str) and gate_value
            else source_base / f"missing-frame-{index}-gate.json"
        )
        gate, gate_error = _validated_evidence(gate_path, TRANSFER_FRAME_GATE_SCHEMA)
        if gate_error:
            readiness_reasons.append(f"frame {index}: {gate_error}")

        frames.append(
            {
                "index": index,
                "metricTimeM": metric_time,
                "directory": _relative(frame_dir, source_base),
                "metadata": {
                    "path": _relative(metadata_path, source_base),
                    "schema": metadata["schema"],
                    "bytes": metadata_path.stat().st_size,
                    "sha256": _sha256(metadata_path),
                },
                "buffers": buffers,
                "gateEvidence": None
                if gate is None
                else {
                    "path": _relative(gate_path, source_base),
                    "schema": gate["schema"],
                    "sha256": _sha256(gate_path),
                },
            }
        )

    times = [frame["metricTimeM"] for frame in frames]
    if any(right <= left for left, right in zip(times, times[1:])):
        raise ValueError("frame metricTimeM values must be strictly increasing")
    actual_max_gap = max(right - left for left, right in zip(times, times[1:]))
    endpoint_tolerance = max(1.0e-12, 1.0e-12 * max(abs(expected_start), abs(expected_end)))
    if abs(times[0] - expected_start) > endpoint_tolerance:
        readiness_reasons.append("first frame does not cover expectedStartMetricTimeM")
    if abs(times[-1] - expected_end) > endpoint_tolerance:
        readiness_reasons.append("last frame does not cover expectedEndMetricTimeM")
    if actual_max_gap > max_gap * (1.0 + 1.0e-12):
        readiness_reasons.append("frame spacing exceeds coverage.maxGapM")

    sequence_gate_value = source.get("sequenceGateEvidence")
    sequence_gate_path = (
        (source_base / sequence_gate_value).resolve()
        if isinstance(sequence_gate_value, str) and sequence_gate_value
        else source_base / "missing-sequence-gate.json"
    )
    sequence_gate, sequence_gate_error = _validated_evidence(
        sequence_gate_path, TRANSFER_SEQUENCE_GATE_SCHEMA
    )
    if sequence_gate_error:
        readiness_reasons.append(sequence_gate_error)

    manifest = {
        "schema": TIME_INDEXED_TRANSFER_SCHEMA,
        "sourceSpec": {
            "path": _relative(source_path, source_base),
            "sha256": _sha256(source_path),
        },
        "assetRoot": _relative(source_base, output_base),
        "metricSource": dict(metric_source),
        "coverage": {
            "expectedStartMetricTimeM": expected_start,
            "expectedEndMetricTimeM": expected_end,
            "declaredMaxGapM": max_gap,
            "actualMaxGapM": actual_max_gap,
            "frameCount": len(frames),
        },
        "layout": {
            "faceSize": reference_face_size,
            "faceOrder": list(reference_face_order or ()),
            "bufferRoles": list(reference_inventory or ()),
            "requiredBufferRoles": list(required_roles),
        },
        "interpolationPolicy": {
            "eventAndFailure": "discrete; differing classes are not interpolated",
            "escapeDirection": "normalized linear interpolation only when both frames are valid escape samples; antipodal or degenerate pairs fail closed",
            "diskTransfer": "interpolate only matching valid image orders; unpremultiply coverage, interpolate r/g, interpolate azimuth on the unit circle, then premultiply",
            "outOfRange": "fail closed; no temporal extrapolation",
        },
        "frames": frames,
        "sequenceGateEvidence": None
        if sequence_gate is None
        else {
            "path": _relative(sequence_gate_path, source_base),
            "schema": sequence_gate["schema"],
            "sha256": _sha256(sequence_gate_path),
        },
        "runtimeAssetReady": not readiness_reasons,
        "readinessReasons": readiness_reasons,
        "claimBoundary": (
            "runtimeAssetReady certifies only manifest completeness and the referenced independent gates; it does not turn an approximate metric into numerical relativity or prove an XR device gate"
        ),
    }
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def validate_time_indexed_manifest(
    manifest_path: Path | str,
    *,
    verify_hashes: bool = True,
) -> ManifestValidation:
    path = Path(manifest_path).resolve()
    errors: list[str] = []
    try:
        manifest = _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return ManifestValidation(False, False, (str(exc),))
    if manifest.get("schema") != TIME_INDEXED_TRANSFER_SCHEMA:
        errors.append("unsupported manifest schema")
    claimed_ready = manifest.get("runtimeAssetReady") is True
    asset_root_value = manifest.get("assetRoot")
    if not isinstance(asset_root_value, str) or Path(asset_root_value).is_absolute():
        errors.append("assetRoot must be a relative path")
        asset_root = path.parent
    else:
        asset_root = (path.parent / asset_root_value).resolve()
        if not asset_root.is_dir():
            errors.append("assetRoot does not exist")

    def verify_record(record: Any, label: str, *, require_bytes: bool) -> Path | None:
        if not isinstance(record, Mapping):
            errors.append(f"{label} record is missing")
            return None
        relative = record.get("path")
        if not isinstance(relative, str):
            errors.append(f"{label} path is missing")
            return None
        try:
            asset = _safe_child(asset_root, relative, label=label)
        except ValueError as exc:
            errors.append(str(exc))
            return None
        if require_bytes and asset.stat().st_size != record.get("bytes"):
            errors.append(f"{label} byte count changed")
        if verify_hashes and _sha256(asset) != record.get("sha256"):
            errors.append(f"{label} SHA-256 changed")
        return asset

    source_asset = verify_record(manifest.get("sourceSpec"), "sourceSpec", require_bytes=False)
    if source_asset is not None:
        try:
            source_spec = _read_json(source_asset)
            if source_spec.get("schema") != TIME_INDEXED_TRANSFER_SOURCE_SCHEMA:
                errors.append("sourceSpec has unsupported schema")
            if source_spec.get("metricSource") != manifest.get("metricSource"):
                errors.append("sourceSpec metricSource differs from manifest")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"sourceSpec cannot be parsed: {exc}")
    if claimed_ready or manifest.get("sequenceGateEvidence") is not None:
        sequence_gate_asset = verify_record(
            manifest.get("sequenceGateEvidence"),
            "sequenceGateEvidence",
            require_bytes=False,
        )
        if sequence_gate_asset is not None:
            gate, gate_error = _validated_evidence(
                sequence_gate_asset, TRANSFER_SEQUENCE_GATE_SCHEMA
            )
            if gate is None and gate_error:
                errors.append(gate_error)
    frames = manifest.get("frames")
    if not isinstance(frames, list) or len(frames) < 2:
        errors.append("manifest requires at least two frames")
        frames = []
    layout = manifest.get("layout")
    if not isinstance(layout, Mapping):
        errors.append("manifest layout is missing")
        layout_roles: tuple[str, ...] = ()
        required_roles: set[str] = set()
        layout_face_size = None
        layout_face_order: tuple[str, ...] = ()
    else:
        raw_roles = layout.get("bufferRoles")
        raw_required = layout.get("requiredBufferRoles")
        layout_roles = tuple(raw_roles) if isinstance(raw_roles, list) else ()
        required_roles = set(raw_required) if isinstance(raw_required, list) else set()
        layout_face_size = layout.get("faceSize")
        layout_face_order = tuple(layout.get("faceOrder") or ())
        if not layout_roles or not required_roles.issubset(layout_roles):
            errors.append("manifest layout buffer roles are inconsistent")
        if layout_face_order != UNITY_CUBE_FACE_ORDER:
            errors.append("manifest layout has incompatible cubemap face order")
    times: list[float] = []
    for index, frame in enumerate(frames):
        try:
            metric_time = float(frame["metricTimeM"])
            if not math.isfinite(metric_time):
                raise ValueError
            times.append(metric_time)
        except (KeyError, TypeError, ValueError):
            errors.append(f"frame {index} has invalid metricTimeM")
        buffer_records = frame.get("buffers")
        if not isinstance(buffer_records, Mapping):
            errors.append(f"frame {index} buffers record is missing")
            buffer_records = {}
        if tuple(sorted(buffer_records)) != layout_roles:
            errors.append(f"frame {index} buffer inventory differs from manifest layout")
        metadata_asset: Path | None = None
        for label, record in [("metadata", frame.get("metadata"))] + list(buffer_records.items()):
            asset = verify_record(record, f"frame {index} {label}", require_bytes=True)
            if label == "metadata":
                metadata_asset = asset
        if metadata_asset is not None:
            try:
                metadata = _read_json(metadata_asset)
                if metadata.get("schema") not in SUPPORTED_FRAME_SCHEMAS:
                    errors.append(f"frame {index} metadata schema is unsupported")
                if metadata.get("faceSize") != layout_face_size:
                    errors.append(f"frame {index} faceSize differs from manifest layout")
                if tuple(metadata.get("faceOrder") or ()) != layout_face_order:
                    errors.append(f"frame {index} face order differs from manifest layout")
                declared = _declared_buffers(metadata)
                if tuple(sorted(declared)) != layout_roles:
                    errors.append(f"frame {index} metadata buffer inventory differs from layout")
                for role, (_, byte_count) in declared.items():
                    record = buffer_records.get(role)
                    if not isinstance(record, Mapping) or record.get("bytes") != byte_count:
                        errors.append(f"frame {index} {role} byte declaration differs from metadata")
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"frame {index} metadata cannot be parsed: {exc}")
        if claimed_ready or frame.get("gateEvidence") is not None:
            gate_asset = verify_record(
                frame.get("gateEvidence"),
                f"frame {index} gateEvidence",
                require_bytes=False,
            )
            if gate_asset is not None:
                gate, gate_error = _validated_evidence(gate_asset, TRANSFER_FRAME_GATE_SCHEMA)
                if gate is None and gate_error:
                    errors.append(gate_error)
    if len(times) == len(frames) and any(
        right <= left for left, right in zip(times, times[1:])
    ):
        errors.append("frame times are not strictly increasing")
    coverage = manifest.get("coverage")
    if isinstance(coverage, Mapping) and len(times) == len(frames) and len(times) >= 2:
        try:
            start = float(coverage["expectedStartMetricTimeM"])
            end = float(coverage["expectedEndMetricTimeM"])
            declared_gap = float(coverage["declaredMaxGapM"])
            actual_gap = max(right - left for left, right in zip(times, times[1:]))
            if claimed_ready and (
                times[0] != start
                or times[-1] != end
                or actual_gap > declared_gap * (1.0 + 1.0e-12)
            ):
                errors.append("manifest coverage is incomplete")
            if not math.isclose(actual_gap, float(coverage["actualMaxGapM"]), rel_tol=1.0e-12):
                errors.append("manifest actualMaxGapM is inconsistent")
        except (KeyError, TypeError, ValueError):
            errors.append("manifest coverage is malformed")
    else:
        errors.append("manifest coverage is missing")
    reasons = manifest.get("readinessReasons")
    if not isinstance(reasons, list) or not all(isinstance(reason, str) for reason in reasons):
        errors.append("manifest readinessReasons is malformed")
    elif claimed_ready and reasons:
        errors.append("ready manifest cannot retain readinessReasons")
    elif not claimed_ready and not reasons:
        errors.append("incomplete manifest must explain why it is not ready")
    ready = claimed_ready and not errors
    return ManifestValidation(not errors, ready, tuple(errors))


def select_time_bracket(metric_times: Sequence[float], metric_time: float) -> tuple[int, int, float]:
    times = np.asarray(metric_times, dtype=np.float64)
    if times.ndim != 1 or times.size < 2 or not np.all(np.isfinite(times)):
        raise ValueError("metric_times must contain at least two finite samples")
    if not np.all(np.diff(times) > 0.0):
        raise ValueError("metric_times must be strictly increasing")
    if not math.isfinite(metric_time) or metric_time < times[0] or metric_time > times[-1]:
        raise ValueError("metric_time lies outside the accepted keyframe interval")
    if metric_time == times[-1]:
        return times.size - 1, times.size - 1, 0.0
    right = int(np.searchsorted(times, metric_time, side="right"))
    left = max(0, right - 1)
    if metric_time == times[left]:
        return left, left, 0.0
    alpha = float((metric_time - times[left]) / (times[right] - times[left]))
    return left, right, alpha


def interpolate_discrete_code(left: int, right: int) -> int | None:
    """Return the common class, or ``None`` rather than inventing a transition."""

    return int(left) if int(left) == int(right) else None


def interpolate_escape_direction(
    left: Sequence[float],
    right: Sequence[float],
    alpha: float,
    *,
    left_valid: bool,
    right_valid: bool,
    antipodal_limit: float = -0.999,
) -> tuple[np.ndarray, bool]:
    if not left_valid or not right_valid or not 0.0 <= alpha <= 1.0:
        return np.full(3, np.nan), False
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    if a.shape != (3,) or b.shape != (3,) or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        return np.full(3, np.nan), False
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a <= 1.0e-12 or norm_b <= 1.0e-12:
        return np.full(3, np.nan), False
    a /= norm_a
    b /= norm_b
    if float(np.dot(a, b)) <= antipodal_limit:
        return np.full(3, np.nan), False
    mixed = (1.0 - alpha) * a + alpha * b
    norm = float(np.linalg.norm(mixed))
    if norm <= 1.0e-12:
        return np.full(3, np.nan), False
    return mixed / norm, True


def interpolate_disk_sample(
    left_transfer: Sequence[float],
    left_redshift: Sequence[float],
    right_transfer: Sequence[float],
    right_redshift: Sequence[float],
    alpha: float,
    *,
    min_coverage: float = 1.0e-6,
) -> tuple[np.ndarray, np.ndarray, bool]:
    """Interpolate one matching disk order using coverage-premultiplied inputs."""

    arrays = [
        np.asarray(value, dtype=np.float64)
        for value in (left_transfer, left_redshift, right_transfer, right_redshift)
    ]
    if any(value.shape != (4,) or not np.all(np.isfinite(value)) for value in arrays):
        return np.zeros(4), np.zeros(4), False
    if not 0.0 <= alpha <= 1.0 or min_coverage <= 0.0:
        return np.zeros(4), np.zeros(4), False
    left_t, left_g, right_t, right_g = arrays
    coverage_left = float(left_t[3])
    coverage_right = float(right_t[3])
    if coverage_left < min_coverage or coverage_right < min_coverage:
        return np.zeros(4), np.zeros(4), False

    radius_left = left_t[0] / coverage_left
    radius_right = right_t[0] / coverage_right
    phase_left = left_t[1:3] / coverage_left
    phase_right = right_t[1:3] / coverage_right
    phase_left_norm = float(np.linalg.norm(phase_left))
    phase_right_norm = float(np.linalg.norm(phase_right))
    if phase_left_norm <= 1.0e-12 or phase_right_norm <= 1.0e-12:
        return np.zeros(4), np.zeros(4), False
    phase = (1.0 - alpha) * phase_left / phase_left_norm + alpha * phase_right / phase_right_norm
    phase_norm = float(np.linalg.norm(phase))
    if phase_norm <= 1.0e-12:
        return np.zeros(4), np.zeros(4), False
    phase /= phase_norm

    coverage = (1.0 - alpha) * coverage_left + alpha * coverage_right
    radius = (1.0 - alpha) * radius_left + alpha * radius_right
    redshift_left = left_g[0] / coverage_left
    redshift_right = right_g[0] / coverage_right
    redshift = (1.0 - alpha) * redshift_left + alpha * redshift_right
    if coverage < min_coverage or radius <= 0.0 or redshift <= 0.0:
        return np.zeros(4), np.zeros(4), False

    transfer = np.array(
        [radius * coverage, phase[0] * coverage, phase[1] * coverage, coverage],
        dtype=np.float64,
    )
    redshift_buffer = np.array([redshift * coverage, 0.0, 0.0, 0.0], dtype=np.float64)
    return transfer, redshift_buffer, True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True, help="source sequence specification")
    parser.add_argument("--out", type=Path, required=True, help="output audited manifest")
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="write a fail-closed manifest even when independent gates are missing or failed",
    )
    args = parser.parse_args(argv)
    manifest = build_time_indexed_manifest(args.spec, args.out)
    print(json.dumps({
        "out": str(args.out),
        "runtimeAssetReady": manifest["runtimeAssetReady"],
        "readinessReasons": manifest["readinessReasons"],
        "frameCount": manifest["coverage"]["frameCount"],
    }, indent=2))
    if not manifest["runtimeAssetReady"] and not args.allow_incomplete:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
