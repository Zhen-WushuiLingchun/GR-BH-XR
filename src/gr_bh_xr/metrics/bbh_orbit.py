"""Auditable orbital states for approximate binary-black-hole metrics."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from ..types import FloatArray


@dataclass(frozen=True)
class BinaryHoleState:
    """One hole's instantaneous background-frame state in geometric units."""

    mass: float
    position: FloatArray
    velocity: FloatArray
    acceleration: FloatArray

    def __post_init__(self) -> None:
        if not math.isfinite(self.mass) or self.mass <= 0.0:
            raise ValueError("hole mass must be positive and finite.")
        for name in ("position", "velocity", "acceleration"):
            value = np.asarray(getattr(self, name))
            if value.shape != (3,) or not np.all(np.isfinite(value)):
                raise ValueError(f"{name} must be a finite three-vector.")
            object.__setattr__(self, name, value)
        speed2 = np.dot(self.velocity, self.velocity)
        if float(np.real(speed2)) >= 1.0:
            raise ValueError("hole trajectory must remain timelike (|v| < 1).")


@dataclass(frozen=True)
class FixedCircularBinaryOrbit:
    """Newtonian circular equal-mass orbit used by the first SKS gate.

    The total mass and separation are constant. This is deliberately the
    smallest Combi-Ressler Eq. 11 slice: no radiation reaction, eccentricity,
    spin precession, merger interpolation, or remnant fit is implied.
    """

    total_mass: float = 1.0
    separation: float = 20.0
    phase0: float = 0.0
    angular_frequency: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.total_mass) or self.total_mass <= 0.0:
            raise ValueError("total_mass must be positive and finite.")
        if not math.isfinite(self.separation) or self.separation <= 0.0:
            raise ValueError("separation must be positive and finite.")
        if not math.isfinite(self.phase0):
            raise ValueError("phase0 must be finite.")
        omega = self.omega
        orbital_speed = 0.5 * self.separation * omega
        if not math.isfinite(omega) or omega <= 0.0:
            raise ValueError("angular_frequency must be positive and finite.")
        if orbital_speed >= 1.0:
            raise ValueError("circular orbit would be superluminal.")

    @property
    def omega(self) -> float:
        if self.angular_frequency is not None:
            return float(self.angular_frequency)
        return math.sqrt(self.total_mass / self.separation**3)

    @property
    def period(self) -> float:
        return 2.0 * math.pi / self.omega

    def states(self, t: float | complex) -> tuple[BinaryHoleState, BinaryHoleState]:
        """Return equal-mass hole states at global coordinate time ``t``."""

        phase = self.phase0 + self.omega * t
        cosine = np.cos(phase)
        sine = np.sin(phase)
        radius = 0.5 * self.separation
        omega = self.omega
        position = radius * np.array([cosine, sine, 0.0], dtype=np.result_type(t))
        velocity = radius * omega * np.array(
            [-sine, cosine, 0.0], dtype=np.result_type(t)
        )
        acceleration = -(omega * omega) * position
        mass = 0.5 * self.total_mass
        first = BinaryHoleState(mass, position, velocity, acceleration)
        second = BinaryHoleState(mass, -position, -velocity, -acceleration)
        return first, second

