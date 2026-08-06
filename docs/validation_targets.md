# Validation Targets

Validation is part of the physics interface. A renderer output is not considered
academic until its relevant validation path is documented.

## Phase 0 Documentation Gate

Before implementation:

- references for AART, RAPTOR, Odyssey, Quest/OpenXR limits, and VR black-hole
  precedent are indexed;
- open arXiv PDFs for RAPTOR, BHAC, Davelaar VR, and AART are stored under
  `references/pdfs/`;
- expanded open PDFs for RAPTOR II, grtrans, ipole, Younsi/Wu/Fuerst GRRT,
  HARM, primitive recovery, EHT GRMHD comparison, iharm3D, Athena++ radiation
  GRMHD, KORAL M1 radiation fluid dynamics, Bruneton real-time shader, and
  Kerr-Newman polarization watchlist are stored under `references/pdfs/`;
- foundational analytic references behind the documented equations are indexed:
  Carter 1968 (Carter constant), Bardeen/Press/Teukolsky 1972 (ISCO), Bardeen
  1973 (Kerr null geodesics and screen coordinates), Cunningham 1975 (disk
  redshift transfer), Luminet 1979 (direct/secondary disk images), and the
  Gralla-Holz-Wald 2019 / Gralla-Lupsasca 2020 photon-ring papers, with open
  PDFs stored where available and pre-arXiv classics indexed by DOI/bibcode;
- every equation block in `docs/equations.md` cites a primary source;
- BibTeX keys for literature and reviewed code repositories are stored in
  `references/references.bib`;
- reference code reviews for RAPTOR, AART, Odyssey, ipole, and grtrans are
  stored under `references/code_reviews/`;
- real-time GLSL/WebGL/Vulkan reference reviews for Zhihu, NPGS, Bruneton, and
  Oseiskar sources are stored under `references/code_reviews/`;
- no third-party source code is copied into this repository;
- shader demos and gray-literature sources are explicitly marked as engineering
  references, not validation benchmarks;
- shadow, critical curve, lensing ring, photon ring, higher-order image, ISCO,
  and disk inner edge are defined;
- equations and conventions are documented;
- first implementation exclusions are explicit.

Phase 0 validation commands:

```text
git status --short --branch
git diff --check
git check-ignore -v references/pdfs/local_only/test.pdf
git check-attr diff merge text -- references/pdfs/example.pdf
```

## Phase 1 CPU Kerr Reference Solver

Required checks:

- null Hamiltonian residual per ray;
- drift of `E = -p_t`;
- drift of `L_z = p_phi`;
- Carter constant drift where applicable;
- horizon hit / sky escape / disk crossing classification;
- Schwarzschild critical impact parameter:

```text
b_c = 3 sqrt(3) M
```

- Kerr critical-curve comparison against spherical photon orbit formulae from
  `gralla2020nullGeodesicsKerr` / `bardeen1973kerrGeodesics` for at least
  `a = 0.5`, `i = 60 deg` and `a = 0.9`, `i = 60 deg`;

Current Phase 1 analytic-derivative target:

```text
outer grouped max |H| < 1e-8 for default Kerr critical-curve runs
near-capture max |H| is recorded but not used as the critical-curve pass/fail gate
```

The stricter outer-ray target is enabled by closed-form derivatives of
`g^{mu nu}`. Near-capture rays are still reported separately because
Boyer-Lindquist coordinates remain ill-conditioned close to the horizon.

Kerr critical-curve validation target:

```text
max_abs_error < 0.05 M
rms_error < 0.02 M
invalid event count = 0
```

Kerr critical-curve JSON must split diagnostics into `outer` and
`near_capture` groups so near-horizon Boyer-Lindquist residual degradation is
not confused with the outer-ray Hamiltonian target.

`E = -p_t` and `L_z = p_phi` drift are still recorded, but they are structural
zeroes for the current Hamiltonian implementation because `t` and `phi` are
cyclic coordinates and the right-hand side does not update `p_t` or `p_phi`.
The informative numerical drift checks are therefore `H` and Carter `Q`.

Lens-map persistence target:

- HDF5 output records `alpha`, `beta`, `event_code`, `min_r`, `h_max_abs`,
  `e_drift_abs`, `lz_drift_abs`, `q_drift_abs`, `disk_crossings`, and
  `failure_code`;
- HDF5 output records `azimuthal_winding = |Delta phi| / (2 pi)` and
  `image_order = floor(2 * azimuthal_winding)` as a screen-ray winding
  diagnostic for photon-ring / high-order-image zooms;
- event-code and failure-code mappings are stored in HDF5 attributes;
- `axis_coordinate_singularity` is a separate failure reason for `L_z = 0`
  rays that hit the Boyer-Lindquist polar-axis coordinate singularity;
- default Schwarzschild `alpha_max = beta_max = 8M` map includes both capture
  and escape samples;
- a validation figure can be generated from the HDF5 file without retracing
  rays.

Ray-example figure target:

- `figures/ray_examples.pdf` can be regenerated from the Phase 1 Hamiltonian
  RHS and shows capture, near-critical, and escape equatorial Schwarzschild
  rays as an illustrative sanity check.

Task 3 was implemented as a Python source package under `src/gr_bh_xr/` rather
than the illustrative C++ paths in the roadmap. The roadmap explicitly allowed
Python or C++ for the reference solver; GPU work remains deferred to Task 4.

The tolerance may be revised only with a documented numerical reason.

## Phase 2 GPU Kerr Lensing

Task 4 starts Phase 2 with a WGPU Vulkan compute prototype. The CPU DOP853
solver remains the scientific reference; the GPU path is a real-time f32
fixed-step RK4 baseline for capture/escape/debug texture generation.

Required Task 4 checks:

- WGPU selects a Vulkan adapter, preferring the NVIDIA discrete GPU when
  available;
- GPU HDF5 output uses schema `gr-bh-xr.phase2.gpu_lens_map.v3` and records
  `alpha`, `beta`, `gpu_event_code`, `gpu_failure_code`, `gpu_min_r`,
  `gpu_h_max_abs`, `gpu_q_drift_abs`, `gpu_steps`, `event_rgba8`, and
  `debug_rgba8`;
- GPU HDF5 output also records the first two true equatorial crossing layers
  as `gpu_disk_r_m`, `gpu_disk_phi_m`, `gpu_disk_sin_phi_m`,
  `gpu_disk_cos_phi_m`, `gpu_disk_t_m`, and `gpu_disk_g_m`; these are transfer
  buffers and do not change the capture/escape event classification gate;
- disk-transfer buffers may contain valid crossings even if the ray later ends
  as `invalid` at the Boyer-Lindquist axis; consumers must treat disk-buffer
  validity independently from the final `event_code`;
- CPU-vs-GPU comparison files also record `cpu_event_code`,
  `cpu_failure_code`, `cpu_min_r`, and the masks used to exclude CPU failures,
  the near-critical screen band, and near-capture Boyer-Lindquist samples;
