"""WGPU fixed-step RK4 Kerr lens-map tracing."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np

from gr_bh_xr.gpu import SCHEMA_VERSION
from gr_bh_xr.gpu.backend import backend_info, create_vulkan_device, require_wgpu
from gr_bh_xr.gpu.codes import SCHEMA_EVENT_CODES, SCHEMA_FAILURE_CODES
from gr_bh_xr.metric import horizon_radius
from gr_bh_xr.types import MetricParams, TraceConfig


@dataclass(frozen=True)
class GpuTraceConfig:
    params: MetricParams
    inclination_deg: float
    grid: int
    alpha_max: float
    beta_max: float
    r_obs: float = 100.0
    step_size: float = 0.05
    steps: int = 8000
    horizon_eps: float = TraceConfig.horizon_eps
    axis_eps: float = TraceConfig.axis_eps
    axis_lz_tol: float = TraceConfig.axis_lz_tol

    def __post_init__(self) -> None:
        if self.grid < 2:
            raise ValueError("GPU lens-map grid must contain at least two samples per axis.")
        if self.alpha_max <= 0.0 or self.beta_max <= 0.0:
            raise ValueError("Screen half-widths alpha_max and beta_max must be positive.")
        if self.step_size <= 0.0:
            raise ValueError("Fixed RK4 step_size must be positive.")
        if self.steps <= 0:
            raise ValueError("Fixed RK4 steps must be positive.")

    @property
    def theta_obs(self) -> float:
        return math.radians(self.inclination_deg)

    @property
    def r_escape(self) -> float:
        return 2.0 * self.r_obs

    def axes(self) -> tuple[np.ndarray, np.ndarray]:
        alpha = np.linspace(-self.alpha_max, self.alpha_max, self.grid, dtype=np.float32)
        beta = np.linspace(-self.beta_max, self.beta_max, self.grid, dtype=np.float32)
        return alpha, beta

    def attrs(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "backend": "wgpu",
            "requested_backend": "vulkan",
            "precision": "f32",
            "rk_method": "fixed_step_rk4",
            "step_size": self.step_size,
            "steps": self.steps,
            "M": self.params.M,
            "a": self.params.a,
            "inclination_deg": self.inclination_deg,
            "r_obs": self.r_obs,
            "grid": self.grid,
            "alpha_max": self.alpha_max,
            "beta_max": self.beta_max,
            "horizon_eps": self.horizon_eps,
            "axis_eps": self.axis_eps,
            "axis_lz_tol": self.axis_lz_tol,
            "coordinate_system": "Boyer-Lindquist exterior",
            "units": "G = c = M = 1 unless attrs[M] differs",
        }


@dataclass(frozen=True)
class GpuLensMap:
    config: GpuTraceConfig
    backend: dict[str, Any]
    alpha: np.ndarray
    beta: np.ndarray
    event_code: np.ndarray
    failure_code: np.ndarray
    min_r: np.ndarray
    h_max_abs: np.ndarray
    q_drift_abs: np.ndarray
    steps: np.ndarray
    event_rgba8: np.ndarray
    debug_rgba8: np.ndarray

    @property
    def event_counts(self) -> dict[str, int]:
        return {
            event: int(np.count_nonzero(self.event_code == code))
            for event, code in SCHEMA_EVENT_CODES.items()
        }

    @property
    def failure_counts(self) -> dict[str, int]:
        return {
            failure: int(np.count_nonzero(self.failure_code == code))
            for failure, code in SCHEMA_FAILURE_CODES.items()
        }


def trace_lens_map(config: GpuTraceConfig) -> GpuLensMap:
    """Run the WGPU Vulkan fixed-step RK4 shader and return diagnostic buffers."""

    wgpu = require_wgpu()
    adapter, device = create_vulkan_device()
    info = backend_info(adapter).as_dict()
    alpha, beta = config.axes()
    n_pixels = config.grid * config.grid

    params = _shader_params(config)
    params_buffer = device.create_buffer_with_data(
        label="gr-bh-xr gpu params",
        data=params,
        usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST,
    )
    out_i32_buffer = device.create_buffer(
        label="gr-bh-xr gpu i32 outputs",
        size=int(n_pixels * 3 * np.dtype(np.int32).itemsize),
        usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_SRC,
    )
    out_f32_buffer = device.create_buffer(
        label="gr-bh-xr gpu f32 outputs",
        size=int(n_pixels * 3 * np.dtype(np.float32).itemsize),
        usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_SRC,
    )

    shader = device.create_shader_module(label="gr-bh-xr gpu rk4 shader", code=WGSL_SHADER)
    pipeline = device.create_compute_pipeline(
        label="gr-bh-xr gpu lens-map pipeline",
        layout="auto",
        compute={"module": shader, "entry_point": "main"},
    )
    bind_group = device.create_bind_group(
        label="gr-bh-xr gpu lens-map bind group",
        layout=pipeline.get_bind_group_layout(0),
        entries=[
            {"binding": 0, "resource": {"buffer": params_buffer}},
            {"binding": 1, "resource": {"buffer": out_i32_buffer}},
            {"binding": 2, "resource": {"buffer": out_f32_buffer}},
        ],
    )
    command_encoder = device.create_command_encoder(label="gr-bh-xr gpu lens-map commands")
    compute_pass = command_encoder.begin_compute_pass()
    compute_pass.set_pipeline(pipeline)
    compute_pass.set_bind_group(0, bind_group, [], 0, 999999)
    workgroups = math.ceil(n_pixels / 64)
    compute_pass.dispatch_workgroups(workgroups)
    compute_pass.end()
    device.queue.submit([command_encoder.finish()])

    out_i32 = np.frombuffer(device.queue.read_buffer(out_i32_buffer), dtype=np.int32).copy()
    out_f32 = np.frombuffer(device.queue.read_buffer(out_f32_buffer), dtype=np.float32).copy()
    out_i32 = out_i32.reshape((n_pixels, 3))
    out_f32 = out_f32.reshape((n_pixels, 3))
    shape = (config.grid, config.grid)
    event_code = out_i32[:, 0].reshape(shape).astype(np.int16)
    failure_code = out_i32[:, 1].reshape(shape).astype(np.int16)
    steps = out_i32[:, 2].reshape(shape).astype(np.int32)
    min_r = out_f32[:, 0].reshape(shape).astype(np.float32)
    h_max_abs = out_f32[:, 1].reshape(shape).astype(np.float32)
    q_drift_abs = out_f32[:, 2].reshape(shape).astype(np.float32)
    event_rgba8 = event_to_rgba8(event_code, failure_code)
    debug_rgba8 = scalar_to_rgba8(np.log10(np.maximum(h_max_abs, 1.0e-12)), invalid=event_code == 3)

    return GpuLensMap(
        config=config,
        backend=info,
        alpha=alpha,
        beta=beta,
        event_code=event_code,
        failure_code=failure_code,
        min_r=min_r,
        h_max_abs=h_max_abs,
        q_drift_abs=q_drift_abs,
        steps=steps,
        event_rgba8=event_rgba8,
        debug_rgba8=debug_rgba8,
    )


def _shader_params(config: GpuTraceConfig) -> np.ndarray:
    alpha_step = 2.0 * config.alpha_max / float(config.grid - 1)
    beta_step = 2.0 * config.beta_max / float(config.grid - 1)
    return np.asarray(
        [
            config.params.M,
            config.params.a,
            config.theta_obs,
            config.r_obs,
            -config.alpha_max,
            -config.beta_max,
            alpha_step,
            beta_step,
            config.horizon_eps,
            config.r_escape,
            config.step_size,
            float(config.steps),
            config.axis_eps,
            config.axis_lz_tol,
            math.pi,
            float(config.grid),
            horizon_radius(config.params),
        ],
        dtype=np.float32,
    )


def event_to_rgba8(event_code: np.ndarray, failure_code: np.ndarray) -> np.ndarray:
    rgba = np.zeros(event_code.shape + (4,), dtype=np.uint8)
    rgba[..., 3] = 255
    rgba[event_code == SCHEMA_EVENT_CODES["capture"]] = np.array([0, 0, 0, 255], dtype=np.uint8)
    rgba[event_code == SCHEMA_EVENT_CODES["escape"]] = np.array([48, 132, 255, 255], dtype=np.uint8)
    rgba[event_code == SCHEMA_EVENT_CODES["disk_crossing"]] = np.array(
        [20, 170, 80, 255], dtype=np.uint8
    )
    invalid = event_code == SCHEMA_EVENT_CODES["invalid"]
    rgba[invalid] = np.array([210, 48, 64, 255], dtype=np.uint8)
    axis = invalid & (failure_code == SCHEMA_FAILURE_CODES["axis_coordinate_singularity"])
    rgba[axis] = np.array([255, 190, 32, 255], dtype=np.uint8)
    return rgba


def scalar_to_rgba8(values: np.ndarray, invalid: np.ndarray | None = None) -> np.ndarray:
    finite = np.isfinite(values)
    if invalid is not None:
        finite &= ~invalid
    rgba = np.zeros(values.shape + (4,), dtype=np.uint8)
    rgba[..., 3] = 255
    if np.any(finite):
        lo = float(np.nanpercentile(values[finite], 2.0))
        hi = float(np.nanpercentile(values[finite], 98.0))
        if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
            lo = float(np.nanmin(values[finite]))
            hi = float(np.nanmax(values[finite]))
        scale = np.clip((values - lo) / max(hi - lo, 1.0e-12), 0.0, 1.0)
        rgba[..., 0] = np.asarray(255.0 * scale, dtype=np.uint8)
        rgba[..., 1] = np.asarray(210.0 * (1.0 - np.abs(scale - 0.5) * 2.0), dtype=np.uint8)
        rgba[..., 2] = np.asarray(255.0 * (1.0 - scale), dtype=np.uint8)
    rgba[~finite] = np.array([45, 45, 45, 255], dtype=np.uint8)
    if invalid is not None:
        rgba[invalid] = np.array([210, 48, 64, 255], dtype=np.uint8)
    return rgba


WGSL_SHADER = r"""
const EVENT_CAPTURE: i32 = 0;
const EVENT_ESCAPE: i32 = 1;
const EVENT_INVALID: i32 = 3;
const FAILURE_NONE: i32 = 0;
const FAILURE_UNCLASSIFIED_MAX_LAMBDA: i32 = 2;
const FAILURE_SOLVER_FAILURE: i32 = 3;
const FAILURE_AXIS_COORDINATE_SINGULARITY: i32 = 4;

