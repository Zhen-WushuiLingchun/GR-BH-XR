# Development Log

Use this log to keep academic and physics-facing context close to the code.
For large entries, create a separate `docs/YYYY-MM-DD-topic.md` note and link it
from here.

## Entry Template

### YYYY-MM-DD - Short title

- Goal:
- Changed files / components:
- Academic reason:
- Physical correspondence:
- Assumptions and conventions:
- Validation:
- References:
- Open issues / next steps:

## Log

### 2026-07-06 - Task 5 Unity static texture bridge

- Goal: Start Task 5 with a Unity/OpenXR-facing static texture bridge and lock
  the coordinate convention before headset work.
- Changed files / components: `src/gr_bh_xr/xr/export_unity_textures.py`,
  `xr/unity_frontend/`, `tests/test_xr_export.py`, `tests/test_sky.py`,
  `validation/quest_pcvr/README.md`, and validation documentation.
- Academic reason: The PCVR renderer must consume auditable transfer buffers
  rather than an ambiguous RGB-only image. The coordinate convention is part of
  the physics contract because a silent mirror or vertical flip would make a
  visually plausible but physically wrong lens map.
- Physical correspondence: The exporter preserves the HDF5 screen order
  `x -> alpha`, `y -> beta`, maps `UV(0,0)` to `(alpha_min, beta_min)`, and
  stores both BH-Cartesian and Unity-space escape direction textures. BH axes
  use `+Z_BH` as the Kerr spin axis and the observer at `phi = 0`,
  `theta = inclination_deg`. Unity `+Z` points from the camera to the black
  hole, Unity `+Y` is the projected spin axis, and Unity `+X` is positive
  `alpha`.
- Assumptions and conventions: Unity consumes raw `.bytes` textures:
  `event_rgba8` as `RGBA32` and `escape_dir_unity_rgba32f` as `RGBAFloat`.
  Geodesics remain generated offline by the Python CPU/GPU tools; Unity does
  not integrate rays.
- Validation: Added tests for the BH-to-Unity basis, raw texture byte counts,
  metadata fields, and a scalar-vs-vectorized escape-direction cross-check so
  the inlined vectorized inverse-metric terms in `sky.py` cannot drift from the
  scalar metric path.
- References: Same Phase 1 Bardeen/Kerr geodesic sources and Task 4 transfer
  buffers. This is an engineering bridge over validated buffers, not a new
  physical model.
- Open issues / next steps: Import the package into a Unity OpenXR PCVR
  project, connect the shader to a cubemap, then record the Task 5 runtime
  protocol: frame pacing, stereo behavior, head-motion stability, angular size,
  and latency.

### 2026-07-06 - Task 4 momentum escape-direction correction

- Goal: Correct the escape-direction transfer buffer before Task 5 consumes it
  for background cubemap sampling.
- Changed files / components: `src/gr_bh_xr/sky.py`,
  `src/gr_bh_xr/geodesic.py`, `src/gr_bh_xr/gpu/trace.py`, CPU/GPU HDF5 schema
  versions, tests, and validation documentation.
- Academic reason: A transfer map must represent the asymptotic propagation
  direction, not only the finite-radius point where a ray intersects the escape
  sphere. Using position angles would introduce an `O(b / r_escape)` systematic
  bias that is large enough to matter for Task 5 background lensing.
- Physical correspondence: Escaped rays now compute `u^mu = g^{mu nu} p_nu` at
  the escape sphere and project `(u^r, r u^theta, r sin(theta) u^phi)` onto the
  local spherical orthonormal basis before converting to Cartesian
  `escape_dir_{x,y,z}` and angles `(escape_theta, escape_phi)`. Non-escape
  pixels remain NaN.
- Assumptions and conventions: The GPU shader still integrates in f32
  fixed-step RK4, but it now returns the final escape state and covariant
  momenta to Python so the CPU and GPU paths share the same f64 direction
  conversion in `sky.py`.
- Validation: `python -m pytest` passed with 22 tests. A Schwarzschild
  `alpha = 8`, equatorial CPU ray changed escape radius from `200M` to `400M`
  with momentum-direction angular drift `2.25e-7 rad`; the same test is now a
  regression gate at `< 1e-5 rad`. CPU-vs-GPU 65x65 validation retained
  full-grid/stable event agreement `1.0` and capture-fraction difference `0.0`
  for Schwarzschild and Kerr `a = 0.5`, `i = 60 deg`. Momentum-direction errors
  were Schwarzschild max `6.3618e-4 rad`, RMS `3.3274e-5 rad`, median
  `3.7357e-6 rad`; Kerr max `0.0029179 rad`, RMS `8.5875e-5 rad`, median
  `3.8686e-6 rad`.
