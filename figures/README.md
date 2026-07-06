# Figures

This directory is reserved for generated validation and presentation figures.
PDF/bitmap outputs are ignored by Git unless a future data policy explicitly
promotes a figure to a tracked artifact.

Current Phase 1 command:

```text
$env:PYTHONPATH='src'
python -m gr_bh_xr.plot_ray_examples --out figures/ray_examples.pdf
```

Task 6 pre-transfer photon-ring / lensing-band zoom:

```text
$env:PYTHONPATH='src'
python -m gr_bh_xr.generate_lens_map --spin 0 --inclination-deg 90 --grid 129 --alpha-min 4.8 --alpha-max 5.6 --beta-min -0.4 --beta-max 0.4 --r-obs 80 --out outputs/task6/lensing_band_zoom_schwarzschild.h5
python -m gr_bh_xr.plot_lensing_band_zoom --input outputs/task6/lensing_band_zoom_schwarzschild.h5 --out figures/lensing_band_zoom_schwarzschild.pdf
```
