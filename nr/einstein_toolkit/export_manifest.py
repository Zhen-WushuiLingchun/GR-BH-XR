"""Build and validate a fail-closed Einstein Toolkit BBH pilot manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

import h5py


SCHEMA = "gr-bh-xr.bbh.nr-pilot-manifest.v1"
REQUIRED_ARTIFACT_ROLES = (
    "cactus_stdout",
    "adm_snapshot",
    "constraints",
    "apparent_horizons",
    "psi4",
    "ray_summary",
)
REQUIRED_RELEASE_KEYS = (
    "et_release",
    "manifest_commit",
    "getcomponents_sha256",
    "thornlist_sha256",
    "build_thornlist_sha256",
    "build_optionlist_sha256",
    "component_commits",
    "local_patches",
)
PINNED_RELEASE_FIELDS = REQUIRED_RELEASE_KEYS
PREFLIGHT_TEST = "linear_wave_z4c"


class PilotManifestError(ValueError):
    """Structured input/provenance failure for an NR pilot manifest."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PilotManifestError("invalid_structure", f"{name} must be an object.")
    return value


def _load_json_artifact(path: Path, role: str) -> Mapping[str, Any]:
    try:
        return _require_mapping(json.loads(path.read_text(encoding="utf8")), role)
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotManifestError(
            "invalid_evidence_artifact", f"{role} is not valid JSON: {path}: {exc}"
        ) from exc


def _inspect_adm_snapshot(path: Path) -> dict[str, Any]:
    try:
        with h5py.File(path, "r") as handle:
            schema = str(handle.attrs.get("schema", ""))
            times = list(map(float, handle["times"])) if "times" in handle else []
            levels = len(handle["levels"]) if "levels" in handle else 0
            extrinsic_curvature_levels = (
                sum(
                    "extrinsic_curvature" in handle[f"levels/{name}"]
                    for name in handle["levels"]
                )
                if "levels" in handle
                else 0
            )
    except OSError as exc:
        raise PilotManifestError(
            "invalid_adm_snapshot", f"Cannot open ADM snapshot {path}: {exc}"
        ) from exc
    compatible = (
        schema == "gr-bh-xr.bbh.adm-snapshot.v1"
        and len(times) >= 2
        and levels >= 1
        and extrinsic_curvature_levels == levels
    )
    return {
        "schema": schema,
        "times_M": times,
        "amr_level_count": levels,
        "extrinsic_curvature_level_count": extrinsic_curvature_levels,
        "compatible": compatible,
    }


