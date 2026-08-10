"""Linear transverse-traceless plane-wave metric used as a dynamic gate.

The physical metric follows Angelil and Saha (2015), Eq. (2), generalized to
an arbitrary propagation direction and polarization angle.  Its inverse and
derivatives are evaluated exactly for the stated finite-amplitude metric;
vacuum validity is claimed only through first order in the strain amplitude.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from ..dynamic_metric import _adm_from_metric
from ..dynamic_types import MetricSample
from ..metric_ks import MINKOWSKI_COVARIANT, MINKOWSKI_INVERSE
from ..types import FloatArray, RayState


def _unit_vector(value: tuple[float, float, float] | FloatArray, name: str) -> FloatArray:
    vector = np.asarray(value, dtype=np.float64)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must be a finite three-vector.")
    norm = float(np.linalg.norm(vector))
    if norm <= 0.0:
        raise ValueError(f"{name} must be nonzero.")
    return vector / norm


def _transverse_basis(direction: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Return a deterministic right-handed basis transverse to ``direction``."""

    candidates = np.eye(3, dtype=np.float64)
    seed = candidates[int(np.argmin(np.abs(candidates @ direction)))]
    basis_u = seed - float(np.dot(seed, direction)) * direction
    basis_u /= np.linalg.norm(basis_u)
    basis_v = np.cross(direction, basis_u)
    return basis_u, basis_v


@dataclass(frozen=True)
class PlaneGWParameters:
    """Parameters for one monochromatic TT plane gravitational wave.

    ``amplitude`` is the physical dimensionless strain.  Display gain is kept
    out of this provider so a visualization cannot silently alter spacetime.
    """

    amplitude: float = 1.0e-3
    angular_frequency: float = 1.0
    propagation_direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    polarization_angle: float = 0.0
    phase: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.amplitude) or abs(self.amplitude) >= 1.0:
            raise ValueError("plane-GW amplitude must be finite with |h| < 1.")
        if not math.isfinite(self.angular_frequency) or self.angular_frequency <= 0.0:
            raise ValueError("plane-GW angular_frequency must be positive and finite.")
        _unit_vector(self.propagation_direction, "propagation_direction")
        if not math.isfinite(self.polarization_angle) or not math.isfinite(self.phase):
            raise ValueError("plane-GW polarization angle and phase must be finite.")


@dataclass(frozen=True)
class PlaneGWMetricProvider:
    """Analytic finite-amplitude metric for a linearized TT plane wave."""

    parameters: PlaneGWParameters
    source_revision: str = "gr-bh-xr.plane-gw-tt.v1"

    @property
    def propagation_direction(self) -> FloatArray:
        return _unit_vector(self.parameters.propagation_direction, "propagation_direction")

    @property
    def polarization_tensor(self) -> FloatArray:
        direction = self.propagation_direction
        basis_u, basis_v = _transverse_basis(direction)
        plus = np.outer(basis_u, basis_u) - np.outer(basis_v, basis_v)
        cross = np.outer(basis_u, basis_v) + np.outer(basis_v, basis_u)
        angle2 = 2.0 * self.parameters.polarization_angle
        return math.cos(angle2) * plus + math.sin(angle2) * cross

    def phase_at(self, t: float, x: FloatArray) -> float:
        return (
            self.parameters.angular_frequency
            * (float(np.dot(self.propagation_direction, np.asarray(x))) - float(t))
            + self.parameters.phase
        )

    def sample(self, t: float, x: FloatArray) -> MetricSample:
        xyz = np.asarray(x, dtype=np.float64)
        if xyz.shape != (3,):
            raise ValueError("x must have shape (3,).")
        tensor = self.polarization_tensor
        phase = self.phase_at(t, xyz)
        strain = self.parameters.amplitude * math.cos(phase)
        gamma_cov = np.eye(3, dtype=np.float64) + strain * tensor
        gamma_inv = np.linalg.inv(gamma_cov)
        g_cov = MINKOWSKI_COVARIANT.copy()
        g_inv = MINKOWSKI_INVERSE.copy()
        g_cov[1:4, 1:4] = gamma_cov
        g_inv[1:4, 1:4] = gamma_inv

        phase_gradient = self.parameters.angular_frequency * np.concatenate(
            [[-1.0], self.propagation_direction]
        )
        d_g_inv = np.zeros((4, 4, 4), dtype=np.float64)
        for mu in range(4):
            d_gamma_cov = (
                -self.parameters.amplitude
                * math.sin(phase)
                * phase_gradient[mu]
                * tensor
            )
            d_g_inv[mu, 1:4, 1:4] = -gamma_inv @ d_gamma_cov @ gamma_inv

        lapse, shift, adm_gamma_cov, adm_gamma_inv = _adm_from_metric(g_cov, g_inv)
        return MetricSample(
            t=float(t),
            x=xyz,
            g_cov=g_cov,
            g_inv=g_inv,
            d_g_inv=d_g_inv,
            lapse=lapse,
            shift=shift,
            gamma_cov=adm_gamma_cov,
            gamma_inv=adm_gamma_inv,
            validity="valid",
            evidence_label="physics_approximation",
            source_revision=self.source_revision,
        )


def plane_gw_initial_state(
    provider: PlaneGWMetricProvider,
    ray_direction: tuple[float, float, float] | FloatArray,
    *,
    t0: float = 0.0,
    x0: tuple[float, float, float] | FloatArray = (0.0, 0.0, 0.0),
) -> RayState:
    """Launch a null ray with the selected spatial coordinate direction."""

    direction = _unit_vector(ray_direction, "ray_direction")
    xyz = np.asarray(x0, dtype=np.float64)
    sample = provider.sample(t0, xyz)
    dt_dlambda = math.sqrt(float(direction @ sample.gamma_cov @ direction))
    tangent = np.concatenate([[dt_dlambda], direction])
    momentum = sample.g_cov @ tangent
    return RayState(x=np.concatenate([[float(t0)], xyz]), p=momentum)


def plane_gw_first_order_time_delay(
    parameters: PlaneGWParameters,
    ray_direction: tuple[float, float, float] | FloatArray,
    distance: float,
) -> float:
    """Return the first-order fixed-plane arrival-time shift.

    This is Eq. (14) of Angelil and Saha (2015) evaluated on the unperturbed
    ray.  The endpoint is the plane ``n dot x = distance``.
    """

    if not math.isfinite(distance) or distance <= 0.0:
        raise ValueError("distance must be positive and finite.")
    provider = PlaneGWMetricProvider(parameters)
    direction = _unit_vector(ray_direction, "ray_direction")
    projection = float(direction @ provider.polarization_tensor @ direction)
    phase_rate = parameters.angular_frequency * (
        float(np.dot(provider.propagation_direction, direction)) - 1.0
    )
    if abs(phase_rate * distance) < 1.0e-8:
        integral = distance * math.cos(parameters.phase)
    else:
        integral = (
            math.sin(parameters.phase + phase_rate * distance)
            - math.sin(parameters.phase)
        ) / phase_rate
    return 0.5 * parameters.amplitude * projection * integral
