"""Analytic and approximate providers for dynamic-spacetime validation."""

from .minkowski_dynamic import MinkowskiMetricProvider
from .bbh_orbit import (
    BinaryHoleState,
    BinaryTrajectory,
    FixedCircularBinaryOrbit,
    QuasiCircularInspiralOrbit,
)
from .bbh_superposed_ks import (
    SuperposedKerrSchildBBHProvider,
    boosted_kerr_ks_perturbation,
    boosted_schwarzschild_ks_perturbation,
    lorentz_boost_covector_jacobian,
)
from .bbh_remnant import MergerRemnantTrajectory, smooth_transition_weight
from .plane_gw import (
    PlaneGWMetricProvider,
    PlaneGWParameters,
    plane_gw_first_order_time_delay,
    plane_gw_initial_state,
)

__all__ = [
    "BinaryHoleState",
    "BinaryTrajectory",
    "FixedCircularBinaryOrbit",
    "QuasiCircularInspiralOrbit",
    "MinkowskiMetricProvider",
    "MergerRemnantTrajectory",
    "PlaneGWMetricProvider",
    "PlaneGWParameters",
    "plane_gw_first_order_time_delay",
    "plane_gw_initial_state",
    "SuperposedKerrSchildBBHProvider",
    "boosted_kerr_ks_perturbation",
    "boosted_schwarzschild_ks_perturbation",
    "lorentz_boost_covector_jacobian",
    "smooth_transition_weight",
]
