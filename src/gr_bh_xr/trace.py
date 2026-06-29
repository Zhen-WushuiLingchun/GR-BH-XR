"""Trace a single Phase 1 reference ray and print diagnostics as JSON."""

from __future__ import annotations

import argparse
import dataclasses
import json
import math

from .geodesic import trace_ray
from .types import CameraConfig, MetricParams, TraceConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, default=0.0, help="Dimensionless Kerr spin a/M.")
    parser.add_argument("--mass", type=float, default=1.0, help="Black-hole mass M.")
    parser.add_argument("--inclination-deg", type=float, default=90.0, help="Observer theta in degrees.")
    parser.add_argument("--r-obs", type=float, default=100.0, help="Observer Boyer-Lindquist radius.")
    parser.add_argument("--alpha", type=float, required=True, help="Bardeen screen alpha.")
    parser.add_argument("--beta", type=float, required=True, help="Bardeen screen beta.")
    parser.add_argument("--max-lambda", type=float, default=800.0)
    parser.add_argument("--r-escape", type=float, default=None)
    parser.add_argument("--stop-on-disk", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    params = MetricParams(M=args.mass, a=args.spin * args.mass)
    camera = CameraConfig(
        r_obs=args.r_obs,
        theta_obs=math.radians(args.inclination_deg),
        alpha=args.alpha,
        beta=args.beta,
    )
    config = TraceConfig(
        max_lambda=args.max_lambda,
        r_escape=args.r_escape,
        stop_on_disk=args.stop_on_disk,
    )
    diagnostics = trace_ray(params, camera, config)
    print(json.dumps(dataclasses.asdict(diagnostics), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
