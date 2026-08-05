"""WGPU fixed-step RK4 Kerr-Schild geodesic tracing.

This module is intentionally separate from :mod:`gr_bh_xr.gpu.trace`, whose
shader is the audited Boyer-Lindquist exterior Task 4 path.  The functions here
accept explicit Kerr-Schild canonical initial states so the first GPU migration
validates the horizon-penetrating Hamiltonian RHS without mixing in a new GPU
camera initializer.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np

from gr_bh_xr.camera import initial_ray_state, initial_ray_state_from_unity_direction
from gr_bh_xr.geodesic_ks import bl_state_to_ks_state, _inner_capture_radius
from gr_bh_xr.gpu.backend import backend_info, create_vulkan_device, require_wgpu
from gr_bh_xr.gpu.codes import SCHEMA_EVENT_CODES, SCHEMA_FAILURE_CODES
from gr_bh_xr.metric import horizon_radius
from gr_bh_xr.sky import escape_direction_or_nan
from gr_bh_xr.types import CameraConfig, MetricParams, RayState, TraceConfig


_KS_TRACE_CONTEXT = None
KS_INPUTS_PER_RAY = 8
KS_DISK_MAX_ORDER = 2
KS_F32_OUTPUTS_PER_RAY = 12 + 4 * KS_DISK_MAX_ORDER


@dataclass(frozen=True)
class KsGpuTraceConfig:
    """Settings for the f32 fixed-step Kerr-Schild GPU tracer."""

    params: MetricParams
    step_size: float = 0.01
    steps: int = 20000
    max_lambda: float = 800.0
    max_step: float = 1.0
    step_r_ref: float = 5.0
    adaptive_step: bool = True
    r_escape: float = 200.0
    horizon_eps: float = TraceConfig.horizon_eps
    sphere_center_xyz: tuple[float, float, float] | None = None
    sphere_radius: float = 0.0
    # Equatorial disk-crossing recording (z = 0 plane, trivial in the
    # Cartesian chart). Disabled when disk_r_out <= 0 so existing gates are
    # untouched. Recorded phi/t are converted to Boyer-Lindquist so the
    # values interoperate with the BL-generated transfer maps.
    disk_r_in: float = 0.0
    disk_r_out: float = 0.0
    # +1 for future-directed rays (exterior emit-forward convention), -1 for
    # past-directed history tracing (interior views: the future cone points
    # inward inside the horizon, so images are built from where the light
    # came from). Only flips the conserved-quantity signs fed to the disk
    # redshift; the Hamiltonian flow itself is orientation-blind.
    time_orientation: float = 1.0

    def __post_init__(self) -> None:
        if self.step_size <= 0.0:
            raise ValueError("step_size must be positive.")
        if self.steps <= 0:
            raise ValueError("steps must be positive.")
        if self.max_lambda <= 0.0:
            raise ValueError("max_lambda must be positive.")
        if self.max_step <= 0.0:
            raise ValueError("max_step must be positive.")
        if self.step_r_ref <= 0.0:
            raise ValueError("step_r_ref must be positive.")
        if self.r_escape <= 0.0:
            raise ValueError("r_escape must be positive.")
        if self.sphere_center_xyz is not None:
            if len(self.sphere_center_xyz) != 3:
                raise ValueError("sphere_center_xyz must contain three values.")
            if self.sphere_radius <= 0.0:
                raise ValueError("sphere_radius must be positive when a sphere target is configured.")
        if self.disk_r_out > 0.0:
            # `ks_phi_shift` / `ks_time_shift` diverge logarithmically at r_+,
            # and their derivative a/Delta blows up alongside. Recording a
            # crossing near the horizon would emit a large finite garbage value
            # rather than fail. Astrophysically the disk never reaches there
            # anyway (the inner edge is the ISCO), so require the margin
            # explicitly instead of relying on every caller to supply it.
            r_plus = horizon_radius(self.params)
            if self.disk_r_in <= r_plus + 0.25 * self.params.M:
                raise ValueError(
                    f"disk_r_in ({self.disk_r_in}) must clear the outer horizon "
                    f"({r_plus}) by 0.25 M: the Boyer-Lindquist azimuth/time "
                    "shifts used to report crossings diverge there."
                )
            if self.disk_r_out <= self.disk_r_in:
                raise ValueError("disk_r_out must exceed disk_r_in.")

    @property
    def capture_r(self) -> float:
        return _inner_capture_radius(self.params, self.horizon_eps)

    def attrs(self) -> dict[str, Any]:
        return {
            "backend": "wgpu",
            "requested_backend": "vulkan",
            "precision": "f32",
            "rk_method": "fixed_step_rk4",
            "coordinate_system": "ingoing Cartesian Kerr-Schild",
            "M": self.params.M,
            "a": self.params.a,
            "step_size": self.step_size,
            "steps": self.steps,
            "max_lambda": self.max_lambda,
            "max_step": self.max_step,
            "step_r_ref": self.step_r_ref,
            "adaptive_step": self.adaptive_step,
            "r_escape": self.r_escape,
            "horizon_eps": self.horizon_eps,
            "capture_r": self.capture_r,
            "sphere_center_xyz": self.sphere_center_xyz,
            "sphere_radius": self.sphere_radius,
            "disk_r_in": self.disk_r_in,
            "disk_r_out": self.disk_r_out,
        }


def ks_states_from_screen_points(
    *,
    params: MetricParams,
    inclination_deg: float,
    r_obs: float,
    alpha: np.ndarray,
    beta: np.ndarray,
) -> list[RayState]:
    """Initialize Bardeen screen rays and transform them to Kerr-Schild states."""

    theta_obs = math.radians(inclination_deg)
    aa = np.asarray(alpha, dtype=np.float64).ravel()
    bb = np.asarray(beta, dtype=np.float64).ravel()
    if aa.shape != bb.shape:
        raise ValueError("alpha and beta must have the same flattened shape.")
    states: list[RayState] = []
    for alpha_value, beta_value in zip(aa, bb):
        bl_state = initial_ray_state(
            params,
            CameraConfig(
                r_obs=r_obs,
                theta_obs=theta_obs,
                alpha=float(alpha_value),
                beta=float(beta_value),
            ),
        )
        states.append(bl_state_to_ks_state(params, bl_state))
    return states


def ks_states_from_unity_directions(
    *,
    params: MetricParams,
    inclination_deg: float,
    r_obs: float,
    directions_unity: np.ndarray,
) -> list[RayState]:
    """Initialize finite-observer Unity directions and transform to KS states."""

    theta_obs = math.radians(inclination_deg)
    directions = np.asarray(directions_unity, dtype=np.float64)
    if directions.ndim != 2 or directions.shape[1] != 3:
        raise ValueError("directions_unity must have shape (N, 3).")
    states: list[RayState] = []
    for direction in directions:
        bl_state = initial_ray_state_from_unity_direction(
            params,
            r_obs=r_obs,
            theta_obs=theta_obs,
            direction_unity=direction,
        )
        states.append(bl_state_to_ks_state(params, bl_state))
    return states


def trace_ks_states(
    config: KsGpuTraceConfig,
    states: "list[RayState] | tuple[RayState, ...] | np.ndarray",
) -> dict[str, Any]:
    """Trace explicit Kerr-Schild canonical states on the WGPU Vulkan backend.

    Accepts either RayState sequences or an already packed float32 array of
    shape (N, 8) = [x^0..x^3, p_0..p_3] for batch callers.
    """

    wgpu, _adapter, device, pipeline, info = _get_ks_trace_context()
    n_rays = len(states)
    if n_rays == 0:
        return _empty_result(info)
    if isinstance(states, np.ndarray):
        if states.ndim != 2 or states.shape[1] != KS_INPUTS_PER_RAY:
            raise ValueError("Packed states must have shape (N, 8).")
        inputs = np.ascontiguousarray(states, dtype=np.float32)
    else:
        inputs = _pack_states(states)
    params = _shader_params(config, n_rays)
    params_buffer = device.create_buffer_with_data(
        label="gr-bh-xr ks gpu params",
        data=params,
        usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST,
    )
    input_buffer = device.create_buffer_with_data(
        label="gr-bh-xr ks gpu initial states",
        data=inputs,
        usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST,
    )
    out_i32_buffer = device.create_buffer(
        label="gr-bh-xr ks gpu i32 outputs",
        size=int(n_rays * 3 * np.dtype(np.int32).itemsize),
        usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_SRC,
    )
    out_f32_buffer = device.create_buffer(
        label="gr-bh-xr ks gpu f32 outputs",
        size=int(n_rays * KS_F32_OUTPUTS_PER_RAY * np.dtype(np.float32).itemsize),
        usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_SRC,
    )
    bind_group = device.create_bind_group(
        label="gr-bh-xr ks gpu bind group",
        layout=pipeline.get_bind_group_layout(0),
        entries=[
            {"binding": 0, "resource": {"buffer": params_buffer}},
            {"binding": 1, "resource": {"buffer": input_buffer}},
            {"binding": 2, "resource": {"buffer": out_i32_buffer}},
            {"binding": 3, "resource": {"buffer": out_f32_buffer}},
        ],
    )
    command_encoder = device.create_command_encoder(label="gr-bh-xr ks gpu commands")
    compute_pass = command_encoder.begin_compute_pass()
    compute_pass.set_pipeline(pipeline)
    compute_pass.set_bind_group(0, bind_group)
    compute_pass.dispatch_workgroups(math.ceil(n_rays / 64))
    compute_pass.end()
    device.queue.submit([command_encoder.finish()])

    out_i32 = np.frombuffer(device.queue.read_buffer(out_i32_buffer), dtype=np.int32).copy()
    out_f32 = np.frombuffer(device.queue.read_buffer(out_f32_buffer), dtype=np.float32).copy()
    out_i32 = out_i32.reshape((n_rays, 3))
    out_f32 = out_f32.reshape((n_rays, KS_F32_OUTPUTS_PER_RAY))
    return {
        "backend": info,
        "event_code": out_i32[:, 0],
        "failure_code": out_i32[:, 1],
        "steps": out_i32[:, 2],
        "min_r": out_f32[:, 0],
        "h_max_abs": out_f32[:, 1],
        "final_r": out_f32[:, 2],
        "lambda_end": out_f32[:, 3],
        "final_x": out_f32[:, 4:8],
        "final_p": out_f32[:, 8:12],
        "disk_r_m": np.stack([out_f32[:, 12], out_f32[:, 16]], axis=1),
        "disk_phi_m": np.stack([out_f32[:, 13], out_f32[:, 17]], axis=1),
        "disk_t_m": np.stack([out_f32[:, 14], out_f32[:, 18]], axis=1),
        "disk_g_m": np.stack([out_f32[:, 15], out_f32[:, 19]], axis=1),
    }


def ks_gpu_escape_directions(params: MetricParams, gpu: dict[str, Any]) -> np.ndarray:
    """Return escaped-ray asymptotic directions from native KS GPU final states."""

    dirs = np.full((gpu["event_code"].shape[0], 3), np.nan, dtype=np.float64)
    escape_code = SCHEMA_EVENT_CODES["escape"]
    for idx, event_code in enumerate(gpu["event_code"]):
        if int(event_code) != escape_code:
            continue
        try:
            from gr_bh_xr.geodesic_ks import ks_state_to_bl_state

            state = RayState(
                x=np.asarray(gpu["final_x"][idx], dtype=np.float64),
                p=np.asarray(gpu["final_p"][idx], dtype=np.float64),
            )
            bl_state = ks_state_to_bl_state(params, state)
            _theta, _phi, dx, dy, dz = escape_direction_or_nan(
                params, "escape", bl_state.x, bl_state.p
            )
            dirs[idx] = (dx, dy, dz)
        except Exception:
            continue
    return dirs


def _pack_states(states: list[RayState] | tuple[RayState, ...]) -> np.ndarray:
    packed = np.empty((len(states), KS_INPUTS_PER_RAY), dtype=np.float32)
    for idx, state in enumerate(states):
        packed[idx, 0:4] = np.asarray(state.x, dtype=np.float32)
        packed[idx, 4:8] = np.asarray(state.p, dtype=np.float32)
    return packed


def _shader_params(config: KsGpuTraceConfig, n_rays: int) -> np.ndarray:
    return np.asarray(
        [
            config.params.M,
            config.params.a,
            config.step_size,
            float(config.steps),
            config.r_escape,
            config.capture_r,
            float(n_rays),
            math.pi,
            1.0 if config.adaptive_step else 0.0,
            config.max_step,
            config.max_lambda,
            config.step_r_ref,
            float(config.sphere_center_xyz[0]) if config.sphere_center_xyz is not None else 0.0,
            float(config.sphere_center_xyz[1]) if config.sphere_center_xyz is not None else 0.0,
            float(config.sphere_center_xyz[2]) if config.sphere_center_xyz is not None else 0.0,
            float(config.sphere_radius) if config.sphere_center_xyz is not None else -1.0,
            config.disk_r_in,
            config.disk_r_out,
            config.time_orientation,
        ],
        dtype=np.float32,
    )


def _empty_result(info: dict[str, Any]) -> dict[str, Any]:
    return {
        "backend": info,
        "event_code": np.empty(0, dtype=np.int32),
        "failure_code": np.empty(0, dtype=np.int32),
        "steps": np.empty(0, dtype=np.int32),
        "min_r": np.empty(0, dtype=np.float32),
        "h_max_abs": np.empty(0, dtype=np.float32),
        "final_r": np.empty(0, dtype=np.float32),
        "lambda_end": np.empty(0, dtype=np.float32),
        "final_x": np.empty((0, 4), dtype=np.float32),
        "final_p": np.empty((0, 4), dtype=np.float32),
        "disk_r_m": np.empty((0, KS_DISK_MAX_ORDER), dtype=np.float32),
        "disk_phi_m": np.empty((0, KS_DISK_MAX_ORDER), dtype=np.float32),
        "disk_t_m": np.empty((0, KS_DISK_MAX_ORDER), dtype=np.float32),
        "disk_g_m": np.empty((0, KS_DISK_MAX_ORDER), dtype=np.float32),
    }


def _get_ks_trace_context():
    global _KS_TRACE_CONTEXT
    if _KS_TRACE_CONTEXT is None:
        wgpu = require_wgpu()
        adapter, device = create_vulkan_device()
        shader = device.create_shader_module(label="gr-bh-xr ks gpu shader", code=KS_WGSL_SHADER)
        pipeline = device.create_compute_pipeline(
            label="gr-bh-xr ks gpu pipeline",
            layout="auto",
            compute={"module": shader, "entry_point": "main"},
        )
        _KS_TRACE_CONTEXT = (wgpu, adapter, device, pipeline, backend_info(adapter).as_dict())
    return _KS_TRACE_CONTEXT


KS_WGSL_SHADER = r"""
const EVENT_CAPTURE: i32 = 0;
const EVENT_ESCAPE: i32 = 1;
const EVENT_OBJECT_HIT: i32 = 4;
const EVENT_INVALID: i32 = 3;
const FAILURE_NONE: i32 = 0;
const FAILURE_UNCLASSIFIED_MAX_LAMBDA: i32 = 2;
const FAILURE_SOLVER_FAILURE: i32 = 3;
const KS_INPUTS_PER_RAY: u32 = 8u;
const KS_F32_OUTPUTS_PER_RAY: u32 = __KS_F32_OUTPUTS_PER_RAY__u;
const KS_DISK_MAX_ORDER: u32 = __KS_DISK_MAX_ORDER__u;

