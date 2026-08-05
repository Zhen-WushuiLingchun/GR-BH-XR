"""Generate rain-frame descent keyframes through the outer horizon.

Each keyframe is a full-sky transfer map for the *rain* observer (Doran E=1,
L=0, Q=0 free fall from rest at infinity) at a sampled point of the actual
infall worldline, traced in the Cartesian ingoing Kerr-Schild chart, which is
regular at the outer horizon.

Images are built by tracing PAST-directed rays: inside the horizon the future
cone points inward, so the view is the history of the light that fell in. Rays
that exhaust the affine budget asymptoting the past horizon are physical
darkness (the pre-collapse region), classified as capture rather than as solver
failures.

The rain frame makes the kinematic aberration and Doppler of the falling
observer explicit: the launcher normalizes `-k.u = 1` for the physical photon,
and the per-texel observer-side factor is analytic,

    E_inf(d) = w + dot(d, xyz),   eInf = [-et_phi, -et_theta, -et_r, -u_t]

with `d` the Unity local view direction. Observed sky and disk quantities scale
by `1 / E_inf`.

Ray validity is decided by the Hamiltonian residual `h_max_abs`, which the
tracer already computes and which is exactly zero for a true null geodesic.
That is a first-principles criterion, observer-radius independent and spin
independent; see `validation/descent_keyframes/README.md` for why the earlier
`min_r` / `lambda_end` heuristics were replaced.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np

from gr_bh_xr.disk import isco_radius
from gr_bh_xr.geodesic_ks import bl_to_ks_phi_shift
from gr_bh_xr.gpu.codes import SCHEMA_EVENT_CODES, SCHEMA_FAILURE_CODES
from gr_bh_xr.gpu.generate_transfer_cubemap import (
    UNITY_CUBE_FACES,
    _bh_to_unity,
    _face_directions,
    _premultiply_disk_samples,
)
from gr_bh_xr.gpu.trace import event_to_rgba8
from gr_bh_xr.gpu.trace_ks import KsGpuTraceConfig, trace_ks_states
from gr_bh_xr.metric import horizon_radius
from gr_bh_xr.metric_ks import ks_metric
from gr_bh_xr.observers import integrate_rain_worldline_ks, kerr_rain_tetrad_ks
from gr_bh_xr.types import MetricParams
from gr_bh_xr.xr.export_unity_textures import unity_basis_from_inclination

DESCENT_SCHEMA = "gr-bh-xr.task8.descent_keyframes.v1"
DISK_ORDER_COUNT = 2

# A true null geodesic has H = 0 identically. Past-directed rays that punch
# through the past horizon are ejected by the backward exp(kappa lambda)
# instability with chaotic directions, and their Hamiltonian residual explodes
# (measured up to 1.7e10). This threshold separates them: on healthy exterior
# keyframes it reproduces the older min_r heuristic set-for-set on all 4096
# sampled texels, while on interior keyframes it recovers 644-799 garbage
# texels per keyframe that the heuristic kept.
DEFAULT_HAMILTONIAN_MAX = 1.0e-2
# Refuse to ship a keyframe whose sky is almost entirely rejected. The healthy
# range measured across a full descent is 0.79-0.98.
MIN_ESCAPE_FRACTION = 0.25


def descent_radius_schedule(
    params: MetricParams, r_start: float, r_min: float, count: int
) -> list[float]:
    """Log-spaced KS radii from `r_start` to `r_min`, nudged off the exact horizon.

    The algebraic rain construction is well conditioned on both sides of `r_+`
    but the surrounding machinery is not: a keyframe sitting exactly on the
    horizon has no clean interior/exterior classification. A small nudge keeps
    every sample in the regular region on one side or the other.

    All margins scale with `M`; an absolute margin would be a ~10x weaker
    safety buffer in geometric units at `M = 10` than at `M = 1`.
    """

    if count < 2:
        raise ValueError("Descent schedule needs at least two keyframes.")
    if r_min <= 0.0 or r_start <= r_min:
        raise ValueError("Descent schedule requires 0 < r_min < r_start.")
    r_plus = horizon_radius(params)
    r_minus = params.M - math.sqrt(max(params.M**2 - params.a**2, 0.0))
    if r_min <= r_minus + 0.1 * params.M:
        raise ValueError(
            "r_min must stay above the inner horizon (mass-inflation region): "
            f"r_min = {r_min} vs r_minus + 0.1 M = {r_minus + 0.1 * params.M}."
        )
    nudge = 5.0e-3 * params.M
    radii = [
        math.exp(math.log(r_start) + (math.log(r_min) - math.log(r_start)) * i / (count - 1))
        for i in range(count)
    ]
    # Pin the endpoints exactly: exp(log(r)) can overshoot r by an ulp, and the
    # worldline sampler rightly refuses a first target above r_start.
    radii[0] = r_start
    radii[-1] = r_min
    nudged = []
    for radius in radii:
        if abs(radius - r_plus) < nudge:
            radius = r_plus - nudge if radius <= r_plus else r_plus + nudge
        nudged.append(radius)
    # The nudge can collide two adjacent samples onto the same value, which
    # would silently request duplicate worldline targets. Fail loudly instead.
    for previous, current in zip(nudged, nudged[1:]):
        if current >= previous:
            raise ValueError(
                "Horizon nudge collapsed two adjacent descent radii "
                f"({previous}, {current}); reduce --keyframes or move r_min."
            )
    return nudged


def _ks_radius_batch(a: float, xyz: np.ndarray) -> np.ndarray:
    a2 = a * a
    rho2 = np.sum(xyz * xyz, axis=1)
    q = rho2 - a2
    r2 = 0.5 * (q + np.sqrt(q * q + 4.0 * a2 * xyz[:, 2] * xyz[:, 2]))
    return np.sqrt(np.maximum(r2, 0.0))


def batch_escape_directions(
    params: MetricParams,
    final_x: np.ndarray,
    final_p: np.ndarray,
    escaped: np.ndarray,
    *,
    apply_chart_rotation: bool = True,
) -> np.ndarray:
    """Vectorized asymptotic direction extraction at the escape endpoint.

    Raises the Kerr-Schild momentum with `g^{mu nu} = eta^{mu nu} - 2H l^mu
    l^nu`, then rotates the spatial part by the analytic azimuth offset between
    the Kerr-Schild Cartesian frame and the BH Cartesian frame at the endpoint
    radius, `delta = atan2(a, r) + bl_to_ks_phi_shift(r)`.

    The rotation is applied as `+delta`. That sign matters and is not obvious:
    the momentum-direction azimuth of an outgoing ray is
    `phi_bl + shift + arctan(eps r / (1 - eps a))` with `eps = a / Delta`, which
    is `phi_bl + aM/r^2` to `O(r^-2)`, whereas `delta` itself is `-aM/r^2`. The
    position-space offset and the momentum-direction offset carry opposite
    signs, so rotating by `-delta` is worse than applying no rotation at all.

    `apply_chart_rotation=False` returns the unrotated directions; the
    validation CLI uses it to assert the rotation is an improvement, which is
    the only formulation that actually discriminates the sign.
    """

    dirs = np.full((final_x.shape[0], 3), np.nan, dtype=np.float64)
    if not np.any(escaped):
        return dirs
    xyz = final_x[escaped, 1:4].astype(np.float64)
    p = final_p[escaped].astype(np.float64)
    r = _ks_radius_batch(params.a, xyz)
    a2 = params.a * params.a
    den = r * r + a2
    h_den = r**4 + a2 * xyz[:, 2] * xyz[:, 2]
    h = params.M * r**3 / h_den
    l_cov = np.stack(
        [
            np.ones_like(r),
            (r * xyz[:, 0] + params.a * xyz[:, 1]) / den,
            (r * xyz[:, 1] - params.a * xyz[:, 0]) / den,
            xyz[:, 2] / r,
        ],
        axis=1,
    )
    # eta^{-1} p with signature (-,+,+,+); l^mu = eta^{-1} l_cov.
    eta_p = p.copy()
    eta_p[:, 0] = -eta_p[:, 0]
    l_contra = l_cov.copy()
    l_contra[:, 0] = -l_contra[:, 0]
    l_dot_p = np.sum(l_contra * p, axis=1)
    u = eta_p - 2.0 * h[:, None] * l_dot_p[:, None] * l_contra
    spatial = u[:, 1:4]
    norm = np.linalg.norm(spatial, axis=1, keepdims=True)
    # A degenerate ray would otherwise produce inf/NaN silently; leave those as
    # NaN so the caller's finiteness mask counts them.
    good = norm[:, 0] > 0.0
    spatial = np.divide(spatial, norm, out=np.full_like(spatial, np.nan), where=norm > 0.0)
    if apply_chart_rotation:
        shift = np.array([bl_to_ks_phi_shift(params, float(value)) for value in r])
        delta = np.arctan2(params.a, r) + shift
        cos_d = np.cos(delta)
        sin_d = np.sin(delta)
        spatial = np.stack(
            [
                cos_d * spatial[:, 0] - sin_d * spatial[:, 1],
                sin_d * spatial[:, 0] + cos_d * spatial[:, 1],
                spatial[:, 2],
            ],
            axis=1,
        )
    spatial[~good] = np.nan
    dirs[escaped] = spatial
    return dirs


def _phi_tilde(a: float, position: np.ndarray) -> float:
    r = float(_ks_radius_batch(a, position[None, :])[0])
    return math.atan2(
        float(position[1]) * r - a * float(position[0]),
        r * float(position[0]) + a * float(position[1]),
    )


def _unwrap_azimuth(value_deg: float, previous_deg: float) -> float:
    """Unwrap a monotonically drifting azimuth in either direction.

    The ingoing-KS chart azimuth of a prograde rain worldline drifts
    *negative*: `dphi_ks/dtau = (a/Delta)(2M/r + dr/dtau)` and
    `|dr/dtau| > 2M/r` throughout, so the chart twist beats the
    Boyer-Lindquist frame dragging (which is itself positive). A one-sided
    unwrap built for increasing azimuth silently fails on this sequence.
    """

    while value_deg - previous_deg > 180.0:
        value_deg -= 360.0
    while value_deg - previous_deg < -180.0:
        value_deg += 360.0
    return value_deg


def generate_descent_keyframes(
    *,
    params: MetricParams,
    theta_list_deg: list[float],
    face_size: int,
    out_dir: Path | str,
    r_start: float,
    r_min: float,
    keyframe_count: int,
    r_escape: float = 200.0,
    step_size: float = 0.01,
    steps: int = 60000,
    max_lambda: float = 1500.0,
    chunk_size: int = 262144,
    hamiltonian_max: float = DEFAULT_HAMILTONIAN_MAX,
    min_escape_fraction: float = MIN_ESCAPE_FRACTION,
    command: str = "",
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    radii = descent_radius_schedule(params, r_start, r_min, keyframe_count)
    escape_code = SCHEMA_EVENT_CODES["escape"]
    capture_code = SCHEMA_EVENT_CODES["capture"]
    invalid_code = SCHEMA_EVENT_CODES["invalid"]
    budget_code = SCHEMA_FAILURE_CODES["unclassified_max_lambda"]
    r_plus = horizon_radius(params)

    keyframes: list[dict[str, Any]] = []
    keyframe_dirs: list[str] = []
    for theta_index, theta_deg in enumerate(theta_list_deg):
        theta = math.radians(theta_deg)
        basis = unity_basis_from_inclination(theta_deg)
        positions = integrate_rain_worldline_ks(
            params, r_start=r_start, theta=theta, r_samples=np.asarray(radii)
        )
        # Fail closed: the manifest pairs radii[i] with positions[i], so a
        # short list would silently mislabel every later keyframe.
        if len(positions) != len(radii):
            raise RuntimeError(
                f"Rain worldline returned {len(positions)} positions for "
                f"{len(radii)} requested radii."
            )
        azimuth_zero = _phi_tilde(params.a, positions[0])
        previous_azimuth = 0.0
        for radius_index, position in enumerate(positions):
            started = time.perf_counter()
            keyframe_dir = out_dir / f"kf_t{theta_index:02d}_r{radius_index:02d}"
            keyframe_dir.mkdir(parents=True, exist_ok=True)
            tetrad = kerr_rain_tetrad_ks(params, position)
            g_obs = ks_metric(params, position)
            # Per-texel observer factor. k = u - n^i e_i for the physical
            # photon, so E_inf = -k_t = -u_t + n^i (e_i)_t, and with
            # (n_r, n_theta, n_phi) = (-d.z, -d.y, -d.x) this is
            # w + dot(d, xyz) with the packing below.
            u_t = float(g_obs[0] @ tetrad.e_time)
            et_r = float(g_obs[0] @ tetrad.e_r)
            et_theta = float(g_obs[0] @ tetrad.e_theta)
            et_phi = float(g_obs[0] @ tetrad.e_phi)

            radius = radii[radius_index]
            is_interior = radius < r_plus
            pixels_per_face = face_size * face_size
            event_cube = np.zeros((6, face_size, face_size, 4), dtype=np.uint8)
            dir_cube = np.zeros((6, face_size, face_size, 4), dtype=np.float32)
            disk_transfer = np.zeros((DISK_ORDER_COUNT, 6, face_size, face_size, 4), dtype=np.float16)
            disk_redshift = np.zeros_like(disk_transfer)
            counts = {
                "escape": 0,
                "physicalCapture": 0,
                "darkPastHorizon": 0,
                "hamiltonianRejected": 0,
                "otherFailure": 0,
                "nonFiniteDirection": 0,
                "diskCrossingsDropped": 0,
            }

            config = KsGpuTraceConfig(
                params=params,
                step_size=step_size,
                steps=steps,
                max_lambda=max_lambda,
                r_escape=r_escape,
                disk_r_in=isco_radius(params),
                disk_r_out=30.0,
                time_orientation=-1.0,
                # Interior observers sit below the default capture radius, so
                # the capture surface is pushed down to the inner-horizon guard
                # r_minus + min(0.05 M, 0.25 gap). Any horizon_eps above about
                # 0.82 M saturates there for a = 0.9; 1.0 is that saturated
                # setting, applied uniformly so exterior and interior keyframes
                # share one capture surface.
                horizon_eps=1.0,
            )
            for face_index, face_name in enumerate(UNITY_CUBE_FACES):
                directions = _face_directions(face_name, face_size).astype(np.float64)
                # Past-directed launcher: an arriving photon along look
                # direction d has spatial momentum -n in the rain frame, so its
                # history ray is q = -u + n.e in the static-map n(d) sign
                # convention.
                n_r = -directions[:, 2]
                n_theta = -directions[:, 1]
                n_phi = -directions[:, 0]
                q = (
                    -tetrad.e_time[None, :]
                    + n_r[:, None] * tetrad.e_r[None, :]
                    + n_theta[:, None] * tetrad.e_theta[None, :]
                    + n_phi[:, None] * tetrad.e_phi[None, :]
                )
                p = q @ g_obs.T
                packed = np.zeros((directions.shape[0], 8), dtype=np.float32)
                packed[:, 1:4] = position[None, :]
                packed[:, 4:8] = p
                face_event = np.zeros((pixels_per_face,), dtype=np.int16)
                face_failure = np.zeros((pixels_per_face,), dtype=np.int16)
                face_dir = np.zeros((pixels_per_face, 4), dtype=np.float32)
                face_disk = np.zeros((DISK_ORDER_COUNT, pixels_per_face, 4), dtype=np.float32)
                for start in range(0, pixels_per_face, chunk_size):
                    end = min(start + chunk_size, pixels_per_face)
                    result = trace_ks_states(config, packed[start:end])
                    event = result["event_code"].astype(np.int16)
                    failure = result["failure_code"].astype(np.int16)
                    # Budget exhaustion asymptoting the past horizon is
                    # physical darkness, not a solver failure.
                    dark = (event == invalid_code) & (failure == budget_code)
                    counts["darkPastHorizon"] += int(np.count_nonzero(dark))
                    counts["otherFailure"] += int(
                        np.count_nonzero((event == invalid_code) & ~dark)
                    )
                    counts["physicalCapture"] += int(np.count_nonzero(event == capture_code))
                    event[event == invalid_code] = capture_code
                    failure[dark] = 0
                    # First-principles validity: H is identically zero for a
                    # null geodesic, so a large residual marks a ray the f32
                    # backward integration has destroyed. This replaces the
                    # earlier min_r / lambda_end heuristics, which blanked
                    # entire exterior keyframes whose own r_obs sat inside the
                    # min_r threshold and let interior garbage through.
                    rejected = (event == escape_code) & (
                        result["h_max_abs"] > hamiltonian_max
                    )
                    event[rejected] = capture_code
                    counts["hamiltonianRejected"] += int(np.count_nonzero(rejected))
                    counts["escape"] += int(np.count_nonzero(event == escape_code))
                    escaped = event == escape_code
                    dirs_bh = batch_escape_directions(
                        params, result["final_x"], result["final_p"], escaped
                    )
                    finite = np.all(np.isfinite(dirs_bh), axis=1)
                    counts["nonFiniteDirection"] += int(np.count_nonzero(escaped & ~finite))
                    valid = escaped & finite
                    dir_unity = _bh_to_unity(
                        np.where(np.isfinite(dirs_bh), dirs_bh, 0.0), valid, basis
                    )
                    seg = np.zeros((end - start, 4), dtype=np.float32)
                    seg[valid, :3] = dir_unity[valid]
                    seg[valid, 3] = 1.0
                    face_event[start:end] = event
                    face_failure[start:end] = failure
                    face_dir[start:end] = seg
                    for order in range(DISK_ORDER_COUNT):
                        disk_r = result["disk_r_m"][:, order]
                        disk_phi = result["disk_phi_m"][:, order]
                        disk_g = result["disk_g_m"][:, order]
                        recorded = np.isfinite(disk_r) & (disk_r > 0.0)
                        disk_valid = (
                            recorded
                            & np.isfinite(disk_phi)
                            & np.isfinite(disk_g)
                            & (disk_g > 0.0)
                        )
                        # A crossing the tracer recorded but whose redshift was
                        # rejected renders no disk; count it rather than
                        # dropping it silently.
                        counts["diskCrossingsDropped"] += int(
                            np.count_nonzero(recorded & ~disk_valid)
                        )
                        disk_packed = np.zeros((end - start, 4), dtype=np.float32)
                        disk_packed[disk_valid, 0] = disk_r[disk_valid]
                        disk_packed[disk_valid, 1] = np.sin(disk_phi[disk_valid])
                        disk_packed[disk_valid, 2] = np.cos(disk_phi[disk_valid])
                        disk_packed[disk_valid, 3] = disk_g[disk_valid]
                        face_disk[order, start:end] = disk_packed
                transfer, redshift, _coverage = _premultiply_disk_samples(face_disk)
                event_cube[face_index] = event_to_rgba8(
                    face_event.reshape((face_size, face_size)),
                    face_failure.reshape((face_size, face_size)),
                )
                dir_cube[face_index] = face_dir.reshape((face_size, face_size, 4))
                for order in range(DISK_ORDER_COUNT):
                    disk_transfer[order, face_index] = transfer[order].reshape(
                        (face_size, face_size, 4)
                    )
                    disk_redshift[order, face_index] = redshift[order].reshape(
                        (face_size, face_size, 4)
                    )

            total_texels = 6 * pixels_per_face
            escape_fraction = counts["escape"] / total_texels
            # Fail closed: a keyframe whose sky is almost entirely rejected is
            # a blank frame, and previously shipped silently with escape = 0.
            if escape_fraction < min_escape_fraction:
                raise RuntimeError(
                    f"Descent keyframe theta={theta_deg} r={radius:.6f} kept only "
                    f"{escape_fraction:.4f} of the sky (minimum "
                    f"{min_escape_fraction}); refusing to ship a blank keyframe."
                )

            event_cube.tofile(keyframe_dir / "event_cube_rgba8.bytes")
            dir_cube.astype("<f4", copy=False).tofile(
                keyframe_dir / "escape_dir_unity_cube_rgba32f.bytes"
            )
            for order in range(DISK_ORDER_COUNT):
                disk_transfer[order].astype("<f2", copy=False).tofile(
                    keyframe_dir / f"disk_order{order}_transfer_cube_rgba16f.bytes"
                )
                disk_redshift[order].astype("<f2", copy=False).tofile(
                    keyframe_dir / f"disk_order{order}_redshift_cube_rgba16f.bytes"
                )

            azimuth_deg = _unwrap_azimuth(
                math.degrees(_phi_tilde(params.a, position) - azimuth_zero), previous_azimuth
            )
            previous_azimuth = azimuth_deg
            elapsed = time.perf_counter() - started
            entry = {
                "dir": keyframe_dir.name,
                "thetaIndex": theta_index,
                "radiusIndex": radius_index,
                "theta_deg": theta_deg,
                "r_obs": radius,
                "interior": bool(is_interior),
                "azimuthDeg": azimuth_deg,
                # Shader form E_inf(d) = w + dot(d, xyz).
                "eInf": [-et_phi, -et_theta, -et_r, -u_t],
                "escapeFraction": escape_fraction,
                "counts": dict(counts),
                "generationSeconds": elapsed,
            }
            keyframes.append(entry)
            keyframe_dirs.append(keyframe_dir.name)
            (keyframe_dir / "descent_keyframe_metadata.json").write_text(
                json.dumps(entry, indent=2, sort_keys=True), encoding="utf8"
            )
            print(
                f"descent theta={theta_deg:.0f} {radius_index + 1}/{keyframe_count}: "
                f"r={radius:.4f} az={azimuth_deg:+.1f} "
                f"escape={counts['escape']} ({escape_fraction:.3f}) "
                f"dark={counts['darkPastHorizon']} "
                f"hRejected={counts['hamiltonianRejected']} "
                f"fail={counts['otherFailure']} elapsed={elapsed:.1f}s",
                flush=True,
            )

    manifest = {
        "schema": DESCENT_SCHEMA,
        "generationCommand": command,
        "faceSize": face_size,
        "metric": {"M": params.M, "a": params.a, "aOverM": params.a / params.M},
        "thetaDegrees": list(theta_list_deg),
        "radiiM": radii,
        "gridOrder": "row-major: index = thetaIndex * len(radiiM) + radiusIndex",
        "keyframeDirs": keyframe_dirs,
        "units": {
            "system": "geometric G = c = 1; radii are code lengths, r/M only when M = 1",
            "radiiM": "geometric length (same unit as M)",
            "azimuthDeg": "deg, ingoing Kerr-Schild chart azimuth relative to the first keyframe",
            "eInf": "dimensionless observed/infinity frequency ratio coefficients",
            "hamiltonianMax": "dimensionless Hamiltonian residual rejection threshold",
        },
        "observer": {
            "tetrad": "Kerr rain frame (Doran E=1, L=0, Q=0), Cartesian Kerr-Schild chart",
            "orientation": "past-directed history tracing",
            "horizonRadius": r_plus,
            "aberrationNote": (
                "Kinematic aberration/Doppler of the falling frame is exact via "
                "the launcher; the per-texel observer factor is analytic, "
                "E_inf(d) = w + dot(d, xyz) with the stored eInf uniform "
                "(d = Unity local view direction, w = -u_t, xyz = negated "
                "tetrad covector t-components in (phi, theta, r) leg order). "
                "Observed sky and disk quantities scale by 1 / E_inf. The "
                "packing is gated by gr_bh_xr.gpu.validate_descent_frames; see "
                "that report for the measured agreement rather than a quoted "
                "constant."
            ),
            "tetradTransportNote": (
                "The rain tetrad is constructed algebraically at each sampled "
                "point, NOT parallel transported along the worldline. "
                "Consecutive keyframes therefore differ from a transported "
                "frame by a rotation this manifest does not record."
            ),
        },
        "validity": {
            "criterion": "hamiltonian residual",
            "hamiltonianMax": hamiltonian_max,
            "minEscapeFraction": min_escape_fraction,
            "note": (
                "H is identically zero for a null geodesic, so h_max_abs marks "
                "rays the f32 backward integration destroyed. This is "
                "observer-radius and spin independent, unlike the min_r and "
                "lambda_end heuristics it replaces."
            ),
        },
        "integration": {
            "step_size": step_size,
            "steps": steps,
            "max_lambda": max_lambda,
            "r_escape": r_escape,
        },
        "keyframes": keyframes,
    }
    (out_dir / "descent_keyframes_metadata.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf8"
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True, help="a / M, dimensionless.")
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--theta-list-deg", type=str, default="60,90")
    parser.add_argument("--face-size", type=int, default=512)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--r-start", type=float, default=9.0)
    parser.add_argument("--r-min", type=float, default=0.75)
    parser.add_argument("--keyframes", type=int, default=20)
    parser.add_argument("--r-escape", type=float, default=200.0)
    parser.add_argument("--step-size", type=float, default=0.01)
    parser.add_argument("--steps", type=int, default=60000)
    parser.add_argument("--max-lambda", type=float, default=1500.0)
    parser.add_argument("--chunk-size", type=int, default=262144)
    parser.add_argument("--hamiltonian-max", type=float, default=DEFAULT_HAMILTONIAN_MAX)
    parser.add_argument("--min-escape-fraction", type=float, default=MIN_ESCAPE_FRACTION)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest = generate_descent_keyframes(
        params=MetricParams(M=args.mass, a=args.spin * args.mass),
        theta_list_deg=[float(part) for part in args.theta_list_deg.split(",") if part.strip()],
        face_size=args.face_size,
        out_dir=args.out_dir,
        r_start=args.r_start,
        r_min=args.r_min,
        keyframe_count=args.keyframes,
        r_escape=args.r_escape,
        step_size=args.step_size,
        steps=args.steps,
        max_lambda=args.max_lambda,
        chunk_size=args.chunk_size,
        hamiltonian_max=args.hamiltonian_max,
        min_escape_fraction=args.min_escape_fraction,
        command=" ".join(sys.argv),
    )
    print(json.dumps({k: manifest[k] for k in ("schema", "radiiM", "thetaDegrees")}, indent=2))


if __name__ == "__main__":
    main()
