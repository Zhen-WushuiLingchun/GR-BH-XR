import numpy as np

from gr_bh_xr.metric_kn import (
    KerrNewmanParams,
    bl_to_ks_cartesian,
    ks_hamiltonian,
    ks_inverse_metric,
    ks_metric,
)
from gr_bh_xr.polarization_kn import (
    ks_to_bl_coordinates,
    project_null_covector_time,
    reproject_screen_basis,
    trace_polarization_basis_kn,
)
from gr_bh_xr.types import RayState, TraceConfig


def test_ks_to_bl_coordinates_roundtrip_oblate_map() -> None:
    params = KerrNewmanParams(M=0.5, a=0.4, charge=0.15)
    expected = (7.0, 1.1, -0.8)
    xyz = bl_to_ks_cartesian(*expected, params.a)

    actual = ks_to_bl_coordinates(params, xyz)

    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=2.0e-15)


def test_null_projection_and_screen_basis_are_metric_orthonormal() -> None:
    params = KerrNewmanParams(M=0.5, a=0.4, charge=0.15)
    state = RayState(
        x=np.array([0.0, 20.0, 0.0, 10.0]),
        p=np.array([-1.0, 1.0, 0.1, 0.5]),
    )
    projected = project_null_covector_time(params, state)
    seeds = np.array([[0.0, 0.0, 1.0, 0.0], [0.0, -0.5, 0.0, 1.0]])
    basis_cov = reproject_screen_basis(params, projected, seeds)
    inverse = ks_inverse_metric(params, projected.x[1:4])
    basis_up = np.einsum("ij,bj->bi", inverse, basis_cov)
    gram = basis_up @ ks_metric(params, projected.x[1:4]) @ basis_up.T

    assert abs(ks_hamiltonian(params, projected.x, projected.p)) < 1.0e-15
    np.testing.assert_allclose(gram, np.eye(2), rtol=0.0, atol=3.0e-15)
    np.testing.assert_allclose(basis_up @ projected.p, 0.0, rtol=0.0, atol=2.0e-15)


def test_complete_walker_penrose_scalar_tracks_direct_parallel_transport() -> None:
    params = KerrNewmanParams(M=0.5, a=0.4, charge=0.15)
    state = project_null_covector_time(
        params,
        RayState(
            x=np.array([0.0, 20.0, 0.0, 10.0]),
            p=np.array([-1.0, 1.0, 0.1, 0.5]),
        ),
    )
    basis = reproject_screen_basis(
        params,
        state,
        np.array([[0.0, 0.0, 1.0, 0.0], [0.0, -0.5, 0.0, 1.0]]),
    )

    diagnostics = trace_polarization_basis_kn(
        params,
        state,
        basis,
        TraceConfig(
            max_lambda=30.0,
            r_escape=25.0,
            horizon_eps=0.01,
            rtol=1.0e-10,
            atol=1.0e-12,
            max_step=0.5,
        ),
        r_obs=np.sqrt(500.0),
    )

    assert diagnostics.event == "escape"
    assert diagnostics.h_max_abs < 1.0e-10
    assert np.max(diagnostics.norm_drift_abs) < 1.0e-9
    assert np.max(diagnostics.transverse_max_abs) < 1.0e-9
    assert np.max(diagnostics.wp_relative_drift) < 1.0e-8
