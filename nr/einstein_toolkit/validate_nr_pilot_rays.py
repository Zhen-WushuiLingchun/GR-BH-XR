"""Compare a fixed camera through two audited NR ADM snapshot resolutions.

The bounded ET pilot spans only ``1M`` of coordinate time.  This gate therefore
freezes each ADM slice and compares the *optical spatial convergence* of the
low/high resolutions.  It is not evidence for a full merger light cone.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import math
from pathlib import Path
from typing import Any, NamedTuple

import h5py
import numpy as np

from gr_bh_xr.dynamic_types import DynamicEventSpec, DynamicTraceConfig, MetricSample
from gr_bh_xr.geodesic_dynamic import dynamic_hamiltonian, trace_dynamic_state
from gr_bh_xr.metrics import ADMMetricSnapshotProvider
from gr_bh_xr.types import RayState


SCHEMA = "gr-bh-xr.bbh.nr-ray-convergence.v1"
EVENT_CODES = {"capture": 0, "escape": 1, "invalid": 2, "budget_exhaustion": 3}


class _FixedTraceResult(NamedTuple):
    event: str
    h_max_abs: float
    final_x: np.ndarray
    final_p: np.ndarray
    steps: int


def _event_crossing_fraction(left: float, right: float, direction: float) -> float | None:
    if direction < 0.0:
        crossed = left > 0.0 and right <= 0.0
    elif direction > 0.0:
        crossed = left < 0.0 and right >= 0.0
    else:
        crossed = (left < 0.0 <= right) or (left > 0.0 >= right)
    if not crossed:
        return None
    scale = abs(left) + abs(right)
    return 0.5 if scale == 0.0 else abs(left) / scale


def _trace_fixed_rk4(
    provider: "FrozenADMSliceProvider",
    state: RayState,
    config: DynamicTraceConfig,
    step_size: float,
) -> _FixedTraceResult:
    """Trace one frozen NR ray without resolving trilinear-grid derivative kinks."""

    if step_size <= 0.0:
        raise ValueError("fixed RK4 step_size must be positive.")
    y = np.concatenate((state.x, state.p)).astype(np.float64, copy=True)
    lam = 0.0
    h_max_abs = 0.0
    steps = 0

    def rhs(values: np.ndarray) -> np.ndarray:
        nonlocal h_max_abs
        sample = provider.sample(float(values[0]), values[1:4])
        if sample.validity != "valid":
            raise ValueError(f"metric provider returned {sample.validity}.")
        momentum = values[4:]
        h_max_abs = max(h_max_abs, abs(dynamic_hamiltonian(sample, momentum)))
        dx = sample.g_inv @ momentum
        dp = np.asarray(
            [
                -0.5 * float(momentum @ sample.d_g_inv[mu] @ momentum)
                for mu in range(4)
            ],
            dtype=np.float64,
        )
        return np.concatenate((dx, dp))

    event_values = [
        float(spec.function(lam, y[:4], y[4:])) for spec in config.events
    ]
    try:
        rhs(y)
        while lam < config.max_lambda:
            step = min(step_size, config.max_lambda - lam)
            k1 = rhs(y)
            k2 = rhs(y + 0.5 * step * k1)
            k3 = rhs(y + 0.5 * step * k2)
            k4 = rhs(y + step * k3)
            next_y = y + (step / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
            if not np.all(np.isfinite(next_y)):
                raise ValueError("fixed RK4 produced a non-finite state.")
            next_lambda = lam + step
            next_event_values = [
                float(spec.function(next_lambda, next_y[:4], next_y[4:]))
                for spec in config.events
            ]
            hits: list[tuple[float, DynamicEventSpec]] = []
            for spec, left, right in zip(
                config.events, event_values, next_event_values, strict=True
            ):
                fraction = _event_crossing_fraction(left, right, spec.direction)
                if fraction is not None and spec.terminal:
                    hits.append((fraction, spec))
            steps += 1
            if hits:
                fraction, spec = min(hits, key=lambda item: item[0])
                y = y + fraction * (next_y - y)
                rhs(y)
                return _FixedTraceResult(
                    spec.name, h_max_abs, y[:4].copy(), y[4:].copy(), steps
                )
            y = next_y
            lam = next_lambda
            event_values = next_event_values
    except Exception:
        return _FixedTraceResult(
            "invalid", h_max_abs, y[:4].copy(), y[4:].copy(), steps
        )
    return _FixedTraceResult(
        "budget_exhaustion", h_max_abs, y[:4].copy(), y[4:].copy(), steps
    )


class FrozenADMSliceProvider:
    """Hold one audited ADM time slice fixed while retaining spatial derivatives."""

    def __init__(self, provider: ADMMetricSnapshotProvider, time_M: float) -> None:
        self.provider = provider
        self.time_M = float(time_M)

    def sample(self, t: float, x: np.ndarray) -> MetricSample:
        sample = self.provider.sample(self.time_M, x)
        if sample.validity != "valid":
            return replace(sample, t=float(t))
        derivatives = sample.d_g_inv.copy()
        derivatives[0] = 0.0
        return replace(
            sample,
            t=float(t),
            d_g_inv=derivatives,
            source_revision=f"{sample.source_revision}:frozen@{self.time_M:.9g}M",
        )


def _orthonormal_spatial_basis(
    gamma: np.ndarray, candidates: tuple[np.ndarray, np.ndarray, np.ndarray]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    basis: list[np.ndarray] = []
    for candidate in candidates:
        vector = np.asarray(candidate, dtype=np.float64).copy()
        for previous in basis:
            vector -= float(vector @ gamma @ previous) * previous
        norm_sq = float(vector @ gamma @ vector)
        if norm_sq <= 0.0 or not math.isfinite(norm_sq):
            raise ValueError("camera spatial basis is not positive definite.")
        basis.append(vector / math.sqrt(norm_sq))
    return basis[0], basis[1], basis[2]


def initial_eulerian_camera_state(
    provider: FrozenADMSliceProvider,
    *,
    observer: np.ndarray,
    screen_x: float,
    screen_y: float,
) -> RayState:
    """Launch one future null ray from the local Eulerian ADM tetrad.

    The pilot camera sits on ``+x`` and looks toward the binary.  ``screen_x``
    points toward ``+y`` and ``screen_y`` toward ``+z``.
    """

    sample = provider.sample(0.0, observer)
    if sample.validity != "valid":
        raise ValueError("pilot observer lies outside the ADM snapshot domain.")
    e_forward, e_right, e_up = _orthonormal_spatial_basis(
        sample.gamma_cov,
        (
            np.array([-1.0, 0.0, 0.0]),
            np.array([0.0, 1.0, 0.0]),
            np.array([0.0, 0.0, 1.0]),
        ),
    )
    direction = e_forward + float(screen_x) * e_right + float(screen_y) * e_up
    direction /= math.sqrt(float(direction @ sample.gamma_cov @ direction))
    e_time = np.concatenate(
        ([1.0 / sample.lapse], -sample.shift / sample.lapse)
    )
    k_contra = e_time + np.concatenate(([0.0], direction))
    p_cov = sample.g_cov @ k_contra
    h = 0.5 * float(p_cov @ sample.g_inv @ p_cov)
    if abs(h) > 1.0e-10 or k_contra[0] <= 0.0:
        raise ValueError(f"pilot camera launch is not future null: H={h}.")
    return RayState(x=np.concatenate(([0.0], observer)), p=p_cov)


def _events(capture_radius_M: float, escape_radius_M: float) -> tuple[DynamicEventSpec, ...]:
    def capture(_lam: float, x: np.ndarray, _p: np.ndarray) -> float:
        point = x[1:4]
        return min(
            float(np.linalg.norm(point - np.array([3.0, 0.0, 0.0]))),
            float(np.linalg.norm(point - np.array([-3.0, 0.0, 0.0]))),
        ) - capture_radius_M

    def escape(_lam: float, x: np.ndarray, _p: np.ndarray) -> float:
        return float(np.linalg.norm(x[1:4])) - escape_radius_M

    return (
        DynamicEventSpec(
            "capture", capture, direction=-1.0, provenance="apparent-horizon-worldtube-proxy"
        ),
        DynamicEventSpec("escape", escape, direction=1.0, provenance="finite-domain-sphere"),
    )


def _escape_direction(provider: FrozenADMSliceProvider, final_x: np.ndarray, final_p: np.ndarray) -> np.ndarray:
    sample = provider.sample(float(final_x[0]), final_x[1:4])
    direction = sample.g_inv @ final_p
    spatial = np.asarray(direction[1:4], dtype=np.float64)
    return spatial / np.linalg.norm(spatial)


def _angular_error(left: np.ndarray, right: np.ndarray) -> float:
    return float(math.acos(float(np.clip(left @ right, -1.0, 1.0))))


def validate_nr_pilot_rays(
    low_path: Path | str,
    high_path: Path | str,
    *,
    grid: int = 7,
    screen_half_width: float = 0.35,
    observer_radius_M: float = 20.0,
    capture_radius_M: float = 0.65,
    escape_radius_M: float = 28.0,
    max_lambda: float = 80.0,
    integration_method: str = "fixed_rk4",
    step_size: float = 0.05,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    if grid < 3 or grid % 2 == 0:
        raise ValueError("grid must be an odd integer >=3.")
    if integration_method not in ("fixed_rk4", "dop853"):
        raise ValueError("integration_method must be fixed_rk4 or dop853.")
    low = ADMMetricSnapshotProvider.from_hdf5(low_path)
    high = ADMMetricSnapshotProvider.from_hdf5(high_path)
    shared_times = sorted(set(low.snapshot.times).intersection(high.snapshot.times))
    if not shared_times:
        raise ValueError("low/high snapshots have no common coordinate time.")

    axis = np.linspace(-screen_half_width, screen_half_width, grid)
    directions: list[tuple[float, float, float]] = []
    low_events: list[int] = []
    high_events: list[int] = []
    low_h: list[float] = []
    high_h: list[float] = []
    low_steps: list[int] = []
    high_steps: list[int] = []
    angle_errors: list[float] = []
    event_matches = 0
    resolved_pairs = 0
    invalid_pairs = 0
    observer = np.array([observer_radius_M, 0.0, 0.0], dtype=np.float64)
    config = DynamicTraceConfig(
        max_lambda=max_lambda,
        rtol=1.0e-8,
        atol=1.0e-10,
        max_step=0.25,
        events=_events(capture_radius_M, escape_radius_M),
    )

    def trace(
        provider: FrozenADMSliceProvider, state: RayState
    ) -> Any:
        if integration_method == "dop853":
            return trace_dynamic_state(provider, state, config)
        return _trace_fixed_rk4(provider, state, config, step_size)

    for time_M in shared_times:
        low_slice = FrozenADMSliceProvider(low, float(time_M))
        high_slice = FrozenADMSliceProvider(high, float(time_M))
        for screen_y in axis:
            for screen_x in axis:
                low_result = trace(
                    low_slice,
                    initial_eulerian_camera_state(
                        low_slice,
                        observer=observer,
                        screen_x=screen_x,
                        screen_y=screen_y,
                    ),
                )
                high_result = trace(
                    high_slice,
                    initial_eulerian_camera_state(
                        high_slice,
                        observer=observer,
                        screen_x=screen_x,
                        screen_y=screen_y,
                    ),
                )
                directions.append((float(time_M), float(screen_x), float(screen_y)))
                low_events.append(EVENT_CODES.get(low_result.event, EVENT_CODES["invalid"]))
                high_events.append(EVENT_CODES.get(high_result.event, EVENT_CODES["invalid"]))
                low_h.append(low_result.h_max_abs)
                high_h.append(high_result.h_max_abs)
                low_steps.append(low_result.steps)
                high_steps.append(high_result.steps)
                angle_error = math.nan
                low_resolved = low_result.event in ("capture", "escape")
                high_resolved = high_result.event in ("capture", "escape")
                if low_resolved and high_resolved:
                    resolved_pairs += 1
                    if low_result.event == high_result.event:
                        event_matches += 1
                    if low_result.event == high_result.event == "escape":
                        angle_error = _angular_error(
                            _escape_direction(low_slice, low_result.final_x, low_result.final_p),
                            _escape_direction(high_slice, high_result.final_x, high_result.final_p),
                        )
                else:
                    invalid_pairs += 1
                angle_errors.append(angle_error)

    angles = np.asarray(angle_errors, dtype=np.float64)
    finite_angles = angles[np.isfinite(angles)]
    total = len(directions)
    event_agreement = event_matches / resolved_pairs if resolved_pairs else 0.0
    report = {
        "schema": SCHEMA,
        "claim": "frozen_slice_two_resolution_nr_optical_convergence",
        "full_dynamic_light_cone_claim": False,
        "configuration": {
            "grid": grid,
            "screen_half_width": screen_half_width,
            "observer_xyz_M": observer.tolist(),
            "capture_radius_M": capture_radius_M,
            "capture_surface": "documented worldtube proxy pending accepted apparent horizons",
            "escape_radius_M": escape_radius_M,
            "times_M": [float(value) for value in shared_times],
            "integration_method": integration_method,
            "step_size_M": step_size if integration_method == "fixed_rk4" else None,
            "dop853_rtol": config.rtol if integration_method == "dop853" else None,
            "dop853_atol": config.atol if integration_method == "dop853" else None,
        },
        "counts": {
            "total": total,
            "resolved_pairs": resolved_pairs,
            "invalid_or_budget_pairs": invalid_pairs,
            "escape_direction_pairs": int(finite_angles.size),
        },
        "event_agreement": event_agreement,
        "escape_direction_error_rad": {
            "median": float(np.median(finite_angles)) if finite_angles.size else math.nan,
            "rms": float(np.sqrt(np.mean(finite_angles**2))) if finite_angles.size else math.nan,
            "max": float(np.max(finite_angles)) if finite_angles.size else math.nan,
        },
        "hamiltonian_max_abs": {
            "low": float(np.nanmax(low_h)),
            "high": float(np.nanmax(high_h)),
        },
        "steps": {
            "low_median": float(np.median(low_steps)),
            "low_max": int(np.max(low_steps)),
            "high_median": float(np.median(high_steps)),
            "high_max": int(np.max(high_steps)),
        },
        "accepted": bool(
            invalid_pairs == 0
            and event_agreement >= 0.98
            and finite_angles.size > 0
            and float(np.median(finite_angles)) < 5.0e-3
        ),
    }
    buffers = {
        "ray_coordinates": np.asarray(directions, dtype=np.float64),
        "low_event_code": np.asarray(low_events, dtype=np.uint8),
        "high_event_code": np.asarray(high_events, dtype=np.uint8),
        "low_h_max_abs": np.asarray(low_h, dtype=np.float64),
        "high_h_max_abs": np.asarray(high_h, dtype=np.float64),
        "low_steps": np.asarray(low_steps, dtype=np.int32),
        "high_steps": np.asarray(high_steps, dtype=np.int32),
        "escape_direction_error_rad": angles,
    }
    return report, buffers


def _write_h5(path: Path, report: dict[str, Any], buffers: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as handle:
        handle.attrs["schema"] = SCHEMA
        handle.attrs["report_json"] = json.dumps(report, sort_keys=True)
        handle.attrs["event_codes_json"] = json.dumps(EVENT_CODES, sort_keys=True)
        for name, values in buffers.items():
            handle.create_dataset(name, data=values, compression="gzip", shuffle=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--low", type=Path, required=True)
    parser.add_argument("--high", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--h5", type=Path)
    parser.add_argument("--grid", type=int, default=7)
    parser.add_argument("--screen-half-width", type=float, default=0.35)
    parser.add_argument(
        "--integration-method",
        choices=("fixed_rk4", "dop853"),
        default="fixed_rk4",
    )
    parser.add_argument("--step-size", type=float, default=0.05)
    args = parser.parse_args()
    report, buffers = validate_nr_pilot_rays(
        args.low,
        args.high,
        grid=args.grid,
        screen_half_width=args.screen_half_width,
        integration_method=args.integration_method,
        step_size=args.step_size,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf8")
    if args.h5 is not None:
        _write_h5(args.h5, report, buffers)
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["accepted"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
