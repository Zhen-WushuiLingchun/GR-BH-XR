import h5py
import numpy as np

from gr_bh_xr.generate_lens_map import EVENT_CODES, FAILURE_CODES, generate_lens_map
from gr_bh_xr.plot_lensing_band_zoom import plot_lensing_band_zoom
from gr_bh_xr.plot_lens_map import plot_lens_map
from gr_bh_xr.types import MetricParams


def test_generate_lens_map_writes_required_hdf5_buffers(tmp_path):
    out = tmp_path / "lensmap_schwarzschild.h5"

    summary = generate_lens_map(
        params=MetricParams(M=1.0, a=0.0),
        inclination_deg=90.0,
        grid=17,
        alpha_max=8.0,
        beta_max=8.0,
        r_obs=50.0,
        max_lambda=700.0,
        horizon_eps=0.3,
        max_step=2.0,
        out=str(out),
        command="pytest",
        verbose=False,
    )

    assert out.exists()
    assert summary["event_counts"]["capture"] > 0
    assert summary["event_counts"]["escape"] > 0
    assert "failure_counts" in summary
    assert summary["failure_counts"]["none"] > 0

    with h5py.File(out, "r") as handle:
        for dataset in (
            "alpha",
            "beta",
            "event_code",
            "failure_code",
            "min_r",
            "h_max_abs",
            "e_drift_abs",
            "lz_drift_abs",
            "q_drift_abs",
            "disk_crossings",
            "azimuthal_winding",
            "image_order",
            "escape_theta",
            "escape_phi",
            "escape_dir_x",
            "escape_dir_y",
            "escape_dir_z",
        ):
            assert dataset in handle
        assert handle["alpha"].shape == (17,)
        assert handle["beta"].shape == (17,)
        assert handle["event_code"].shape == (17, 17)
        assert handle.attrs["schema"] == "gr-bh-xr.phase1.lens_map.v6"
        assert handle.attrs["M"] == 1.0
        assert handle.attrs["a"] == 0.0
        assert handle.attrs["grid"] == 17
        assert handle.attrs["alpha_min"] == -8.0
        assert handle.attrs["beta_min"] == -8.0
        assert handle.attrs["horizon_eps"] == 0.3
        assert handle.attrs["generation_command"] == "pytest"
        for event, code in EVENT_CODES.items():
            assert handle["event_code"].attrs[f"code_{event}"] == code
        for failure, code in FAILURE_CODES.items():
            assert handle["failure_code"].attrs[f"code_{failure}"] == code
        event_codes = handle["event_code"][...]
        failure_codes = handle["failure_code"][...]
        assert np.count_nonzero(event_codes == EVENT_CODES["capture"]) > 0
        assert np.count_nonzero(event_codes == EVENT_CODES["escape"]) > 0
        escape_mask = event_codes == EVENT_CODES["escape"]
        assert np.all(np.isfinite(handle["escape_theta"][...][escape_mask]))
        assert np.all(np.isfinite(handle["escape_phi"][...][escape_mask]))
        assert np.all(np.isfinite(handle["escape_dir_x"][...][escape_mask]))
        assert np.nanmax(handle["azimuthal_winding"][...]) >= 0.0
        assert np.nanmax(handle["image_order"][...]) >= 0
        assert np.count_nonzero(failure_codes == FAILURE_CODES["none"]) > 0
        axis_col = len(handle["alpha"]) // 2
        axis_invalid = event_codes[:, axis_col] == EVENT_CODES["invalid"]
        assert np.count_nonzero(axis_invalid) > 0
        assert np.all(
            failure_codes[:, axis_col][axis_invalid]
            == FAILURE_CODES["axis_coordinate_singularity"]
        )


def test_plot_lens_map_renders_pdf_from_hdf5(tmp_path):
    h5_path = tmp_path / "lensmap_schwarzschild.h5"
    pdf_path = tmp_path / "shadow_validation.pdf"
    generate_lens_map(
        params=MetricParams(M=1.0, a=0.0),
        inclination_deg=90.0,
        grid=17,
        alpha_max=8.0,
        beta_max=8.0,
        r_obs=50.0,
        max_lambda=700.0,
        horizon_eps=0.3,
        max_step=2.0,
        out=h5_path,
        command="pytest",
        verbose=False,
    )

    plot_lens_map(input_path=h5_path, out=pdf_path)

    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


def test_lensing_band_zoom_uses_asymmetric_screen_window(tmp_path):
    h5_path = tmp_path / "lensing_band_zoom.h5"
    pdf_path = tmp_path / "lensing_band_zoom.pdf"

    summary = generate_lens_map(
        params=MetricParams(M=1.0, a=0.0),
        inclination_deg=90.0,
        grid=9,
        alpha_min=4.8,
        alpha_max=5.6,
        beta_min=-0.4,
        beta_max=0.4,
        r_obs=80.0,
        max_lambda=700.0,
        horizon_eps=0.3,
        max_step=2.0,
        out=h5_path,
        command="pytest zoom",
        verbose=False,
    )

    assert summary["alpha_range"] == [4.8, 5.6]
    assert summary["beta_range"] == [-0.4, 0.4]
    assert summary["max_image_order"] is not None

    with h5py.File(h5_path, "r") as handle:
        assert handle.attrs["schema"] == "gr-bh-xr.phase1.lens_map.v6"
        np.testing.assert_allclose(handle["alpha"][[0, -1]], [4.8, 5.6])
        np.testing.assert_allclose(handle["beta"][[0, -1]], [-0.4, 0.4])
        assert "azimuthal_winding" in handle
        assert "image_order" in handle
        assert np.nanmax(handle["image_order"][...]) >= 1

    plot_lensing_band_zoom(input_path=h5_path, out=pdf_path)

    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
