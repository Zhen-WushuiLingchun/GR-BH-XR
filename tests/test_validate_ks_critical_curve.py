import math

from gr_bh_xr.types import MetricParams
from gr_bh_xr.validate_ks_critical_curve import SCHEMA, validate_ks_critical_curve


def test_ks_critical_curve_validation_smoke():
    result = validate_ks_critical_curve(
        params=MetricParams(M=1.0, a=0.9),
        theta_obs=math.radians(60.0),
        angles=8,
        r_obs=80.0,
        max_lambda=900.0,
        horizon_eps=0.02,
        curve_samples=512,
        refine_steps=7,
    )

    assert result["schema"] == SCHEMA
    assert abs(result["center"]["alpha"] - 0.94) < 0.1
    assert result["max_abs_error"] < 0.2
    assert result["event_counts"]["invalid"] == 0
    assert result["worst_diagnostics"]["h_max_abs"] < 1.0e-7
