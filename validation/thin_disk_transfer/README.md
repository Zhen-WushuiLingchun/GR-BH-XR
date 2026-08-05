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
  For nonzero Kerr spin, the numerical radial integral is checked against the
  Page-Thorne root/log closed form in `x = sqrt(r/M)`, using the roots of
  `x^3 - 3x + 2a = 0`.

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

For the CPU blackbody color LUT seed:

```text
$env:PYTHONPATH='src'
python -m gr_bh_xr.generate_disk_color_lut --temperature-min-k 1000 --temperature-max-k 40000 --samples 256 --out outputs/task6/disk_color_lut_1000_40000_256.npz
```

For Unity disk-color audit assets, also export raw one-dimensional RGBA32F
textures and JSON metadata. Place these four files in the same Unity
`FullSkyTransfer...` directory as the disk transfer cubemaps:

```text
$env:PYTHONPATH='src'
python -m gr_bh_xr.generate_disk_color_lut `
  --temperature-min-k 1000 --temperature-max-k 40000 --samples 256 `
  --out outputs/task6/disk_color_lut_1000_40000_256.npz `
  --raw-rgba32f outputs/task6/disk_color_lut_rgba32f.bytes `
  --metadata-json outputs/task6/disk_color_lut_metadata.json `
  --spin 0.9 --r-max 30 --radius-samples 512 --temperature-scale-k 6500 `
  --radial-raw-rgba32f outputs/task6/disk_radial_lut_rgba32f.bytes `
  --radial-metadata-json outputs/task6/disk_radial_lut_metadata.json
```

The color LUT is indexed by `log(T_obs)`. The radial LUT stores normalized
Page-Thorne `F(r)` and `[F(r)/max(F)]^(1/4)`. Unity combines these with each
pixel's transfer-map redshift as `T_obs = g T_scale T_shape` and baseline
bolometric brightness `F_norm g^4`. The LUTs do not set absolute luminosity;
that still requires an accretion-rate and distance normalization.

### Color LUT v2: inverse Planck locus in alpha

Schema `gr-bh-xr.task6.disk_color_lut.v2` keeps the RGB chromaticity table
unchanged and fills the previously constant alpha channel with the *inverse*
Planck locus, so one texture carries both directions of the blackbody color
map:

```text
forward:  s = log(T_obs / T_min) / log(T_max / T_min)  ->  rgb chromaticity
inverse:  u = R / (R + B) of a source pixel            ->  alpha = s
          T = T_min * (T_max / T_min)^alpha
```

This is a project chromaticity heuristic (a red-to-blue ratio match), not a
literature-derived spectral fit; see `docs/equations.md`. It ignores the green
channel and minimizes no residual, so an off-locus pixel's recovered
temperature has no goodness-of-fit meaning. `u` is scale invariant but not
gamma invariant, so the caller must supply linear values.

`u` decreases with temperature along the locus, but only after the cold
plateau is removed: below roughly `1.9e3 K` the clipped linear sRGB blue
channel is exactly zero, so `u = 1` for a run of rows and the raw coordinate is
not invertible there. `blackbody_locus_inverse` keeps only the hottest member
of the plateau (`44` of `256` rows dropped for the default `1000-40000 K`
range, recorded as `plateauRowsDropped`) and fails closed if fewer than two
rows survive or the remainder is not strictly monotone. That failure is
reachable from the CLI - `--temperature-max-k 1800` inverts nothing - and is
tested.

The inverse therefore **saturates on the cold side**: `1000 K` and `1500 K`
both recover as `1933.06 K`, about `1.6` LUT texels above the `1889.88 K`
anchor row published as `alphaAnchorTemperatureK`. The inverse can never
return `temperatureMinK`. "Hottest temperature consistent with the
chromaticity" is true only to the LUT's temperature resolution.

Alpha is resampled at texel centers of `u`, so a shader samples it with the
source pixel's `u` directly and needs no correction. The RGB rows are
endpoint-inclusive in `s`, so the coordinate that lands exactly on row `i` is
`(s * (samples - 1) + 0.5) / samples`; that producer contract is tested
directly. The current Unity consumer samples with `u = s` instead, a
half-texel offset worth `0.72%` in effective temperature (`0.0021` per linear
sRGB channel) at `samples = 256`, and `0.027 M` in radius (`0.048` in
normalized flux on the steep inner rise) at `samples = 512` for the radial
LUT. This producer does not own the shader, so the mismatch is recorded in the
emitted metadata for the Unity worktree to reconcile rather than papered over.

`tests/test_disk_spectrum.py` gates the round trip through an emulated
bilinear fetch with clamp addressing. Measured worst case on the five-point
set `2500/4000/6500/12000/25000 K` is `2.52e-4` (at `25000 K`), and the
regression bound is `1e-3` with about `4x` headroom; a loose `3%` per-point
tolerance is kept as the user-facing bound. Boundary points are pinned
separately because the mid-range is the easy region: the hot end `40000 K`
recovers as `39652.60 K` (rel `8.68e-3`, the dense worst case, since
`du/dlnT` falls by `17x` toward `40000 K`), and the cold saturation is
asserted explicitly.

The safeguard that matters physically is structural rather than numerical: the
same LUT is used forward and backward, so in exact arithmetic the ratio is an
identity at `g = 1` and cannot distort an unshifted source color. That
identity is still subject to the consumer's own division guard, which is
Task 9-10 territory and not gated here.

### Radial LUT dimensions

`fluxPeakShape` is **not** dimensionless. It has geometric dimension
`length^-2` and scales as `M^-2` at fixed `r/M` - measured
`peak * M^2 = 4.260486e-3` for `M = 1, 2, 10` at `a/M = 0.9`, `r_max/M = 30`.
The omitted `Mdot / (4 pi)` factor is itself dimensionless in `G = c = 1`, so
dropping it cannot remove the dimension. Only the stored channels
`F/max(F)` and `[F/max(F)]^(1/4)` are dimensionless. `rMin`, `rMax`, `rISCO`,
`M` and `a` are geometric code lengths equal to `r/M` only when `M = 1`, and
`a` is `J/M` rather than the dimensionless spin despite the CLI flag being
named `--spin`; `aOverM` and `rIscoOverM` are published so the dimensionless
values are machine-readable.

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
- The Kerr `a=0.9` Page-Thorne numerical integral and closed-form expression
  match to relative `3e-6`; `a=0.998` gives the expected thin-disk efficiency
  anchor `1-E_ISCO = 0.320994`.
- A mass-scaling regression with `M=2`, `a/M=0.9` requires the closed form to
  scale as `M^-2`, matching the numerical integral.
- Redshift application helpers enforce `T_obs = g T_emit`, `g^3` specific
  intensity weighting, `g^4` bolometric weighting, and a reproducible
  blackbody LUT file with monotonic temperature samples and finite colors.
- Unity raw-LUT export writes RGBA32F color and radial tables with JSON
  metadata; tests require log-temperature indexing, linear-radius indexing,
  valid byte counts, and `T_shape^4 = F_norm` for positive Page-Thorne samples.

Next validation target: generate a Unity package containing the LUT files and
capture an A/B audit against the older visual proxy. Time-delay-aware hot-spot
animation still requires exporting `Delta t_m` to Unity disk textures.
