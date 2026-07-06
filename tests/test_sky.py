import numpy as np

from gr_bh_xr.sky import escape_direction_arrays, momentum_direction_from_state
from gr_bh_xr.types import MetricParams


def test_vectorized_escape_direction_matches_scalar_metric_path():
    params = MetricParams(M=1.0, a=0.73)
    r = np.asarray([12.0, 40.0, 160.0], dtype=np.float64)
    theta = np.asarray([0.7, 1.3, 2.2], dtype=np.float64)
    phi = np.asarray([0.2, 2.0, 5.1], dtype=np.float64)
    p_t = np.asarray([-1.0, -1.0, -1.0], dtype=np.float64)
    p_r = np.asarray([0.9, 1.1, 0.7], dtype=np.float64)
    p_theta = np.asarray([0.3, -0.2, 0.15], dtype=np.float64)
    p_phi = np.asarray([-2.0, 4.0, 1.5], dtype=np.float64)

    result = escape_direction_arrays(
        params=params,
        event_code=np.ones(3, dtype=np.int16),
        r=r,
        theta=theta,
        phi=phi,
        p_t=p_t,
        p_r=p_r,
        p_theta=p_theta,
        p_phi=p_phi,
        escape_code=1,
    )

    for idx in range(3):
        expected = momentum_direction_from_state(
            params,
            r=float(r[idx]),
            theta=float(theta[idx]),
            phi=float(phi[idx]),
            p_t=float(p_t[idx]),
            p_r=float(p_r[idx]),
            p_theta=float(p_theta[idx]),
            p_phi=float(p_phi[idx]),
        )
        actual = tuple(component[idx] for component in result)
        np.testing.assert_allclose(actual, expected, rtol=0.0, atol=1.0e-12)