- References: Same Phase 1 Bardeen screen-coordinate and Kerr geodesic sources;
  this fixes transfer-buffer semantics rather than changing the metric model.
- Open issues / next steps: Task 5 can now consume `gpu_escape_dir_{x,y,z}` for
  static cubemap/skybox lookup. Renderer-side cubemap axis conventions and
  Unity/OpenXR texture import remain the next integration layer.

### 2026-07-06 - Task 4 WGPU Vulkan GPU lensing prototype

- Goal: Start Task 4 with a Vulkan-backed WGPU compute baseline for GPU Kerr
  capture/escape lens maps and XR-oriented debug textures.
- Changed files / components: `pyproject.toml`, `src/gr_bh_xr/gpu/`, GPU tests,
  `validation/gpu_kerr_lensing/README.md`, `renderer/vulkan_compute/README.md`,
  and this validation-target documentation.
- Academic reason: Move from the closed Phase 1 CPU reference solver to a
  real-time GPU path while keeping every GPU output comparable against CPU
  event/failure buffers and exclusion masks.
- Physical correspondence: The WGSL shader follows the Phase 1
  Boyer-Lindquist exterior inverse metric, analytic inverse-metric derivatives,
  Bardeen screen constants, capture/escape classification, and axis-coordinate
  invalid semantics. The GPU integrator is f32 fixed-step RK4, not the CPU
  DOP853 reference.
- Assumptions and conventions: WGPU is used as the Vulkan implementation layer
  because the local machine has Vulkan adapters but no SPIR-V compiler or
  validation toolchain. Task 4 does not include thin-disk transfer, redshift,
  time delay, GRRT, Quest/OpenXR runtime integration, adaptive RK, or
  Kerr-Schild continuation.
- Validation: `python -m pytest` passed with 20 tests. `python -m
  gr_bh_xr.gpu.check_backend` selected the NVIDIA GeForce RTX 5080 Laptop GPU
  with WGPU backend type `Vulkan`. CPU-vs-GPU 65x65 validation reported
  Schwarzschild stable agreement `1.0`, capture-fraction difference `0.0`,
  and GPU failures outside exclusions `0`; Kerr `a = 0.5`, `i = 60 deg`
  reported stable agreement `1.0`, capture-fraction difference `0.0`, and GPU
  failures outside exclusions `0`. 129x129 GPU lens maps reproduced the Phase 1
  CPU event counts for Schwarzschild (`capture = 5385`, `escape = 11178`,
  `invalid = 78`) and Kerr `a = 0.5`, `i = 60 deg` (`capture = 5296`,
  `escape = 11263`, `invalid = 82`). A noninteractive preview snapshot was
  written with `python -m gr_bh_xr.gpu.preview --save-and-exit`.
- References: GPU design remains tied to the Phase 1 analytic sources in
  `docs/equations.md`; WGPU/Vulkan implementation notes are recorded under
  `renderer/vulkan_compute/README.md`.
- Open issues / next steps: Task 4 still needs interactive preview review on
  the user-visible desktop and later CPU-vs-GPU checks for texture import into a
  Unity/OpenXR path. Future GPU work should add adaptive refinement, winding or
  image-order diagnostics, and eventually a coordinate treatment that does not
  terminate at Boyer-Lindquist axis/horizon limitations.

### 2026-07-06 - Task 4 review follow-up

- Goal: Tighten the GPU validation audit fields before pushing the first Task 4
  commit.
- Changed files / components: `src/gr_bh_xr/gpu/validate.py`, GPU tests,
  `validation/gpu_kerr_lensing/README.md`, and validation documentation.
- Academic reason: Stable-region agreement excludes near-capture and
  critical-band samples by design. A separate full-grid event agreement field
  prevents capture/escape count differences from accidentally cancelling in the
  summary.
- Physical correspondence: No shader physics changed. The added documentation
  records a 256x256 fixed-step f32 polar artifact for small-`|L_z|` rays near
  the Boyer-Lindquist axis, where the GPU can step across a narrow centrifugal
  barrier or exhaust its shorter affine-parameter budget.
- Validation: Post-review 65x65 Schwarzschild and Kerr `a = 0.5`, `i = 60 deg`
  checks had full-grid event agreement `1.0`; the 256x256 Kerr example exposed
  25 `solver_failure` and 4 `unclassified_max_lambda` near-polar pixels that
  are now documented as prototype limitations.
