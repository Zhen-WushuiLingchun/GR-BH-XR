"""Convert native NPGS audit captures into versioned GR-BH-XR artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import h5py
import numpy as np

from .npgs_contract import (
    SCHEMA as INTEGRATION_SCHEMA,
    accepted_features,
    integration_manifest,
    validate_native_integration_metadata,
)


RAW_SCHEMA_V1 = "gr-bh-xr.npgs.audit.raw.v1"
RAW_SCHEMA_V2 = "gr-bh-xr.npgs.audit.raw.v2"
RAW_SCHEMA_V3 = "gr-bh-xr.npgs.audit.raw.v3"
RAW_SCHEMA_V4 = "gr-bh-xr.npgs.audit.raw.v4"
RAW_SCHEMA = RAW_SCHEMA_V4
SCHEMA = "gr-bh-xr.npgs.audit.v1"
RECORD_FLOAT_COUNTS = {
    RAW_SCHEMA_V1: 32,
    RAW_SCHEMA_V2: 48,
    RAW_SCHEMA_V3: 64,
    RAW_SCHEMA_V4: 72,
}
DISK_ORDERS = 2


@dataclass(frozen=True)
class NpgsAuditCapture:
    """Validated native capture in raw NPGS and normalized M units."""

    raw_path: Path
    metadata_path: Path
    metadata: dict[str, Any]
    records: np.ndarray
    event_code: np.ndarray
    failure_code: np.ndarray
    min_r_m: np.ndarray
    steps: np.ndarray
    escape_dir: np.ndarray
    escape_valid: np.ndarray
    h_max_raw_abs: np.ndarray
    h_max_projected_abs: np.ndarray
    momentum_correction_relative: np.ndarray
    q_drift_abs: np.ndarray
    e_drift_abs: np.ndarray
    l_spin_axis_drift_abs: np.ndarray
    q_samples: np.ndarray
    final_universe_sign: np.ndarray
    disk_r_m: np.ndarray
    disk_sin_phi_m: np.ndarray
    disk_cos_phi_m: np.ndarray
    disk_g_m: np.ndarray
    disk_delta_t_m: np.ndarray
    disk_order: np.ndarray
    disk_validity: np.ndarray
    disk_flags: np.ndarray
    initial_ingoing_x: np.ndarray | None
    initial_ingoing_p_cov: np.ndarray | None
    final_ingoing_x: np.ndarray | None
    final_ingoing_p_cov: np.ndarray | None
    camera_fx_cov_native: np.ndarray | None
    camera_fy_cov_native: np.ndarray | None
    camera_walker_penrose: np.ndarray | None
    camera_basis_diagnostics: np.ndarray | None
    dynamic_meta: np.ndarray | None
    dynamic_diagnostics: np.ndarray | None


def load_native_audit(
    raw_path: Path | str,
    *,
    metadata_path: Path | str | None = None,
) -> NpgsAuditCapture:
    """Load and fail-closed validate an NPGS native audit capture."""

    raw_path = Path(raw_path).resolve()
    if metadata_path is None:
        metadata_path = raw_path.with_name(raw_path.name + ".json")
    metadata_path = Path(metadata_path).resolve()
    metadata = json.loads(metadata_path.read_text(encoding="utf8"))
    _validate_metadata(metadata)

    height = _positive_int(metadata, "height")
    width = _positive_int(metadata, "width")
    raw_schema = str(metadata["schema"])
    record_float_count = RECORD_FLOAT_COUNTS[raw_schema]
    record_bytes = record_float_count * np.dtype("<f4").itemsize
    expected_bytes = height * width * record_bytes
    actual_bytes = raw_path.stat().st_size
    if actual_bytes != expected_bytes:
        raise ValueError(
            f"Raw audit byte length is {actual_bytes}; expected {expected_bytes} "
            f"for {width}x{height}x{record_float_count} float32 values."
        )

    records = np.fromfile(raw_path, dtype="<f4").reshape(height, width, record_float_count)
    if not np.all(np.isfinite(records)):
        bad = np.argwhere(~np.isfinite(records))[0]
        raise ValueError(
            "Raw audit contains a non-finite value at "
            f"row={bad[0]}, col={bad[1]}, field={bad[2]}."
        )

    event_code = _integer_field(records[..., 0], "event_code", np.int8)
    failure_code = _integer_field(records[..., 1], "failure_code", np.int16)
    steps = _integer_field(records[..., 3], "steps", np.uint32, minimum=0)
    q_samples = _integer_field(records[..., 14], "q_samples", np.uint32, minimum=0)
    _validate_codes(event_code, metadata["event_codes"], "event")
    _validate_codes(failure_code, metadata["failure_codes"], "failure")

    parameters = metadata["parameters"]
    mass_internal = float(parameters["M_internal"])
    if not np.isfinite(mass_internal) or mass_internal <= 0.0:
        raise ValueError("parameters.M_internal must be finite and positive.")

    escape_valid = _binary_field(records[..., 7], "escape_valid")
    escape_dir = records[..., 4:7].astype(np.float32, copy=True)
    escape_code = int(metadata["event_codes"]["escape"])
    expected_escape_valid = event_code == escape_code
    if not np.array_equal(escape_valid, expected_escape_valid):
        raise ValueError("escape_valid must be true exactly for escape event records.")
    if np.any(escape_valid):
        norms = np.linalg.norm(escape_dir[escape_valid].astype(np.float64), axis=-1)
        if np.max(np.abs(norms - 1.0)) > 5.0e-4:
            raise ValueError("A valid escape direction is not unit normalized within 5e-4.")

    disk_r = np.empty((DISK_ORDERS, height, width), dtype=np.float32)
    disk_sin_phi = np.empty_like(disk_r)
    disk_cos_phi = np.empty_like(disk_r)
    disk_g = np.empty_like(disk_r)
    disk_delta_t = np.empty_like(disk_r)
    disk_order = np.empty((DISK_ORDERS, height, width), dtype=np.int16)
    disk_validity = np.empty((DISK_ORDERS, height, width), dtype=bool)
    disk_flags = np.empty((DISK_ORDERS, height, width), dtype=np.int16)
    for order, start in enumerate((16, 24)):
        disk_r[order] = records[..., start] / mass_internal
        disk_sin_phi[order] = records[..., start + 1]
        disk_cos_phi[order] = records[..., start + 2]
        disk_g[order] = records[..., start + 3]
        disk_delta_t[order] = records[..., start + 4] / mass_internal
        disk_order[order] = _integer_field(
            records[..., start + 5], f"disk{order}_order", np.int16, minimum=0
        )
        disk_validity[order] = _binary_field(
            records[..., start + 6], f"disk{order}_validity"
        )
        disk_flags[order] = _integer_field(
            records[..., start + 7], f"disk{order}_flags", np.int16, minimum=0
        )

    if not bool(metadata["claims"]["disk_transfer_slots_valid"]):
        if np.any(disk_validity):
            raise ValueError(
                "Native metadata declares disk slots reserved, but valid disk records were emitted."
            )
    else:
        _validate_disk_transfer(
            metadata,
            disk_r=disk_r,
            disk_sin_phi=disk_sin_phi,
            disk_cos_phi=disk_cos_phi,
            disk_g=disk_g,
            disk_delta_t=disk_delta_t,
            disk_order=disk_order,
            disk_validity=disk_validity,
            disk_flags=disk_flags,
        )

    for values in (disk_r, disk_sin_phi, disk_cos_phi, disk_g, disk_delta_t):
        values[~disk_validity] = np.nan

    has_canonical_state = raw_schema in (RAW_SCHEMA_V2, RAW_SCHEMA_V3, RAW_SCHEMA_V4)
    initial_ingoing_x = records[..., 32:36].copy() if has_canonical_state else None
    initial_ingoing_p_cov = records[..., 36:40].copy() if has_canonical_state else None
    final_ingoing_x = records[..., 40:44].copy() if has_canonical_state else None
    final_ingoing_p_cov = records[..., 44:48].copy() if has_canonical_state else None
    has_camera_evidence = raw_schema in (RAW_SCHEMA_V3, RAW_SCHEMA_V4)
    camera_fx_cov_native = records[..., 48:52].copy() if has_camera_evidence else None
    camera_fy_cov_native = records[..., 52:56].copy() if has_camera_evidence else None
    camera_walker_penrose = records[..., 56:60].copy() if has_camera_evidence else None
    camera_basis_diagnostics = records[..., 60:64].copy() if has_camera_evidence else None
    dynamic_meta = records[..., 64:68].copy() if raw_schema == RAW_SCHEMA_V4 else None
    dynamic_diagnostics = records[..., 68:72].copy() if raw_schema == RAW_SCHEMA_V4 else None

    capture = NpgsAuditCapture(
        raw_path=raw_path,
        metadata_path=metadata_path,
        metadata=metadata,
        records=records,
        event_code=event_code,
        failure_code=failure_code,
        min_r_m=(records[..., 2] / mass_internal).astype(np.float32),
        steps=steps,
        escape_dir=escape_dir,
        escape_valid=escape_valid,
        h_max_raw_abs=records[..., 8].copy(),
        h_max_projected_abs=records[..., 9].copy(),
        momentum_correction_relative=records[..., 10].copy(),
        q_drift_abs=records[..., 11].copy(),
        e_drift_abs=records[..., 12].copy(),
        l_spin_axis_drift_abs=records[..., 13].copy(),
        q_samples=q_samples,
        final_universe_sign=records[..., 15].copy(),
        disk_r_m=disk_r,
        disk_sin_phi_m=disk_sin_phi,
        disk_cos_phi_m=disk_cos_phi,
        disk_g_m=disk_g,
        disk_delta_t_m=disk_delta_t,
        disk_order=disk_order,
        disk_validity=disk_validity,
        disk_flags=disk_flags,
        initial_ingoing_x=initial_ingoing_x,
        initial_ingoing_p_cov=initial_ingoing_p_cov,
        final_ingoing_x=final_ingoing_x,
        final_ingoing_p_cov=final_ingoing_p_cov,
        camera_fx_cov_native=camera_fx_cov_native,
        camera_fy_cov_native=camera_fy_cov_native,
        camera_walker_penrose=camera_walker_penrose,
        camera_basis_diagnostics=camera_basis_diagnostics,
        dynamic_meta=dynamic_meta,
        dynamic_diagnostics=dynamic_diagnostics,
    )
    _validate_native_summary(capture)
    return capture


def convert_native_audit(
    raw_path: Path | str,
    *,
    out_h5: Path | str,
    out_json: Path | str,
    metadata_path: Path | str | None = None,
    npgs_root: Path | str | None = None,
    command: str = "",
) -> dict[str, Any]:
    """Convert a validated raw capture into HDF5 plus a compact JSON summary."""

    capture = load_native_audit(raw_path, metadata_path=metadata_path)
    out_h5 = Path(out_h5).resolve()
    out_json = Path(out_json).resolve()
    out_h5.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    source = _source_revisions(npgs_root)
    summary = _build_summary(capture, source=source, out_h5=out_h5)
    _write_hdf5(capture, out_h5=out_h5, source=source, command=command)
    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
    return summary


def _write_hdf5(
    capture: NpgsAuditCapture,
    *,
    out_h5: Path,
    source: Mapping[str, str],
    command: str,
) -> None:
    metadata = capture.metadata
    parameters = metadata["parameters"]
    with h5py.File(out_h5, "w") as handle:
        handle.attrs["schema"] = SCHEMA
        handle.attrs["raw_schema"] = str(metadata["schema"])
        handle.attrs["source_raw_file"] = str(capture.raw_path)
        handle.attrs["source_metadata_file"] = str(capture.metadata_path)
        handle.attrs["generation_command"] = command
        handle.attrs["width"] = int(metadata["width"])
        handle.attrs["height"] = int(metadata["height"])
        handle.attrs["M"] = 1.0
        handle.attrs["M_internal"] = float(parameters["M_internal"])
        handle.attrs["a_over_M"] = float(parameters["spin_a_over_M"])
        handle.attrs["Q_charge_over_M"] = float(parameters["charge_Q_over_M"])
        handle.attrs["inclination_deg"] = float(parameters["inclination_deg"])
        handle.attrs["r_obs_M"] = float(parameters["r_obs_M"])
        handle.attrs["fov_deg"] = float(parameters["fov_deg"])
        handle.attrs["observer_mode"] = str(parameters["observer_mode"])
        handle.attrs["coordinate_system"] = "NPGS Cartesian Kerr-Schild"
        handle.attrs["units"] = "G = c = M = 1; native raw uses Rs = 1 and M_internal = 0.5"
        handle.attrs["row_order"] = str(metadata["row_order"])
        handle.attrs["npgs_upstream_sha"] = source["upstream_sha"]
        handle.attrs["npgs_fork_sha"] = source["fork_sha"]
        handle.attrs["audit_shader_sha256"] = source["audit_shader_sha256"]
        handle.attrs["device_json"] = json.dumps(metadata["device"], sort_keys=True)
        handle.attrs["claims_json"] = json.dumps(metadata["claims"], sort_keys=True)
        handle.attrs["integration_contract_schema"] = INTEGRATION_SCHEMA
        handle.attrs["accepted_integration_features_json"] = json.dumps(
            [feature.value for feature in accepted_features(metadata)]
        )
        handle.attrs["parameters_json"] = json.dumps(parameters, sort_keys=True)
        handle.attrs["source_metadata_json"] = json.dumps(metadata, sort_keys=True)

        handle.create_dataset(
            "raw_record_f32", data=capture.records, compression="gzip", shuffle=True
        )
        event_ds = handle.create_dataset(
            "event_code", data=capture.event_code, compression="gzip", shuffle=True
        )
        for name, code in metadata["event_codes"].items():
            event_ds.attrs[f"code_{name}"] = int(code)
        failure_ds = handle.create_dataset(
            "failure_code", data=capture.failure_code, compression="gzip", shuffle=True
        )
        for name, code in metadata["failure_codes"].items():
            failure_ds.attrs[f"code_{name}"] = int(code)

        datasets = {
            "min_r_M": capture.min_r_m,
            "steps": capture.steps,
            "escape_dir": capture.escape_dir,
            "escape_valid": capture.escape_valid.astype(np.uint8),
            "h_max_raw_abs": capture.h_max_raw_abs,
            "h_max_projected_abs": capture.h_max_projected_abs,
            "momentum_correction_relative": capture.momentum_correction_relative,
            "e_drift_abs": capture.e_drift_abs,
            "l_spin_axis_drift_abs": capture.l_spin_axis_drift_abs,
            "q_drift_abs": capture.q_drift_abs,
            "q_samples": capture.q_samples,
            "final_universe_sign": capture.final_universe_sign,
            "disk_r_m": capture.disk_r_m,
            "disk_sin_phi_m": capture.disk_sin_phi_m,
            "disk_cos_phi_m": capture.disk_cos_phi_m,
            "disk_g_m": capture.disk_g_m,
            "disk_delta_t_m": capture.disk_delta_t_m,
            "disk_order": capture.disk_order,
            "disk_validity": capture.disk_validity.astype(np.uint8),
            "disk_flags": capture.disk_flags,
        }
        for name, values in datasets.items():
            handle.create_dataset(name, data=values, compression="gzip", shuffle=True)
        state_datasets = {
            "initial_ingoing_x_native": capture.initial_ingoing_x,
            "initial_ingoing_p_cov_native": capture.initial_ingoing_p_cov,
            "final_ingoing_x_native": capture.final_ingoing_x,
            "final_ingoing_p_cov_native": capture.final_ingoing_p_cov,
            "camera_fx_cov_native": capture.camera_fx_cov_native,
            "camera_fy_cov_native": capture.camera_fy_cov_native,
            "camera_walker_penrose": capture.camera_walker_penrose,
            "camera_basis_diagnostics": capture.camera_basis_diagnostics,
            "dynamic_meta": capture.dynamic_meta,
            "dynamic_diagnostics": capture.dynamic_diagnostics,
        }
        for name, values in state_datasets.items():
            if values is not None:
                handle.create_dataset(name, data=values, compression="gzip", shuffle=True)


def _build_summary(
    capture: NpgsAuditCapture,
    *,
    source: Mapping[str, str],
    out_h5: Path,
) -> dict[str, Any]:
    metadata = capture.metadata
    event_counts = _named_counts(capture.event_code, metadata["event_codes"])
    failure_counts = _named_counts(capture.failure_code, metadata["failure_codes"])
    escape_norm_error = np.abs(
        np.linalg.norm(capture.escape_dir[capture.escape_valid].astype(np.float64), axis=-1) - 1.0
    )
    return {
        "schema": SCHEMA,
        "out_h5": str(out_h5),
        "source_raw": str(capture.raw_path),
        "width": int(metadata["width"]),
        "height": int(metadata["height"]),
        "parameters": metadata["parameters"],
        "device": metadata["device"],
        "source": dict(source),
        "event_counts": event_counts,
        "failure_counts": failure_counts,
        "disk_valid_by_order": [
            int(np.count_nonzero(capture.disk_validity[order]))
            for order in range(DISK_ORDERS)
        ],
        "canonical_state_present": capture.initial_ingoing_x is not None,
        "camera_polarization_evidence_present": bool(
            capture.metadata["claims"].get("camera_polarization_evidence_emitted", False)
        ) and capture.camera_fx_cov_native is not None,
        "dynamic_metric_evidence_present": capture.dynamic_meta is not None,
        "max_steps": int(np.max(capture.steps)),
        "max_raw_hamiltonian_abs": float(np.max(capture.h_max_raw_abs)),
        "max_projected_hamiltonian_abs": float(np.max(capture.h_max_projected_abs)),
        "max_momentum_correction_relative": float(
            np.max(capture.momentum_correction_relative)
        ),
        "max_energy_drift_abs": float(np.max(capture.e_drift_abs)),
        "max_spin_axis_angular_momentum_drift_abs": float(
            np.max(capture.l_spin_axis_drift_abs)
        ),
        "max_carter_drift_abs": float(np.max(capture.q_drift_abs)),
        "max_dynamic_hamiltonian_abs": float(
            np.max(np.abs(capture.dynamic_diagnostics[..., 2]))
        ) if capture.dynamic_diagnostics is not None else None,
        "max_dynamic_p_t_change_abs": float(
            np.max(np.abs(capture.dynamic_diagnostics[..., 3]))
        ) if capture.dynamic_diagnostics is not None else None,
        "max_escape_direction_norm_error": float(np.max(escape_norm_error))
        if escape_norm_error.size
        else None,
        "claims": metadata["claims"],
        "integration_contract_schema": INTEGRATION_SCHEMA,
        "accepted_integration_features": [
            feature.value for feature in accepted_features(metadata)
        ],
        "integration_status": integration_manifest()["features"],
    }


def _validate_metadata(metadata: Mapping[str, Any]) -> None:
    raw_schema = metadata.get("schema")
    if raw_schema not in RECORD_FLOAT_COUNTS:
        raise ValueError(f"Unsupported native audit schema: {metadata.get('schema')!r}.")
    if metadata.get("dtype") != "float32-little-endian":
        raise ValueError("Native audit dtype must be float32-little-endian.")
    record_float_count = RECORD_FLOAT_COUNTS[str(raw_schema)]
    record_bytes = record_float_count * np.dtype("<f4").itemsize
    if int(metadata.get("record_float_count", -1)) != record_float_count:
        raise ValueError(f"Native audit record must contain {record_float_count} floats.")
    if int(metadata.get("record_bytes", -1)) != record_bytes:
        raise ValueError(f"Native audit record must contain {record_bytes} bytes.")
    for key in ("parameters", "device", "claims", "event_codes", "failure_codes"):
        if not isinstance(metadata.get(key), Mapping):
            raise ValueError(f"Native audit metadata is missing object {key!r}.")
    validate_native_integration_metadata(metadata)
    if "escape" not in metadata["event_codes"]:
        raise ValueError("Native audit event mapping is missing 'escape'.")
    if "disk_transfer_slots_valid" not in metadata["claims"]:
        raise ValueError("Native audit claims omit disk_transfer_slots_valid.")
    if raw_schema in (RAW_SCHEMA_V2, RAW_SCHEMA_V3, RAW_SCHEMA_V4):
        contract = metadata.get("canonical_state_contract")
        if not isinstance(contract, Mapping):
            raise ValueError("Native audit canonical-state metadata is missing canonical_state_contract.")
        if contract.get("chart") != "ingoing Cartesian Kerr-Schild":
            raise ValueError("Native audit canonical states must use ingoing Cartesian Kerr-Schild.")
        if contract.get("component_order") != ["x", "y", "z", "t"]:
            raise ValueError("Native audit canonical state component order is not (x,y,z,t).")
        if contract.get("momentum_variance") != "covariant":
            raise ValueError("Native audit momentum must be covariant.")
    if raw_schema in (RAW_SCHEMA_V3, RAW_SCHEMA_V4):
        dynamic = bool(metadata["parameters"].get("bbh_enabled", False))
        if not dynamic and metadata["claims"].get("camera_polarization_evidence_emitted") is not True:
            raise ValueError("Stationary native audit v3/v4 must declare camera polarization evidence emission.")
    if raw_schema == RAW_SCHEMA_V4:
        if metadata["claims"].get("dynamic_metric_evidence_emitted") is not True:
            raise ValueError("Native audit v4 must declare dynamic metric evidence emission.")
        provider = metadata.get("metric_provider")
        if not isinstance(provider, Mapping):
            raise ValueError("Native audit v4 is missing metric_provider metadata.")
        if bool(metadata["parameters"].get("bbh_enabled", False)) == bool(provider.get("stationary", True)):
            raise ValueError("Native audit v4 BBH mode disagrees with metric-provider stationarity.")


def _validate_native_summary(capture: NpgsAuditCapture) -> None:
    summary = capture.metadata.get("summary")
    if not isinstance(summary, Mapping):
        raise ValueError("Native audit metadata is missing its summary object.")
    event_counts = _named_counts(capture.event_code, capture.metadata["event_codes"])
    expected = {
        "pixels": capture.event_code.size,
        "capture": event_counts.get("capture", 0),
        "escape": event_counts.get("escape", 0),
        "invalid": event_counts.get("invalid", 0),
        "nonfinite_records": 0,
    }
    for key, value in expected.items():
        if int(summary.get(key, -1)) != value:
            raise ValueError(
                f"Native sidecar summary {key!r}={summary.get(key)!r} does not match raw value {value}."
            )


def _validate_disk_transfer(
    metadata: Mapping[str, Any],
    *,
    disk_r: np.ndarray,
    disk_sin_phi: np.ndarray,
    disk_cos_phi: np.ndarray,
    disk_g: np.ndarray,
    disk_delta_t: np.ndarray,
    disk_order: np.ndarray,
    disk_validity: np.ndarray,
    disk_flags: np.ndarray,
) -> None:
    """Fail closed on physically malformed native disk-transfer records."""

    claims = metadata["claims"]
    required_claims = {
        "disk_phi_coordinate": "Boyer-Lindquist",
        "disk_delta_t_coordinate": "Boyer-Lindquist observer-minus-emitter time",
        "disk_redshift_definition": (
            "nu_observer_local / nu_emitter; observer-local launch frequency normalized to 1"
        ),
    }
    for key, expected in required_claims.items():
        if claims.get(key) != expected:
            raise ValueError(f"Native disk-transfer claim {key!r} is missing or inconsistent.")

    parameters = metadata["parameters"]
    r_in = float(parameters.get("disk_inner_radius_M", math.nan))
    r_out = float(parameters.get("disk_outer_radius_M", math.nan))
    if not (math.isfinite(r_in) and math.isfinite(r_out) and 0.0 < r_in < r_out):
        raise ValueError("Native disk radii must satisfy 0 < r_in < r_out in M units.")
    if np.any((disk_flags < 0) | (disk_flags > 7)):
        raise ValueError("Native disk flags must be a three-bit mask in [0, 7].")

    for order in range(DISK_ORDERS):
        valid = disk_validity[order]
        if not np.any(valid):
            continue
        if np.any(disk_order[order, valid] != order):
            raise ValueError(f"Valid disk order {order} records do not preserve true crossing order.")
        if np.any(disk_flags[order, valid] != 0):
            raise ValueError(f"Valid disk order {order} records must have zero flags.")
        if np.any((disk_r[order, valid] < r_in) | (disk_r[order, valid] > r_out)):
            raise ValueError(f"Valid disk order {order} radii fall outside the declared annulus.")
        phase_norm = (
            disk_sin_phi[order, valid].astype(np.float64) ** 2
            + disk_cos_phi[order, valid].astype(np.float64) ** 2
        )
        if np.max(np.abs(phase_norm - 1.0)) > 5.0e-4:
            raise ValueError(f"Valid disk order {order} phases are not unit normalized.")
        if np.any(disk_g[order, valid] <= 0.0):
            raise ValueError(f"Valid disk order {order} redshifts must be positive.")
        if np.any(disk_delta_t[order, valid] < 0.0):
            raise ValueError(f"Valid disk order {order} delays must be non-negative.")


def _source_revisions(npgs_root: Path | str | None) -> dict[str, str]:
    if npgs_root is None:
        return {"upstream_sha": "unknown", "fork_sha": "unknown", "audit_shader_sha256": "unknown"}
    root = Path(npgs_root).resolve()
    fork_sha = _git_output(root, "rev-parse", "HEAD")
    upstream_sha = _git_output(root, "rev-parse", "upstream/master")
    shader = root / "NPGS" / "Assets" / "Shaders" / "BlackHole_audit.frag.spv"
    if not shader.is_file():
        raise ValueError(f"Compiled audit shader was not found at {shader}.")
    shader_sha = hashlib.sha256(shader.read_bytes()).hexdigest()
    return {
        "upstream_sha": upstream_sha,
        "fork_sha": fork_sha,
        "audit_shader_sha256": shader_sha,
    }


def _git_output(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf8",
    )
    return result.stdout.strip()


def _positive_int(metadata: Mapping[str, Any], key: str) -> int:
    value = int(metadata.get(key, 0))
    if value <= 0:
        raise ValueError(f"Native audit {key} must be positive.")
    return value


def _integer_field(
    values: np.ndarray,
    name: str,
    dtype: np.dtype[Any] | type[np.generic],
    *,
    minimum: int | None = None,
) -> np.ndarray:
    rounded = np.rint(values)
    if not np.array_equal(values, rounded):
        raise ValueError(f"Raw audit field {name!r} contains non-integral values.")
    if minimum is not None and np.any(rounded < minimum):
        raise ValueError(f"Raw audit field {name!r} contains values below {minimum}.")
    return rounded.astype(dtype)


def _binary_field(values: np.ndarray, name: str) -> np.ndarray:
    integer = _integer_field(values, name, np.int8)
    if np.any((integer != 0) & (integer != 1)):
        raise ValueError(f"Raw audit field {name!r} must contain only 0 or 1.")
    return integer.astype(bool)


def _validate_codes(values: np.ndarray, mapping: Mapping[str, Any], label: str) -> None:
    allowed = {int(code) for code in mapping.values()}
    unknown = sorted(int(value) for value in set(np.unique(values)) - allowed)
    if unknown:
        raise ValueError(f"Raw audit contains unknown {label} codes: {unknown}.")


def _named_counts(values: np.ndarray, mapping: Mapping[str, Any]) -> dict[str, int]:
    return {name: int(np.count_nonzero(values == int(code))) for name, code in mapping.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--out-h5", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--npgs-root", type=Path, default=Path("runtime/NPGS"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = convert_native_audit(
        args.raw,
        metadata_path=args.metadata,
        out_h5=args.out_h5,
        out_json=args.out_json,
        npgs_root=args.npgs_root,
        command=" ".join(sys.argv),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
