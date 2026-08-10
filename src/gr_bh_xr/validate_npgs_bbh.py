"""Cross-check native dynamic-BBH rays against the CPU f64 oracle."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from .dynamic_types import DynamicEventSpec, DynamicTraceConfig
from .geodesic_dynamic import trace_dynamic_state
from .metrics import FixedCircularBinaryOrbit, SuperposedKerrSchildBBHProvider
from .npgs_audit import RAW_SCHEMA_V4, load_native_audit
from .validate_npgs_kerr import (
    native_initial_state_to_python_ks,
    python_direction_to_npgs,
)


SCHEMA = "gr-bh-xr.npgs.bbh-crosscheck.v1"
CPU_EVENT_CODES = {"capture": 0, "escape": 1, "invalid": 3}


def _expected_native_camera_direction(
    *,
    row: int,
    col: int,
    height: int,
    width: int,
    parameters: dict[str, Any],
) -> np.ndarray:
    """Reconstruct the audit camera ray without using the shader launch state."""

    u = (float(col) + 0.5) / float(width)
    # TraceRay flips the OpenGL framebuffer row before constructing the ray.
    v = 1.0 - (float(row) + 0.5) / float(height)
    fov_scale = math.tan(math.radians(float(parameters["fov_deg"])) / 2.0)
    camera_direction = np.array(
        [
            fov_scale * (2.0 * u - 1.0),
            fov_scale * (2.0 * v - 1.0) * float(height) / float(width),
            -1.0,
        ],
        dtype=np.float64,
    )
    camera_direction /= np.linalg.norm(camera_direction)
    right = np.asarray(parameters["camera_right"], dtype=np.float64)
    up = np.asarray(parameters["camera_up"], dtype=np.float64)
    back = np.asarray(parameters["camera_back"], dtype=np.float64)
    world_direction = (
        camera_direction[0] * right
        + camera_direction[1] * up
        + camera_direction[2] * back
    )
    return world_direction / np.linalg.norm(world_direction)


def validate_npgs_bbh(
    raw: Path | str,
    *,
    samples: int = 257,
    boundary_pixels: int = 1,
    out: Path | str | None = None,
    h5: Path | str | None = None,
) -> dict[str, Any]:
    """Replay exact native launch states in the independent f64 BBH provider."""

    capture = load_native_audit(raw)
    metadata = capture.metadata
    parameters = metadata["parameters"]
    if metadata["schema"] != RAW_SCHEMA_V4:
        raise ValueError("Dynamic BBH comparison requires native audit raw schema v4.")
    if parameters.get("bbh_enabled") is not True:
        raise ValueError("Native capture does not declare BBH mode.")
    if metadata["metric_provider"].get("stationary") is not False:
        raise ValueError("BBH comparison requires a nonstationary metric provider.")
    if capture.initial_ingoing_x is None or capture.initial_ingoing_p_cov is None:
        raise ValueError("Dynamic BBH comparison requires exact canonical launch states.")

    total_mass = float(parameters["bbh_total_mass_internal"])
    separation = float(parameters["bbh_separation_internal"])
    metric_time = float(parameters["bbh_metric_time_internal"])
    omega = float(parameters["bbh_omega_per_internal_time"])
    phase_at_launch = float(parameters["bbh_phase_rad"])
    worldtube_factor = float(parameters["bbh_worldtube_factor"])
    escape_radius = float(parameters["bbh_escape_radius_internal"])
    orbit = FixedCircularBinaryOrbit(
        total_mass=total_mass,
        separation=separation,
        phase0=phase_at_launch - omega * metric_time,
    )
    # The event lies outside the provider's fail-closed domain so DOP853 can
    # bracket it without evaluating a Runge-Kutta stage inside the excision.
    provider = SuperposedKerrSchildBBHProvider(
        orbit=orbit,
        worldtube_factor=max(1.0, worldtube_factor - 0.2),
    )

    def worldtube_event(_lam: float, x: np.ndarray, _p: np.ndarray) -> float:
        holes = provider.hole_states(float(x[0]))
        radii = provider.rest_radii(float(x[0]), x[1:4])
        return min(
            radius - worldtube_factor * hole.mass
            for radius, hole in zip(radii, holes, strict=True)
        )

    def escape_event(_lam: float, x: np.ndarray, _p: np.ndarray) -> float:
        return float(np.linalg.norm(x[1:4]) - escape_radius)

    config = DynamicTraceConfig(
        max_lambda=max(400.0, 4.0 * escape_radius),
        rtol=2.0e-10,
        atol=2.0e-12,
        max_step=0.5,
        events=(
            DynamicEventSpec(
                "capture", worldtube_event, direction=-1.0, provenance="bbh_worldtube"
            ),
            DynamicEventSpec(
                "escape", escape_event, direction=1.0, provenance="com_radius"
            ),
        ),
    )

    flat_indices = _sample_indices(capture.event_code.size, samples)
    rows, cols = np.unravel_index(flat_indices, capture.event_code.shape)
    count = flat_indices.size
    cpu_event = np.full(count, CPU_EVENT_CODES["invalid"], dtype=np.int8)
    cpu_h_max = np.full(count, np.nan, dtype=np.float64)
    cpu_delta_pt = np.full(count, np.nan, dtype=np.float64)
    launch_direction_error = np.full(count, np.nan, dtype=np.float64)
    direction_error = np.full(count, np.nan, dtype=np.float64)
    delta_pt_error = np.full(count, np.nan, dtype=np.float64)
    messages: list[str] = []

    for index, (row, col) in enumerate(zip(rows, cols, strict=True)):
        state = native_initial_state_to_python_ks(
            capture.initial_ingoing_x[row, col],
            capture.initial_ingoing_p_cov[row, col],
        )
        launch_sample = provider.sample(float(state.x[0]), state.x[1:4])
        launch_tangent = launch_sample.g_inv @ state.p
        launch_direction = python_direction_to_npgs(
            launch_tangent[1:4] / np.linalg.norm(launch_tangent[1:4])
        )
        expected_direction = _expected_native_camera_direction(
            row=int(row),
            col=int(col),
            height=capture.event_code.shape[0],
            width=capture.event_code.shape[1],
            parameters=parameters,
        )
        launch_direction_error[index] = math.acos(
            float(np.clip(np.dot(launch_direction, expected_direction), -1.0, 1.0))
        )
        result = trace_dynamic_state(provider, state, config)
        cpu_event[index] = CPU_EVENT_CODES.get(result.event, CPU_EVENT_CODES["invalid"])
        cpu_h_max[index] = result.h_max_abs
        cpu_delta_pt[index] = result.p_t_final - result.p_t_initial
        if result.failure_reason != "none":
            messages.append(f"row={row}, col={col}: {result.message}")
            continue
        native_delta_pt = float(capture.dynamic_diagnostics[row, col, 3])
        # The native-to-reference conversion reverses the complete covector.
        delta_pt_error[index] = abs(cpu_delta_pt[index] + native_delta_pt)
        if result.event == "escape":
            sample = provider.sample(float(result.final_x[0]), result.final_x[1:4])
            tangent = sample.g_inv @ result.final_p
            direction = tangent[1:4]
            norm = float(np.linalg.norm(direction))
            if math.isfinite(norm) and norm > 0.0:
                cpu_direction = python_direction_to_npgs(direction / norm)
                native_direction = capture.escape_dir[row, col].astype(np.float64)
                native_direction /= np.linalg.norm(native_direction)
                direction_error[index] = math.acos(
                    float(np.clip(np.dot(cpu_direction, native_direction), -1.0, 1.0))
                )

    native_event = capture.event_code[rows, cols]
    native_failure = capture.failure_code[rows, cols]
    none_code = int(metadata["failure_codes"]["none"])
    invalid_code = int(metadata["event_codes"]["invalid"])
    native_resolved = (native_failure == none_code) & (native_event != invalid_code)
    cpu_resolved = cpu_event != CPU_EVENT_CODES["invalid"]
    both_invalid = ~native_resolved & ~cpu_resolved
    native_only_invalid = ~native_resolved & cpu_resolved
    cpu_only_invalid = native_resolved & ~cpu_resolved
    compared = native_resolved & cpu_resolved
    boundary = _event_boundary_mask(capture.event_code, boundary_pixels)[rows, cols]
    stable = compared & ~boundary
    event_match = native_event == cpu_event
    stable_escape = stable & event_match & (native_event == int(metadata["event_codes"]["escape"]))
    finite_direction = stable_escape & np.isfinite(direction_error)
    direction_values = direction_error[finite_direction]
    direction_gradient, refinement_level = _audit_gradient_refinement(
        capture.event_code,
        capture.escape_dir,
        escape_code=int(metadata["event_codes"]["escape"]),
        boundary_pixels=boundary_pixels,
    )

    agreement_all = _fraction(event_match[compared])
    agreement_stable = _fraction(event_match[stable])
    direction_median = _optional_stat(direction_values, np.median)
    direction_rms = _optional_stat(
        direction_values, lambda value: np.sqrt(np.mean(value * value))
    )
    direction_max = _optional_stat(direction_values, np.max)
    launch_direction_max = _optional_stat(
        launch_direction_error[np.isfinite(launch_direction_error)], np.max
    )
    native_escape_h = np.abs(
        capture.dynamic_diagnostics[..., 2][
            capture.event_code == int(metadata["event_codes"]["escape"])
        ]
    )
    passed = bool(
        agreement_stable is not None
        and agreement_stable >= 0.98
        and direction_median is not None
        and direction_median < 1.0e-4
        and direction_rms is not None
        and direction_rms < 5.0e-4
        and launch_direction_max is not None
        and launch_direction_max < 1.0e-6
        and int(np.count_nonzero(cpu_only_invalid)) == 0
        and int(np.count_nonzero(native_only_invalid)) == 0
    )

    summary: dict[str, Any] = {
        "schema": SCHEMA,
        "source_raw": str(Path(raw).resolve()),
        "parameters": parameters,
        "samples_requested": int(samples),
        "samples_compared": int(np.count_nonzero(compared)),
        "stable_samples": int(np.count_nonzero(stable)),
        "both_invalid": int(np.count_nonzero(both_invalid)),
        "native_only_invalid": int(np.count_nonzero(native_only_invalid)),
        "cpu_only_invalid": int(np.count_nonzero(cpu_only_invalid)),
        "event_agreement_all_resolved": agreement_all,
        "event_agreement_stable": agreement_stable,
        "event_conflicts_stable": int(np.count_nonzero(stable & ~event_match)),
        "direction_samples_stable": int(direction_values.size),
        "direction_error_median_rad": direction_median,
        "direction_error_rms_rad": direction_rms,
        "direction_error_max_rad": direction_max,
        "launch_direction_error_max_rad": launch_direction_max,
        "audit_refinement_pixels": int(np.count_nonzero(refinement_level)),
        "audit_refinement_level2_pixels": int(np.count_nonzero(refinement_level == 2)),
        "escape_direction_gradient_max_rad": _optional_stat(
            direction_gradient[np.isfinite(direction_gradient)], np.max
        ),
        "cpu_h_max_abs": _optional_stat(cpu_h_max[np.isfinite(cpu_h_max)], np.max),
        "native_escape_h_max_abs": _optional_stat(native_escape_h, np.max),
        "native_escape_h_median_abs": _optional_stat(native_escape_h, np.median),
        "delta_p_t_error_max": _optional_stat(
            delta_pt_error[np.isfinite(delta_pt_error)], np.max
        ),
        "messages": messages,
        "thresholds": {
            "event_agreement_stable_min": 0.98,
            "direction_error_median_rad_max": 1.0e-4,
            "direction_error_rms_rad_max": 5.0e-4,
            "launch_direction_error_max_rad": 1.0e-6,
            "unexpected_one_sided_invalid_max": 0,
        },
        "claim_boundary": (
            "This gate validates the first equal-mass, nonspinning, fixed-circular "
            "superposed boosted Schwarzschild Kerr-Schild slice. It is a physics "
            "approximation with excision worldtubes, not an Einstein evolution or "
            "event-horizon reconstruction."
        ),
        "passed": passed,
    }

    if h5 is not None:
        h5_path = Path(h5)
        h5_path.parent.mkdir(parents=True, exist_ok=True)
        with h5py.File(h5_path, "w") as handle:
            handle.attrs["schema"] = SCHEMA
            handle.attrs["source_raw"] = str(Path(raw).resolve())
            handle.attrs["summary_json"] = json.dumps(summary, sort_keys=True)
            for name, values in {
                "row": rows,
                "col": cols,
                "native_event_code": native_event,
                "native_failure_code": native_failure,
                "cpu_event_code": cpu_event,
                "stable_mask": stable.astype(np.uint8),
                "boundary_mask": boundary.astype(np.uint8),
                "direction_error_rad": direction_error,
                "launch_direction_error_rad": launch_direction_error,
                "cpu_h_max_abs": cpu_h_max,
                "cpu_delta_p_t": cpu_delta_pt,
                "delta_p_t_error_abs": delta_pt_error,
            }.items():
                handle.create_dataset(name, data=values, compression="gzip", shuffle=True)
            handle.create_dataset(
                "escape_direction_gradient_rad",
                data=direction_gradient,
                compression="gzip",
                shuffle=True,
            )
            handle.create_dataset(
                "audit_refinement_level",
                data=refinement_level,
                compression="gzip",
                shuffle=True,
            )
        summary["out_h5"] = str(h5_path.resolve())

    if out is not None:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf8")
    return summary


def _sample_indices(pixel_count: int, samples: int) -> np.ndarray:
    if samples <= 0 or samples >= pixel_count:
        return np.arange(pixel_count, dtype=np.int64)
    centers = (np.arange(samples, dtype=np.float64) + 0.5) * pixel_count / samples
    return np.unique(np.minimum(centers.astype(np.int64), pixel_count - 1))


def _event_boundary_mask(event_code: np.ndarray, radius: int) -> np.ndarray:
    event = np.asarray(event_code)
    boundary = np.zeros(event.shape, dtype=bool)
    boundary[1:, :] |= event[1:, :] != event[:-1, :]
    boundary[:-1, :] |= event[:-1, :] != event[1:, :]
    boundary[:, 1:] |= event[:, 1:] != event[:, :-1]
    boundary[:, :-1] |= event[:, :-1] != event[:, 1:]
    for _ in range(radius):
        grown = boundary.copy()
        grown[1:, :] |= boundary[:-1, :]
        grown[:-1, :] |= boundary[1:, :]
        grown[:, 1:] |= boundary[:, :-1]
        grown[:, :-1] |= boundary[:, 1:]
        boundary = grown
    return boundary


def _audit_gradient_refinement(
    event_code: np.ndarray,
    escape_dir: np.ndarray,
    *,
    escape_code: int,
    boundary_pixels: int,
    direction_threshold_rad: float = 0.02,
) -> tuple[np.ndarray, np.ndarray]:
    """Build an audit-buffer refinement schedule without inspecting RGB color."""

    events = np.asarray(event_code)
    directions = np.asarray(escape_dir, dtype=np.float64)
    if directions.shape != events.shape + (3,):
        raise ValueError("escape directions must have shape event_code.shape + (3,)")
    gradient = np.full(events.shape, np.nan, dtype=np.float64)
    gradient[np.asarray(events) == escape_code] = 0.0

    # Work on explicit views so both pixels adjacent to a high-gradient edge
    # receive the same refinement request.
    valid_h = (events[:, :-1] == escape_code) & (events[:, 1:] == escape_code)
    if np.any(valid_h):
        left = directions[:, :-1][valid_h]
        right = directions[:, 1:][valid_h]
        left_norm = np.linalg.norm(left, axis=-1)
        right_norm = np.linalg.norm(right, axis=-1)
        finite = (
            np.isfinite(left).all(axis=-1)
            & np.isfinite(right).all(axis=-1)
            & (left_norm > 0.0)
            & (right_norm > 0.0)
        )
        angle = np.full(valid_h.sum(), np.nan, dtype=np.float64)
        angle[finite] = np.arccos(
            np.clip(
                np.sum(left[finite] * right[finite], axis=-1)
                / (left_norm[finite] * right_norm[finite]),
                -1.0,
                1.0,
            )
        )
        left_view = gradient[:, :-1]
        right_view = gradient[:, 1:]
        left_view[valid_h] = np.fmax(left_view[valid_h], angle)
        right_view[valid_h] = np.fmax(right_view[valid_h], angle)

    valid_v = (events[:-1, :] == escape_code) & (events[1:, :] == escape_code)
    if np.any(valid_v):
        top = directions[:-1, :][valid_v]
        bottom = directions[1:, :][valid_v]
        top_norm = np.linalg.norm(top, axis=-1)
        bottom_norm = np.linalg.norm(bottom, axis=-1)
        finite = (
            np.isfinite(top).all(axis=-1)
            & np.isfinite(bottom).all(axis=-1)
            & (top_norm > 0.0)
            & (bottom_norm > 0.0)
        )
        angle = np.full(valid_v.sum(), np.nan, dtype=np.float64)
        angle[finite] = np.arccos(
            np.clip(
                np.sum(top[finite] * bottom[finite], axis=-1)
                / (top_norm[finite] * bottom_norm[finite]),
                -1.0,
                1.0,
            )
        )
        top_view = gradient[:-1, :]
        bottom_view = gradient[1:, :]
        top_view[valid_v] = np.fmax(top_view[valid_v], angle)
        bottom_view[valid_v] = np.fmax(bottom_view[valid_v], angle)

    boundary = _event_boundary_mask(events, boundary_pixels)
    refinement = np.zeros(events.shape, dtype=np.uint8)
    refinement[np.isfinite(gradient) & (gradient > direction_threshold_rad)] = 1
    refinement[boundary] = 2
    return gradient, refinement


def _fraction(values: np.ndarray) -> float | None:
    return float(np.mean(values)) if values.size else None


def _optional_stat(values: np.ndarray, function) -> float | None:
    return float(function(values)) if values.size else None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=257)
    parser.add_argument("--boundary-pixels", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--h5", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    summary = validate_npgs_bbh(
        args.raw,
        samples=args.samples,
        boundary_pixels=args.boundary_pixels,
        out=args.out,
        h5=args.h5,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
