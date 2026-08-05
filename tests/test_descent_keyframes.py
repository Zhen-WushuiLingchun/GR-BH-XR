import math

import numpy as np
import pytest

from gr_bh_xr.gpu.generate_descent_keyframes import (
    DEFAULT_HAMILTONIAN_MAX,
    DESCENT_SCHEMA,
    _unwrap_azimuth,
    batch_escape_directions,
    descent_radius_schedule,
)
from gr_bh_xr.gpu.trace_ks import (
    KS_DISK_MAX_ORDER,
    KS_F32_OUTPUTS_PER_RAY,
    KS_WGSL_SHADER,
    KsGpuTraceConfig,
)
from gr_bh_xr.metric import horizon_radius
from gr_bh_xr.types import MetricParams


def test_descent_radius_schedule_brackets_the_horizon_and_avoids_it():
    params = MetricParams(M=1.0, a=0.9)
    r_plus = horizon_radius(params)

    radii = descent_radius_schedule(params, 9.0, 0.75, 20)

    assert len(radii) == 20
    assert all(later < earlier for earlier, later in zip(radii, radii[1:]))
    assert radii[0] == pytest.approx(9.0, rel=1.0e-12)
    # The grid must actually cross the horizon; that is the point of the path.
    assert any(value > r_plus for value in radii)
    assert any(value < r_plus for value in radii)
    # And no sample may sit on it.
    assert all(abs(value - r_plus) >= 5.0e-3 - 1.0e-12 for value in radii)


def test_descent_radius_schedule_guards_scale_with_mass():
    """Absolute margins would be a ~10x weaker buffer in geometric units at M = 10."""

    for mass in (1.0, 2.0, 10.0):
        params = MetricParams(M=mass, a=0.9 * mass)
        r_minus = mass - math.sqrt(max(mass**2 - (0.9 * mass) ** 2, 0.0))
        # Just inside the guard must fail, just outside must pass, at every M.
        with pytest.raises(ValueError, match="inner horizon"):
            descent_radius_schedule(params, 9.0 * mass, r_minus + 0.05 * mass, 10)
        radii = descent_radius_schedule(params, 9.0 * mass, r_minus + 0.2 * mass, 10)
        assert len(radii) == 10


def test_descent_radius_schedule_rejects_bad_input():
    params = MetricParams(M=1.0, a=0.9)

    with pytest.raises(ValueError):
        descent_radius_schedule(params, 9.0, 0.75, 1)
    with pytest.raises(ValueError):
        descent_radius_schedule(params, 0.75, 9.0, 8)
    # Two adjacent radii falling inside the nudge band on the SAME side both
    # snap to the same value. That must fail loudly rather than silently
    # requesting duplicate worldline targets.
    r_plus = horizon_radius(params)
    with pytest.raises(ValueError, match="collapsed"):
        descent_radius_schedule(params, r_plus + 4.0e-3, r_plus + 1.0e-3, 2)
    # Straddling the horizon is fine: the two nudges push to opposite sides.
    straddle = descent_radius_schedule(params, r_plus + 1.0e-3, r_plus - 1.0e-3, 2)
    assert straddle[0] > r_plus > straddle[1]


def test_azimuth_unwrap_handles_negative_drift():
    """Ingoing-KS chart azimuth of a prograde rain worldline drifts negative.

    dphi_ks/dtau = (a/Delta)(2M/r + dr/dtau) with |dr/dtau| > 2M/r, so the
    chart twist beats the Boyer-Lindquist frame dragging. A one-sided unwrap
    built for increasing azimuth silently fails on this sequence.
    """

    # A wrap of a decreasing sequence appears as a +358 jump.
    assert _unwrap_azimuth(179.0, -179.0) == pytest.approx(-181.0)
    # And the increasing direction still works.
    assert _unwrap_azimuth(-179.0, 179.0) == pytest.approx(181.0)
    # No wrap, no change.
    assert _unwrap_azimuth(-23.0, -20.0) == pytest.approx(-23.0)


