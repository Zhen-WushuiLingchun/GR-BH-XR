import math

import numpy as np
import pytest

from gr_bh_xr.metric import horizon_radius
from gr_bh_xr.observers import (
    RAIN_MIN_SIN_THETA,
    analytic_kerr_frame_dragging_omega,
    analytic_kerr_rain_velocity_ks,
    analytic_zamo_lapse,
    gram_matrix,
    integrate_rain_worldline_ks,
    kerr_rain_tetrad_ks,
    kerr_rain_velocity_ks,
    ks_gram_matrix,
    push_bl_tetrad_to_ks,
    schwarzschild_radial_freefall_initial_state,
    schwarzschild_radial_freefall_initial_tetrad,
    static_observer_tetrad,
    transport_schwarzschild_radial_freefall_tetrad,
    transported_gram_matrices,
    zamo_angular_velocity,
    zamo_lapse,
    zamo_tetrad,
)
from gr_bh_xr.geodesic_ks import ks_state_to_bl_state
from gr_bh_xr.metric import inverse_metric
from gr_bh_xr.metric_ks import (
    bl_to_ks_cartesian,
    ks_inverse_metric,
    ks_metric,
    ks_radius,
    ks_radius_gradient,
)
from gr_bh_xr.types import MetricParams, RayState

MINKOWSKI = np.diag([-1.0, 1.0, 1.0, 1.0])


def _rain_position(params: MetricParams, r: float, theta: float) -> np.ndarray:
    return np.asarray(bl_to_ks_cartesian(r, theta, 0.0, params.a), dtype=np.float64)


def _rain_zone_radii(params: MetricParams) -> dict[str, list[float]]:
    """Radii outside, essentially at, and inside the outer horizon.

    The interior samples stay above the inner horizon: the Cartesian ingoing
    Kerr-Schild chart is regular through `r_+`, which is exactly what makes a
    horizon-crossing observer frame possible, but the mass-inflation region
    below `r_-` is out of scope.
    """

    r_plus = horizon_radius(params)
    r_minus = params.M - math.sqrt(max(params.M**2 - params.a**2, 0.0))
    inside = [r_plus - 1.0e-3, 0.5 * (r_plus + max(r_minus, 0.3))]
    return {
        "outside": [20.0, 6.0, r_plus + 0.1],
        "at": [r_plus + 1.0e-3, r_plus - 1.0e-3],
        "inside": [value for value in inside if value > max(r_minus + 0.05, 0.25)],
    }


def test_zamo_angular_velocity_and_lapse_match_analytic_kerr_formulae():
    params = MetricParams(M=1.0, a=0.9)
    r = 3.2
    theta = math.radians(63.0)

    assert zamo_angular_velocity(params, r, theta) == pytest.approx(
        analytic_kerr_frame_dragging_omega(params, r, theta), rel=2.0e-15
    )
    assert zamo_lapse(params, r, theta) == pytest.approx(
        analytic_zamo_lapse(params, r, theta), rel=2.0e-15
    )


def test_zamo_tetrad_is_orthonormal_outside_horizon():
    params = MetricParams(M=1.0, a=0.9)
    tetrad = zamo_tetrad(params, r=2.1, theta=math.pi / 2.0)
    gram = gram_matrix(params, tetrad)

    np.testing.assert_allclose(gram, np.diag([-1.0, 1.0, 1.0, 1.0]), atol=4.0e-15)


def test_static_observer_fails_inside_ergoregion_but_zamo_remains_defined():
    params = MetricParams(M=1.0, a=0.9)
    r = 1.8
    theta = math.pi / 2.0

    assert horizon_radius(params) < r < 2.0
    with pytest.raises(ValueError, match="ergoregion"):
        static_observer_tetrad(params, r=r, theta=theta)

    tetrad = zamo_tetrad(params, r=r, theta=theta)
    np.testing.assert_allclose(gram_matrix(params, tetrad), np.diag([-1.0, 1.0, 1.0, 1.0]), atol=1.0e-14)


