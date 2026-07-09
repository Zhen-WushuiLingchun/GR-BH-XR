"""Generate CPU blackbody color LUT assets for thin-disk visual shaders."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .disk_spectrum import write_blackbody_lut_npz


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--temperature-min-k", type=float, default=1000.0)
    parser.add_argument("--temperature-max-k", type=float, default=40000.0)
    parser.add_argument("--samples", type=int, default=256)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = write_blackbody_lut_npz(
        args.out,
        temperature_min_k=args.temperature_min_k,
        temperature_max_k=args.temperature_max_k,
        samples=args.samples,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