def test_ks_shader_stride_constants_match_python():
    """The buffer is sized in Python and written at the WGSL stride.

    A desync silently offsets every readback field rather than failing, so the
    shader constants are substituted from the Python values and pinned here.
    """

    assert "__KS_" not in KS_WGSL_SHADER
    assert f"const KS_F32_OUTPUTS_PER_RAY: u32 = {KS_F32_OUTPUTS_PER_RAY}u;" in KS_WGSL_SHADER
    assert f"const KS_DISK_MAX_ORDER: u32 = {KS_DISK_MAX_ORDER}u;" in KS_WGSL_SHADER
    assert KS_F32_OUTPUTS_PER_RAY == 12 + 4 * KS_DISK_MAX_ORDER
    # The highest indexed write must fit inside the declared stride.
    highest = max(
        int(line.split("fbase + ")[1].split("u]")[0])
        for line in KS_WGSL_SHADER.splitlines()
        if "out_f32[fbase + " in line
    )
    assert highest == KS_F32_OUTPUTS_PER_RAY - 1


def test_ks_disk_recording_requires_clearance_from_the_horizon():
    """ks_phi_shift / ks_time_shift diverge logarithmically at r_+.

    Recording a crossing there would emit a large finite garbage value rather
    than fail, so the config refuses instead of trusting every caller to pass
    an ISCO-like inner edge.
    """

    params = MetricParams(M=1.0, a=0.9)
    r_plus = horizon_radius(params)

    with pytest.raises(ValueError, match="clear the outer horizon"):
        KsGpuTraceConfig(params=params, disk_r_in=r_plus + 0.01, disk_r_out=30.0)
    with pytest.raises(ValueError, match="disk_r_out must exceed"):
        KsGpuTraceConfig(params=params, disk_r_in=10.0, disk_r_out=5.0)
    # Disabled recording keeps the legacy configuration untouched.
    KsGpuTraceConfig(params=params, disk_r_in=0.0, disk_r_out=0.0)
    KsGpuTraceConfig(params=params, disk_r_in=2.32, disk_r_out=30.0)


def test_batch_escape_directions_is_empty_safe_and_finite_masked():
    params = MetricParams(M=1.0, a=0.9)
    final_x = np.zeros((3, 4), dtype=np.float32)
    final_p = np.zeros((3, 4), dtype=np.float32)
    escaped = np.zeros(3, dtype=bool)

    dirs = batch_escape_directions(params, final_x, final_p, escaped)
    assert dirs.shape == (3, 3)
    assert np.all(np.isnan(dirs))


def test_descent_schema_and_validity_defaults_are_versioned():
    assert DESCENT_SCHEMA == "gr-bh-xr.task8.descent_keyframes.v1"
    # H is identically zero for a null geodesic; this is a first-principles
    # validity criterion, not a tuned heuristic.
    assert DEFAULT_HAMILTONIAN_MAX == 1.0e-2


def test_descent_frame_validation_gate_passes_with_recorded_thresholds():
    from gr_bh_xr.gpu.validate_descent_frames import (
        MIN_COMPARED,
        THRESHOLDS,
        validate_descent_frames,
    )

    report = validate_descent_frames(
        params=MetricParams(M=1.0, a=0.9),
        theta_deg=60.0,
        r_obs=2.35,
        direction_count=1024,
        r_escape_far=200.0,
        r_escape_near=20.0,
        step_size=0.01,
        steps=60000,
        max_lambda=1500.0,
    )

    assert report["passed"], report["failures"]
    for name, threshold in THRESHOLDS.items():
        if name in report["checks"]:
            assert report["checks"][name] <= threshold, (name, report["checks"][name])

    # Fail closed: statistics must rest on a real sample.
    assert report["chartDirectionFar"]["comparedCount"] >= MIN_COMPARED
    assert report["chartDirectionNear"]["comparedCount"] >= MIN_COMPARED
    assert report["chartDirectionFar"]["nonFiniteCount"] == 0

    # The chart rotation must be an improvement over applying none. This is the
    # only formulation that discriminates its sign: at r_escape = 200 the
    # correction is smaller than the measured agreement, so a plain threshold
    # there passes whether the rotation is right, absent, or sign-flipped.
    assert report["chartDirectionNear"]["rotationIsImprovement"]
    assert report["chartDirectionFar"]["rotationIsImprovement"]

    # The observer-factor check is an algebraic identity, so its power comes
    # from the negative controls failing loudly.
    energy = report["energyPacking"]
    assert energy["negativeControlPermutedLegOrder"] > 1.0
    assert energy["negativeControlProseSignForm"] > 1.0
    assert energy["nullResidualMax"] < 1.0e-12
    # The float32 agreement sits at one ULP, which is the floor: any threshold
    # below 2^-23 is unachievable in principle at E ~ 1.
    assert energy["f32MaxAbs"] < 4.0 * energy["f32UlpAtUnity"]
    assert energy["f64MaxAbs"] < 1.0e-14
