"""Equal-mass superposed boosted Kerr-Schild BBH metric.

This is the first validated slice of Combi and Ressler Eq. (11): two
nonspinning Schwarzschild Kerr-Schild perturbations move on a fixed circular
orbit. It is a fast physics approximation, not an Einstein evolution.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from ..dynamic_metric import _adm_from_metric
from ..dynamic_types import MetricSample
from ..metric_ks import MINKOWSKI_COVARIANT
from ..types import FloatArray
from .bbh_orbit import BinaryHoleState, FixedCircularBinaryOrbit


_COMPLEX_STEP = 1.0e-28


def lorentz_boost_covector_jacobian(velocity: FloatArray) -> FloatArray:
    """Return ``partial X^a / partial x^b`` from Combi-Ressler Eq. (10)."""

    v = np.asarray(velocity)
    speed2 = np.dot(v, v)
    gamma = 1.0 / np.sqrt(1.0 - speed2)
    dtype = np.result_type(v, gamma)
    jacobian = np.eye(4, dtype=dtype)
    jacobian[0, 0] = gamma
    jacobian[0, 1:4] = -gamma * v
    jacobian[1:4, 0] = -gamma * v
    if abs(speed2) > 1.0e-30:
        jacobian[1:4, 1:4] += ((gamma - 1.0) / speed2) * np.outer(v, v)
    return jacobian


def boosted_schwarzschild_ks_perturbation(
    event: FloatArray, hole: BinaryHoleState
) -> tuple[FloatArray, complex]:
    """Return one boosted Schwarzschild KS perturbation and rest radius."""

    x = np.asarray(event)
    displacement = x[1:4] - hole.position
    v = hole.velocity
    speed2 = np.dot(v, v)
    gamma = 1.0 / np.sqrt(1.0 - speed2)
    rest_position = displacement.copy()
    if abs(speed2) > 1.0e-30:
        rest_position += ((gamma - 1.0) / speed2) * np.dot(v, displacement) * v
    radius = np.sqrt(np.dot(rest_position, rest_position))
    if abs(radius) <= 1.0e-14:
        raise ValueError("superposed KS metric is singular at a hole center.")

    rest_l_cov = np.concatenate(
        [np.ones(1, dtype=np.result_type(event)), rest_position / radius]
    )
    jacobian = lorentz_boost_covector_jacobian(v)
    global_l_cov = jacobian.T @ rest_l_cov
    perturbation = (2.0 * hole.mass / radius) * np.outer(global_l_cov, global_l_cov)
    return perturbation, radius


@dataclass(frozen=True)
class SuperposedKerrSchildBBHProvider:
    """Combi-Ressler Eq. (11) for a fixed equal-mass circular binary."""

    orbit: FixedCircularBinaryOrbit = FixedCircularBinaryOrbit()
    worldtube_factor: float = 2.0
    source_revision: str = "gr-bh-xr.combi-ressler-eq11.equal-mass-v1"

    def __post_init__(self) -> None:
        if not math.isfinite(self.worldtube_factor) or self.worldtube_factor <= 0.0:
            raise ValueError("worldtube_factor must be positive and finite.")

    @property
    def evidence_label(self) -> str:
        return "physics_approximation"

    def hole_states(self, t: float | complex) -> tuple[BinaryHoleState, BinaryHoleState]:
        return self.orbit.states(t)

    def covariant_metric(self, t: float | complex, x: FloatArray) -> FloatArray:
        event = np.concatenate([[t], np.asarray(x)])
        dtype = np.result_type(event)
        metric = MINKOWSKI_COVARIANT.astype(dtype, copy=True)
        for hole in self.hole_states(t):
            perturbation, _radius = boosted_schwarzschild_ks_perturbation(event, hole)
            metric += perturbation
        return metric

    def inverse_metric(self, t: float | complex, x: FloatArray) -> FloatArray:
        return np.linalg.inv(self.covariant_metric(t, x))

    def rest_radii(self, t: float, x: FloatArray) -> tuple[float, float]:
        event = np.concatenate([[float(t)], np.asarray(x, dtype=np.float64)])
        radii = []
        for hole in self.hole_states(float(t)):
            _perturbation, radius = boosted_schwarzschild_ks_perturbation(event, hole)
            radii.append(float(np.real(radius)))
        return radii[0], radii[1]

    def metric_and_adm(
        self, t: float, x: FloatArray
    ) -> tuple[FloatArray, FloatArray, float, FloatArray, FloatArray, FloatArray]:
        g_cov = np.asarray(self.covariant_metric(t, x), dtype=np.float64)
        g_inv = np.linalg.inv(g_cov)
        lapse, shift, gamma_cov, gamma_inv = _adm_from_metric(g_cov, g_inv)
        return g_cov, g_inv, lapse, shift, gamma_cov, gamma_inv

    def sample(self, t: float, x: FloatArray) -> MetricSample:
        xyz = np.asarray(x, dtype=np.float64)
        if xyz.shape != (3,) or not np.all(np.isfinite(xyz)):
            raise ValueError("x must be a finite three-vector.")
        g_cov, g_inv, lapse, shift, gamma_cov, gamma_inv = self.metric_and_adm(t, xyz)

        event = np.concatenate([[float(t)], xyz])
        d_g_inv = np.empty((4, 4, 4), dtype=np.float64)
        for mu in range(4):
            perturbed = event.astype(np.complex128)
            perturbed[mu] += 1j * _COMPLEX_STEP
            inverse = self.inverse_metric(perturbed[0], perturbed[1:4])
            d_g_inv[mu] = np.imag(inverse) / _COMPLEX_STEP

        radii = self.rest_radii(t, xyz)
        holes = self.hole_states(t)
        outside_worldtubes = all(
            radius > self.worldtube_factor * hole.mass
            for radius, hole in zip(radii, holes, strict=True)
        )
        return MetricSample(
            t=float(t),
            x=xyz,
            g_cov=g_cov,
            g_inv=g_inv,
            d_g_inv=d_g_inv,
            lapse=lapse,
            shift=shift,
            gamma_cov=gamma_cov,
            gamma_inv=gamma_inv,
            validity="valid" if outside_worldtubes else "outside_domain",
            evidence_label="physics_approximation",
            source_revision=self.source_revision,
        )