- stable-region CPU-vs-GPU event agreement is at least `98%` for
  Schwarzschild and Kerr `a = 0.5`, `i = 60 deg`;
- Schwarzschild GPU capture fraction differs from the same-grid CPU capture
  fraction by less than `0.03`;
- GPU failure counts are zero outside documented CPU-failure, critical-band,
  and near-capture exclusions;
- CPU-vs-GPU comparison output records both the stable-region event agreement
  used for the gate and a full-grid event-agreement field used to detect
  cancelling capture/escape count errors;
- escaped rays record momentum-derived asymptotic sky direction buffers, not
  escape-sphere position angles, and the GPU validator compares CPU-vs-GPU unit
  direction vectors on stable escaped pixels;
- the CPU escape-direction definition is regression-tested by comparing the
  same Schwarzschild escape ray at `r_escape = 200M` and `400M`, requiring
  angular drift below `1e-5 rad`;
- generated HDF5/debug texture artifacts stay under ignored `outputs/phase2/`.
- the analytic critical-curve band is marked by a refinement buffer and
  supersampled into subpixel capture/invalid fractions for downstream texture
  and photon-ring work.

Task 4 explicitly does not validate thin-disk transfer, redshift, time delay,
GRRT, Quest/OpenXR runtime integration, adaptive RK, or Kerr-Schild
horizon/axis continuation. Large `gpu_h_max_abs` values near capture or failure
pixels are audit metadata for the f32 fixed-step shader, not a replacement for
the Phase 1 CPU Hamiltonian gate.

At 256x256, small-`|L_z|` near-polar rays exposed a fixed-step f32 artifact in
the first Task 4 commit: if the even grid sampled columns close to but not
exactly on `alpha = 0`, RK4 could step over the narrow polar centrifugal
barrier and report `solver_failure`, or use the shorter GPU affine-parameter
budget and report `unclassified_max_lambda`. The follow-up shader adds
near-polar substepping and reserves `polar_step_overshoot = 5`; the reviewed
256x256 Kerr case now has zero solver/max-lambda failures.

Tier 1 latency evidence must be recorded before claiming interactive
parameter-space tracing. The benchmark command is
`python -m gr_bh_xr.gpu.benchmark_latency`; results must state whether
critical-band refinement is enabled and must separate GPU tracing/readback from
HDF5 writes and Unity texture upload. On 2026-07-07, the local RTX 5080 Laptop
GPU measured Kerr `a = 0.9`, `i = 60 deg`, `r_obs = 100M`, `h = 0.05`,
`8000` steps at `49 ms`, `186 ms`, and `653 ms` for raw `256x256`, `512x512`,
and `1024x1024` maps. With `critical_refine_band = 0.25M` and `2x2`
refinement, the corresponding times were `113 ms`, `346 ms`, and `1.24 s`.
These numbers support slider-release or progressive single-Kerr updates, not
headset-rate per-frame geodesic integration.

## Phase 3 Quest PCVR

Task 5 begins with a static Unity texture bridge. Before any headset claim,
the bridge must define the coordinate contract from HDF5 screen buffers to
Unity textures:

- raw texture pixel order is documented as `x -> alpha`, with exported `y`
  vertically flipped relative to solver rows so `UV(0,0) -> (alpha_min,
  beta_max)` and `UV(1,1) -> (alpha_max, beta_min)`;
- the metadata records that solver `+beta` points toward increasing
  Boyer-Lindquist `theta` / visual down, while Unity texture `+V` points visual
  up after the export flip;
- black-hole Cartesian axes are documented with `+Z_BH` as the spin axis and
  the observer at Boyer-Lindquist `phi = 0`, `theta = inclination_deg`;
- Unity basis vectors are stored in exported metadata, with `forward_BH` from
  camera to black hole, `up_BH` as the projected spin axis, and `right_BH` as
  the positive-`alpha` direction;
- Unity consumes `event_rgba8` plus `escape_dir_unity_rgba32f`, not a visual
  RGB-only render;
- background-lensing claims use a full-sky transfer cubemap generated from the
  finite-radius static observer tetrad. A finite `alpha,beta` lens texture may
  be used as a higher-resolution central patch, but it must blend into the
  full-sky transfer map rather than falling back to an unlensed skybox at the
  screen-window edge;
- Unity shaders use explicit lens-screen world basis vectors for physical
  directions and must not use scale-bearing object matrices for escaped-ray
  cubemap lookup or angular-window ray projection;
- runtime recentering or anchor rotation must refresh the lens-screen basis,
  either by reapplying the material binding or by a per-frame lightweight
  basis update;
- the exporter is tested on synthetic HDF5 input and a weak-deflection GPU map
  so byte sizes, valid masks, basis mapping, and vertical handedness cannot
  silently flip or mirror.

Required checks:

- before Quest runtime validation, the Unity desktop gate includes both a
  sign-level quadrant handedness capture and a magnitude-sensitive protractor
  capture that compares screenshot color bands against `escape_dir_unity`;
- the angular-window path is tested on desktop at yaw `0 deg`, `2 deg`, and
  `4 deg` before it is used as evidence for head-rotation stability;
- the full-sky path is tested on desktop at yaw `0 deg`, `2 deg`, and `4 deg`
  with `-grbhxrFullSkyTransferDir`, and the validation image must not show the
  square hard boundary produced by unlensed-skybox fallback;
- the full-sky finite-observer tetrad path is compared against the CPU DOP853
  reference with `python -m gr_bh_xr.gpu.validate_full_sky_transfer` before it
  is used for Quest first-run claims. Stable-sample event agreement must be at
  least `98%`, GPU failures outside documented exclusions must be `0`, and
  stable escaped-ray direction errors should satisfy median `< 1e-4 rad` and
  RMS `< 5e-4 rad`;
- the full-sky protractor/yaw gate must compare the Unity screenshot against
  `escape_dir_unity_cube_rgba32f.bytes` from the full-sky cubemap, not against
  the old 2D `escape_dir_unity_rgba32f.bytes` patch. Across the former
  `[-8M, 8M]` window boundary, adjacent valid protractor samples may differ by
  at most one 10-degree band except where capture/invalid event masks
  intervene;
- Unity disk visual captures used for Quest readiness must consume disk
  transfer cubemap schema v2 or later: `disk_order*_transfer_cube_rgba16f`
  stores coverage-premultiplied `r_m`, `sin(phi_m)`, `cos(phi_m)`, and
  coverage, while `disk_order*_redshift_cube_rgba16f` stores
  coverage-premultiplied `g_m`. Legacy binary-validity disk cubes are allowed
  for older audit images but not for final disk-edge visual acceptance;
- the Unity shader includes single-pass instanced stereo macros so Quest/OpenXR
  does not render a missing or eye-shifted lens map in one eye;
- the angular-window yaw test is interpreted only as head-rotation anchoring
  for a fixed distant observer. It is not accepted as evidence for changing the
  physical Kerr observer inclination or orbiting around the black hole;
