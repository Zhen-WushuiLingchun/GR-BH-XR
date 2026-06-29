"""Physics-auditable black-hole reference tools."""

from .camera import initial_ray_state, screen_constants
from .geodesic import trace_ray
from .metric import carter_constant, hamiltonian, horizon_radius
from .types import CameraConfig, MetricParams, RayDiagnostics, RayState, TraceConfig

__all__ = [
    "CameraConfig",
    "MetricParams",
    "RayDiagnostics",
    "RayState",
    "TraceConfig",
    "carter_constant",
    "hamiltonian",
    "horizon_radius",
    "initial_ray_state",
    "screen_constants",
    "trace_ray",
]
