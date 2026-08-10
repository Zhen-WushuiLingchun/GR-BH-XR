"""Versioned ADM-volume snapshots for audited numerical-relativity rays.

The schema stores primitive 3+1 fields rather than RGB images or waveform
modes.  A consumer can therefore reconstruct the four-metric and the complete
Hamiltonian force while preserving producer, gauge, AMR, interpolation, and
checksum provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import h5py
import numpy as np

from .dynamic_types import TimeDependentMetricProvider


SCHEMA = "gr-bh-xr.bbh.adm-snapshot.v1"
REQUIRED_METADATA_KEYS = (
    "producer",
    "formulation",
    "gauge",
    "coordinate_system",
    "units",
    "constraint_history",
    "source_kind",
)


class SnapshotCompatibilityError(ValueError):
    """Structured fail-closed error for unsupported NR products."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"reason_code": self.reason_code, "message": self.message}


@dataclass(frozen=True)
class SnapshotInspection:
    compatible: bool
    reason_code: str
    message: str
    schema: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "compatible": self.compatible,
            "reason_code": self.reason_code,
            "message": self.message,
            "schema": self.schema,
        }


@dataclass(frozen=True)
class ADMSnapshotLevel:
    """One uniform Cartesian AMR level.

    Arrays use ``(time,x,y,z,...)`` order. ``valid_lower`` and ``valid_upper``
    describe the closed coordinate region in which this level may supply a
    complete multilinear stencil.  Raw array extent outside that region is
    guard data and is never selected silently.
    """

    level_id: int
    parent_level: int | None
    origin: np.ndarray
    spacing: np.ndarray
    valid_lower: np.ndarray
    valid_upper: np.ndarray
    lapse: np.ndarray
    shift: np.ndarray
    gamma_cov: np.ndarray
    spatial_error_bound: np.ndarray

    def __post_init__(self) -> None:
        for name in ("origin", "spacing", "valid_lower", "valid_upper"):
            value = np.asarray(getattr(self, name), dtype=np.float64)
            if value.shape != (3,) or not np.all(np.isfinite(value)):
                raise ValueError(f"{name} must be a finite three-vector.")
            object.__setattr__(self, name, value)
        lapse = np.asarray(self.lapse, dtype=np.float64)
        shift = np.asarray(self.shift, dtype=np.float64)
        gamma = np.asarray(self.gamma_cov, dtype=np.float64)
        error = np.asarray(self.spatial_error_bound, dtype=np.float64)
        if lapse.ndim != 4 or min(lapse.shape[1:]) < 2:
            raise ValueError("lapse must have shape (nt,nx,ny,nz) with each grid axis >=2.")
        if shift.shape != lapse.shape + (3,):
            raise ValueError("shift must have shape lapse.shape+(3,).")
        if gamma.shape != lapse.shape + (3, 3):
            raise ValueError("gamma_cov must have shape lapse.shape+(3,3).")
        if error.shape != (lapse.shape[0],):
            raise ValueError("spatial_error_bound must contain one value per time slice.")
        if not np.all(np.isfinite(lapse)) or np.any(lapse <= 0.0):
            raise ValueError("lapse samples must be positive and finite.")
        if not np.all(np.isfinite(shift)) or not np.all(np.isfinite(gamma)):
            raise ValueError("ADM field arrays must be finite.")
        if not np.all(np.isfinite(error)) or np.any(error < 0.0):
            raise ValueError("spatial_error_bound must be finite and nonnegative.")
        if np.any(self.spacing <= 0.0):
            raise ValueError("spacing must be positive.")
        raw_upper = self.origin + self.spacing * (np.asarray(lapse.shape[1:]) - 1)
        tolerance = 1.0e-12 * np.maximum(1.0, np.maximum(np.abs(self.origin), np.abs(raw_upper)))
        if np.any(self.valid_lower < self.origin - tolerance) or np.any(
            self.valid_upper > raw_upper + tolerance
        ):
            raise ValueError("valid bounds must lie within the raw grid extent.")
        if np.any(self.valid_upper <= self.valid_lower):
            raise ValueError("valid_upper must exceed valid_lower on every axis.")
        object.__setattr__(self, "lapse", lapse)
        object.__setattr__(self, "shift", shift)
        object.__setattr__(self, "gamma_cov", gamma)
        object.__setattr__(self, "spatial_error_bound", error)

    @property
    def grid_shape(self) -> tuple[int, int, int]:
        return tuple(int(value) for value in self.lapse.shape[1:])