- for the Task 7 baked path, observer translation is accepted only as roam
  keyframe playback over an `(r_obs, theta)` grid, and only as a *quasi-static*
  sequence: no kinematic aberration is modeled between keyframes. Details and
  measured numbers are in `validation/roam_keyframes/README.md`. Required
  checks:
  - the roam manifest (`roam_keyframes_metadata.json`, schema
    `gr-bh-xr.task7.roam_keyframes.v2`) records log-spaced radii and sorted
    theta rows inside the envelope, with every grid point outside the
    ergosphere at its polar angle validated *before* any GPU time is spent;
  - the theta envelope is `[30, 150] deg`, which is exactly the grid the
    committed tests exercise. It is recorded as a tested range, not a measured
    failure boundary: a full-sky sweep at `r_obs = 2.5M` and `6M` finds at most
    1 invalid texel of 3456 anywhere in `theta = 2..178 deg`, with no cliff at
    either end. The envelope must NOT be justified by the Bardeen
    `1/sin(theta_obs)` screen-map degeneracy - that argument applies to
    `gr_bh_xr.gpu.preview`, which evaluates the `alpha`/`beta` screen map,
    whereas the roam path reaches the tracer through `initial_state_direction`
    and never evaluates it. A test pins that the rationale is not repeated;
  - the shadow gate is on `captureSolidAngleFraction` (solid-angle weighted,
    taken from the raw pre-repair classification), not on a raw texel count,
    because cube texels do not subtend equal solid angle. It must grow
    monotonically per theta row as `r_obs` decreases, within a tolerance of
    `3 / sqrt(total_pixels)`; a strict comparison is quantization-limited at
    the outer keyframes. Measured at `a/M = 0.9`, face 32:
    `0.000620` at `100M` to `0.551254` (theta = 30 and 150 deg) and `0.673544`
    (theta = 90 deg) at `2.5M`;
  - equatorial mirror symmetry is gated as a real per-ray invariant in
    `tests/test_roam_mirror_symmetry.py`, not as a prose claim and not as a
    capture-fraction table comparison (the cubemap texel set is itself
    invariant under the Unity y-flip, so aggregate counts are largely forced to
    agree). Escape directions must satisfy `(dx, dy, dz) -> (dx, -dy, dz)`
    between `theta` and `180 - theta`, and `r_m`, `g_m` are reflection scalars.
    Measured over 10800 ray pairs: 0 event mismatches, 0 one-sided disk
    records, escape direction p50 `0.00078 deg` / p99 `0.0183 deg`,
    `|delta r_m|` p99 `1.54e-4 M`, `|delta g_m|` p99 `1.19e-5`. The p99
    direction figure is the f32 representation floor of the `arccos(dot)`
    metric itself (a unit f32 vector dotted with itself already yields up to
    `0.0428 deg`), so the gate is a percentile plus a bounded-outlier fraction
    rather than a max, whose tail is chaotic photon-ring rays;
  - every keyframe uses an escape radius no smaller than `200M` rather than the
    legacy `2 r_obs` rule, because momentum-direction extraction at `2 r_obs`
    is not asymptotic for a near-horizon observer: measured `6.695 deg` mean /
    `22.79 deg` max direction error at `r_obs = 2.5M`, falling below
    `0.35 deg` by `r_escape = 20` and reaching its floor by `50`. The residual
    floor (`0.13 deg` at `2.5M`, `0.007 deg` at `100M`) is accumulated f32 RK4
    error along the longer near-horizon path and is NOT removable by any escape
    radius;
  - polar-band texels are REPORTED, NOT REPAIRED (`polarBand.repaired: false`).
    The chart-regular fix is a Cartesian Kerr-Schild retrace, which requires
    the KS tracer's equatorial disk-crossing outputs and therefore lands with
    the Kerr-Schild work;
  - the manifest separates `eventCounts` (raw, pre-repair) from
    `shippedEventCounts` (the bytes actually written), because the repair
    stages rewrite event codes and the two can legitimately disagree. Every
    post-trace stage carries `stages.*.applied` so a stage that is configured
    off cannot be advertised by an unconditional note;
- the validation report states that this Unity path renders a precomputed
  transfer map in real time; it does not perform per-frame geodesic integration;
- the skybox/background asset resolution is recorded separately from lens-map
  resolution. A 4K all-sky map is not enough for a narrow `~9 deg` VR FOV if
  the goal is crisp stellar background detail;
- stereo disparity is correct;
- lens map remains stable under head motion;
- 72 Hz or 90 Hz target feasibility is recorded;
- black-hole angular size and scale are documented;
- PC-to-Quest latency is recorded or qualitatively evaluated.

The full-sky cubemap still has a deferred display-polish item: a one-texel
dilation of capture/invalid edges before direction interpolation may be needed
for a full-sky-only visual mode. It is not part of the current Quest first-run
gate because the mixed shader covers the central capture edge with the
high-resolution local patch.

Minimum success:

```text
Quest 3 shows a head-stable Kerr shadow plus background lensing over PCVR.
```

## Phase 4 Thin Disk Transfer Function

Required checks:

- before adding emissivity, a critical/lensing-band zoom figure can be produced
  from CPU lens-map buffers and shows the winding/image-order proxy near the
  Schwarzschild critical curve;
- disk intersection events are recorded by crossing/image order `m`;
- `r_m`, `phi_m`, `g_m`, `Delta t_m`, and `n_m` are inspectable;
- direct, secondary, and higher-order images can be isolated;
- redshift and Doppler terms are tested in at least one limiting or benchmark
  case;
- time-delay sampling is tested with a simple time-dependent disk feature.
- real-time disk animation for the single-Kerr path uses the static transfer
  map with disk-frame advection
  `phi_emit = phi_m - Omega(r_m) * (t - Delta t_m)`; it must not retrace
  geodesics per frame unless the metric or observer changes;
- the first Unity hot-spot demo may use the display cubemap channels
  `(r_m, sin(phi_m), cos(phi_m), coverage)` plus a redshift companion cube for
  `g_m` in schema v2, or the legacy `(r_m, sin(phi_m), cos(phi_m), g_m)` cube
  in older non-final assets, for a stationary-axisymmetric lookup,
  but it must document when the Unity package lacks a separate `Delta t_m`
  channel and therefore omits light-travel-time delay in the visual shader;
- the display convention chooses and documents whether observed intensity is
  weighted by `g^3` or `g^4`, and tests the selected convention on a simple
  disk pattern before visual mode is accepted.

Current CPU transfer v2 target:

- HDF5 schema `gr-bh-xr.task6.thin_disk_transfer.v2` records
  `disk_r_m`, `disk_phi_m`, `disk_t_m`, and `disk_g_m` with shape
  `(max_order, grid, grid)`;
- `m` is the true zero-based equatorial crossing order before disk-annulus
  filtering, so a ray whose first equatorial crossing falls inside ISCO and
  second crossing hits the emitting annulus is stored in the `m = 1` layer;