@group(0) @binding(0) var<storage, read> params: array<f32>;
@group(0) @binding(1) var<storage, read_write> out_i32: array<i32>;
@group(0) @binding(2) var<storage, read_write> out_f32: array<f32>;

struct State {
    t: f32,
    r: f32,
    th: f32,
    ph: f32,
    pt: f32,
    pr: f32,
    pth: f32,
    pph: f32,
};

fn sigma(r: f32, th: f32, a: f32) -> f32 {
    let c = cos(th);
    return r * r + a * a * c * c;
}

fn delta(r: f32, m: f32, a: f32) -> f32 {
    return r * r - 2.0 * m * r + a * a;
}

fn qder(value: f32, deriv: f32, denom: f32, denom_deriv: f32) -> f32 {
    return (deriv * denom - value * denom_deriv) / (denom * denom);
}

fn is_bad(v: f32) -> bool {
    return (v != v) || abs(v) > 1.0e30;
}

fn clamp_s2(s2: f32) -> f32 {
    return max(s2, 1.0e-10);
}

fn hamiltonian(s: State) -> f32 {
    let m = params[0];
    let a = params[1];
    let a2 = a * a;
    let sn = sin(s.th);
    let s2 = clamp_s2(sn * sn);
    let sig = sigma(s.r, s.th, a);
    let dlt = delta(s.r, m, a);
    let rp = s.r * s.r + a2;
    let shell = rp * rp - a2 * dlt * s2;
    let gtt = -shell / (sig * dlt);
    let gtp = -2.0 * m * a * s.r / (sig * dlt);
    let grr = dlt / sig;
    let gth = 1.0 / sig;
    let gpp = (dlt - a2 * s2) / (sig * dlt * s2);
    return 0.5 * (
        gtt * s.pt * s.pt
        + 2.0 * gtp * s.pt * s.pph
        + grr * s.pr * s.pr
        + gth * s.pth * s.pth
        + gpp * s.pph * s.pph
    );
}

