from gr_bh_xr.types import MetricParams
from gr_bh_xr.validate_ks_bl_crosscheck import validate_ks_bl_crosscheck


def test_ks_bl_crosscheck_smoke_has_no_event_mismatches():
    summary = validate_ks_bl_crosscheck(
        params=MetricParams(M=1.0, a=0.9),
        inclination_deg=60.0,
        alpha_min=-8.0,
        alpha_max=8.0,
        beta=0.0,
        samples=9,
        r_obs=100.0,
        max_lambda=1200.0,
        r_escape=200.0,
        horizon_eps=0.05,
        max_step=1.0,
    )

    assert summary["event_mismatches"] == 0
    assert summary["escape_direction_sample_count"] > 0
    assert summary["escape_direction_max_error_rad"] < 1.0e-6


def test_ks_bl_crosscheck_edge_on_smoke_has_no_event_mismatches():
    summary = validate_ks_bl_crosscheck(
        params=MetricParams(M=1.0, a=0.9),
        inclination_deg=90.0,
        alpha_min=-8.0,
        alpha_max=8.0,
        beta=0.0,
        samples=9,
        r_obs=100.0,
        max_lambda=1200.0,
        r_escape=200.0,
        horizon_eps=0.05,
        max_step=1.0,
    )

    assert summary["event_mismatches"] == 0
    assert summary["escape_direction_sample_count"] > 0
    assert summary["escape_direction_max_error_rad"] < 1.0e-6