- References: Same Phase 1 equations and Task 4 WGPU/Vulkan notes.
- Open issues / next steps: Add a dedicated polar failure code or near-pole
  substepping, then implement near-critical adaptive refinement before making
  stronger high-resolution GPU claims.

### 2026-07-06 - Task 4 critical-band refinement and polar substeps

- Goal: Close the remaining Phase 2 GPU Kerr-lensing gate for near-critical
  refinement and remove the 256x256 small-`|L_z|` polar fixed-step artifact.
- Changed files / components: `src/gr_bh_xr/gpu/trace.py`,
  `src/gr_bh_xr/gpu/generate_lens_map.py`, `src/gr_bh_xr/gpu/validate.py`,
  `src/gr_bh_xr/gpu/preview.py`, failure-code schema, GPU tests, and GPU
  validation documentation.
- Academic reason: AART-style critical-curve refinement is needed before using
  GPU lens maps as auditable texture products near the shadow boundary. The
  previous 256x256 failures were a numerical stepping artifact, so they needed
  either a distinct code path or mitigation before stronger GPU claims.
- Physical correspondence: Center-ray event codes are unchanged for CPU-vs-GPU
  comparison. The analytic critical-curve distance field marks pixels for 2x2
  subpixel tracing and records `gpu_refinement_level`,
  `gpu_subpixel_capture_fraction`, and `gpu_subpixel_invalid_fraction`. Near
  the Boyer-Lindquist polar axis, small-`|L_z|` rays use local RK4 substeps and
  reserve `polar_step_overshoot = 5` for any remaining polar step artifact.
- Assumptions and conventions: The shader remains f32 fixed-step RK4 in
  Boyer-Lindquist exterior coordinates. Preview disables critical-band
  refinement by default for interactive responsiveness, while generated maps
  and validators keep it enabled by default.
- Validation: The 256x256 Kerr `a = 0.5`, `i = 60 deg` GPU map reported
  `solver_failure = 0`, `unclassified_max_lambda = 0`, `invalid = 0`, and
  `refined_pixels = 4102`. The 65x65 Kerr CPU-vs-GPU validation retained
  `full_grid_event_agreement = 1.0`, stable agreement `1.0`, capture-fraction
  difference `0.0`, and GPU failures outside exclusions `0`, with
  `refined_pixels = 254`.
- References: Same Phase 1 analytic sources and AART-inspired adaptive
  sampling motivation listed in the project references.
- Open issues / next steps: Move from CPU-visible HDF5/debug textures to the
  Task 5 Unity/OpenXR texture bridge, then measure headset frame pacing,
  stereo stability, and head-motion behavior.

### 2026-07-06 - Task 4 escape-direction map

- Goal: Add the physical background-lensing buffer needed before Task 5 PCVR:
  escaped-ray sky direction.
- Changed files / components: `src/gr_bh_xr/sky.py`, CPU/GPU lens-map schemas,
  GPU validator, GPU tests, and validation documentation.
- Academic reason: A capture mask is enough for a shadow, but background
  lensing requires a transfer map from screen coordinates to asymptotic sky
  direction. This makes the next Unity/OpenXR step consume a physics buffer
  rather than inventing a visual-only distortion.
- Physical correspondence: Escaped rays now record `(theta_inf, phi_inf)` and
  a unit Cartesian direction vector. Non-escape pixels are NaN. The GPU
  validator compares CPU and GPU escaped-ray direction vectors on the same
  stable mask used for event agreement.
- Assumptions and conventions: This entry introduced the direction-buffer
  contract. The later momentum-correction entry above supersedes the initial
  finite-radius position-angle interpretation. Renderer-specific cubemap axes
  remain a Task 5 convention layer.
- Validation: Kerr `a = 0.5`, `i = 60 deg`, 65x65 CPU-vs-GPU validation kept
  full-grid/stable event agreement `1.0` and capture-fraction difference `0.0`;
  escaped-direction comparison used 2746 stable escaped pixels with max angular
  error `0.002916683 rad`, RMS `0.000168729 rad`, and median
  `4.04749e-05 rad`. A 256x256 Kerr map still reported zero invalid/failure
  pixels and refined 4096 critical-band pixels, taking about `2.46 s` including
  device setup and HDF5 write after cKDTree critical-band acceleration.
- References: Same Bardeen screen-coordinate and Kerr geodesic sources as
  Phase 1; this is a transfer-buffer exposure, not a new metric model.
