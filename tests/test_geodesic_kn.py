import numpy as np

from gr_bh_xr.geodesic_kn import hamiltonian_rhs_kn, trace_state_kn
from gr_bh_xr.metric_kn import KerrNewmanParams, ks_hamiltonian, ks_inverse_metric
from gr_bh_xr.types import RayState, TraceConfig


def _future_null_covector(
    params: KerrNewmanParams, x: np.ndarray, spatial_covector: np.ndarray
) -> np.ndarray:
    inverse = ks_inverse_metric(params, x[1:4])
    b = float(inverse[0, 1:4] @ spatial_covector)
    c = float(0.5 * spatial_covector @ inverse[1:4, 1:4] @ spatial_covector)
    roots = np.roots([0.5 * inverse[0, 0], b, c])
    candidates = [float(root.real) for root in roots if abs(float(root.imag)) < 1.0e-12]
    return np.concatenate(([min(candidates)], spatial_covector))


def test_kn_rhs_preserves_stationary_energy_structurally() -> None:
    params = KerrNewmanParams(M=1.0, a=0.5, charge=0.4)
    x = np.array([0.0, 12.0, 1.0, 3.0])
    p = _future_null_covector(params, x, np.array([-0.8, 0.1, 0.2]))

    rhs = hamiltonian_rhs_kn(params, 0.0, np.concatenate([x, p]))

    assert abs(ks_hamiltonian(params, x, p)) < 2.0e-15
    assert rhs[4] == 0.0


def test_kn_f64_oracle_traces_an_inward_equatorial_ray_to_horizon() -> None:
    params = KerrNewmanParams(M=1.0, a=0.3, charge=0.4)
    x = np.array([0.0, 20.0, 0.0, 0.0])
    p = _future_null_covector(params, x, np.array([-1.0, 0.0, 0.0]))
    diagnostics = trace_state_kn(
        params,
        RayState(x=x, p=p),
        TraceConfig(max_lambda=100.0, r_escape=40.0, horizon_eps=1.0e-5, max_step=0.5),
        r_obs=20.0,
    )

    assert diagnostics.event == "capture"
    assert diagnostics.h_max_abs < 2.0e-9
    assert diagnostics.e_drift_abs == 0.0
    assert diagnostics.lz_drift_abs < 1.0e-10