@group(0) @binding(0) var<storage, read> params: array<f32>;
@group(0) @binding(1) var<storage, read> initial_states: array<f32>;
@group(0) @binding(2) var<storage, read_write> out_i32: array<i32>;
@group(0) @binding(3) var<storage, read_write> out_f32: array<f32>;

struct StateKS {
    t: f32,
    x: f32,
    y: f32,
    z: f32,
    pt: f32,
    px: f32,
    py: f32,
    pz: f32,
};

struct MetricKS {
    r: f32,
    h: f32,
    lx: f32,
    ly: f32,
    lz: f32,
};

fn is_bad(v: f32) -> bool {
    return (v != v) || abs(v) > 1.0e30;
}

fn qder(value: f32, deriv: f32, denom: f32, denom_deriv: f32) -> f32 {
    return (deriv * denom - value * denom_deriv) / (denom * denom);
}

fn ks_radius_xyz(x: f32, y: f32, z: f32) -> f32 {
    let a = params[1];
    let a2 = a * a;
    let rho2 = x * x + y * y + z * z;
    if (a2 <= 1.0e-20) {
        return sqrt(max(rho2, 0.0));
    }
    let q = rho2 - a2;
    let root = sqrt(max(q * q + 4.0 * a2 * z * z, 0.0));
    var r2 = 0.5 * (q + root);
    if (q < 0.0) {
        let denom = max(root - q, 1.0e-20);
        r2 = (2.0 * a2 * z * z) / denom;
    }
    return sqrt(max(r2, 0.0));
}

