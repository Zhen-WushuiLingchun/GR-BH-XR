from gr_bh_xr.plot_ray_examples import plot_ray_examples


def test_plot_ray_examples_renders_pdf(tmp_path):
    out = tmp_path / "ray_examples.pdf"

    plot_ray_examples(out=out, r_obs=50.0, max_lambda=400.0)

    assert out.exists()
    assert out.stat().st_size > 0