@dataclass(frozen=True)
class NRADMSnapshot:
    times: np.ndarray
    levels: tuple[ADMSnapshotLevel, ...]
    temporal_error_bound: np.ndarray
    metadata: Mapping[str, Any]
    source_path: Path | None = None

    def __post_init__(self) -> None:
        times = np.asarray(self.times, dtype=np.float64)
        temporal_error = np.asarray(self.temporal_error_bound, dtype=np.float64)
        if times.ndim != 1 or times.size < 2 or not np.all(np.isfinite(times)):
            raise ValueError("times must be a finite one-dimensional array with >=2 entries.")
        if np.any(np.diff(times) <= 0.0):
            raise ValueError("times must be strictly increasing.")
        if temporal_error.shape != (times.size - 1,):
            raise ValueError("temporal_error_bound must contain one value per interval.")
        if np.any(temporal_error < 0.0) or not np.all(np.isfinite(temporal_error)):
            raise ValueError("temporal_error_bound must be finite and nonnegative.")
        if not self.levels:
            raise ValueError("at least one AMR level is required.")
        level_ids = [level.level_id for level in self.levels]
        if len(set(level_ids)) != len(level_ids):
            raise ValueError("AMR level IDs must be unique.")
        by_id = {level.level_id: level for level in self.levels}
        for level in self.levels:
            if level.lapse.shape[0] != times.size:
                raise ValueError("every AMR level must contain every declared time slice.")
            if level.parent_level is not None:
                if level.parent_level not in by_id:
                    raise ValueError(f"AMR parent level {level.parent_level} does not exist.")
                if level.parent_level == level.level_id:
                    raise ValueError("an AMR level cannot be its own parent.")
                parent = by_id[level.parent_level]
                if np.any(level.spacing >= parent.spacing):
                    raise ValueError("a child AMR level must be finer than its parent on every axis.")
        validate_snapshot_metadata(self.metadata)
        object.__setattr__(self, "times", times)
        object.__setattr__(self, "temporal_error_bound", temporal_error)
        object.__setattr__(self, "levels", tuple(self.levels))
        object.__setattr__(self, "metadata", dict(self.metadata))


def validate_snapshot_metadata(metadata: Mapping[str, Any]) -> None:
    missing = [key for key in REQUIRED_METADATA_KEYS if key not in metadata]
    if missing:
        raise SnapshotCompatibilityError(
            "missing_provenance",
            f"ADM snapshot metadata is missing required keys: {', '.join(missing)}.",
        )
    producer = metadata["producer"]
    if not isinstance(producer, Mapping) or any(
        not str(producer.get(key, "")).strip() for key in ("name", "version", "commit")
    ):
        raise SnapshotCompatibilityError(
            "missing_producer_revision",
            "producer must declare non-empty name, version, and commit fields.",
        )
    if metadata["source_kind"] != "adm_volume":
        raise SnapshotCompatibilityError(
            "waveform_only_asset" if metadata["source_kind"] == "waveform_only" else "unsupported_source_kind",
            "Strong-field ray tracing requires evolved ADM volume fields, not waveform-only data.",
        )


def _array_digest(array: np.ndarray) -> str:
    values = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(values.dtype.str.encode("ascii"))
    digest.update(np.asarray(values.shape, dtype=np.int64).tobytes())
    digest.update(values.tobytes(order="C"))
    return digest.hexdigest()


