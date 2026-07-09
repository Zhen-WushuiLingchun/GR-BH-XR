"""Generate CPU blackbody color LUT assets for thin-disk visual shaders."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .disk_spectrum import (
    write_blackbody_lut_npz,
    write_blackbody_lut_unity_raw,
    write_page_thorne_radial_lut_unity_raw,
)
from .types import MetricParams


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--temperature-min-k", type=float, default=1000.0)
    parser.add_argument("--temperature-max-k", type=float, default=40000.0)
    parser.add_argument("--samples", type=int, default=256)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--raw-rgba32f", type=Path, default=None)
    parser.add_argument("--metadata-json", type=Path, default=None)
    parser.add_argument("--radial-raw-rgba32f", type=Path, default=None)
    parser.add_argument("--radial-metadata-json", type=Path, default=None)
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--spin", type=float, default=0.9)
    parser.add_argument("--r-max", type=float, default=30.0)
    parser.add_argument("--radius-samples", type=int, default=512)
    parser.add_argument("--temperature-scale-k", type=float, default=6500.0)
    parser.add_argument("--retrograde", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = write_blackbody_lut_npz(
        args.out,
        temperature_min_k=args.temperature_min_k,
        temperature_max_k=args.temperature_max_k,
        samples=args.samples,
    )
    if args.raw_rgba32f is not None:
        summary["unity_color_lut"] = write_blackbody_lut_unity_raw(
            args.raw_rgba32f,
            metadata_out=args.metadata_json,
            temperature_min_k=args.temperature_min_k,
            temperature_max_k=args.temperature_max_k,
            samples=args.samples,
        )
    if args.radial_raw_rgba32f is not None:
        summary["unity_radial_lut"] = write_page_thorne_radial_lut_unity_raw(
            args.radial_raw_rgba32f,
            metadata_out=args.radial_metadata_json,
            params=MetricParams(M=args.mass, a=args.spin),
            r_max=args.r_max,
            samples=args.radius_samples,
            prograde=not args.retrograde,
            temperature_scale_k=args.temperature_scale_k,
        )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