- `r_in = r_ISCO(a)` follows `bardeen1972rotatingBlackHoles`;
- Keplerian redshift `g = E / (u^t (E - Omega L_z))` is stored for each valid
  disk crossing and follows `cunningham1975kerrDiskSpectrum`;
- Schwarzschild checks include `r_ISCO = 6M` and `g(L_z=0) = sqrt(1 - 3M/r)`;
- the first Luminet-style diagnostic is an equal-radius transfer plot that
  separates direct (`m = 0`) and secondary (`m = 1`) Schwarzschild disk images;
- the first Unity disk integration is an audit mode, not a beauty shader:
  full-sky disk-transfer cubemaps store `(r_m, sin(phi_m), cos(phi_m), g_m)` as
  `RGBAHalf` for the first two true equatorial crossing orders, and the shader
  displays `g_m` false color plus equal-`r_m` bands;
- emission profile, observed intensity, optical depth, and visual disk
  animation remain deferred until the disk audit mode can be compared against
  CPU Luminet-style transfer plots.

Current GPU transfer v3 comparison target:

- CPU and GPU disk-transfer validation must use matched `grid`, screen bounds,
  observer radius, horizon cutoff, disk annulus, and crossing order. The formal
  Schwarzschild gate uses an even grid, such as `64x64`, with
  `alpha,beta in [-30M, 30M]` and `r_obs = 100M` to avoid exact `alpha = 0`
  axis samples.
- Stable-region comparison excludes CPU/GPU failures, critical-band pixels,
  near-capture pixels, and a documented disk-annulus edge band.
- Required stable-region metrics for matched finite disk hits:

```text
validity mismatch count = 0 outside exclusions
max |Delta r_m| < 1e-2 M
max |Delta g_m| < 1e-3
max phi_m angular error < 1e-3 rad
Delta t_m is recorded and reported; its tighter threshold is set after display-scale runs
```

- A sign-change crossing detector can miss a measure-zero tangential double
  crossing when a theta turning point lies exactly on the equatorial plane.
  CPU and GPU currently share this limitation; it must be revisited before
  using such edge cases for claims.
- The current Unity disk visual emissivity `pow(saturate(6/r), 2.2)` is a
  documented fallback proxy only. When `disk_color_lut_rgba32f.bytes` and
  `disk_radial_lut_rgba32f.bytes` are bound, the Unity disk visual path must
  use the Page-Thorne radial LUT and blackbody color LUT: baseline brightness is
  `F_norm g^4`, and color is sampled by `log(T_obs)` with
  `T_obs = g T_scale F_norm^(1/4)`.
- The CPU Page-Thorne/color seed in `src/gr_bh_xr/disk_spectrum.py` validates
  the Schwarzschild circular-orbit anchor `E(r=6M)=sqrt(8/9)`,
  `L_z(r=6M)=sqrt(12)`, enforces zero torque at `r_ISCO`, checks positive flux
  outside the ISCO for Schwarzschild and Kerr, and verifies blackbody
  chromaticity against the expected D65-like Planckian locus near `6504K`.
  The Page-Thorne numerical integral is independently checked against the
  nonzero-spin root/log closed form based on `x^3 - 3x + 2a = 0`; the current
  `a = 0.9` gate matches to relative `3e-6`. The near-extremal
  `a = 0.998` ISCO efficiency anchor is `1-E_ISCO = 0.320994`.
  A separate `M = 2`, `a/M = 0.9` regression requires the closed form to scale
  as `M^-2`, matching the numerical integral's physical flux dimension.
  Redshift application tests enforce `T_obs = g T_emit`, `g^3` specific
  intensity weighting, `g^4` bolometric weighting, and a reproducible
  `.npz` blackbody LUT with monotonic temperature samples and finite
  max-normalized linear-sRGB colors.
  Unity raw-asset tests additionally require RGBA32F color/radial LUT byte
  counts, JSON metadata, log-temperature indexing, linear-radius indexing, and
  `T_shape^4 = F_norm` for positive Page-Thorne samples.
- Disk color LUT schema `gr-bh-xr.task6.disk_color_lut.v2` adds the inverse
  Planck locus to the previously unused alpha channel. The inversion is a
  project chromaticity heuristic (a red-to-blue ratio match), not a
  literature-derived spectral fit; see `docs/equations.md`. Required checks in
  `tests/test_disk_spectrum.py`:
  - the forward chromaticity coordinate `u = R / (R + B)` is bounded in
    `[0, 1]`, equals `1` at the cold end where the clipped sRGB blue channel is
    zero, and is *not* globally monotone - the sub-plateau is the reason a raw
    inversion is invalid;
  - `blackbody_locus_inverse` drops the plateau rows (recorded as
    `plateauRowsDropped`; `44` of `256` rows for the default `1000-40000 K`
    range), raises when fewer than two rows survive or when the remainder is
    not strictly monotone, and returns a non-increasing table in `[0, 1]`. The
    fail-closed case is reachable from the CLI (`--temperature-max-k 1800`) and
    is tested;
  - the chromaticity -> alpha -> temperature round trip, evaluated through an
    emulated bilinear texture fetch with clamp addressing, recovers the
    emitting temperature within a `1e-3` regression bound over
    `2500-25000 K`. Measured worst case on that five-point set is `2.52e-4`
    (at `25000 K`), so the gate keeps about `4x` headroom. The loose `3%`
    per-point tolerance is retained as the user-facing bound;
  - boundary behavior is pinned separately because the mid-range is the
    easy region: the hot end `40000 K` recovers to `39652.60 K`
    (rel `8.68e-3`, the dense worst case over `2500-40000 K`; the locus
    flattens by `17x` in `du/dlnT` toward `40000 K`), and the cold end
    *saturates by design* - `1000 K` and `1500 K` both return `1933.06 K`,
    about `1.6` LUT texels above the `1889.88 K` anchor row. The inverse can
    never return `temperatureMinK`; the reachable floor is published as
    `alphaAnchorTemperatureK`;
  - `alpha` is the dimensionless log-normalized temperature
    `s = log(T / T_min) / log(T_max / T_min)`, so `T = T_min (T_max/T_min)^a`.
    Because the same LUT is used forward and backward, the ratio form is an
    identity at `g = 1` in exact arithmetic, so a fit error cannot change an
    unshifted source color. That identity is subject to the consumer's own
    division guard, which is Task 9-10 territory and not gated here.
