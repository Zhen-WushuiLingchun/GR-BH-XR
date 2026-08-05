"""Stage B validation gate for the Kerr-Schild rain (Doran) observer frame.

The rain frame is the E=1, L=0, Q=0 free-fall congruence: observers released
from rest at infinity, falling at constant Boyer-Lindquist polar angle.  It is
the observer frame the horizon-crossing descent path needs, because the static
and ZAMO frames both fail before the horizon while the ingoing Kerr-Schild
chart stays regular through it.

This module is the committed producer for that gate.  It samples a
deterministic grid on both sides of the outer horizon and reports, per zone:

- the four defining constraints (`u.u + 1`, `u_t + 1`, `L_z`, `dtheta/dtau`);
- tetrad Gram orthonormality against `diag(-1, 1, 1, 1)`;
- agreement with an independent closed-form Doran reference, which is the
  check that actually pins the physics: all four constraint residuals can be
  satisfied by the wrong root branch;
- the Schwarzschild `a = 0` radial limit `dr/dtau = -sqrt(2M/r)`;
- a dedicated regression exactly at `r = r_+`, where the normalization
  quadratic degenerates (`quad_a -> 0`) and a naive root formula loses the
  solution entirely.

Run:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_rain_observer --out outputs/tier2/rain_observer_gate.json
```
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from .metric import horizon_radius
from .metric_ks import bl_to_ks_cartesian, ks_metric, ks_radius, ks_radius_gradient
from .observers import (
    RAIN_MIN_SIN_THETA,
    analytic_kerr_rain_velocity_ks,
    kerr_rain_tetrad_ks,
    kerr_rain_velocity_ks,
    ks_gram_matrix,
)
from .types import MetricParams

# Deterministic sampling grid.  No RNG anywhere in this module.
SPINS = (0.0, 0.5, 0.9, 0.998)
THETAS = (0.4, 1.0, math.pi / 2.0, 2.0, 2.7)
EXTERIOR_RADII = (60.0, 20.0, 6.0, 3.0)
HORIZON_OFFSETS = (0.1, 0.01, 1.0e-3)
SCHWARZSCHILD_RADII = (20.0, 8.0, 4.1, 3.0, 1.5)

MINKOWSKI = np.diag([-1.0, 1.0, 1.0, 1.0])

# Committed thresholds.  Every value carries at least an order of magnitude of
# headroom over the measured worst case recorded in
# `docs/validation_targets.md`; see that file for the measured numbers and for
# why the domain excludes the symmetry axis.
THRESHOLDS: dict[str, float] = {
    "u_norm_outside": 1.0e-13,
    "u_norm_at": 1.0e-13,
    "u_norm_inside": 1.0e-12,
    "u_t_plus_one": 1.0e-13,
    "lz": 1.0e-13,
    "dtheta_dtau": 1.0e-11,
    "gram_outside": 1.0e-13,
    "gram_at": 1.0e-13,
    "gram_inside": 1.0e-12,
    "analytic_agreement": 1.0e-13,
    "schwarzschild_radial": 1.0e-13,
    "horizon_exact_u_norm": 1.0e-13,
}

# `L_z` is dimensionful and grows like `r`, so the gate is stated on a bounded
# radial domain rather than as a scale-free number.
LZ_DOMAIN_R_MAX = 60.0


def _zone(radius: float, r_plus: float) -> str:
    if radius >= r_plus + 0.1:
        return "outside"
    if radius < r_plus - 1.0e-3:
        return "inside"
    return "at"


def _sample(params: MetricParams, radius: float, theta: float) -> dict[str, float]:
    """Return all residuals for one (spin, radius, theta) sample."""

    xyz = np.asarray(bl_to_ks_cartesian(radius, theta, 0.0, params.a), dtype=np.float64)
    g = ks_metric(params, xyz)
    u = kerr_rain_velocity_ks(params, xyz)
    grad_r = ks_radius_gradient(params, xyz)

    u_norm = float(u @ g @ u) + 1.0
    u_t = float(g[0] @ u) + 1.0
    lz = -float(xyz[1]) * float(g[1] @ u) + float(xyz[0]) * float(g[2] @ u)
    # d(cos theta)/dtau = (r u^z - z grad_r . u_spatial) / r^2.
    dtheta = (ks_radius(params, xyz) * u[3] - float(xyz[2]) * float(grad_r @ u[1:4])) / (
        ks_radius(params, xyz) ** 2
    )

    tetrad = kerr_rain_tetrad_ks(params, xyz)
    gram = float(np.max(np.abs(ks_gram_matrix(params, tetrad) - MINKOWSKI)))
    analytic = float(np.max(np.abs(u - analytic_kerr_rain_velocity_ks(params, radius, theta))))

    return {
        "u_norm_plus_one": abs(u_norm),
        "u_t_plus_one": abs(u_t),
        "lz": abs(lz),
        "dtheta_dtau": abs(dtheta),
        "gram": gram,
        "analytic": analytic,
    }


def run_gate() -> dict[str, Any]:
    """Evaluate the full deterministic rain-observer gate."""

    zones: dict[str, dict[str, float]] = {
        zone: {key: 0.0 for key in ("u_norm_plus_one", "u_t_plus_one", "lz", "dtheta_dtau", "gram", "analytic")}
        for zone in ("outside", "at", "inside")
    }
    counts = {"outside": 0, "at": 0, "inside": 0}

    for spin in SPINS:
        params = MetricParams(M=1.0, a=spin)
        r_plus = horizon_radius(params)
        r_minus = params.M - math.sqrt(max(params.M**2 - params.a**2, 0.0))
        radii = list(EXTERIOR_RADII)
        for offset in HORIZON_OFFSETS:
            radii.append(r_plus + offset)
            interior = r_plus - offset
            # Stay above the inner horizon: the mass-inflation region is not
            # part of this gate's claim.
            if interior > r_minus + 0.05:
                radii.append(interior)
        for radius in radii:
            if radius <= 0.2:
                continue
            for theta in THETAS:
                zone = _zone(radius, r_plus)
                sample = _sample(params, radius, theta)
                counts[zone] += 1
                for key, value in sample.items():
                    if key == "lz" and radius > LZ_DOMAIN_R_MAX:
                        continue
                    zones[zone][key] = max(zones[zone][key], value)

    # Fail closed: a zone with no samples would otherwise report a max of 0.0
    # and pass vacuously.
    for zone, count in counts.items():
        if count == 0:
            raise RuntimeError(f"Rain gate produced no samples for the '{zone}' zone.")

    # Dedicated regression exactly on the outer horizon, where the
    # normalization quadratic degenerates.
    horizon_exact: dict[str, float] = {"u_norm_plus_one": 0.0, "analytic": 0.0}
    horizon_samples = 0
    for spin in (0.0, 0.9, 0.998):
        params = MetricParams(M=1.0, a=spin)
        r_plus = horizon_radius(params)
        for theta in (0.4, math.pi / 2.0):
            xyz = np.asarray(bl_to_ks_cartesian(r_plus, theta, 0.0, spin), dtype=np.float64)
            g = ks_metric(params, xyz)
            u = kerr_rain_velocity_ks(params, xyz)
            horizon_exact["u_norm_plus_one"] = max(
                horizon_exact["u_norm_plus_one"], abs(float(u @ g @ u) + 1.0)
            )
            horizon_exact["analytic"] = max(
                horizon_exact["analytic"],
                float(np.max(np.abs(u - analytic_kerr_rain_velocity_ks(params, r_plus, theta)))),
            )
            horizon_samples += 1
    if horizon_samples == 0:
        raise RuntimeError("Rain gate produced no exact-horizon samples.")

    # Schwarzschild radial free-fall limit, evaluated at exact radii.
    schwarzschild = MetricParams(M=1.0, a=0.0)
    schwarzschild_worst = 0.0
    schwarzschild_rows: list[dict[str, float]] = []
    for radius in SCHWARZSCHILD_RADII:
        xyz = np.asarray(bl_to_ks_cartesian(radius, math.pi / 2.0, 0.0, 0.0), dtype=np.float64)
        u = kerr_rain_velocity_ks(schwarzschild, xyz)
        dr_dtau = float(ks_radius_gradient(schwarzschild, xyz) @ u[1:4])
        expected = -math.sqrt(2.0 * schwarzschild.M / radius)
        error = abs(dr_dtau - expected)
        schwarzschild_worst = max(schwarzschild_worst, error)
        schwarzschild_rows.append(
            {"r": radius, "dr_dtau": dr_dtau, "expected": expected, "abs_error": error}
        )
    if not schwarzschild_rows:
        raise RuntimeError("Rain gate produced no Schwarzschild-limit samples.")

    checks = {
        "u_norm_outside": zones["outside"]["u_norm_plus_one"],
        "u_norm_at": zones["at"]["u_norm_plus_one"],
        "u_norm_inside": zones["inside"]["u_norm_plus_one"],
        "u_t_plus_one": max(zones[z]["u_t_plus_one"] for z in zones),
        "lz": max(zones[z]["lz"] for z in zones),
        "dtheta_dtau": max(zones[z]["dtheta_dtau"] for z in zones),
        "gram_outside": zones["outside"]["gram"],
        "gram_at": zones["at"]["gram"],
        "gram_inside": zones["inside"]["gram"],
        "analytic_agreement": max(zones[z]["analytic"] for z in zones),
        "schwarzschild_radial": schwarzschild_worst,
        "horizon_exact_u_norm": horizon_exact["u_norm_plus_one"],
    }
    failures = {
        name: {"measured": value, "threshold": THRESHOLDS[name]}
        for name, value in checks.items()
        if not (value <= THRESHOLDS[name])
    }

    return {
        "schema": "gr-bh-xr.task8.rain_observer_gate.v1",
        "observer": "Kerr rain frame (Doran E=1, L=0, Q=0), Cartesian Kerr-Schild chart",
        "domain": {
            "spins_aOverM": list(SPINS),
            "thetaRad": list(THETAS),
            "exteriorRadiiM": list(EXTERIOR_RADII),
            "horizonOffsetsM": list(HORIZON_OFFSETS),
            "minSinTheta": RAIN_MIN_SIN_THETA,
            "lzDomainRMax": LZ_DOMAIN_R_MAX,
            "note": (
                "The symmetry axis is excluded by construction: the constraint "
                "matrix loses rank there and its condition number grows like "
                "6 / theta, so the velocity error scales as 2e-16 / theta. "
                "Interior samples stay above the inner horizon; the "
                "mass-inflation region is out of scope."
            ),
        },
        "sampleCounts": counts,
        "horizonExactSamples": horizon_samples,
        "zones": zones,
        "horizonExact": horizon_exact,
        "schwarzschildLimit": schwarzschild_rows,
        "checks": checks,
        "thresholds": dict(THRESHOLDS),
        "failures": failures,
        "passed": not failures,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None, help="Optional JSON output path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_gate()
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf8")
    print(text)
    return 0 if report["passed"] else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
