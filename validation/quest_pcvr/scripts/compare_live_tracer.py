"""Cross-check the Unity live compute tracer against the Python wgpu tracer.

Reads a ValidationDump directory (raw escape-direction / disk buffers plus the
metadata JSON carrying the exact observer tetrad the compute pass used),
re-traces a texel sample with `gr_bh_xr.gpu.trace_ks` from the same states,
and reports angular direction errors and disk (r, g) differences. This is the
same CPU/GPU cross-check pattern used for the Task 4 tracer gates.

Fail-closed contract
--------------------
Every numeric the two implementations must agree on is read from the dump's
metadata rather than hardcoded here. A constant written independently on both
sides is not a test of agreement, it is an assumption of it: the capture
surface was hardcoded on both sides and silently differed by 0.35 M in the
static case while the gate still reported perfect agreement.

The dump declares which stages it produced in `meta["stages"]`. Every declared
stage MUST be validated or the run fails; the required set additionally has to
be present unless it is explicitly waived on the command line. Previously each
stage was guarded by a bare `path.exists()` and a dump containing only the
three main buffers printed PASS.

Cross-worktree dependency: `batch_escape_directions` and the Kerr-Schild
disk-crossing extensions to `trace_ks` are owned by the Task 7-8 physics
worktree. This script cannot run on a branch that lacks them; the import below
fails loudly rather than degrading to a partial check.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from gr_bh_xr.geodesic_ks import bl_to_ks_phi_shift
from gr_bh_xr.gpu.generate_descent_keyframes import batch_escape_directions
from gr_bh_xr.gpu.generate_transfer_cubemap import _face_directions, _face_directions_from_uv
from gr_bh_xr.gpu.trace_ks import KsGpuTraceConfig, trace_ks_states
from gr_bh_xr.types import MetricParams
from gr_bh_xr.xr.export_unity_textures import unity_basis_from_inclination

# Stages the Unity ValidationDump is expected to emit. `main` is implicit in
# every dump; the rest are separately dispatched compute kernels, each of
# which shipped unvalidated at some point in this file's history.
REQUIRED_STAGES = ("main", "refine", "window", "windowRefine")

# Observer-basis probe tolerance, degrees. Not a taste value: the run asserts
# it is at least four times below the smallest separation between the accepted
# basis and every wrong-sign candidate over the whole probe grid, so a passing
# run cannot be a loose threshold accepting a sign error.
BASIS_PROBE_TOLERANCE_DEG = 1.0e-3
BASIS_PROBE_DISCRIMINATION_FACTOR = 4.0

# Floor on the texel sample that resolves the escaped-momentum rotation sign.
# The check used to be wrapped in `if np.any(...)`, so a dump that produced no
# comparable texel skipped the only sign gate in the file and still printed
# PASS.
MIN_CHART_SIGN_SAMPLES = 256


def horizon_radii(params: MetricParams) -> tuple[float, float]:
    root = math.sqrt(max(params.M * params.M - params.a * params.a, 0.0))
    return params.M + root, params.M - root


def accepted_observer_basis_bh(theta_deg: float, phi_bl: float) -> np.ndarray:
    """Accepted BH-frame observer basis at `(theta, phi_bl)`, rows right/up/forward.

    `unity_basis_from_inclination` is exactly this construction at
    `phi_bl = 0`: the observer direction is BL-SPHERICAL,
    `(sin th cos phi, sin th sin phi, cos th)`, `forward = -observer`, `up` is
    the spin-axis projection of forward and `right = up x forward`. Kerr
    axisymmetry makes the generalization a rigid rotation about the spin axis,
    which is asserted against `unity_basis_from_inclination` below rather than
    assumed.
    """

    theta = math.radians(float(theta_deg))
    observer = np.array(
        [math.sin(theta) * math.cos(phi_bl), math.sin(theta) * math.sin(phi_bl), math.cos(theta)],
        dtype=np.float64,
    )
    forward = -observer / np.linalg.norm(observer)
    spin = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    up = spin - float(np.dot(spin, forward)) * forward
    if np.linalg.norm(up) < 1.0e-10:
        fallback = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        up = fallback - float(np.dot(fallback, forward)) * forward
    up = up / np.linalg.norm(up)
    right = np.cross(up, forward)
    right = right / np.linalg.norm(right)
    up = np.cross(forward, right)
    return np.stack([right, up, forward], axis=0)


def ks_unrotated_observer_basis_bh(
    params: MetricParams, theta_deg: float, phi_bl: float, radius: float
) -> np.ndarray:
    """The rejected alternative: un-rotate the KS Cartesian POSITION by -delta.

    Correct in azimuth and wrong in polar angle - the KS embedding carries
    `sqrt(r^2 + a^2)` in the equatorial component, so the recovered polar angle
    is `atan2(sqrt(r^2 + a^2) sin th, r cos th)`. Kept here as a discrimination
    candidate so the probe tolerance is measured against it.
    """

    theta = math.radians(float(theta_deg))
    phi_ks = phi_bl + bl_to_ks_phi_shift(params, radius)
    sin_t = math.sin(theta)
    pos = np.array(
        [
            (radius * math.cos(phi_ks) - params.a * math.sin(phi_ks)) * sin_t,
            (radius * math.sin(phi_ks) + params.a * math.cos(phi_ks)) * sin_t,
            radius * math.cos(theta),
        ],
        dtype=np.float64,
    )
    delta = math.atan2(params.a, radius) + bl_to_ks_phi_shift(params, radius)
    cos_d, sin_d = math.cos(-delta), math.sin(-delta)
    pos_bh = np.array(
        [cos_d * pos[0] - sin_d * pos[1], sin_d * pos[0] + cos_d * pos[1], pos[2]],
        dtype=np.float64,
    )
    forward = -pos_bh / np.linalg.norm(pos_bh)
    spin = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    up = spin - float(np.dot(spin, forward)) * forward
    up = up / np.linalg.norm(up)
    right = np.cross(up, forward)
    right = right / np.linalg.norm(right)
    up = np.cross(forward, right)
    return np.stack([right, up, forward], axis=0)


def basis_separation_deg(left: np.ndarray, right: np.ndarray) -> float:
    """Largest per-leg angular separation between two bases, degrees."""

    dots = np.clip(np.sum(left * right, axis=1), -1.0, 1.0)
    return float(np.max(np.degrees(np.arccos(dots))))


def check_observer_basis_probes(params: MetricParams, probes: list) -> dict:
    """Gate the C# observer-position basis role, independently of the kernel.

    The traced directions in this dump use an identity `_Basis*Bh`, so nothing
    else here touches the runtime observer basis. Each probe carries the basis
    the runtime pass would build at `(r, azimuth, chart)`, produced by the same
    code; this compares it against the accepted mapping and, critically, also
    measures how far the WRONG-sign candidates sit, so the tolerance is proven
    discriminating rather than merely small.
    """

    if not probes:
        raise SystemExit(
            "dump is missing observerBasisProbes: the C# observer-position "
            "basis is the one escape-direction role this dump does not "
            "otherwise exercise, and a dump without it cannot gate its sign."
        )
    # Anchor the generalization: at phi_bl = 0 it must BE the accepted
    # function, not merely resemble it. Without this the reference could drift
    # and both sides of the comparison would move together.
    for theta_deg in sorted({float(probe["thetaDeg"]) for probe in probes}):
        accepted_zero = unity_basis_from_inclination(theta_deg)
        anchor = np.stack(
            [accepted_zero.right_bh, accepted_zero.up_bh, accepted_zero.forward_bh], axis=0
        )
        drift = basis_separation_deg(accepted_observer_basis_bh(theta_deg, 0.0), anchor)
        if drift > 1.0e-9:
            raise SystemExit(
                f"observer-basis reference drifted from unity_basis_from_inclination "
                f"at theta = {theta_deg} deg by {drift:.3e} deg; the gate's own "
                "reference is wrong."
            )

    worst_error = 0.0
    smallest_separation = float("inf")
    worst_probe = None
    for probe in probes:
        radius = float(probe["rM"])
        theta_deg = float(probe["thetaDeg"])
        azimuth = math.radians(float(probe["azimuthDeg"]))
        shift = bl_to_ks_phi_shift(params, radius)
        chart = str(probe["chart"])
        if chart == "ks":
            phi_bl = azimuth - shift
        elif chart == "bl":
            phi_bl = azimuth
        else:
            raise SystemExit(f"observerBasisProbes carries an unknown chart {chart!r}.")

        unity_basis = np.array(
            [probe["rightBh"], probe["upBh"], probe["forwardBh"]], dtype=np.float64
        )
        accepted = accepted_observer_basis_bh(theta_deg, phi_bl)
        error = basis_separation_deg(unity_basis, accepted)
        if error > worst_error:
            worst_error = error
            worst_probe = probe

        # Wrong-sign candidates. `+shift` is the momentum convention applied to
        # a position (only distinguishable on a KS-labelled probe, which is why
        # the probe grid carries both charts); the KS-position un-rotation is
        # the polar-angle mistake.
        candidates = [ks_unrotated_observer_basis_bh(params, theta_deg, phi_bl, radius)]
        if chart == "ks":
            candidates.append(accepted_observer_basis_bh(theta_deg, azimuth + shift))
        for candidate in candidates:
            separation = basis_separation_deg(accepted, candidate)
            smallest_separation = min(smallest_separation, separation)

    return {
        "probeCount": len(probes),
        "maxDeg": worst_error,
        "worstProbe": worst_probe,
        "smallestWrongSignSeparationDeg": smallest_separation,
        "toleranceDeg": BASIS_PROBE_TOLERANCE_DEG,
        "toleranceIsDiscriminating": bool(
            smallest_separation
            > BASIS_PROBE_DISCRIMINATION_FACTOR * BASIS_PROBE_TOLERANCE_DEG
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=4096)
    parser.add_argument(
        "--allow-missing-stage",
        action="append",
        default=[],
        choices=["refine", "window", "windowRefine"],
        help=(
            "Waive a required stage for a deliberately reduced dump. Repeatable. "
            "The waiver is recorded in the summary so a reduced run can never be "
            "mistaken for a full one."
        ),
    )
    args = parser.parse_args()

    meta = json.loads((args.dump_dir / "live_tracer_validation.json").read_text(encoding="utf8"))
    face = int(meta["faceSize"])
    params = MetricParams(M=float(meta["mass"]), a=float(meta["spin"]))
    position = np.asarray(meta["position"], dtype=np.float64)
    tetrad = {
        key: np.asarray(meta[key], dtype=np.float64)
        for key in ("tetradTime", "tetradR", "tetradTheta", "tetradPhi")
    }
    rain = bool(meta["rainFrame"])
    # Driven by the dump, not re-derived from `rain`, so a Unity-side change of
    # the emit/receive convention shows up as a mismatch instead of being
    # mirrored here.
    orientation = float(meta["timeOrientation"])
    if orientation != (-1.0 if rain else 1.0):
        raise SystemExit(
            f"timeOrientation {orientation} disagrees with rainFrame={rain}; "
            "the dump's own convention is inconsistent."
        )
    declared_stages = list(meta.get("stages", []))
    if "main" not in declared_stages:
        raise SystemExit(
            "dump metadata does not declare the 'main' stage; this dump predates "
            "the structured stage contract and cannot be accepted."
        )
    validated_stages: set[str] = set()

    unity_dir = np.fromfile(
        args.dump_dir / "live_escape_dir_rgba32f.bytes", dtype=np.float32
    ).reshape(6, face, face, 4)
    unity_disk = np.fromfile(
        args.dump_dir / "live_disk0_rgba32f.bytes", dtype=np.float32
    ).reshape(6, face, face, 4)
    unity_g = np.fromfile(
        args.dump_dir / "live_redshift0_rgba32f.bytes", dtype=np.float32
    ).reshape(6, face, face, 4)

    # Sample texels uniformly and rebuild the exact same launch states.
    rng = np.random.default_rng(20260714)
    total = 6 * face * face
    picks = rng.choice(total, size=min(args.samples, total), replace=False)
    faces = ["PositiveX", "NegativeX", "PositiveY", "NegativeY", "PositiveZ", "NegativeZ"]
    from gr_bh_xr.metric_ks import ks_metric

    g_obs = ks_metric(params, position)
    states = np.zeros((picks.size, 8), dtype=np.float32)
    unity_dirs = np.zeros((picks.size, 4), dtype=np.float64)
    unity_disks = np.zeros((picks.size, 4), dtype=np.float64)
    unity_gs = np.zeros(picks.size, dtype=np.float64)
    for row, flat in enumerate(picks):
        face_index = flat // (face * face)
        in_face = flat % (face * face)
        py = in_face // face
        px = in_face % face
        directions = _face_directions(faces[face_index], face).reshape(face, face, 3)
        d = directions[py, px]
        n_r, n_th, n_ph = -d[2], -d[1], -d[0]
        q = (
            orientation * tetrad["tetradTime"]
            + n_r * tetrad["tetradR"]
            + n_th * tetrad["tetradTheta"]
            + n_ph * tetrad["tetradPhi"]
        )
        p = g_obs @ q
        states[row, 1:4] = position
        states[row, 4:8] = p
        unity_dirs[row] = unity_dir[face_index, py, px]
        unity_disks[row] = unity_disk[face_index, py, px]
        unity_gs[row] = unity_g[face_index, py, px, 0]

    # `_inner_capture_radius` computes max(1e-4, r_- + margin, r_+ - eps), so
    # inverting Unity's absolute captureR through eps = r_+ - captureR
    # reproduces it exactly whenever the r_- floor does not dominate. The
    # assertion below is what makes that structural rather than hopeful: at
    # |a|/M > 0.994987 the floor takes over and the two surfaces diverge.
    r_plus, _r_minus = horizon_radii(params)
    unity_capture_r = float(meta["captureR"])
    r_escape = float(meta["rEscape"])
    config = KsGpuTraceConfig(
        params=params,
        step_size=float(meta["stepSize"]),
        steps=int(meta["maxSteps"]),
        max_lambda=float(meta["maxLambda"]),
        max_step=float(meta["maxStep"]),
        step_r_ref=float(meta["stepRRef"]),
        adaptive_step=bool(meta["adaptiveStep"]),
        r_escape=r_escape,
        disk_r_in=float(meta["diskRIn"]),
        disk_r_out=float(meta["diskROut"]),
        time_orientation=orientation,
        horizon_eps=r_plus - unity_capture_r,
    )
    if abs(config.capture_r - unity_capture_r) > 1.0e-6:
        raise SystemExit(
            f"capture surface mismatch: Unity traces to r = {unity_capture_r!r} but "
            f"the Python config resolves to r = {config.capture_r!r}. The two "
            "tracers would be integrating to different termination radii, so no "
            "agreement figure from this dump is meaningful."
        )

    hamiltonian_max = float(meta["hamiltonianMax"])

    def apply_hug_criteria(result_dict, escaped_mask):
        # Validity is the Hamiltonian residual and nothing else. H is
        # identically zero for a null geodesic, so max|H| marks a ray the f32
        # integration destroyed - observer-radius and spin independent.
        #
        # This replaces the launch-radius and affine-length heuristics the
        # dump used to publish. Mirroring those here was worse than useless:
        # the comparator reproduced the same bad rule, so the Unity kernel and
        # its own gate agreed perfectly while both blanked the entire sky for
        # any observer inside r_+ + 0.05 M.
        return escaped_mask & (result_dict["h_max_abs"] <= hamiltonian_max)

    # The dumped tetrad is otherwise taken entirely on faith: every launch
    # state on both sides is built from it, so a wrong tetrad cancels out and
    # the gate still reports agreement. Check it against the independently
    # computed observer metric before using it.
    tetrad_legs = [
        tetrad["tetradTime"],
        tetrad["tetradR"],
        tetrad["tetradTheta"],
        tetrad["tetradPhi"],
    ]
    minkowski = np.diag([-1.0, 1.0, 1.0, 1.0])
    gram = np.array(
        [[float(a @ g_obs @ b) for b in tetrad_legs] for a in tetrad_legs],
        dtype=np.float64,
    )
    gram_error = float(np.max(np.abs(gram - minkowski)))
    if gram_error > 1.0e-6:
        raise SystemExit(
            f"dumped tetrad is not orthonormal: max |g(e_a, e_b) - eta_ab| = "
            f"{gram_error:.3e}. Every launch state derives from this tetrad, so "
            "no agreement figure from this dump is meaningful."
        )

    result = trace_ks_states(config, states)
    escaped = apply_hug_criteria(result, result["event_code"] == 1)
    py_dirs = batch_escape_directions(params, result["final_x"], result["final_p"], escaped)

    both = escaped & (unity_dirs[:, 3] > 0.5) & np.all(np.isfinite(py_dirs), axis=1)
    dots = np.clip(
        np.sum(py_dirs[both] * unity_dirs[both, :3], axis=1)
        / (
            np.linalg.norm(py_dirs[both], axis=1)
            * np.linalg.norm(unity_dirs[both, :3], axis=1)
        ),
        -1.0,
        1.0,
    )
    angles = np.degrees(np.arccos(dots))
    disk_both = (result["disk_r_m"][:, 0] > 0.0) & (unity_disks[:, 3] > 0.5)
    dr = np.abs(result["disk_r_m"][disk_both, 0] - unity_disks[disk_both, 0])
    dg = np.abs(result["disk_g_m"][disk_both, 0] - unity_gs[disk_both])
    event_match = float(np.mean(escaped == (unity_dirs[:, 3] > 0.5)))

    summary = {
        "samples": int(picks.size),
        "escapedBoth": int(both.sum()),
        "eventAgreement": event_match,
        "dirMedianDeg": float(np.median(angles)) if both.any() else None,
        "dirP99Deg": float(np.percentile(angles, 99)) if both.any() else None,
        "diskSamples": int(disk_both.sum()),
        "diskRMedian": float(np.median(dr)) if disk_both.any() else None,
        "diskGMedian": float(np.median(dg)) if disk_both.any() else None,
        "tetradGramError": gram_error,
        "captureR": unity_capture_r,
        "declaredStages": declared_stages,
    }
    validated_stages.add("main")

    mask_bits = meta["maskBits"]
    escape_bit = int(mask_bits["escape"])
    disk0_bit = int(mask_bits["disk0"])
    disk1_bit = int(mask_bits["disk1"])
    subray_grid = int(meta["refineSubrayGrid"])
    subray_scale = float(meta["refineSubrayOffsetScale"])
    subray_count = subray_grid * subray_grid

    # ------------------------------------------------------------------
    # Limb-refine stage (fractional-coverage anti-aliasing): verify the
    # event mask, that non-limb texels are untouched, and re-trace the 3x3
    # subrays of sampled limb texels to reproduce the coverage and the
    # coverage-premultiplied disk means.
    # ------------------------------------------------------------------
    mask_path = args.dump_dir / "live_event_mask_u32.bytes"
    refined_path = args.dump_dir / "live_escape_dir_refined_rgba32f.bytes"
    if "refine" in declared_stages:
        for required in (mask_path, refined_path):
            if not required.exists():
                raise SystemExit(
                    f"dump declares the 'refine' stage but {required.name} is missing."
                )
    if mask_path.exists() and refined_path.exists():
        mask = np.fromfile(mask_path, dtype=np.uint32).reshape(6, face, face)
        refined_dir = np.fromfile(refined_path, dtype=np.float32).reshape(6, face, face, 4)
        refined_disk = np.fromfile(
            args.dump_dir / "live_disk0_refined_rgba32f.bytes", dtype=np.float32
        ).reshape(6, face, face, 4)
        refined_g = np.fromfile(
            args.dump_dir / "live_redshift0_refined_rgba32f.bytes", dtype=np.float32
        ).reshape(6, face, face, 4)

        # Mask bits must restate the main-pass channels exactly. Bit values
        # come from the dump's own `maskBits` map so a Unity-side layout
        # change cannot silently pass against a hardcoded 1/2/4 here.
        mask_escape = (mask & escape_bit).astype(bool)
        summary["maskEscapeAgreement"] = float(np.mean(mask_escape == (unity_dir[..., 3] > 0.5)))
        summary["maskDisk0Agreement"] = float(
            np.mean(((mask & disk0_bit) > 0) == (unity_disk[..., 3] > 0.5))
        )
        # Order-1 disk bit was never checked at all. It is not dumped as a
        # channel, so the strongest available statement is that the bit is
        # only ever set where an order-0 crossing also occurred (a second
        # crossing implies a first).
        summary["maskDisk1ImpliesDisk0"] = bool(
            np.all(((mask & disk1_bit) == 0) | ((mask & disk0_bit) > 0))
        )

        # In-face 4-neighborhood mask discontinuity = the kernel's limb set.
        limb = np.zeros((6, face, face), dtype=bool)
        limb[:, :, 1:] |= mask[:, :, 1:] != mask[:, :, :-1]
        limb[:, :, :-1] |= mask[:, :, :-1] != mask[:, :, 1:]
        limb[:, 1:, :] |= mask[:, 1:, :] != mask[:, :-1, :]
        limb[:, :-1, :] |= mask[:, :-1, :] != mask[:, 1:, :]
        summary["limbTexels"] = int(limb.sum())

        untouched = ~limb
        summary["nonLimbUntouched"] = bool(
            np.array_equal(refined_dir[untouched], unity_dir[untouched])
            and np.array_equal(refined_disk[untouched], unity_disk[untouched])
        )

        limb_flat = np.flatnonzero(limb.reshape(-1))
        refine_samples = int(min(192, limb_flat.size))
        if refine_samples == 0:
            raise SystemExit(
                "the refine stage produced an empty limb set: the event mask has no "
                "discontinuity anywhere on the cube, which cannot happen for a view "
                "that contains a shadow edge. Refusing to report a vacuous pass."
            )
        if refine_samples > 0:
            # Subray layout from the dump, not hardcoded: grid N and offset
            # scale s give offsets (i - (N-1)/2) * s in texel units.
            sub_offsets = (
                np.arange(subray_grid, dtype=np.float64) - 0.5 * (subray_grid - 1)
            ) * subray_scale
            sub_picks = rng.choice(limb_flat, size=refine_samples, replace=False)
            sub_states = np.zeros((refine_samples * subray_count, 8), dtype=np.float32)
            for row, flat in enumerate(sub_picks):
                face_index = int(flat) // (face * face)
                in_face = int(flat) % (face * face)
                py = in_face // face
                px = in_face % face
                uu = 2.0 * ((px + 0.5 + np.tile(sub_offsets, subray_grid)) / face) - 1.0
                vv = 2.0 * ((py + 0.5 + np.repeat(sub_offsets, subray_grid)) / face) - 1.0
                dirs9 = _face_directions_from_uv(faces[face_index], uu, vv)
                for sub in range(subray_count):
                    d = dirs9[sub]
                    q = (
                        orientation * tetrad["tetradTime"]
                        - d[2] * tetrad["tetradR"]
                        - d[1] * tetrad["tetradTheta"]
                        - d[0] * tetrad["tetradPhi"]
                    )
                    sub_states[row * subray_count + sub, 1:4] = position
                    sub_states[row * subray_count + sub, 4:8] = g_obs @ q
            sub_result = trace_ks_states(config, sub_states)
            sub_escaped = apply_hug_criteria(sub_result, sub_result["event_code"] == 1)
            sub_dirs = batch_escape_directions(
                params, sub_result["final_x"], sub_result["final_p"], sub_escaped
            )
            cov_diffs = np.zeros(refine_samples)
            rep_angles = []
            disk_pre_diffs = []
            g_pre_diffs = []
            for row, flat in enumerate(sub_picks):
                face_index = int(flat) // (face * face)
                in_face = int(flat) % (face * face)
                py = in_face // face
                px = in_face % face
                esc9 = sub_escaped[row * subray_count : (row + 1) * subray_count]
                coverage = float(np.mean(esc9))
                gpu = refined_dir[face_index, py, px]
                cov_diffs[row] = abs(coverage - float(gpu[3]))
                if esc9.any() and gpu[3] > 1.0e-4:
                    d9 = sub_dirs[row * subray_count : (row + 1) * subray_count][esc9]
                    mean = d9.sum(axis=0)
                    mean /= max(np.linalg.norm(mean), 1.0e-12)
                    rep = d9[int(np.argmax(d9 @ mean))]
                    gpu_rep = gpu[:3] / max(np.linalg.norm(gpu[:3]), 1.0e-12)
                    dot = float(np.clip(rep @ gpu_rep, -1.0, 1.0))
                    rep_angles.append(math.degrees(math.acos(dot)))
                disk_r9 = sub_result["disk_r_m"][row * subray_count : (row + 1) * subray_count, 0]
                disk_g9 = sub_result["disk_g_m"][row * subray_count : (row + 1) * subray_count, 0]
                valid9 = (disk_r9 > 0.0) & (disk_g9 > 0.0)
                pre_r = float(np.where(valid9, disk_r9, 0.0).sum() / subray_count)
                pre_g = float(np.where(valid9, disk_g9, 0.0).sum() / subray_count)
                disk_pre_diffs.append(abs(pre_r - float(refined_disk[face_index, py, px, 0])))
                g_pre_diffs.append(abs(pre_g - float(refined_g[face_index, py, px, 0])))
            summary["refineSamples"] = refine_samples
            summary["refineCoverageMeanDiff"] = float(np.mean(cov_diffs))
            summary["refineCoverageP95Diff"] = float(np.percentile(cov_diffs, 95))
            summary["refineRepDirMedianDeg"] = (
                float(np.median(rep_angles)) if rep_angles else None
            )
            summary["refineDiskPreMedianDiff"] = float(np.median(disk_pre_diffs))
            summary["refineGPreMedianDiff"] = float(np.median(g_pre_diffs))
            validated_stages.add("refine")

    # ------------------------------------------------------------------
    # Angular-window stage: same physics, gnomonic texel -> direction map
    # (alpha = R x/z, beta = -R y/z with symmetric bounds). Re-derive the
    # directions from the dumped bounds and re-trace a sample.
    # ------------------------------------------------------------------
    win_dir_path = args.dump_dir / "live_window_dir_rgba32f.bytes"
    if "window" in declared_stages:
        if not win_dir_path.exists():
            raise SystemExit(
                f"dump declares the 'window' stage but {win_dir_path.name} is missing."
            )
        if "windowSize" not in meta:
            raise SystemExit(
                "dump declares the 'window' stage but the metadata carries no "
                "windowSize/windowHalfAlpha/windowRObs. The window buffers cannot "
                "be interpreted without them."
            )
    if win_dir_path.exists() and "windowSize" in meta:
        wsize = int(meta["windowSize"])
        half_alpha = float(meta["windowHalfAlpha"])
        r_obs_win = float(meta["windowRObs"])
        win_dir = np.fromfile(win_dir_path, dtype=np.float32).reshape(wsize, wsize, 4)
        win_disk = np.fromfile(
            args.dump_dir / "live_window_disk0_rgba32f.bytes", dtype=np.float32
        ).reshape(wsize, wsize, 4)
        win_g = np.fromfile(
            args.dump_dir / "live_window_redshift0_rgba32f.bytes", dtype=np.float32
        ).reshape(wsize, wsize, 4)

        wpicks = rng.choice(wsize * wsize, size=min(1024, wsize * wsize), replace=False)
        wstates = np.zeros((wpicks.size, 8), dtype=np.float32)
        w_unity_dirs = np.zeros((wpicks.size, 4), dtype=np.float64)
        w_unity_disks = np.zeros((wpicks.size, 4), dtype=np.float64)
        w_unity_gs = np.zeros(wpicks.size, dtype=np.float64)
        for row, flat in enumerate(wpicks):
            py = int(flat) // wsize
            px = int(flat) % wsize
            u = (px + 0.5) / wsize
            v = (py + 0.5) / wsize
            alpha = (2.0 * u - 1.0) * half_alpha
            beta = (1.0 - 2.0 * v) * half_alpha
            d = np.array([alpha / r_obs_win, -beta / r_obs_win, 1.0], dtype=np.float64)
            d /= np.linalg.norm(d)
            q = (
                orientation * tetrad["tetradTime"]
                - d[2] * tetrad["tetradR"]
                - d[1] * tetrad["tetradTheta"]
                - d[0] * tetrad["tetradPhi"]
            )
            wstates[row, 1:4] = position
            wstates[row, 4:8] = g_obs @ q
            w_unity_dirs[row] = win_dir[py, px]
            w_unity_disks[row] = win_disk[py, px]
            w_unity_gs[row] = win_g[py, px, 0]
        w_result = trace_ks_states(config, wstates)
        w_escaped = apply_hug_criteria(w_result, w_result["event_code"] == 1)
        w_py_dirs = batch_escape_directions(
            params, w_result["final_x"], w_result["final_p"], w_escaped
        )
        w_both = w_escaped & (w_unity_dirs[:, 3] > 0.5) & np.all(np.isfinite(w_py_dirs), axis=1)
        w_dots = np.clip(
            np.sum(w_py_dirs[w_both] * w_unity_dirs[w_both, :3], axis=1)
            / (
                np.linalg.norm(w_py_dirs[w_both], axis=1)
                * np.linalg.norm(w_unity_dirs[w_both, :3], axis=1)
            ),
            -1.0,
            1.0,
        )
        w_angles = np.degrees(np.arccos(w_dots))
        w_disk_both = (w_result["disk_r_m"][:, 0] > 0.0) & (w_unity_disks[:, 3] > 0.5)
        w_dr = np.abs(w_result["disk_r_m"][w_disk_both, 0] - w_unity_disks[w_disk_both, 0])
        w_dg = np.abs(w_result["disk_g_m"][w_disk_both, 0] - w_unity_gs[w_disk_both])
        summary["windowSamples"] = int(wpicks.size)
        summary["windowEventAgreement"] = float(
            np.mean(w_escaped == (w_unity_dirs[:, 3] > 0.5))
        )
        summary["windowDirMedianDeg"] = (
            float(np.median(w_angles)) if w_both.any() else None
        )
        summary["windowDiskRMedian"] = float(np.median(w_dr)) if w_disk_both.any() else None
        summary["windowDiskGMedian"] = float(np.median(w_dg)) if w_disk_both.any() else None
        validated_stages.add("window")

        # --------------------------------------------------------------
        # Window limb-refine stage. The RefineWindow kernel used to ship
        # entirely unvalidated: the dump never dispatched it. Same
        # fractional-coverage contract as the cube-face refine pass.
        # --------------------------------------------------------------
        win_mask_path = args.dump_dir / "live_window_mask_u32.bytes"
        win_refined_path = args.dump_dir / "live_window_dir_refined_rgba32f.bytes"
        if "windowRefine" in declared_stages:
            for required in (win_mask_path, win_refined_path):
                if not required.exists():
                    raise SystemExit(
                        f"dump declares the 'windowRefine' stage but {required.name} "
                        "is missing."
                    )
        if win_mask_path.exists() and win_refined_path.exists():
            win_mask = np.fromfile(win_mask_path, dtype=np.uint32).reshape(wsize, wsize)
            win_refined_dir = np.fromfile(
                win_refined_path, dtype=np.float32
            ).reshape(wsize, wsize, 4)

            summary["windowMaskEscapeAgreement"] = float(
                np.mean((win_mask & escape_bit).astype(bool) == (win_dir[..., 3] > 0.5))
            )

            w_limb = np.zeros((wsize, wsize), dtype=bool)
            w_limb[:, 1:] |= win_mask[:, 1:] != win_mask[:, :-1]
            w_limb[:, :-1] |= win_mask[:, :-1] != win_mask[:, 1:]
            w_limb[1:, :] |= win_mask[1:, :] != win_mask[:-1, :]
            w_limb[:-1, :] |= win_mask[:-1, :] != win_mask[1:, :]
            summary["windowLimbTexels"] = int(w_limb.sum())
            summary["windowNonLimbUntouched"] = bool(
                np.array_equal(win_refined_dir[~w_limb], win_dir[~w_limb])
            )

            w_limb_flat = np.flatnonzero(w_limb.reshape(-1))
            w_refine_samples = int(min(128, w_limb_flat.size))
            if w_refine_samples == 0:
                raise SystemExit(
                    "the windowRefine stage produced an empty limb set: the window "
                    "event mask has no discontinuity. Refusing to report a vacuous "
                    "pass."
                )
            w_sub_offsets = (
                np.arange(subray_grid, dtype=np.float64) - 0.5 * (subray_grid - 1)
            ) * subray_scale
            w_sub_picks = rng.choice(w_limb_flat, size=w_refine_samples, replace=False)
            w_sub_states = np.zeros((w_refine_samples * subray_count, 8), dtype=np.float32)
            for row, flat in enumerate(w_sub_picks):
                py = int(flat) // wsize
                px = int(flat) % wsize
                su = np.tile(w_sub_offsets, subray_grid)
                sv = np.repeat(w_sub_offsets, subray_grid)
                uu = (px + 0.5 + su) / wsize
                vv = (py + 0.5 + sv) / wsize
                alpha = (2.0 * uu - 1.0) * half_alpha
                beta = (1.0 - 2.0 * vv) * half_alpha
                for sub in range(subray_count):
                    d = np.array(
                        [alpha[sub] / r_obs_win, -beta[sub] / r_obs_win, 1.0],
                        dtype=np.float64,
                    )
                    d /= np.linalg.norm(d)
                    q = (
                        orientation * tetrad["tetradTime"]
                        - d[2] * tetrad["tetradR"]
                        - d[1] * tetrad["tetradTheta"]
                        - d[0] * tetrad["tetradPhi"]
                    )
                    w_sub_states[row * subray_count + sub, 1:4] = position
                    w_sub_states[row * subray_count + sub, 4:8] = g_obs @ q
            w_sub_result = trace_ks_states(config, w_sub_states)
            w_sub_escaped = apply_hug_criteria(
                w_sub_result, w_sub_result["event_code"] == 1
            )
            w_cov_diffs = np.zeros(w_refine_samples)
            for row, flat in enumerate(w_sub_picks):
                py = int(flat) // wsize
                px = int(flat) % wsize
                esc = w_sub_escaped[row * subray_count : (row + 1) * subray_count]
                coverage = float(np.mean(esc))
                w_cov_diffs[row] = abs(coverage - float(win_refined_dir[py, px, 3]))
            summary["windowRefineSamples"] = w_refine_samples
            summary["windowRefineCoverageMeanDiff"] = float(np.mean(w_cov_diffs))
            summary["windowRefineCoverageP95Diff"] = float(
                np.percentile(w_cov_diffs, 95)
            )
            validated_stages.add("windowRefine")

    # ------------------------------------------------------------------
    # Structured event classification. The display renders every non-escape
    # class dark, but the scientific artifact must not conflate physical
    # capture, a non-finite RK state, and affine-budget exhaustion - and the
    # comparator must be able to say WHICH class disagreed.
    # ------------------------------------------------------------------
    class_path = args.dump_dir / "live_class_u32.bytes"
    hmax_path = args.dump_dir / "live_h_max_abs_f32.bytes"
    for required in (class_path, hmax_path):
        if not required.exists():
            raise SystemExit(
                f"dump is missing {required.name}: the structured classification "
                "artifact is mandatory, a bare escape/not-escape mask cannot "
                "distinguish capture from solver failure from budget exhaustion."
            )
    bits = meta["classBits"]
    unity_class = np.fromfile(class_path, dtype=np.uint32).reshape(6, face, face)
    unity_hmax = np.fromfile(hmax_path, dtype=np.float32).reshape(6, face, face)
    flat_class = unity_class.reshape(-1)[picks]
    flat_hmax = unity_hmax.reshape(-1)[picks]
    unity_event = (flat_class >> int(bits["eventShift"])) & np.uint32(bits["eventMask"])
    unity_failure = (flat_class >> int(bits["failureShift"])) & np.uint32(bits["failureMask"])
    unity_rejected = (flat_class & np.uint32(bits["hamiltonianRejectedBit"])) > 0

    py_event = result["event_code"].astype(np.uint32)
    py_failure = result["failure_code"].astype(np.uint32)
    py_rejected = (result["event_code"] == 1) & (result["h_max_abs"] > hamiltonian_max)

    summary["eventCodeAgreement"] = float(np.mean(unity_event == py_event))
    summary["failureCodeAgreement"] = float(np.mean(unity_failure == py_failure))
    summary["hamiltonianRejectAgreement"] = float(np.mean(unity_rejected == py_rejected))
    summary["hamiltonianMax"] = hamiltonian_max
    summary["classCounts"] = {
        "escape": int(np.count_nonzero((py_event == 1) & ~py_rejected)),
        "physicalCapture": int(np.count_nonzero(py_event == 0)),
        "numericalInvalid": int(np.count_nonzero((py_event == 3) & (py_failure == 3))),
        "budgetExhausted": int(np.count_nonzero((py_event == 3) & (py_failure == 2))),
        "hamiltonianRejected": int(np.count_nonzero(py_rejected)),
    }
    escaping_total = int(np.count_nonzero(py_event == 1))
    summary["excludedFraction"] = (
        float(np.count_nonzero(py_rejected) / escaping_total) if escaping_total else 0.0
    )
    summary["escapeFraction"] = float(
        np.count_nonzero((py_event == 1) & ~py_rejected) / max(1, picks.size)
    )
    kept = (py_event == 1) & ~py_rejected
    summary["hMaxMedianDiff"] = (
        float(np.median(np.abs(flat_hmax[kept] - result["h_max_abs"][kept])))
        if np.any(kept)
        else None
    )

    # ------------------------------------------------------------------
    # ESCAPED-MOMENTUM chart rotation SIGN (the kernel's role). A plain
    # angular threshold at r_escape = 200 M cannot discriminate it: the whole
    # correction, 2|delta| = 2.60e-3 deg, is only ~8x the measured f32
    # agreement floor there. The only discriminating formulation is that
    # agreeing with the ROTATED reference must beat agreeing with the
    # unrotated one - a dimensionless comparison with no tuned threshold.
    #
    # This is NOT skipped when the sample is thin: a sign gate that silently
    # evaporates is the failure mode it exists to prevent.
    # ------------------------------------------------------------------
    unrotated = batch_escape_directions(
        params, result["final_x"], result["final_p"], escaped, apply_chart_rotation=False
    )
    rot_ok = both & np.all(np.isfinite(unrotated), axis=1)
    rot_count = int(np.count_nonzero(rot_ok))
    if rot_count < MIN_CHART_SIGN_SAMPLES:
        raise SystemExit(
            f"only {rot_count} texels can discriminate the escape-direction "
            f"rotation sign (minimum {MIN_CHART_SIGN_SAMPLES}); refusing to "
            "report a pass for a sign gate that did not run."
        )

    def _max_angle(reference):
        dots = np.clip(
            np.sum(reference[rot_ok] * unity_dirs[rot_ok, :3], axis=1)
            / (
                np.linalg.norm(reference[rot_ok], axis=1)
                * np.linalg.norm(unity_dirs[rot_ok, :3], axis=1)
            ),
            -1.0,
            1.0,
        )
        return float(np.max(np.degrees(np.arccos(dots))))

    summary["chartSignSamples"] = rot_count
    summary["chartRotatedMaxDeg"] = _max_angle(py_dirs)
    summary["chartUnrotatedMaxDeg"] = _max_angle(unrotated)
    summary["rotationIsImprovement"] = bool(
        summary["chartRotatedMaxDeg"] < summary["chartUnrotatedMaxDeg"]
    )
    # r_escape this dump actually resolved the sign at. The gate is only
    # discriminating while 2|delta| stays above the f32 agreement floor, so
    # record it and refuse a dump that resolved the sign nowhere useful. See
    # `validation/quest_pcvr/README.md` for the multi-r_escape dump set.
    delta_deg = abs(
        math.degrees(math.atan2(params.a, r_escape) + bl_to_ks_phi_shift(params, r_escape))
    )
    summary["chartDeltaDeg"] = delta_deg
    summary["chartSignMarginRatio"] = (
        2.0 * delta_deg / max(summary["chartRotatedMaxDeg"], 1.0e-12)
    )

    # ------------------------------------------------------------------
    # OBSERVER-POSITION basis SIGN (the C# role). Separate gate, separate
    # data, opposite sign: this one must be -delta / BL-spherical while the
    # kernel above must be +delta. Nothing else in this dump touches it.
    # ------------------------------------------------------------------
    summary["observerBasis"] = check_observer_basis_probes(
        params, meta.get("observerBasisProbes") or []
    )

    summary["validatedStages"] = sorted(validated_stages)
    summary["waivedStages"] = sorted(set(args.allow_missing_stage))
    print(json.dumps(summary, indent=2))
    # Stage coverage first. A threshold that was never evaluated is not a
    # threshold that passed, so an absent stage fails the run before any
    # numeric gate gets the chance to look successful.
    waived = set(args.allow_missing_stage)
    missing_declared = [s for s in declared_stages if s not in validated_stages]
    if missing_declared:
        raise SystemExit(
            f"dump declares stages {declared_stages} but only "
            f"{sorted(validated_stages)} were validated; unvalidated: "
            f"{missing_declared}."
        )
    missing_required = [
        s for s in REQUIRED_STAGES if s not in validated_stages and s not in waived
    ]
    if missing_required:
        raise SystemExit(
            f"required stages {missing_required} were not validated. Re-dump with "
            "GRBHXRGateAutomation.BatchLiveTracerValidationDump, or waive them "
            "explicitly with --allow-missing-stage."
        )

    # Gate thresholds: same-algorithm f32 vs f32 must agree except at the
    # photon-shell chaotic set. Each population must be non-empty; an empty
    # comparison set used to skip its threshold silently.
    assert event_match > 0.995, "event classification mismatch"
    # Structured classification must agree class-by-class, not merely on
    # escape/not-escape - two implementations can agree on a binary mask while
    # disagreeing about why a ray is dark.
    assert summary["eventCodeAgreement"] > 0.995, "raw event code disagreement"
    assert summary["failureCodeAgreement"] > 0.995, "raw failure code disagreement"
    assert summary["hamiltonianRejectAgreement"] > 0.995, "validity verdict disagreement"
    assert summary["classCounts"]["numericalInvalid"] == 0, (
        "solver failures present; the classification is not clean and no agreement "
        "figure from this dump is meaningful"
    )
    # gr_bh_xr.gpu.validate_descent_frames.MAX_EXCLUDED_FRACTION
    assert summary["excludedFraction"] <= 0.35, (
        f"Hamiltonian residual excluded {summary['excludedFraction']:.3f} of escaping "
        "rays; the configuration is broken"
    )
    # gr_bh_xr.gpu.generate_descent_keyframes.MIN_ESCAPE_FRACTION - a view whose
    # sky is almost entirely dark is a blank frame, which is exactly what the
    # removed launch-radius heuristic produced near the horizon.
    assert summary["escapeFraction"] >= 0.25, (
        f"escape fraction {summary['escapeFraction']:.3f} below the accepted floor; "
        "refusing to report a blank sky as a pass"
    )
    if summary.get("hMaxMedianDiff") is not None:
        assert summary["hMaxMedianDiff"] < 1.0e-5, "Hamiltonian residual disagreement"
    # Escaped-MOMENTUM rotation sign. Never a bare threshold, and never
    # conditional - see the comment above.
    assert summary["rotationIsImprovement"], (
        "Unity matches the UNROTATED chart better than the rotated one: the "
        "escape-direction rotation sign is wrong (must be +delta)"
    )
    assert summary["chartSignMarginRatio"] > 2.0, (
        f"at r_escape = {r_escape} the sign correction 2|delta| = "
        f"{2.0 * summary['chartDeltaDeg']:.3e} deg is not comfortably above the "
        f"measured agreement {summary['chartRotatedMaxDeg']:.3e} deg; this dump "
        "cannot resolve the sign. Re-dump at a smaller r_escape."
    )
    # Observer-position basis sign. Independent of the above: it uses probe
    # data, the opposite sign, and its own discrimination proof.
    basis_summary = summary["observerBasis"]
    assert basis_summary["toleranceIsDiscriminating"], (
        f"observer-basis tolerance {basis_summary['toleranceDeg']} deg is not at "
        f"least {BASIS_PROBE_DISCRIMINATION_FACTOR}x below the smallest wrong-sign "
        f"separation {basis_summary['smallestWrongSignSeparationDeg']:.3e} deg; the "
        "probe grid cannot discriminate and a pass would be meaningless"
    )
    assert basis_summary["maxDeg"] < BASIS_PROBE_TOLERANCE_DEG, (
        f"Unity observer basis disagrees with the accepted keyframe mapping by "
        f"{basis_summary['maxDeg']:.3e} deg (worst probe "
        f"{basis_summary['worstProbe']}); the observer-position chart sign or the "
        "BL-spherical construction is wrong (must be -delta, NOT the kernel's "
        "+delta)"
    )
    assert both.any(), "no texel escaped in both tracers; direction gate is vacuous"
    assert summary["dirMedianDeg"] < 0.05, "median direction error too large"
    assert disk_both.any(), "no disk crossing in both tracers; disk gate is vacuous"
    assert summary["diskRMedian"] < 0.05, "median disk radius error too large"
    assert summary["diskGMedian"] < 1.0e-3, "median disk g error too large"
    if "refine" in validated_stages:
        assert summary["maskEscapeAgreement"] > 0.9999, "event mask disagrees with main channels"
        assert summary["maskDisk0Agreement"] > 0.9999, "disk mask disagrees with main channels"
        assert summary["maskDisk1ImpliesDisk0"], "order-1 disk bit set without an order-0 crossing"
        assert summary["nonLimbUntouched"], "refine wrote outside the limb set"
        # Every limb subray grazes the discontinuity, so allow rare
        # single-subray event flips between the two f32 tracers.
        assert summary["refineCoverageMeanDiff"] < 0.02, "refine coverage mismatch"
        assert summary["refineCoverageP95Diff"] <= 0.115, "refine coverage tail mismatch"
        assert summary["refineRepDirMedianDeg"] is not None, "refine produced no comparable direction"
        assert summary["refineRepDirMedianDeg"] < 0.1, "refine representative dir mismatch"
        assert summary["refineDiskPreMedianDiff"] < 0.05, "refine disk premultiply mismatch"
        assert summary["refineGPreMedianDiff"] < 1.0e-3, "refine g premultiply mismatch"
    if "window" in validated_stages:
        assert summary["windowEventAgreement"] > 0.995, "window event mismatch"
        assert summary["windowDirMedianDeg"] is not None, "window produced no comparable direction"
        assert summary["windowDirMedianDeg"] < 0.05, "window direction error too large"
        assert summary["windowDiskRMedian"] is not None, "window produced no disk crossing"
        assert summary["windowDiskRMedian"] < 0.05, "window disk radius error too large"
        assert summary["windowDiskGMedian"] < 1.0e-3, "window disk g error too large"
    if "windowRefine" in validated_stages:
        assert summary["windowMaskEscapeAgreement"] > 0.9999, "window mask disagrees with channels"
        assert summary["windowNonLimbUntouched"], "window refine wrote outside the limb set"
        assert summary["windowRefineCoverageMeanDiff"] < 0.02, "window refine coverage mismatch"
        assert summary["windowRefineCoverageP95Diff"] <= 0.115, "window refine coverage tail mismatch"
    stage_note = f"stages {sorted(validated_stages)}"
    if waived:
        stage_note += f", WAIVED {sorted(waived)}"
    print(f"live tracer cross-check PASSED ({stage_note})")


if __name__ == "__main__":
    main()
