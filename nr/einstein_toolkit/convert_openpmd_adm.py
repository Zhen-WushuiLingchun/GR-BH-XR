"""Convert two CarpetX openPMD BP5 slices into the audited ADM schema.

The converter is deliberately strict.  It accepts the primitive ADM fields
written by ``ADMBaseX`` and preserves disconnected CarpetX chunks as separate
AMR patches.  It refuses inconsistent patch geometry, missing components, or
non-positive lapse/metric samples.  Raw CarpetX arrays use ``(z,y,x)`` order;
the GR-BH-XR schema stores ``(time,x,y,z,...)``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

import numpy as np

from gr_bh_xr.nr_snapshot import ADMSnapshotLevel, NRADMSnapshot, write_nr_snapshot


SCHEMA = "gr-bh-xr.bbh.carpetx-openpmd-conversion.v1"
_MESH = re.compile(r"admbasex_(lapse|shift|metric|curv)_patch00_lev(\d+)$")
_COMPONENTS = {
    "lapse": ("admbasex_alp",),
    "shift": ("admbasex_betax", "admbasex_betay", "admbasex_betaz"),
    "metric": (
        "admbasex_gxx",
        "admbasex_gxy",
        "admbasex_gxz",
        "admbasex_gyy",
        "admbasex_gyz",
        "admbasex_gzz",
    ),
    "curv": (
        "admbasex_kxx",
        "admbasex_kxy",
        "admbasex_kxz",
        "admbasex_kyy",
        "admbasex_kyz",
        "admbasex_kzz",
    ),
}


def _sha256_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(entry for entry in path.rglob("*") if entry.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf8"))
        digest.update(b"\0")
        with item.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def _chunk_bbox(chunks: Iterable[Any]) -> tuple[np.ndarray, np.ndarray]:
    chunks = list(chunks)
    if not chunks:
        raise ValueError("openPMD record component has no available chunks.")
    offsets = np.asarray([chunk.offset for chunk in chunks], dtype=np.int64)
    extents = np.asarray([chunk.extent for chunk in chunks], dtype=np.int64)
    lower = np.min(offsets, axis=0)
    upper = np.max(offsets + extents, axis=0)
    coverage = np.zeros(tuple(int(v) for v in upper - lower), dtype=np.bool_)
    for offset, extent in zip(offsets, extents, strict=True):
        relative = offset - lower
        slices = tuple(
            slice(int(start), int(start + size))
            for start, size in zip(relative, extent, strict=True)
        )
        coverage[slices] = True
    if not np.all(coverage):
        raise ValueError("openPMD AMR chunk union contains holes inside its bounding box.")
    return lower, upper


def _axis_permutation(labels: Iterable[str]) -> tuple[int, int, int]:
    labels = tuple(str(label).lower() for label in labels)
    if sorted(labels) != ["x", "y", "z"]:
        raise ValueError(f"expected Cartesian x/y/z axis labels, got {labels!r}.")
    return tuple(labels.index(axis) for axis in ("x", "y", "z"))


def _read_component_patches(
    series: Any, component: Any
) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    boxes = sorted(
        (
            (
                np.asarray(chunk.offset, dtype=np.int64),
                np.asarray(chunk.offset, dtype=np.int64)
                + np.asarray(chunk.extent, dtype=np.int64),
            )
            for chunk in component.available_chunks()
        ),
        key=lambda box: tuple(int(value) for value in box[0]),
    )
    if not boxes:
        raise ValueError("openPMD record component has no available chunks.")
    requests = [
        component.load_chunk(lower.tolist(), (upper - lower).tolist())
        for lower, upper in boxes
    ]
    series.flush()
    return [
        (np.asarray(request, dtype=np.float64), lower, upper)
        for request, (lower, upper) in zip(requests, boxes, strict=True)
    ]


def _read_slice(path: Path) -> dict[str, Any]:
    try:
        import openpmd_api as io
    except ImportError as exc:  # pragma: no cover - dependency error is CLI-facing
        raise RuntimeError("openpmd-api is required to convert CarpetX BP5 output.") from exc

    series = io.Series(str(path), io.Access.read_only)
    try:
        iteration_ids = list(series.iterations)
        if len(iteration_ids) != 1:
            raise ValueError(f"expected one iteration in {path}, got {iteration_ids}.")
        iteration = series.iterations[iteration_ids[0]]
        level_ids = sorted(
            {
                int(match.group(2))
                for name in iteration.meshes
                if (match := _MESH.fullmatch(str(name))) is not None
            }
        )
        if not level_ids:
            raise ValueError(f"no ADMBaseX meshes found in {path}.")
        levels: dict[int, list[dict[str, Any]]] = {}
        for level_id in level_ids:
            fields: dict[str, list[list[np.ndarray]]] = {}
            reference: list[dict[str, Any]] | None = None
            for field, component_names in _COMPONENTS.items():
                mesh_name = f"admbasex_{field}_patch00_lev{level_id:02d}"
                if mesh_name not in iteration.meshes:
                    raise ValueError(f"missing mesh {mesh_name} in {path}.")
                mesh = iteration.meshes[mesh_name]
                permutation = _axis_permutation(mesh.axis_labels)
                source_spacing = np.asarray(mesh.grid_spacing, dtype=np.float64)
                source_offset = np.asarray(mesh.grid_global_offset, dtype=np.float64)
                component_arrays: list[list[np.ndarray]] = []
                bboxes: list[tuple[np.ndarray, np.ndarray]] | None = None
                for component_name in component_names:
                    if component_name not in mesh:
                        raise ValueError(f"missing component {mesh_name}/{component_name}.")
                    patches = _read_component_patches(series, mesh[component_name])
                    component_bboxes = [(lower, upper) for _, lower, upper in patches]
                    if bboxes is None:
                        bboxes = component_bboxes
                    elif len(component_bboxes) != len(bboxes) or any(
                        not (
                            np.array_equal(lower, expected_lower)
                            and np.array_equal(upper, expected_upper)
                        )
                        for (lower, upper), (expected_lower, expected_upper) in zip(
                            component_bboxes, bboxes, strict=True
                        )
                    ):
                        raise ValueError(f"component chunk boxes differ inside {mesh_name}.")
                    component_arrays.append(
                        [np.transpose(array, axes=permutation) for array, _, _ in patches]
                    )
                assert bboxes is not None
                descriptors = []
                for lower, upper in bboxes:
                    origin_source = source_offset + lower * source_spacing
                    descriptors.append(
                        {
                            "origin": origin_source[list(permutation)],
                            "spacing": source_spacing[list(permutation)],
                            "shape": tuple(
                                int(value)
                                for value in (upper - lower)[list(permutation)]
                            ),
                        }
                    )
                if reference is None:
                    reference = descriptors
                else:
                    if len(reference) != len(descriptors):
                        raise ValueError(
                            f"ADM field patch count differs on level {level_id}."
                        )
                    for patch_index, (expected, descriptor) in enumerate(
                        zip(reference, descriptors, strict=True)
                    ):
                        for key in ("origin", "spacing", "shape"):
                            if not np.allclose(
                                expected[key],
                                descriptor[key],
                                rtol=0.0,
                                atol=1.0e-12,
                            ):
                                raise ValueError(
                                    f"ADM field geometry differs on level {level_id}, "
                                    f"patch {patch_index}: {key}."
                                )
                fields[field] = component_arrays
            assert reference is not None
            level_patches: list[dict[str, Any]] = []
            for patch_index, descriptor in enumerate(reference):
                lapse = fields["lapse"][0][patch_index]
                shift = np.stack(
                    [component[patch_index] for component in fields["shift"]],
                    axis=-1,
                )
                gxx, gxy, gxz, gyy, gyz, gzz = (
                    component[patch_index] for component in fields["metric"]
                )
                kxx, kxy, kxz, kyy, kyz, kzz = (
                    component[patch_index] for component in fields["curv"]
                )
                gamma = np.empty(lapse.shape + (3, 3), dtype=np.float64)
                gamma[..., 0, 0], gamma[..., 0, 1], gamma[..., 0, 2] = gxx, gxy, gxz
                gamma[..., 1, 0], gamma[..., 1, 1], gamma[..., 1, 2] = gxy, gyy, gyz
                gamma[..., 2, 0], gamma[..., 2, 1], gamma[..., 2, 2] = gxz, gyz, gzz
                extrinsic = np.empty(lapse.shape + (3, 3), dtype=np.float64)
                extrinsic[..., 0, 0], extrinsic[..., 0, 1], extrinsic[..., 0, 2] = kxx, kxy, kxz
                extrinsic[..., 1, 0], extrinsic[..., 1, 1], extrinsic[..., 1, 2] = kxy, kyy, kyz
                extrinsic[..., 2, 0], extrinsic[..., 2, 1], extrinsic[..., 2, 2] = kxz, kyz, kzz
                eigen_min = float(np.min(np.linalg.eigvalsh(gamma)))
                if not np.all(np.isfinite(lapse)) or np.min(lapse) <= 0.0:
                    raise ValueError(
                        f"level {level_id} patch {patch_index} contains non-positive lapse samples."
                    )
                if eigen_min <= 0.0:
                    raise ValueError(
                        f"level {level_id} patch {patch_index} spatial metric is not "
                        f"positive definite; min eigenvalue={eigen_min}."
                    )
                level_patches.append(
                    {
                        **descriptor,
                        "source_level_id": level_id,
                        "source_patch_index": patch_index,
                        "lapse": lapse,
                        "shift": shift,
                        "gamma_cov": gamma,
                        "extrinsic_curvature": extrinsic,
                        "gamma_eigenvalue_min": eigen_min,
                    }
                )
            levels[level_id] = level_patches
        return {
            "time_M": float(iteration.time),
            "iteration": int(iteration_ids[0]),
            "levels": levels,
        }
    finally:
        series.close()


def _patch_geometry_matches(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(
        np.allclose(left[key], right[key], rtol=0.0, atol=1.0e-12)
        for key in ("origin", "spacing", "shape")
    )


def _select_parent_level_id(
    child: dict[str, Any],
    prior_patches: Iterable[tuple[int, int, dict[str, Any]]],
) -> int:
    """Return the nearest coarser output patch containing the child center."""

    child_shape = np.asarray(child["shape"], dtype=np.int64)
    child_upper = child["origin"] + child["spacing"] * (child_shape - 1)
    child_center = 0.5 * (child["origin"] + child_upper)
    candidates: list[tuple[int, float, int]] = []
    for source_level_id, output_level_id, patch in prior_patches:
        if np.any(patch["spacing"] <= child["spacing"]):
            continue
        patch_shape = np.asarray(patch["shape"], dtype=np.int64)
        patch_upper = patch["origin"] + patch["spacing"] * (patch_shape - 1)
        tolerance = 1.0e-12 * np.maximum(
            1.0, np.maximum(np.abs(patch["origin"]), np.abs(patch_upper))
        )
        if np.any(child_center < patch["origin"] - tolerance) or np.any(
            child_center > patch_upper + tolerance
        ):
            continue
        candidates.append(
            (source_level_id, float(np.prod(patch["spacing"])), output_level_id)
        )
    if not candidates:
        raise ValueError(
            "AMR patch has no containing coarser parent: "
            f"source level {child['source_level_id']} patch "
            f"{child['source_patch_index']}."
        )
    # Prefer the highest source level, then the finest containing patch.
    return max(candidates, key=lambda item: (item[0], -item[1]))[2]


def convert_openpmd_adm(
    inputs: Iterable[Path | str],
    output: Path | str,
    *,
    release_lock: Path | str,
    constraint_summary: Path | str,
    resolution_label: str,
) -> Path:
    paths = tuple(Path(path).resolve() for path in inputs)
    if len(paths) != 2 or paths[0] == paths[1]:
        raise ValueError("exactly two distinct BP5 time slices are required.")
    slices = tuple(_read_slice(path) for path in paths)
    if slices[1]["time_M"] <= slices[0]["time_M"]:
        raise ValueError("BP5 slice times must be strictly increasing.")
    if set(slices[0]["levels"]) != set(slices[1]["levels"]):
        raise ValueError("AMR level sets differ between the two time slices.")

    lock = json.loads(Path(release_lock).read_text(encoding="utf8"))
    constraints = json.loads(Path(constraint_summary).read_text(encoding="utf8"))
    levels: list[ADMSnapshotLevel] = []
    conversion_levels: list[dict[str, Any]] = []
    prior_patches: list[tuple[int, int, dict[str, Any]]] = []
    next_output_level_id = 0
    minimum_source_level = min(slices[0]["levels"])
    for source_level_id in sorted(slices[0]["levels"]):
        left_patches = slices[0]["levels"][source_level_id]
        right_patches = slices[1]["levels"][source_level_id]
        if len(left_patches) != len(right_patches):
            raise ValueError(
                f"AMR source level {source_level_id} patch count changed between snapshots."
            )
        for source_patch_index, (left, right) in enumerate(
            zip(left_patches, right_patches, strict=True)
        ):
            if not _patch_geometry_matches(left, right):
                raise ValueError(
                    f"AMR source level {source_level_id} patch {source_patch_index} "
                    "geometry changed between snapshots."
                )
            output_level_id = next_output_level_id
            next_output_level_id += 1
            parent_level_id = (
                None
                if source_level_id == minimum_source_level
                else _select_parent_level_id(left, prior_patches)
            )
            shape = np.asarray(left["shape"], dtype=np.int64)
            raw_upper = left["origin"] + left["spacing"] * (shape - 1)
            spatial_budget = float(np.max(left["spacing"]))
            levels.append(
                ADMSnapshotLevel(
                    level_id=output_level_id,
                    parent_level=parent_level_id,
                    origin=left["origin"],
                    spacing=left["spacing"],
                    valid_lower=left["origin"],
                    valid_upper=raw_upper,
                    lapse=np.stack((left["lapse"], right["lapse"])),
                    shift=np.stack((left["shift"], right["shift"])),
                    gamma_cov=np.stack((left["gamma_cov"], right["gamma_cov"])),
                    spatial_error_bound=np.full(2, spatial_budget),
                    extrinsic_curvature=np.stack(
                        (
                            left["extrinsic_curvature"],
                            right["extrinsic_curvature"],
                        )
                    ),
                )
            )
            conversion_levels.append(
                {
                    "level_id": output_level_id,
                    "source_level_id": source_level_id,
                    "source_patch_index": source_patch_index,
                    "parent_level_id": parent_level_id,
                    "origin_M": left["origin"].tolist(),
                    "spacing_M": left["spacing"].tolist(),
                    "shape": left["shape"],
                    "gamma_eigenvalue_min": min(
                        left["gamma_eigenvalue_min"],
                        right["gamma_eigenvalue_min"],
                    ),
                    "spatial_error_budget_M": spatial_budget,
                }
            )
            prior_patches.append((source_level_id, output_level_id, left))

    metadata = {
        "producer": {
            "name": "Einstein Toolkit",
            "version": lock["et_release"],
            "commit": lock["manifest_commit"],
            "component_commits": lock["component_commits"],
        },
        "formulation": "CottonmouthZ4c4m evolved ADMBaseX fields",
        "gauge": "moving-puncture gauge, eta_beta=1/M",
        "extrinsic_curvature_convention": "K_ij = -0.5 Lie_n(gamma_ij)",
        "coordinate_system": "CarpetX Cartesian (t,x,y,z), signature (-,+,+,+)",
        "units": {"system": "geometric", "G": 1, "c": 1, "M_total": 1},
        "constraint_history": constraints,
        "source_kind": "adm_volume",
        "conversion": {
            "schema": SCHEMA,
            "resolution_label": resolution_label,
            "axis_conversion": "CarpetX (z,y,x) to GR-BH-XR (x,y,z)",
            "extrinsic_curvature_stored": True,
            "spatial_error_note": (
                "Grid spacing is stored as a conservative interpolation budget, not as a measured convergence error."
            ),
            "temporal_error_note": (
                "Snapshot spacing is stored as a conservative interpolation budget; the two-resolution ray gate measures actual disagreement."
            ),
            "inputs": [
                {"path": str(path), "sha256_tree": _sha256_tree(path)} for path in paths
            ],
            "levels": conversion_levels,
        },
    }
    snapshot = NRADMSnapshot(
        times=np.asarray([item["time_M"] for item in slices]),
        levels=tuple(levels),
        temporal_error_bound=np.asarray([slices[1]["time_M"] - slices[0]["time_M"]]),
        metadata=metadata,
    )
    return write_nr_snapshot(output, snapshot)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--release-lock", type=Path, required=True)
    parser.add_argument("--constraint-summary", type=Path, required=True)
    parser.add_argument("--resolution-label", required=True)
    args = parser.parse_args()
    path = convert_openpmd_adm(
        args.input,
        args.out,
        release_lock=args.release_lock,
        constraint_summary=args.constraint_summary,
        resolution_label=args.resolution_label,
    )
    print(path)


if __name__ == "__main__":
    main()
