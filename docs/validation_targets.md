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
- the Unity shader includes single-pass instanced stereo macros so Quest/OpenXR
  does not render a missing or eye-shifted lens map in one eye;
- the angular-window yaw test is interpreted only as head-rotation anchoring
  for a fixed distant observer. It is not accepted as evidence for changing the
  physical Kerr observer inclination or orbiting around the black hole;
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
  `(r_m, sin(phi_m), cos(phi_m), g_m)` for a stationary-axisymmetric lookup,
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
  documented visual proxy only. A physically stronger disk visual mode must add
  a Page-Thorne-style relativistic thin-disk flux model with its source indexed
  in `references/` before replacing the proxy in claims.

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
  max `9.66e-3 rad`, and GPU `max |H| = 6.07e-6`. The near-horizon exterior
  direction-error band currently has only `3` samples, so Task 4 still requires
  a dedicated low-`r_obs` near-horizon fan before realtime claims.
- This Task 2 shader does not yet implement arbitrary observer worldlines,
  finite-distance object intersections, or headset-rate near-horizon free
  flight.

Stage B observer checks:

- Observer worldlines must state their domain: static/ZAMO-like, circular,
  radial free fall, or explicitly accelerated craft.
- Camera tetrads must be transported along the worldline, with orthonormality
  drift recorded.
- Large-radius/low-speed tetrad launch must reduce to the existing static
  observer mapping plus the special-relativistic aberration limit.
- Redshift must use the observer four-velocity, not the static-observer value.

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