- Both Unity LUT metadata files must be dimensionally self-describing, and the
  claims must be numerically true rather than asserted by string. The metadata
  carries a `units` block naming the unit of every numeric field and a
  `sampling` block giving the row-to-physical-value map, the exact texture
  coordinate including the `(samples - 1)` endpoint convention, the addressing
  and filtering modes, and an explicit note where the current consumer differs.
  Specifically:
  - `fluxPeakShape` is **not** dimensionless. It carries geometric dimension
    `length^-2` and scales as `M^-2` at fixed `r/M`; the omitted
    `Mdot / (4 pi)` factor is itself dimensionless in `G = c = 1`, so dropping
    it cannot remove that dimension. Measured `peak * M^2 = 4.260486e-3` for
    `M = 1, 2, 10` at `a/M = 0.9`, `r_max/M = 30`. This is gated numerically by
    `test_page_thorne_flux_peak_shape_scales_as_inverse_mass_squared`, which
    ties the asset metadata to the existing closed-form `M^-2` scaling test.
    The texture *channels* `F/max(F)` and `[F/max(F)]^(1/4)` are dimensionless;
    only the normalization constant is not;
  - `rMin`, `rMax`, `rISCO`, `M` and `a` are geometric code lengths, equal to
    `r/M` only when `M = 1`. `a` is `J/M`, not the dimensionless spin, even
    though the CLI flag is named `--spin`; `aOverM` and `rIscoOverM` are
    published so the dimensionless values are machine-readable;
  - the producer contract is that the documented exact coordinate
    `u = (s * (samples - 1) + 0.5) / samples` returns its own row under
    bilinear/clamp fetch, and this is tested directly. The current Unity
    consumer instead samples with `u = s`, a half-texel offset worth `0.72%`
    in effective temperature (`0.0021` per linear sRGB channel) at
    `samples = 256`, and `0.027 M` in radius (`0.048` in normalized flux on
    the steep inner rise) at `samples = 512`. This producer does not own the
    shader; the mismatch is recorded in the emitted metadata so the Unity
    worktree can reconcile it, and it is deliberately not asserted away here.
    The alpha channel needs no such correction because it is resampled at
    texel centers, so the consumer's `u` is already correct.

## Phase 5 MR Overlay

Required checks:

- MR-1 claims only compositing, not true camera-pixel lensing;
- Depth API or equivalent occlusion is visually checked;
- parameters shown in the UI map to documented physical quantities;
- limitations of passthrough pixel access are recorded before any lensing claim.

## Tier 2 Near-Horizon Kerr-Schild Roaming

Tier 2 near-horizon roaming is not headset-rate per-frame geodesic integration.
The accepted architecture is a precomputed observer worldline with transfer-map
keyframes sampled along observer proper time, then Unity/Quest interpolation and
playback. Head rotation remains a cubemap lookup; observer position follows the
validated worldline. Six-degree-of-freedom free flight remains Tier 2.5+ and
requires a realtime tracer or audited surrogate.

Stage A CPU Kerr-Schild reference checks:

- `src/gr_bh_xr/metric_ks.py` must keep covariant/inverse metric consistency,
  Schwarzschild limit, finite outer-horizon behavior, and analytic derivative
  agreement with finite differences under test.
- `src/gr_bh_xr/geodesic_ks.py` must use the Hamiltonian form with Cartesian
  Kerr-Schild inverse metric derivatives and record horizon crossing, escape,
  and equatorial disk crossings without Boyer-Lindquist horizon/axis failures.
  Carter-constant diagnostics must convert KS states to BL only in the safe
  exterior and report skipped samples rather than forcing a singular conversion.
- Captured rays should be continued inside the outer horizon only far enough to
  prove horizon penetration. For near-extremal spins, the numerical capture
  surface must remain outside the Cauchy horizon, e.g. by using
  `max(r_- + margin, r_+ - eps)`.
- Exterior-domain BL-vs-KS cross-validation must compare event class,
  asymptotic escape direction, disk crossing fields, and Hamiltonian residuals.
  A first representative Kerr escaped-ray direction gate is in place; dense
  full-sky sampling remains required before transfer-map keyframe claims.
- `python -m gr_bh_xr.validate_ks_bl_crosscheck` records the current exterior
  fan gate. The reviewed `a = 0.9`, `i = 60 deg` and `i = 90 deg`,
  `alpha in [-8M, 8M]`, `beta = 0`, `55`-ray fans have
  `both_valid_event_mismatches = 0` and maximum escaped-direction error about
  `2.1e-8 rad`, which is the double-precision `acos` resolution floor. The
  `beta = +4` / `beta = -4` fans also require `both_valid_event_mismatches = 0`
  and `ks_invalid_bl_valid = 0`; any `bl_invalid_ks_valid` rays are recorded as
  BL coordinate-pathology improvements only when KS Hamiltonian residuals remain
  bounded.
- `python -m gr_bh_xr.validate_ks_disk_transfer` records the KS-vs-BL thin-disk
  transfer gate. The formal `64x64` even grid should use matched screen bounds,
  observer radius, horizon cutoff, disk annulus, and crossing order; accepted
  output has `disk_validity_mismatch_count = 0` and reports `Delta r_m`,
  wrapped `Delta phi_m`, `Delta t_m`, and `Delta g_m` error fields.
- Kerr critical-curve regression must recover the existing `a = 0.9`,
  `i = 60 deg` center and error thresholds before any near-horizon visual claim.
  The current KS gate records `center alpha = 0.9359348514M`,
  `max_abs_error = 0.0027052051M`, `rms_error = 0.0004011217M`, and
  `invalid = 0`.
- Conserved quantities `E`, `L_z`, exterior Carter `Q`, and Hamiltonian
  residuals must be reported through and across the outer horizon; bounded
  residuals near `r_+` are the direct evidence that the horizon-penetrating
  coordinates are doing
  useful work.

Task 2 WGSL Kerr-Schild checks:

- `src/gr_bh_xr/gpu/trace_ks.py` validates the Cartesian Kerr-Schild
  Hamiltonian RHS and fixed-step RK4 kernel in f32 WGPU while receiving
  explicit CPU-initialized KS canonical states. This gate isolates GPU
  metric/RHS correctness from camera-initialization work.
- `python -m gr_bh_xr.gpu.validate_ks` must compare CPU f64 KS traces against
  GPU f32 KS traces on both screen-coordinate fans and deterministic full-sky
  directions. Both-side max-lambda unclassified samples must be counted
  separately from resolved samples. Resolved/stable-event agreement must be at
  least `98%`, GPU failures outside CPU-invalid / near-capture exclusions must
  be `0`, and escaped-ray momentum-direction errors must be reported by
  `min_r` band.
- GPU KS Hamiltonian residuals are grouped by `min_r` band. Exterior samples
  are expected to be far tighter than near-horizon or horizon-crossing samples;
  horizon-crossing f32 residuals are diagnostic evidence for the fixed-step
  kernel, not a replacement for the CPU f64 exterior `1e-8` target.
- The current `a = 0.9`, `i = 60 deg`, `max_lambda = 800M` adaptive-step gate
  records `sample_count = 677`, `both_unclassified_max_lambda = 0`,
  `resolved_event_agreement = 1.0`, `stable_event_agreement = 1.0`,
  `gpu_failure_outside_exclusions = 0`, and a weak-outer escaped-direction
  median/max of `1.15e-6` and `7.49e-5 rad`. The gate uses
  `h = h0 * max(1, r / r_ref)` with `h0 = 0.01M` and `r_ref = 5M` so weak-field
  rays are accelerated while the photon-shell band keeps the strong-field
  step floor. A photon-shell proxy band
  `r_+ + max(0.1M, 2 horizon_eps) < min_r <= 5.5M` is reported separately; in
  the current run it has `50` escaped-direction samples, median `7.55e-5 rad`,
  max `9.66e-3 rad`, and GPU `max |H| = 6.07e-6`.
