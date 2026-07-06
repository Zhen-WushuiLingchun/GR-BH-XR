"""Plot representative Phase 1 Schwarzschild ray paths."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np
from scipy.integrate import solve_ivp

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from .camera import initial_ray_state
from .geodesic import hamiltonian_rhs, trace_ray
from .metric import horizon_radius
from .types import CameraConfig, MetricParams, TraceConfig


@dataclass(frozen=True)
class RayExample:
    label: str
    alpha: float
    beta: float = 0.0


DEFAULT_EXAMPLES = (
    RayExample("capture", 4.8),
    RayExample("near critical", 3.0 * math.sqrt(3.0)),
    RayExample("escape", 6.2),
)


def _integrate_path(
    params: MetricParams,
    camera: CameraConfig,
    config: TraceConfig,
) -> np.ndarray:
    state = initial_ray_state(params, camera)
    y0 = np.concatenate([state.x, state.p])
    capture_r = horizon_radius(params) + config.horizon_eps
    r_escape = config.r_escape if config.r_escape is not None else 2.0 * camera.r_obs

    def capture_event(_lam: float, y: np.ndarray) -> float:
        return float(y[1] - capture_r)

    capture_event.terminal = True  # type: ignore[attr-defined]
    capture_event.direction = -1.0  # type: ignore[attr-defined]

    def escape_event(_lam: float, y: np.ndarray) -> float:
        return float(y[1] - r_escape)

    escape_event.terminal = True  # type: ignore[attr-defined]
    escape_event.direction = 1.0  # type: ignore[attr-defined]

    sol = solve_ivp(
        lambda lam, y: hamiltonian_rhs(params, lam, y),
        (0.0, config.max_lambda),
        y0,
        method="DOP853",
        rtol=config.rtol,
        atol=config.atol,
        max_step=config.max_step,
        events=[capture_event, escape_event],
    )
    return sol.y.T


def plot_ray_examples(
    *,
    out: Path | str,
    r_obs: float = 80.0,
    max_lambda: float = 600.0,
) -> None:
    """Render capture, near-critical, and escape examples to a PDF."""

    out = Path(out)
    params = MetricParams(M=1.0, a=0.0)
    config = TraceConfig(max_lambda=max_lambda, r_escape=2.0 * r_obs, max_step=1.0)

    fig, ax = plt.subplots(figsize=(7.2, 5.8), constrained_layout=True)
    colors = {"capture": "#c2410c", "near critical": "#7c3aed", "escape": "#0369a1"}

    for example in DEFAULT_EXAMPLES:
        camera = CameraConfig(
            r_obs=r_obs,
            theta_obs=math.pi / 2.0,
            alpha=example.alpha,
            beta=example.beta,
        )
        path = _integrate_path(params, camera, config)
        diagnostics = trace_ray(params, camera, config)
        r = path[:, 1]
        phi = path[:, 3]
        x = r * np.cos(phi)
        y = r * np.sin(phi)
        ax.plot(
            x,
            y,
            color=colors[example.label],
            label=(
                f"{example.label}: b={example.alpha:.4g}, "
                f"event={diagnostics.event}, H={diagnostics.h_max_abs:.1e}"
            ),
        )

    horizon = plt.Circle((0.0, 0.0), horizon_radius(params), color="black", alpha=0.9)
    photon_sphere = plt.Circle(
        (0.0, 0.0),
        3.0 * params.M,
        color="#64748b",
        fill=False,
        linestyle="--",
        linewidth=1.0,
    )
    ax.add_patch(horizon)
    ax.add_patch(photon_sphere)
    ax.scatter([r_obs], [0.0], marker="x", color="#111827", label="observer")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-15.0, r_obs + 5.0)
    ax.set_ylim(-35.0, 35.0)
    ax.set_xlabel("x / M")
    ax.set_ylabel("y / M")
    ax.set_title("Phase 1 Schwarzschild equatorial ray examples")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.25)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("outputs/phase1/ray_examples.pdf"))
    parser.add_argument("--r-obs", type=float, default=80.0)
    parser.add_argument("--max-lambda", type=float, default=600.0)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    plot_ray_examples(out=args.out, r_obs=args.r_obs, max_lambda=args.max_lambda)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