- Open issues / next steps: Define the renderer cubemap coordinate convention
  and implement the Unity/OpenXR texture bridge.

### 2026-07-06 - Phase 1 closeout review

- Goal: Record that Phase 1 CPU Kerr reference solver work has passed external
  review and can close before Task 4 GPU work begins.
- Changed files / components: Documentation only.
- Academic reason: Preserve the review boundary between the auditable CPU
  baseline and the upcoming GPU real-time Kerr lensing implementation.
- Physical correspondence: No equations or solver behavior changed. The review
  independently checked the analytic inverse-metric derivatives, axis failure
  classification, Kerr critical-curve validation, and lens-map audit outputs.
- Assumptions and conventions: Phase 1 remains a Python Boyer-Lindquist
  exterior reference solver. Axis-regular or Kerr-Schild continuation is
  deferred and is not blocking Task 4 CPU-vs-GPU fixed-case comparison work.
- Validation: External review accepted `96e0c35`; local docs check pending for
  this closeout note.
- References: Same Phase 1 analytic sources listed in `docs/equations.md`.
- Open issues / next steps: Begin Task 4 GPU Kerr lensing planning and
  implementation. Remaining non-blocking Phase 1 follow-ups are
  winding/image-order diagnostics and future axis-regular continuation.

### 2026-07-06 - Phase 1.2 axis classification and analytic derivatives

- Goal: Close the remaining Phase 1 audit issues before GPU work by correcting
  axis-singularity invalid semantics, adding the missing ray-example figure
  generator, and replacing finite-difference inverse-metric derivatives with
  closed-form derivatives.
- Changed files / components: `src/gr_bh_xr/types.py`,
  `src/gr_bh_xr/geodesic.py`, `src/gr_bh_xr/metric.py`,
  `src/gr_bh_xr/generate_lens_map.py`, `src/gr_bh_xr/plot_ray_examples.py`,
  tests, `docs/equations.md`, `docs/validation_targets.md`,
  `data/lens_maps/README.md`, `figures/README.md`, and validation README files.
- Academic reason: The previous `failure_code` field showed that default
  lens-map invalid pixels were not near-critical max-lambda failures; they were
  `alpha = 0`, `L_z = 0` rays reaching the Boyer-Lindquist polar-axis coordinate
  singularity. The audit trail now records that cause explicitly.
- Physical correspondence: Axis hits remain `event = invalid` because the
  Boyer-Lindquist coordinate chart fails at `theta = 0, pi`, but the
  `failure_reason` is now `axis_coordinate_singularity`. The Hamiltonian RHS
  uses analytic derivatives of the inverse metric with respect to `r` and
  `theta`; finite differences remain only as a test oracle.
- Assumptions and conventions: The reference solver remains a Python
  Boyer-Lindquist exterior implementation under `src/gr_bh_xr/`, although the
  original roadmap listed illustrative C++ paths. The roadmap allowed Python or
  C++ for this reference stage; GPU kernels remain a later task.
- Validation: `python -m pytest` passed with 17 tests. Kerr `a = 0.9`,
  `i = 60 deg`, 24-angle validation reported `max_abs_error =
  0.002557648497466758 M`, invalid events `0`, outer `h_max_abs =
  3.850047197717643e-09`, and near-capture `h_max_abs =
  1.2032874110445846e-06`. A 17x17 Schwarzschild lens-map CLI run reported
  event counts `capture = 85`, `escape = 194`, `invalid = 10`, and failure
  counts `axis_coordinate_singularity = 10`, `none = 279`,
  `trace_exception = 0`, `solver_failure = 0`, `unclassified_max_lambda = 0`.
  Full 129x129 lens-map reruns reported Schwarzschild `invalid = 78` with
  `axis_coordinate_singularity = 78`, and Kerr `a = 0.5`, `i = 60 deg`
  `invalid = 82` with `axis_coordinate_singularity = 82`; both had
  `trace_exception = 0`, `solver_failure = 0`, and `unclassified_max_lambda =
  0`.
  `python -m gr_bh_xr.plot_ray_examples --out figures/ray_examples.pdf`
  generated the missing ray-example figure.
- References: Same Phase 1 Hamiltonian and Bardeen screen-coordinate sources as
  `docs/equations.md`; no new literature was required.
- Open issues / next steps: A future axis-regular or Kerr-Schild tracer should
  replace the axis termination with a physical continuation. Lens maps still
  need winding/image-order diagnostics before disk transfer work.

### 2026-07-06 - Phase 1 audit semantics tightening