fn metric_ks(x: f32, y: f32, z: f32) -> MetricKS {
    let m = params[0];
    let a = params[1];
    let a2 = a * a;
    let r = ks_radius_xyz(x, y, z);
    let r2 = r * r;
    let den = max(r2 + a2, 1.0e-20);
    let hden = max(r2 * r2 + a2 * z * z, 1.0e-20);
    let h = m * r * r * r / hden;
    return MetricKS(
        r,
        h,
        (r * x + a * y) / den,
        (r * y - a * x) / den,
        z / max(r, 1.0e-20),
    );
}

fn inv_metric_times_p(k: MetricKS, p: vec4<f32>) -> vec4<f32> {
    let lt = -1.0;
    let dot_l_p = lt * p.x + k.lx * p.y + k.ly * p.z + k.lz * p.w;
    let scale = -2.0 * k.h * dot_l_p;
    return vec4<f32>(
        -p.x + scale * lt,
        p.y + scale * k.lx,
        p.z + scale * k.ly,
        p.w + scale * k.lz,
    );
}

fn ks_horizon_r_plus() -> f32 {
    let m = params[0];
    let a = params[1];
    return m + sqrt(max(m * m - a * a, 0.0));
}

fn ks_horizon_r_minus() -> f32 {
    let m = params[0];
    let a = params[1];
    return m - sqrt(max(m * m - a * a, 0.0));
}

