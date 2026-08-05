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


def static_observer_sky_blueshift(params: MetricParams, r_obs: float, theta_obs: float) -> float:
    """Frequency ratio observed/emitted for sky photons seen by a static observer.

    For `u = d/dt / sqrt(-g_tt)` and a photon with conserved `E_inf = -p_t`, the
    observed frequency is `E_inf / sqrt(-g_tt)`: direction independent, and
    greater than one (gravitational blueshift of the background sky).
    """

    sigma = r_obs * r_obs + params.a * params.a * math.cos(theta_obs) ** 2
    g_tt = -(1.0 - 2.0 * params.M * r_obs / sigma)
    if g_tt >= 0.0:
        raise ValueError("Static observer undefined at or inside the ergosphere.")
    return 1.0 / math.sqrt(-g_tt)


FULL_SKY_PACKAGE_SCHEMA = "gr-bh-xr.task5.full_sky_transfer_cubemap.v3"
UNITY_CUBE_FACES = ("PositiveX", "NegativeX", "PositiveY", "NegativeY", "PositiveZ", "NegativeZ")
DISK_TRANSFER_ORDER_COUNT = 2
DEFAULT_DISK_COVERAGE_SUBSAMPLES = 4
# Rays whose Boyer-Lindquist integration approached the polar axis closer than
# this (radians, in min(theta, pi - theta)) are recorded as an audit count.
# They are NOT repaired here: the first-principles fix is a Kerr-Schild retrace,
# which needs the KS tracer's equatorial disk-crossing outputs and therefore
# lands with the Kerr-Schild work rather than in this Boyer-Lindquist stage.
DEFAULT_POLAR_BAND_THRESHOLD = 0.01


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
    r_escape_min: float = 0.0,
    polar_band_threshold: float = DEFAULT_POLAR_BAND_THRESHOLD,
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
        r_escape_min=r_escape_min,
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
    escape_edge_texels = 0
    retraced_texels = 0
    inpainted_texels = 0
    polar_band_texels = 0
    solid_angle_total = 0.0
    solid_angle_capture = 0.0
    for face_index, face_name in enumerate(UNITY_CUBE_FACES):
        directions = _face_directions(face_name, face_size)
        # Cube texels do not subtend equal solid angle. For a normalized face
        # direction the largest-magnitude component is the face-axis cosine,
        # and the texel solid angle scales as its cube.
        face_weight = np.max(np.abs(directions), axis=1).astype(np.float64) ** 3
        face_event = np.zeros((pixels_per_face,), dtype=np.int16)
        face_failure = np.zeros((pixels_per_face,), dtype=np.int16)
        face_dir = np.zeros((pixels_per_face, 4), dtype=np.float32)
        face_disk = np.zeros((DISK_TRANSFER_ORDER_COUNT, pixels_per_face, 4), dtype=np.float32)
        face_min_pole = np.full((pixels_per_face,), np.pi, dtype=np.float32)
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
            face_min_pole[start:end] = result["min_pole"]
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
        polar_band_texels += int(np.count_nonzero(face_min_pole < polar_band_threshold))
        # Solid-angle-weighted shadow measure, taken from the raw pre-repair
        # classification so image repairs cannot move a physics gate.
        solid_angle_total += float(np.sum(face_weight))
        solid_angle_capture += float(
            np.sum(face_weight[face_event == SCHEMA_EVENT_CODES["capture"]])
        )

        face_dir, face_edge_count = _coverage_premultiply_escape_face(
            config=config,
            face_name=face_name,
            face_size=face_size,
            face_dir=face_dir,
            basis=basis,
            subsamples=disk_coverage_subsamples,
            chunk_size=chunk_size,
        )
        escape_edge_texels += face_edge_count

        face_disk_transfer, face_disk_redshift, face_coverage = _coverage_premultiply_disk_face(
            config=config,
            face_name=face_name,
            face_size=face_size,
            face_disk=face_disk,
            disk_coverage_subsamples=disk_coverage_subsamples,
            chunk_size=chunk_size,
        )

        retraced_texels += _retrace_invalid_face(
            config=config,
            face_name=face_name,
            face_size=face_size,
            face_event=face_event,
            face_failure=face_failure,
            face_dir=face_dir,
            face_disk_transfer=face_disk_transfer,
            face_disk_redshift=face_disk_redshift,
            basis=basis,
            subsamples=disk_coverage_subsamples,
            chunk_size=chunk_size,
        )
        inpainted_texels += _inpaint_invalid_face(
            face_size=face_size,
            face_event=face_event,
            face_failure=face_failure,
            face_dir=face_dir,
            face_disk_transfer=face_disk_transfer,
            face_disk_redshift=face_disk_redshift,
        )

        event_cube[face_index] = event_to_rgba8(
            face_event.reshape((face_size, face_size)),
            face_failure.reshape((face_size, face_size)),
        )
        dir_cube[face_index] = face_dir.reshape((face_size, face_size, 4))
        for order in range(DISK_TRANSFER_ORDER_COUNT):
            disk_transfer_cube[order, face_index] = face_disk_transfer[order].reshape((face_size, face_size, 4))
            disk_redshift_cube[order, face_index] = face_disk_redshift[order].reshape((face_size, face_size, 4))
            # Read coverage back out of the shipped array rather than from the
            # pre-repair `face_coverage`, so these statistics describe the
            # bytes actually written.
            coverage = face_disk_transfer[order][:, 3]
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
            "skyBlueshift": static_observer_sky_blueshift(
                params, r_obs, math.radians(inclination_deg)
            ),
            "skyBlueshiftNote": (
                "omega_obs / omega_inf = 1 / sqrt(-g_tt) for sky photons seen by "
                "the static observer; direction independent. This is the "
                "observer-frame frequency ratio only; how a consumer weights "
                "brightness or color with it is not asserted here."
            ),
        },
        "integration": {
            "step_size": step_size,
            "steps": steps,
            "lambda_budget": step_size * steps,
            "lambda_budget_note": (
                "affine budget in geometric length. The launcher normalizes "
                "-p.u = 1 in the observer frame, so E = -p_t = sqrt(-g_tt) "
                "shrinks toward the horizon and a fixed budget buys less "
                "coordinate path at small r_obs than at large r_obs."
            ),
            "horizon_eps": horizon_eps,
            "r_escape": config.r_escape,
            "r_escape_min": r_escape_min,
            "r_escape_note": (
                "effective escape radius is max(2 * r_obs, r_escape_min). The "
                "legacy 2 * r_obs rule is not asymptotic for near-horizon "
                "observers: measured escape-direction extraction error at "
                "r_obs = 2.5M is 6.7 deg mean / 22.8 deg max, falling below "
                "0.35 deg once r_escape >= 20M and reaching its floor by 50M."
            ),
        },
        "backend": backend,
        "eventCounts": event_counts,
        "eventCountsNote": (
            "raw per-ray classification accumulated during tracing, BEFORE the "
            "retrace and inpaint stages. The shipped event cube is post-repair, "
            "so these counts and that array can legitimately disagree; "
            "shippedEventCounts records the array."
        ),
        "shippedEventCounts": _count_events(event_cube),
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
        "captureSolidAngleFraction": (
            solid_angle_capture / solid_angle_total if solid_angle_total > 0.0 else 0.0
        ),
        "captureSolidAngleNote": (
            "fraction of the observer's 4 pi sky captured by the horizon, "
            "weighted by cube-texel solid angle rather than texel count, and "
            "taken from the raw pre-repair classification so image repairs "
            "cannot move a physics gate. This is the quantity that must grow "
            "monotonically as a static observer approaches."
        ),
        # Every post-trace stage reports whether it actually ran. A stage that
        # is configured off must not be advertised by an unconditional note.
        "stages": {
            "escapeCoverage": {
                "applied": bool(disk_coverage_subsamples > 1),
                "edgeTexels": escape_edge_texels,
                "subsamplesPerAxis": disk_coverage_subsamples,
                "note": (
                    "escape-direction alpha is fractional escape coverage at the "
                    "capture boundary and the direction channels are "
                    "premultiplied by it; the stored direction is a genuine "
                    "traced subray, not a mean over the photon-ring winding."
                )
                if disk_coverage_subsamples > 1
                else (
                    "NOT APPLIED (disk_coverage_subsamples <= 1): escape alpha "
                    "is a binary 0/1 validity flag and directions are not "
                    "premultiplied."
                ),
            },
            "invalidRetrace": {
                "applied": bool(disk_coverage_subsamples > 1),
                "texels": retraced_texels,
                "note": (
                    "solver-failure texels are re-traced with jittered "
                    "sub-texel rays that miss the measure-zero Boyer-Lindquist "
                    "axis locus; the stored direction is a genuine traced ray."
                )
                if disk_coverage_subsamples > 1
                else "NOT APPLIED (disk_coverage_subsamples <= 1).",
            },
            "invalidInpaint": {
                "applied": True,
                "texels": inpainted_texels,
                "note": (
                    "texels whose jittered retrace also failed adopt the "
                    "coverage-weighted mean of their non-invalid neighbours. "
                    "This is a heuristic repair, not traced physics, and is "
                    "counted here so a reviewer can bound how much of the cube "
                    "it touched."
                ),
            },
        },
        "polarBand": {
            "threshold_rad": polar_band_threshold,
            "texels": polar_band_texels,
            "repaired": False,
            "note": (
                "count of texels whose Boyer-Lindquist trajectory approached the "
                "polar axis closer than threshold_rad in min(theta, pi - theta). "
                "These are REPORTED, NOT REPAIRED: the chart-regular fix is a "
                "Cartesian Kerr-Schild retrace, which needs the KS tracer's "
                "equatorial disk-crossing outputs and therefore lands with the "
                "Kerr-Schild work. Treat a large count as a quality caveat on "
                "this keyframe."
            ),
        },
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


