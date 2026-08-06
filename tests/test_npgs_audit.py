import json
from pathlib import Path

import h5py
import numpy as np
import pytest

from gr_bh_xr.npgs_audit import (
    RAW_SCHEMA,
    SCHEMA,
    convert_native_audit,
    load_native_audit,
)


def _write_capture(tmp_path: Path) -> tuple[Path, Path]:
    raw = tmp_path / "audit.bin"
    metadata_path = tmp_path / "audit.bin.json"
    records = np.zeros((2, 2, 32), dtype="<f4")
    records[..., 2] = 4.0
    records[..., 3] = 12.0
    records[..., 14] = 3.0
    records[..., 15] = 1.0
    records[0, 0, 0] = 0.0
    records[0, 1:, 0] = 1.0
    records[1, :, 0] = 1.0
    records[0, 1:, 4:7] = [1.0, 0.0, 0.0]
    records[1, :, 4:7] = [0.0, 0.0, 1.0]
    records[records[..., 0] == 1.0, 7] = 1.0
    records[..., 8] = 1.0e-3
    records[..., 9] = 1.0e-5
    records[..., 10] = 2.0e-4
    records[..., 11] = 3.0e-4
    records.tofile(raw)

    metadata = {
        "schema": RAW_SCHEMA,
        "dtype": "float32-little-endian",
        "record_float_count": 32,
        "record_bytes": 128,
        "width": 2,
        "height": 2,
        "row_order": "visual top first",
        "parameters": {
            "M_internal": 0.5,
            "spin_a_over_M": 0.9,
            "charge_Q_over_M": 0.0,
            "inclination_deg": 60.0,
            "r_obs_M": 100.0,
            "r_obs_internal": 50.0,
            "fov_deg": 16.0,
            "quality": 1.0,
            "observer_mode": "static",
            "spin_axis": [0.0, 1.0, 0.0],
        },
        "device": {"name": "synthetic", "driver_version_raw": 1},
        "claims": {
            "disk_transfer_slots_valid": False,
            "raw_hamiltonian_is_pre_projection": True,
        },
        "event_codes": {"capture": 0, "escape": 1, "invalid": 3},
        "failure_codes": {"none": 0, "step_budget_exhausted": 2},
        "summary": {
            "pixels": 4,
            "capture": 1,
            "escape": 3,
            "invalid": 0,
            "nonfinite_records": 0,
        },
    }
    metadata_path.write_text(json.dumps(metadata), encoding="utf8")
    return raw, metadata_path


def test_load_native_audit_validates_and_converts_native_units(tmp_path: Path) -> None:
    raw, metadata = _write_capture(tmp_path)
    capture = load_native_audit(raw, metadata_path=metadata)

    assert capture.records.shape == (2, 2, 32)
    assert capture.event_code.dtype == np.int8
    assert capture.steps.dtype == np.uint32
    np.testing.assert_allclose(capture.min_r_m, 8.0)
    assert np.count_nonzero(capture.escape_valid) == 3
    assert np.all(np.isnan(capture.disk_r_m))


def test_convert_native_audit_writes_final_hdf5_and_json(tmp_path: Path) -> None:
    raw, metadata = _write_capture(tmp_path)
    out_h5 = tmp_path / "audit.h5"
    out_json = tmp_path / "audit.json"

    summary = convert_native_audit(
        raw,
        metadata_path=metadata,
        out_h5=out_h5,
        out_json=out_json,
        npgs_root=None,
        command="pytest",
    )

    assert summary["schema"] == SCHEMA
    assert summary["event_counts"] == {"capture": 1, "escape": 3, "invalid": 0}
    assert summary["failure_counts"] == {"none": 4, "step_budget_exhausted": 0}
    assert summary["disk_valid_by_order"] == [0, 0]
    assert json.loads(out_json.read_text(encoding="utf8"))["max_steps"] == 12

    with h5py.File(out_h5, "r") as handle:
        assert handle.attrs["schema"] == SCHEMA
        assert handle.attrs["M_internal"] == 0.5
        assert handle.attrs["generation_command"] == "pytest"
        assert handle["raw_record_f32"].shape == (2, 2, 32)
        assert handle["escape_dir"].shape == (2, 2, 3)
        assert handle["disk_r_m"].shape == (2, 2, 2)
        np.testing.assert_allclose(handle["min_r_M"][...], 8.0)


def test_load_native_audit_rejects_truncated_and_inconsistent_records(tmp_path: Path) -> None:
    raw, metadata = _write_capture(tmp_path)
    raw.write_bytes(raw.read_bytes()[:-4])
    with pytest.raises(ValueError, match="byte length"):
        load_native_audit(raw, metadata_path=metadata)

    raw, metadata = _write_capture(tmp_path)
    records = np.fromfile(raw, dtype="<f4").reshape(2, 2, 32)
    records[0, 0, 7] = 1.0
    records.tofile(raw)
    with pytest.raises(ValueError, match="escape_valid"):
        load_native_audit(raw, metadata_path=metadata)


def test_load_native_audit_rejects_nonfinite_or_unknown_codes(tmp_path: Path) -> None:
    raw, metadata = _write_capture(tmp_path)
    records = np.fromfile(raw, dtype="<f4").reshape(2, 2, 32)
    records[0, 0, 8] = np.nan
    records.tofile(raw)
    with pytest.raises(ValueError, match="non-finite"):
        load_native_audit(raw, metadata_path=metadata)

    raw, metadata = _write_capture(tmp_path)
    records = np.fromfile(raw, dtype="<f4").reshape(2, 2, 32)
    records[0, 0, 0] = 9.0
    records.tofile(raw)
    with pytest.raises(ValueError, match="unknown event"):
        load_native_audit(raw, metadata_path=metadata)
