"""Asymptotic sky-direction helpers for escaped Boyer-Lindquist rays."""

from __future__ import annotations

import math

import numpy as np


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


def escape_direction_or_nan(event: str, theta: float, phi: float) -> tuple[float, float, float, float, float]:
    """Return `(theta, phi, x, y, z)` for escaped rays and NaNs otherwise."""

    if event != "escape" or not math.isfinite(theta) or not math.isfinite(phi):
        return (math.nan, math.nan, math.nan, math.nan, math.nan)
    wrapped_phi = wrap_phi(phi)
    dx, dy, dz = direction_from_spherical(theta, wrapped_phi)
    return (float(theta), wrapped_phi, dx, dy, dz)


def escape_direction_arrays(
    *,
    event_code: np.ndarray,
    theta: np.ndarray,
    phi: np.ndarray,
    escape_code: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized escaped-ray sky direction with NaNs for non-escape pixels."""

    theta = np.asarray(theta, dtype=np.float32)
    phi = np.asarray(phi, dtype=np.float32)
    mask = (event_code == escape_code) & np.isfinite(theta) & np.isfinite(phi)
    escape_theta = np.full(theta.shape, np.nan, dtype=np.float32)
    escape_phi = np.full(theta.shape, np.nan, dtype=np.float32)
    dir_x = np.full(theta.shape, np.nan, dtype=np.float32)
    dir_y = np.full(theta.shape, np.nan, dtype=np.float32)
    dir_z = np.full(theta.shape, np.nan, dtype=np.float32)
    if np.any(mask):
        wrapped_phi = np.mod(phi[mask], np.float32(2.0 * math.pi))
        escape_theta[mask] = theta[mask]
        escape_phi[mask] = wrapped_phi
        sin_t = np.sin(theta[mask])
        dir_x[mask] = sin_t * np.cos(wrapped_phi)
        dir_y[mask] = sin_t * np.sin(wrapped_phi)
        dir_z[mask] = np.cos(theta[mask])
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
