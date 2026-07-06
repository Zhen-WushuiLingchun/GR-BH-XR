"""Export GPU lens-map HDF5 buffers as Unity-consumable static textures."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys
from typing import Any

import h5py
import numpy as np


PACKAGE_SCHEMA = "gr-bh-xr.task5.unity_texture_package.v2"


@dataclass(frozen=True)
class UnityBasis:
    """BH-Cartesian basis vectors used as Unity right/up/forward axes."""

    right_bh: np.ndarray
    up_bh: np.ndarray
    forward_bh: np.ndarray


def unity_basis_from_inclination(inclination_deg: float) -> UnityBasis:
    """Return the documented BH-to-Unity basis for an observer at phi=0.

    BH Cartesian coordinates use +Z as the Kerr spin axis and +X at observer
    azimuth phi=0. Unity forward points from the camera toward the black hole.
    Unity right is the positive-alpha screen direction.
    """

    theta = math.radians(float(inclination_deg))
    observer_bh = np.asarray([math.sin(theta), 0.0, math.cos(theta)], dtype=np.float64)
    forward_bh = _normalize(-observer_bh)
    spin_bh = np.asarray([0.0, 0.0, 1.0], dtype=np.float64)
    up_bh = spin_bh - float(np.dot(spin_bh, forward_bh)) * forward_bh
    if np.linalg.norm(up_bh) < 1.0e-10:
        fallback = np.asarray([1.0, 0.0, 0.0], dtype=np.float64)
        up_bh = fallback - float(np.dot(fallback, forward_bh)) * forward_bh
    up_bh = _normalize(up_bh)
    right_bh = _normalize(np.cross(up_bh, forward_bh))
    up_bh = _normalize(np.cross(forward_bh, right_bh))
    return UnityBasis(right_bh=right_bh, up_bh=up_bh, forward_bh=forward_bh)


def export_unity_texture_package(
    *,
    input_path: Path | str,
    out_dir: Path | str,
    command: str = "",
    target_size: int | None = None,
) -> dict[str, Any]:
    """Export event and escape-direction textures plus coordinate metadata."""

    input_path = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with h5py.File(input_path, "r") as handle:
        alpha = handle["alpha"][...].astype(np.float64)
        beta = handle["beta"][...].astype(np.float64)
        event_rgba8 = handle["event_rgba8"][...].astype(np.uint8)
        dir_bh = np.stack(
            [
                handle["gpu_escape_dir_x"][...],
                handle["gpu_escape_dir_y"][...],
                handle["gpu_escape_dir_z"][...],
            ],
            axis=-1,
        ).astype(np.float32)
        event_code = handle["gpu_event_code"][...]
        source_attrs = {key: _json_value(value) for key, value in handle.attrs.items()}
        inclination_deg = float(handle.attrs["inclination_deg"])

    source_height, source_width = event_rgba8.shape[:2]
    height, width = source_height, source_width
    if event_rgba8.shape != (height, width, 4):
        raise ValueError("event_rgba8 must be an HxWx4 buffer.")
    if dir_bh.shape != (height, width, 3):
        raise ValueError("escape direction buffers must match event texture dimensions.")
    if alpha.shape != (width,) or beta.shape != (height,):
        raise ValueError("alpha/beta axes do not match texture dimensions.")
    if target_size is not None:
        if target_size < 2:
            raise ValueError("target_size must be at least 2 when provided.")
        height = int(target_size)
        width = int(target_size)

    basis = unity_basis_from_inclination(inclination_deg)
    valid = (event_code == 1) & np.all(np.isfinite(dir_bh), axis=-1)
    dir_bh_rgba = _pack_direction_rgba(dir_bh, valid)
    dir_unity = _bh_to_unity(dir_bh, valid, basis)
    dir_unity_rgba = _pack_direction_rgba(dir_unity, valid)
    if (height, width) != (source_height, source_width):
        event_rgba8 = _resize_nearest(event_rgba8, height, width)
        event_code = _resize_nearest(event_code, height, width)
        dir_bh_rgba = _resize_direction_rgba(dir_bh_rgba, height, width)
        dir_unity_rgba = _resize_direction_rgba(dir_unity_rgba, height, width)
    escape_pixels = int(np.count_nonzero(event_code == 1))
    export_event_rgba8 = np.flipud(event_rgba8)
    export_dir_bh_rgba = np.flipud(dir_bh_rgba)
    export_dir_unity_rgba = np.flipud(dir_unity_rgba)

    event_path = out_dir / "event_rgba8.bytes"
    dir_bh_path = out_dir / "escape_dir_bh_rgba32f.bytes"
    dir_unity_path = out_dir / "escape_dir_unity_rgba32f.bytes"
    metadata_path = out_dir / "lens_map_metadata.json"
    preview_path = out_dir / "event_preview.png"

    export_event_rgba8.tofile(event_path)
    export_dir_bh_rgba.astype("<f4", copy=False).tofile(dir_bh_path)
    export_dir_unity_rgba.astype("<f4", copy=False).tofile(dir_unity_path)
    _write_event_preview(preview_path, export_event_rgba8)

    metadata = _metadata(
        source_path=input_path,
        source_attrs=source_attrs,
        command=command,
        alpha=alpha,
        beta=beta,
        width=width,
        height=height,
        source_width=source_width,
        source_height=source_height,
        basis=basis,
        event_path=event_path.name,
        dir_bh_path=dir_bh_path.name,
        dir_unity_path=dir_unity_path.name,
        preview_path=preview_path.name,
        escape_pixels=escape_pixels,
    )
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf8")

    return {
        "out_dir": str(out_dir),
        "schema": PACKAGE_SCHEMA,
        "width": width,
        "height": height,
        "source_width": source_width,
        "source_height": source_height,
        "escape_pixels": escape_pixels,
        "files": {
            "event_rgba8": str(event_path),
            "escape_dir_bh_rgba32f": str(dir_bh_path),
            "escape_dir_unity_rgba32f": str(dir_unity_path),
            "metadata": str(metadata_path),
            "event_preview": str(preview_path),
        },
    }


def _bh_to_unity(dir_bh: np.ndarray, valid: np.ndarray, basis: UnityBasis) -> np.ndarray:
    dir_unity = np.full(dir_bh.shape, np.nan, dtype=np.float32)
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
    mapped[good] = mapped[good] / norm[good, np.newaxis]
    local = np.flatnonzero(valid)
    if np.any(good):
        dir_unity.reshape((-1, 3))[local[good]] = mapped[good].astype(np.float32)
    return dir_unity


def _pack_direction_rgba(direction: np.ndarray, valid: np.ndarray) -> np.ndarray:
    rgba = np.zeros(direction.shape[:2] + (4,), dtype=np.float32)
    rgba[..., :3] = np.where(valid[..., np.newaxis], direction, 0.0)
    rgba[..., 3] = valid.astype(np.float32)
    return rgba


def _resize_nearest(values: np.ndarray, target_height: int, target_width: int) -> np.ndarray:
    source_height, source_width = values.shape[:2]
    if (source_height, source_width) == (target_height, target_width):
        return values
    rows = np.rint(np.linspace(0, source_height - 1, target_height)).astype(np.int64)
    cols = np.rint(np.linspace(0, source_width - 1, target_width)).astype(np.int64)
    return values[rows[:, np.newaxis], cols]


def _resize_linear(values: np.ndarray, target_height: int, target_width: int) -> np.ndarray:
    source_height, source_width = values.shape[:2]
    if (source_height, source_width) == (target_height, target_width):
        return values
    src_y = np.linspace(0.0, source_height - 1, target_height)
    y0 = np.floor(src_y).astype(np.int64)
    y1 = np.clip(y0 + 1, 0, source_height - 1)
    wy = (src_y - y0).astype(np.float32)
    rows = (1.0 - wy)[:, np.newaxis, np.newaxis] * values[y0] + wy[
        :, np.newaxis, np.newaxis
    ] * values[y1]
    src_x = np.linspace(0.0, source_width - 1, target_width)
    x0 = np.floor(src_x).astype(np.int64)
    x1 = np.clip(x0 + 1, 0, source_width - 1)
    wx = (src_x - x0).astype(np.float32)
    return (1.0 - wx)[np.newaxis, :, np.newaxis] * rows[:, x0] + wx[
        np.newaxis, :, np.newaxis
    ] * rows[:, x1]


def _resize_direction_rgba(
    direction_rgba: np.ndarray, target_height: int, target_width: int
) -> np.ndarray:
    resized = _resize_linear(direction_rgba.astype(np.float32), target_height, target_width)
    valid = resized[..., 3] > 0.5
    norm = np.linalg.norm(resized[..., :3], axis=-1)
    good = valid & np.isfinite(norm) & (norm > 0.0)
    rgb = resized[..., :3].copy()
    resized[..., :3] = 0.0
    resized[..., 3] = valid.astype(np.float32)
    rgb_out = resized[..., :3]
    rgb_out[good] = rgb[good] / norm[good, np.newaxis]
    return resized.astype(np.float32, copy=False)


def _metadata(
    *,
    source_path: Path,
    source_attrs: dict[str, Any],
    command: str,
    alpha: np.ndarray,
    beta: np.ndarray,
    width: int,
    height: int,
    source_width: int,
    source_height: int,
    basis: UnityBasis,
    event_path: str,
    dir_bh_path: str,
    dir_unity_path: str,
    preview_path: str,
    escape_pixels: int,
) -> dict[str, Any]:
    return {
        "schema": PACKAGE_SCHEMA,
        "sourceHdf5": str(source_path),
        "sourceSchema": source_attrs.get("schema", ""),
        "generationCommand": command,
        "width": width,
        "height": height,
        "escapePixels": escape_pixels,
        "resolution": {
            "sourceWidth": source_width,
            "sourceHeight": source_height,
            "exportWidth": width,
            "exportHeight": height,
            "nativeTraceResolution": source_width == width and source_height == height,
            "resampling": (
                "none"
                if source_width == width and source_height == height
                else "display resample: nearest event texture, bilinear normalized direction texture"
            ),
            "physicsNote": (
                "If nativeTraceResolution is false, the exported texture is display-resampled "
                "from the source lens map and must not be used as evidence of higher physical "
                "ray-tracing resolution."
            ),
        },
        "screenConvention": {
            "alphaColumnOrder": "x=0 is alpha_min; x=width-1 is alpha_max",
            "betaRowOrder": "exported y=0 is beta_max; exported y=height-1 is beta_min",
            "textureOrigin": "bottom_left",
            "uToAlpha": "alpha = alpha_min + u * (alpha_max - alpha_min)",
            "vToBeta": "beta = beta_max - v * (beta_max - beta_min)",
            "positiveAlpha": "Unity +X / screen right",
            "positiveBeta": "solver +beta increases theta and points visually downward; export applies flipud so texture +V points visually upward toward decreasing beta",
            "verticalFlipApplied": True,
        },
        "screen": {
            "alphaMin": float(alpha[0]),
            "alphaMax": float(alpha[-1]),
            "betaMin": float(beta[0]),
            "betaMax": float(beta[-1]),
        },
        "bhCartesianConvention": {
            "x": "Boyer-Lindquist phi=0 equatorial direction",
            "y": "Boyer-Lindquist phi=pi/2 equatorial direction",
            "z": "Kerr spin axis",
            "observer": "r_obs at phi=0 and theta=inclination_deg",
        },
        "unityBasisInBhCoordinates": {
            "rightBh": basis.right_bh.tolist(),
            "upBh": basis.up_bh.tolist(),
            "forwardBh": basis.forward_bh.tolist(),
            "mapping": "unity = (dot(dir_bh,rightBh), dot(dir_bh,upBh), dot(dir_bh,forwardBh))",
        },
        "textures": {
            "eventRgba8": {
                "file": event_path,
                "format": "raw RGBA8",
                "bytes": width * height * 4,
            },
            "escapeDirBhRgba32f": {
                "file": dir_bh_path,
                "format": "raw little-endian RGBAFloat",
                "channels": "x_bh, y_bh, z_bh, valid_escape",
                "bytes": width * height * 4 * 4,
            },
            "escapeDirUnityRgba32f": {
                "file": dir_unity_path,
                "format": "raw little-endian RGBAFloat",
                "channels": "x_unity, y_unity, z_unity, valid_escape",
                "bytes": width * height * 4 * 4,
            },
            "eventPreviewPng": {
                "file": preview_path,
                "role": "human preview only; raw .bytes files are authoritative",
            },
        },
        "sourceAttributes": source_attrs,
    }


def _write_event_preview(path: Path, event_rgba8: np.ndarray) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    plt.imsave(path, event_rgba8, origin="lower")


def _normalize(value: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(value)
    if not math.isfinite(float(norm)) or norm <= 0.0:
        raise ValueError("Cannot normalize a zero or non-finite vector.")
    return value / norm


def _json_value(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, bytes):
        return value.decode("utf8", errors="replace")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, dest="input_path")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--target-size",
        type=int,
        default=None,
        help=(
            "Optional square export resolution, e.g. 4096 for a 4K display texture. "
            "This resamples the source lens map for display and does not add physical trace resolution."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = export_unity_texture_package(
        input_path=args.input_path,
        out_dir=args.out_dir,
        command=" ".join(sys.argv),
        target_size=args.target_size,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