// Equatorial Keplerian angular velocity; identical formula to the audited
// BL shader (function of r and the conserved quantities only, so it is
// chart independent).
fn disk_omega_ks(r: f32) -> f32 {
    let m = params[0];
    let a = params[1];
    var orbit_sign = 1.0;
    if (a < 0.0) {
        orbit_sign = -1.0;
    }
    let sqrt_m = sqrt(m);
    return orbit_sign * sqrt_m / (pow(r, 1.5) + orbit_sign * a * sqrt_m);
}

fn disk_redshift_ks(r: f32, pt: f32, pph: f32) -> f32 {
    let m = params[0];
    let a = params[1];
    let a2 = a * a;
    // Equator: sigma = r^2, sin^2(theta) = 1.
    let sig = r * r;
    let dlt = r * r - 2.0 * m * r + a2;
    let rp = r * r + a2;
    let shell = rp * rp - a2 * dlt;
    let gtt_inv = -shell / (sig * dlt);
    let gtphi_inv = -2.0 * m * a * r / (sig * dlt);
    let gphiphi_inv = (dlt - a2) / (sig * dlt);
    let det_inv = gtt_inv * gphiphi_inv - gtphi_inv * gtphi_inv;
    let g_tt = gphiphi_inv / det_inv;
    let g_tphi = -gtphi_inv / det_inv;
    let g_phiphi = gtt_inv / det_inv;
    let omega = disk_omega_ks(r);
    let norm = -(g_tt + 2.0 * omega * g_tphi + omega * omega * g_phiphi);
    if (norm <= 0.0 || is_bad(norm)) {
        return -1.0;
    }
    let u_t = 1.0 / sqrt(norm);
    let energy = -pt;
    let denom = u_t * (energy - omega * pph);
    if (denom <= 0.0 || is_bad(denom)) {
        return -1.0;
    }
    return energy / denom;
}

