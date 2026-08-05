import math

import pytest

from gr_bh_xr.gpu.generate_roam_keyframes import (
    DEFAULT_R_ESCAPE_MIN,
    ROAM_KEYFRAMES_SCHEMA,
    ROAM_THETA_MAX_DEG,
    ROAM_THETA_MIN_DEG,
    capture_monotonicity_tolerance,
    ergosphere_radius,
    roam_radius_schedule,
    validate_static_observer_radii,
    validate_theta_rows,
)
from gr_bh_xr.gpu.generate_transfer_cubemap import static_observer_sky_blueshift
from gr_bh_xr.gpu.trace import GpuTraceConfig
from gr_bh_xr.types import MetricParams


def test_roam_radius_schedule_is_log_spaced_and_hits_endpoints():
    radii = roam_radius_schedule(100.0, 2.5, 16)

    assert len(radii) == 16
    assert radii[0] == pytest.approx(100.0, rel=1.0e-12)
    assert radii[-1] == pytest.approx(2.5, rel=1.0e-12)
    ratios = [radii[i + 1] / radii[i] for i in range(len(radii) - 1)]
    for ratio in ratios:
        assert ratio == pytest.approx(ratios[0], rel=1.0e-12)
        assert ratio < 1.0


def test_roam_radius_schedule_rejects_bad_input():
    with pytest.raises(ValueError):
        roam_radius_schedule(100.0, 2.5, 1)
    with pytest.raises(ValueError):
        roam_radius_schedule(2.5, 100.0, 8)
    with pytest.raises(ValueError):
        roam_radius_schedule(100.0, -1.0, 8)


def test_ergosphere_radius_limits():
    params = MetricParams(M=1.0, a=0.9)

    # Equator: r_E = 2M for any spin; pole: r_E = r_+.
    assert ergosphere_radius(params, math.pi / 2.0) == pytest.approx(2.0, abs=1.0e-14)
    r_plus = 1.0 + math.sqrt(1.0 - 0.81)
    assert ergosphere_radius(params, 0.0) == pytest.approx(r_plus, abs=1.0e-14)


def test_static_observer_validation_rejects_ergosphere_entry():
    params = MetricParams(M=1.0, a=0.9)

    # At inclination 60 deg the ergosphere sits at 1 + sqrt(1 - a^2/4).
    r_ergo = 1.0 + math.sqrt(1.0 - 0.81 * 0.25)
    returned = validate_static_observer_radii(params, 60.0, [100.0, 2.5])
    assert returned == pytest.approx(r_ergo, abs=1.0e-14)

    with pytest.raises(ValueError, match="ergosphere"):
        validate_static_observer_radii(params, 60.0, [100.0, r_ergo + 0.05])


def test_static_observer_margin_scales_with_mass():
    """The admitted worst-case tetrad boost must not depend on the mass unit.

    With an absolute 0.1 margin the boost 1/sqrt(-g_tt) at the gate boundary is
    4.58 at M = 1 but 14.2 at M = 10, i.e. the safety buffer silently tightens
    as M grows. Scaling the margin by M keeps it fixed.
    """

    def boost_at_gate(mass: float) -> float:
        params = MetricParams(M=mass, a=0.9 * mass)
        r_ergo = ergosphere_radius(params, math.pi / 2.0)
        r_gate = r_ergo + 0.1 * params.M
        sigma = r_gate * r_gate
        return 1.0 / math.sqrt(1.0 - 2.0 * params.M * r_gate / sigma)

    assert boost_at_gate(2.0) == pytest.approx(boost_at_gate(1.0), rel=1.0e-12)
    assert boost_at_gate(10.0) == pytest.approx(boost_at_gate(1.0), rel=1.0e-12)

    # And the gate itself still fires in scaled units.
    scaled = MetricParams(M=2.0, a=1.8)
    with pytest.raises(ValueError, match="ergosphere"):
        validate_static_observer_radii(scaled, 90.0, [200.0, 4.05])
    assert validate_static_observer_radii(scaled, 90.0, [200.0, 5.0]) == pytest.approx(4.0)


def test_gpu_trace_config_escape_radius_floor():
    params = MetricParams(M=1.0, a=0.9)
    base = dict(params=params, inclination_deg=60.0, grid=2, alpha_max=1.0, beta_max=1.0)

    # Far observer keeps the legacy 2 * r_obs rule.
    far = GpuTraceConfig(r_obs=100.0, r_escape_min=DEFAULT_R_ESCAPE_MIN, **base)
    assert far.r_escape == pytest.approx(200.0)

    # Near-horizon observer must not treat r = 2 * r_obs as asymptotic: the
    # measured extraction error there is 6.7 deg mean / 22.8 deg max.
    near = GpuTraceConfig(r_obs=2.5, r_escape_min=DEFAULT_R_ESCAPE_MIN, **base)
    assert near.r_escape == pytest.approx(DEFAULT_R_ESCAPE_MIN)

    legacy = GpuTraceConfig(r_obs=2.5, **base)
    assert legacy.r_escape == pytest.approx(5.0)

    with pytest.raises(ValueError, match="r_escape_min"):
        GpuTraceConfig(r_obs=10.0, r_escape_min=-1.0, **base)