def test_zamo_converges_to_static_observer_in_far_field():
    params = MetricParams(M=1.0, a=0.9)
    r = 1.0e4
    theta = math.radians(71.0)
    zamo = zamo_tetrad(params, r=r, theta=theta)
    static = static_observer_tetrad(params, r=r, theta=theta)

    assert abs(zamo_angular_velocity(params, r, theta)) < 2.0e-12
    np.testing.assert_allclose(zamo.e_time, static.e_time, atol=2.0e-12)
    np.testing.assert_allclose(zamo.e_r, static.e_r, atol=1.0e-15)
    np.testing.assert_allclose(zamo.e_theta, static.e_theta, atol=1.0e-15)
    np.testing.assert_allclose(zamo.e_phi, static.e_phi, atol=2.0e-8)


def test_zamo_horizon_limit_probe():
    params = MetricParams(M=1.0, a=0.9)
    r_plus = horizon_radius(params)
    omega_h = params.a / (2.0 * params.M * r_plus)
    theta = math.pi / 2.0

    eps_values = [1.0e-3, 1.0e-4, 1.0e-5]
    omega_errors = []
    lapse_scaled = []
    for eps in eps_values:
        r = r_plus + eps
        omega_errors.append(abs(zamo_angular_velocity(params, r, theta) / omega_h - 1.0))
        lapse_scaled.append(zamo_lapse(params, r, theta) / math.sqrt(eps))

    assert omega_errors[1] < 0.12 * omega_errors[0]
    assert omega_errors[2] < 0.12 * omega_errors[1]
    assert lapse_scaled[2] == pytest.approx(lapse_scaled[1], rel=5.0e-4)


def test_pushed_zamo_tetrad_is_orthonormal_in_ks_chart():
    params = MetricParams(M=1.0, a=0.9)
    bl_tetrad = zamo_tetrad(params, r=3.2, theta=1.1, phi=0.4)

    ks_tetrad = push_bl_tetrad_to_ks(params, bl_tetrad)
    gram = ks_gram_matrix(params, ks_tetrad)

    assert ks_tetrad.kind == "zamo_pushed_to_ks"
    np.testing.assert_allclose(gram, np.diag([-1.0, 1.0, 1.0, 1.0]), atol=2.0e-10)


def test_schwarzschild_freefall_initial_tetrad_matches_worldline_velocity():
    params = MetricParams(M=1.0, a=0.0)
    r = 12.0
    theta = math.radians(65.0)
    state = schwarzschild_radial_freefall_initial_state(params, r=r, theta=theta)
    tetrad = schwarzschild_radial_freefall_initial_tetrad(params, r=r, theta=theta)

    u_ks = ks_inverse_metric(params, state.x[1:4]) @ state.p

    np.testing.assert_allclose(tetrad.e_time, u_ks, atol=2.0e-12)
    np.testing.assert_allclose(ks_gram_matrix(params, tetrad), np.diag([-1.0, 1.0, 1.0, 1.0]), atol=2.0e-12)


