"""Generate an (r, theta) grid of full-sky transfer cubemaps for near-horizon roaming.

Each keyframe is an independent finite-radius static-observer full-sky transfer
map (same contract as ``generate_transfer_cubemap``). The runtime binds the
keyframe nearest in (log r_obs, theta), so the stack realizes a quasi-static
roam: the observer worldline is a sequence of momentarily static observers.

Azimuthal motion needs no keyframes at all. Kerr is axisymmetric and both
launchers start the ray at ``phi = 0`` at the observer, so every recorded
azimuth is already relative to the observer and orbiting in phi is an exact
rigid rotation of the map basis about the spin axis. That exactness assumes the
disk model is itself axisymmetric; a consumer painting a non-axisymmetric
feature from ``phi_m`` must add the observer azimuth back.

No kinematic aberration between keyframes is modeled: this is a quasi-static
sequence, not a boosted worldline. The rain-frame descent path is the separate
construction that does model the falling observer's aberration.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

from gr_bh_xr.gpu.generate_transfer_cubemap import (
    DEFAULT_DISK_COVERAGE_SUBSAMPLES,
    DEFAULT_POLAR_BAND_THRESHOLD,
    generate_transfer_cubemap,
)
from gr_bh_xr.gpu.trace import GpuTraceConfig
from gr_bh_xr.types import MetricParams, TraceConfig

ROAM_KEYFRAMES_SCHEMA = "gr-bh-xr.task7.roam_keyframes.v2"

# Escape radius floor. The legacy `2 * r_obs` rule is not asymptotic for a
# near-horizon observer: measured escape-direction extraction error at
# r_obs = 2.5M is 6.7 deg mean / 22.8 deg max, dropping below 0.35 deg once
# r_escape >= 20M and reaching its floor by 50M. 200M is deliberately
# conservative.
DEFAULT_R_ESCAPE_MIN = 200.0

# Validated roam envelope. These are the rows the committed tests exercise, NOT
# a measured failure boundary: a full-sky sweep at r_obs = 2.5M and 6M shows at
# most 1 invalid texel of 3456 anywhere in theta = 2..178 deg, with no cliff at
# either end and a non-monotonic invalid count that tracks which texel happens
# to land on the polar axis rather than any degradation in theta. Widen this
# only together with a committed near-polar keyframe artifact.
#
# Note in particular that this envelope is NOT the `gpu.preview` [20, 160]
# envelope. That one is about the Bardeen alpha/beta screen map, whose
# 1/sin(theta_obs) factor genuinely degrades near the poles. This generator
# reaches the tracer through `initial_state_direction`, which builds the tetrad
# from a Unity unit vector and never evaluates that screen map, so the Bardeen
# rationale does not apply here.
ROAM_THETA_MIN_DEG = 30.0
ROAM_THETA_MAX_DEG = 150.0
DEFAULT_THETA_LIST_DEG = (30.0, 60.0, 90.0, 120.0, 150.0)


def ergosphere_radius(params: MetricParams, theta: float) -> float:
    """Outer ergosurface `r_E(theta) = M + sqrt(M^2 - a^2 cos^2 theta)`.

    This is the `+` root of `g_tt = 0`, so `g_tt < 0` exactly for `r > r_E`.
    `|a| < M` is enforced by `MetricParams`, so the root is always real.
    """

    cos_theta = math.cos(theta)
    discriminant = params.M * params.M - params.a * params.a * cos_theta * cos_theta
    return params.M + math.sqrt(discriminant)


def roam_radius_schedule(r_max: float, r_min: float, count: int) -> list[float]:
    """Log-spaced observer radii from `r_max` down to `r_min` inclusive.

    Radii are geometric code lengths, equal to `r/M` only when `M = 1`.
    """

    if count < 2:
        raise ValueError("Roam schedule needs at least two keyframes.")
    if r_min <= 0.0 or r_max <= r_min:
        raise ValueError("Roam schedule requires 0 < r_min < r_max.")
    log_max = math.log(r_max)
    log_min = math.log(r_min)
    return [
        math.exp(log_max + (log_min - log_max) * index / (count - 1))
        for index in range(count)
    ]


def validate_theta_rows(theta_list_deg: list[float]) -> list[float]:
    """Theta rows must be strictly increasing and inside the validated envelope."""

    if len(theta_list_deg) < 1:
        raise ValueError("At least one theta row is required.")
    for theta in theta_list_deg:
        if not (ROAM_THETA_MIN_DEG <= theta <= ROAM_THETA_MAX_DEG):
            raise ValueError(
                f"theta = {theta} deg is outside the validated roam envelope "
                f"[{ROAM_THETA_MIN_DEG}, {ROAM_THETA_MAX_DEG}] deg. That bound is "
                "the tested grid, not a known failure boundary; widen it only "
                "together with a committed near-polar keyframe artifact."
            )
    if sorted(theta_list_deg) != list(theta_list_deg):
        raise ValueError("theta rows must be sorted ascending.")
    if len(set(theta_list_deg)) != len(theta_list_deg):
        raise ValueError("theta rows must be unique.")
    return list(theta_list_deg)


def validate_static_observer_radii(
    params: MetricParams,
    inclination_deg: float,
    radii: list[float],
    margin: float | None = None,
) -> float:
    """Every keyframe radius must sit outside the ergosphere at the observer's theta.

    The GPU launcher builds a *static* observer tetrad (u along d/dt), which
    only exists where `g_tt < 0`. Returns the ergosphere radius at the observer
    polar angle for the manifest.

    `margin` defaults to `0.1 * M` rather than a bare `0.1` so the admitted
    worst-case tetrad boost `1 / sqrt(-g_tt)` is scale invariant: with an
    absolute margin it would be 4.58 at `M = 1` but 14.2 at `M = 10`.
    """

    if margin is None:
        margin = 0.1 * params.M
    theta = math.radians(inclination_deg)
    r_ergo = ergosphere_radius(params, theta)
    r_min = min(radii)
    if r_min <= r_ergo + margin:
        raise ValueError(
            f"Static observer tetrad undefined near/inside ergosphere: "
            f"min radius {r_min:.4f} vs ergosphere {r_ergo:.4f} at "
            f"inclination {inclination_deg:.1f} deg (margin {margin}, "
            f"geometric length with M = {params.M})."
        )
    return r_ergo


def capture_monotonicity_tolerance(total_pixels: int) -> float:
    """Allowed decrease in capture solid-angle fraction between adjacent radii.

    The capture measure is a discretized boundary, so its quantization noise
    scales as the boundary length over the texel count. At the outer keyframes
    the per-step signal is comparable to that noise, and a strict comparison
    turns an expensive multi-hour grid into a spurious failure. This tolerance
    is deliberately far below the physical growth in the near-horizon rows
    where the gate actually has to bite.
    """

    if total_pixels <= 0:
        raise ValueError("total_pixels must be positive.")
    return 3.0 / math.sqrt(float(total_pixels))


def generate_roam_keyframes(
    *,
    params: MetricParams,
    theta_list_deg: list[float],
    face_size: int,
    out_dir: Path | str,
    r_max: float,
    r_min: float,
    keyframe_count: int,
    step_size: float,
    steps: int,
    horizon_eps: float,
    chunk_size: int,
    disk_coverage_subsamples: int = DEFAULT_DISK_COVERAGE_SUBSAMPLES,
    r_escape_min: float = DEFAULT_R_ESCAPE_MIN,
    polar_band_threshold: float = DEFAULT_POLAR_BAND_THRESHOLD,
    command: str = "",
) -> dict[str, Any]:
    """Generate the (theta x radius) keyframe grid plus a roam manifest JSON."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    theta_rows = validate_theta_rows(theta_list_deg)
    radii = roam_radius_schedule(r_max, r_min, keyframe_count)
    # Validate the whole grid before spending GPU time on any keyframe.
    ergo_by_row = [
        validate_static_observer_radii(params, theta_deg, radii) for theta_deg in theta_rows
    ]
    tolerance = capture_monotonicity_tolerance(face_size * face_size * 6)

    keyframes: list[dict[str, Any]] = []
    for theta_index, theta_deg in enumerate(theta_rows):
        previous_capture = -1.0
        for radius_index, r_obs in enumerate(radii):
            keyframe_dir = out_dir / f"kf_t{theta_index:02d}_r{radius_index:02d}"
            started = time.perf_counter()
            metadata = generate_transfer_cubemap(
                params=params,
                inclination_deg=theta_deg,
                face_size=face_size,
                out_dir=keyframe_dir,
                r_obs=r_obs,
                step_size=step_size,
                steps=steps,
                horizon_eps=horizon_eps,
                chunk_size=chunk_size,
                disk_coverage_subsamples=disk_coverage_subsamples,
                r_escape_min=r_escape_min,
                polar_band_threshold=polar_band_threshold,
                command=command,
            )
            elapsed = time.perf_counter() - started
            # Physical monotonicity gate per theta row: the shadow solid angle
            # seen by a static observer grows as the observer approaches. Use
            # the solid-angle measure, not the texel count, because cube texels
            # do not subtend equal solid angle.
            capture = float(metadata["captureSolidAngleFraction"])
            if capture < previous_capture - tolerance:
                raise ValueError(
                    f"Shadow capture solid-angle fraction decreased from "
                    f"{previous_capture:.6f} to {capture:.6f} between radii "
                    f"{radii[radius_index - 1]:.4f} and {r_obs:.4f} at "
                    f"theta = {theta_deg} deg (tolerance {tolerance:.2e}); "
                    "keyframe grid is inconsistent."
                )
            previous_capture = capture
            keyframes.append(
                {
                    "dir": keyframe_dir.name,
                    "thetaIndex": theta_index,
                    "radiusIndex": radius_index,
                    "theta_deg": theta_deg,
                    "r_obs": r_obs,
                    "captureSolidAngleFraction": capture,
                    "rawCaptureTexelFraction": (
                        int(metadata["eventCounts"]["capture"]) / int(metadata["totalPixels"])
                    ),
                    "skyBlueshift": float(metadata["observer"]["skyBlueshift"]),
                    "validEscapePixels": int(metadata["validEscapePixels"]),
                    "retracedTexels": int(metadata["stages"]["invalidRetrace"]["texels"]),
                    "inpaintedTexels": int(metadata["stages"]["invalidInpaint"]["texels"]),
                    "polarBandTexels": int(metadata["polarBand"]["texels"]),
                    "eventCounts": metadata["eventCounts"],
                    "generationSeconds": elapsed,
                }
            )
            print(
                f"roam keyframe theta={theta_deg:.0f} deg "
                f"{radius_index + 1}/{keyframe_count}: r_obs={r_obs:.4f} "
                f"captureSolidAngle={capture:.6f} "
                f"skyBlueshift={keyframes[-1]['skyBlueshift']:.4f} "
                f"elapsed={elapsed:.1f}s",
                flush=True,
            )

    manifest = {
        "schema": ROAM_KEYFRAMES_SCHEMA,
        "generationCommand": command,
        "faceSize": face_size,
        "metric": {"M": params.M, "a": params.a, "aOverM": params.a / params.M},
        "observer": {
            "tetrad": "finite-radius static observer per keyframe; Unity +z is radially inward",
            "ergosphereRadiusByRow": ergo_by_row,
        },
        "units": {
            "system": "geometric G = c = 1; radii are code lengths, r/M only when M = 1",
            "radiiM": "geometric length (same unit as M)",
            "ergosphereRadiusByRow": "geometric length (same unit as M)",
            "thetaDegrees": "deg",
            "r_escape_min": "geometric length (same unit as M)",
            "polar_band_threshold": "rad, in min(theta, pi - theta)",
            "lambda_budget": "geometric length of affine parameter",
            "captureSolidAngleFraction": "dimensionless fraction of 4 pi",
        },
        "radiusSpacing": "log",
        "radiiM": radii,
        "thetaDegrees": theta_rows,
        "thetaEnvelopeDeg": [ROAM_THETA_MIN_DEG, ROAM_THETA_MAX_DEG],
        "gridOrder": "row-major: index = thetaIndex * len(radiiM) + radiusIndex",
        "captureMonotonicityTolerance": tolerance,
        "integration": {
            "step_size": step_size,
            "steps": steps,
            "lambda_budget": step_size * steps,
            "horizon_eps": horizon_eps,
            "r_escape_min": r_escape_min,
            "polar_band_threshold": polar_band_threshold,
        },
        "locomotionNote": (
            "Quasi-static roam grid: each keyframe is an independent "
            "static-observer full-sky transfer map, and the runtime binds the "
            "keyframe nearest in (log r_obs, theta). Azimuthal motion is exact "
            "by axisymmetry (a rigid rotation of the map basis about the spin "
            "axis), provided the disk model is itself axisymmetric. No "
            "kinematic aberration between keyframes is modeled: this is a "
            "quasi-static sequence, not a boosted worldline."
        ),
        "keyframes": keyframes,
    }
    manifest_path = out_dir / "roam_keyframes_metadata.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf8")
    return manifest


