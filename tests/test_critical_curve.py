import math

from gr_bh_xr.critical_curve import (
    critical_curve_polygon,
    photon_shell_bounds,
    screen_beta_squared,
    spherical_photon_constants,
    visible_critical_points,
)
from gr_bh_xr.metric import horizon_radius
from gr_bh_xr.types import MetricParams
from gr_bh_xr.validate_kerr_critical_curve import validate_kerr_critical_curve


def test_photon_shell_bounds_are_ordered_and_outside_horizon():
    params = MetricParams(M=1.0, a=0.5)

    r_minus, r_plus = photon_shell_bounds(params)

    assert horizon_radius(params) < r_minus < r_plus


def test_edge_on_beta_squared_matches_eta_and_endpoints_are_equatorial():
    params = MetricParams(M=1.0, a=0.5)
    r_minus, r_plus = photon_shell_bounds(params)

    for r_photon in (r_minus, r_plus):
        lam, eta = spherical_photon_constants(params, r_photon)
        beta2 = screen_beta_squared(params, math.pi / 2.0, lam, eta)

        assert abs(beta2 - eta) < 1.0e-9
        assert abs(eta) < 1.0e-8


def test_visible_curve_is_finite_for_inclined_kerr():
    params = MetricParams(M=1.0, a=0.5)

    upper, lower = visible_critical_points(params, math.radians(60.0), samples=256)
    polygon = critical_curve_polygon(params, math.radians(60.0), samples=256)

    assert len(upper) == len(lower)
    assert polygon.shape[1] == 2
    assert polygon.shape[0] >= 2 * len(upper)
    assert all(math.isfinite(point.alpha) and math.isfinite(point.beta) for point in upper + lower)


def test_kerr_critical_curve_validation_smoke():
    result = validate_kerr_critical_curve(
        params=MetricParams(M=1.0, a=0.5),
        theta_obs=math.radians(60.0),
        angles=12,
        r_obs=80.0,
        max_lambda=900.0,
        horizon_eps=0.02,
        curve_samples=512,
        refine_steps=8,
    )

    assert result["max_abs_error"] < 0.15
    assert result["event_counts"]["invalid"] == 0
    for key in (
        "max_abs_error",
        "rms_error",
        "median_abs_error",
        "event_counts",
        "worst_diagnostics",
        "diagnostic_groups",
    ):
        assert key in result
    assert "outer" in result["diagnostic_groups"]
    assert "near_capture" in result["diagnostic_groups"]
    assert result["diagnostic_groups"]["outer"]["count"] > 0
    assert result["diagnostic_groups"]["near_capture"]["count"] > 0
