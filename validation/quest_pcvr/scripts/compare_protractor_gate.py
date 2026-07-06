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


def load_direction_package(package_dir: Path) -> np.ndarray:
    metadata = json.loads((package_dir / "lens_map_metadata.json").read_text(encoding="utf8"))
    width = int(metadata["width"])
    height = int(metadata["height"])
    return np.fromfile(package_dir / "escape_dir_unity_rgba32f.bytes", dtype="<f4").reshape(
        (height, width, 4)
    )


def load_srgb_png(path: Path) -> np.ndarray:
    image = mpimg.imread(path)
    if image.dtype.kind in {"u", "i"}:
        image = image.astype(np.float64) / np.iinfo(image.dtype).max
    return np.asarray(image[..., :3], dtype=np.float64)


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
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=61)
    parser.add_argument("--old-skew", type=float, default=20.0)
    parser.add_argument("--mapping", default="u=x,v=1-y")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    directions = load_direction_package(args.package_dir)
    image_srgb = load_srgb_png(args.screenshot)
    result = compare_protractor(
        image_srgb,
        directions,
        samples=args.samples,
        old_skew=args.old_skew,
        mapping=args.mapping,
    )

    payload = asdict(result)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
