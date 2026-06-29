import math

from gr_bh_xr.types import MetricParams
from gr_bh_xr.validate_shadow import estimate_schwarzschild_bc


def test_validate_shadow_estimates_schwarzschild_critical_b():
    result = estimate_schwarzschild_bc(
        params=MetricParams(M=1.0, a=0.0),
        r_obs=70.0,
        theta_obs=math.pi / 2.0,
        grid=21,
        max_lambda=900.0,
        refine_steps=8,
    )

    assert result["abs_error"] < 0.03
    assert result["sample_counts"]["capture"] > 0
    assert result["sample_counts"]["escape"] > 0