- Post-review step-size scans showed that the `photon_shell_proxy` direction
  tail is f32 roundoff random walk amplified by the photon-shell Lyapunov
  instability, not a monotonic truncation-error limit: fixed `h = 0.001`
  reached shell-band max error `3.42e-1 rad`, `h = 0.005` with floor
  `1.82e-2 rad`, current `h = 0.01` with floor `9.66e-3 rad`, and the
  previous no-floor shell step `h ~= 0.024` `1.83e-3 rad`. Therefore
  `photon_shell_proxy` remains a recorded diagnostic band rather than a hard
  f32 direction threshold. Offline keyframe generation should CPU-f64 retrace
  texels near the analytic critical curve, while realtime paths must document
  the expected `~1e-3` to `~1e-2 rad` photon-ring direction noise.
- `python -m gr_bh_xr.gpu.validate_ks_near_horizon` records the dedicated
  low-observer-radius Task 2 gate. The current `a = 0.9`, `i = 60 deg`,
  `r_obs = 10M, 5M, 3M`, `256`-direction runs use `r_escape = 200M` and report
  minimum resolved/stable event agreement `1.0`, total both-side
  max-lambda-unclassified samples `0`, total GPU failures outside exclusions
  `0`, and `10` near-horizon-exterior escaped-direction samples. Median/max
  escaped-direction errors are `7.52e-7/1.23e-5 rad` at `10M`,
  `1.23e-6/1.02e-4 rad` at `5M`, and `2.57e-6/4.56e-5 rad` at `3M`.
- This Task 2 shader does not yet implement arbitrary observer worldlines,
  finite-distance object intersections, or headset-rate near-horizon free
  flight.

Task 3 finite-distance object checks:

- `src/gr_bh_xr/geodesic_ks.py` may trace a spherical finite-distance target
  in Cartesian Kerr-Schild coordinates. The CPU reference detects the
  closest-approach event, verifies whether the closest point is inside the
  target, and bisects dense output back to the first surface hit. This avoids
  missing a finite sphere when a DOP853 step enters and exits the target before
  the next accepted endpoint. The object-hit event records the hit affine
  parameter, hit position, canonical `p_t`, and static-object redshift when the
  static worldline is physically allowed.
- Static finite-distance object redshift uses
  `g = E / (-p_mu u_static^mu)` with `u_static^t = 1 / sqrt(-g_tt)`. If
  `g_tt >= 0`, the static worldline is inside the ergoregion and the helper
  must return `NaN`; callers must not silently render such an object as a
  static emitter. This value is normalized to an observer at infinity; a
  near-horizon observer must include its own `-p_mu u_obs^mu` factor.
- The current CPU seed is validated by a Schwarzschild straight-through
  sphere-hit regression that recovers the front-surface intersection and
  `sqrt(1 - 2M/r_hit)` static redshift. It is not yet the finite-distance
  weak-field lens-equation gate.
- `python -m gr_bh_xr.validate_ks_finite_lens` records the weak-field
  finite-distance lensing anchor. It uses Schneider, Ehlers, and Falco's
  standard point-lens Einstein angle
  `theta_E^2 = 4M D_LS / (D_L D_S)` as the first-order scale and Keeton &
  Petters' Schwarzschild second-order bending coefficient
  `alpha_hat = 4M / b + 15 pi M^2 / (4 b^2)` to interpret the leading
  percent-level offset. The current `D_L = 10000M`, `D_LS = 5000M`,
  target-radius `5M`, `81`-sample run gives
  `theta_E = 0.0115470054 rad`, refined hit-band center
  `0.0116959935 rad`, first-order relative offset `1.290e-2`, second-order
  prediction `0.0116942675 rad`, and second-order residual `1.49e-4`.
  A scaled `D_L = 40000M`, `D_LS = 20000M` run gives first-order offset
  `6.414e-3`, second-order prediction offset `6.377e-3`, and second-order
  residual `3.73e-5`.
- Formal Task 3 GPU acceptance remains pending: add a WGSL sphere-intersection
  path and CPU/GPU comparison. The nearer `D_L = 200M`, `D_LS = 100M`
  configuration is treated as a finite-distance demo configuration rather than
  a strict first-order weak-field pass/fail gate.
- `python -m gr_bh_xr.gpu.validate_ks_finite_object` records the first WGSL
  finite-sphere intersection comparison. The WGSL path checks the closest point
  on each RK4 segment rather than only the step endpoint, matching the CPU
  closest-approach semantics at validation scale. The current `D_L = 1000M`,
  `D_LS = 500M`, target-radius `10M`, `81`-sample run has CPU and GPU event
  counts `object_hit = 35`, `escape = 46`; total event mismatch `0`;
  stable-event mismatch `0`; stable-event agreement `1.0`; GPU failures `0`.
  The object edge band remains reported separately for future configurations
  where f32 segment detection and CPU dense-output surface refinement may
  still differ at the finite target limb.

Task 4 frustum realtime benchmark:

- `python -m gr_bh_xr.gpu.benchmark_latency --mode ks-frustum` records the
  first KS frustum-only latency decision table. It measures WGPU dispatch,
  readback, and event summaries for explicit KS initial states; it excludes
  Python finite-observer initial-state construction and Unity texture upload.
  The current KS shader has sphere-target support but does not yet implement
  disk crossings, so `disk_crossings_enabled = false` is recorded.
- The decision rule is single-eye median `< 11 ms` before claiming low-resolution
  90 Hz realtime tracing. Current `a = 0.9`, `i = 60 deg`, `100 deg` FOV,
  `h0 = 0.01M`, `r_escape = 200M`, `max_lambda = 800M` results:

```text
grid   r_obs values         median ms range       best Hz range       90 Hz claim
128    20,10,5,3,2M         17.3 - 22.4           44.6 - 57.9         no
256    20,10,5,3,2M         67.9 - 79.6           12.6 - 14.7         no
512    20,10,5,3,2M         266.1 - 301.6         3.3 - 3.8           no
```

- Interpretation: the present f32 KS kernel is useful for offline/interactive
  transfer updates and for keyframe generation evidence, but the measured
  frustum cost does not justify headset-rate near-horizon free-flight claims.
  The next realtime path should be keyframe playback, foveated/lower-resolution
  tracing, or an audited surrogate rather than full-frustum per-frame tracing.

Stage B observer checks:

- Observer worldlines must state their domain: static/ZAMO-like, circular,
  radial free fall, or explicitly accelerated craft.
