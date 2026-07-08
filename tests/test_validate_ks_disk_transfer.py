from gr_bh_xr.types import MetricParams
from gr_bh_xr.validate_ks_disk_transfer import SCHEMA, validate_ks_disk_transfer


def test_ks_disk_transfer_compare_matches_bl_on_small_kerr_grid(tmp_path):
    out = tmp_path / "ks_disk_compare.json"
    h5 = tmp_path / "ks_disk_compare.h5"

    summary = validate_ks_disk_transfer(
        params=MetricParams(M=1.0, a=0.5),
        inclination_deg=60.0,
        grid=6,
        alpha_max=12.0,
        beta_max=12.0,
        r_obs=80.0,
        max_lambda=900.0,
        r_escape=160.0,
        horizon_eps=0.05,
        max_step=1.0,
        r_out=30.0,
        max_order=2,
        out=out,
        h5=h5,
        verbose=False,
    )

    assert summary["schema"] == SCHEMA
    assert out.exists()
    assert h5.exists()
    assert summary["event_mismatch_count"] == 0
    assert summary["disk_validity_mismatch_count"] == 0
    assert summary["compare_sample_count"] > 0
    assert summary["bl_valid_by_order"] == summary["ks_valid_by_order"]
    assert summary["disk_r_max_abs_error"] < 1.0e-6
    assert summary["disk_phi_max_error_rad"] < 1.0e-6
    assert summary["disk_t_max_abs_error"] < 1.0e-6
    assert summary["disk_g_max_abs_error"] < 1.0e-8
    assert summary["ks_h_max_abs"] < 1.0e-8
