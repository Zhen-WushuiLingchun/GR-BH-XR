import math

import h5py
import numpy as np

from gr_bh_xr.disk import isco_radius, redshift_factor
from gr_bh_xr.generate_disk_transfer import SCHEMA, generate_disk_transfer
from gr_bh_xr.geodesic import trace_ray
from gr_bh_xr.types import CameraConfig, MetricParams, TraceConfig


def test_isco_and_redshift_schwarzschild_limits():
    params = MetricParams(M=1.0, a=0.0)

    assert math.isclose(isco_radius(params), 6.0, rel_tol=0.0, abs_tol=1.0e-14)
    g = redshift_factor(params, r=10.0, p_t=-1.0, p_phi=0.0)

    assert math.isclose(g, math.sqrt(1.0 - 3.0 / 10.0), rel_tol=1.0e-12)


def test_trace_ray_records_equatorial_crossing_states():
    params = MetricParams(M=1.0, a=0.0)
    diagnostics = trace_ray(
        params,
        CameraConfig(r_obs=80.0, theta_obs=math.radians(60.0), alpha=3.0, beta=3.0),
        TraceConfig(max_lambda=900.0, r_escape=160.0, max_step=2.0),
    )

    assert diagnostics.disk_crossings >= 1
    assert len(diagnostics.disk_crossing_r) == diagnostics.disk_crossings
    assert len(diagnostics.disk_crossing_phi) == diagnostics.disk_crossings
    assert len(diagnostics.disk_crossing_p_phi) == diagnostics.disk_crossings
    assert all(math.isfinite(value) for value in diagnostics.disk_crossing_r)


def test_generate_disk_transfer_writes_thin_disk_buffers(tmp_path):
    out = tmp_path / "disk_transfer.h5"

    summary = generate_disk_transfer(
        params=MetricParams(M=1.0, a=0.0),
        inclination_deg=60.0,
        grid=9,
        alpha_max=12.0,
        beta_max=12.0,
        r_obs=80.0,
        max_lambda=900.0,
        horizon_eps=0.3,
        max_step=2.0,
        r_out=30.0,
        max_order=2,
        out=out,
        command="pytest disk transfer",
        verbose=False,
    )

    assert summary["schema"] == SCHEMA
    assert summary["pixels_with_disk_hit"] > 0
    assert summary["valid_by_order"][0] > 0

    with h5py.File(out, "r") as handle:
        assert handle.attrs["schema"] == SCHEMA
        assert math.isclose(float(handle.attrs["r_in"]), 6.0, rel_tol=0.0, abs_tol=1.0e-14)
        assert handle.attrs["r_out"] == 30.0
        assert handle.attrs["max_order"] == 2
        for dataset in (
            "alpha",
            "beta",
            "event_code",
            "failure_code",
            "disk_crossing_count",
            "disk_r_m",
            "disk_phi_m",
            "disk_t_m",
            "disk_g_m",
        ):
            assert dataset in handle
        assert handle["disk_r_m"].shape == (2, 9, 9)
        valid = np.isfinite(handle["disk_r_m"][...])
        assert np.count_nonzero(valid) > 0
        assert np.all(handle["disk_r_m"][...][valid] >= 6.0)
        assert np.all(handle["disk_r_m"][...][valid] <= 30.0)
        assert np.all(np.isfinite(handle["disk_g_m"][...][valid]))
        assert np.nanmin(handle["disk_g_m"][...]) > 0.0
