"""Extract auditable diagnostics from one Einstein Toolkit BBH pilot run."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable

import numpy as np


SCHEMA = "gr-bh-xr.bbh.nr-pilot-run.v1"
_AH_POS = re.compile(r"pos=\[([^,]+),([^,]+),([^\]]+)\]")
_AH_RADIUS = re.compile(
    r"r_avg=([^ ]+)\s+r_min=([^ ]+)\s+r_max=([^ ]+)"
)
_AH_EXPANSION = re.compile(r"Theta_maxabs=([^ ]+)")
_AH_EXPANSION_UNICODE = re.compile(r"\u0398_maxabs=([^ ]+)")
_AH_DIRECT_THETA = re.compile(
    r"Theta rms-norm\s+([^,]+),\s+infinity-norm\s+([^ ]+)"
)
_AH_DIRECT_RADIUS = re.compile(
    r"AH\s+(\d+)/(\d+):\s+r=([^ ]+)\s+at\s+\(([^,]+),([^,]+),([^\)]+)\)"
)
_AH_DIRECT_AREA = re.compile(
    r"AH\s+(\d+)/(\d+):\s+area=([^ ]+)\s+m_irreducible=([^ ]+)"
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _hash_tree(path: Path) -> dict[str, Any]:
    files = sorted(item for item in path.rglob("*") if item.is_file())
    digest = hashlib.sha256()
    total = 0
    entries: list[dict[str, Any]] = []
    for item in files:
        relative = item.relative_to(path).as_posix()
        item_hash = _sha256_file(item)
        size = item.stat().st_size
        digest.update(relative.encode("utf8"))
        digest.update(b"\0")
        digest.update(item_hash.encode("ascii"))
        digest.update(b"\0")
        total += size
        entries.append({"path": relative, "bytes": size, "sha256": item_hash})
    return {
        "path": str(path.resolve()),
        "file_count": len(files),
        "bytes": total,
        "sha256_tree": digest.hexdigest(),
        "files": entries,
    }


def _read_tsv(path: Path) -> tuple[list[str], np.ndarray]:
    lines = path.read_text(encoding="utf8", errors="replace").splitlines()
    header = next((line for line in lines if line.startswith("# 1:")), None)
    if header is None:
        raise ValueError(f"No numbered TSV header in {path}")
    columns = [part.split(":", 1)[1] for part in header[2:].split("\t")]
    rows = [
        [float(value) for value in line.split("\t")]
        for line in lines
        if line and not line.startswith("#")
    ]
    data = np.asarray(rows, dtype=np.float64)
    if data.ndim != 2 or data.shape[1] != len(columns):
        raise ValueError(f"Malformed TSV rows in {path}")
    return columns, data


def _vector_l2(columns: list[str], data: np.ndarray, token: str) -> np.ndarray:
    indices = [
        index
        for index, name in enumerate(columns)
        if token in name.lower() and name.lower().endswith(".l2norm")
    ]
    if not indices:
        raise ValueError(f"No {token} L2 columns")
    values = data[:, indices]
    return np.linalg.norm(values, axis=1)


def extract_constraints(data_dir: Path) -> dict[str, Any]:
    norms = data_dir / "norms"
    result: dict[str, Any] = {
        "schema": "gr-bh-xr.bbh.nr-constraints.v1",
        "source_dir": str(norms.resolve()),
        "histories": {},
    }
    cases = {
        "hamiltonian": ("cottonmouthz4c4m-hamcons.tsv", "hamcons"),
        "momentum": ("cottonmouthz4c4m-momcons.tsv", "momcons"),
        "z4": ("cottonmouthz4c4m-ztcons.tsv", "ztcons"),
    }
    final_values: dict[str, float] = {}
    for label, (filename, token) in cases.items():
        columns, data = _read_tsv(norms / filename)
        values = _vector_l2(columns, data, token)
        history = [
            {
                "iteration": int(row[0]),
                "time_M": float(row[1]),
                "l2": float(value),
            }
            for row, value in zip(data, values, strict=True)
        ]
        result["histories"][label] = history
        final_values[label] = float(values[-1])
    result["final_l2"] = final_values
    result["finite"] = all(
        math.isfinite(item["l2"])
        for history in result["histories"].values()
        for item in history
    )
    return result


def _collect_punctures(data_dir: Path) -> dict[str, Any]:
    samples: dict[float, dict[str, Any]] = {}
    for path in sorted(data_dir.glob("puncturetracker-pt_loc*.tsv")):
        columns, data = _read_tsv(path)
        lookup = {name: index for index, name in enumerate(columns)}
        for row in data:
            time = float(row[lookup["time"]])
            samples[time] = {
                "iteration": int(row[lookup["iteration"]]),
                "time_M": time,
                "puncture_0": [
                    float(row[lookup[f"pt_loc_{axis}[0]"]])
                    for axis in ("x", "y", "z")
                ],
                "puncture_1": [
                    float(row[lookup[f"pt_loc_{axis}[1]"]])
                    for axis in ("x", "y", "z")
                ],
            }
    return {
        "samples": [samples[key] for key in sorted(samples)],
        "finite": bool(samples)
        and all(
            np.all(np.isfinite(item[label]))
            for item in samples.values()
            for label in ("puncture_0", "puncture_1")
        ),
    }


def _parse_ahfinderx_solutions(stdout: Path, threshold: float) -> list[dict[str, Any]]:
    solutions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in stdout.read_text(encoding="utf8", errors="replace").splitlines():
        if "INFO (AHFinderX): iter: 1" in line:
            if current is not None:
                solutions.append(current)
            current = {"iterations": 1}
            continue
        if current is None:
            continue
        if "INFO (AHFinderX): iter:" in line:
            current["iterations"] = int(line.rsplit(":", 1)[1].strip())
        elif match := _AH_POS.search(line):
            current["center"] = [float(match.group(i)) for i in range(1, 4)]
        elif match := _AH_RADIUS.search(line):
            current["radius_avg_M"] = float(match.group(1))
            current["radius_min_M"] = float(match.group(2))
            current["radius_max_M"] = float(match.group(3))
        else:
            match = _AH_EXPANSION.search(line) or _AH_EXPANSION_UNICODE.search(line)
            if match:
                current["theta_max_abs"] = float(match.group(1))
    if current is not None:
        solutions.append(current)
    for index, solution in enumerate(solutions):
        solution["solution_index"] = index
        required = ("center", "radius_avg_M", "theta_max_abs")
        solution["accepted"] = all(key in solution for key in required) and (
            0.0 < float(solution.get("radius_avg_M", math.nan))
            and float(solution.get("theta_max_abs", math.inf)) <= threshold
        )
    return solutions


def _parse_ahfinderdirect_solutions(
    stdout: Path, threshold: float
) -> list[dict[str, Any]]:
    solutions: list[dict[str, Any]] = []
    latest_theta: tuple[float, float] | None = None
    pending_by_horizon: dict[int, dict[str, Any]] = {}
    for line in stdout.read_text(encoding="utf8", errors="replace").splitlines():
        if match := _AH_DIRECT_THETA.search(line):
            latest_theta = float(match.group(1)), float(match.group(2))
            continue
        if match := _AH_DIRECT_RADIUS.search(line):
            horizon = int(match.group(1))
            solution = {
                "horizon_number": horizon,
                "horizon_count": int(match.group(2)),
                "radius_avg_M": float(match.group(3)),
                "center": [float(match.group(i)) for i in range(4, 7)],
            }
            if latest_theta is not None:
                solution["theta_rms"] = latest_theta[0]
                solution["theta_max_abs"] = latest_theta[1]
            pending_by_horizon[horizon] = solution
            solutions.append(solution)
            continue
        if match := _AH_DIRECT_AREA.search(line):
            horizon = int(match.group(1))
            solution = pending_by_horizon.get(horizon)
            if solution is not None:
                solution["area_M2"] = float(match.group(3))
                solution["irreducible_mass_M"] = float(match.group(4))
    for index, solution in enumerate(solutions):
        solution["solution_index"] = index
        required = (
            "center",
            "radius_avg_M",
            "theta_max_abs",
            "area_M2",
            "irreducible_mass_M",
        )
        solution["accepted"] = all(key in solution for key in required) and (
            0.0 < float(solution.get("radius_avg_M", math.nan))
            and float(solution.get("area_M2", math.nan)) > 0.0
            and float(solution.get("theta_max_abs", math.inf)) <= threshold
        )
    return solutions


def extract_horizons(data_dir: Path, stdout: Path, threshold: float) -> dict[str, Any]:
    punctures = _collect_punctures(data_dir)
    text = stdout.read_text(encoding="utf8", errors="replace")
    direct = "INFO (AHFinderDirect)" in text
    solutions = (
        _parse_ahfinderdirect_solutions(stdout, threshold)
        if direct
        else _parse_ahfinderx_solutions(stdout, threshold)
    )
    accepted = [item for item in solutions if item["accepted"]]
    center_offsets: list[float] = []
    if accepted and punctures["samples"]:
        puncture_positions = [
            np.asarray(sample[label], dtype=np.float64)
            for sample in punctures["samples"]
            for label in ("puncture_0", "puncture_1")
        ]
        for solution in accepted:
            center_offsets.append(
                min(
                    float(
                        np.linalg.norm(
                            np.asarray(solution["center"], dtype=np.float64) - position
                        )
                    )
                    for position in puncture_positions
                )
            )
    accepted_horizons = sorted(
        {int(item["horizon_number"]) for item in accepted if "horizon_number" in item}
    )
    puncture_samples_present = bool(punctures["samples"])
    return {
        "schema": "gr-bh-xr.bbh.nr-apparent-horizon.v1",
        "finder": "SpacetimeX/AHFinderDirect" if direct else "SpacetimeX/AHFinderX",
        "finder_scope": (
            "both individual horizons are solved independently"
            if direct
            else "one +x individual horizon; the -x companion is constrained by "
            "equal-mass pi-rotation symmetry and both punctures are tracked"
        ),
        "max_expansion_threshold": threshold,
        "solution_count": len(solutions),
        "accepted_solution_count": len(accepted),
        "accepted_horizon_numbers": accepted_horizons,
        "solutions": solutions,
        "punctures": punctures,
        "center_to_puncture_max_M": max(center_offsets) if center_offsets else None,
        "finite": (
            len(accepted_horizons) >= 2
            and (not puncture_samples_present or punctures["finite"])
            if direct
            else punctures["finite"] and bool(accepted)
        ),
    }


def extract_psi4(data_dir: Path, extraction_radius: float) -> dict[str, Any]:
    modes: list[dict[str, Any]] = []
    for path in sorted(data_dir.glob("mp_NP_Psi4_l*_m*_r*.asc")):
        values = np.loadtxt(path, ndmin=2)
        match = re.search(r"_l(-?\d+)_m(-?\d+)_r([0-9.]+)\.asc$", path.name)
        if match is None:
            continue
        modes.append(
            {
                "l": int(match.group(1)),
                "m": int(match.group(2)),
                "radius_M": float(match.group(3)),
                "sample_count": int(values.shape[0]),
                "time_min_M": float(values[0, 0]),
                "time_max_M": float(values[-1, 0]),
                "max_abs": float(np.max(np.hypot(values[:, 1], values[:, 2]))),
                "path": str(path.resolve()),
                "sha256": _sha256_file(path),
            }
        )
    time_max = max((mode["time_max_M"] for mode in modes), default=math.nan)
    return {
        "schema": "gr-bh-xr.bbh.nr-psi4.v1",
        "extraction_radius_M": extraction_radius,
        "modes": modes,
        "finite": bool(modes)
        and all(math.isfinite(mode["max_abs"]) for mode in modes),
        "bounded_pilot_note": (
            f"The {time_max:g}M evolution is shorter than the light travel time "
            f"to r={extraction_radius:g}M; these modes prove producer plumbing, "
            "not a merger waveform."
        ),
    }


def extract_adm_index(data_dir: Path) -> dict[str, Any]:
    snapshots = [
        _hash_tree(path)
        for path in sorted(data_dir.glob("*.bp5"))
        if path.is_dir()
    ]
    return {
        "schema": "gr-bh-xr.bbh.nr-openpmd-index.v1",
        "backend": "openPMD ADIOS2 BP5",
        "snapshots": snapshots,
        "snapshot_count": len(snapshots),
        "finite_volume_fields": bool(snapshots),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf8")


def analyze_run(
    data_dir: Path | str,
    stdout: Path | str,
    output_dir: Path | str,
    *,
    label: str,
    resolution: float,
    grid_spacing_M: float,
    horizon_threshold: float = 1.0e-3,
    extraction_radius_M: float = 20.0,
) -> dict[str, Any]:
    data = Path(data_dir).resolve()
    log = Path(stdout).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "constraints": extract_constraints(data),
        "apparent_horizons": extract_horizons(data, log, horizon_threshold),
        "psi4": extract_psi4(data, extraction_radius_M),
        "adm_snapshot": extract_adm_index(data),
    }
    paths: dict[str, str] = {}
    for role, payload in artifacts.items():
        path = output / f"{label}_{role}.json"
        _write_json(path, payload)
        paths[role] = str(path)
    summary = {
        "schema": SCHEMA,
        "label": label,
        "resolution": float(resolution),
        "grid_spacing_M": float(grid_spacing_M),
        "data_dir": str(data),
        "cactus_stdout": str(log),
        "artifacts": paths,
        "producer_gate_passed": bool(
            artifacts["constraints"]["finite"]
            and artifacts["apparent_horizons"]["finite"]
            and artifacts["psi4"]["finite"]
            and artifacts["adm_snapshot"]["finite_volume_fields"]
        ),
    }
    summary_path = output / f"{label}_run_summary.json"
    _write_json(summary_path, summary)
    summary["summary_path"] = str(summary_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--stdout", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--resolution", type=float, required=True)
    parser.add_argument("--grid-spacing-M", type=float, required=True)
    parser.add_argument("--horizon-threshold", type=float, default=1.0e-3)
    args = parser.parse_args()
    result = analyze_run(
        args.data_dir,
        args.stdout,
        args.out_dir,
        label=args.label,
        resolution=args.resolution,
        grid_spacing_M=args.grid_spacing_M,
        horizon_threshold=args.horizon_threshold,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