def _parse_theta_list(raw: str) -> list[float]:
    return [float(part) for part in raw.split(",") if part.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True, help="a / M, dimensionless.")
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument(
        "--theta-list-deg",
        type=str,
        default=",".join(str(v) for v in DEFAULT_THETA_LIST_DEG),
        help="Comma-separated observer polar angles in degrees (grid rows).",
    )
    parser.add_argument("--face-size", type=int, default=512)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--r-max", type=float, default=100.0, help="Geometric length, not r/M."
    )
    parser.add_argument(
        "--r-min", type=float, default=2.5, help="Geometric length, not r/M."
    )
    parser.add_argument("--keyframes", type=int, default=12)
    parser.add_argument("--step-size", type=float, default=GpuTraceConfig.step_size)
    parser.add_argument("--steps", type=int, default=28000)
    parser.add_argument("--horizon-eps", type=float, default=TraceConfig.horizon_eps)
    parser.add_argument("--chunk-size", type=int, default=262144)
    parser.add_argument("--disk-coverage-subsamples", type=int, default=DEFAULT_DISK_COVERAGE_SUBSAMPLES)
    parser.add_argument("--r-escape-min", type=float, default=DEFAULT_R_ESCAPE_MIN)
    parser.add_argument("--polar-band-threshold", type=float, default=DEFAULT_POLAR_BAND_THRESHOLD)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest = generate_roam_keyframes(
        params=MetricParams(M=args.mass, a=args.spin * args.mass),
        theta_list_deg=_parse_theta_list(args.theta_list_deg),
        face_size=args.face_size,
        out_dir=args.out_dir,
        r_max=args.r_max,
        r_min=args.r_min,
        keyframe_count=args.keyframes,
        step_size=args.step_size,
        steps=args.steps,
        horizon_eps=args.horizon_eps,
        chunk_size=args.chunk_size,
        disk_coverage_subsamples=args.disk_coverage_subsamples,
        r_escape_min=args.r_escape_min,
        polar_band_threshold=args.polar_band_threshold,
        command=" ".join(sys.argv),
    )
    print(
        json.dumps(
            {k: manifest[k] for k in ("schema", "radiiM", "thetaDegrees", "faceSize")},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
