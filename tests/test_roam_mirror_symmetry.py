"""Equatorial mirror-symmetry invariant for the Task 7 roam keyframe stack.

Kerr is invariant under the isometry `theta -> pi - theta`: the Boyer-Lindquist
metric depends on theta only through `cos^2 theta` and `sin^2 theta`, and the
reflection commutes with both Killing vectors, so `E` and `L_z` are preserved
and `r_m`, `g_m` are reflection scalars.

With `unity_basis_from_inclination` the reflected basis satisfies

    right' = R right,   up' = -R up,   forward' = R forward,   R = diag(1, 1, -1)

so a Unity local ray `(rx, ry, rz)` at inclination `theta` is the exact mirror
of `(rx, -ry, rz)` at `180 - theta`, and escape directions must map as
`(dx, dy, dz) -> (dx, -dy, dz)` in Unity components.

This is an *unforced* invariant: nothing in the tracer imposes it, so a
regression in the tetrad construction, the Unity basis, the polar substepping
or the disk-crossing recorder breaks it. It is the real mirror check; asserting
that two capture-fraction table rows agree is much weaker, because the cubemap
texel set is itself invariant under the Unity y-flip and aggregate counts are
therefore forced to agree except where an invalid texel appears.
"""

import math

import numpy as np
import pytest

from gr_bh_xr.gpu.backend import select_vulkan_adapter
from gr_bh_xr.gpu.codes import SCHEMA_EVENT_CODES
from gr_bh_xr.gpu.generate_transfer_cubemap import _bh_to_unity
from gr_bh_xr.gpu.trace import GpuTraceConfig, trace_unity_direction_points
from gr_bh_xr.sky import escape_direction_arrays
from gr_bh_xr.types import MetricParams
from gr_bh_xr.xr.export_unity_textures import unity_basis_from_inclination


def _require_vulkan_adapter():
    pytest.importorskip("wgpu")
    try:
        return select_vulkan_adapter()
    except RuntimeError as exc:  # pragma: no cover - hardware dependent
        pytest.skip(str(exc))


ESCAPE = SCHEMA_EVENT_CODES["escape"]
UNITY_Y_FLIP = np.array([1.0, -1.0, 1.0])

# Thresholds measured on wgpu/Vulkan f32 at a/M = 0.9, 600 directions per cell,
# theta in {20, 30, 60, 90} deg x r_obs in {2.5, 6, 30}M, n = 5375 escaping
# mirror pairs:
#     direction angle  p50 0.00078  p90 0.0142  p99 0.0183  p99.9 0.0218 deg
#     |dr_m|           p99 1.54e-4  p99.9 6.17e-4  max 6.31e-3 M
#     |dg_m|           p99 1.19e-5  p99.9 3.27e-5  max 5.01e-4
# The p99 direction figure is the f32 *representation* floor of the
# arccos(dot) metric itself: a unit f32 vector dotted with itself already
# yields up to 0.043 deg of apparent angle. So the invariant holds as tightly
# as f32 can express it. The tail (max 1.68 deg, 2 of 5375 pairs) is chaotic
# near-critical rays whose min_r sat on the photon ring, where exponential
# sensitivity to f32 rounding is physical rather than a defect. A max-based
# gate would therefore be flaky; use a percentile plus a bounded-outlier gate.
DIRECTION_P99_DEG = 0.05
DIRECTION_OUTLIER_DEG = 0.5
DIRECTION_OUTLIER_FRACTION = 0.005
DISK_R_P99 = 1.0e-3
DISK_R_MAX = 5.0e-2
DISK_G_P99 = 1.0e-4
DISK_G_MAX = 5.0e-3