// Ingoing-KS azimuth/time shifts relative to Boyer-Lindquist at radius r
// (exterior, r > r_plus): phi_ks = phi_bl + a/(r+ - r-) ln|(r - r+)/(r - r-)|,
// t_ks = t_bl + 2M/(r+ - r-) (r+ ln|r - r+| - r- ln|r - r-|).
fn ks_phi_shift(r: f32) -> f32 {
    let a = params[1];
    let rp = ks_horizon_r_plus();
    let rm = ks_horizon_r_minus();
    let dr = max(rp - rm, 1.0e-6);
    return a / dr * log(abs((r - rp) / max(abs(r - rm), 1.0e-12)));
}

fn ks_time_shift(r: f32) -> f32 {
    let m = params[0];
    let rp = ks_horizon_r_plus();
    let rm = ks_horizon_r_minus();
    let dr = max(rp - rm, 1.0e-6);
    return 2.0 * m / dr * (rp * log(max(abs(r - rp), 1.0e-12)) - rm * log(max(abs(r - rm), 1.0e-12)));
}

fn hamiltonian_ks(s: StateKS) -> f32 {
    let k = metric_ks(s.x, s.y, s.z);
    let p = vec4<f32>(s.pt, s.px, s.py, s.pz);
    let u = inv_metric_times_p(k, p);
    return 0.5 * dot(p, u);
}

