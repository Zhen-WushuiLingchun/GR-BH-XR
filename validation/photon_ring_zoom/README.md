# Photon-Ring / Lensing-Band Zoom Validation

Phase: Task 6 pre-transfer diagnostic.

This validation target makes high-order image structure visible before the thin
disk transfer function exists. It uses the CPU Boyer-Lindquist reference tracer
and the same capture/escape event semantics as Phase 1. It does not add disk
emissivity, redshift, observed intensity, or GRRT.

## Physical Meaning

The zoom records two screen-ray diagnostics:

- `azimuthal_winding = |Delta phi| / (2 pi)`;
- `image_order = floor(2 * azimuthal_winding)`.

This `image_order` is a half-orbit winding proxy for background-lensing and
photon-ring inspection. It is not the final thin-disk crossing order `m`.
Task 6 disk transfer will later record per-crossing `(r_m, phi_m, g_m,
Delta t_m, n_m)`.

The expected qualitative behavior follows
`gralla2019shadowsPhotonRings` and `gralla2020lensingKerr`: higher-order image
bands are exponentially compressed toward the critical curve. In a full
`alpha, beta in [-8M, 8M]` map the `n >= 2` structure is near or below the
pixel scale, so a narrow screen window is required.

## Command

From the source tree:

```text
$env:PYTHONPATH='src'
python -m gr_bh_xr.generate_lens_map --spin 0 --inclination-deg 90 --grid 129 --alpha-min 4.8 --alpha-max 5.6 --beta-min -0.4 --beta-max 0.4 --r-obs 80 --out outputs/task6/lensing_band_zoom_schwarzschild.h5
python -m gr_bh_xr.plot_lensing_band_zoom --input outputs/task6/lensing_band_zoom_schwarzschild.h5 --out figures/lensing_band_zoom_schwarzschild.pdf
```

Generated HDF5/PDF outputs are ignored by Git.

## Acceptance

- HDF5 schema is `gr-bh-xr.phase1.lens_map.v6`.
- `azimuthal_winding` and `image_order` datasets exist and match the screen
  grid.
- The screen window is asymmetric and records `alpha_min`, `alpha_max`,
  `beta_min`, and `beta_max` as attributes.
- The zoom figure renders image-order proxy, azimuthal winding, and minimum
  radius panels without retracing rays.
- The figure is interpreted only as photon-ring / high-order-image diagnostic
  support, not as a thin-disk transfer image.
