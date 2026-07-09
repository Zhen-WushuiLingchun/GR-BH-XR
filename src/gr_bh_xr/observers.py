"""Observer tetrads for finite-radius Kerr camera work.

The Stage B near-horizon path needs observer frames that remain meaningful
where the static tetrad fails.  This module starts with Boyer-Lindquist ZAMO /
LNRF frames in the exterior domain; Kerr-Schild worldline transport remains a
later Stage B task.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .geodesic_ks import bl_to_ks_jacobian
from .metric import covariant_metric, delta, horizon_radius, sigma
from .metric_ks import bl_to_ks_cartesian, ks_metric
from .types import FloatArray, MetricParams


@dataclass(frozen=True)
class BLObserverTetrad:
    """Contravariant orthonormal tetrad in Boyer-Lindquist coordinates."""

    x: FloatArray
    e_time: FloatArray
    e_r: FloatArray
    e_theta: FloatArray
    e_phi: FloatArray
    kind: str

    def vectors(self) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
        return self.e_time, self.e_r, self.e_theta, self.e_phi


@dataclass(frozen=True)
class KSObserverTetrad:
    """Contravariant orthonormal tetrad in Cartesian Kerr-Schild coordinates."""

    x: FloatArray
    e_time: FloatArray
    e_r: FloatArray
    e_theta: FloatArray
    e_phi: FloatArray
    kind: str

    def vectors(self) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
        return self.e_time, self.e_r, self.e_theta, self.e_phi


def frame_inner_product(params: MetricParams, x: FloatArray, u: FloatArray, v: FloatArray) -> float:
    """Return `g_mu nu u^mu v^nu` for BL-coordinate contravariant vectors."""

    r = float(x[1])
    theta = float(x[2])
    g = covariant_metric(params, r, theta)
    return float(np.asarray(u, dtype=np.float64) @ g @ np.asarray(v, dtype=np.float64))


def ks_frame_inner_product(params: MetricParams, x: FloatArray, u: FloatArray, v: FloatArray) -> float:
    """Return `g_mu nu u^mu v^nu` for KS-coordinate contravariant vectors."""

    g = ks_metric(params, np.asarray(x, dtype=np.float64)[1:4])
    return float(np.asarray(u, dtype=np.float64) @ g @ np.asarray(v, dtype=np.float64))


def gram_matrix(params: MetricParams, tetrad: BLObserverTetrad) -> FloatArray:
    """Return the tetrad Gram matrix, expected to be diag(-1, 1, 1, 1)."""

    vectors = tetrad.vectors()
    return np.array(
        [[frame_inner_product(params, tetrad.x, left, right) for right in vectors] for left in vectors],
        dtype=np.float64,
    )


def ks_gram_matrix(params: MetricParams, tetrad: KSObserverTetrad) -> FloatArray:
    """Return the KS tetrad Gram matrix, expected to be diag(-1, 1, 1, 1)."""

    vectors = tetrad.vectors()
    return np.array(
        [[ks_frame_inner_product(params, tetrad.x, left, right) for right in vectors] for left in vectors],
        dtype=np.float64,
    )


def zamo_angular_velocity(params: MetricParams, r: float, theta: float) -> float:
    """Return the ZAMO / LNRF frame-dragging angular velocity `omega`.

    This is `omega = -g_tphi / g_phiphi`, equal to `2 M a r / A` in the usual
    Kerr notation of Bardeen, Press & Teukolsky.
    """

    g = covariant_metric(params, r, theta)
    g_phiphi = float(g[3, 3])
    if g_phiphi <= 0.0 or not math.isfinite(g_phiphi):
        raise ValueError("ZAMO angular velocity requires spacelike phi coordinate.")
    return -float(g[0, 3]) / g_phiphi


def zamo_lapse(params: MetricParams, r: float, theta: float) -> float:
    """Return the BL ZAMO lapse `alpha = sqrt(Sigma Delta / A)`."""

    dlt = delta(params, r)
    if dlt <= 0.0:
        raise ValueError("ZAMO lapse is defined only outside the outer horizon.")
    g = covariant_metric(params, r, theta)
    g_tt = float(g[0, 0])
    g_tphi = float(g[0, 3])
    g_phiphi = float(g[3, 3])
    value = (g_tphi * g_tphi - g_tt * g_phiphi) / g_phiphi
    if value <= 0.0 or not math.isfinite(value):
        raise ValueError("ZAMO lapse normalization is not timelike.")
    return math.sqrt(value)


def zamo_tetrad(params: MetricParams, *, r: float, theta: float, phi: float = 0.0) -> BLObserverTetrad:
    """Return an exterior Boyer-Lindquist ZAMO / LNRF orthonormal tetrad."""

    if r <= horizon_radius(params):
        raise ValueError("ZAMO tetrad is exterior-only in Boyer-Lindquist coordinates.")
    g = covariant_metric(params, r, theta)
    g_rr = float(g[1, 1])
    g_thetatheta = float(g[2, 2])
    g_phiphi = float(g[3, 3])
    if min(g_rr, g_thetatheta, g_phiphi) <= 0.0:
        raise ValueError("ZAMO spatial tetrad normalization is not spacelike.")

    omega = zamo_angular_velocity(params, r, theta)
    lapse = zamo_lapse(params, r, theta)
    e_time = np.array([1.0 / lapse, 0.0, 0.0, omega / lapse], dtype=np.float64)
    e_r = np.array([0.0, 1.0 / math.sqrt(g_rr), 0.0, 0.0], dtype=np.float64)
    e_theta = np.array([0.0, 0.0, 1.0 / math.sqrt(g_thetatheta), 0.0], dtype=np.float64)
    e_phi = np.array([0.0, 0.0, 0.0, 1.0 / math.sqrt(g_phiphi)], dtype=np.float64)
    return BLObserverTetrad(
        x=np.array([0.0, r, theta, phi], dtype=np.float64),
        e_time=e_time,
        e_r=e_r,
        e_theta=e_theta,
        e_phi=e_phi,
        kind="zamo",
    )


def static_observer_tetrad(
    params: MetricParams, *, r: float, theta: float, phi: float = 0.0
) -> BLObserverTetrad:
    """Return a static-observer tetrad where `partial_t` is timelike."""

    g = covariant_metric(params, r, theta)
    g_tt = float(g[0, 0])
    g_tphi = float(g[0, 3])
    g_rr = float(g[1, 1])
    g_thetatheta = float(g[2, 2])
    g_phiphi = float(g[3, 3])
    if g_tt >= 0.0:
        raise ValueError("Static observer tetrad is unavailable inside the ergoregion.")
    if min(g_rr, g_thetatheta) <= 0.0:
        raise ValueError("Static observer spatial tetrad is exterior-only in BL coordinates.")

    e_time = np.array([1.0 / math.sqrt(-g_tt), 0.0, 0.0, 0.0], dtype=np.float64)
    e_r = np.array([0.0, 1.0 / math.sqrt(g_rr), 0.0, 0.0], dtype=np.float64)
    e_theta = np.array([0.0, 0.0, 1.0 / math.sqrt(g_thetatheta), 0.0], dtype=np.float64)
    phi_norm_sq = g_phiphi - g_tphi * g_tphi / g_tt
    if phi_norm_sq <= 0.0:
        raise ValueError("Static observer phi tetrad normalization is not spacelike.")
    e_phi_phi = 1.0 / math.sqrt(phi_norm_sq)
    e_phi_t = (-g_tphi / g_tt) * e_phi_phi
    e_phi = np.array([e_phi_t, 0.0, 0.0, e_phi_phi], dtype=np.float64)
    return BLObserverTetrad(
        x=np.array([0.0, r, theta, phi], dtype=np.float64),
        e_time=e_time,
        e_r=e_r,
        e_theta=e_theta,
        e_phi=e_phi,
        kind="static",
    )


def push_bl_tetrad_to_ks(params: MetricParams, tetrad: BLObserverTetrad) -> KSObserverTetrad:
    """Push an exterior BL tetrad into ingoing Cartesian Kerr-Schild coordinates.

    This is a chart transform for existing exterior observer frames, not a
    transported near-horizon worldline frame. It is used as the first Stage B-2
    bridge so the already validated ZAMO/LNRF basis can initialize future
    Kerr-Schild rays without changing its physical observer definition.
    """

    r = float(tetrad.x[1])
    theta = float(tetrad.x[2])
    phi_bl = float(tetrad.x[3])
    jac = bl_to_ks_jacobian(params, r, theta, phi_bl)
    xyz = bl_to_ks_cartesian(r, theta, phi_bl + _ks_phi_shift_from_jacobian(params, r, jac), params.a)
    x_ks = np.array([float(tetrad.x[0]) + _ks_time_shift_from_jacobian(params, r, jac), *xyz], dtype=np.float64)
    return KSObserverTetrad(
        x=x_ks,
        e_time=jac @ tetrad.e_time,
        e_r=jac @ tetrad.e_r,
        e_theta=jac @ tetrad.e_theta,
        e_phi=jac @ tetrad.e_phi,
        kind=f"{tetrad.kind}_pushed_to_ks",
    )


def analytic_kerr_frame_dragging_omega(params: MetricParams, r: float, theta: float) -> float:
    """Return `2 M a r / A`, used as an independent ZAMO omega check."""

    s = math.sin(theta)
    a = params.a
    dlt = delta(params, r)
    a_term = (r * r + a * a) ** 2 - a * a * dlt * s * s
    return 2.0 * params.M * a * r / a_term


def analytic_zamo_lapse(params: MetricParams, r: float, theta: float) -> float:
    """Return `sqrt(Sigma Delta / A)`, used as an independent lapse check."""

    s = math.sin(theta)
    a = params.a
    dlt = delta(params, r)
    a_term = (r * r + a * a) ** 2 - a * a * dlt * s * s
    return math.sqrt(sigma(params, r, theta) * dlt / a_term)


def _ks_phi_shift_from_jacobian(params: MetricParams, r: float, jac: FloatArray) -> float:
    """Recover the KS azimuth shift used by the shared Jacobian helper.

    The public Jacobian intentionally exposes only derivatives. For the pushed
    tetrad position we need the matching coordinate map; keeping this local
    avoids exposing another low-level transform while preserving exact
    consistency with `geodesic_ks.bl_to_ks_jacobian`.
    """

    if abs(params.a) <= 1.0e-14:
        return 0.0
    # d phi_shift / dr is the Jacobian's implicit `a / Delta`; integrate with
    # the same closed form as the canonical KS state transform.
    rp = horizon_radius(params)
    rm = params.M - math.sqrt(params.M * params.M - params.a * params.a)
    gap = rp - rm
    return params.a / gap * (math.log(abs(r - rp)) - math.log(abs(r - rm)))


def _ks_time_shift_from_jacobian(params: MetricParams, r: float, jac: FloatArray) -> float:
    rp = horizon_radius(params)
    rm = params.M - math.sqrt(params.M * params.M - params.a * params.a)
    gap = rp - rm
    return (2.0 * params.M / gap) * (rp * math.log(abs(r - rp)) - rm * math.log(abs(r - rm)))
