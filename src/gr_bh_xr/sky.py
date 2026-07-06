"""Asymptotic sky-direction helpers for escaped Boyer-Lindquist rays."""

from __future__ import annotations

import math

import numpy as np

from .metric import inverse_metric
from .types import MetricParams


def wrap_phi(phi: float) -> float:
    """Wrap an azimuthal angle to `[0, 2 pi)`."""

    value = math.fmod(float(phi), 2.0 * math.pi)
    return value + 2.0 * math.pi if value < 0.0 else value


def direction_from_spherical(theta: float, phi: float) -> tuple[float, float, float]:
    """Return the unit Cartesian direction for spherical angles."""

    wrapped_phi = wrap_phi(phi)
    sin_t = math.sin(theta)
    return (
        sin_t * math.cos(wrapped_phi),
        sin_t * math.sin(wrapped_phi),
        math.cos(theta),
    )


def momentum_direction_from_state(
    params: MetricParams,
    *,
    r: float,
    theta: float,
    phi: float,
    p_t: float,
    p_r: float,
    p_theta: float,
    p_phi: float,
) -> tuple[float, float, float, float, float]:
    """Return escaped-ray momentum direction `(theta, phi, x, y, z)`.

    The direction is computed from the contravariant momentum
    `u^mu = g^{mu nu} p_nu` at the escape sphere, not from the ray's position on
    that sphere. This removes the finite-radius `O(b / r_escape)` position-angle
    bias and makes the buffer suitable for background-cubemap sampling.
    """

    values = (r, theta, phi, p_t, p_r, p_theta, p_phi)
    if not all(math.isfinite(value) for value in values):
        return (math.nan, math.nan, math.nan, math.nan, math.nan)

    try:
        u = inverse_metric(params, float(r), float(theta)) @ np.asarray(
            [p_t, p_r, p_theta, p_phi], dtype=np.float64
        )
    except Exception:
        return (math.nan, math.nan, math.nan, math.nan, math.nan)

    sin_t = math.sin(theta)
    cos_t = math.cos(theta)
    wrapped_phi = wrap_phi(phi)
    sin_p = math.sin(wrapped_phi)
    cos_p = math.cos(wrapped_phi)
    v_r = float(u[1])
    v_theta = float(r * u[2])
    v_phi = float(r * sin_t * u[3])
    dx = v_r * sin_t * cos_p + v_theta * cos_t * cos_p - v_phi * sin_p
    dy = v_r * sin_t * sin_p + v_theta * cos_t * sin_p + v_phi * cos_p
    dz = v_r * cos_t - v_theta * sin_t
    norm = math.sqrt(dx * dx + dy * dy + dz * dz)
    if not math.isfinite(norm) or norm <= 0.0:
        return (math.nan, math.nan, math.nan, math.nan, math.nan)

    dx /= norm
    dy /= norm
    dz /= norm
    escape_theta = math.acos(max(-1.0, min(1.0, dz)))
    escape_phi = wrap_phi(math.atan2(dy, dx))
    return (escape_theta, escape_phi, dx, dy, dz)


def escape_direction_or_nan(
    params: MetricParams, event: str, x: np.ndarray, p: np.ndarray
) -> tuple[float, float, float, float, float]:
    """Return momentum sky direction for escaped rays and NaNs otherwise."""

    if event != "escape":
        return (math.nan, math.nan, math.nan, math.nan, math.nan)
    return momentum_direction_from_state(
        params,
        r=float(x[1]),
        theta=float(x[2]),
        phi=float(x[3]),
        p_t=float(p[0]),
        p_r=float(p[1]),
        p_theta=float(p[2]),
        p_phi=float(p[3]),
    )


