"""Shared contracts for time-dependent spacetime tracing.

The dynamic path uses Cartesian coordinates with signature ``(-,+,+,+)`` and
covariant canonical momenta.  It intentionally does not expose stationary
Kerr conservation diagnostics as generic fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal, Protocol, runtime_checkable

import numpy as np

from .types import FloatArray


MetricValidity = Literal["valid", "outside_domain", "invalid"]
EvidenceLabel = Literal[
    "analytic_exact",
    "physics_approximation",
    "nr_snapshot",
    "visual_only",
]


@dataclass(frozen=True)
class MetricSample:
    """Metric and derivative sample at one spacetime event.

    ``d_g_inv[mu, alpha, beta]`` is ``partial_mu g^{alpha beta}``.
    The ADM fields follow
    ``g^{00}=-1/lapse^2`` and ``g^{0i}=shift^i/lapse^2``.
    """

    t: float
    x: FloatArray
    g_cov: FloatArray
    g_inv: FloatArray
    d_g_inv: FloatArray
    lapse: float
    shift: FloatArray
    gamma_cov: FloatArray
    gamma_inv: FloatArray
    validity: MetricValidity
    evidence_label: EvidenceLabel
    source_revision: str
    interpolation_error: float = 0.0

    def __post_init__(self) -> None:
        arrays = {
            "x": (self.x, (3,)),
            "g_cov": (self.g_cov, (4, 4)),
            "g_inv": (self.g_inv, (4, 4)),
            "d_g_inv": (self.d_g_inv, (4, 4, 4)),
            "shift": (self.shift, (3,)),
            "gamma_cov": (self.gamma_cov, (3, 3)),
            "gamma_inv": (self.gamma_inv, (3, 3)),
        }
        for name, (value, shape) in arrays.items():
            array = np.asarray(value, dtype=np.float64)
            if array.shape != shape:
                raise ValueError(f"{name} must have shape {shape}, got {array.shape}.")
            object.__setattr__(self, name, array)
        if not np.isfinite(self.t):
            raise ValueError("metric sample time must be finite.")
        if self.validity == "valid":
            numeric = [self.x, self.g_cov, self.g_inv, self.d_g_inv, self.shift,
                       self.gamma_cov, self.gamma_inv]
            if not all(np.all(np.isfinite(value)) for value in numeric):
                raise ValueError("a valid metric sample must contain only finite arrays.")
            if not np.isfinite(self.lapse) or self.lapse <= 0.0:
                raise ValueError("a valid metric sample must have positive finite lapse.")
        if not np.isfinite(self.interpolation_error) or self.interpolation_error < 0.0:
            raise ValueError("interpolation_error must be finite and nonnegative.")
        if not self.source_revision:
            raise ValueError("source_revision must be non-empty.")


@runtime_checkable
class TimeDependentMetricProvider(Protocol):
    """Provider interface shared by analytic, approximate, and NR metrics."""

    def sample(self, t: float, x: FloatArray) -> MetricSample:
        """Sample the metric at coordinate time ``t`` and spatial point ``x``."""


DynamicEventFunction = Callable[[float, FloatArray, FloatArray], float]


@dataclass(frozen=True)
class DynamicEventSpec:
    """An event surface kept deliberately separate from the metric provider."""

    name: str
    function: DynamicEventFunction
    terminal: bool = True
    direction: float = 0.0
    provenance: str = "caller"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("dynamic event name must be non-empty.")
        if self.direction not in (-1.0, 0.0, 1.0):
            raise ValueError("dynamic event direction must be -1, 0, or 1.")


@dataclass(frozen=True)
class DynamicTraceConfig:
    """DOP853 settings and caller-owned event surfaces."""

    max_lambda: float = 800.0
    rtol: float = 1.0e-9
    atol: float = 1.0e-11
    max_step: float = 2.0
    events: tuple[DynamicEventSpec, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.max_lambda <= 0.0 or self.max_step <= 0.0:
            raise ValueError("max_lambda and max_step must be positive.")
        if self.rtol <= 0.0 or self.atol <= 0.0:
            raise ValueError("rtol and atol must be positive.")


@dataclass(frozen=True)
class DynamicRayDiagnostics:
    """Audit record for one generic dynamic-spacetime ray."""

    event: str
    event_provenance: str
    failure_reason: str
    message: str
    h_initial: float
    h_final: float
    h_max_abs: float
    lambda_end: float
    steps: int
    final_x: FloatArray
    final_p: FloatArray
    p_t_initial: float
    p_t_final: float
    provider_valid_samples: int
    provider_invalid_samples: int
    interpolation_error_max: float
    metric_evidence_label: str
    metric_source_revision: str

    def __post_init__(self) -> None:
        for name in ("final_x", "final_p"):
            array = np.asarray(getattr(self, name), dtype=np.float64)
            if array.shape != (4,):
                raise ValueError(f"{name} must have shape (4,).")
            object.__setattr__(self, name, array)