fn carter_q(s: State) -> f32 {
    let a = params[1];
    let sn = sin(s.th);
    let s2 = clamp_s2(sn * sn);
    let c = cos(s.th);
    let e = -s.pt;
    let lz = s.pph;
    return s.pth * s.pth + c * c * (lz * lz / s2 - a * a * e * e);
}

fn rhs(s: State) -> State {
    let m = params[0];
    let a = params[1];
    let a2 = a * a;
    let r = s.r;
    let th = s.th;
    let sn = sin(th);
    let c = cos(th);
    let s2 = clamp_s2(sn * sn);
    let sig = sigma(r, th, a);
    let dlt = delta(r, m, a);
    let r2 = r * r;
    let rp = r2 + a2;
    let sig_r = 2.0 * r;
    let sig_t = -2.0 * a2 * sn * c;
    let dlt_r = 2.0 * (r - m);
    let s2_t = 2.0 * sn * c;
    let den = sig * dlt;
    let den_r = sig_r * dlt + sig * dlt_r;
    let den_t = sig_t * dlt;
    let shell = rp * rp - a2 * dlt * s2;
    let shell_r = 4.0 * r * rp - a2 * dlt_r * s2;
    let shell_t = -a2 * dlt * s2_t;
    let dgtt_r = -qder(shell, shell_r, den, den_r);
    let dgtt_t = -qder(shell, shell_t, den, den_t);
    let gtphi_num = -2.0 * m * a * r;
    let gtphi_num_r = -2.0 * m * a;
    let dgtp_r = qder(gtphi_num, gtphi_num_r, den, den_r);
    let dgtp_t = qder(gtphi_num, 0.0, den, den_t);
    let dgrr_r = qder(dlt, dlt_r, sig, sig_r);
    let dgrr_t = qder(dlt, 0.0, sig, sig_t);
    let dgth_r = -sig_r / (sig * sig);
    let dgth_t = -sig_t / (sig * sig);
    let gpp_num = dlt - a2 * s2;
    let gpp_num_r = dlt_r;
    let gpp_num_t = -a2 * s2_t;
    let gpp_den = sig * dlt * s2;
    let gpp_den_r = den_r * s2;
    let gpp_den_t = den_t * s2 + den * s2_t;
    let dgpp_r = qder(gpp_num, gpp_num_r, gpp_den, gpp_den_r);
    let dgpp_t = qder(gpp_num, gpp_num_t, gpp_den, gpp_den_t);
    let gtt = -shell / den;
    let gtp = gtphi_num / den;
    let grr = dlt / sig;
    let gth = 1.0 / sig;
    let gpp = gpp_num / gpp_den;
    let dpr = -0.5 * (
        dgtt_r * s.pt * s.pt
        + 2.0 * dgtp_r * s.pt * s.pph
        + dgrr_r * s.pr * s.pr
        + dgth_r * s.pth * s.pth
        + dgpp_r * s.pph * s.pph
    );
    let dpth = -0.5 * (
        dgtt_t * s.pt * s.pt
        + 2.0 * dgtp_t * s.pt * s.pph
        + dgrr_t * s.pr * s.pr
        + dgth_t * s.pth * s.pth
        + dgpp_t * s.pph * s.pph
    );
    return State(
        gtt * s.pt + gtp * s.pph,
        grr * s.pr,
        gth * s.pth,
        gtp * s.pt + gpp * s.pph,
        0.0,
        dpr,
        dpth,
        0.0,
    );
}