def test_theta_rows_validated_against_documented_envelope():
    assert validate_theta_rows([30.0, 60.0, 90.0, 120.0, 150.0]) == [30.0, 60.0, 90.0, 120.0, 150.0]

    # The envelope is exactly what the committed grid exercises.
    assert (ROAM_THETA_MIN_DEG, ROAM_THETA_MAX_DEG) == (30.0, 150.0)
    for bad in ([10.0, 60.0], [29.9, 60.0], [60.0, 150.1]):
        with pytest.raises(ValueError, match="validated roam envelope"):
            validate_theta_rows(bad)
    with pytest.raises(ValueError, match="sorted"):
        validate_theta_rows([90.0, 60.0])
    with pytest.raises(ValueError, match="unique"):
        validate_theta_rows([60.0, 60.0])


def test_theta_envelope_does_not_claim_the_bardeen_screen_rationale():
    """The roam path never evaluates the alpha/beta screen map.

    The [20, 160] preview envelope exists because the Bardeen screen map
    carries a 1/sin(theta_obs) factor. This generator reaches the tracer through
    `initial_state_direction`, which builds the tetrad from a Unity unit vector
    and contains no such factor, so that rationale must not be repeated here.
    """

    import inspect

    from gr_bh_xr.gpu import generate_roam_keyframes as module

    source = inspect.getsource(module)
    with pytest.raises(ValueError) as excinfo:
        validate_theta_rows([10.0])
    assert "Bardeen" not in str(excinfo.value)
    assert "not a known failure boundary" in str(excinfo.value)
    # The module may explain why the preview envelope does NOT apply, but must
    # not assert the degeneracy as this path's own justification.
    assert "does not apply here" in source


def test_capture_monotonicity_tolerance_shrinks_with_resolution():
    coarse = capture_monotonicity_tolerance(6 * 64 * 64)
    fine = capture_monotonicity_tolerance(6 * 512 * 512)

    assert coarse > fine > 0.0
    # Far below the physical near-horizon growth the gate must still catch.
    assert fine < 1.0e-2
    with pytest.raises(ValueError):
        capture_monotonicity_tolerance(0)


def test_static_observer_sky_blueshift_anchors():
    params = MetricParams(M=1.0, a=0.9)

    # Analytic 1/sqrt(1 - 2 M r / Sigma) at theta = 60 deg, r = 2.5M.
    sigma = 2.5**2 + 0.81 * 0.25
    expected = 1.0 / math.sqrt(1.0 - 5.0 / sigma)
    assert static_observer_sky_blueshift(params, 2.5, math.radians(60.0)) == pytest.approx(
        expected, rel=1.0e-14
    )
    # Far field limit: 1 + M/r + O((M/r)^2).
    far = static_observer_sky_blueshift(params, 1.0e4, math.radians(60.0))
    assert far == pytest.approx(1.0 + 1.0e-4, abs=2.0e-8)
    # Schwarzschild anchor: 1/sqrt(1 - 2M/r) at r = 4M is sqrt(2).
    schw = MetricParams(M=1.0, a=0.0)
    assert static_observer_sky_blueshift(schw, 4.0, math.pi / 2.0) == pytest.approx(
        math.sqrt(2.0), rel=1.0e-14
    )
    with pytest.raises(ValueError, match="ergosphere"):
        static_observer_sky_blueshift(params, 1.8, math.pi / 2.0)


def test_sky_blueshift_is_mirror_symmetric_about_the_equator():
    """theta -> pi - theta is an isometry of Kerr, so the blueshift must match."""

    params = MetricParams(M=1.0, a=0.9)
    for theta_deg in (30.0, 45.0, 60.0, 80.0):
        north = static_observer_sky_blueshift(params, 4.0, math.radians(theta_deg))
        south = static_observer_sky_blueshift(params, 4.0, math.radians(180.0 - theta_deg))
        assert north == pytest.approx(south, rel=1.0e-15)
        ergo_north = ergosphere_radius(params, math.radians(theta_deg))
        ergo_south = ergosphere_radius(params, math.radians(180.0 - theta_deg))
        assert ergo_north == pytest.approx(ergo_south, rel=1.0e-15)


def test_roam_schema_constant_is_versioned():
    assert ROAM_KEYFRAMES_SCHEMA == "gr-bh-xr.task7.roam_keyframes.v2"