- Goal: Address post-review audit semantics before moving to the next physics
  feature: clarify Hamiltonian tolerance wording, identify structural
  conserved-quantity zeroes, and separate lens-map invalid causes.
- Changed files / components: `src/gr_bh_xr/validate_kerr_critical_curve.py`,
  `src/gr_bh_xr/generate_lens_map.py`, `src/gr_bh_xr/plot_lens_map.py`, tests,
  `docs/validation_targets.md`, `data/lens_maps/README.md`, and validation
  README files.
- Academic reason: Keep validation claims aligned with what the current
  finite-difference Boyer-Lindquist reference solver actually demonstrates,
  rather than letting audit buffers imply stronger numerical evidence than they
  contain.
- Physical correspondence: The critical-curve pass/fail gate remains boundary
  error plus invalid count. Hamiltonian residuals are split into outer and
  near-capture groups using `r_+ + max(0.1 M, 2 horizon_eps)`. `E` and `L_z`
  drift are documented as structural zeroes from cyclic coordinates; `H` and
  Carter `Q` remain the informative numerical residuals.
- Assumptions and conventions: The current finite-difference metric derivative
  implementation is documented as producing outer grouped `max |H|` at roughly
  the `1e-7` level for high-spin critical-curve runs; `abs(H) < 1e-8` is
  deferred until analytic derivatives or a better near-horizon coordinate
  treatment.
- Validation: `python -m pytest` passed with 14 tests. A targeted Kerr
  `a = 0.9`, `i = 60 deg`, 24-angle validation reported `max_abs_error =
  0.002557648497466758 M`, invalid events `0`, outer `h_max_abs =
  4.27889450538288e-08`, and near-capture `h_max_abs =
  0.0001606790337973507`. A 17x17 Schwarzschild lens-map CLI run wrote HDF5
  schema v2 with event counts `capture = 85`, `escape = 194`, `invalid = 10`
  and failure counts `none = 279`, `solver_failure = 10`, `trace_exception = 0`,
  `unclassified_max_lambda = 0`; the plot CLI rendered
  `outputs/phase1/shadow_validation_audit17.pdf`.
- References: Same Phase 1 Hamiltonian and Bardeen screen-coordinate sources as
  `docs/equations.md`.
- Open issues / next steps: Analytic metric derivatives and axis-specific
  failure classification were addressed in the Phase 1.2 entry above. Lens maps
  still need adaptive refinement and image-order/winding diagnostics.

### 2026-06-29 - Diagnostic grouping and Phase 1 lens-map buffers

- Goal: Split Kerr critical-curve diagnostics so near-horizon
  Boyer-Lindquist residuals cannot be mistaken for outer-ray residuals, then
  persist Phase 1 lens-map audit buffers.
- Changed files / components: `src/gr_bh_xr/validate_kerr_critical_curve.py`,
  `src/gr_bh_xr/generate_lens_map.py`, `src/gr_bh_xr/plot_lens_map.py`, tests,
  `data/lens_maps/README.md`, and `validation/lens_map/README.md`.
- Academic reason: The renderer must expose capture/escape state and numerical
  residuals as data products, not only as rendered images. The Kerr critical
  validator also needs to separate curve-comparison success from the known
  Boyer-Lindquist near-horizon numerical limitation.
- Physical correspondence: Lens maps store screen coordinates `(alpha, beta)`,
  event class, minimum Boyer-Lindquist radius, Hamiltonian residual, `E`,
  `L_z`, Carter `Q` drift, and equatorial crossing counts for each screen
  sample.
- Assumptions and conventions: The lens-map generator keeps the Phase 1
  Boyer-Lindquist exterior tracer and default `horizon_eps = 0.3 M`. HDF5 and
  PDF outputs are generated under ignored `outputs/phase1/`.
- Validation: `python -m pytest` passed with 13 tests. Kerr `a = 0.9`,
  `i = 60 deg` critical-curve validation still had
  `max_abs_error = 0.002705205141551481 M`, `rms_error =
  0.00040112169064067534 M`, invalid events `0`; grouped diagnostics reported
  outer `h_max_abs = 1.750051806803654e-07` and near-capture `h_max_abs =
  0.0001606790337973507`. Generated 129x129 lens maps produced Schwarzschild
  counts `capture = 5385`, `escape = 11178`, `invalid = 78`, and Kerr `a = 0.5`,
  `i = 60 deg` counts `capture = 5296`, `escape = 11263`, `invalid = 82`; the
  Schwarzschild HDF5 rendered to `outputs/phase1/shadow_validation.pdf`.