def _sky_directions(count: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    directions = rng.normal(size=(count, 3))
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    return np.ascontiguousarray(directions, dtype=np.float32)


def _trace(params, inclination_deg, directions, r_obs):
    config = GpuTraceConfig(
        params=params,
        inclination_deg=inclination_deg,
        grid=2,
        alpha_max=1.0,
        beta_max=1.0,
        r_obs=r_obs,
        step_size=0.05,
        steps=24000,
    )
    result = trace_unity_direction_points(config, directions)
    event_code = result["event_code"].astype(np.int16)
    escape = escape_direction_arrays(
        params=params,
        event_code=event_code,
        r=result["final_r"],
        theta=result["final_theta"],
        phi=result["final_phi"],
        p_t=result["final_p_t"],
        p_r=result["final_p_r"],
        p_theta=result["final_p_theta"],
        p_phi=result["final_p_phi"],
        escape_code=ESCAPE,
    )
    dir_bh = np.stack(escape[2:], axis=-1)
    escaped = (event_code == ESCAPE) & np.all(np.isfinite(dir_bh), axis=-1)
    dir_unity = _bh_to_unity(
        np.where(np.isfinite(dir_bh), dir_bh, 0.0),
        escaped,
        unity_basis_from_inclination(inclination_deg),
    )
    return {
        "event": event_code,
        "escaped": escaped,
        "dir_unity": dir_unity.astype(np.float64),
        "disk_r": result["disk_r_m"].astype(np.float64),
        "disk_g": result["disk_g_m"].astype(np.float64),
    }


def test_unity_basis_reflects_under_equatorial_mirror():
    """Closed-form check of the basis identity the GPU test relies on."""

    reflect = np.diag([1.0, 1.0, -1.0])
    for inclination_deg in (5.0, 20.0, 30.0, 60.0, 90.0, 120.0, 160.0, 175.0):
        basis = unity_basis_from_inclination(inclination_deg)
        mirror = unity_basis_from_inclination(180.0 - inclination_deg)
        assert np.allclose(mirror.right_bh, reflect @ basis.right_bh, atol=1.0e-14)
        assert np.allclose(mirror.up_bh, -(reflect @ basis.up_bh), atol=1.0e-14)
        assert np.allclose(mirror.forward_bh, reflect @ basis.forward_bh, atol=1.0e-14)

    # Closed forms: right = -e_y, up = (-cos t, 0, sin t), forward = -observer.
    theta = math.radians(37.0)
    basis = unity_basis_from_inclination(37.0)
    assert np.allclose(basis.right_bh, [0.0, -1.0, 0.0], atol=1.0e-14)
    assert np.allclose(basis.up_bh, [-math.cos(theta), 0.0, math.sin(theta)], atol=1.0e-14)
    assert np.allclose(
        basis.forward_bh, [-math.sin(theta), 0.0, -math.cos(theta)], atol=1.0e-14
    )


@pytest.mark.parametrize("inclination_deg", [30.0, 60.0])
@pytest.mark.parametrize("r_obs", [2.5, 30.0])
def test_roam_keyframes_obey_equatorial_mirror_symmetry(inclination_deg, r_obs):
    _require_vulkan_adapter()
    params = MetricParams(M=1.0, a=0.9)
    directions = _sky_directions(600, seed=3)
    mirrored = np.ascontiguousarray(directions * UNITY_Y_FLIP.astype(np.float32))

    north = _trace(params, inclination_deg, directions, r_obs)
    south = _trace(params, 180.0 - inclination_deg, mirrored, r_obs)

    # 1. Event classification is a reflection scalar: exact agreement.
    assert np.array_equal(north["event"], south["event"])

    # 2. The disk-crossing recorder must fire on the same rays and the same
    #    image orders on both sides (no one-sided records).
    assert np.array_equal(north["disk_r"] > 0.0, south["disk_r"] > 0.0)

    # 3. Escape directions map as (dx, dy, dz) -> (dx, -dy, dz).
    both = north["escaped"] & south["escaped"]
    assert np.count_nonzero(both) > 100
    cos_angle = np.clip(
        np.sum(north["dir_unity"][both] * south["dir_unity"][both] * UNITY_Y_FLIP, axis=1),
        -1.0,
        1.0,
    )
    angle_deg = np.degrees(np.arccos(cos_angle))
    assert np.percentile(angle_deg, 99) <= DIRECTION_P99_DEG
    outliers = np.count_nonzero(angle_deg > DIRECTION_OUTLIER_DEG) / angle_deg.size
    assert outliers <= DIRECTION_OUTLIER_FRACTION

    # 4. Disk crossing radius and redshift are reflection scalars.
    recorded = (north["disk_r"] > 0.0) & (south["disk_r"] > 0.0)
    assert np.count_nonzero(recorded) > 50
    delta_r = np.abs(north["disk_r"] - south["disk_r"])[recorded]
    delta_g = np.abs(north["disk_g"] - south["disk_g"])[recorded]
    assert np.percentile(delta_r, 99) <= DISK_R_P99
    assert delta_r.max() <= DISK_R_MAX
    assert np.percentile(delta_g, 99) <= DISK_G_P99
    assert delta_g.max() <= DISK_G_MAX
