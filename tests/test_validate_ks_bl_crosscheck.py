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

    assert summary["schema"] == "gr-bh-xr.tier2.ks_bl_crosscheck.v2"
    assert summary["event_mismatches"] == 0
    assert summary["both_valid_event_mismatches"] == 0
    assert summary["bl_invalid_ks_valid"] == 0
    assert summary["ks_invalid_bl_valid"] == 0
    assert summary["escape_direction_sample_count"] > 0
    assert summary["escape_direction_max_error_rad"] < 1.0e-6
    assert all("event_comparison" in row for row in summary["samples_detail"])


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

    assert summary["schema"] == "gr-bh-xr.tier2.ks_bl_crosscheck.v2"
    assert summary["event_mismatches"] == 0
    assert summary["both_valid_event_mismatches"] == 0
    assert summary["bl_invalid_ks_valid"] == 0
    assert summary["ks_invalid_bl_valid"] == 0
    assert summary["escape_direction_sample_count"] > 0
    assert summary["escape_direction_max_error_rad"] < 1.0e-6


def test_ks_bl_crosscheck_separates_bl_axis_failure_from_hard_mismatch():
    summary = validate_ks_bl_crosscheck(
        params=MetricParams(M=1.0, a=0.9),
        inclination_deg=60.0,
        alpha_min=-4.0,
        alpha_max=4.0,
        beta=4.0,
        samples=9,
        r_obs=100.0,
        max_lambda=1200.0,
        r_escape=200.0,
        horizon_eps=0.05,
        max_step=1.0,
    )

    assert summary["both_valid_event_mismatches"] == 0
    assert summary["ks_invalid_bl_valid"] == 0
    assert summary["bl_invalid_ks_valid"] >= 1
    assert summary["bl_invalid_ks_valid_max_h"] < 1.0e-7
    assert any(row["event_comparison"] == "bl_invalid_ks_valid" for row in summary["samples_detail"])