- References: Data products follow the Phase 1 Hamiltonian/Carter diagnostics
  and Bardeen screen coordinates documented in `docs/equations.md`.
- Open issues / next steps: Later Phase 1.2 review reclassified the 129x129
  invalid samples as `alpha = 0` Boyer-Lindquist axis-coordinate hits, not
  near-critical `max_lambda` exhaustion. Future work should add
  winding/image-order diagnostics and finite-radius tetrads.

### 2026-06-29 - Kerr critical curve validation

- Goal: Validate the Phase 1 Kerr capture/escape boundary against the analytic
  critical curve before adding lens-map persistence or finite-radius tetrads.
- Changed files / components: `src/gr_bh_xr/critical_curve.py`,
  `src/gr_bh_xr/validate_kerr_critical_curve.py`, tests, and
  `validation/kerr_critical_curve/README.md`.
- Academic reason: A Schwarzschild shadow test validates only the `a = 0`
  degeneracy. The Kerr solver needs an analytic photon-shell / critical-curve
  comparison to support claims that Kerr ray tracing is physically aligned.
- Physical correspondence: Implements spherical photon orbit constants
  `(lambda_tilde, eta_tilde)`, the Bardeen screen map, visible critical-curve
  branches, and radial capture/escape bisection against the analytic curve.
- Assumptions and conventions: The validator uses `horizon_eps = 0.02 M` so
  high-spin prograde comparisons are not biased by the safer general tracing
  default `r_+ + 0.3 M`.
- Validation: `python -m pytest` passed with 11 tests. Default runs produced
  `a = 0.5`, `i = 60 deg`: `max_abs_error = 0.003645603127708341 M`,
  `rms_error = 0.000739284655592394 M`, invalid events `0`; and `a = 0.9`,
  `i = 60 deg`: `max_abs_error = 0.002705205141551481 M`,
  `rms_error = 0.00040112169064067534 M`, invalid events `0`.
- References: `gralla2020nullGeodesicsKerr`, `gralla2020lensingKerr`, and
  `bardeen1973kerrGeodesics`.
- Open issues / next steps: Persist full lens maps and add finite-radius
  observer tetrads after the critical-curve gate is stable.

### 2026-06-29 - Phase 1 Python CPU Kerr reference solver

- Goal: Start Phase 1 with an auditable Python CPU reference tracer for
  Schwarzschild/Kerr exterior null geodesics.
- Changed files / components: `pyproject.toml`, `src/gr_bh_xr/`,
  `tests/`, and `validation/schwarzschild_shadow/README.md`.
- Academic reason: Establish a small, inspectable numerical baseline before any
  GPU shader, disk-transfer, GRRT, or XR work.
- Physical correspondence: Implements Boyer-Lindquist exterior inverse metric,
  Hamiltonian null-ray evolution, Bardeen asymptotic screen constants, horizon
  capture classification, sky escape classification, and diagnostics for
  `H`, `E`, `L_z`, and Carter `Q`.
- Assumptions and conventions: Geometric units with `M = 1` by default. Capture
  is classified at `r <= r_+ + 0.3 M` because the Phase 1 Boyer-Lindquist solver
  intentionally stops before the coordinate singularity; Kerr-Schild
  horizon-penetrating integration is deferred.
- Validation: `python -m pytest` passed with 7 tests. Schwarzschild shadow
  validation with grid 129 estimated `b_c = 5.196157378143742` versus
  `3 sqrt(3) M = 5.196152422706632`, absolute error
  `4.9554371095439365e-06`.
- References: Equation/source keys are listed in `docs/equations.md`; primary
  analytic provenance is in
  `references/source_notes/2026-06-29-foundational-analytic-references.md`.
- Open issues / next steps: Replace finite-difference metric derivatives with
  analytic derivatives if stricter near-horizon residuals are needed; add
  Kerr-specific critical-curve comparisons against Gralla-Lupsasca/AART after
  the Schwarzschild baseline is stable.

### 2026-06-29 - Foundational analytic references and Phase 0 fixes

- Goal: Close the Phase 0 gap where GRRT/GRMHD codes and shaders were indexed but
  the primary analytic literature behind the documented equations was missing,
  and fix three audit issues from the Phase 0 review.