- The first ZAMO / LNRF tetrad gate must validate
  `omega = -g_tphi / g_phiphi = 2 M a r / A`, the lapse
  `alpha = sqrt(Sigma Delta / A)`, tetrad orthonormality, far-field convergence
  to the static-observer tetrad, and static-frame failure inside the
  ergoregion where the ZAMO frame remains defined outside `r_+`.
- The ZAMO near-horizon probe records `omega -> Omega_H` and
  `alpha proportional to sqrt(r-r_+)` as exterior BL-coordinate behavior. It is
  not a formal horizon-crossing gate because the BL ZAMO helper remains
  exterior-only.
- The exterior BL ZAMO tetrad may be pushed into the Cartesian Kerr-Schild
  chart by the BL-to-KS Jacobian and must remain orthonormal under the
  Kerr-Schild metric. This validates the chart bridge only; transported
  worldline tetrads remain a later Stage B gate.
- Camera tetrads must be transported along the worldline, with orthonormality
  drift recorded.
- Large-radius/low-speed tetrad launch must reduce to the existing static
  observer mapping plus the special-relativistic aberration limit.
- Redshift must use the observer four-velocity, not the static-observer value.
- The first transported-worldline seed is the Schwarzschild radial free-fall
  observer from rest at infinity. Its gate requires: boosted initial
  `e_time = u`, parallel-transported Gram matrices remain close to
  `diag(-1,1,1,1)`, transported `e_time` stays equal to the geodesic
  four-velocity, and BL radial velocity satisfies
  `dr/dtau = -sqrt(2M/r)` along the sampled path. This seed is a transport
  validation anchor, not yet the full Kerr near-horizon camera model.

Stage B rain-observer gate (Kerr free-fall camera through the outer horizon):

The rain frame is the Doran (`doran2000newKerrForm`) free-fall congruence -
`E = 1`, `L = 0`, `Q = 0`, released from rest at infinity - expressed in
Cartesian ingoing Kerr-Schild coordinates. It is the first observer frame in
this project that is defined on both sides of `r_+`, which is exactly what the
horizon-crossing descent path needs, because the static frame already fails at
the ergosurface and the BL ZAMO helper is exterior-only.

The four defining conditions are **consistent, not overdetermined**: with
`E = 1` and `L = 0` the Carter polar potential reduces to `Theta = Q`
identically, independent of `theta`, so `Q = 0` makes `dtheta/dtau = 0` an
exact solution at every polar angle.

The committed producer is `python -m gr_bh_xr.validate_rain_observer`
(schema `gr-bh-xr.task8.rain_observer_gate.v1`). It samples a deterministic
grid - no RNG - over `a/M in {0, 0.5, 0.9, 0.998}`, `theta in {0.4, 1.0,
pi/2, 2.0, 2.7} rad`, exterior radii `{60, 20, 6, 3}M` and horizon offsets
`{0.1, 0.01, 1e-3}M` on both sides, and **fails closed**: a zone with zero
samples raises rather than reporting a vacuous `max()` over an empty set.
Current run: 100 exterior, 60 at-horizon, 35 interior, 6 exact-horizon and 5
Schwarzschild-limit samples.

Committed thresholds and the measured worst case behind each:

```text
check                              threshold   measured    headroom
|u.u + 1|          outside          1e-13      1.11e-15      90x
|u.u + 1|          at r_+ +/- 1e-3  1e-13      2.11e-15      47x
|u.u + 1|          inside r_+       1e-12      9.99e-16    1000x
|u_t + 1|                           1e-13      1.55e-15      64x
|L_z|  (r <= 60M)                   1e-13      2.44e-15      41x
|dtheta/dtau|                       1e-11      4.85e-16       2e4x
Gram max|G - diag(-1,1,1,1)| out    1e-13      1.11e-15      90x
Gram, at r_+ +/- 1e-3               1e-13      2.11e-15      47x
Gram, inside r_+                    1e-12      9.99e-16    1000x
|u - u_analytic|_inf                1e-13      3.36e-15      30x
Schwarzschild |u^r + sqrt(2M/r)|    1e-13      6.66e-16     150x
|u.u + 1| EXACTLY at r = r_+        1e-13      8.88e-16     113x
```

Required properties of this gate:

- **Compare against an independent closed form, not only residuals.** All four
  constraint residuals can be satisfied by the wrong root branch, so the gate
  includes `|u - u_analytic|_inf` against `analytic_kerr_rain_velocity_ks`,
  whose expressions are rationalized to stay regular at `Delta = 0`.
- **Exactly `r = r_+` is a dedicated regression.** The outgoing rain branch
  diverges as `Delta -> 0` in the ingoing chart, which drives the normalization
  quadratic's leading coefficient to zero on the horizon. A naive
  `(-b -/+ sqrt(disc)) / (2a)` evaluation cancels catastrophically there and
  returns an `O(1)`-wrong velocity or finds no root at all; the Vieta-stable
  form keeps full precision. This is the single highest-value check in the set.
- **`L_z` is dimensionful and grows like `r`**, so the gate states the
  `r <= 60M` domain rather than pretending to a scale-free number.
- **The symmetry axis is excluded by construction, and that exclusion is
  explicit.** The constraint matrix loses rank on the axis (both the axial
  Killing row and the polar row vanish identically) and its condition number
  grows like `6/theta`, so the velocity error scales as `2e-16/theta`.
  `kerr_rain_velocity_ks` raises below `sin(theta) = 1e-6` rather than
  returning a degraded frame. This matters because a mis-oriented `e_theta`
  still orthonormalizes perfectly - an orthonormality gate can never detect it,
  which is why `sin(theta)` is computed exactly as `rho / r` rather than
  through a floored `sqrt(max(1 - cos^2, eps))`.
- **Do not gate the worldline sampler against requested radii.** The
  Schwarzschild limit must be evaluated at an exact radius, or against
  `ks_radius(recorded_sample)`. Comparing against the *requested* target
  measures the step controller, not the physics: the earlier sampler recorded
  radii up to `8.8e-7 M` off target, which propagated into an apparent
  `1e-10`-class error floor in `dr/dtau` that has nothing to do with the
  algebraic solve (that solve is machine-exact, `6.66e-16`). The sampler now
  bisects onto the requested radius, landing within `4.8e-13`.
- Interior samples stay above the inner horizon; the mass-inflation region is
  out of scope.

Not yet claimed: the rain tetrad is built algebraically at each point, not
parallel transported along the worldline, so consecutive samples differ from a
transported frame by a rotation this gate does not record. The transported-frame
requirement above is still open for this frame.

Task 8 rain-frame descent keyframe checks:

Full details and measured numbers are in
`validation/descent_keyframes/README.md`. The committed producer is
`python -m gr_bh_xr.gpu.validate_descent_frames` (schema
`gr-bh-xr.task8.descent_frame_validation.v1`), which is deterministic
(Fibonacci-sphere directions, deterministic worldline integrator, no RNG) and
fails closed: it raises rather than reporting a statistic if fewer than 256
rays survive, if any direction is non-finite, or if more than `35%` of escaping
rays are excluded by Hamiltonian residual.

