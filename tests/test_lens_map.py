import h5py
import numpy as np

from gr_bh_xr.generate_lens_map import EVENT_CODES, FAILURE_CODES, generate_lens_map
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
        ):
            assert dataset in handle
        assert handle["alpha"].shape == (17,)
        assert handle["beta"].shape == (17,)
        assert handle["event_code"].shape == (17, 17)
        assert handle.attrs["M"] == 1.0
        assert handle.attrs["a"] == 0.0
        assert handle.attrs["grid"] == 17
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
        assert np.count_nonzero(failure_codes == FAILURE_CODES["none"]) > 0


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