- Changed files / components: `references/references.bib`,
  `references/references.md`,
  `references/source_notes/2026-06-29-foundational-analytic-references.md`,
  `references/pdfs/2019-gralla-holz-wald-shadows-photon-lensing-rings.pdf`,
  `references/pdfs/2020-gralla-lupsasca-lensing-by-kerr.pdf`,
  `references/pdfs/2020-gralla-lupsasca-null-geodesics-kerr.pdf`,
  `references/pdfs/2016-odyssey-gpu-kerr-grrt.pdf`, `references/pdfs/README.md`,
  `docs/equations.md`, `docs/physical_scope.md`, and
  `docs/validation_targets.md`.
- Academic reason: An auditable renderer needs provenance for its equations.
  Added Carter 1968, Bardeen/Press/Teukolsky 1972, Bardeen 1973, Cunningham 1975,
  Luminet 1979, Gralla-Holz-Wald 2019, and the two Gralla-Lupsasca 2020 papers,
  then linked each equation block to its primary source.
- Physical correspondence: Carter constant and separability, ISCO and LNRF,
  Kerr null geodesics and screen coordinates, disk redshift transfer,
  direct/secondary images, and photon-ring/lensing-ring structure are now traced
  to primary sources rather than only to reference codes.
- Assumptions and conventions: Open arXiv PDFs (Gralla x3, Odyssey) are stored in
  `references/pdfs/`; pre-arXiv classics (Carter, BPT, Bardeen, Cunningham,
  Luminet) have no open PDF and are indexed by DOI/bibcode only.
- Validation: All four arXiv IDs confirmed against arXiv abstract pages before
  download (titles/authors/journal match BibTeX); the two Gralla-Lupsasca papers
  were disambiguated (1910.12873 lensing, 1910.12881 geodesics); each PDF checked
  for a `%PDF` header; repository consistency checks rerun.
- Fixes applied: (1) Odyssey open PDF stored and `pu2016odyssey` given an arXiv
  eprint; (2) Wayback archived snapshots and access dates added for the Meta and
  Unity web docs (device-optimization save still pending); (3) PDF year
  convention documented in `references/pdfs/README.md` to resolve the KORAL
  filename-vs-citation-year question (it follows the same arXiv-year pattern as
  BHAC and is intentional).
- References: See `references/references.md` and
  `references/source_notes/2026-06-29-foundational-analytic-references.md`.
- Open issues / next steps: Re-archive the Meta device-optimization page once the
  Wayback save completes; begin Phase 1 CPU Kerr solver with the
  Gralla-Lupsasca closed-form geodesics as an analytic cross-check.

### 2026-06-28 - Expanded GRRT, GRMHD, and GLSL reference baseline

- Goal: Add deeper GRRT, relativistic-fluid, and real-time shader references
  before implementation starts.
- Changed files / components: `references/pdfs/*.pdf`,
  `references/references.bib`, `references/references.md`,
  `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`,
  `references/code_reviews/2026-06-28-glsl-and-realtime-projects.md`,
  `docs/physical_scope.md`, `docs/validation_targets.md`, and `AGENTS.md`.
- Academic reason: Separate paper-grade GRRT/GRMHD validation material from
  shader-engineering examples and gray literature.
- Physical correspondence: Added references for polarized GRRT, invariant
  transfer formulation, HARM-family GRMHD, primitive recovery, radiation-GRMHD,
  and real-time Schwarzschild shader precomputation. Kerr-Newman charge remains
  outside the validated first-year Kerr scope.
- Assumptions and conventions: Open arXiv PDFs are stored in `references/pdfs/`;
  Zhihu content is summarized only; third-party code was inspected in temporary
  clones and not copied.
- Validation: Confirmed source metadata from arXiv/GitHub/opencli, then
  requires repository consistency checks listed in `docs/validation_targets.md`.
- References: See `references/references.md`,
  `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`, and
  `references/code_reviews/2026-06-28-glsl-and-realtime-projects.md`.
- Open issues / next steps: Start Phase 1 CPU Kerr solver with diagnostic
  buffers before any GLSL acceleration.

### 2026-06-28 - Phase 0 literature and code baseline

- Goal: Complete the Phase 0 literature/code baseline before starting the CPU
  Kerr solver.
- Changed files / components: `references/pdfs/*.pdf`,
  `references/references.bib`, `references/references.md`,
  `references/code_reviews/2026-06-28-reference-code-baseline.md`,
  `references/source_notes/2026-06-28-phase0-download-log.md`,
  `docs/validation_targets.md`, and `validation/README.md`.
- Academic reason: Make the project auditable from source paper to validation
  target before numerical implementation begins.
