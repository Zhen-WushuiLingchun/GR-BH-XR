"""Compare a Unity protractor gate screenshot against escape-direction bytes.

The protractor gate encodes polar angle away from Unity +Z in 10-degree bands.
This script reads the PNG screenshot, converts its sRGB samples back to linear
values, bilinearly samples ``escape_dir_unity_rgba32f.bytes``, and compares the
observed bands against two hypotheses:

- the raw exported direction;
- the old failure mode where x/y direction components were scaled by 20 before
  normalization.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import matplotlib.image as mpimg
import numpy as np


UNITY_CUBE_FACES = ("PositiveX", "NegativeX", "PositiveY", "NegativeY", "PositiveZ", "NegativeZ")


@dataclass(frozen=True)
class ProtractorComparison:
    mapping: str
    valid: int
    exact_raw: int
    exact_old_skew: int
    raw_closer: int
    old_skew_closer: int
    tie: int
    mean_abs_band_error_raw: float
    mean_abs_band_error_old_skew: float
    seam_pair_count: int = 0
    seam_max_observed_band_jump: float = float("nan")
    seam_violations: int = 0


def srgb_to_linear(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    return np.where(values <= 0.04045, values / 12.92, ((values + 0.055) / 1.055) ** 2.4)


def band_from_direction(direction: np.ndarray) -> int | None:
    direction = np.asarray(direction[:3], dtype=np.float64)
    norm = float(np.linalg.norm(direction))
    if norm <= 0.0 or not math.isfinite(norm):
        return None
    unit = direction / norm
    theta_deg = math.degrees(math.acos(max(-1.0, min(1.0, float(unit[2])))))
    return max(0, min(17, int(math.floor(theta_deg / 10.0))))


def band_from_linear_rgb(rgb: np.ndarray) -> int:
    encoded = float(rgb[0])
    return max(0, min(17, int(round(encoded * 18.0 - 0.5))))


def bilinear_direction(directions: np.ndarray, u: float, v: float) -> np.ndarray:
    height, width, _ = directions.shape
    x = max(0.0, min(float(width - 1), u * (width - 1)))
    y = max(0.0, min(float(height - 1), v * (height - 1)))
    x0 = int(math.floor(x))
    y0 = int(math.floor(y))
    x1 = min(width - 1, x0 + 1)
    y1 = min(height - 1, y0 + 1)
    tx = x - x0
    ty = y - y0
    return (
        (1.0 - tx) * (1.0 - ty) * directions[y0, x0]
        + tx * (1.0 - ty) * directions[y0, x1]
        + (1.0 - tx) * ty * directions[y1, x0]
        + tx * ty * directions[y1, x1]
    )


def bilinear_cubemap_direction(cube: np.ndarray, direction: np.ndarray) -> np.ndarray:
    face, u, v = cubemap_face_uv(direction)
    face_index = UNITY_CUBE_FACES.index(face)
    return bilinear_direction_texel_center(cube[face_index], u, v)


def bilinear_direction_texel_center(directions: np.ndarray, u: float, v: float) -> np.ndarray:
    height, width, _ = directions.shape
    x = np.clip(u * width - 0.5, 0.0, width - 1.0)
    y = np.clip(v * height - 0.5, 0.0, height - 1.0)
    x0 = int(np.floor(x))
    y0 = int(np.floor(y))
    x1 = min(x0 + 1, width - 1)
    y1 = min(y0 + 1, height - 1)
    tx = x - x0
    ty = y - y0
    return (
        (1.0 - tx) * (1.0 - ty) * directions[y0, x0]
        + tx * (1.0 - ty) * directions[y0, x1]
        + (1.0 - tx) * ty * directions[y1, x0]
        + tx * ty * directions[y1, x1]
    )


def cubemap_face_uv(direction: np.ndarray) -> tuple[str, float, float]:
    direction = np.asarray(direction[:3], dtype=np.float64)
    norm = float(np.linalg.norm(direction))
    if norm <= 0.0 or not math.isfinite(norm):
        raise ValueError("direction must be finite and non-zero")
    x, y, z = direction / norm
    ax = abs(x)
    ay = abs(y)
    az = abs(z)
    if ax >= ay and ax >= az:
        if x >= 0.0:
            face = "PositiveX"
            uu = -z / ax
            vv = -y / ax
        else:
            face = "NegativeX"
            uu = z / ax
            vv = -y / ax
    elif ay >= ax and ay >= az:
        if y >= 0.0:
            face = "PositiveY"
            uu = x / ay
            vv = z / ay
        else:
            face = "NegativeY"
            uu = x / ay
            vv = -z / ay
    else:
        if z >= 0.0:
            face = "PositiveZ"
            uu = x / az
            vv = -y / az
        else:
            face = "NegativeZ"
            uu = -x / az
            vv = -y / az
    return face, 0.5 * (uu + 1.0), 0.5 * (vv + 1.0)


def screen_ray_direction(screen_x: float, screen_y: float, *, fov_deg: float, yaw_deg: float) -> np.ndarray:
    half = math.tan(math.radians(fov_deg) * 0.5)
    camera_ray = np.asarray(
        [
            (2.0 * screen_x - 1.0) * half,
            (1.0 - 2.0 * screen_y) * half,
            1.0,
        ],
        dtype=np.float64,
    )
    camera_ray = camera_ray / np.linalg.norm(camera_ray)
    yaw = math.radians(yaw_deg)
    cy = math.cos(yaw)
    sy = math.sin(yaw)
    return np.asarray(
        [
            cy * camera_ray[0] + sy * camera_ray[2],
            camera_ray[1],
            -sy * camera_ray[0] + cy * camera_ray[2],
        ],
        dtype=np.float64,
    )


def compare_protractor(
    image_srgb: np.ndarray,
    directions: np.ndarray,
    *,
    samples: int = 61,
    old_skew: float = 20.0,
    mapping: str = "u=x,v=1-y",
) -> ProtractorComparison:
    if samples < 2:
        raise ValueError("samples must be at least 2")
    if image_srgb.ndim != 3 or image_srgb.shape[2] < 3:
        raise ValueError("image_srgb must have shape (height, width, channels>=3)")
    if directions.ndim != 3 or directions.shape[2] != 4:
        raise ValueError("directions must have shape (height, width, 4)")

    mapper = _screen_to_texture_mapping(mapping)
    image_linear = srgb_to_linear(image_srgb[..., :3])

    valid = 0
    exact_raw = 0
    exact_old_skew = 0
    raw_closer = 0
    old_skew_closer = 0
    tie = 0
    raw_abs = 0.0
    skew_abs = 0.0

    for screen_y in np.linspace(0.05, 0.95, samples):
        for screen_x in np.linspace(0.05, 0.95, samples):
            px = int(round(screen_x * (image_linear.shape[1] - 1)))
            py = int(round(screen_y * (image_linear.shape[0] - 1)))
            rgb = image_linear[py, px]
            if float(np.linalg.norm(rgb)) < 0.08:
                continue

            u, v = mapper(float(screen_x), float(screen_y))
            direction = bilinear_direction(directions, u, v)
            if float(direction[3]) < 0.5:
                continue

            raw_band = band_from_direction(direction)
            skew_band = band_from_direction(
                np.asarray([old_skew * direction[0], old_skew * direction[1], direction[2]])
            )
            if raw_band is None or skew_band is None or raw_band == skew_band:
                continue

            observed_band = band_from_linear_rgb(rgb)
            raw_error = abs(observed_band - raw_band)
            skew_error = abs(observed_band - skew_band)

            valid += 1
            exact_raw += int(raw_error == 0)
            exact_old_skew += int(skew_error == 0)
            raw_abs += raw_error
            skew_abs += skew_error

            if raw_error < skew_error:
                raw_closer += 1
            elif skew_error < raw_error:
                old_skew_closer += 1
            else:
                tie += 1

    return ProtractorComparison(
        mapping=mapping,
        valid=valid,
        exact_raw=exact_raw,
        exact_old_skew=exact_old_skew,
        raw_closer=raw_closer,
        old_skew_closer=old_skew_closer,
        tie=tie,
        mean_abs_band_error_raw=raw_abs / valid if valid else float("nan"),
        mean_abs_band_error_old_skew=skew_abs / valid if valid else float("nan"),
    )


def compare_full_sky_protractor(
    image_srgb: np.ndarray,
    cube_directions: np.ndarray,
    *,
    samples: int = 61,
    fov_deg: float,
    yaw_deg: float,
    r_obs: float,
    alpha_max: float,
    beta_max: float,
    seam_tolerance_bands: int = 1,
) -> ProtractorComparison:
    if samples < 2:
        raise ValueError("samples must be at least 2")
    if image_srgb.ndim != 3 or image_srgb.shape[2] < 3:
        raise ValueError("image_srgb must have shape (height, width, channels>=3)")
    if cube_directions.ndim != 4 or cube_directions.shape[0] != len(UNITY_CUBE_FACES):
        raise ValueError("cube_directions must have shape (6, face, face, 4)")

    image_linear = srgb_to_linear(image_srgb[..., :3])
    valid = 0
    exact_raw = 0
    raw_closer = 0
    raw_abs = 0.0
    for screen_y in np.linspace(0.05, 0.95, samples):
        for screen_x in np.linspace(0.05, 0.95, samples):
            px = int(round(screen_x * (image_linear.shape[1] - 1)))
            py = int(round(screen_y * (image_linear.shape[0] - 1)))
            rgb = image_linear[py, px]
            if float(np.linalg.norm(rgb)) < 0.08:
                continue
            observed_band = band_from_linear_rgb(rgb)
            local_ray = screen_ray_direction(screen_x, screen_y, fov_deg=fov_deg, yaw_deg=yaw_deg)
            direction = bilinear_cubemap_direction(cube_directions, local_ray)
            if float(direction[3]) < 0.5:
                continue
            raw_band = band_from_direction(direction)
            if raw_band is None:
                continue
            raw_error = abs(observed_band - raw_band)
            valid += 1
            exact_raw += int(raw_error == 0)
            raw_abs += raw_error
            if raw_error == 0:
                raw_closer += 1

    seam = seam_stats(
        image_linear,
        fov_deg=fov_deg,
        yaw_deg=yaw_deg,
        r_obs=r_obs,
        alpha_max=alpha_max,
        beta_max=beta_max,
        tolerance_bands=seam_tolerance_bands,
    )
    return ProtractorComparison(
        mapping=f"full-sky-cubemap,fov={fov_deg},yaw={yaw_deg}",
        valid=valid,
        exact_raw=exact_raw,
        exact_old_skew=0,
        raw_closer=raw_closer,
        old_skew_closer=0,
        tie=0,
        mean_abs_band_error_raw=raw_abs / valid if valid else float("nan"),
        mean_abs_band_error_old_skew=float("nan"),
        seam_pair_count=seam["pair_count"],
        seam_max_observed_band_jump=seam["max_observed_band_jump"],
        seam_violations=seam["violations"],
    )


def seam_stats(
    image_linear: np.ndarray,
    *,
    fov_deg: float,
    yaw_deg: float,
    r_obs: float,
    alpha_max: float,
    beta_max: float,
    tolerance_bands: int,
    samples: int = 101,
) -> dict[str, int | float]:
    bands = np.full((samples, samples), -1, dtype=np.int16)
    inside = np.zeros((samples, samples), dtype=bool)
    nonblack = np.zeros((samples, samples), dtype=bool)
    coords = np.linspace(0.02, 0.98, samples)
    for iy, screen_y in enumerate(coords):
        for ix, screen_x in enumerate(coords):
            px = int(round(screen_x * (image_linear.shape[1] - 1)))
            py = int(round(screen_y * (image_linear.shape[0] - 1)))
            rgb = image_linear[py, px]
            if float(np.linalg.norm(rgb)) < 0.08:
                continue
            local_ray = screen_ray_direction(screen_x, screen_y, fov_deg=fov_deg, yaw_deg=yaw_deg)
            if local_ray[2] <= 1.0e-5:
                continue
            alpha = r_obs * local_ray[0] / local_ray[2]
            beta = -r_obs * local_ray[1] / local_ray[2]
            inside[iy, ix] = abs(alpha) <= alpha_max and abs(beta) <= beta_max
            nonblack[iy, ix] = True
            bands[iy, ix] = band_from_linear_rgb(rgb)

    jumps: list[int] = []
    for axis in (0, 1):
        if axis == 0:
            pairs = zip(inside[:-1, :].ravel(), inside[1:, :].ravel(), bands[:-1, :].ravel(), bands[1:, :].ravel(), nonblack[:-1, :].ravel(), nonblack[1:, :].ravel())
        else:
            pairs = zip(inside[:, :-1].ravel(), inside[:, 1:].ravel(), bands[:, :-1].ravel(), bands[:, 1:].ravel(), nonblack[:, :-1].ravel(), nonblack[:, 1:].ravel())
        for inside_a, inside_b, band_a, band_b, valid_a, valid_b in pairs:
            if inside_a == inside_b or not valid_a or not valid_b:
                continue
            jumps.append(abs(int(band_a) - int(band_b)))
    if not jumps:
        return {"pair_count": 0, "max_observed_band_jump": math.nan, "violations": 0}
    return {
        "pair_count": len(jumps),
        "max_observed_band_jump": float(max(jumps)),
        "violations": int(sum(jump > tolerance_bands for jump in jumps)),
    }


def load_direction_package(package_dir: Path) -> np.ndarray:
    metadata = json.loads((package_dir / "lens_map_metadata.json").read_text(encoding="utf8"))
    width = int(metadata["width"])
    height = int(metadata["height"])
    return np.fromfile(package_dir / "escape_dir_unity_rgba32f.bytes", dtype="<f4").reshape(
        (height, width, 4)
    )


def load_full_sky_direction_package(package_dir: Path) -> np.ndarray:
    metadata = json.loads((package_dir / "full_sky_transfer_metadata.json").read_text(encoding="utf8"))
    face_size = int(metadata["faceSize"])
    data = np.fromfile(package_dir / "escape_dir_unity_cube_rgba32f.bytes", dtype="<f4")
    return data.reshape((len(UNITY_CUBE_FACES), face_size, face_size, 4))


def load_srgb_png(path: Path) -> np.ndarray:
    image = mpimg.imread(path)
    if image.dtype.kind in {"u", "i"}:
        image = image.astype(np.float64) / np.iinfo(image.dtype).max
    return np.asarray(image[..., :3], dtype=np.float64)


def json_ready(value):
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    return value


def _screen_to_texture_mapping(mapping: str) -> Callable[[float, float], tuple[float, float]]:
    mappings: dict[str, Callable[[float, float], tuple[float, float]]] = {
        "u=x,v=y": lambda x, y: (x, y),
        "u=x,v=1-y": lambda x, y: (x, 1.0 - y),
        "u=1-x,v=y": lambda x, y: (1.0 - x, y),
        "u=1-x,v=1-y": lambda x, y: (1.0 - x, 1.0 - y),
    }
    try:
        return mappings[mapping]
    except KeyError as exc:
        raise ValueError(f"unknown mapping {mapping!r}; choose one of {sorted(mappings)}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path)
    parser.add_argument("--full-sky-package-dir", type=Path)
    parser.add_argument("--screenshot", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=61)
    parser.add_argument("--old-skew", type=float, default=20.0)
    parser.add_argument("--mapping", default="u=x,v=1-y")
    parser.add_argument("--fov-deg", type=float, default=9.1478)
    parser.add_argument("--yaw-deg", type=float, default=0.0)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--alpha-max", type=float, default=8.0)
    parser.add_argument("--beta-max", type=float, default=8.0)
    parser.add_argument("--seam-tolerance-bands", type=int, default=1)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    image_srgb = load_srgb_png(args.screenshot)
    if args.full_sky_package_dir is not None:
        cube_directions = load_full_sky_direction_package(args.full_sky_package_dir)
        result = compare_full_sky_protractor(
            image_srgb,
            cube_directions,
            samples=args.samples,
            fov_deg=args.fov_deg,
            yaw_deg=args.yaw_deg,
            r_obs=args.r_obs,
            alpha_max=args.alpha_max,
            beta_max=args.beta_max,
            seam_tolerance_bands=args.seam_tolerance_bands,
        )
    else:
        if args.package_dir is None:
            parser.error("--package-dir is required unless --full-sky-package-dir is used")
        directions = load_direction_package(args.package_dir)
        result = compare_protractor(
            image_srgb,
            directions,
            samples=args.samples,
            old_skew=args.old_skew,
            mapping=args.mapping,
        )

    payload = asdict(result)
    if args.json:
        print(json.dumps(json_ready(payload), indent=2, sort_keys=True))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
