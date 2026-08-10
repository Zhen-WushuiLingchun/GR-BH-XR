"""Independent finite-difference ADM constraints for metric-provider audits."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol

import numpy as np

from .dynamic_types import MetricSample
from .types import FloatArray


class _MetricProvider(Protocol):
    def sample(self, t: float, x: FloatArray) -> MetricSample: ...


@dataclass(frozen=True)
class ConstraintSample:
    """Vacuum ADM constraint residual at one coordinate event."""

    t: float
    x: FloatArray
    stencil_step: float
    hamiltonian: float
    momentum: FloatArray
    ricci_scalar: float
    extrinsic_trace: float

    @property
    def momentum_norm(self) -> float:
        return float(np.linalg.norm(self.momentum))


@dataclass(frozen=True)
class _AdmFields:
    lapse: float
    shift: FloatArray
    gamma_cov: FloatArray
    gamma_inv: FloatArray


def adm_constraint_sample(
    provider: _MetricProvider,
    t: float,
    x: FloatArray,
    *,
    stencil_step: float = 0.04,
) -> ConstraintSample:
    """Evaluate vacuum Hamiltonian and momentum constraints.

    The implementation is deliberately independent of the provider's metric
    derivatives. Centered finite differences act on reconstructed ADM fields.
    It is an audit oracle, not the production ray-tracing path.
    """

    if not math.isfinite(stencil_step) or stencil_step <= 0.0:
        raise ValueError("stencil_step must be positive and finite.")
    point = np.asarray(x, dtype=np.float64)
    if point.shape != (3,) or not np.all(np.isfinite(point)):
        raise ValueError("x must be a finite three-vector.")

    cache: dict[tuple[float, float, float, float], _AdmFields] = {}

    def adm(time: float, xyz: FloatArray) -> _AdmFields:
        key = (float(time), *(float(value) for value in xyz))
        if key not in cache:
            if hasattr(provider, "metric_and_adm"):
                _g_cov, _g_inv, lapse, shift, gamma_cov, gamma_inv = (
                    provider.metric_and_adm(time, xyz)  # type: ignore[attr-defined]
                )
                cache[key] = _AdmFields(lapse, shift, gamma_cov, gamma_inv)
            else:
                sample = provider.sample(time, xyz)
                if sample.validity != "valid":
                    raise ValueError("constraint stencil left provider validity domain.")
                cache[key] = _AdmFields(
                    sample.lapse, sample.shift, sample.gamma_cov, sample.gamma_inv
                )
        return cache[key]

    def offset(time: float, xyz: FloatArray, axis: int, amount: float) -> tuple[float, FloatArray]:
        if axis == 0:
            return time + amount, xyz
        shifted = xyz.copy()
        shifted[axis - 1] += amount
        return time, shifted

    def derivative(field, time: float, xyz: FloatArray, axis: int) -> FloatArray:
        plus_t, plus_x = offset(time, xyz, axis, stencil_step)
        minus_t, minus_x = offset(time, xyz, axis, -stencil_step)
        return (field(adm(plus_t, plus_x)) - field(adm(minus_t, minus_x))) / (
            2.0 * stencil_step
        )

    def christoffel(time: float, xyz: FloatArray) -> FloatArray:
        fields = adm(time, xyz)
        d_gamma = np.empty((3, 3, 3), dtype=np.float64)
        for axis in range(3):
            d_gamma[axis] = derivative(
                lambda value: value.gamma_cov, time, xyz, axis + 1
            )
        symbols = np.zeros((3, 3, 3), dtype=np.float64)
        for upper in range(3):
            for left in range(3):
                for right in range(3):
                    symbols[upper, left, right] = 0.5 * sum(
                        fields.gamma_inv[upper, lower]
                        * (
                            d_gamma[left, lower, right]
                            + d_gamma[right, lower, left]
                            - d_gamma[lower, left, right]
                        )
                        for lower in range(3)
                    )
        return symbols

    def extrinsic_curvature(time: float, xyz: FloatArray) -> tuple[FloatArray, FloatArray]:
        fields = adm(time, xyz)
        symbols = christoffel(time, xyz)
        d_gamma_dt = derivative(lambda value: value.gamma_cov, time, xyz, 0)

        def beta_cov(value: _AdmFields) -> FloatArray:
            return value.gamma_cov @ value.shift

        beta_lower = beta_cov(fields)
        d_beta = np.empty((3, 3), dtype=np.float64)
        for axis in range(3):
            d_beta[axis] = derivative(beta_cov, time, xyz, axis + 1)
        covariant_beta = np.empty((3, 3), dtype=np.float64)
        for left in range(3):
            for right in range(3):
                covariant_beta[left, right] = d_beta[left, right] - np.dot(
                    symbols[:, left, right], beta_lower
                )
        curvature = (
            -d_gamma_dt + covariant_beta + covariant_beta.T
        ) / (2.0 * fields.lapse)
        return curvature, symbols

    fields = adm(float(t), point)
    curvature, symbols = extrinsic_curvature(float(t), point)

    d_symbols = np.empty((3, 3, 3, 3), dtype=np.float64)
    for axis in range(3):
        plus = point.copy()
        minus = point.copy()
        plus[axis] += stencil_step
        minus[axis] -= stencil_step
        d_symbols[axis] = (
            christoffel(float(t), plus) - christoffel(float(t), minus)
        ) / (2.0 * stencil_step)

    ricci_cov = np.zeros((3, 3), dtype=np.float64)
    for left in range(3):
        for right in range(3):
            value = 0.0
            for upper in range(3):
                value += d_symbols[upper, upper, left, right]
                value -= d_symbols[right, upper, left, upper]
                for lower in range(3):
                    value += symbols[upper, left, right] * symbols[lower, upper, lower]
                    value -= symbols[lower, left, upper] * symbols[upper, right, lower]
            ricci_cov[left, right] = value
    ricci_scalar = float(np.einsum("ij,ij->", fields.gamma_inv, ricci_cov))

    curvature_up = fields.gamma_inv @ curvature @ fields.gamma_inv
    trace = float(np.einsum("ij,ij->", fields.gamma_inv, curvature))
    curvature_squared = float(np.einsum("ij,ij->", curvature, curvature_up))
    hamiltonian = ricci_scalar + trace * trace - curvature_squared

    def momentum_tensor(time: float, xyz: FloatArray) -> FloatArray:
        local = adm(time, xyz)
        local_k, _ = extrinsic_curvature(time, xyz)
        local_trace = float(np.einsum("ij,ij->", local.gamma_inv, local_k))
        return local.gamma_inv @ local_k @ local.gamma_inv - local.gamma_inv * local_trace

    momentum_up = momentum_tensor(float(t), point)
    d_momentum = np.empty((3, 3, 3), dtype=np.float64)
    for axis in range(3):
        plus = point.copy()
        minus = point.copy()
        plus[axis] += stencil_step
        minus[axis] -= stencil_step
        d_momentum[axis] = (
            momentum_tensor(float(t), plus) - momentum_tensor(float(t), minus)
        ) / (2.0 * stencil_step)

    momentum = np.zeros(3, dtype=np.float64)
    for upper in range(3):
        value = 0.0
        for derivative_axis in range(3):
            value += d_momentum[derivative_axis, upper, derivative_axis]
            for lower in range(3):
                value += (
                    symbols[upper, derivative_axis, lower]
                    * momentum_up[lower, derivative_axis]
                )
                value += (
                    symbols[derivative_axis, derivative_axis, lower]
                    * momentum_up[upper, lower]
                )
        momentum[upper] = value

    return ConstraintSample(
        t=float(t),
        x=point,
        stencil_step=stencil_step,
        hamiltonian=float(hamiltonian),
        momentum=momentum,
        ricci_scalar=ricci_scalar,
        extrinsic_trace=trace,
    )