- Physical correspondence: RAPTOR, AART, Odyssey, ipole, and grtrans were
  reviewed as external baselines for ray tracing, GRRT, adaptive photon-ring
  sampling, and later polarized-transfer diagnostics. No equations were changed
  in this step.
- Assumptions and conventions: Open arXiv PDFs are stored in `references/pdfs/`;
  third-party code is not vendored; GPL/BSD/MIT license notes are recorded only
  to guide future comparison boundaries.
- Validation: Phase 0 is validated by repository navigation checks,
  `git diff --check`, local-only PDF ignore checks, PDF binary attribute checks,
  and confirming all indexed PDF paths exist.
- References: See `references/references.md`, `references/references.bib`, and
  `references/code_reviews/2026-06-28-reference-code-baseline.md`.
- Open issues / next steps: Start Phase 1 with a CPU Schwarzschild/Kerr
  reference solver and selected-ray diagnostic output.

### 2026-06-28 - PDF literature storage convention

- Goal: Add a dedicated place for original literature PDFs while keeping the
  central reference index authoritative.
- Changed files / components: `references/pdfs/README.md`, `AGENTS.md`,
  `references/references.md`, `README.md`, `.gitignore`, `.gitattributes`,
  `docs/plans/2026-06-28-physics-auditable-renderer.md`, and
  `references/source_notes/2026-06-28-physics-auditable-renderer-sources.md`.
- Academic reason: Make it easy to inspect original papers next to their
  summaries and project-use notes.
- Physical correspondence: No physics equations changed; this is a source
  traceability improvement for future derivations and benchmark claims.
- Assumptions and conventions: Open or safely redistributable PDFs may be stored
  in `references/pdfs/`; restricted, license-unclear, temporary, or oversized
  PDFs belong in ignored `references/pdfs/local_only/`.
- Validation: Confirm `references/pdfs/local_only/` is ignored while
  `references/pdfs/README.md` remains tracked.
- References: Existing entries in `references/references.md` now include a
  `PDF path` field.
- Open issues / next steps: Download and index open-access PDFs for the initial
  RAPTOR, AART, BHAC, and Davelaar papers when needed.

### 2026-06-28 - Physics-auditable renderer roadmap

- Goal: Convert the project direction into a staged physics-auditable renderer
  plan.
- Changed files / components: `docs/plans/2026-06-28-physics-auditable-renderer.md`,
  `docs/physical_scope.md`, `docs/equations.md`, `docs/validation_targets.md`,
  `AGENTS.md`, `references/references.md`, and
  `references/source_notes/2026-06-28-physics-auditable-renderer-sources.md`.
- Academic reason: Prevent the project from becoming a visual-only black-hole
  shader by requiring transfer quantities, validation targets, and literature
  traceability.
- Physical correspondence: The core renderer is framed as a map from observer
  screen coordinates `(alpha, beta)` to capture state, disk crossing data,
  redshift, time delay, image order, optical depth, and observed intensity.
- Assumptions and conventions: First-year work targets single-Kerr physics and
  Quest PCVR/MR display. Full GRMHD, BBH numerical relativity, Quest-native
  GRRT, and direct neural image generation are deferred.
- Validation: Documentation-level validation only; no solver exists yet. The
  plan defines future checks for Hamiltonian drift, conserved quantities,
  Schwarzschild shadow radius, disk transfer, headset behavior, and benchmark
  comparisons.
- References: See `references/references.md` entries for RAPTOR, Odyssey, BHAC,
  AART, Davelaar VR work, Meta Quest documentation, Unity OpenXR Meta
  passthrough documentation, and Meta Depth API.
- Open issues / next steps: Choose the initial reference-solver language and
  data format, then implement Phase 1 CPU Kerr geodesic validation.

### 2026-06-28 - Repository documentation protocol

- Goal: Establish project documentation rules for agent work, literature
  tracking, development logs, and local-only paper drafts.
- Changed files / components: `AGENTS.md`, `references/references.md`,
  `docs/development_log.md`, `.gitignore`, and local `paper_draft/`.
- Academic reason: Keep implementation decisions traceable to literature,
  assumptions, and project-level scientific reasoning from the beginning.
- Physical correspondence: No physics model has been implemented yet; this
  entry only defines the protocol for documenting future model-to-visualization
  mappings.
- Assumptions and conventions: Literature entries belong in
  `references/references.md`; manuscript drafts remain local in `paper_draft/`.
- Validation: Confirm repository layout and Git ignore behavior after editing.
- References: None.
- Open issues / next steps: Add technology-stack-specific build, test, and
  validation instructions once the project architecture is chosen.
