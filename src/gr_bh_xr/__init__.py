"""Physics-auditable black-hole reference tools."""

from .camera import initial_ray_state, screen_constants
from .critical_curve import (
    critical_curve_polygon,
    photon_shell_bounds,
    screen_coordinates,
    spherical_photon_constants,
)
from .geodesic import trace_ray
from .metric import (
    carter_constant,
    hamiltonian,
    horizon_radius,
    inverse_metric_derivatives_finite_difference,
)
from .types import (
    CameraConfig,
    FailureReason,
    MetricParams,
    RayDiagnostics,
    RayState,
    TraceConfig,
)

__all__ = [
    "CameraConfig",
    "FailureReason",
    "MetricParams",
    "RayDiagnostics",
    "RayState",
    "TraceConfig",
    "carter_constant",
    "critical_curve_polygon",
    "hamiltonian",
    "horizon_radius",
    "initial_ray_state",
    "inverse_metric_derivatives_finite_difference",
    "photon_shell_bounds",
    "screen_coordinates",
    "screen_constants",
    "spherical_photon_constants",
    "trace_ray",
]
