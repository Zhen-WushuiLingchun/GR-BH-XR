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


@dataclass(frozen=True)
class QuasiCircularInspiralOrbit:
    """Leading-quadrupole adiabatic inspiral with an explicit validity cutoff.

    ``mass_ratio`` is ``q = m1 / m2`` with ``0 < q <= 1``. The relative
    separation follows the Peters-Mathews circular radiation-reaction law.
    This is a validated PN entry model, not the full Combi-Ressler 4PN orbit.
    """

    total_mass: float = 1.0
    initial_separation: float = 20.0
    mass_ratio: float = 1.0
    phase0: float = 0.0
    t0: float = 0.0
    minimum_separation: float = 6.0

    def __post_init__(self) -> None:
        values = (
            self.total_mass,
            self.initial_separation,
            self.mass_ratio,
            self.phase0,
            self.t0,
            self.minimum_separation,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("inspiral parameters must be finite.")
        if self.total_mass <= 0.0:
            raise ValueError("total_mass must be positive.")
        if not (0.0 < self.mass_ratio <= 1.0):
            raise ValueError("mass_ratio must satisfy 0 < q=m1/m2 <= 1.")
        if self.minimum_separation <= 0.0:
            raise ValueError("minimum_separation must be positive.")
        if self.initial_separation <= self.minimum_separation:
            raise ValueError("initial_separation must exceed minimum_separation.")

    @property
    def masses(self) -> tuple[float, float]:
        second = self.total_mass / (1.0 + self.mass_ratio)
        first = self.mass_ratio * second
        return first, second

    @property
    def symmetric_mass_ratio(self) -> float:
        first, second = self.masses
        return first * second / self.total_mass**2

    @property
    def radiation_reaction_coefficient(self) -> float:
        return 64.0 / 5.0 * self.symmetric_mass_ratio * self.total_mass**3

    @property
    def valid_until(self) -> float:
        numerator = self.initial_separation**4 - self.minimum_separation**4
        return self.t0 + numerator / (4.0 * self.radiation_reaction_coefficient)

    def separation_at(self, t: float | complex) -> float | complex:
        argument = self.initial_separation**4 - 4.0 * self.radiation_reaction_coefficient * (
            t - self.t0
        )
        if not np.iscomplexobj(argument) and float(argument) <= self.minimum_separation**4:
            raise ValueError("inspiral left its preregistered PN validity domain.")
        return np.power(argument, 0.25)

    def phase_at(self, t: float | complex) -> float | complex:
        separation = self.separation_at(t)
        coefficient = 1.0 / (
            32.0 * self.symmetric_mass_ratio * self.total_mass**2.5
        )
        return self.phase0 + coefficient * (
            self.initial_separation**2.5 - separation**2.5
        )

    def states(self, t: float | complex) -> tuple[BinaryHoleState, BinaryHoleState]:
        separation = self.separation_at(t)
        phase = self.phase_at(t)
        coefficient = self.radiation_reaction_coefficient
        radial_rate = -coefficient / separation**3
        radial_acceleration = -3.0 * coefficient**2 / separation**7
        omega = np.sqrt(self.total_mass / separation**3)
        omega_rate = -1.5 * omega * radial_rate / separation

        cosine = np.cos(phase)
        sine = np.sin(phase)
        dtype = np.result_type(t)
        radial = np.array([cosine, sine, 0.0], dtype=dtype)
        azimuthal = np.array([-sine, cosine, 0.0], dtype=dtype)
        relative_position = separation * radial
        relative_velocity = radial_rate * radial + separation * omega * azimuthal
        relative_acceleration = (
            (radial_acceleration - separation * omega * omega) * radial
            + (2.0 * radial_rate * omega + separation * omega_rate) * azimuthal
        )

        first_mass, second_mass = self.masses
        first_fraction = second_mass / self.total_mass
        second_fraction = first_mass / self.total_mass
        first = BinaryHoleState(
            first_mass,
            first_fraction * relative_position,
            first_fraction * relative_velocity,
            first_fraction * relative_acceleration,
        )
        second = BinaryHoleState(
            second_mass,
            -second_fraction * relative_position,
            -second_fraction * relative_velocity,
            -second_fraction * relative_acceleration,
        )
        return first, second