fn add_scaled(s: State, k: State, h: f32) -> State {
    return State(
        s.t + h * k.t,
        s.r + h * k.r,
        s.th + h * k.th,
        s.ph + h * k.ph,
        s.pt + h * k.pt,
        s.pr + h * k.pr,
        s.pth + h * k.pth,
        s.pph + h * k.pph,
    );
}

fn rk4_step(s: State, h: f32) -> State {
    let k1 = rhs(s);
    let k2 = rhs(add_scaled(s, k1, 0.5 * h));
    let k3 = rhs(add_scaled(s, k2, 0.5 * h));
    let k4 = rhs(add_scaled(s, k3, h));
    return State(
        s.t + h * (k1.t + 2.0 * k2.t + 2.0 * k3.t + k4.t) / 6.0,
        s.r + h * (k1.r + 2.0 * k2.r + 2.0 * k3.r + k4.r) / 6.0,
        s.th + h * (k1.th + 2.0 * k2.th + 2.0 * k3.th + k4.th) / 6.0,
        s.ph + h * (k1.ph + 2.0 * k2.ph + 2.0 * k3.ph + k4.ph) / 6.0,
        s.pt,
        s.pr + h * (k1.pr + 2.0 * k2.pr + 2.0 * k3.pr + k4.pr) / 6.0,
        s.pth + h * (k1.pth + 2.0 * k2.pth + 2.0 * k3.pth + k4.pth) / 6.0,
        s.pph,
    );
}

