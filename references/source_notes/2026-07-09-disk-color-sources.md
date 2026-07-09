# 2026-07-09 Disk Color And Thin-Disk Flux Sources

## Search Context

- Search date: 2026-07-09
- Search terms:
  - Page Thorne 1974 black hole accretion disk flux zero torque
  - Wyman Sloan Shirley analytic CIE XYZ color matching functions
  - CIE 1931 colour matching functions 2 degree observer
- Goal: Replace the Unity disk emissivity proxy with a physically stronger CPU
  asset-generation path for Page-Thorne flux, redshifted blackbody color, and a
  documented color-matching approximation.

## Sources Added

### `page1974diskAccretionStructure`

- Stable locator: https://ui.adsabs.harvard.edu/abs/1974ApJ...191..499P/abstract
- PDF status: Not stored; pre-arXiv classic / publisher-controlled source.
- Summary: Page and Thorne derive the time-averaged relativistic thin-disk
  structure and flux profile around a black hole, including the zero-torque
  inner boundary at the ISCO.
- Project use: `src/gr_bh_xr/disk_spectrum.py` uses the circular-orbit
  `E`, `L_z`, `Omega`, and radial integral structure as a dimensionless flux
  shape for future disk-color lookup tables.
- Limitations: The current helper omits accretion-rate normalization, mass-to-SI
  scaling, limb darkening, returning radiation, and radiative-transfer optical
  depth. It is a validation/asset-generation seed, not yet a full disk image
  renderer.

### `wyman2013cieMatchingFits`

- Stable locator: https://jcgt.org/published/0002/02/01/
- PDF status: Not stored; open JCGT paper available online.
- Summary: Wyman, Sloan, and Shirley provide simple analytic approximations to
  the CIE 1931 2-degree XYZ color matching functions.
- Project use: `src/gr_bh_xr/disk_spectrum.py` uses the fits to integrate
  Planck spectra into XYZ chromaticity and max-normalized linear sRGB without
  storing a large CIE table.
- Limitations: The approximation is intended for deterministic visualization
  asset generation. A future calibrated radiometric mode should compare against
  the official CIE table directly.

### `cie2019xyz1931Dataset`

- Stable locator: https://cie.co.at/datatable/cie-1931-colour-matching-functions-2-degree-observer
- PDF status: Not applicable; official tabulated data page.
- Summary: Official CIE 1931 color-matching data table behind the analytic fit
  reference.
- Project use: Background provenance for color matching and a future exact-table
  validation target if the analytic fit is replaced.
- Limitations: The table is not vendored in this repository in the current
  seed.

## Implementation Notes

- The CPU seed intentionally validates only dimensionless flux shape and
  chromaticity. It does not change the Unity shader claim yet.
- The selected validation anchors are:
  - Schwarzschild circular orbit at `r=6M`:
    `E=sqrt(8/9)`, `L_z=sqrt(12)`;
  - zero flux at `r_ISCO`;
  - positive flux outside `r_ISCO`;
  - a `6504K` blackbody chromaticity near the expected D65-like Planckian
    locus.
