"""Smooth inspiral-to-remnant trajectory for the superposed KS provider."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from ..types import FloatArray
from .bbh_orbit import BinaryHoleState, BinaryTrajectory, QuasiCircularInspiralOrbit


def smooth_transition_weight(value: float | complex) -> float | complex:
    """Return the C-infinity transition function from paper Appendix B."""

    real_value = float(np.real(value))
    if real_value <= 0.0:
        return 0.0
    if real_value >= 1.0:
        return 1.0
    logit = -1.0 / value + 1.0 / (1.0 - value)
    if float(np.real(logit)) >= 0.0:
        return 1.0 / (1.0 + np.exp(-logit))
    exponential = np.exp(logit)
    return exponential / (1.0 + exponential)


def _transition_kinematics(
    value: float | complex, duration: float
) -> tuple[float | complex, float | complex, float | complex]:
    weight = smooth_transition_weight(value)
    if float(np.real(value)) <= 0.0 or float(np.real(value)) >= 1.0:
        return weight, 0.0, 0.0
    first = 1.0 / value**2 + 1.0 / (1.0 - value) ** 2
    second = -2.0 / value**3 + 2.0 / (1.0 - value) ** 3
    derivative_s = weight * (1.0 - weight) * first
    second_s = weight * (1.0 - weight) * (
        (1.0 - 2.0 * weight) * first**2 + second
    )
    return weight, derivative_s / duration, second_s / duration**2


@dataclass(frozen=True)
class MergerRemnantTrajectory:
    """Blend an accepted binary trajectory into a supplied Kerr remnant.

    Mass and specific spin follow Combi-Ressler Eqs. (14)-(15). Positions are
    additionally blended to a shared remnant worldline with derivatives kept
    internally consistent. Remnant fits are intentionally external inputs.
    """

    inspiral: BinaryTrajectory = QuasiCircularInspiralOrbit()
    transition_start: float = 100.0
    transition_duration: float = 20.0
    remnant_mass: float = 0.95
    remnant_spin: tuple[float, float, float] = (0.0, 0.0, 0.65)
    remnant_position_at_end: tuple[float, float, float] = (0.0, 0.0, 0.0)
    remnant_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        scalar_values = (
            self.transition_start,
            self.transition_duration,
            self.remnant_mass,
        )
        if not all(math.isfinite(value) for value in scalar_values):
            raise ValueError("remnant transition scalars must be finite.")
        if self.transition_duration <= 0.0:
            raise ValueError("transition_duration must be positive.")
        if self.remnant_mass <= 0.0:
            raise ValueError("remnant_mass must be positive.")
        for name in ("remnant_spin", "remnant_position_at_end", "remnant_velocity"):
            vector = np.asarray(getattr(self, name), dtype=np.float64)
            if vector.shape != (3,) or not np.all(np.isfinite(vector)):
                raise ValueError(f"{name} must be a finite three-vector.")
        if np.linalg.norm(self.remnant_spin) > self.remnant_mass + 1.0e-14:
            raise ValueError("remnant must satisfy the Kerr bound |a_f| <= M_f.")
        if np.linalg.norm(self.remnant_velocity) >= 1.0:
            raise ValueError("remnant_velocity must be timelike.")
        valid_until = getattr(self.inspiral, "valid_until", math.inf)
        if self.transition_end > valid_until:
            raise ValueError("transition must finish inside the inspiral validity domain.")

    @property
    def transition_end(self) -> float:
        return self.transition_start + self.transition_duration

    @property
    def source_revision(self) -> str:
        return "merger-remnant-supplied-v1"

    def transition_weight(self, t: float | complex) -> float | complex:
        value = (t - self.transition_start) / self.transition_duration
        return smooth_transition_weight(value)

    def states(self, t: float | complex) -> tuple[BinaryHoleState, BinaryHoleState]:
        real_time = float(np.real(t))
        if real_time <= self.transition_start:
            return self.inspiral.states(t)

        target_position = np.asarray(self.remnant_position_at_end) + np.asarray(
            self.remnant_velocity
        ) * (t - self.transition_end)
        target_velocity = np.asarray(self.remnant_velocity)
        target_acceleration = np.zeros(3)
        target_spin = np.asarray(self.remnant_spin)
        if real_time >= self.transition_end:
            remnant_term = BinaryHoleState(
                0.5 * self.remnant_mass,
                target_position,
                target_velocity,
                target_acceleration,
                target_spin,
            )
            return remnant_term, remnant_term

        source_states = self.inspiral.states(t)
        normalized = (t - self.transition_start) / self.transition_duration
        weight, weight_rate, weight_acceleration = _transition_kinematics(
            normalized, self.transition_duration
        )
        result = []
        for source in source_states:
            position_delta = target_position - source.position
            velocity_delta = target_velocity - source.velocity
            position = source.position + weight * position_delta
            velocity = (
                source.velocity
                + weight * velocity_delta
                + weight_rate * position_delta
            )
            acceleration = (
                source.acceleration
                + weight * (target_acceleration - source.acceleration)
                + 2.0 * weight_rate * velocity_delta
                + weight_acceleration * position_delta
            )
            result.append(
                BinaryHoleState(
                    source.mass * (1.0 - weight)
                    + 0.5 * self.remnant_mass * weight,
                    position,
                    velocity,
                    acceleration,
                    source.spin * (1.0 - weight) + target_spin * weight,
                )
            )
        return result[0], result[1]