def write_nr_snapshot(path: Path | str, snapshot: NRADMSnapshot) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    checksums: dict[str, str] = {}
    with h5py.File(output, "w") as handle:
        handle.attrs["schema"] = SCHEMA
        handle.attrs["metadata_json"] = json.dumps(snapshot.metadata, sort_keys=True)
        handle.attrs["component_order"] = "t,x,y,z"
        handle.attrs["spatial_interpolation"] = "cell-local trilinear"
        handle.attrs["temporal_interpolation"] = "piecewise linear"
        handle.attrs["checksum_algorithm"] = "sha256(dtype,shape,C-order-bytes)"

        def store(name: str, values: np.ndarray) -> None:
            array = np.asarray(values)
            handle.create_dataset(name, data=array, compression="gzip", shuffle=True)
            checksums[f"/{name}"] = _array_digest(array)

        store("times", snapshot.times)
        store("temporal_error_bound", snapshot.temporal_error_bound)
        levels_group = handle.create_group("levels")
        for level in sorted(snapshot.levels, key=lambda item: item.level_id):
            group = levels_group.create_group(str(level.level_id))
            group.attrs["level_id"] = level.level_id
            group.attrs["parent_level"] = -1 if level.parent_level is None else level.parent_level
            group.attrs["origin"] = level.origin
            group.attrs["spacing"] = level.spacing
            group.attrs["valid_lower"] = level.valid_lower
            group.attrs["valid_upper"] = level.valid_upper
            for field_name, values in (
                ("lapse", level.lapse),
                ("shift", level.shift),
                ("gamma_cov", level.gamma_cov),
                ("spatial_error_bound", level.spatial_error_bound),
            ):
                dataset_path = f"levels/{level.level_id}/{field_name}"
                handle.create_dataset(dataset_path, data=values, compression="gzip", shuffle=True)
                checksums[f"/{dataset_path}"] = _array_digest(values)
        handle.attrs["checksums_json"] = json.dumps(checksums, sort_keys=True)
    return output


def load_nr_snapshot(path: Path | str, *, verify_checksums: bool = True) -> NRADMSnapshot:
    source = Path(path)
    inspection = inspect_nr_asset(source)
    if not inspection.compatible:
        raise SnapshotCompatibilityError(inspection.reason_code, inspection.message)
    with h5py.File(source, "r") as handle:
        metadata = json.loads(str(handle.attrs["metadata_json"]))
        checksums = json.loads(str(handle.attrs.get("checksums_json", "{}")))

        def read(name: str) -> np.ndarray:
            values = np.asarray(handle[name])
            if verify_checksums:
                expected = checksums.get(f"/{name}")
                if expected is None:
                    raise SnapshotCompatibilityError(
                        "missing_checksum", f"Dataset /{name} has no checksum entry."
                    )
                actual = _array_digest(values)
                if actual != expected:
                    raise SnapshotCompatibilityError(
                        "checksum_mismatch", f"Checksum mismatch for dataset /{name}."
                    )
            return values

        times = read("times")
        temporal_error = read("temporal_error_bound")
        levels: list[ADMSnapshotLevel] = []
        for name in sorted(handle["levels"], key=lambda value: int(value)):
            group = handle[f"levels/{name}"]
            level_id = int(group.attrs["level_id"])
            parent = int(group.attrs["parent_level"])
            levels.append(
                ADMSnapshotLevel(
                    level_id=level_id,
                    parent_level=None if parent < 0 else parent,
                    origin=np.asarray(group.attrs["origin"]),
                    spacing=np.asarray(group.attrs["spacing"]),
                    valid_lower=np.asarray(group.attrs["valid_lower"]),
                    valid_upper=np.asarray(group.attrs["valid_upper"]),
                    lapse=read(f"levels/{name}/lapse"),
                    shift=read(f"levels/{name}/shift"),
                    gamma_cov=read(f"levels/{name}/gamma_cov"),
                    spatial_error_bound=read(f"levels/{name}/spatial_error_bound"),
                )
            )
    return NRADMSnapshot(
        times=times,
        levels=tuple(levels),
        temporal_error_bound=temporal_error,
        metadata=metadata,
        source_path=source.resolve(),
    )


def inspect_nr_asset(path: Path | str) -> SnapshotInspection:
    source = Path(path)
    if not source.exists():
        return SnapshotInspection(False, "missing_asset", f"Snapshot does not exist: {source}")
    try:
        with h5py.File(source, "r") as handle:
            schema = str(handle.attrs.get("schema", "")) or None
            if schema == SCHEMA:
                required = {"times", "temporal_error_bound", "levels"}
                missing = sorted(required.difference(handle.keys()))
                if missing:
                    return SnapshotInspection(
                        False,
                        "missing_adm_fields",
                        f"Snapshot is missing required root objects: {', '.join(missing)}.",
                        schema,
                    )
                missing_attrs = [
                    name
                    for name in ("metadata_json", "checksums_json")
                    if name not in handle.attrs
                ]
                if missing_attrs:
                    return SnapshotInspection(
                        False,
                        "missing_provenance",
                        f"Snapshot is missing required attributes: {', '.join(missing_attrs)}.",
                        schema,
                    )
                return SnapshotInspection(True, "compatible", "Audited ADM volume schema.", schema)
            names: list[str] = []
            handle.visit(names.append)
            lowered = " ".join(names).lower()
            waveform_tokens = ("psi4", "strain", "rh_over_m", "y_l2_m2", "waveform")
            if any(token in lowered for token in waveform_tokens):
                return SnapshotInspection(
                    False,
                    "waveform_only_asset",
                    "Waveform/horizon products do not provide an evolved near-zone ADM volume.",
                    schema,
                )
            return SnapshotInspection(
                False,
                "unsupported_schema",
                "Input is not gr-bh-xr.bbh.adm-snapshot.v1 and needs an explicit converter.",
                schema,
            )
    except OSError as exc:
        return SnapshotInspection(False, "unreadable_asset", f"HDF5 open failed: {exc}")