fn initial_state(alpha: f32, beta: f32) -> State {
    let m = params[0];
    let a = params[1];
    let theta = params[2];
    let r_obs = params[3];
    let sn = sin(theta);
    let c = cos(theta);
    let s2 = clamp_s2(sn * sn);
    let e = 1.0;
    let lz = -alpha * sn;
    let q = beta * beta + c * c * (alpha * alpha - a * a);
    let pth2 = max(q - c * c * (lz * lz / s2 - a * a * e * e), 0.0);
    let pth_sign = select(1.0, -1.0, beta < 0.0);
    var s = State(0.0, r_obs, theta, 0.0, -e, 0.0, pth_sign * sqrt(pth2), lz);
    let a2 = a * a;
    let sig = sigma(r_obs, theta, a);
    let dlt = delta(r_obs, m, a);
    let rp = r_obs * r_obs + a2;
    let shell = rp * rp - a2 * dlt * s2;
    let gtt = -shell / (sig * dlt);
    let gtp = -2.0 * m * a * r_obs / (sig * dlt);
    let grr = dlt / sig;
    let gth = 1.0 / sig;
    let gpp = (dlt - a2 * s2) / (sig * dlt * s2);
    let other = gtt * s.pt * s.pt + 2.0 * gtp * s.pt * s.pph + gth * s.pth * s.pth + gpp * s.pph * s.pph;
    s.pr = -sqrt(max(-other / grr, 0.0));
    return s;
}

fn state_is_bad(s: State) -> bool {
    return is_bad(s.t) || is_bad(s.r) || is_bad(s.th) || is_bad(s.ph)
        || is_bad(s.pt) || is_bad(s.pr) || is_bad(s.pth) || is_bad(s.pph);
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
    let grid = u32(params[15]);
    let pixel_count = grid * grid;
    let idx = gid.x;
    if (idx >= pixel_count) {
        return;
    }
    let row = idx / grid;
    let col = idx - row * grid;
    let alpha = params[4] + f32(col) * params[6];
    let beta = params[5] + f32(row) * params[7];
    let h = params[10];
    let max_steps = u32(params[11]);
    let axis_eps = params[12];
    let axis_lz_tol = params[13];
    let pi = params[14];
    let capture_r = params[16] + params[8];
    let escape_r = params[9];
    var s = initial_state(alpha, beta);
    var event = EVENT_INVALID;
    var failure = FAILURE_UNCLASSIFIED_MAX_LAMBDA;
    var step_count: u32 = 0u;
    var min_r = s.r;
    var h_abs = abs(hamiltonian(s));
    var h_max = h_abs;
    var q0 = carter_q(s);
    var qmin = q0;
    var qmax = q0;
    if (state_is_bad(s)) {
        failure = FAILURE_SOLVER_FAILURE;
    } else {
        for (var i = 0u; i < max_steps; i = i + 1u) {
            s = rk4_step(s, h);
            step_count = i + 1u;
            if (state_is_bad(s) || s.r <= 0.0) {
                failure = FAILURE_SOLVER_FAILURE;
                break;
            }
            min_r = min(min_r, s.r);
            if (abs(s.pph) <= axis_lz_tol && min(s.th, pi - s.th) <= axis_eps) {
                failure = FAILURE_AXIS_COORDINATE_SINGULARITY;
                break;
            }
            if (s.th <= 0.0 || s.th >= pi) {
                failure = FAILURE_SOLVER_FAILURE;
                break;
            }
            h_abs = abs(hamiltonian(s));
            h_max = max(h_max, h_abs);
            let qv = carter_q(s);
            qmin = min(qmin, qv);
            qmax = max(qmax, qv);
            if (s.r <= capture_r) {
                event = EVENT_CAPTURE;
                failure = FAILURE_NONE;
                break;
            }
            if (s.r >= escape_r) {
                event = EVENT_ESCAPE;
                failure = FAILURE_NONE;
                break;
            }
        }
    }
    let ibase = idx * 3u;
    let fbase = idx * 3u;
    out_i32[ibase + 0u] = event;
    out_i32[ibase + 1u] = failure;
    out_i32[ibase + 2u] = i32(step_count);
    out_f32[fbase + 0u] = min_r;
    out_f32[fbase + 1u] = h_max;
    out_f32[fbase + 2u] = qmax - qmin;
}
"""