fn h_derivative(r: f32, z: f32, dr: f32, dz: f32) -> f32 {
    let m = params[0];
    let a = params[1];
    let a2 = a * a;
    let r2 = r * r;
    let hden = max(r2 * r2 + a2 * z * z, 1.0e-20);
    let hden_der = 4.0 * r * r2 * dr + 2.0 * a2 * z * dz;
    let numerator = m * r2 * r;
    let numerator_der = 3.0 * m * r2 * dr;
    return (numerator_der * hden - numerator * hden_der) / (hden * hden);
}

fn l_derivative(axis: u32, x: f32, y: f32, z: f32, r: f32, dr: f32) -> vec3<f32> {
    let a = params[1];
    let a2 = a * a;
    var dx = 0.0;
    var dy = 0.0;
    var dz = 0.0;
    if (axis == 0u) {
        dx = 1.0;
    } else if (axis == 1u) {
        dy = 1.0;
    } else {
        dz = 1.0;
    }
    let den = max(r * r + a2, 1.0e-20);
    let den_der = 2.0 * r * dr;
    let lx_num = r * x + a * y;
    let lx_num_der = dr * x + r * dx + a * dy;
    let ly_num = r * y - a * x;
    let ly_num_der = dr * y + r * dy - a * dx;
    return vec3<f32>(
        qder(lx_num, lx_num_der, den, den_der),
        qder(ly_num, ly_num_der, den, den_der),
        (dz * r - z * dr) / max(r * r, 1.0e-20),
    );
}

fn p_dg_p(p: vec4<f32>, k: MetricKS, dh: f32, dl: vec3<f32>) -> f32 {
    let l = vec4<f32>(-1.0, k.lx, k.ly, k.lz);
    let dl4 = vec4<f32>(0.0, dl.x, dl.y, dl.z);
    let lp = dot(l, p);
    let dlp = dot(dl4, p);
    return -2.0 * dh * lp * lp - 4.0 * k.h * dlp * lp;
}

fn rhs_ks(s: StateKS) -> StateKS {
    let a = params[1];
    let a2 = a * a;
    let k = metric_ks(s.x, s.y, s.z);
    let p = vec4<f32>(s.pt, s.px, s.py, s.pz);
    let u = inv_metric_times_p(k, p);
    let r = max(k.r, 1.0e-20);
    let r2 = r * r;
    let rho2 = s.x * s.x + s.y * s.y + s.z * s.z;
    let radius_den = max(2.0 * r2 - rho2 + a2, 1.0e-20);
    let drx = s.x * r / radius_den;
    let dry = s.y * r / radius_den;
    let drz = s.z * (r2 + a2) / (r * radius_den);
    let dhx = h_derivative(r, s.z, drx, 0.0);
    let dhy = h_derivative(r, s.z, dry, 0.0);
    let dhz = h_derivative(r, s.z, drz, 1.0);
    let dlx = l_derivative(0u, s.x, s.y, s.z, r, drx);
    let dly = l_derivative(1u, s.x, s.y, s.z, r, dry);
    let dlz = l_derivative(2u, s.x, s.y, s.z, r, drz);
    return StateKS(
        u.x,
        u.y,
        u.z,
        u.w,
        0.0,
        -0.5 * p_dg_p(p, k, dhx, dlx),
        -0.5 * p_dg_p(p, k, dhy, dly),
        -0.5 * p_dg_p(p, k, dhz, dlz),
    );
}

fn add_scaled(s: StateKS, k: StateKS, h: f32) -> StateKS {
    return StateKS(
        s.t + h * k.t,
        s.x + h * k.x,
        s.y + h * k.y,
        s.z + h * k.z,
        s.pt + h * k.pt,
        s.px + h * k.px,
        s.py + h * k.py,
        s.pz + h * k.pz,
    );
}