def _validate_producer_preflight(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf8", errors="replace")
    compared_match = re.search(
        r"Success:\s+(\d+) files compared,\s+(\d+) differ in the last digits",
        text,
    )
    failed_match = re.search(r"Number failed\s*->\s*(\d+)", text)
    test_passed = bool(
        re.search(rf"^\s*{re.escape(PREFLIGHT_TEST)}\s+\(from\s+", text, re.MULTILINE)
    )
    files_compared = int(compared_match.group(1)) if compared_match else 0
    last_digit_differences = int(compared_match.group(2)) if compared_match else -1
    failures = int(failed_match.group(1)) if failed_match else -1
    accepted = bool(
        test_passed
        and files_compared > 0
        and 0 <= last_digit_differences <= files_compared
        and failures == 0
    )
    return {
        "test": PREFLIGHT_TEST,
        "files_compared": files_compared,
        "last_digit_differences": last_digit_differences,
        "failures": failures,
        "accepted": accepted,
    }


def _validate_run_evidence(artifacts: Mapping[str, Path]) -> dict[str, Any]:
    constraints = _load_json_artifact(artifacts["constraints"], "constraints")
    horizons = _load_json_artifact(artifacts["apparent_horizons"], "apparent_horizons")
    psi4 = _load_json_artifact(artifacts["psi4"], "psi4")
    rays = _load_json_artifact(artifacts["ray_summary"], "ray_summary")
    adm = _inspect_adm_snapshot(artifacts["adm_snapshot"])
    final_l2 = _require_mapping(constraints.get("final_l2"), "constraints.final_l2")
    finite_constraints = bool(constraints.get("finite")) and all(
        math.isfinite(float(final_l2.get(name, math.nan)))
        for name in ("hamiltonian", "momentum", "z4")
    )
    horizon_numbers = sorted(
        int(value) for value in horizons.get("accepted_horizon_numbers", [])
    )
    horizon_gate = bool(horizons.get("finite")) and horizon_numbers == [1, 2]
    psi4_gate = bool(psi4.get("finite")) and bool(psi4.get("modes"))
    ray_counts = _require_mapping(rays.get("counts"), "ray_summary.counts")
    ray_errors = _require_mapping(
        rays.get("escape_direction_error_rad"),
        "ray_summary.escape_direction_error_rad",
    )
    ray_event_agreement = float(rays.get("event_agreement", math.nan))
    ray_median_error = float(ray_errors.get("median", math.nan))
    ray_gate = bool(rays.get("accepted"))
    ray_gate &= rays.get("claim") == "frozen_slice_two_resolution_nr_optical_convergence"
    ray_gate &= rays.get("full_dynamic_light_cone_claim") is False
    ray_gate &= int(ray_counts.get("total", 0)) > 0
    ray_gate &= int(ray_counts.get("resolved_pairs", 0)) > 0
    ray_gate &= int(ray_counts.get("invalid_or_budget_pairs", -1)) == 0
    ray_gate &= int(ray_counts.get("escape_direction_pairs", 0)) > 0
    ray_gate &= math.isfinite(ray_event_agreement) and ray_event_agreement >= 0.98
    ray_gate &= math.isfinite(ray_median_error) and ray_median_error < 5.0e-3
    stdout_text = artifacts["cactus_stdout"].read_text(
        encoding="utf8", errors="replace"
    )
    clean_exit = "Done." in stdout_text and not re.search(
        r"Cactus exiting with return code [1-9]|Segmentation fault|nan in shift",
        stdout_text,
        flags=re.IGNORECASE,
    )
    gates = {
        "clean_producer_exit": clean_exit,
        "finite_constraint_history": finite_constraints,
        "two_individual_apparent_horizons": horizon_gate,
        "psi4_plumbing": psi4_gate,
        "compatible_adm_volume": bool(adm["compatible"]),
        "fixed_camera_ray_gate": ray_gate,
    }
    return {
        "gates": gates,
        "passed": all(gates.values()),
        "constraint_final_l2": {name: float(final_l2[name]) for name in final_l2},
        "apparent_horizon_numbers": horizon_numbers,
        "adm": adm,
        "ray": {
            "claim": rays.get("claim"),
            "event_agreement": ray_event_agreement,
            "escape_direction_error_rad": dict(ray_errors),
        },
    }


def build_pilot_manifest(spec_path: Path | str) -> dict[str, Any]:
    """Resolve a two-resolution pilot spec and hash every evidence artifact."""

    source = Path(spec_path).resolve()
    spec = _require_mapping(json.loads(source.read_text(encoding="utf8")), "spec")
    release = _require_mapping(spec.get("release"), "release")
    missing_release = [key for key in REQUIRED_RELEASE_KEYS if not release.get(key)]
    if missing_release:
        raise PilotManifestError(
            "missing_release_provenance",
            "Release provenance is missing: " + ", ".join(missing_release),
        )
    components = _require_mapping(release["component_commits"], "component_commits")
    for required in ("Cactus", "CarpetX", "Cottonmouth", "SpacetimeX"):
        commit = str(components.get(required, ""))
        if len(commit) != 40:
            raise PilotManifestError(
                "missing_component_revision",
                f"component_commits.{required} must be a full 40-character Git SHA.",
            )
    patches = _require_mapping(release["local_patches"], "local_patches")
    if not patches or any(
        len(str(digest)) != 64 for digest in patches.values()
    ):
        raise PilotManifestError(
            "missing_patch_revision",
            "Every local ET patch must have a full SHA-256 digest.",
        )
    pinned = _require_mapping(
        json.loads(
            Path(__file__).with_name("release_lock.json").read_text(encoding="utf8")
        ),
        "release_lock",
    )
    mismatched_release_fields = [
        key for key in PINNED_RELEASE_FIELDS if release.get(key) != pinned.get(key)
    ]
    if mismatched_release_fields:
        raise PilotManifestError(
            "release_provenance_mismatch",
            "Pilot release differs from the repository lock: "
            + ", ".join(mismatched_release_fields),
        )

    preflight_path = (
        source.parent / str(spec.get("producer_preflight", ""))
    ).resolve()
    if not preflight_path.is_file():
        raise PilotManifestError(
            "missing_producer_preflight",
            f"Producer linear-wave preflight log does not exist: {preflight_path}",
        )
    preflight_validation = _validate_producer_preflight(preflight_path)

    raw_runs = spec.get("runs")
    if not isinstance(raw_runs, list) or len(raw_runs) != 2:
        raise PilotManifestError(
            "missing_resolution_pair", "Exactly two NR pilot runs are required."
        )
    resolved_runs: list[dict[str, Any]] = []
    resolutions: list[float] = []
    for index, raw_run in enumerate(raw_runs):
        run = _require_mapping(raw_run, f"runs[{index}]")
        resolution = float(run.get("resolution", 0.0))
        if resolution <= 0.0:
            raise PilotManifestError(
                "invalid_resolution", f"runs[{index}].resolution must be positive."
            )
        resolutions.append(resolution)
        artifacts = _require_mapping(run.get("artifacts"), f"runs[{index}].artifacts")
        missing = [role for role in REQUIRED_ARTIFACT_ROLES if role not in artifacts]
        if missing:
            raise PilotManifestError(
                "missing_evidence_artifact",
                f"runs[{index}] lacks required artifact roles: {', '.join(missing)}.",
            )
        resolved_artifacts: dict[str, dict[str, Any]] = {}
        artifact_paths: dict[str, Path] = {}
        for role in REQUIRED_ARTIFACT_ROLES:
            path = (source.parent / str(artifacts[role])).resolve()
            if not path.is_file():
                raise PilotManifestError(
                    "missing_evidence_file", f"{role} does not exist: {path}"
                )
            resolved_artifacts[role] = {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            artifact_paths[role] = path
        parfile = (source.parent / str(run.get("parfile", ""))).resolve()
        if not parfile.is_file():
            raise PilotManifestError(
                "missing_parameter_file", f"Parameter file does not exist: {parfile}"
            )
        executable_sha256 = str(run.get("producer_executable_sha256", ""))
        if len(executable_sha256) != 64 or not re.fullmatch(
            r"[0-9a-f]{64}", executable_sha256
        ):
            raise PilotManifestError(
                "missing_producer_executable_revision",
                f"runs[{index}].producer_executable_sha256 must be lowercase SHA-256.",
            )
        validation = _validate_run_evidence(artifact_paths)
        resolved_runs.append(
            {
                "label": str(run.get("label", f"resolution-{index}")),
                "resolution": resolution,
                "grid_spacing_M": float(run.get("grid_spacing_M", 0.0)),
                "producer_command": str(run.get("producer_command", "")),
                "producer_executable_sha256": executable_sha256,
                "parfile": {
                    "path": str(parfile),
                    "sha256": _sha256(parfile),
                },
                "artifacts": resolved_artifacts,
                "validation": validation,
            }
        )
    if resolutions[0] == resolutions[1]:
        raise PilotManifestError(
            "duplicate_resolution", "The two pilot resolutions must be distinct."
        )
    normalized_parfiles = []
    for run in resolved_runs:
        text = Path(run["parfile"]["path"]).read_text(encoding="utf8")
        normalized_parfiles.append(re.sub(r"^\$rho\s*=\s*[12]\s*$", "$rho = RESOLUTION", text, flags=re.MULTILINE))
    parameter_pair_matches = normalized_parfiles[0] == normalized_parfiles[1]
    low, high = sorted(resolved_runs, key=lambda item: item["resolution"])
    resolution_ordered = (
        float(high["grid_spacing_M"]) > 0.0
        and float(low["grid_spacing_M"]) > float(high["grid_spacing_M"])
    )
    constraint_ratios = {
        name: float(high["validation"]["constraint_final_l2"][name])
        / max(float(low["validation"]["constraint_final_l2"][name]), 1.0e-300)
        for name in ("hamiltonian", "momentum", "z4")
    }
    validation = {
        "producer_preflight_passed": preflight_validation["accepted"],
        "runs_passed": all(run["validation"]["passed"] for run in resolved_runs),
        "parameter_pair_differs_only_by_rho": parameter_pair_matches,
        "resolution_ordered": resolution_ordered,
        "constraint_final_l2_high_over_low": constraint_ratios,
        "constraint_convergence_note": (
            "Global puncture-unmasked L2 ratios are diagnostic only; the optical convergence gate is the accepted claim."
        ),
    }
    validation["accepted"] = bool(
        validation["producer_preflight_passed"]
        and validation["runs_passed"]
        and parameter_pair_matches
        and resolution_ordered
    )
    return {
        "schema": SCHEMA,
        "claim": "bounded_two_resolution_nr_pipeline_pilot",
        "full_nr_merger_claim": False,
        "release": dict(release),
        "producer_preflight": {
            "path": str(preflight_path),
            "bytes": preflight_path.stat().st_size,
            "sha256": _sha256(preflight_path),
            "validation": preflight_validation,
        },
        "runs": resolved_runs,
        "required_artifact_roles": list(REQUIRED_ARTIFACT_ROLES),
        "claims": {
            "bounded_two_resolution_nr_pipeline_pilot": validation["accepted"],
            "full_nr_merger": False,
            "event_horizon": False,
            "converged_waveform": False,
        },
        "validation": validation,
        "accepted": validation["accepted"],
    }


def write_pilot_manifest(spec_path: Path | str, output_path: Path | str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_pilot_manifest(spec_path)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        path = write_pilot_manifest(args.spec, args.out)
    except PilotManifestError as exc:
        print(json.dumps({"accepted": False, "reason_code": exc.reason_code, "message": exc.message}, indent=2))
        raise SystemExit(2) from exc
    print(path)


if __name__ == "__main__":
    main()
