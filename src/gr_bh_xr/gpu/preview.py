"""XR-oriented PC debug preview for the Task 4 GPU lens-map texture contract."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import time

import numpy as np

from gr_bh_xr.gpu.generate_lens_map import write_gpu_lens_map
from gr_bh_xr.gpu.trace import GpuLensMap, GpuTraceConfig, scalar_to_rgba8, trace_lens_map
from gr_bh_xr.types import MetricParams


@dataclass
class PreviewState:
    spin: float
    inclination_deg: float
    alpha_max: float
    beta_max: float
    view_index: int
    lens_map: GpuLensMap
    rgba: np.ndarray


VIEW_NAMES = ("event", "min_r", "h_residual", "q_drift")
PREVIEW_ENVELOPE_MIN_INCLINATION_DEG = 20.0
PREVIEW_ENVELOPE_MAX_INCLINATION_DEG = 160.0
PREVIEW_ENVELOPE_MAX_ABS_SPIN = 0.95


def preview_envelope_warning(spin: float, inclination_deg: float) -> str:
    """Return a title-bar warning for known f32 fixed-step preview limits."""
    outside_inclination = not (
        PREVIEW_ENVELOPE_MIN_INCLINATION_DEG
        <= inclination_deg
        <= PREVIEW_ENVELOPE_MAX_INCLINATION_DEG
    )
    outside_spin = abs(spin) > PREVIEW_ENVELOPE_MAX_ABS_SPIN
    if outside_inclination or outside_spin:
        return " | WARNING: outside f32 preview envelope"
    return ""


def build_config(
    *,
    mass: float,
    spin: float,
    inclination_deg: float,
    grid: int,
    alpha_max: float,
    beta_max: float,
    r_obs: float,
    step_size: float,
    steps: int,
    horizon_eps: float,
    critical_refine_band: float,
    critical_refine_factor: int,
) -> GpuTraceConfig:
    return GpuTraceConfig(
        params=MetricParams(M=mass, a=spin * mass),
        inclination_deg=inclination_deg,
        grid=grid,
        alpha_max=alpha_max,
        beta_max=beta_max,
        r_obs=r_obs,
        step_size=step_size,
        steps=steps,
        horizon_eps=horizon_eps,
        critical_refine_band=critical_refine_band,
        critical_refine_factor=critical_refine_factor,
    )


def view_rgba(lens_map: GpuLensMap, view_name: str) -> np.ndarray:
    invalid = lens_map.event_code == 3
    if view_name == "event":
        return lens_map.event_rgba8
    if view_name == "min_r":
        return scalar_to_rgba8(lens_map.min_r, invalid=invalid)
    if view_name == "h_residual":
        return scalar_to_rgba8(np.log10(np.maximum(lens_map.h_max_abs, 1.0e-12)), invalid=invalid)
    if view_name == "q_drift":
        return scalar_to_rgba8(np.log10(np.maximum(lens_map.q_drift_abs, 1.0e-12)), invalid=invalid)
    raise ValueError(f"Unknown preview view: {view_name}")


def save_snapshot(state: PreviewState, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    path = out_dir / (
        f"gpu_preview_{timestamp}_a{state.spin:.3f}_i{state.inclination_deg:.1f}.h5"
    )
    write_gpu_lens_map(path, state.lens_map, command="gr_bh_xr.gpu.preview interactive save")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spin", type=float, required=True)
    parser.add_argument("--mass", type=float, default=1.0)
    parser.add_argument("--inclination-deg", type=float, required=True)
    parser.add_argument("--grid", type=int, default=256)
    parser.add_argument("--alpha-max", type=float, required=True)
    parser.add_argument("--beta-max", type=float, required=True)
    parser.add_argument("--r-obs", type=float, default=100.0)
    parser.add_argument("--step-size", type=float, default=GpuTraceConfig.step_size)
    parser.add_argument("--steps", type=int, default=GpuTraceConfig.steps)
    parser.add_argument("--horizon-eps", type=float, default=GpuTraceConfig.horizon_eps)
    parser.add_argument("--critical-refine-band", type=float, default=0.0)
    parser.add_argument(
        "--critical-refine-factor", type=int, default=GpuTraceConfig.critical_refine_factor
    )
    parser.add_argument("--save-dir", type=Path, default=Path("outputs/phase2"))
    parser.add_argument("--save-and-exit", type=Path, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = build_config(
        mass=args.mass,
        spin=args.spin,
        inclination_deg=args.inclination_deg,
        grid=args.grid,
        alpha_max=args.alpha_max,
        beta_max=args.beta_max,
        r_obs=args.r_obs,
        step_size=args.step_size,
        steps=args.steps,
        horizon_eps=args.horizon_eps,
        critical_refine_band=args.critical_refine_band,
        critical_refine_factor=args.critical_refine_factor,
    )
    lens_map = trace_lens_map(config)
    state = PreviewState(
        spin=args.spin,
        inclination_deg=args.inclination_deg,
        alpha_max=args.alpha_max,
        beta_max=args.beta_max,
        view_index=0,
        lens_map=lens_map,
        rgba=view_rgba(lens_map, VIEW_NAMES[0]),
    )
    if args.save_and_exit is not None:
        write_gpu_lens_map(args.save_and_exit, lens_map, command="gr_bh_xr.gpu.preview save-and-exit")
        return

    from rendercanvas.auto import RenderCanvas, loop

    canvas = RenderCanvas(size=(args.grid, args.grid), title=_title(state))
    context = canvas.get_context("bitmap")

    def redraw() -> None:
        context.set_bitmap(np.flipud(state.rgba))

    def recompute() -> None:
        cfg = build_config(
            mass=args.mass,
            spin=state.spin,
            inclination_deg=state.inclination_deg,
            grid=args.grid,
            alpha_max=state.alpha_max,
            beta_max=state.beta_max,
            r_obs=args.r_obs,
            step_size=args.step_size,
            steps=args.steps,
            horizon_eps=args.horizon_eps,
            critical_refine_band=args.critical_refine_band,
            critical_refine_factor=args.critical_refine_factor,
        )
        state.lens_map = trace_lens_map(cfg)
        state.rgba = view_rgba(state.lens_map, VIEW_NAMES[state.view_index])
        canvas.set_title(_title(state))
        canvas.request_draw(redraw)

    @canvas.add_event_handler("key_down")
    def on_key(event):
        key = str(event.get("key", event.get("key_code", ""))).lower()
        if key in ("escape", "esc"):
            canvas.close()
        elif key == "a":
            state.spin = max(0.0, state.spin - 0.05)
            recompute()
        elif key == "z":
            state.spin = min(0.99, state.spin + 0.05)
            recompute()
        elif key == "i":
            state.inclination_deg = max(1.0, state.inclination_deg - 5.0)
            recompute()
        elif key == "k":
            state.inclination_deg = min(179.0, state.inclination_deg + 5.0)
            recompute()
        elif key in ("+", "="):
            state.alpha_max *= 1.1
            state.beta_max *= 1.1
            recompute()
        elif key in ("-", "_"):
            state.alpha_max = max(1.0, state.alpha_max / 1.1)
            state.beta_max = max(1.0, state.beta_max / 1.1)
            recompute()
        elif key == "d":
            state.view_index = (state.view_index + 1) % len(VIEW_NAMES)
            state.rgba = view_rgba(state.lens_map, VIEW_NAMES[state.view_index])
            canvas.set_title(_title(state))
            canvas.request_draw(redraw)
        elif key == "s":
            path = save_snapshot(state, args.save_dir)
            canvas.set_title(f"{_title(state)} saved {path.name}")

    canvas.request_draw(redraw)
    loop.run()


def _title(state: PreviewState) -> str:
    warning = preview_envelope_warning(state.spin, state.inclination_deg)
    return (
        f"GR-BH-XR GPU preview | a={state.spin:.2f} | i={state.inclination_deg:.1f} | "
        f"view={VIEW_NAMES[state.view_index]}{warning}"
    )


if __name__ == "__main__":
    main()