def escape_direction_arrays(
    *,
    params: MetricParams,
    event_code: np.ndarray,
    r: np.ndarray,
    theta: np.ndarray,
    phi: np.ndarray,
    p_t: np.ndarray | float,
    p_r: np.ndarray,
    p_theta: np.ndarray,
    p_phi: np.ndarray,
    escape_code: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized escaped-ray momentum direction with NaNs for non-escape pixels."""

    event_code = np.asarray(event_code)
    shape = event_code.shape
    r = np.broadcast_to(np.asarray(r, dtype=np.float64), shape)
    theta = np.broadcast_to(np.asarray(theta, dtype=np.float64), shape)
    phi = np.broadcast_to(np.asarray(phi, dtype=np.float64), shape)
    p_t = np.broadcast_to(np.asarray(p_t, dtype=np.float64), shape)
    p_r = np.broadcast_to(np.asarray(p_r, dtype=np.float64), shape)
    p_theta = np.broadcast_to(np.asarray(p_theta, dtype=np.float64), shape)
    p_phi = np.broadcast_to(np.asarray(p_phi, dtype=np.float64), shape)

    escape_theta = np.full(shape, np.nan, dtype=np.float64)
    escape_phi = np.full(shape, np.nan, dtype=np.float64)
    dir_x = np.full(shape, np.nan, dtype=np.float64)
    dir_y = np.full(shape, np.nan, dtype=np.float64)
    dir_z = np.full(shape, np.nan, dtype=np.float64)

    sin_t_all = np.sin(theta)
    s2_all = sin_t_all * sin_t_all
    mask = (
        (event_code == escape_code)
        & np.isfinite(r)
        & np.isfinite(theta)
        & np.isfinite(phi)
        & np.isfinite(p_t)
        & np.isfinite(p_r)
        & np.isfinite(p_theta)
        & np.isfinite(p_phi)
        & (s2_all > 1.0e-14)
    )
    if np.any(mask):
        rr = r[mask]
        th = theta[mask]
        ph = phi[mask]
        pt = p_t[mask]
        pr = p_r[mask]
        pth = p_theta[mask]
        pph = p_phi[mask]
        a = params.a
        a2 = a * a
        sig = rr * rr + a2 * np.cos(th) ** 2
        dlt = rr * rr - 2.0 * params.M * rr + a2
        sin_t = np.sin(th)
        cos_t = np.cos(th)
        s2 = sin_t * sin_t
        finite_metric = np.isfinite(sig) & np.isfinite(dlt) & (np.abs(dlt) > 1.0e-14)
        g_tphi = -2.0 * params.M * a * rr / (sig * dlt)
        g_rr = dlt / sig
        g_thetatheta = 1.0 / sig
        g_phiphi = (dlt - a2 * s2) / (sig * dlt * s2)
        u_r = g_rr * pr
        u_theta = g_thetatheta * pth
        u_phi = g_tphi * pt + g_phiphi * pph

        wrapped_phi = np.mod(ph, 2.0 * math.pi)
        sin_p = np.sin(wrapped_phi)
        cos_p = np.cos(wrapped_phi)
        v_r = u_r
        v_theta = rr * u_theta
        v_phi = rr * sin_t * u_phi
        dx = v_r * sin_t * cos_p + v_theta * cos_t * cos_p - v_phi * sin_p
        dy = v_r * sin_t * sin_p + v_theta * cos_t * sin_p + v_phi * cos_p
        dz = v_r * cos_t - v_theta * sin_t
        norm = np.sqrt(dx * dx + dy * dy + dz * dz)
        finite = finite_metric & np.isfinite(norm) & (norm > 0.0)
        local = np.flatnonzero(mask)
        if np.any(finite):
            target = local[finite]
            ndx = dx[finite] / norm[finite]
            ndy = dy[finite] / norm[finite]
            ndz = dz[finite] / norm[finite]
            dir_x.flat[target] = ndx
            dir_y.flat[target] = ndy
            dir_z.flat[target] = ndz
            escape_theta.flat[target] = np.arccos(np.clip(ndz, -1.0, 1.0))
            escape_phi.flat[target] = np.mod(np.arctan2(ndy, ndx), 2.0 * math.pi)
    return escape_theta, escape_phi, dir_x, dir_y, dir_z


def angular_error_from_dirs(
    ax: np.ndarray,
    ay: np.ndarray,
    az: np.ndarray,
    bx: np.ndarray,
    by: np.ndarray,
    bz: np.ndarray,
) -> np.ndarray:
    """Return angular separation in radians for finite unit-vector components."""

    dot = ax * bx + ay * by + az * bz
    return np.arccos(np.clip(dot, -1.0, 1.0))
