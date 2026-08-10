"""Explicit field-map converter from CarpetX/openPMD-like HDF5 to ADM v1.

The converter intentionally does not guess thorn field names.  A producer-side
field map and provenance JSON are required so gauge and component conventions
cannot drift silently between Einstein Toolkit releases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import h5py
import numpy as np

from .nr_snapshot import (
    ADMSnapshotLevel,
    NRADMSnapshot,
    SnapshotCompatibilityError,
    inspect_nr_asset,
    write_nr_snapshot,
)


def convert_carpetx_snapshot(
    input_path: Path | str,
    output_path: Path | str,
    *,
    field_map: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> Path:
    """Convert explicitly mapped ADM arrays from an HDF5/openPMD export."""

    source = Path(input_path)
    if not source.exists():
        raise SnapshotCompatibilityError("missing_asset", f"Input does not exist: {source}")
    if "times" not in field_map or "levels" not in field_map:
        inspection = inspect_nr_asset(source)
        if inspection.reason_code == "waveform_only_asset":
            raise SnapshotCompatibilityError(inspection.reason_code, inspection.message)
        raise SnapshotCompatibilityError(
            "missing_field_map",
            "field_map must declare a times dataset and at least one ADM level.",
        )

    with h5py.File(source, "r") as handle:
        times = _read_dataset(handle, str(field_map["times"]))
        levels: list[ADMSnapshotLevel] = []
        for spec in field_map["levels"]:
            lapse = _read_dataset(handle, str(spec["lapse"]))
            shift = np.stack(
                [_read_dataset(handle, str(path)) for path in spec["shift"]], axis=-1
            )
            gamma_components = [
                [_read_dataset(handle, str(path)) for path in row]
                for row in spec["gamma_cov"]
            ]
            gamma = np.empty(lapse.shape + (3, 3), dtype=np.float64)
            for i in range(3):
                for j in range(3):
                    gamma[..., i, j] = gamma_components[i][j]
            error_spec = spec.get("spatial_error_bound")
            if isinstance(error_spec, str):
                spatial_error = _read_dataset(handle, error_spec)
            else:
                spatial_error = np.asarray(
                    error_spec if error_spec is not None else np.zeros(times.size),
                    dtype=np.float64,
                )
            levels.append(
                ADMSnapshotLevel(
                    level_id=int(spec["level_id"]),
                    parent_level=(
                        None if spec.get("parent_level") is None else int(spec["parent_level"])
                    ),
                    origin=np.asarray(spec["origin"], dtype=np.float64),
                    spacing=np.asarray(spec["spacing"], dtype=np.float64),
                    valid_lower=np.asarray(spec["valid_lower"], dtype=np.float64),
                    valid_upper=np.asarray(spec["valid_upper"], dtype=np.float64),
                    lapse=lapse,
                    shift=shift,
                    gamma_cov=gamma,
                    spatial_error_bound=spatial_error,
                )
            )
        temporal_spec = field_map.get("temporal_error_bound")
        if isinstance(temporal_spec, str):
            temporal_error = _read_dataset(handle, temporal_spec)
        else:
            temporal_error = np.asarray(
                temporal_spec
                if temporal_spec is not None
                else np.zeros(max(0, times.size - 1)),
                dtype=np.float64,
            )

    converted_metadata = dict(metadata)
    converted_metadata["conversion"] = {
        "tool": "gr_bh_xr.convert_carpetx_snapshot",
        "input": str(source.resolve()),
        "input_sha256": _file_sha256(source),
        "field_map": field_map,
    }
    snapshot = NRADMSnapshot(
        times=times,
        levels=tuple(levels),
        temporal_error_bound=temporal_error,
        metadata=converted_metadata,
    )
    return write_nr_snapshot(output_path, snapshot)


def _read_dataset(handle: h5py.File, path: str) -> np.ndarray:
    normalized = path.lstrip("/")
    if normalized not in handle:
        raise SnapshotCompatibilityError(
            "missing_adm_field", f"Mapped dataset does not exist: {path}"
        )
    return np.asarray(handle[normalized], dtype=np.float64)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--field-map", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args()
    field_map = json.loads(args.field_map.read_text(encoding="utf8"))
    metadata = json.loads(args.metadata.read_text(encoding="utf8"))
    output = convert_carpetx_snapshot(
        args.input, args.out, field_map=field_map, metadata=metadata
    )
    print(json.dumps({"schema": "gr-bh-xr.bbh.adm-snapshot.v1", "out": str(output.resolve())}))


if __name__ == "__main__":
    main()