fn rk4_step_ks(s: StateKS, h: f32) -> StateKS {
    let k1 = rhs_ks(s);
    let k2 = rhs_ks(add_scaled(s, k1, 0.5 * h));
    let k3 = rhs_ks(add_scaled(s, k2, 0.5 * h));
    let k4 = rhs_ks(add_scaled(s, k3, h));
    return StateKS(
        s.t + h * (k1.t + 2.0 * k2.t + 2.0 * k3.t + k4.t) / 6.0,
        s.x + h * (k1.x + 2.0 * k2.x + 2.0 * k3.x + k4.x) / 6.0,
        s.y + h * (k1.y + 2.0 * k2.y + 2.0 * k3.y + k4.y) / 6.0,
        s.z + h * (k1.z + 2.0 * k2.z + 2.0 * k3.z + k4.z) / 6.0,
        s.pt,
        s.px + h * (k1.px + 2.0 * k2.px + 2.0 * k3.px + k4.px) / 6.0,
        s.py + h * (k1.py + 2.0 * k2.py + 2.0 * k3.py + k4.py) / 6.0,
        s.pz + h * (k1.pz + 2.0 * k2.pz + 2.0 * k3.pz + k4.pz) / 6.0,
    );
}

fn state_is_bad(s: StateKS) -> bool {
    return is_bad(s.t) || is_bad(s.x) || is_bad(s.y) || is_bad(s.z)
        || is_bad(s.pt) || is_bad(s.px) || is_bad(s.py) || is_bad(s.pz);
}

fn adaptive_step_size(s: StateKS, lambda_used: f32) -> f32 {
    let base_h = params[2];
    let adaptive = params[8] > 0.5;
    let max_h = params[9];
    let max_lambda = params[10];
    let r_ref = max(params[11], 1.0e-6);
    var h = base_h;
    if (adaptive) {
        let r = ks_radius_xyz(s.x, s.y, s.z);
        h = clamp(base_h * max(1.0, r / r_ref), base_h, max_h);
    }
    return min(h, max(max_lambda - lambda_used, 0.0));
}

fn load_state(idx: u32) -> StateKS {
    let base = idx * KS_INPUTS_PER_RAY;
    return StateKS(
        initial_states[base + 0u],
        initial_states[base + 1u],
        initial_states[base + 2u],
        initial_states[base + 3u],
        initial_states[base + 4u],
        initial_states[base + 5u],
        initial_states[base + 6u],
        initial_states[base + 7u],
    );
}

