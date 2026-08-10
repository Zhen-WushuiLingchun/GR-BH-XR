"""Reference metric providers for the generic time-dependent interface."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .dynamic_types import MetricSample
from .metric_ks import (
    MINKOWSKI_COVARIANT,
    MINKOWSKI_INVERSE,
    ks_inverse_metric,
    ks_inverse_metric_derivatives,
    ks_metric,
)
from .types import FloatArray, MetricParams


def _adm_from_metric(g_cov: FloatArray, g_inv: FloatArray) -> tuple[float, FloatArray, FloatArray, FloatArray]:
    """Reconstruct lapse, shift, and spatial metric blocks."""

    g00 = float(g_inv[0, 0])
    if g00 >= 0.0:
        raise ValueError("metric does not admit the selected spacelike 3+1 slicing.")
    lapse = 1.0 / math.sqrt(-g00)
    shift = lapse * lapse * np.asarray(g_inv[0, 1:4], dtype=np.float64)
    gamma_cov = np.asarray(g_cov[1:4, 1:4], dtype=np.float64)
    gamma_inv = np.asarray(g_inv[1:4, 1:4], dtype=np.float64) + np.outer(shift, shift) / (lapse * lapse)
    return lapse, shift, gamma_cov, gamma_inv


def finite_difference_inverse_metric_derivatives(
    provider: object, t: float, x: FloatArray, *, relative_step: float = 1.0e-5
) -> FloatArray:
    """Central-difference oracle for ``partial_mu g^{alpha beta}``.

    This helper is intentionally independent of provider analytic derivatives
    and is used only in validation tests.
    """

    if relative_step <= 0.0:
        raise ValueError("relative_step must be positive.")
    event = np.concatenate([[float(t)], np.asarray(x, dtype=np.float64)])
    if event.shape != (4,):
        raise ValueError("x must have shape (3,).")
    derivatives = np.empty((4, 4, 4), dtype=np.float64)
    for mu in range(4):
        step = relative_step * max(1.0, abs(float(event[mu])))
        plus = event.copy()
        minus = event.copy()
        plus[mu] += step
        minus[mu] -= step
        plus_metric = provider.sample(float(plus[0]), plus[1:4]).g_inv
        minus_metric = provider.sample(float(minus[0]), minus[1:4]).g_inv
        derivatives[mu] = (plus_metric - minus_metric) / (2.0 * step)
    return derivatives


@dataclass(frozen=True)
class MinkowskiMetricProvider:
    """Exact flat-spacetime provider using Cartesian inertial coordinates."""

    source_revision: str = "gr-bh-xr.minkowski.v1"

    def sample(self, t: float, x: FloatArray) -> MetricSample:
        xyz = np.asarray(x, dtype=np.float64)
        return MetricSample(
            t=float(t),
            x=xyz,
            g_cov=MINKOWSKI_COVARIANT.copy(),
            g_inv=MINKOWSKI_INVERSE.copy(),
            d_g_inv=np.zeros((4, 4, 4), dtype=np.float64),
            lapse=1.0,
            shift=np.zeros(3, dtype=np.float64),
            gamma_cov=np.eye(3, dtype=np.float64),
            gamma_inv=np.eye(3, dtype=np.float64),
            validity="valid",
            evidence_label="analytic_exact",
            source_revision=self.source_revision,
        )


@dataclass(frozen=True)
class StationaryKerrSchildProvider:
    """Adapter exposing the accepted Cartesian Kerr-Schild metric contract."""

    params: MetricParams
    source_revision: str = "gr-bh-xr.metric-ks.v1"

    def sample(self, t: float, x: FloatArray) -> MetricSample:
        xyz = np.asarray(x, dtype=np.float64)
        g_cov = ks_metric(self.params, xyz)
        g_inv = ks_inverse_metric(self.params, xyz)
        spatial = ks_inverse_metric_derivatives(self.params, xyz)
        derivatives = np.zeros((4, 4, 4), dtype=np.float64)
        derivatives[1:4] = np.asarray(spatial)
        lapse, shift, gamma_cov, gamma_inv = _adm_from_metric(g_cov, g_inv)
        return MetricSample(
            t=float(t),
            x=xyz,
            g_cov=g_cov,
            g_inv=g_inv,
            d_g_inv=derivatives,
            lapse=lapse,
            shift=shift,
            gamma_cov=gamma_cov,
            gamma_inv=gamma_inv,
            validity="valid",
            evidence_label="analytic_exact",
            source_revision=self.source_revision,
        )


@dataclass(frozen=True)
class IsotropicScaleFactorProvider:
    """Analytic time-dependent test metric ``ds^2=-dt^2+A(t)^2 dx^2``.

    This is a solver oracle, not a BBH model.  It exists to prove that the
    generic Hamiltonian path actually integrates ``p_t``.
    """

    scale0: float = 1.0
    rate: float = 1.0e-3
    source_revision: str = "gr-bh-xr.isotropic-scale-factor.v1"

    def _scale(self, t: float) -> float:
        scale = self.scale0 + self.rate * float(t)
        if scale <= 0.0:
            raise ValueError("scale factor left the provider validity domain.")
        return scale

    def sample(self, t: float, x: FloatArray) -> MetricSample:
        xyz = np.asarray(x, dtype=np.float64)
        scale = self._scale(t)
        scale2 = scale * scale
        g_cov = np.diag([-1.0, scale2, scale2, scale2]).astype(np.float64)
        inv_scale2 = 1.0 / scale2
        g_inv = np.diag([-1.0, inv_scale2, inv_scale2, inv_scale2]).astype(np.float64)
        derivatives = np.zeros((4, 4, 4), dtype=np.float64)
        derivatives[0, 1, 1] = -2.0 * self.rate / (scale**3)
        derivatives[0, 2, 2] = derivatives[0, 1, 1]
        derivatives[0, 3, 3] = derivatives[0, 1, 1]
        return MetricSample(
            t=float(t),
            x=xyz,
            g_cov=g_cov,
            g_inv=g_inv,
            d_g_inv=derivatives,
            lapse=1.0,
            shift=np.zeros(3, dtype=np.float64),
            gamma_cov=g_cov[1:4, 1:4],
            gamma_inv=g_inv[1:4, 1:4],
            validity="valid",
            evidence_label="analytic_exact",
            source_revision=self.source_revision,
        )
