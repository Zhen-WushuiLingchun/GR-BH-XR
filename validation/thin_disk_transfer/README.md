# Thin Disk Transfer Validation

Phase: Task 6 CPU thin-disk transfer function.

This is the first formal disk-transfer data product. It records where screen
rays cross an equatorial, geometrically thin Keplerian disk and computes the
Cunningham-style redshift factor for those crossings. It does not yet assign a
disk optical depth or observed intensity. A CPU-side Page-Thorne/color seed now
exists as a validation and asset-generation path before the Unity visual proxy
is replaced.

## Physical Model

- Coordinates: Boyer-Lindquist exterior coordinates, geometric units.
- Disk plane: `theta = pi / 2`.
- Disk inner edge: `r_in = r_ISCO(a)` from
  `bardeen1972rotatingBlackHoles`.
- Disk outer edge: user-provided `r_out`.
- Emitter: equatorial circular Keplerian four-velocity.
- Redshift: `g = nu_obs / nu_emit = E / (u^t (E - Omega L_z))`, using the
  asymptotic observer convention already used by the Bardeen screen camera.
- Emissivity/color seed: `src/gr_bh_xr/disk_spectrum.py` computes a
  Page-Thorne-style zero-torque flux shape `F(r)`, converts it to
  `T_eff(r) proportional to F(r)^(1/4)`, and integrates blackbody spectra
  against analytic CIE 1931 color-matching fits for future disk-color LUTs.
  The result is dimensionless until an accretion-rate and mass scale are chosen.

Crossing order `m` is the zero-based order of true equatorial-plane crossings
before annulus filtering. Crossings outside `r_ISCO <= r_m <= r_out` are not
stored, but later valid crossings keep their true `m` slot. This is the
disk-image order used to separate direct, secondary, and higher-order images;
it is distinct from the photon-ring zoom's azimuthal winding proxy.

## Command

From the source tree:

```text
$env:PYTHONPATH='src'
python -m gr_bh_xr.generate_disk_transfer --spin 0 --inclination-deg 60 --grid 65 --alpha-max 12 --beta-max 12 --r-out 30 --max-order 2 --out outputs/task6/disk_transfer_schwarzschild_i60.h5
```

Generated HDF5 outputs are ignored by Git.

For the first Luminet-style equal-radius diagnostic, use a high-inclination
Schwarzschild map and render direct/secondary `r_m(alpha,beta)` curves:

```text
$env:PYTHONPATH='src'
python -m gr_bh_xr.generate_disk_transfer --spin 0 --inclination-deg 80 --grid 65 --alpha-max 30 --beta-max 30 --r-out 30 --max-order 2 --out outputs/task6/disk_transfer_luminet_i80.h5
python -m gr_bh_xr.plot_disk_transfer --input outputs/task6/disk_transfer_luminet_i80.h5 --out outputs/task6/luminet_equal_radius_i80.pdf
```

For the formal Luminet-orientation check, prefer an even grid or a small
`alpha` offset so the grid does not sample `alpha = 0` exactly:

```text
$env:PYTHONPATH='src'
python -m gr_bh_xr.generate_disk_transfer --spin 0 --inclination-deg 80 --grid 64 --alpha-max 30 --beta-max 30 --r-out 30 --max-order 2 --out outputs/task6/disk_transfer_luminet_i80_64_even.h5
python -m gr_bh_xr.plot_disk_transfer --input outputs/task6/disk_transfer_luminet_i80_64_even.h5 --out outputs/task6/luminet_equal_radius_i80_64_even.pdf
```

This figure is a geometric transfer diagnostic: it shows direct (`m = 0`) and
secondary (`m = 1`) equal-radius curves plus the direct-image redshift buffer.
It is not yet a Luminet intensity image because emissivity, optical depth, and
observed intensity are still deferred.

`plot_disk_transfer` displays the vertical axis as visual beta, matching the
Unity export convention. The raw solver coordinate `+beta` increases
Boyer-Lindquist `theta`, which is visually downward on the observer screen, so
the plot reverses the raw beta rows and labels the axis as
`visual beta / M (up = - solver beta)`.

The Boyer-Lindquist exterior solver still terminates `L_z = 0` rays at the
polar-axis coordinate singularity. In a high-inclination Schwarzschild disk
plot this can remove a narrow far-side secondary arch near `alpha = 0`.
Avoiding an exact `alpha = 0` sample makes the surrounding arch visible, but it
does not remove the underlying coordinate limitation; an axis-regular or
Kerr-Schild continuation remains the physical fix.

## HDF5 Schema

Schema: `gr-bh-xr.task6.thin_disk_transfer.v2`.

Datasets:

- `alpha`, `beta`: screen axes.
- `event_code`, `failure_code`: final ray event and failure reason.
- `disk_crossing_count`: number of stored valid emitting-annulus crossings per
  pixel.
- `disk_m`: true equatorial crossing-order axis.
- `disk_r_m`, `disk_phi_m`, `disk_t_m`, `disk_g_m`: arrays with shape
  `(max_order, grid, grid)` and NaN where a crossing order is absent.

Attributes record `M`, `a`, `inclination_deg`, `r_obs`, screen bounds,
`r_in`, `r_out`, `max_order`, and numerical integration settings.

## Acceptance

- `r_ISCO(a=0) = 6M`.
- Schwarzschild redshift for `L_z = 0` at radius `r` reduces to
  `g = sqrt(1 - 3M/r)`.
- A small Schwarzschild disk-transfer map writes all required datasets and has
  at least one valid direct disk crossing.
- Stored disk radii satisfy `r_in <= r_m <= r_out` and stored `g_m` values are
  finite and positive.
- A Luminet-style equal-radius diagnostic can be produced with separate
  direct and secondary panels from the same HDF5 transfer file.
- CPU disk-color helpers reproduce `E(r=6M)=sqrt(8/9)`,
  `L_z(r=6M)=sqrt(12)`, enforce `F(r_ISCO)=0`, produce positive flux outside
  the ISCO, and place a `6504K` blackbody near the expected D65-like
  chromaticity.

Next validation target: add emissivity and observed-intensity buffers, then
compare a rendered high-inclination Schwarzschild disk image against the
qualitative Luminet 1979 direct/secondary morphology.