def _count_events(event_cube: np.ndarray) -> dict[str, int]:
    """Classify the shipped event cube so metadata can be checked against bytes."""

    codes = event_cube[..., 0].astype(np.int16)
    return {
        name: int(np.count_nonzero(codes == code)) for name, code in SCHEMA_EVENT_CODES.items()
    }


def _representative_direction(unit_directions: np.ndarray) -> np.ndarray:
    """Pick the genuine subray direction closest to the mean.

    Averaging escape directions across the photon-ring winding produces a
    direction no ray actually has, which paints stray speckles along the shadow
    limb.  A real traced direction is correct at sub-texel level by
    construction.
    """

    mean_dir = np.sum(unit_directions, axis=0, dtype=np.float64)
    norm = np.linalg.norm(mean_dir)
    if norm <= 0.0:
        return unit_directions[0].astype(np.float32)
    scores = unit_directions.astype(np.float64) @ (mean_dir / norm)
    return unit_directions[int(np.argmax(scores))].astype(np.float32)


def _trace_subray_escape(
    *,
    config: GpuTraceConfig,
    directions: np.ndarray,
    basis: Any,
    chunk_size: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Trace sub-texel directions, returning packed Unity dirs and event codes."""

    escape_code = SCHEMA_EVENT_CODES["escape"]
    packed = np.zeros((directions.shape[0], 4), dtype=np.float32)
    events = np.zeros((directions.shape[0],), dtype=np.int16)
    for start in range(0, directions.shape[0], chunk_size):
        end = min(start + chunk_size, directions.shape[0])
        result = trace_unity_direction_points(config, directions[start:end])
        event_code = result["event_code"].astype(np.int16)
        escape = escape_direction_arrays(
            params=config.params,
            event_code=event_code,
            r=result["final_r"],
            theta=result["final_theta"],
            phi=result["final_phi"],
            p_t=result["final_p_t"],
            p_r=result["final_p_r"],
            p_theta=result["final_p_theta"],
            p_phi=result["final_p_phi"],
            escape_code=escape_code,
        )
        dir_bh = np.stack(escape[2:], axis=-1)
        valid = (event_code == escape_code) & np.all(np.isfinite(dir_bh), axis=-1)
        dir_unity = _bh_to_unity(np.where(np.isfinite(dir_bh), dir_bh, 0.0), valid, basis)
        chunk = np.zeros((end - start, 4), dtype=np.float32)
        chunk[valid, :3] = dir_unity[valid]
        chunk[valid, 3] = 1.0
        packed[start:end] = chunk
        events[start:end] = event_code
    return packed, events


def _coverage_premultiply_escape_face(
    *,
    config: GpuTraceConfig,
    face_name: str,
    face_size: int,
    face_dir: np.ndarray,
    basis: Any,
    subsamples: int,
    chunk_size: int,
) -> tuple[np.ndarray, int]:
    """Anti-alias the escape/capture boundary with fractional escape coverage.

    Alpha becomes the escaping-subray fraction and the direction channels are
    premultiplied by it, so bilinear filtering across the shadow limb
    interpolates a meaningful coverage instead of stepping through a binary
    validity gate.
    """

    if subsamples <= 1:
        return face_dir, 0

    valid = (face_dir[:, 3] > 0.0).reshape((face_size, face_size))
    edge_indices = np.flatnonzero(_validity_boundary_mask(valid).ravel())
    if edge_indices.size == 0:
        return face_dir, 0

    directions = _subpixel_face_directions(
        face_name=face_name,
        face_size=face_size,
        flat_indices=edge_indices,
        subsamples=subsamples,
    )
    sub_count = subsamples * subsamples
    sub_dirs, _ = _trace_subray_escape(
        config=config, directions=directions, basis=basis, chunk_size=chunk_size
    )

    for edge_pos, flat_index in enumerate(edge_indices):
        samples = sub_dirs[edge_pos * sub_count : (edge_pos + 1) * sub_count]
        escaped = samples[:, 3] > 0.0
        coverage = float(np.count_nonzero(escaped)) / float(sub_count)
        face_dir[flat_index] = 0.0
        if coverage <= 0.0:
            continue
        face_dir[flat_index, :3] = _representative_direction(samples[escaped, :3]) * coverage
        face_dir[flat_index, 3] = coverage
    return face_dir, int(edge_indices.size)


def _retrace_invalid_face(
    *,
    config: GpuTraceConfig,
    face_name: str,
    face_size: int,
    face_event: np.ndarray,
    face_failure: np.ndarray,
    face_dir: np.ndarray,
    face_disk_transfer: np.ndarray,
    face_disk_redshift: np.ndarray,
    basis: Any,
    subsamples: int,
    chunk_size: int,
) -> int:
    """Re-trace solver-failure texels with jittered sub-texel rays.

    The Boyer-Lindquist polar-axis failure column is a measure-zero chart
    locus, so sub-texel directions offset from the texel centre miss it and the
    retrace yields genuine physics instead of a neighbour-smeared seam.  Texels
    whose subrays all fail are left for neighbour inpainting.
    """

    invalid_code = SCHEMA_EVENT_CODES["invalid"]
    escape_code = SCHEMA_EVENT_CODES["escape"]
    capture_code = SCHEMA_EVENT_CODES["capture"]
    invalid_indices = np.flatnonzero(face_event == invalid_code)
    if invalid_indices.size == 0 or subsamples <= 1:
        return 0

    directions = _subpixel_face_directions(
        face_name=face_name,
        face_size=face_size,
        flat_indices=invalid_indices,
        subsamples=subsamples,
    )
    sub_count = subsamples * subsamples
    order_count = face_disk_transfer.shape[0]
    sub_dirs, sub_event = _trace_subray_escape(
        config=config, directions=directions, basis=basis, chunk_size=chunk_size
    )
    sub_disk = np.zeros((order_count, directions.shape[0], 4), dtype=np.float32)
    for start in range(0, directions.shape[0], chunk_size):
        end = min(start + chunk_size, directions.shape[0])
        result = trace_unity_direction_points(config, directions[start:end])
        for order in range(order_count):
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
            sub_disk[order, start:end] = disk_packed

    retraced = 0
    for position, flat_index in enumerate(invalid_indices):
        sample_slice = slice(position * sub_count, (position + 1) * sub_count)
        usable = sub_event[sample_slice] != invalid_code
        usable_count = int(np.count_nonzero(usable))
        if usable_count == 0:
            continue
        samples = sub_dirs[sample_slice]
        escaped = usable & (samples[:, 3] > 0.0)
        coverage = float(np.count_nonzero(escaped)) / float(usable_count)
        face_dir[flat_index] = 0.0
        if coverage > 0.0:
            face_dir[flat_index, :3] = _representative_direction(samples[escaped, :3]) * coverage
            face_dir[flat_index, 3] = coverage
        face_event[flat_index] = escape_code if coverage >= 0.5 else capture_code
        face_failure[flat_index] = 0
        for order in range(order_count):
            disk_samples = sub_disk[order, sample_slice]
            disk_valid = usable & (disk_samples[:, 0] > 0.0) & (disk_samples[:, 3] > 0.0)
            face_disk_transfer[order, flat_index] = 0.0
            face_disk_redshift[order, flat_index] = 0.0
            if not np.any(disk_valid):
                continue
            denominator = float(usable_count)
            for channel in range(3):
                face_disk_transfer[order, flat_index, channel] = (
                    float(np.sum(disk_samples[disk_valid, channel], dtype=np.float64)) / denominator
                )
            face_disk_transfer[order, flat_index, 3] = (
                float(np.count_nonzero(disk_valid)) / denominator
            )
            face_disk_redshift[order, flat_index, 0] = (
                float(np.sum(disk_samples[disk_valid, 3], dtype=np.float64)) / denominator
            )
        retraced += 1
    return retraced


def _inpaint_invalid_face(
    *,
    face_size: int,
    face_event: np.ndarray,
    face_failure: np.ndarray,
    face_dir: np.ndarray,
    face_disk_transfer: np.ndarray,
    face_disk_redshift: np.ndarray,
) -> int:
    """Fill remaining solver-failure texels from their neighbours.

    Heuristic repair, not traced physics.  An invalid texel surrounded mostly
    by escaping neighbours adopts their premultiplied mean direction/coverage;
    one inside the shadow becomes a plain capture texel.  Disk channels are
    averaged in premultiplied space, which is the correct linear operation for
    coverage-weighted data.  Returns the number of texels rewritten so callers
    can record it.
    """

    invalid_code = SCHEMA_EVENT_CODES["invalid"]
    capture_code = SCHEMA_EVENT_CODES["capture"]
    escape_code = SCHEMA_EVENT_CODES["escape"]
    order_count = face_disk_transfer.shape[0]
    total_inpainted = 0
    for _ in range(2):
        event2d = face_event.reshape((face_size, face_size))
        invalid_mask = event2d == invalid_code
        if not np.any(invalid_mask):
            break
        dir2d = face_dir.reshape((face_size, face_size, 4))
        disk2d = face_disk_transfer.reshape((order_count, face_size, face_size, 4))
        redshift2d = face_disk_redshift.reshape(disk2d.shape)
        neighbour_alpha_sum = np.zeros((face_size, face_size), dtype=np.float64)
        neighbour_dir_sum = np.zeros((face_size, face_size, 4), dtype=np.float64)
        neighbour_disk_sum = np.zeros((order_count, face_size, face_size, 4), dtype=np.float64)
        neighbour_redshift_sum = np.zeros_like(neighbour_disk_sum)
        neighbour_count = np.zeros((face_size, face_size), dtype=np.float64)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                shifted_ok = np.roll(np.roll(event2d, dy, axis=0), dx, axis=1) != invalid_code
                # Rolled-in wraparound rows/columns are not real neighbours.
                if dy == 1:
                    shifted_ok[0, :] = False
                elif dy == -1:
                    shifted_ok[-1, :] = False
                if dx == 1:
                    shifted_ok[:, 0] = False
                elif dx == -1:
                    shifted_ok[:, -1] = False
                weight = shifted_ok.astype(np.float64)
                neighbour_count += weight
                shifted_dir = np.roll(np.roll(dir2d, dy, axis=0), dx, axis=1)
                neighbour_dir_sum += shifted_dir * weight[..., np.newaxis]
                neighbour_alpha_sum += shifted_dir[..., 3] * weight
                for order in range(order_count):
                    neighbour_disk_sum[order] += (
                        np.roll(np.roll(disk2d[order], dy, axis=0), dx, axis=1)
                        * weight[..., np.newaxis]
                    )
                    neighbour_redshift_sum[order] += (
                        np.roll(np.roll(redshift2d[order], dy, axis=0), dx, axis=1)
                        * weight[..., np.newaxis]
                    )

        fixable = invalid_mask & (neighbour_count > 0.0)
        if not np.any(fixable):
            break
        counts = np.maximum(neighbour_count, 1.0)
        escape_like = fixable & ((neighbour_alpha_sum / counts) > 0.5)
        capture_like = fixable & ~escape_like

        dir_mean = neighbour_dir_sum / counts[..., np.newaxis]
        dir2d[escape_like] = dir_mean[escape_like].astype(np.float32)
        dir2d[capture_like] = 0.0
        for order in range(order_count):
            disk2d[order][fixable] = (
                (neighbour_disk_sum[order] / counts[..., np.newaxis])[fixable]
            ).astype(disk2d.dtype)
            redshift2d[order][fixable] = (
                (neighbour_redshift_sum[order] / counts[..., np.newaxis])[fixable]
            ).astype(redshift2d.dtype)

        event2d[escape_like] = escape_code
        event2d[capture_like] = capture_code
        face_failure.reshape((face_size, face_size))[fixable] = 0
        total_inpainted += int(np.count_nonzero(fixable))
    return total_inpainted


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
    parser.add_argument("--r-escape-min", type=float, default=0.0)
    parser.add_argument("--polar-band-threshold", type=float, default=DEFAULT_POLAR_BAND_THRESHOLD)
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
        r_escape_min=args.r_escape_min,
        polar_band_threshold=args.polar_band_threshold,
        command=" ".join(sys.argv),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
