"""Shared dataclasses for Phase 1 reference geodesics.

The Phase 1 solver follows the analytic-source boundary in docs/equations.md:
Boyer-Lindquist exterior coordinates are used for the reference integrator and
for conserved-quantity checks; horizon-penetrating Kerr-Schild integration is
deferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

EventType = Literal["capture", "escape", "disk_crossing", "invalid"]
FailureReason = Literal[
    "none",
    "axis_coordinate_singularity",
    "trace_exception",
    "unclassified_max_lambda",
    "solver_failure",
    "polar_step_overshoot",
]
FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class MetricParams:
    """Boyer-Lindquist Kerr metric parameters in geometric units."""

    M: float = 1.0
    a: float = 0.0

    def __post_init__(self) -> None:
        if self.M <= 0.0:
            raise ValueError("Metric mass M must be positive.")
        if abs(self.a) >= self.M:
            raise ValueError("Phase 1 supports only sub-extremal |a| < M.")


@dataclass(frozen=True)
class CameraConfig:
    """Asymptotic Bardeen screen coordinate configuration."""

    r_obs: float
    theta_obs: float
    alpha: float
    beta: float

    def __post_init__(self) -> None:
        if self.r_obs <= 0.0:
            raise ValueError("Observer radius must be positive.")
        if not (0.0 < self.theta_obs < np.pi):
            raise ValueError("Observer theta must be in (0, pi).")


@dataclass(frozen=True)
class RayState:
    """Canonical Boyer-Lindquist ray state `(x^mu, p_mu)`."""

    x: FloatArray
    p: FloatArray


@dataclass(frozen=True)
class TraceConfig:
    """Integrator and event settings for a single reference ray."""

    max_lambda: float = 800.0
    r_escape: float | None = None
    horizon_eps: float = 3.0e-1
    rtol: float = 1.0e-9
    atol: float = 1.0e-11
    max_step: float = 2.0
    stop_on_disk: bool = False
    axis_eps: float = 1.0e-5
    axis_lz_tol: float = 1.0e-12


@dataclass(frozen=True)
class RayDiagnostics:
    """Trace diagnostics required by the Phase 1 validation gate."""

    event: EventType
    h_max_abs: float
    e_drift_abs: float
    lz_drift_abs: float
    q_drift_abs: float
    lambda_end: float
    steps: int
    min_r: float
    disk_crossings: int
    q_initial: float
    q_final: float
    escape_theta: float = np.nan
    escape_phi: float = np.nan
    escape_dir_x: float = np.nan
    escape_dir_y: float = np.nan
    escape_dir_z: float = np.nan
    failure_reason: FailureReason = "none"
    message: str = ""