def test_transported_schwarzschild_freefall_tetrad_preserves_gram_and_velocity():
    params = MetricParams(M=1.0, a=0.0)
    path = transport_schwarzschild_radial_freefall_tetrad(
        params,
        r_start=12.0,
        theta=math.radians(72.0),
        r_stop=3.0,
        tau_max=30.0,
        max_step=0.08,
    )

    grams = transported_gram_matrices(params, path)
    target = np.diag([-1.0, 1.0, 1.0, 1.0])
    assert float(np.max(np.abs(grams - target))) < 5.0e-7

    velocity_errors = []
    radial_errors = []
    for state_values, frame in zip(path.states[:: max(1, path.states.shape[0] // 12)], path.frames[:: max(1, path.states.shape[0] // 12)]):
        x = state_values[:4]
        p = state_values[4:8]
        u_ks = ks_inverse_metric(params, x[1:4]) @ p
        velocity_errors.append(float(np.max(np.abs(frame[0] - u_ks))))

        bl_state = ks_state_to_bl_state(params, RayState(x=x, p=p))
        u_bl = inverse_metric(params, float(bl_state.x[1]), float(bl_state.x[2])) @ bl_state.p
        r_bl = float(bl_state.x[1])
        radial_errors.append(abs(float(u_bl[1]) + math.sqrt(2.0 * params.M / r_bl)))

    assert max(velocity_errors) < 5.0e-7
    assert max(radial_errors) < 5.0e-7
    assert ks_radius(params, path.states[-1, 1:4]) == pytest.approx(3.0, abs=2.0e-6)


# --- Kerr-Schild rain (Doran) observer frame -------------------------------


@pytest.mark.parametrize("spin", [0.0, 0.5, 0.9, 0.998])
def test_rain_velocity_satisfies_its_four_defining_constraints(spin):
    """E = 1, L_z = 0, dtheta/dtau = 0, u.u = -1 on both sides of r_+.

    With E = 1 and L = 0 the Carter polar potential reduces to Theta = Q
    identically, independent of theta, so Q = 0 makes theta = const an exact
    solution at every polar angle: the four conditions are consistent, not
    overdetermined.
    """

    params = MetricParams(M=1.0, a=spin)
    checked = 0
    for radii in _rain_zone_radii(params).values():
        for radius in radii:
            for theta in (0.4, 1.0, math.pi / 2.0, 2.3):
                xyz = _rain_position(params, radius, theta)
                g = ks_metric(params, xyz)
                u = kerr_rain_velocity_ks(params, xyz)
                grad_r = ks_radius_gradient(params, xyz)
                r_ks = ks_radius(params, xyz)

                assert abs(float(u @ g @ u) + 1.0) < 1.0e-12
                assert abs(float(g[0] @ u) + 1.0) < 1.0e-13
                lz = -float(xyz[1]) * float(g[1] @ u) + float(xyz[0]) * float(g[2] @ u)
                assert abs(lz) < 1.0e-13
                d_cos_theta = (
                    r_ks * u[3] - float(xyz[2]) * float(grad_r @ u[1:4])
                ) / (r_ks * r_ks)
                assert abs(d_cos_theta) < 1.0e-11
                # Ingoing and future-pointing. g^tt = -(1 + 2H) < 0 everywhere
                # in the ingoing chart, so u^t > 0 is a valid causal test even
                # inside the outer horizon.
                assert float(grad_r @ u[1:4]) < 0.0
                assert u[0] > 0.0
                checked += 1
    assert checked > 0


@pytest.mark.parametrize("spin", [0.0, 0.5, 0.9, 0.998])
def test_rain_velocity_matches_independent_doran_closed_form(spin):
    """Residuals alone cannot pin the branch; compare against the closed form."""

    params = MetricParams(M=1.0, a=spin)
    worst = 0.0
    for radii in _rain_zone_radii(params).values():
        for radius in radii:
            for theta in (0.4, math.pi / 2.0, 2.3):
                xyz = _rain_position(params, radius, theta)
                u = kerr_rain_velocity_ks(params, xyz)
                reference = analytic_kerr_rain_velocity_ks(params, radius, theta)
                worst = max(worst, float(np.max(np.abs(u - reference))))
    assert worst < 1.0e-13


@pytest.mark.parametrize("spin", [0.0, 0.9, 0.998])
def test_rain_velocity_is_stable_exactly_on_the_outer_horizon(spin):
    """Regression: the normalization quadratic degenerates at r = r_+.

    The outgoing rain branch diverges as Delta -> 0 in the ingoing chart, which
    drives the quadratic's leading coefficient to zero exactly on the horizon.
    A naive (-b -/+ sqrt(disc)) / (2a) evaluation then cancels catastrophically
    and either returns an O(1)-wrong velocity or finds no root at all; the
    Vieta-stable form keeps full precision.
    """

    params = MetricParams(M=1.0, a=spin)
    r_plus = horizon_radius(params)
    for theta in (0.4, math.pi / 2.0, 2.3):
        xyz = _rain_position(params, r_plus, theta)
        g = ks_metric(params, xyz)
        u = kerr_rain_velocity_ks(params, xyz)
        assert abs(float(u @ g @ u) + 1.0) < 1.0e-13
        reference = analytic_kerr_rain_velocity_ks(params, r_plus, theta)
        assert float(np.max(np.abs(u - reference))) < 1.0e-13


@pytest.mark.parametrize("spin", [0.0, 0.5, 0.9, 0.998])
def test_rain_tetrad_is_orthonormal_outside_at_and_inside_the_horizon(spin):
    params = MetricParams(M=1.0, a=spin)
    tolerance = {"outside": 1.0e-13, "at": 1.0e-13, "inside": 1.0e-12}
    for zone, radii in _rain_zone_radii(params).items():
        for radius in radii:
            for theta in (0.4, 1.0, math.pi / 2.0, 2.3):
                tetrad = kerr_rain_tetrad_ks(params, _rain_position(params, radius, theta))
                gram = ks_gram_matrix(params, tetrad)
                assert float(np.max(np.abs(gram - MINKOWSKI))) < tolerance[zone]


def test_rain_tetrad_spatial_legs_keep_their_documented_orientation():
    """e_r toward increasing r, e_theta toward increasing polar angle, e_phi prograde."""

    params = MetricParams(M=1.0, a=0.9)
    r_plus = horizon_radius(params)
    for radius in (20.0, 6.0, r_plus + 1.0e-3, r_plus - 1.0e-3):
        for theta in (0.6, math.pi / 2.0, 2.3):
            xyz = _rain_position(params, radius, theta)
            tetrad = kerr_rain_tetrad_ks(params, xyz)
            grad_r = ks_radius_gradient(params, xyz)
            assert float(grad_r @ tetrad.e_r[1:4]) > 0.0
            # d(cos theta) along e_theta must be negative: polar angle grows.
            r_ks = ks_radius(params, xyz)
            d_cos = r_ks * tetrad.e_theta[3] - float(xyz[2]) * float(grad_r @ tetrad.e_theta[1:4])
            assert d_cos < 0.0
            # e_phi is along the axial Killing direction (0, -y, x, 0).
            axial = np.array([0.0, -xyz[1], xyz[0], 0.0])
            assert float(tetrad.e_phi @ ks_metric(params, xyz) @ axial) > 0.0


def test_rain_frame_refuses_the_symmetry_axis_instead_of_degrading_silently():
    """On the axis the constraint system loses rank; cond ~ 6 / theta near it.

    This must raise rather than return a frame: a mis-oriented e_theta still
    orthonormalizes perfectly, so no Gram check could ever detect it.
    """

    params = MetricParams(M=1.0, a=0.9)
    for theta in (0.0, 1.0e-9, math.pi - 1.0e-9):
        with pytest.raises(ValueError, match="symmetry axis"):
            kerr_rain_velocity_ks(params, _rain_position(params, 6.0, theta))
        with pytest.raises(ValueError, match="symmetry axis"):
            kerr_rain_tetrad_ks(params, _rain_position(params, 6.0, theta))

    # Just inside the accepted domain the frame is still accurate.
    theta_edge = 10.0 * RAIN_MIN_SIN_THETA
    tetrad = kerr_rain_tetrad_ks(params, _rain_position(params, 6.0, theta_edge))
    assert float(np.max(np.abs(ks_gram_matrix(params, tetrad) - MINKOWSKI))) < 1.0e-12


def test_rain_recovers_schwarzschild_radial_freefall_limit():
    """a = 0 rain must reproduce dr/dtau = -sqrt(2M/r) exactly."""

    params = MetricParams(M=1.0, a=0.0)
    worst = 0.0
    for radius in (20.0, 8.0, 4.1, 3.0, 1.5):
        for theta in (0.6, math.pi / 2.0, 2.3):
            xyz = _rain_position(params, radius, theta)
            u = kerr_rain_velocity_ks(params, xyz)
            dr_dtau = float(ks_radius_gradient(params, xyz) @ u[1:4])
            worst = max(worst, abs(dr_dtau + math.sqrt(2.0 * params.M / radius)))
    # The algebraic solve is machine-exact here: any 1e-10-class floor comes
    # from a worldline sampler recording off-target radii, not from physics.
    assert worst < 1.0e-13


def test_rain_worldline_sampler_lands_on_the_requested_radii():
    params = MetricParams(M=1.0, a=0.0)
    targets = np.array([20.0, 8.0, 4.1, 3.0, 1.5])

    positions = integrate_rain_worldline_ks(
        params, r_start=25.0, theta=math.pi / 2.0, r_samples=targets
    )

    assert len(positions) == targets.size
    for target, position in zip(targets, positions):
        assert ks_radius(params, position) == pytest.approx(float(target), abs=1.0e-9)
        u = kerr_rain_velocity_ks(params, position)
        dr_dtau = float(ks_radius_gradient(params, position) @ u[1:4])
        assert dr_dtau == pytest.approx(
            -math.sqrt(2.0 * params.M / float(target)), abs=1.0e-9
        )


def test_rain_worldline_sampler_rejects_bad_sample_lists():
    params = MetricParams(M=1.0, a=0.9)

    with pytest.raises(ValueError, match="strictly decreasing"):
        integrate_rain_worldline_ks(
            params, r_start=10.0, theta=1.0, r_samples=np.array([8.0, 8.0, 6.0])
        )
    # Targets marginally above r_start must be refused outright: silently
    # clamping them would merge distinct targets into duplicates and break the
    # strict ordering that was just validated.
    with pytest.raises(ValueError, match="must not exceed r_start"):
        integrate_rain_worldline_ks(
            params, r_start=10.0, theta=1.0, r_samples=np.array([10.0 + 5.0e-12, 9.0])
        )
    with pytest.raises(ValueError, match="non-empty"):
        integrate_rain_worldline_ks(
            params, r_start=10.0, theta=1.0, r_samples=np.array([])
        )


def test_rain_worldline_accumulates_frame_dragging_through_the_horizon():
    """Kerr rain must pick up azimuth; Schwarzschild rain must not."""

    kerr = MetricParams(M=1.0, a=0.9)
    r_plus = horizon_radius(kerr)
    targets = np.array([6.0, 3.0, r_plus + 0.05, r_plus - 0.05])

    positions = integrate_rain_worldline_ks(
        kerr, r_start=9.0, theta=math.pi / 2.0, r_samples=targets
    )
    assert len(positions) == targets.size
    assert ks_radius(kerr, positions[-1]) < r_plus
    azimuths = [math.atan2(float(p[1]), float(p[0])) for p in positions]
    assert abs(azimuths[-1] - azimuths[0]) > 1.0e-3

    schwarzschild = MetricParams(M=1.0, a=0.0)
    flat = integrate_rain_worldline_ks(
        schwarzschild, r_start=9.0, theta=math.pi / 2.0, r_samples=np.array([6.0, 3.0, 2.5])
    )
    for position in flat:
        assert math.atan2(float(position[1]), float(position[0])) == pytest.approx(
            0.0, abs=1.0e-12
        )


def test_rain_observer_stage_b_gate_passes_with_recorded_thresholds():
    from gr_bh_xr.validate_rain_observer import THRESHOLDS, run_gate

    report = run_gate()

    assert report["passed"], report["failures"]
    # Fail closed: every zone must actually have been sampled, otherwise a
    # max() over an empty set would report a vacuous pass.
    for zone, count in report["sampleCounts"].items():
        assert count > 0, zone
    assert report["horizonExactSamples"] > 0
    assert len(report["schwarzschildLimit"]) == 5
    for name, threshold in THRESHOLDS.items():
        assert report["checks"][name] <= threshold, (name, report["checks"][name])