- Ray validity is decided by the Hamiltonian residual `h_max_abs`, which is
  identically zero for a null geodesic. This is observer-radius and spin
  independent, and it replaces two defective geometric heuristics:
  - exterior `min_r < r_+ + 0.05` was applied regardless of the observer's own
    radius, so any exterior keyframe with `r_obs < r_+ + 0.05` had every ray
    reclassified as dark. The default schedule hits this - index 14 of a
    20-keyframe `9M -> 0.75M` descent at `a/M = 0.9` lands at `r = 1.4423`,
    exterior but only `0.0064` above `r_+` - and that keyframe rendered
    COMPLETELY BLACK with no error and a printed `escape=0`;
  - interior `lambda_end > 0.6 max_lambda` was about `10x` under-inclusive,
    admitting 644-799 texels per interior keyframe with `h_max_abs` up to
    `1.7e10`.
  On healthy exterior keyframes the two criteria agree set-for-set on all 4096
  sampled texels. Measured escape fraction across a full descent now runs
  `0.986` at `9M` to `0.801` at `0.75M` with no discontinuity, and the
  previously black keyframe keeps `0.847`.
- The generator fails closed on a blank keyframe (`min_escape_fraction`,
  default `0.25`) and requires exactly one worldline position per requested
  radius.
- Chart-direction agreement between the batched extraction and the exact
  per-ray conversion is gated at TWO escape radii, because a single far-radius
  threshold cannot discriminate. At `r_escape = 200M` the analytic azimuth
  correction is about `1.3e-3 deg`, larger than the measured agreement itself,
  so a threshold there passes whether the rotation is correct, absent, or
  sign-flipped - which is how a sign error survived. Measured:

```text
r_escape = 200M : max 3.251e-4 deg, median 2.180e-4 deg
   no rotation  : max 1.333e-3 deg, median 1.165e-3 deg
r_escape =  20M : max 7.543e-2 deg, median 2.709e-2 deg
   no rotation  : max 1.587e-1 deg, median 1.261e-1 deg
```

  The gate additionally asserts `rotationIsImprovement` - applying the rotation
  must beat not applying it - which is dimensionless and self-calibrating. The
  correction is `+delta` with `delta = atan2(a, r) + shift(r)`: the
  momentum-direction azimuth offset is `+aM/r^2` while `delta` is `-aM/r^2`, so
  rotating by `-delta` is worse than doing nothing at every radius tested.
- The float32 observer-factor threshold is `4 ULP = 4.8e-7`, NOT `1e-7`.
  `E_inf` spans `[0.095, 1.905]` over this direction set, so the smallest
  representable nonzero float32 difference near `E ~ 1` is `2^-23 = 1.192e-7`:
  **a threshold below one ULP is unachievable in principle**, and the measured
  value `1.196e-7` is exactly that floor. The float64 path measures `6.66e-16`
  against a `1e-14` gate. An earlier manifest claimed `2.7e-8`; that figure is
  arithmetically impossible for a float32 max-abs over this range and was never
  computed by any committed code, and the archived `5.96e-8` is `2^-24`,
  consistent with a float64-vs-float32 comparison rather than the stated one.
  Neither is used as a gate.
- The observer-factor check is a packing identity, not an integrator test:
  `rk4_step_ks` carries `p_t` through unmodified. Its discriminating power comes
  from two negative controls that must fail by more than `0.1` - a permuted leg
  order (`1.575`) and the sign form that appeared in the original prose
  (`1.812`). The launcher's null residual `g(q, q)` measures `3.00e-15`.
- Kerr-Schild disk-crossing recording requires `disk_r_in` to clear `r_+` by
  `0.25 M`, because the Boyer-Lindquist azimuth and time shifts used to report
  a crossing diverge logarithmically there and would emit a large finite
  garbage value rather than fail.
- The WGSL stride constants are substituted from the Python constants and
  pinned by a test: the readback buffer is sized in Python while the shader
  writes at the WGSL stride, so a desync would silently offset every field.

Not yet claimed for the descent path: the tetrad is algebraic at each point
rather than parallel transported, so `azimuthDeg` records a rotation of the
observer position and not of the frame; disk edges carry no sub-texel coverage;
and `disk_phi_m` from the KS tracer is wrapped-then-offset rather than the
unwrapped integrated azimuth the Boyer-Lindquist tracer stores.

Task 9 Unity live-tracer observer-frame gate:

- The Unity validation dump and the Python GPU comparator share the dumped
  observer frame when constructing launch states. Event and direction agreement
  therefore cannot validate that frame; a common frame error cancels exactly.
- Before tracing, `compare_live_tracer.py` must independently reconstruct the
  runtime binary32 metric/station inputs, BL-to-KS observer position, and the
  accepted static or rain KS tetrad. Position and every tetrad leg are compared
  at `1e-9` relative/absolute scale.
- Rain dumps additionally require agreement with the independent Doran
  four-velocity, `dr/dtau < 0`, and future-pointing branch selection.
- All dumps require positive orientation for increasing radius, increasing
  polar angle, and prograde azimuth. Gram orthonormality remains a separate
  invariant but is never sufficient by itself because leg flips and spatial
  rotations preserve it.
- The comparison summary must persist the complete `observerFrame` evidence;
  a dump that predates this metadata/gate contract cannot support a Task 9
  scientific pass.

## Phase 6 Simplified GRRT

Required checks:

- invariant intensity equation is tested on a simple analytic case;
- emission and absorption units/conventions are documented;
- at least one comparison path is recorded against RAPTOR, Odyssey, ipole,
  grtrans, or an analytic limit;
- polarization is explicitly deferred unless Stokes transport is implemented
  and validated.

## Phase 7 GRMHD Snapshot Cache

Required checks:

- input snapshot fields are listed and units are documented;
- interpolation method is documented;
- cache format records enough metadata to reproduce image generation;
- Quest playback/query mode is separated from offline GRRT generation.

## Long-Range BBH Track

Required checks:

- BBH visual toy is labeled as approximate and non-Einstein-solution;
- time-dependent vacuum lensing uses a documented metric source;
- single-Kerr static transfer maps are not reused as physical evidence for
  BBH, multi-black-hole, or gravitational-wave lensing; those systems need
  time-dependent transfer maps, offline/cache playback, adaptive tracing, or
  validated surrogates tied to the chosen metric;
- toy accretion is not represented as full GRMHD;
- full BBH + GRMHD + GRRT is treated as offline/cache/surrogate work.

Static single-Kerr playback is not a sufficient architecture for this track.
Long-range real-time or interactive work must introduce one of:

- adaptive GPU tracing with progressive/tiled updates;
- time-indexed transfer-map cache playback tied to a documented metric;
- reduced-order or neural surrogates trained on exact transfer-buffer data;
- hybrid modes that keep audit buffers for escape/capture, redshift, time
  delay, and image order rather than directly generating RGB output.

Neural acceleration must learn transfer functions or radiance fields from
validated exact data. It must not replace the audit buffers with an untraceable
image generator.