fn segment_hits_sphere(start_pos: vec3<f32>, end_pos: vec3<f32>, center: vec3<f32>, radius: f32) -> bool {
    let segment = end_pos - start_pos;
    let denom = dot(segment, segment);
    var closest = end_pos;
    if (denom > 0.0) {
        let u = clamp(dot(center - start_pos, segment) / denom, 0.0, 1.0);
        closest = start_pos + u * segment;
    }
    return distance(closest, center) <= radius;
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
    let idx = gid.x;
    let ray_count = u32(params[6]);
    if (idx >= ray_count) {
        return;
    }
    let max_steps = u32(params[3]);
    let escape_r = params[4];
    let capture_r = params[5];
    let max_lambda = params[10];
    let sphere_center = vec3<f32>(params[12], params[13], params[14]);
    let sphere_radius = params[15];
    let disk_r_in = params[16];
    let disk_r_out = params[17];
    var s = load_state(idx);
    var event = EVENT_INVALID;
    var failure = FAILURE_UNCLASSIFIED_MAX_LAMBDA;
    var step_count: u32 = 0u;
    var lambda_used = 0.0;
    var min_r = ks_radius_xyz(s.x, s.y, s.z);
    var h_max = abs(hamiltonian_ks(s));
    var disk_order = 0u;
    var disk_r0 = -1.0;
    var disk_phi0 = -1.0;
    var disk_t0 = -1.0;
    var disk_g0 = -1.0;
    var disk_r1 = -1.0;
    var disk_phi1 = -1.0;
    var disk_t1 = -1.0;
    var disk_g1 = -1.0;
    if (state_is_bad(s)) {
        failure = FAILURE_SOLVER_FAILURE;
    } else {
        for (var i = 0u; i < max_steps; i = i + 1u) {
            let dh = adaptive_step_size(s, lambda_used);
            if (dh <= 0.0 || lambda_used >= max_lambda) {
                break;
            }
            let prev_pos = vec3<f32>(s.x, s.y, s.z);
            let prev_t = s.t;
            s = rk4_step_ks(s, dh);
            let curr_pos = vec3<f32>(s.x, s.y, s.z);
            lambda_used = lambda_used + dh;
            step_count = step_count + 1u;
            if (state_is_bad(s)) {
                failure = FAILURE_SOLVER_FAILURE;
                break;
            }
            if (disk_r_out > 0.0) {
                // z = 0 crossing: trivial and singularity-free in the
                // Cartesian chart. Order counts every true equatorial
                // crossing, matching the BL image-order semantics.
                let crosses = (prev_pos.z < -1.0e-9 && curr_pos.z >= 0.0)
                    || (prev_pos.z > 1.0e-9 && curr_pos.z <= 0.0);
                if (crosses) {
                    let frac = clamp(abs(prev_pos.z) / max(abs(prev_pos.z - curr_pos.z), 1.0e-12), 0.0, 1.0);
                    let xc = prev_pos.x + frac * (curr_pos.x - prev_pos.x);
                    let yc = prev_pos.y + frac * (curr_pos.y - prev_pos.y);
                    let rc = ks_radius_xyz(xc, yc, 0.0);
                    if (disk_order < KS_DISK_MAX_ORDER && rc >= disk_r_in && rc <= disk_r_out) {
                        let a_spin = params[1];
                        let orientation = params[18];
                        let phi_ks = atan2(yc * rc - a_spin * xc, rc * xc + a_spin * yc);
                        let phc = phi_ks - ks_phi_shift(rc);
                        let tc = (prev_t + frac * (s.t - prev_t)) - ks_time_shift(rc);
                        let pph = xc * s.py - yc * s.px;
                        let gc = disk_redshift_ks(rc, orientation * s.pt, orientation * pph);
                        if (disk_order == 0u) {
                            disk_r0 = rc;
                            disk_phi0 = phc;
                            disk_t0 = tc;
                            disk_g0 = gc;
                        } else {
                            disk_r1 = rc;
                            disk_phi1 = phc;
                            disk_t1 = tc;
                            disk_g1 = gc;
                        }
                    }
                    disk_order = disk_order + 1u;
                }
            }
            let r = ks_radius_xyz(s.x, s.y, s.z);
            if (is_bad(r) || r <= 1.0e-6) {
                failure = FAILURE_SOLVER_FAILURE;
                break;
            }
            min_r = min(min_r, r);
            h_max = max(h_max, abs(hamiltonian_ks(s)));
            if (r <= capture_r) {
                event = EVENT_CAPTURE;
                failure = FAILURE_NONE;
                break;
            }
            if (sphere_radius > 0.0 && segment_hits_sphere(prev_pos, curr_pos, sphere_center, sphere_radius)) {
                event = EVENT_OBJECT_HIT;
                failure = FAILURE_NONE;
                break;
            }
            if (r >= escape_r) {
                event = EVENT_ESCAPE;
                failure = FAILURE_NONE;
                break;
            }
        }
    }
    let ibase = idx * 3u;
    let fbase = idx * KS_F32_OUTPUTS_PER_RAY;
    out_i32[ibase + 0u] = event;
    out_i32[ibase + 1u] = failure;
    out_i32[ibase + 2u] = i32(step_count);
    out_f32[fbase + 0u] = min_r;
    out_f32[fbase + 1u] = h_max;
    out_f32[fbase + 2u] = ks_radius_xyz(s.x, s.y, s.z);
    out_f32[fbase + 3u] = lambda_used;
    out_f32[fbase + 4u] = s.t;
    out_f32[fbase + 5u] = s.x;
    out_f32[fbase + 6u] = s.y;
    out_f32[fbase + 7u] = s.z;
    out_f32[fbase + 8u] = s.pt;
    out_f32[fbase + 9u] = s.px;
    out_f32[fbase + 10u] = s.py;
    out_f32[fbase + 11u] = s.pz;
    out_f32[fbase + 12u] = disk_r0;
    out_f32[fbase + 13u] = disk_phi0;
    out_f32[fbase + 14u] = disk_t0;
    out_f32[fbase + 15u] = disk_g0;
    out_f32[fbase + 16u] = disk_r1;
    out_f32[fbase + 17u] = disk_phi1;
    out_f32[fbase + 18u] = disk_t1;
    out_f32[fbase + 19u] = disk_g1;
}
"""

# The WGSL stride is substituted from the Python constants rather than written
# as a literal: the readback buffer is sized from the Python value and the
# shader writes at the WGSL value, so a desync would silently offset every
# field rather than fail.
KS_WGSL_SHADER = KS_WGSL_SHADER.replace(
    "__KS_F32_OUTPUTS_PER_RAY__", str(KS_F32_OUTPUTS_PER_RAY)
).replace("__KS_DISK_MAX_ORDER__", str(KS_DISK_MAX_ORDER))
