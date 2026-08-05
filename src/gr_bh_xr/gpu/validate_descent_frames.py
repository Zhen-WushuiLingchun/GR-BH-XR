"""Deterministic validation gate for the rain-frame descent keyframes.

Two checks, both reproducible from this module alone. No RNG anywhere:
directions come from a Fibonacci sphere, observer positions from the
deterministic rain worldline integrator.

1. **Chart direction.** The batched asymptotic escape-direction extraction in
   `generate_descent_keyframes.batch_escape_directions` is compared against the
   exact per-ray chart conversion (`ks_state_to_bl_state` ->
   `momentum_direction_from_state`), the same path the static maps use.

   This is run at two escape radii on purpose. At `r_escape = 200M` the
   analytic azimuth correction `delta = atan2(a, r) + shift(r)` is only about
   `0.0013 deg`, which is *smaller than the measured agreement itself*, so a
   gate there passes whether the rotation is applied correctly, omitted, or
   sign-flipped. It cannot discriminate. At `r_escape = 20M` the correction is
   large enough to separate the cases, and the gate additionally asserts that
   applying the rotation is better than not applying it, which is a
   dimensionless self-calibrating check on the sign.

2. **Observer-factor packing.** The shader form `E_inf(d) = w + dot(d, xyz)`
   with `eInf = [-et_phi, -et_theta, -et_r, -u_t]` is compared against the
   conserved `p_t` of the launched state, in float64 and float32, with two
   negative controls (permuted leg order, and the sign form that appeared in
   the original prose) that MUST fail.

   Note what this check does and does not cover: `rk4_step_ks` carries `p_t`
   through unmodified, so comparing against the *traced* `p_t` is algebraically
   identical to comparing against the launched one. This is a packing identity
   test, not an integrator test, and is labelled as such. Its value comes from
   the negative controls.

Run:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.validate_descent_frames --out outputs/task8/descent_frames.json
```
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from gr_bh_xr.geodesic_ks import ks_state_to_bl_state
from gr_bh_xr.gpu.codes import SCHEMA_EVENT_CODES
from gr_bh_xr.gpu.generate_descent_keyframes import batch_escape_directions
from gr_bh_xr.gpu.trace_ks import KsGpuTraceConfig, trace_ks_states
from gr_bh_xr.metric_ks import ks_metric
from gr_bh_xr.observers import kerr_rain_tetrad_ks
from gr_bh_xr.sky import momentum_direction_from_state
from gr_bh_xr.types import MetricParams, RayState

DESCENT_VALIDATION_SCHEMA = "gr-bh-xr.task8.descent_frame_validation.v1"

# Minimum sample sizes. Below these the gate fails rather than reporting a
# statistic over a handful of rays.
MIN_DIRECTIONS = 512
MIN_COMPARED = 256

# Hamiltonian residual above which a ray is excluded from the comparison as
# numerically destroyed. Matching the generator's own validity criterion.
HAMILTONIAN_MAX = 1.0e-2
# Excluding more than this fraction means the configuration itself is broken.
MAX_EXCLUDED_FRACTION = 0.35

THRESHOLDS: dict[str, float] = {
    # Regression tripwire at the far escape radius. Measured 0.00263 deg for
    # the traced comparison; this is deliberately NOT the discriminating gate.
    "chart_direction_max_deg_far": 0.0040,
    "chart_direction_median_deg_far": 0.0030,
    # The discriminating gate. Measured 0.106 deg with the correct sign,
    # 0.290 deg with the sign flipped, 0.154 deg with no rotation at all.
    "chart_direction_max_deg_near": 0.15,
    # Packing identity. 1 float32 ULP at E ~ 1 is 1.19e-7, so any threshold
    # below that is unachievable in principle; 4 ULP absorbs different
    # sampling and observer radii.
    "energy_packing_f32": 4.8e-7,
    "energy_packing_f64": 1.0e-14,
    # Negative controls must be nowhere near passing.
    "negative_control_min": 0.1,
}


def deterministic_directions(count: int) -> np.ndarray:
    """Fibonacci-sphere sampling. Deterministic by construction, no RNG."""

    if count < 1:
        raise ValueError("direction count must be positive.")
    index = np.arange(count, dtype=np.float64) + 0.5
    z = 1.0 - 2.0 * index / count
    radius = np.sqrt(np.maximum(1.0 - z * z, 0.0))
    phi = index * math.pi * (3.0 - math.sqrt(5.0))
    return np.stack([radius * np.cos(phi), radius * np.sin(phi), z], axis=1)


def _rain_launch(
    params: MetricParams, position: np.ndarray, directions: np.ndarray
) -> tuple[np.ndarray, dict[str, float]]:
    """Pack past-directed rain-frame launch states and the eInf uniform."""

    tetrad = kerr_rain_tetrad_ks(params, position)
    g_obs = ks_metric(params, position)
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
    e_inf = {
        "u_t": float(g_obs[0] @ tetrad.e_time),
        "et_r": float(g_obs[0] @ tetrad.e_r),
        "et_theta": float(g_obs[0] @ tetrad.e_theta),
        "et_phi": float(g_obs[0] @ tetrad.e_phi),
        "p_t": p[:, 0],
        "null_residual": float(np.max(np.abs(np.einsum("ij,jk,ik->i", q, g_obs, q)))),
    }
    return packed, e_inf


def check_energy_packing(
    params: MetricParams, *, position: np.ndarray, directions: np.ndarray
) -> dict[str, Any]:
    """Compare the shader observer factor against the conserved p_t."""

    if directions.shape[0] < MIN_DIRECTIONS:
        raise ValueError(
            f"energy packing check needs at least {MIN_DIRECTIONS} directions, "
            f"got {directions.shape[0]}."
        )
    _packed, info = _rain_launch(params, position, directions)
    p_t = np.asarray(info["p_t"], dtype=np.float64)

    shipped = np.array([-info["et_phi"], -info["et_theta"], -info["et_r"]], dtype=np.float64)
    w = -info["u_t"]
    e_shader = w + directions @ shipped
    f64_error = float(np.max(np.abs(e_shader - p_t)))

    e32 = np.float32(w) + directions.astype(np.float32) @ shipped.astype(np.float32)
    f32_error = float(np.max(np.abs(e32.astype(np.float64) - p_t)))

    permuted = np.array([-info["et_r"], -info["et_theta"], -info["et_phi"]], dtype=np.float64)
    permuted_error = float(np.max(np.abs((w + directions @ permuted) - p_t)))
    # The sign form that appeared in the original prose: E = -(u_t + n^i e_i_t).
    prose = np.array([info["et_phi"], info["et_theta"], info["et_r"]], dtype=np.float64)
    prose_error = float(np.max(np.abs((w + directions @ prose) - p_t)))

    return {
        "sampleCount": int(directions.shape[0]),
        "eInf": [-info["et_phi"], -info["et_theta"], -info["et_r"], -info["u_t"]],
        "nullResidualMax": info["null_residual"],
        "eInfRange": [float(np.min(p_t)), float(np.max(p_t))],
        "f64MaxAbs": f64_error,
        "f32MaxAbs": f32_error,
        "f32UlpAtUnity": float(2.0**-23),
        "negativeControlPermutedLegOrder": permuted_error,
        "negativeControlProseSignForm": prose_error,
        "note": (
            "p_t is carried unmodified by the RK4 step, so this is a packing "
            "identity test rather than an integrator test; the negative "
            "controls carry the discriminating power."
        ),
    }


def check_chart_directions(
    params: MetricParams,
    *,
    position: np.ndarray,
    directions: np.ndarray,
    r_escape: float,
    step_size: float,
    steps: int,
    max_lambda: float,
) -> dict[str, Any]:
    """Batch versus exact asymptotic direction at one escape radius."""

    if directions.shape[0] < MIN_DIRECTIONS:
        raise ValueError(
            f"chart direction check needs at least {MIN_DIRECTIONS} directions, "
            f"got {directions.shape[0]}."
        )
    packed, _info = _rain_launch(params, position, directions)
    config = KsGpuTraceConfig(
        params=params,
        step_size=step_size,
        steps=steps,
        max_lambda=max_lambda,
        r_escape=r_escape,
        time_orientation=-1.0,
        horizon_eps=1.0,
    )
    result = trace_ks_states(config, packed)
    event = result["event_code"].astype(np.int16)
    escaped = event == SCHEMA_EVENT_CODES["escape"]
    healthy = escaped & (result["h_max_abs"] <= HAMILTONIAN_MAX)
    excluded = int(np.count_nonzero(escaped & ~healthy))

    rotated = batch_escape_directions(
        params, result["final_x"], result["final_p"], healthy, apply_chart_rotation=True
    )
    unrotated = batch_escape_directions(
        params, result["final_x"], result["final_p"], healthy, apply_chart_rotation=False
    )

    exact = np.full((directions.shape[0], 3), np.nan, dtype=np.float64)
    for index in np.flatnonzero(healthy):
        state = RayState(
            x=result["final_x"][index].astype(np.float64),
            p=result["final_p"][index].astype(np.float64),
        )
        bl_state = ks_state_to_bl_state(params, state)
        exact[index] = momentum_direction_from_state(
            params,
            r=float(bl_state.x[1]),
            theta=float(bl_state.x[2]),
            phi=float(bl_state.x[3]),
            p_t=float(bl_state.p[0]),
            p_r=float(bl_state.p[1]),
            p_theta=float(bl_state.p[2]),
            p_phi=float(bl_state.p[3]),
        )[2:]

    finite = (
        np.all(np.isfinite(exact), axis=1)
        & np.all(np.isfinite(rotated), axis=1)
        & np.all(np.isfinite(unrotated), axis=1)
    )
    nonfinite = int(np.count_nonzero(healthy & ~finite))
    compared = healthy & finite
    compared_count = int(np.count_nonzero(compared))
    # Fail closed: never reduce over an empty or tiny set.
    if compared_count < MIN_COMPARED:
        raise RuntimeError(
            f"chart direction check compared only {compared_count} rays at "
            f"r_escape = {r_escape} (minimum {MIN_COMPARED}); refusing to "
            "report a statistic."
        )

    def angles(candidate: np.ndarray) -> np.ndarray:
        dots = np.clip(np.sum(candidate[compared] * exact[compared], axis=1), -1.0, 1.0)
        return np.degrees(np.arccos(dots))

    rotated_deg = angles(rotated)
    unrotated_deg = angles(unrotated)
    return {
        "rEscape": r_escape,
        "launched": int(directions.shape[0]),
        "escaped": int(np.count_nonzero(escaped)),
        "excludedByHamiltonian": excluded,
        "excludedFraction": excluded / max(1, int(np.count_nonzero(escaped))),
        "nonFiniteCount": nonfinite,
        "comparedCount": compared_count,
        "maxDeg": float(np.max(rotated_deg)),
        "medianDeg": float(np.median(rotated_deg)),
        "noRotationMaxDeg": float(np.max(unrotated_deg)),
        "noRotationMedianDeg": float(np.median(unrotated_deg)),
        "rotationIsImprovement": bool(np.max(rotated_deg) < np.max(unrotated_deg)),
    }


def validate_descent_frames(
    *,
    params: MetricParams,
    theta_deg: float,
    r_obs: float,
    direction_count: int,
    r_escape_far: float,
    r_escape_near: float,
    step_size: float,
    steps: int,
    max_lambda: float,
) -> dict[str, Any]:
    from gr_bh_xr.metric_ks import bl_to_ks_cartesian

    theta = math.radians(theta_deg)
    position = np.asarray(bl_to_ks_cartesian(r_obs, theta, 0.0, params.a), dtype=np.float64)
    directions = deterministic_directions(direction_count)

    far = check_chart_directions(
        params,
        position=position,
        directions=directions,
        r_escape=r_escape_far,
        step_size=step_size,
        steps=steps,
        max_lambda=max_lambda,
    )
    near = check_chart_directions(
        params,
        position=position,
        directions=directions,
        r_escape=r_escape_near,
        step_size=step_size,
        steps=steps,
        max_lambda=max_lambda,
    )
    energy = check_energy_packing(params, position=position, directions=directions)

    for report in (far, near):
        if report["excludedFraction"] > MAX_EXCLUDED_FRACTION:
            raise RuntimeError(
                f"chart direction check at r_escape = {report['rEscape']} excluded "
                f"{report['excludedFraction']:.3f} of escaping rays by Hamiltonian "
                f"residual (maximum {MAX_EXCLUDED_FRACTION}); the configuration is broken."
            )
        if report["nonFiniteCount"] > 0:
            raise RuntimeError(
                f"chart direction check at r_escape = {report['rEscape']} produced "
                f"{report['nonFiniteCount']} non-finite directions."
            )

    checks = {
        "chart_direction_max_deg_far": far["maxDeg"],
        "chart_direction_median_deg_far": far["medianDeg"],
        "chart_direction_max_deg_near": near["maxDeg"],
        "energy_packing_f32": energy["f32MaxAbs"],
        "energy_packing_f64": energy["f64MaxAbs"],
    }
    failures = {
        name: {"measured": value, "threshold": THRESHOLDS[name]}
        for name, value in checks.items()
        if not (value <= THRESHOLDS[name])
    }
    if not near["rotationIsImprovement"]:
        failures["rotation_is_improvement"] = {
            "measured": near["maxDeg"],
            "threshold": near["noRotationMaxDeg"],
        }
    for control in ("negativeControlPermutedLegOrder", "negativeControlProseSignForm"):
        if energy[control] <= THRESHOLDS["negative_control_min"]:
            failures[control] = {
                "measured": energy[control],
                "threshold": THRESHOLDS["negative_control_min"],
            }

    return {
        "schema": DESCENT_VALIDATION_SCHEMA,
        "metric": {"M": params.M, "a": params.a, "aOverM": params.a / params.M},
        "observer": {
            "theta_deg": theta_deg,
            "r_obs": r_obs,
            "positionKs": position.tolist(),
            "frame": "Kerr rain (Doran E=1, L=0, Q=0), past-directed launch",
        },
        "sampling": {
            "directions": direction_count,
            "scheme": "Fibonacci sphere, deterministic (no RNG)",
            "hamiltonianMax": HAMILTONIAN_MAX,
        },
        "chartDirectionFar": far,
        "chartDirectionNear": near,
        "energyPacking": energy,
        "checks": checks,
        "thresholds": dict(THRESHOLDS),
        "failures": failures,
        "passed": not failures,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, default=0.9, help="a / M, dimensionless.")
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--theta-deg", type=float, default=60.0)
    parser.add_argument("--r-obs", type=float, default=2.35)
    parser.add_argument("--directions", type=int, default=4096)
    parser.add_argument("--r-escape-far", type=float, default=200.0)
    parser.add_argument("--r-escape-near", type=float, default=20.0)
    parser.add_argument("--step-size", type=float, default=0.01)
    parser.add_argument("--steps", type=int, default=60000)
    parser.add_argument("--max-lambda", type=float, default=1500.0)
    parser.add_argument("--out", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_descent_frames(
        params=MetricParams(M=args.mass, a=args.spin * args.mass),
        theta_deg=args.theta_deg,
        r_obs=args.r_obs,
        direction_count=args.directions,
        r_escape_far=args.r_escape_far,
        r_escape_near=args.r_escape_near,
        step_size=args.step_size,
        steps=args.steps,
        max_lambda=args.max_lambda,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf8")
    print(text)
    return 0 if report["passed"] else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
