# Thin Disk Transfer Validation

Phase: Task 6 CPU thin-disk transfer function.

This is the first formal disk-transfer data product. It records where screen
rays cross an equatorial, geometrically thin Keplerian disk and computes the
Cunningham-style redshift factor for those crossings. It does not yet assign a
disk emissivity, optical depth, or observed intensity.

## Physical Model

- Coordinates: Boyer-Lindquist exterior coordinates, geometric units.
- Disk plane: `theta = pi / 2`.
- Disk inner edge: `r_in = r_ISCO(a)` from
  `bardeen1972rotatingBlackHoles`.
- Disk outer edge: user-provided `r_out`.
- Emitter: equatorial circular Keplerian four-velocity.
- Redshift: `g = nu_obs / nu_emit = E / (u^t (E - Omega L_z))`, using the
  asymptotic observer convention already used by the Bardeen screen camera.

Crossing order `m` is the order of valid disk crossings inside
`r_ISCO <= r_m <= r_out`. This is the disk-transfer order, distinct from the
photon-ring zoom's azimuthal winding proxy.

## Command

From the source tree:

```text
$env:PYTHONPATH='src'
python -m gr_bh_xr.generate_disk_transfer --spin 0 --inclination-deg 60 --grid 65 --alpha-max 12 --beta-max 12 --r-out 30 --max-order 2 --out outputs/task6/disk_transfer_schwarzschild_i60.h5
```

Generated HDF5 outputs are ignored by Git.

## HDF5 Schema

Schema: `gr-bh-xr.task6.thin_disk_transfer.v1`.

Datasets:

- `alpha`, `beta`: screen axes.
- `event_code`, `failure_code`: final ray event and failure reason.
- `disk_crossing_count`: number of stored valid disk crossings per pixel.
- `disk_m`: stored crossing-order axis.
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

Next validation target: reproduce a Luminet-style direct/secondary thin-disk
image or equal-radius curve diagnostic before GPU/Unity texture integration.
