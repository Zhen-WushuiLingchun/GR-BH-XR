"""Generate a full-sky GPU transfer cubemap for Unity lookup."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np

from gr_bh_xr.gpu.codes import SCHEMA_EVENT_CODES
from gr_bh_xr.gpu.trace import GpuTraceConfig, event_to_rgba8, trace_unity_direction_points
from gr_bh_xr.sky import escape_direction_arrays
from gr_bh_xr.types import MetricParams, TraceConfig
from gr_bh_xr.xr.export_unity_textures import unity_basis_from_inclination


FULL_SKY_PACKAGE_SCHEMA = "gr-bh-xr.task5.full_sky_transfer_cubemap.v2"
UNITY_CUBE_FACES = ("PositiveX", "NegativeX", "PositiveY", "NegativeY", "PositiveZ", "NegativeZ")
DISK_TRANSFER_ORDER_COUNT = 2
DEFAULT_DISK_COVERAGE_SUBSAMPLES = 4


def generate_transfer_cubemap(
    *,
    params: MetricParams,
    inclination_deg: float,
    face_size: int,
    out_dir: Path | str,
    r_obs: float,
    step_size: float,
    steps: int,
    horizon_eps: float,
    chunk_size: int,
    disk_coverage_subsamples: int = DEFAULT_DISK_COVERAGE_SUBSAMPLES,
    command: str = "",
) -> dict[str, Any]:
    """Generate raw Unity cubemap bytes for all view directions."""

    if face_size < 2:
        raise ValueError("face_size must be at least 2.")
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive.")
    if disk_coverage_subsamples < 1:
        raise ValueError("disk_coverage_subsamples must be positive.")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    config = GpuTraceConfig(
        params=params,
        inclination_deg=inclination_deg,
        grid=2,
        alpha_max=1.0,
        beta_max=1.0,
        r_obs=r_obs,
        step_size=step_size,
        steps=steps,
        horizon_eps=horizon_eps,
        critical_refine_band=0.0,
        critical_refine_factor=1,
    )
    basis = unity_basis_from_inclination(inclination_deg)
    pixels_per_face = face_size * face_size
    total_pixels = pixels_per_face * len(UNITY_CUBE_FACES)
    event_cube = np.zeros((len(UNITY_CUBE_FACES), face_size, face_size, 4), dtype=np.uint8)
    dir_cube = np.zeros((len(UNITY_CUBE_FACES), face_size, face_size, 4), dtype=np.float32)
    disk_transfer_cube = np.zeros(
        (DISK_TRANSFER_ORDER_COUNT, len(UNITY_CUBE_FACES), face_size, face_size, 4),
        dtype=np.float16,
    )
    disk_redshift_cube = np.zeros(
        (DISK_TRANSFER_ORDER_COUNT, len(UNITY_CUBE_FACES), face_size, face_size, 4),
        dtype=np.float16,
    )

    backend: dict[str, Any] | None = None
    event_counts = {name: 0 for name in SCHEMA_EVENT_CODES}
    failure_counts: dict[str, int] = {}
    disk_valid_by_order = [0 for _ in range(DISK_TRANSFER_ORDER_COUNT)]
    disk_fractional_by_order = [0 for _ in range(DISK_TRANSFER_ORDER_COUNT)]
    disk_coverage_sum_by_order = [0.0 for _ in range(DISK_TRANSFER_ORDER_COUNT)]
    for face_index, face_name in enumerate(UNITY_CUBE_FACES):
        directions = _face_directions(face_name, face_size)
        face_event = np.zeros((pixels_per_face,), dtype=np.int16)
        face_failure = np.zeros((pixels_per_face,), dtype=np.int16)
        face_dir = np.zeros((pixels_per_face, 4), dtype=np.float32)
        face_disk = np.zeros((DISK_TRANSFER_ORDER_COUNT, pixels_per_face, 4), dtype=np.float32)
        for start in range(0, pixels_per_face, chunk_size):
            end = min(start + chunk_size, pixels_per_face)
            result = trace_unity_direction_points(config, directions[start:end])
            backend = result["backend"]
            event_code = result["event_code"].astype(np.int16)
            failure_code = result["failure_code"].astype(np.int16)
            escape = escape_direction_arrays(
                params=params,
                event_code=event_code,
                r=result["final_r"],
                theta=result["final_theta"],
                phi=result["final_phi"],
                p_t=result["final_p_t"],
                p_r=result["final_p_r"],
                p_theta=result["final_p_theta"],
                p_phi=result["final_p_phi"],
                escape_code=SCHEMA_EVENT_CODES["escape"],
            )
            dir_bh = np.stack(escape[2:], axis=-1)
            valid = (event_code == SCHEMA_EVENT_CODES["escape"]) & np.all(np.isfinite(dir_bh), axis=-1)
            dir_unity = _bh_to_unity(dir_bh, valid, basis)
            packed = np.zeros((end - start, 4), dtype=np.float32)
            packed[valid, :3] = dir_unity[valid]
            packed[valid, 3] = 1.0
            face_event[start:end] = event_code
            face_failure[start:end] = failure_code
            face_dir[start:end] = packed
            for order in range(DISK_TRANSFER_ORDER_COUNT):
                disk_r = result["disk_r_m"][:, order]
                disk_phi = result["disk_phi_m"][:, order]
                disk_g = result["disk_g_m"][:, order]
                disk_valid = (
                    np.isfinite(disk_r)
                    & np.isfinite(disk_phi)
                    & np.isfinite(disk_g)
                    & (disk_r > 0.0)
                    & (disk_g > 0.0)
                )
                disk_packed = np.zeros((end - start, 4), dtype=np.float32)
                disk_packed[disk_valid, 0] = disk_r[disk_valid]
                disk_packed[disk_valid, 1] = np.sin(disk_phi[disk_valid])
                disk_packed[disk_valid, 2] = np.cos(disk_phi[disk_valid])
                disk_packed[disk_valid, 3] = disk_g[disk_valid]
                face_disk[order, start:end] = disk_packed
            for name, code in SCHEMA_EVENT_CODES.items():
                event_counts[name] += int(np.count_nonzero(event_code == code))
            for code in np.unique(failure_code):
                failure_counts[str(int(code))] = failure_counts.get(str(int(code)), 0) + int(
                    np.count_nonzero(failure_code == code)
                )
        event_cube[face_index] = event_to_rgba8(
            face_event.reshape((face_size, face_size)),
            face_failure.reshape((face_size, face_size)),
        )
        dir_cube[face_index] = face_dir.reshape((face_size, face_size, 4))
        face_disk_transfer, face_disk_redshift, face_coverage = _coverage_premultiply_disk_face(
            config=config,
            face_name=face_name,
            face_size=face_size,
            face_disk=face_disk,
            disk_coverage_subsamples=disk_coverage_subsamples,
            chunk_size=chunk_size,
        )
        for order in range(DISK_TRANSFER_ORDER_COUNT):
            disk_transfer_cube[order, face_index] = face_disk_transfer[order].reshape((face_size, face_size, 4))
            disk_redshift_cube[order, face_index] = face_disk_redshift[order].reshape((face_size, face_size, 4))
            coverage = face_coverage[order]
            disk_valid_by_order[order] += int(np.count_nonzero(coverage > 0.0))
            disk_fractional_by_order[order] += int(np.count_nonzero((coverage > 0.0) & (coverage < 1.0)))
            disk_coverage_sum_by_order[order] += float(np.sum(coverage, dtype=np.float64))

    event_path = out_dir / "event_cube_rgba8.bytes"
    dir_path = out_dir / "escape_dir_unity_cube_rgba32f.bytes"
    disk_paths = [
        out_dir / f"disk_order{order}_transfer_cube_rgba16f.bytes"
        for order in range(DISK_TRANSFER_ORDER_COUNT)
    ]
    disk_redshift_paths = [
        out_dir / f"disk_order{order}_redshift_cube_rgba16f.bytes"
        for order in range(DISK_TRANSFER_ORDER_COUNT)
    ]
    metadata_path = out_dir / "full_sky_transfer_metadata.json"
    event_cube.tofile(event_path)
    dir_cube.astype("<f4", copy=False).tofile(dir_path)
    for order, disk_path in enumerate(disk_paths):
        disk_transfer_cube[order].astype("<f2", copy=False).tofile(disk_path)
    for order, disk_path in enumerate(disk_redshift_paths):
        disk_redshift_cube[order].astype("<f2", copy=False).tofile(disk_path)
    metadata = {
        "schema": FULL_SKY_PACKAGE_SCHEMA,
        "generationCommand": command,
        "faceSize": face_size,
        "faceOrder": list(UNITY_CUBE_FACES),
        "eventCubeRgba8": event_path.name,
        "escapeDirUnityCubeRgba32f": dir_path.name,
        "diskTransferCubesRgba16f": [path.name for path in disk_paths],
        "diskRedshiftCubesRgba16f": [path.name for path in disk_redshift_paths],
        "bytes": {
            "eventCubeRgba8": int(event_cube.nbytes),
            "escapeDirUnityCubeRgba32f": int(dir_cube.nbytes),
            "diskTransferCubesRgba16f": [
                int(disk_transfer_cube[order].nbytes) for order in range(DISK_TRANSFER_ORDER_COUNT)
            ],
            "diskRedshiftCubesRgba16f": [
                int(disk_redshift_cube[order].nbytes) for order in range(DISK_TRANSFER_ORDER_COUNT)
            ],
        },
        "metric": {"M": params.M, "a": params.a},
        "observer": {
            "r_obs": r_obs,
            "inclination_deg": inclination_deg,
            "theta_obs_rad": math.radians(inclination_deg),
            "tetrad": "finite-radius static observer; Unity +z is radially inward",
        },
        "integration": {
            "step_size": step_size,
            "steps": steps,
            "lambda_budget": step_size * steps,
            "horizon_eps": horizon_eps,
        },
        "backend": backend,
        "eventCounts": event_counts,
        "failureCountsByCode": failure_counts,
        "diskTransfer": {
            "orderCount": DISK_TRANSFER_ORDER_COUNT,
            "channels": "coverage-premultiplied r_m, sin(phi_m), cos(phi_m), coverage",
            "redshiftChannels": "coverage-premultiplied g_m in red channel; other channels reserved",
            "format": "raw little-endian RGBAHalf cubemap per order",
            "validity": (
                "alpha is disk-hit coverage in [0,1]. Data channels are premultiplied by coverage; "
                "shader consumers divide by interpolated coverage and use coverage as opacity."
            ),
            "coverageSubsamplesPerAxis": disk_coverage_subsamples,
            "r_in": float(config.attrs()["disk_r_in"]),
            "r_out": float(config.disk_r_out),
            "imageOrder": "order index is the true equatorial crossing order m, not the annulus-hit count",
            "validByOrder": disk_valid_by_order,
            "fractionalCoverageByOrder": disk_fractional_by_order,
            "coverageSumByOrder": disk_coverage_sum_by_order,
        },
        "totalPixels": total_pixels,
        "validEscapePixels": int(np.count_nonzero(dir_cube[..., 3] >= 0.5)),
        "boundaryNote": (
            "Full-sky cubemap has no alpha/beta window fallback. Every cubemap texel is traced "
            "from the same finite observer tetrad, so there is no square hard boundary."
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf8")
    return metadata


def _face_directions(face_name: str, face_size: int) -> np.ndarray:
    coords = (np.arange(face_size, dtype=np.float32) + 0.5) / float(face_size)
    u = 2.0 * coords - 1.0
    v = 2.0 * coords - 1.0
    uu, vv = np.meshgrid(u, v)
    return _face_directions_from_uv(face_name, uu, vv).reshape((-1, 3)).astype(np.float32)


def _face_directions_from_uv(face_name: str, uu: np.ndarray, vv: np.ndarray) -> np.ndarray:
    if face_name == "PositiveX":
        dirs = np.stack([np.ones_like(uu), -vv, -uu], axis=-1)
    elif face_name == "NegativeX":
        dirs = np.stack([-np.ones_like(uu), -vv, uu], axis=-1)
    elif face_name == "PositiveY":
        dirs = np.stack([uu, np.ones_like(uu), vv], axis=-1)
    elif face_name == "NegativeY":
        dirs = np.stack([uu, -np.ones_like(uu), -vv], axis=-1)
    elif face_name == "PositiveZ":
        dirs = np.stack([uu, -vv, np.ones_like(uu)], axis=-1)
    elif face_name == "NegativeZ":
        dirs = np.stack([-uu, -vv, -np.ones_like(uu)], axis=-1)
    else:
        raise ValueError(f"Unknown Unity cubemap face: {face_name}")
    norm = np.linalg.norm(dirs, axis=-1, keepdims=True)
    return dirs / norm


def _coverage_premultiply_disk_face(
    *,
    config: GpuTraceConfig,
    face_name: str,
    face_size: int,
    face_disk: np.ndarray,
    disk_coverage_subsamples: int,
    chunk_size: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    transfer, redshift, coverage = _premultiply_disk_samples(face_disk)
    if disk_coverage_subsamples <= 1:
        return transfer, redshift, coverage

    edge_mask = np.zeros((face_size, face_size), dtype=bool)
    for order in range(DISK_TRANSFER_ORDER_COUNT):
        valid = coverage[order].reshape((face_size, face_size)) > 0.0
        edge_mask |= _validity_boundary_mask(valid)
    edge_indices = np.flatnonzero(edge_mask.ravel())
    if edge_indices.size == 0:
        return transfer, redshift, coverage

    directions = _subpixel_face_directions(
        face_name=face_name,
        face_size=face_size,
        flat_indices=edge_indices,
        subsamples=disk_coverage_subsamples,
    )
    sub_count = disk_coverage_subsamples * disk_coverage_subsamples
    sub_disk = np.zeros((DISK_TRANSFER_ORDER_COUNT, directions.shape[0], 4), dtype=np.float32)
    for start in range(0, directions.shape[0], chunk_size):
        end = min(start + chunk_size, directions.shape[0])
        result = trace_unity_direction_points(config, directions[start:end])
        for order in range(DISK_TRANSFER_ORDER_COUNT):
            disk_r = result["disk_r_m"][:, order]
            disk_phi = result["disk_phi_m"][:, order]
            disk_g = result["disk_g_m"][:, order]
            valid = (
                np.isfinite(disk_r)
                & np.isfinite(disk_phi)
                & np.isfinite(disk_g)
                & (disk_r > 0.0)
                & (disk_g > 0.0)
            )
            packed = np.zeros((end - start, 4), dtype=np.float32)
            packed[valid, 0] = disk_r[valid]
            packed[valid, 1] = np.sin(disk_phi[valid])
            packed[valid, 2] = np.cos(disk_phi[valid])
            packed[valid, 3] = disk_g[valid]
            sub_disk[order, start:end] = packed

    for order in range(DISK_TRANSFER_ORDER_COUNT):
        for edge_pos, flat_index in enumerate(edge_indices):
            sample_slice = slice(edge_pos * sub_count, (edge_pos + 1) * sub_count)
            samples = sub_disk[order, sample_slice]
            valid = (samples[:, 0] > 0.0) & (samples[:, 3] > 0.0)
            cov = float(np.count_nonzero(valid)) / float(sub_count)
            coverage[order, flat_index] = cov
            transfer[order, flat_index] = 0.0
            redshift[order, flat_index] = 0.0
            if cov <= 0.0:
                continue
            # Store sum(valid values) / total samples, not average over valid samples.
            # The shader divides by interpolated coverage before using r, phi, and g.
            transfer[order, flat_index, 0] = float(np.sum(samples[valid, 0], dtype=np.float64)) / float(sub_count)
            transfer[order, flat_index, 1] = float(np.sum(samples[valid, 1], dtype=np.float64)) / float(sub_count)
            transfer[order, flat_index, 2] = float(np.sum(samples[valid, 2], dtype=np.float64)) / float(sub_count)
            transfer[order, flat_index, 3] = cov
            redshift[order, flat_index, 0] = float(np.sum(samples[valid, 3], dtype=np.float64)) / float(sub_count)
    return transfer, redshift, coverage


def _premultiply_disk_samples(face_disk: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    transfer = np.zeros_like(face_disk, dtype=np.float32)
    redshift = np.zeros_like(face_disk, dtype=np.float32)
    coverage = np.zeros(face_disk.shape[:2], dtype=np.float32)
    valid = (face_disk[..., 0] > 0.0) & (face_disk[..., 3] > 0.0) & np.all(np.isfinite(face_disk), axis=-1)
    coverage[valid] = 1.0
    transfer[..., 0] = np.where(valid, face_disk[..., 0], 0.0)
    transfer[..., 1] = np.where(valid, face_disk[..., 1], 0.0)
    transfer[..., 2] = np.where(valid, face_disk[..., 2], 0.0)
    transfer[..., 3] = coverage
    redshift[..., 0] = np.where(valid, face_disk[..., 3], 0.0)
    return transfer, redshift, coverage


def _validity_boundary_mask(valid: np.ndarray) -> np.ndarray:
    boundary = np.zeros(valid.shape, dtype=bool)
    vertical = valid[1:, :] != valid[:-1, :]
    horizontal = valid[:, 1:] != valid[:, :-1]
    boundary[1:, :] |= vertical
    boundary[:-1, :] |= vertical
    boundary[:, 1:] |= horizontal
    boundary[:, :-1] |= horizontal
    return boundary


def _subpixel_face_directions(
    *,
    face_name: str,
    face_size: int,
    flat_indices: np.ndarray,
    subsamples: int,
) -> np.ndarray:
    rows = (flat_indices // face_size).astype(np.float32)
    cols = (flat_indices % face_size).astype(np.float32)
    offsets = (np.arange(subsamples, dtype=np.float32) + 0.5) / float(subsamples)
    dirs: list[np.ndarray] = []
    for oy in offsets:
        for ox in offsets:
            u = 2.0 * ((cols + ox) / float(face_size)) - 1.0
            v = 2.0 * ((rows + oy) / float(face_size)) - 1.0
            dirs.append(_face_directions_from_uv(face_name, u, v).astype(np.float32))
    return np.stack(dirs, axis=1).reshape((-1, 3))


def _bh_to_unity(dir_bh: np.ndarray, valid: np.ndarray, basis: Any) -> np.ndarray:
    dir_unity = np.zeros(dir_bh.shape, dtype=np.float32)
    if not np.any(valid):
        return dir_unity
    vectors = dir_bh[valid].astype(np.float64)
    mapped = np.stack(
        [
            vectors @ basis.right_bh,
            vectors @ basis.up_bh,
            vectors @ basis.forward_bh,
        ],
        axis=-1,
    )
    norm = np.linalg.norm(mapped, axis=-1)
    good = np.isfinite(norm) & (norm > 0.0)
    local = np.flatnonzero(valid)
    if np.any(good):
        dir_unity.reshape((-1, 3))[local[good]] = (
            mapped[good] / norm[good, np.newaxis]
        ).astype(np.float32)
    return dir_unity


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True)
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, required=True)
    parser.add_argument("--face-size", type=int, default=256)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--step-size", type=float, default=GpuTraceConfig.step_size)
    parser.add_argument("--steps", type=int, default=GpuTraceConfig.steps)
    parser.add_argument("--horizon-eps", type=float, default=TraceConfig.horizon_eps)
    parser.add_argument("--chunk-size", type=int, default=262144)
    parser.add_argument("--disk-coverage-subsamples", type=int, default=DEFAULT_DISK_COVERAGE_SUBSAMPLES)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = generate_transfer_cubemap(
        params=MetricParams(M=args.mass, a=args.spin * args.mass),
        inclination_deg=args.inclination_deg,
        face_size=args.face_size,
        out_dir=args.out_dir,
        r_obs=args.r_obs,
        step_size=args.step_size,
        steps=args.steps,
        horizon_eps=args.horizon_eps,
        chunk_size=args.chunk_size,
        disk_coverage_subsamples=args.disk_coverage_subsamples,
        command=" ".join(sys.argv),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
