import numpy as np

from gr_bh_xr.metric_kn import KerrNewmanParams, ks_invariants
from gr_bh_xr.types import RayState
from gr_bh_xr.validate_npgs_kerr import native_initial_state_to_python_ks
from gr_bh_xr.validate_npgs_kerr_newman import (
    NpgsKerrNewmanThresholds,
    _finite_stat,
)


def test_kerr_newman_native_gate_is_nonzero_charge_and_quality_two() -> None:
    thresholds = NpgsKerrNewmanThresholds()

    assert thresholds.event_agreement == 0.98
    assert thresholds.direction_median_rad == 1.0e-4
    assert thresholds.direction_rms_rad == 5.0e-4
    assert thresholds.minimum_native_quality == 2.0


def test_native_state_conversion_preserves_kn_initial_invariants() -> None:
    params = KerrNewmanParams(M=0.5, a=0.3, charge=0.25)
    native_x = np.array([20.0, 10.0, -5.0, 0.0])
    native_p = np.array([0.1, -0.3, 0.8, -1.0])

    state = native_initial_state_to_python_ks(native_x, native_p)
    values = ks_invariants(params, state.x, state.p)

    assert isinstance(state, RayState)
    assert np.isfinite(values.hamiltonian)
    assert values.energy == -1.0
    assert np.isfinite(values.angular_momentum_z)
    assert np.isfinite(values.carter_q)


def test_finite_stat_ignores_nan_and_handles_empty_groups() -> None:
    values = np.array([np.nan, 3.0, 1.0])

    assert _finite_stat(values, np.max) == 3.0
    assert _finite_stat(np.array([np.nan]), np.max) is None
