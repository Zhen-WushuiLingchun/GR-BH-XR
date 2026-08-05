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

from gr_bh_xr.gpu.generate_descent_keyframes import batch_escape_directions
from gr_bh_xr.gpu.generate_transfer_cubemap import _face_directions, _face_directions_from_uv
from gr_bh_xr.gpu.trace_ks import KsGpuTraceConfig, trace_ks_states
from gr_bh_xr.types import MetricParams

# Stages the Unity ValidationDump is expected to emit. `main` is implicit in
# every dump; the rest are separately dispatched compute kernels, each of
# which shipped unvalidated at some point in this file's history.
REQUIRED_STAGES = ("main", "refine", "window", "windowRefine")


def horizon_radii(params: MetricParams) -> tuple[float, float]:
    root = math.sqrt(max(params.M * params.M - params.a * params.a, 0.0))
    return params.M + root, params.M - root


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
    config = KsGpuTraceConfig(
        params=params,
        step_size=float(meta["stepSize"]),
        steps=int(meta["maxSteps"]),
        max_lambda=float(meta["maxLambda"]),
        max_step=float(meta["maxStep"]),
        step_r_ref=float(meta["stepRRef"]),
        adaptive_step=bool(meta["adaptiveStep"]),
        r_escape=float(meta["rEscape"]),
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

    hug_min_r = float(meta["hugMinR"])
    hug_lambda = float(meta["hugLambda"])

    def apply_hug_criteria(result_dict, escaped_mask):
        # The compute tracer's post-hoc horizon-hug darkening, driven by the
        # same two thresholds it used rather than by a re-derived branch. A
        # zero threshold means the corresponding criterion was inactive for
        # this dump, which is how Unity encodes it.
        if hug_min_r > 0.0:
            escaped_mask = escaped_mask & ~(result_dict["min_r"] < hug_min_r)
        if hug_lambda > 0.0:
            escaped_mask = escaped_mask & ~(result_dict["lambda_end"] > hug_lambda)
        return escaped_mask

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