def sample_provider_level(
    provider: TimeDependentMetricProvider,
    *,
    times: Sequence[float],
    axes: tuple[Sequence[float], Sequence[float], Sequence[float]],
    level_id: int = 0,
    parent_level: int | None = None,
    valid_lower: Sequence[float] | None = None,
    valid_upper: Sequence[float] | None = None,
    spatial_error_bound: Sequence[float] | None = None,
) -> ADMSnapshotLevel:
    """Sample an analytic/provider oracle into one uniform ADM level."""

    time_values = np.asarray(times, dtype=np.float64)
    coordinates = tuple(np.asarray(axis, dtype=np.float64) for axis in axes)
    for axis in coordinates:
        if axis.ndim != 1 or axis.size < 2 or np.any(np.diff(axis) <= 0.0):
            raise ValueError("each coordinate axis must be strictly increasing with >=2 nodes.")
        spacing = np.diff(axis)
        if not np.allclose(spacing, spacing[0], rtol=1.0e-12, atol=1.0e-14):
            raise ValueError("schema v1 levels require uniform spacing.")
    shape = (time_values.size,) + tuple(axis.size for axis in coordinates)
    lapse = np.empty(shape, dtype=np.float64)
    shift = np.empty(shape + (3,), dtype=np.float64)
    gamma = np.empty(shape + (3, 3), dtype=np.float64)
    for ti, time in enumerate(time_values):
        for ix, x in enumerate(coordinates[0]):
            for iy, y in enumerate(coordinates[1]):
                for iz, z in enumerate(coordinates[2]):
                    sample = provider.sample(float(time), np.array([x, y, z]))
                    if sample.validity != "valid":
                        raise SnapshotCompatibilityError(
                            "provider_invalid_sample",
                            f"Provider was {sample.validity} at t={time}, x={(x, y, z)}.",
                        )
                    lapse[ti, ix, iy, iz] = sample.lapse
                    shift[ti, ix, iy, iz] = sample.shift
                    gamma[ti, ix, iy, iz] = sample.gamma_cov
    lower = np.asarray(valid_lower if valid_lower is not None else [axis[0] for axis in coordinates])
    upper = np.asarray(valid_upper if valid_upper is not None else [axis[-1] for axis in coordinates])
    errors = np.asarray(
        spatial_error_bound if spatial_error_bound is not None else np.zeros(time_values.size),
        dtype=np.float64,
    )
    return ADMSnapshotLevel(
        level_id=level_id,
        parent_level=parent_level,
        origin=np.array([axis[0] for axis in coordinates]),
        spacing=np.array([axis[1] - axis[0] for axis in coordinates]),
        valid_lower=lower,
        valid_upper=upper,
        lapse=lapse,
        shift=shift,
        gamma_cov=gamma,
        spatial_error_bound=errors,
    )


def default_synthetic_metadata(*, producer_commit: str = "synthetic") -> dict[str, Any]:
    return {
        "producer": {
            "name": "gr-bh-xr synthetic ADM gate",
            "version": "1",
            "commit": producer_commit,
        },
        "formulation": "analytic 3+1 sampling",
        "gauge": "source-provider coordinates",
        "coordinate_system": "Cartesian (t,x,y,z), signature (-,+,+,+)",
        "units": {"system": "geometric", "G": 1, "c": 1, "mass_scale": "declared by case"},
        "constraint_history": {"kind": "analytic_or_independently_validated", "samples": []},
        "source_kind": "adm_volume",
    }
