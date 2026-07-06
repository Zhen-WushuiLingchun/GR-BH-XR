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
- GPU HDF5 output uses schema `gr-bh-xr.phase2.gpu_lens_map.v2` and records
  `alpha`, `beta`, `gpu_event_code`, `gpu_failure_code`, `gpu_min_r`,
  `gpu_h_max_abs`, `gpu_q_drift_abs`, `gpu_steps`, `event_rgba8`, and
  `debug_rgba8`;
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
- the exporter is tested on synthetic HDF5 input and a weak-deflection GPU map
  so byte sizes, valid masks, basis mapping, and vertical handedness cannot
  silently flip or mirror.

Required checks:

- stereo disparity is correct;
- lens map remains stable under head motion;
- 72 Hz or 90 Hz target feasibility is recorded;
- black-hole angular size and scale are documented;
- PC-to-Quest latency is recorded or qualitatively evaluated.

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

Current CPU transfer v1 target:

- HDF5 schema `gr-bh-xr.task6.thin_disk_transfer.v1` records
  `disk_r_m`, `disk_phi_m`, `disk_t_m`, and `disk_g_m` with shape
  `(max_order, grid, grid)`;
- `r_in = r_ISCO(a)` follows `bardeen1972rotatingBlackHoles`;
- Keplerian redshift `g = E / (u^t (E - Omega L_z))` is stored for each valid
  disk crossing and follows `cunningham1975kerrDiskSpectrum`;
- Schwarzschild checks include `r_ISCO = 6M` and `g(L_z=0) = sqrt(1 - 3M/r)`;
- emission profile, observed intensity, optical depth, and GPU/Unity texture
  integration remain deferred until the CPU transfer buffers pass review.

## Phase 5 MR Overlay

Required checks:

- MR-1 claims only compositing, not true camera-pixel lensing;
- Depth API or equivalent occlusion is visually checked;
- parameters shown in the UI map to documented physical quantities;
- limitations of passthrough pixel access are recorded before any lensing claim.

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
- toy accretion is not represented as full GRMHD;
- full BBH + GRMHD + GRRT is treated as offline/cache/surrogate work.
