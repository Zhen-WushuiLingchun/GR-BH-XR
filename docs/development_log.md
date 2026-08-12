# Development Log

### 2026-08-12 - Task 11 native Vulkan transfer-keyframe playback

- Goal: turn the accepted time-indexed transfer manifest into a bounded NPGS
  playback path without blending discrete ray classes or falling back to RGB
  frame interpolation.
- Changes: added a two-slot Vulkan residency manager for the six required v3
  cubemap roles, dedicated prepass/composite shader variants, descriptor
  bindings for both bracket endpoints, physical per-texel interpolation, and
  `--transfer-keyframes` playback/smoke CLI options. Slot replacement waits for
  in-flight work before image destruction; asynchronous staging remains a
  performance follow-up rather than a correctness claim.
- Physical correspondence: event/failure classes remain discrete; escape
  directions use guarded normalized interpolation; disk orders are
  coverage-unpremultiplied, interpolate radius/redshift and circular azimuth,
  then are premultiplied again. Playback time is metric coordinate time in
  `M`; requests outside accepted coverage fail rather than extrapolate.
- Validation: the Release C++ and all shader variants compiled. A native RTX
  5080 Vulkan smoke loaded frames `0/1`, rendered their midpoint, replaced
  physical slot 0 with frame 2, retained exactly two slots (`4,992` bytes per
  frame; `9,984` resident), selected `(left=1,right=2,alpha=0.5)`, and exited
  `0`. Every delayed load rehashes the exact bytes sent to Vulkan. An initial
  time outside `[0,2]M` exited `1`. The fixture crosses disk
  azimuth `+179/-179 deg`, rotates escape direction `+X -> +Y`, and changes
  radius/redshift/coverage; the authoritative Python midpoint contract and
  NPGS shader/source contract pass focused regression tests.
- Claim boundary: this closes native residency and interpolation mechanics,
  not the complete inspiral-merger-ringdown asset gate. Native disk color is
  still a labelled visual proxy until Page-Thorne/LUT shading is connected.

### 2026-08-12 - Task 11 native NPGS transfer preflight

- Goal: enforce the accepted Python time-indexed transfer contract again at
  the native runtime boundary before Vulkan resources can be uploaded.
- Changes: added `FTransferKeyframeSequence`, native JSON and SHA-256 loading,
  independent frame/sequence gate validation, strict time bracketing, and the
  `--validate-transfer-keyframes` one-shot NPGS CLI.
- Physical correspondence: this layer selects two accepted transfer states at
  a bounded metric coordinate time; it does not synthesize missing ray classes,
  extrapolate beyond NR coverage, or promote an approximate source metric.
- Validation: the Release build completed; a two-frame v3 fixture selected
  `(0,1,0.5)` and exited zero. A one-byte event-buffer mutation was rejected
  with exit code `3` due to a SHA-256 mismatch. Three source-contract tests
  pin project inclusion, content/gate validation, and fail-closed bracketing.
- Open issue: decoded Vulkan resource residency and physical per-texel temporal
  interpolation remain intentionally deferred until a production merger
  sequence earns `runtimeAssetReady=true`.

### 2026-08-12 - Task 11 time-indexed BBH transfer asset contract

- Goal: turn the measured BBH runtime decision (offline time-indexed NR
  transfer keyframes) into a versioned, fail-closed data contract before a
  large merger asset is generated.
- Changes: added `gr_bh_xr.transfer_keyframes`, a CLI and manifest schema for
  strict metric-time sequences; content-addressed source/frame/gate records;
  v3 cubemap layout and byte validation; bounded frame selection; and
  physically guarded event, escape-direction, and disk-order interpolation.
- Physical correspondence: time is metric coordinate time in units of `M`.
  Discrete ray outcomes are not averaged. Disk interpolation preserves true
  crossing order, coverage premultiplication, circular azimuth, redshift, and
  radius semantics. Static roam grids are rejected because their parameter
  index is not a dynamic spacetime coordinate.
- Validation: ten focused tests cover ready/incomplete manifests, checksum
  mutation, legacy-schema rejection, bounded bracketing, discrete-event
  changes, unit-direction interpolation, azimuth wraparound, and missing disk
  orders. The production BBH asset remains deliberately unclaimed.
- Next: implement the same frame-bracket contract in native NPGS, then connect
  decoded Vulkan resources after a production sequence exists.

## 2026-08-10 - Task 10 measured BBH runtime decision

- Combined the measured `1832x1920`-per-eye synthetic-stereo timing records
  with the accepted Task 8 manifest in a versioned, executable decision tool.
- The stationary path measured `10.188 ms` p95 while full dynamic BBH tracing
  measured `2655.530 ms` p95. Full-resolution dynamic tracing is therefore an
  offline audit kernel, not a 72/90 Hz XR path.
- The bounded NR pilot qualifies a time-indexed keyframe architecture, but no
  complete merger keyframe asset exists yet. Surrogate training remains closed
  because the pilot is not an accepted exact training corpus.
- Foveated and progressive costs remain explicitly labelled estimates. Native
  OpenXR total-frame refresh remains a device-only gate.

## 2026-08-10 - Task 9 dynamic OpenXR/MR timing contract

- Added predicted-display-time to metric-time and binary-phase mapping while
  preserving physical and display-amplified GW signals as separate values.
- Added a bounded causal camera history: delayed rays select frames captured at
  or before their retarded source time. Stale, uncovered, or inconsistent
  camera evidence fails closed.
- Added finite-distance scene-hit provenance and explicit color/depth
  registration. Depth cannot certify RGB delivery and cannot be silently paired
  with another color sequence.
- The focused Python contract suite passed `22` tests; the native Release build
  completed with zero errors. Device RGB/depth delivery and total-frame timing
  remain separate hardware gates.

## 2026-08-10 - Task 8 bounded Einstein Toolkit BBH pilot

- Pinned Einstein Toolkit `ET_2026_05` plus the exact build option list,
  thorn list, component revisions, and six local compatibility/audit patches.
- An optimized Release `linear_wave_z4c` preflight compared `36` files with
  zero failures before either BBH run was accepted.
- Completed low/high fixed-box equal-mass nonspinning runs over `0..1M`. The
  finer final Hamiltonian/momentum/Z4 L2 ratios were
  `0.320814/0.0398197/0.00747885`; both individual apparent horizons and `25`
  finite Psi4 modes were retained.
- Converted disconnected CarpetX openPMD chunks into independent audited ADM
  patches containing `alpha`, `beta^i`, `gamma_ij`, and `K_ij`. The frozen-slice
  `7x7`, two-time gate resolved all `98` low/high ray pairs with event agreement
  `1.0`; this is a bounded pipeline pilot, not a converged merger waveform.

## 2026-08-10 - Task 7 audited ADM snapshot ingestion

- Added `gr-bh-xr.bbh.adm-snapshot.v1` for evolved ADM volume fields with
  mandatory producer/gauge/formulation/units/constraint provenance and
  per-dataset SHA-256 verification.
- Reconstructed the four-metric and all Hamiltonian inverse-metric derivatives
  from trilinearly interpolated `alpha`, `beta^i`, and `gamma_ij`, with linear
  time interpolation and stored spatial/temporal error bounds.
- Added explicit AMR parent and validity-box selection. The finest complete
  stencil is used; guard regions fall back to a declared parent and uncovered
  coordinates return `outside_domain`.
- The synthetic gate records Minkowski metric/derivative errors
  `4.44e-16/3.33e-16`, plane-GW metric/derivative convergence ratios
  `3.996/1.979`, and Kerr node/inverse-identity errors `3.33e-16`.
- Added an explicit CarpetX/openPMD-like field-map converter with source-file
  checksum. It refuses to guess thorn names, gauge, or component order.
- Waveform-only SXS-shaped input is rejected with the structured reason
  `waveform_only_asset`; no waveform mode is misrepresented as a near-zone
  four-dimensional metric.

## 2026-08-10 - Task 6 audited native dynamic BBH tracing

- Ported the accepted equal-mass, nonspinning fixed-orbit superposed
  Kerr-Schild approximation to the shared NPGS GLSL metric interface.
- Added a full four-dimensional RK4 branch with non-frozen `p_t`, worldtube and
  escape events, raw-v4 dynamic diagnostics, and exact canonical launch/final
  states for independent replay.
- Replaced generic `mat4 inverse` calls with the exact rank-two Woodbury inverse
  of the two Kerr-Schild updates. A direct f64 algebra test anchors equivalence.
- The 33x33 native map contains `18/1071/0` capture/escape/invalid pixels. The
  33-ray f64 replay gives event agreement `1.0`, direction median/RMS
  `1.83e-5/5.51e-5 rad`, no one-sided invalids, and maximum `Delta p_t`
  disagreement `3.15e-5`. Reconstructing each launch ray from the declared
  camera basis gives a maximum `1.73e-7 rad` discrepancy, independently
  validating the negative-affine sign and camera-to-BBH coordinate path.
- Added an HDF5 refinement schedule from event and escape-direction gradients,
  explicitly avoiding RGB edge detection, and wired the dynamic provider into
  the synthetic sequential-stereo timing path.
- This is prescribed approximate-metric evaluation plus real ray integration,
  not an Einstein evolution. Capture is an explicit `2.4 m_i` worldtube, not
  an event-horizon claim.
- Sequential dynamic stereo p95 was `2137.67/2655.53/3392.45/3811.41 ms` at
  per-eye `1600x1728/1832x1920/2064x2208/2464x2592`. This decisively fails the
  XR real-time gate and forces a later keyframe/foveated/surrogate decision;
  it is not hidden behind the much faster stationary NPGS figures.

## 2026-08-10 - Task 5d merger-to-remnant transition

- Added the Combi-Ressler Appendix-B smooth interpolation for mass and
  specific spin, plus a derivative-consistent coalescence of both coordinate
  centers onto a supplied remnant worldline.
- Before the transition the provider is exactly the selected inspiral; after
  it, two coincident `M_f/2,a_f` terms sum to one physical Kerr remnant.
- Remnant properties remain explicit inputs pending independently validated NR
  fits. The transition retains the `physics_approximation` label.
- The formal gate reports exact-inspiral error `0`, single-remnant endpoint
  error `2.22e-16`, inverse-derivative disagreement `3.35e-9`, and sampled
  Hamiltonian residuals `7.81e-5 -> 5.57e-4 -> 6.46e-7` across pre/mid/post.

## 2026-08-10 - Task 5c generic-spin Kerr-Schild terms

- Generalized each superposed hole from a Schwarzschild term to the arbitrary
  spin-vector Kerr-Schild form while preserving the zero-spin API.
- Added explicit dimensionless spin vectors to fixed and shrinking orbit
  providers, with the real subextremal bound `|chi|<=1`.
- Added formal single-Kerr, rigid-rotation covariance, derivative, and ADM
  constraint gates. The model remains a constraint-audited approximation.

## 2026-08-10 - Task 5b leading-quadrupole inspiral orbit

- Added unequal-mass quasi-circular inspiral states with the explicit
  convention `q=m1/m2<=1`, center-of-mass weighting, and Peters leading-order
  radiation reaction.
- Analytic `r(t)` and `phi(t)` reproduce `dr/dt`, Keplerian `Omega`, and
  Newtonian binding-energy/quadrupole-flux balance in the formal gate.
- The formal gate reports maximum relative errors `2.20e-9`, `3.01e-9`, and
  `3.09e-16` respectively, with zero center-of-mass residual for `q=1,0.5`.
- The orbit fails closed at a configured minimum separation and is labelled as
  a PN entry approximation, not the full Combi-Ressler 4PN trajectory or a
  merger model.

## 2026-08-10 - Task 5a equal-mass superposed KS provider

- Implemented the first Combi-Ressler Eq. 11 slice: equal-mass nonspinning
  Schwarzschild KS perturbations on a fixed Newtonian circular orbit with
  instantaneous Lorentz boosts.
- Added complex-step derivatives for all four inverse-metric coordinates and
  an independent finite-difference ADM Hamiltonian/momentum constraint oracle.
- The formal gate covers separations `10/20/40M` and two phases. It records
  derivative difference `6.37e-12`, exchange symmetry `2.22e-16`, near-hole
  `max|H|=5.47e-2`, bridge `2.01e-3`, and far `2.97e-7`.
- Constraint residuals are persisted as approximation evidence. The declared
  capture worldtubes are not called event or apparent horizons.
- PN inspiral, aligned/generic spin, merger interpolation, and the NPGS GLSL
  provider remain subsequent independent tasks.

## 2026-08-10 - Task 4 analytic dynamic-spacetime gates

- Added an arbitrary-direction, arbitrary-polarization TT plane-wave metric
  provider with exact finite-amplitude inversion and analytic derivatives,
  while limiting the vacuum claim to linear order in physical strain.
- Added a fixed-arrival-plane f64 gate against Angelil and Saha Eq. 14. At
  `h=1e-3`, the delay residual is `5.12e-7`; halving `h` reduces it by a factor
  `3.99982`, giving observed order `1.99994`.
- The gate records `max|H|=1.05e-15`, nonzero `Delta p_t=-3.8567e-4`, and a
  physical angular displacement of `1.01793e-4 rad`.
- Display amplification is kept outside the metric provider and persisted
  separately so gravitational-wave visibility cannot be mistaken for physical
  strain.

## 2026-08-10 - Task 3 native metric-provider interface

- Added native C++ and shared GLSL metric-provider contracts carrying metric
  time, analytic derivatives, ADM fields, validity, evidence, interpolation
  error, and revision provenance.
- Routed the accepted stationary Kerr-Newman RHS through the shared GLSL
  adapter.  Stationarity is now the explicit reason `p_t` remains fixed; the
  forthcoming dynamic adapters must provide a nonzero time derivative.
- The Release build compiled all four black-hole shader variants and the f64
  native provider.  A 17x17 raw-v3 Kerr audit was byte-identical before and
  after extraction (SHA-256
  `3C8B5F371DDD781D76DE58C95BE63509E04000A58CD1914A256C592978A82B33`),
  with 4 capture, 285 escape, and no invalid/nonfinite records.
- A representative 1832x1920 sequential stereo measurement changed from
  10.164 ms to 10.188 ms GPU p95, a 0.24-percent increase.  This is not an
  OpenXR headset-frame claim.

## 2026-08-10 - Task 2 f64 time-dependent Hamilton oracle

- Added the shared `MetricSample`/provider/event contracts and a full
  eight-dimensional DOP853 canonical solver with `dp_t` enabled.
- Kept capture, escape, horizon, and emitter events outside metric providers so
  future apparent-horizon and NR-domain policies remain auditable.
- Added exact Minkowski, stationary Cartesian Kerr-Schild, and analytic
  time-dependent scale-factor providers.  The last is a solver oracle only.
- Focused gates pass for straight-line propagation, all inverse-metric
  derivatives, KS capture/escape zero regression, nonzero time-dependent
  `p_t`, Hamiltonian preservation, and fail-closed provider-domain exits.
- Observed anchors include `max|H|=5.55e-17` in Minkowski, KS derivative
  difference `6.09e-12`, and stationary KS event-path residuals below
  `1.8e-11`.

## 2026-08-10 - Task 1 sequential synthetic-stereo performance gate

- Added a device-independent NPGS stereo view scheduler with asymmetric FOV
  tangents, physical left/right origins through `meters_per_M`, and a native
  sequential render mode.
- Added Vulkan timestamps around prepass, composite, and post processing plus
  a fail-closed Python pair aggregator (`>=99%` valid timestamp pairs).
- On RTX 5080 Laptop / driver 591.74, 1600x1728 per eye passed the 90 Hz physics
  render budget in all disk/polarization combinations (p95 7.80-8.11 ms),
  1832x1920 passed only 72 Hz (9.95-10.23 ms), and larger tested extents failed
  the 11 ms physics budget.
- This is not an OpenXR total-frame claim. Sequential TAA accumulation is
  disabled to prevent cross-eye history contamination; multiview remains open.

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

### 2026-08-10 - BBH dynamic-spacetime implementation plan and literature baseline

- Goal: freeze a long-horizon, reviewable route from the accepted single-hole
  NPGS runtime to approximate real-time BBH tracing, offline numerical-
  relativity truth data, and time-correct XR/MR rendering.
- Changed files / components: added
  `docs/plans/2026-08-10-bbh-dynamic-spacetime-xr.md` and
  `references/source_notes/2026-08-10-bbh-dynamic-spacetime-foundations.md`;
  registered their status and gates in `docs/current_status.md`,
  `docs/validation_targets.md`, and the central literature indexes.
- Academic reason: a dynamic BBH metric removes stationarity, so the renderer
  must evolve the full four-dimensional Hamilton system and cannot reuse Kerr
  energy, axial angular momentum, or Carter conservation as generic evidence.
- Physical correspondence: the first interactive provider is a constraint-
  audited superposed Kerr-Schild approximation. The high-fidelity path consumes
  time-indexed ADM fields from an offline BSSN/Z4c or generalized-harmonic
  evolution. Runtime capture uses apparent horizons/worldtubes; event horizons
  remain offline future-global products.
- Assumptions and conventions: geometric units and signature `(-,+,+,+)` are
  retained. Real-time metric evaluation, real-time ray integration, and
  real-time Einstein evolution are separate claims. Any visible amplification
  of a gravitational-wave effect records `visual_gain` separately.
- Validation: documentation contracts require the active plan, source note,
  evidence labels, simulated-stereo timing budgets, dynamic Hamiltonian gate,
  apparent-horizon boundary, and camera/metric timing semantics. The focused
  documentation suite passed `4` tests and the complete repository suite passed
  `273` tests in `152.28 s`. No BBH implementation or performance acceptance
  is claimed by this entry.
- References: Bohn et al. 2015; Vincent et al. 2011/2012; Combi et al. 2021;
  Combi and Ressler 2024/2026 revision; BSSN, moving-puncture and generalized-
  harmonic foundations; Einstein Toolkit/CarpetX; SXS data documentation;
  dynamical horizons; analytic plane-GW optics.
- Open issues / next steps: finish the equation-level Task 0 review, then run
  the simulated stereo performance gate and implement the Python f64 dynamic
  metric oracle before modifying the NPGS shader core.

### 2026-08-10 - BBH equation freeze and Combi-Ressler source audit

- Goal: close Task 0 with a primary dynamic Hamiltonian, an independent 3+1
  cross-check, and a pinned review of the public approximate-BBH source.
- Changed files / components: expanded the dynamic section of
  `docs/equations.md`; added
  `references/code_reviews/2026-08-10-combi-ressler-bbh-metric.md`; updated the
  source note, literature indexes, and documentation contract tests.
- Academic reason: a time-dependent metric requires `p_t` evolution and a
  source-level provenance boundary before formulas are ported to Python or
  GLSL.
- Physical correspondence: the primary oracle is the covariant canonical
  four-dimensional null Hamiltonian. Vincent's Eulerian energy/direction form
  and Bohn's normalized covariant momentum form are independent 3+1 checks.
  Runtime capture remains an apparent-horizon/worldtube claim, never a local
  event-horizon claim.
- Assumptions and conventions: signature `(-,+,+,+)`, geometric units,
  `x^0=t`, and covariant canonical momentum. The Combi-Ressler model remains a
  `physics_approximation` rather than an Einstein evolution.
- Validation: Zenodo archive `public_repo.zip` (446718 bytes) reproduced the
  published MD5 `ecc4d1268342520f29e4537d5f3ab183`. The generated metric form,
  external dependencies, missing derivative/constraint interface, and mixed
  file-level licenses were inspected. The archive remains ignored and is not
  vendored.
- References: Vincent et al. 2012; Bohn et al. 2015; Combi and Ressler v3;
  Zenodo `10.5281/zenodo.10841021`; Ashtekar and Krishnan 2004.
- Open issues / next steps: choose and gate the ADM interpolation basis during
  Task 7. Task 1 synthetic stereo and Task 2 f64 dynamic Hamilton work may now
  begin independently.

### 2026-08-10 - Native NPGS OpenXR and MR interface contracts

- Goal: complete the device-independent NPGS runtime boundary before physical
  headset work, and repair the passthrough definition so placeholder textures,
  extension enumeration, or depth-only acquisition cannot pass as live lensed
  room radiance.
- Changed files / components: fork commit `6c9a3aa` adds separate desktop and
  OpenXR render-sink contracts, asymmetric stereo views, explicit
  `meters_per_M`, injected extension probing, calibrated color/depth records,
  and bounded passthrough claim decisions. GR-BH-XR adds
  `gr-bh-xr.npgs.integration.v1`, `gr-bh-xr.npgs.mr-frame.v1`, fail-closed
  audit metadata integration, tests, source notes, and validation documents.
- Academic reason: using NPGS directly for its validated fast physics does not
  remove the need to distinguish accepted ray geometry from unvalidated
  emission, XR lifecycle, MR delivery, or BBH/GW claims.
- Physical correspondence: native coordinates remain ingoing Cartesian
  Kerr-Schild `(x,y,z,t)` with covariant momentum, spin `+y`, native
  `M=0.5`, and normalized `M=1`. Each XR eye supplies its own tracked origin and
  asymmetric FOV. A passthrough frame must include calibrated intrinsics and a
  rigid capture pose before its pixels can define incident room radiance.
- Assumptions and conventions: a forward camera supports only a forward-cone
  claim. Cached rear radiance is time-frozen, and environment depth is an
  independent optional measurement rather than proof of RGB delivery.
- Validation: the NPGS Release build completed with zero errors; a 640x480
  desktop smoke run preserved the GLFW path. The focused integration suite
  passed `31` tests and the complete repository suite passed `271` tests in
  `153.07 s`. The manifest CLI wrote the reviewed feature matrix successfully.
- References: official OpenXR 1.1 and `XR_KHR_vulkan_enable2`, indexed in
  `references/references.md`; NPGS upstream remained at `a039e64` on the
  2026-08-10 public-ref refresh.
- Open issues / next steps: implement the real OpenXR session and stereo
  swapchain sink, then bind a supported camera API and persist one delivered
  frame satisfying the MR contract. No device acceptance is claimed here.

### 2026-08-06 - NPGS camera polarization and Walker-Penrose gate

- Goal: Reuse NPGS's native polarization path while independently determining
  whether its camera basis and Walker-Penrose scalar satisfy the physical
  transport definition.
- Changed files / components: native audit raw v3 adds camera basis/WP evidence;
  the shared GLSL path now performs complete Gram-Schmidt and evaluates the
  full BL Walker-Penrose scalar from the active ingoing/outgoing KS chart. A
  minimal Python f64 oracle integrates the parallel-transport equation and a
  fail-closed validator persists JSON/HDF5 evidence. The NPGS shader compiler
  now hashes recursive include contents so shared-physics edits cannot leave
  checked-in SPIR-V stale after a clean checkout.
- Academic reason: the former Cartesian shortcut was fast but nonconserved, so
  visual plausibility could not establish polarization transport correctness.
- Physical correspondence: the oracle transports `f^mu` with
  `df^mu/dlambda=-Gamma^mu_(nu rho)k^nu f^rho`; the scalar uses
  `K=(A-iB)(r-i a cos(theta))`. NPGS remains the renderer and the CPU code is
  only an independent definition-level check.
- Validation: all 1089 camera bases were valid. Norm/orthogonality maxima were
  `2.38e-7/5.12e-8`; 2178 native-vs-f64 scalar comparisons gave median/p99/max
  `1.46e-7/1.05e-6/6.82e-6`. Sixteen direct f64 transports gave maximum
  `abs(H)=1.17e-10`, norm drift `2.56e-10`, transversality `5.50e-11`, and
  Walker-Penrose relative drift `3.61e-8`. The rejected shortcut drifted up to
  `0.324`. The complete repository suite passed `254` tests; a repeated native
  Release build reported all 20 shader outputs current and zero build errors.
- References: `li2026kerrNewmanPolarizedTransfer`; ipole and RAPTOR II remain
  later polarized-transfer benchmarks.
- Open issues / next steps: validate emission, absorption, Faraday terms, and
  Stokes output separately before making a polarized-GRRT image claim; proceed
  to native OpenXR and MR only on the accepted geometry path.

### 2026-08-06 - NPGS native Kerr disk-transfer gate

- Goal: Reuse NPGS's shared native `TraceRay` path for disk transfer while
  independently checking its first two equatorial crossings against the CPU
  f64 Kerr reference.
- Changed files / components: the NPGS fork now exports `m=0/1` crossing
  radius, Boyer-Lindquist azimuth/time delay, finite-observer redshift, true
  crossing order, validity, and flags through raw-v2. GR-BH-XR adds a
  fail-closed parser, exact-state replay validator, HDF5/JSON evidence, tests,
  a Unicode-safe native capture wrapper, and gate documentation.
- Academic reason: NPGS is used directly as the runtime; only a minimal
  independent replay is retained so the renderer does not certify its own
  transfer quantities.
- Physical correspondence: the disk is a neutral circular Kerr emitter over
  `[r_ISCO,30M]`. The native finite-observer definition is
  `g=1/[u^t(E-Omega L)]` because the camera tetrad fixes local launch frequency
  to one. Killing `E` and spin-axis `L` are evaluated from the exact initial
  canonical state, not from separately interpolated crossing fields.
- Validation: quality 2, `a/M=0.9`, `Q=0`, `i=60 deg`, `r_obs=100M`, 65x65
  produced `60 capture / 4165 escape / 0 invalid`, with native disk validity
  `[1439,41]`. The 318-ray f64 replay included every second crossing and gave
  native/CPU/compared valid counts `[142,41]`, zero presence/validity/flag/order
  mismatches, and max errors `0.0199722M` in radius, `3.4780e-4 rad` in azimuth,
  `0.0207713M` in delay, and `2.0221e-4` in redshift.
- Numerical boundary: NPGS dynamically changes KS charts. The single-chart CPU
  oracle stops past-directed captured rays `0.01M` outside `r_+`; all compared
  disk crossings precede that guard. The resulting CPU worst `abs(H)=2.95e-4`
  is retained as a chart-boundary diagnostic, not used as disk acceptance.
- Claim boundary: this closes Kerr `Q=0` disk geometry/kinematics only.
  Charged-disk physics, Page-Thorne integration, Walker-Penrose polarization,
  maximal extension, and OpenXR remain open.
- References: Cunningham disk transfer and the indexed NPGS revision; see
  `validation/npgs_disk_transfer/README.md`.
- Open issues / next steps: independently audit NPGS's existing polarization
  path, then begin native Vulkan/OpenXR integration.

### 2026-08-06 - Native NPGS nonzero-charge Kerr-Newman gate

- Goal: Accept or reject NPGS's nonzero-charge geodesic kernel without
  replacing the native runtime or using the GLSL implementation as its own
  scientific reference.
- Changed files / components: added a minimal independent f64 Kerr-Newman BL/KS
  metric, analytic derivatives, neutral-photon DOP853 replay tracer,
  `H/E/L_z/Q_Carter` diagnostics, raw-v2 native validator, HDF5/JSON evidence,
  tests, equations, and gate documentation.
- Academic reason: NPGS already supplies the faster and broader renderer. The
  project only implements the smallest independent oracle needed to distinguish
  a correct KN kernel from a visually plausible one.
- Physical correspondence: `Delta=r^2-2Mr+a^2+Q_charge^2` and
  `H_KS=(Mr^3-Q_charge^2 r^2/2)/(r^4+a^2z^2)` follow
  `li2026kerrNewmanPolarizedTransfer` Eq. 2.1-2.2. Neutral photon motion keeps
  the Hamiltonian and Killing/Carter diagnostics; no Lorentz force is included.
- Validation: unit gates cover `Q_charge=0 -> Kerr`, `a=0 -> RN`, analytic
  horizons, BL/KS tensor equivalence, `det(g_KS)=-1`, metric derivatives, and a
  captured nonzero-charge ray. Native quality-2 generic KN
  (`a/M=0.6,Q/M=0.5`) produced `101/988/0` capture/escape/invalid; 257 f64
  replays gave stable agreement `1.0` and direction median/RMS
  `1.43e-5/2.99e-5 rad`. The RN runtime limit (`a=0,Q/M=0.6`) produced
  `97/992/0`; 129 replays gave `1.0` and `1.62e-5/4.07e-5 rad`.
  The complete repository suite passed `243` tests.
- Claim boundary: this accepts neutral sub-extremal exterior KN ray geometry.
  The CPU capture event is at `r_+ + 0.02M`; capture residuals are not presented
  as horizon-penetration evidence. Polarization, charged particles, disk/jet
  emission, Cauchy-horizon continuation, and maximal extension remain open.
- References: `li2026kerrNewmanPolarizedTransfer`; NPGS fork/raw-v2 provenance.
- Open issues / next steps: validate NPGS disk semantics and Walker-Penrose
  polarization independently, then begin native Vulkan/OpenXR integration.

### 2026-08-06 - NPGS exact-state Kerr replacement gate

- Goal: Determine whether the native NPGS `Q_charge=0` path can replace the
  accepted Kerr runtime without reconstructing camera initial conditions or
  using NPGS as its own reference.
- Changed files / components: NPGS raw audit schema v2 now records exact initial
  and final ingoing Cartesian Kerr-Schild canonical states; the shared visual
  kernel keeps exact Kerr geometry active through the finite escape boundary;
  Carter diagnostics use the angular separation formula rather than the
  cancellation-prone radial potential. GR-BH-XR adds a BL/KS dual-reference
  cross-check and full-grid endpoint invariant persistence.
- Academic reason: A visual match is insufficient for runtime replacement. The
  CPU must replay the exact state consumed by the native shader and independently
  compare event class, escaped direction, Hamiltonian, and Killing/Carter
  diagnostics.
- Physical correspondence: NPGS stores `(x,y,z,t)`, spin along `+y`, and traces
  with negative affine step. The CPU uses `(t,x,y,z)`, spin along `+z`, and
  positive affine step. The cross-check applies the proper spatial rotation
  `(x,y,z)_N -> (x,-z,y)_P` and negates the complete covector. BL f64 supplies
  exterior event classification; ingoing Cartesian KS f64 supplies escaped-ray
  direction in the same regular chart.
- Validation: native quality 2 at `a/M=0.9`, `Q=0`, `i=60 deg`, `r_obs=100M`,
  33x33 produced `104 capture / 985 escape / 0 invalid`. On 257 deterministic
  CPU samples, stable and all-resolved event agreement were both `1.0`; escaped
  direction median/RMS/max errors were `1.39e-5 / 2.77e-5 / 9.51e-5 rad`.
  Full-grid endpoint drift maxima were `0` for `E`, `6.71e-4` for `L_z`, and
  `1.02e-3` for `Q`. Escaped endpoint `abs(H)` was at most `1.90e-7`.
  Same-machine visual timing at fork `20acb4a` measured 189 median FPS at
  1080p and 71 at 4K versus the pre-audit 183/69 comparison, so the five-percent
  regression gate passes. The complete GR-BH-XR suite passed `232` tests, and
  the raw-v2 artifact converted successfully to HDF5/JSON with its exact-state
  and source-provenance fields intact.
- Claim boundary: quality 1 remains a visual fast mode; quality 2 is the minimum
  accepted audit/scientific mode. Captured endpoint covectors can be `O(1e4)` at
  the horizon, making f32-serialized endpoint H cancellation-conditioned; that
  value and a single `0.099` transient stepwise Carter spike remain recorded but
  are not substituted for endpoint invariant drift.
- Open issues / next steps: the `Q=0` Kerr replacement slice is closed. Nonzero
  charge, Walker-Penrose polarization, native OpenXR, and disk-transfer parity
  remain gated independently.

### 2026-08-06 - Native NPGS audit capture and versioned artifact conversion

- Goal: Make NPGS emit inspectable physics records while preserving its visual
  fast path, then convert the native binary into the repository's versioned
  HDF5/JSON evidence format.
- Changed files / components: the fork now has an opt-in offscreen audit pass,
  native readback and metadata CLI, deterministic descriptor-set ordering, and
  a corrected reflected-storage-buffer binding path. GR-BH-XR adds
  `gr_bh_xr.npgs_audit` with fail-closed parsing, unit conversion, provenance,
  HDF5 persistence, and synthetic corruption tests.
- Academic reason: an RGB renderer cannot replace the accepted solver. Event,
  failure, escape direction, minimum radius, step count, raw/projected
  Hamiltonian, correction magnitude, and conserved-quantity drift must be
  available to an independent reference validator.
- Physical correspondence: native NPGS uses `R_s=1`, hence
  `M_internal=0.5`; exported radius and coordinate-time fields are converted to
  `M` units. Hamiltonian projection is explicitly recorded as an algorithmic
  correction and is not presented as raw RK accuracy. Disk slots remain
  reserved and invalid in this revision.
- Validation: Release build and `spirv-val` passed. Native smoke captures gave
  Schwarzschild `29 capture / 260 escape` at 17x17 and Kerr `a=0.9, i=60 deg`
  `104 capture / 985 escape` at 33x33, with zero invalid/non-finite records.
  The latter converted successfully with maximum escape-direction norm error
  `1.00e-7`. Same-condition visual A/B measured 183 vs 181 FPS at 1080p and 69
  vs 68 FPS at 4K, below the five-percent regression gate.
- Open issues / next steps: run the Kerr `Q_charge=0` event/direction comparison
  against the Python f64 Kerr-Schild reference. Nonzero charge and polarization
  remain blocked on independent reference modules.

### 2026-08-06 - Complete NPGS upstream sync and exact native performance zero point

- Goal: Complete the full current public NPGS repository before integration,
  make its source build reproducibly, and establish a resolution-authenticated
  fast-path baseline before adding audit outputs.
- Changed files / components: created the GPL fork/submodule boundary, local
  bootstrap/doctor/build/benchmark scripts, generated and validated the shader
  runtime assets missing from upstream, made shader startup fail closed, and
  added deterministic native launch plus exact-framebuffer benchmark modes.
- Source audit: official `master`, tag/prerelease `v-114514-test` all resolve
  to `a039e6417b28d53cbd413ee8f6d64543e755aa3e`. Closed draft PR #1 contains
  Windows CI/dependency wiring only. No public BBH/GW branch or release source
  beyond that commit was found. The local history is non-shallow and
  `git fsck --full --strict` passed.
- Physical correspondence: no NPGS physics feature is accepted by this step.
  The measured path is the existing visual prepass/composite/TAA path with
  default `M=0.5 (Rs=1)`, `a/M=0.998`, zero charge, static observer mode, and
  polarization disabled.
- Validation: Release build succeeded; all six required SPIR-V files passed
  `spirv-val --target-env vulkan1.4`; missing shader assets now exit cleanly
  instead of dereferencing an empty stage list. Exact framebuffer checks
  rejected a DPI/work-area-clamped false 4K run, then measured 200 median FPS
  at 1920 x 1080 and 76 median FPS at 3840 x 2160 after the borderless hidden
  surface fix. The complete GR-BH-XR suite passed `220` tests.
- Evidence: `validation/npgs_native_baseline/README.md` and ignored
  `outputs/npgs/baseline_*.json`.
- Open issues / next steps: add the shared visual/audit GLSL core and
  `gr-bh-xr.npgs.audit.v1`, force `Q_charge=0` for the first CPU comparison,
  and do not begin native OpenXR claims before the Kerr gate passes.

### 2026-08-06 - Task 9/10 baseline freeze and native NPGS migration decision

- Goal: Publish the complete Unity live-tracing/MR baseline before beginning a
  GPL-compatible native NPGS migration, and create one canonical status source
  that cannot confuse historical task numbering with current capabilities.
- Changed files / components: restored the missing stable Unity `.meta` file,
  added `docs/current_status.md`, linked it from the repository documentation,
  and corrected the stale baked-only statement in the Unity package README.
- Academic reason: A third-party renderer can only replace this project after
  independent equation and buffer-level gates. The existing CPU reference and
  audit paths must remain available during migration.
- Physical correspondence: No equations changed. The status document separates
  baked transfer lookup, batched live Kerr-Schild integration, worldline
  playback, unaccepted MR, and the proposed Kerr-Newman runtime.
- Assumptions and conventions: The reviewed public NPGS baseline is
  `a039e6417b28d53cbd413ee8f6d64543e755aa3e`; its Kerr-Newman and polarization
  claims remain candidates until independently validated. BBH/GW showcase media
  is not treated as available source code.
- Validation: Full repository suite `214 passed`; `git diff --check`; complete
  Unity asset `.meta` coverage.
- References: Existing NPGS entry and code review in `references/`.
- Open issues / next steps: Create the NPGS fork and pinned submodule, reproduce
  its unmodified desktop build, then add a separate audit path before native
  OpenXR work.

### 2026-08-06 - Version-locked URP 17 asset repair

- Goal: Make the formal Unity project openable, compilable and buildable under
  its locked Unity `6000.0.76f1` / URP `17.0.4` toolchain after some render
  pipeline assets were serialized by a newer editor, without hand-editing any
  serialized version field.
- Changed files / components: added
  `xr/unity_frontend/Editor/GRBHXRUrpAssetRepair.cs`; added URP/core references
  to `xr/unity_frontend/Editor/GRBHXR.Editor.asmdef`; added a fail-closed
  preflight call as the first statement of
  `GRBHXRQuestPcvrSetup.BuildWindowsOpenXrPlayer`; added two source-contract
  tests and a `_csharp_code_only` helper to `tests/test_xr_export.py`; updated
  `xr/unity_frontend/README.md` and `validation/quest_pcvr/README.md`.
- Academic reason: None directly. This is build-tooling integrity work. Its only
  physics-facing role is negative: it keeps a corrupted render pipeline from
  being mistaken for a rendering result, and it keeps the editor version lock
  enforceable so future gate captures are reproducible.
- Physical correspondence: None. No equation, constant, coordinate convention,
  unit, or renderer output is touched by this change.
- Assumptions and conventions: The contamination was diagnosed as Unity `6000.5`
  / URP `17.5.0`, not URP 18. Evidence: `Library.6000.5.backup_20260718`
  contains URP `17.5.0`, whose `k_LastVersion` constants are `10` (global
  settings), `13` (RP asset) and `3` (renderer data), matching the observed
  `m_AssetVersion: 10` and `k_AssetVersion: 13`. The two renderer data assets
  were still at `2`, which is current for 17.0.4, and were reused by reference.
  `UniversalRenderPipelineGlobalSettings` and its `Ensure()` overload are
  `internal` in URP 17.0.4, so the public
  `RenderPipelineGlobalSettingsUtils.Create(Type, path)` overload is used with
  the concrete type taken from the loaded asset. No version number is
  hardcoded: the expected version is read from a freshly constructed instance.
  Repair rewrites the existing asset object in place via
  `EditorUtility.CopySerialized` from a pristine object, so GUIDs, asset paths,
  and the `GraphicsSettings` / `QualitySettings` registrations are preserved.
  Compatible graphics settings inside the managed-reference container are first
  sanitized through a data-source clone, copied by stable type into the pristine
  object, and serialized again for exact comparison. All incompatible assets are
  backed up before the first write; an exception restores and reimports every
  backup.
- Validation: Unity `6000.0.76f1` batch runs against the formal project, full
  logs and machine-readable reports preserved under
  `outputs/claude_agents/2026-08-05-mr-device-gate/urp17-repair/`. The initial
  repair implementation was **rejected** after an independent diff showed that
  it reset the valid
  `URPShaderStrippingSetting.m_StripUnusedPostProcessingVariants` value from `1`
  to `0`; its report did not disclose that loss. The corrected schema-v2 repair
  was rerun from the untouched pre-repair copies. It preserved and serialized
  identically all 26 URP-17.0.4-compatible managed settings, including the
  stripping flag and default volume-profile reference; removed only the nine
  unavailable 17.5-only types; preserved all renderer-data slots and default
  renderer indices; retained all asset GUIDs and registrations; and produced
  `m_AssetVersion` 10 -> 8 plus both RP asset versions 13 -> 12. A deliberate
  failure after the first repaired asset exited `1`, emitted
  `rollbackPerformed: true`, and restored all three originals byte-for-byte at
  versions 10/13/13 before the final successful repair. The final preflight
  exited `0`. Post-write version compatibility, registration equality, and
  transient cleanup are inside the transaction, so any late gate failure also
  restores the backed-up render-pipeline assets. The audit/preflight paths may
  create and then delete URP's
  hard-coded transient `Assets/DefaultVolumeProfile.asset`; acceptance requires
  successful deletion, so they do not leave a project asset behind. The final
  transaction implementation was rerun under
  `urp17-repair/transaction-v5/`: injected repair exit `1` with rollback to
  `10/13/13`, normal repair exit `0` at `8/12/12` with the stripping flag still
  `1`, final preflight exit `0`, and the repository suite reported `171 passed`.
- References: URP 17.0.4 and SRP core 17.0.4 package sources in the formal
  project's `Library/PackageCache`, read directly rather than from documentation.
  Key sites: `Runtime/UniversalRenderPipelineGlobalSettings.cs:22,31,239`,
  `Runtime/Data/UniversalRenderPipelineAsset.cs:449,678`,
  `core Runtime/RenderPipeline/RenderPipelineGlobalSettingsUtils.cs:35`,
  `core Runtime/RenderPipeline/RenderPipelineGraphicsSettingsContainer.cs:38-45`,
  `Editor/BuildProcessors/URPBuildDataValidator.cs`.
- Open issues / next steps: `validation/quest_pcvr/scripts/quest_pcvr_preflight.ps1`
  still defaults to Unity `6000.5.2f1`, which is how this corruption arose;
  changing it also changes a pinned assertion in `tests/test_xr_export.py` and
  was left out of this focused commit. The preflight does not expand the
  `IncludeAdditionalRPAssets` label/scene inclusion set (currently disabled).
  `Assets/Settings/DefaultVolumeProfile.asset` still carries nine orphaned
  `VolumeComponent` sub-objects leaked from `Unity.RenderPipelines.Core.Editor.Tests`;
  unrelated to versioning, harmless at runtime, not addressed here. A repaired,
  compiling project is explicitly not a device-validated one: no headset run and
  no MR passthrough RGB claim follows from this change.

### 2026-08-05 - Independent Unity live-tracer observer-frame gate

- Goal: Close a common-mode hole in the Task 9 Unity/Python comparison: both
  tracers launched from the dumped tetrad, so a wrong observer frame could
  cancel out and still produce perfect downstream agreement.
- Changed files / components: extended
  `validation/quest_pcvr/scripts/compare_live_tracer.py`,
  `tests/test_xr_export.py`, `validation/quest_pcvr/README.md`, and
  `docs/validation_targets.md`.
- Academic reason: A physics-auditable renderer must validate the observer who
  defines the local sky, not only the rays launched from a shared unverified
  frame.
- Physical correspondence: reconstructs the runtime binary32 Kerr parameters,
  finite observer station, full KS static/rain tetrad convention, independent
  Doran rain four-velocity, ingoing branch, and radial/polar/azimuthal leg
  orientation before any GPU cross-check is allowed to run.
- Assumptions and conventions: Unity stores metric/station controls as
  binary32 but promotes them to double for frame construction; the comparator
  reproduces that promotion before applying `1e-9` equality thresholds.
- Validation: behavior tests accept the independent rain reference, reject a
  flipped polar leg even though its Gram matrix is unchanged, and verify the
  complete static spatial convention rather than only its two-plane. The
  comparison JSON now persists the `observerFrame` evidence.
- References: `doran2000newKerrForm`; no new source added.
- Open issues / next steps: existing v6 validation dumps predate the corrected
  frame/stage metadata and are intentionally rejected. A fresh formal Unity
  dump is required before claiming the complete Task 9 device-side gate.

### 2026-08-05 - Audited horizon-crossing descent keyframes

- Goal: Add the Task 8 rain-frame descent keyframe path with a committed,
  deterministic validation producer, and replace its geometry-based ray
  validity heuristics with a first-principles criterion.
- Changed files / components: added
  `src/gr_bh_xr/gpu/generate_descent_keyframes.py`,
  `src/gr_bh_xr/gpu/validate_descent_frames.py`,
  `tests/test_descent_keyframes.py`,
  `validation/descent_keyframes/README.md`; extended
  `src/gr_bh_xr/gpu/trace_ks.py` with equatorial disk-crossing recording, a
  packed-array input path, and `time_orientation`.
- Academic reason: This is the first path in the project that renders from
  inside the horizon. Its claims about aberration, chart conversion and ray
  validity are exactly the ones that cannot be checked by eye, so each needs a
  producer that runs.
- Physical correspondence: full-sky maps for the Doran rain observer sampled
  along the actual infall worldline, in the Cartesian ingoing Kerr-Schild
  chart. Rays are traced PAST-directed because inside the horizon the future
  cone points inward, so the image is the history of the light that fell in.
  The per-texel observer factor is analytic, `E_inf(d) = w + dot(d, xyz)` with
  `eInf = [-et_phi, -et_theta, -et_r, -u_t]`, verified to `6.66e-16` in float64.
- Assumptions and conventions: `time_orientation = -1` flips the conserved
  quantities fed to the disk redshift, which is required because `g` is
  invariant under flipping `E` and `L` together and without it every
  past-traced disk sample fails the `denom <= 0` guard and is silently
  discarded. Validity is claimed between the inner and outer horizons.
- Validation: `python -m gr_bh_xr.gpu.validate_descent_frames`, deterministic
  (Fibonacci-sphere directions, no RNG) and fail-closed on small samples,
  non-finite directions, or excessive Hamiltonian exclusion. At `a/M = 0.9`,
  `theta = 60 deg`, `r_obs = 2.35M`, 4096 directions, 3658 compared:
  chart direction `3.251e-4 deg` max / `2.180e-4` median at `r_escape = 200M`
  and `7.543e-2` / `2.709e-2` at `20M`; observer factor `6.66e-16` (f64) and
  `1.196e-7` (f32); negative controls `1.575` and `1.812`; launcher null
  residual `3.00e-15`. A face-24 descent of 20 keyframes runs `0.986` to
  `0.801` escape fraction with no discontinuity, and azimuth drifts monotonically
  to `-23.7 deg`.
- Audit findings acted on:
  - BLOCKER: the exterior horizon-hug rule `min_r < r_+ + 0.05` was applied
    regardless of the observer's own radius, so any exterior keyframe with
    `r_obs < r_+ + 0.05` had every ray - including ones launched straight
    outward - reclassified as dark. The DEFAULT schedule hits this: index 14 of
    a 20-keyframe `9M -> 0.75M` descent lands at `r = 1.4423`, exterior but
    only `0.0064` above `r_+`, and rendered COMPLETELY BLACK with no error and
    a printed `escape=0`. It now keeps `0.847` of the sky.
  - BLOCKER: the interior rule `lambda_end > 0.6 max_lambda` was about `10x`
    under-inclusive, admitting 644-799 texels per interior keyframe with
    `h_max_abs` up to `1.7e10`. Both rules are replaced by the Hamiltonian
    residual, which is zero for a null geodesic and is already computed by the
    tracer but was never read. On healthy exterior keyframes the two criteria
    agree set-for-set on all 4096 sampled texels.
  - The escape-direction chart rotation had the WRONG SIGN. The
    momentum-direction azimuth offset is `+aM/r^2` while
    `delta = atan2(a, r) + shift(r)` is `-aM/r^2`, so rotating by `-delta` was
    measurably worse than applying no rotation at all, at every radius tested.
    Fixed to `+delta`: `3.251e-4 deg` against `1.333e-3` unrotated at
    `r_escape = 200M`.
  - The "validated to 0.0026 deg" claim could not have caught that: at
    `r_escape = 200M` the correction is `1.3e-3 deg`, larger than the agreement
    being measured, so the gate passes whether the rotation is right, absent,
    or sign-flipped. The gate now runs at two escape radii and asserts
    `rotationIsImprovement`, which is dimensionless and self-calibrating.
  - The `2.7e-8` energy-consistency figure in the manifest and docstring was
    never produced by any committed code, and is arithmetically impossible: a
    float32 max-abs over `E_inf` in `[0.095, 1.905]` cannot be below one ULP at
    `E ~ 1`, which is `2^-23 = 1.192e-7`. The measured value is `1.196e-7`,
    exactly that floor. The gate therefore uses `4 ULP = 4.8e-7`, deliberately
    LOOSER than the `1e-7` in the task brief, because any threshold below one
    ULP is unachievable in principle. The archived `5.96e-8` is `2^-24`,
    consistent with a float64-vs-float32 comparison rather than the stated one.
  - Dead expression `np.sum(l_cov * eta_p, axis=1) * 0.0` removed; it was also
    mathematically identical to the surviving term.
  - `descent_radius_schedule` margins now scale with `M` (an absolute margin
    was a ~10x weaker buffer in geometric units at `M = 10`), endpoints are
    pinned exactly against `exp(log(r))` overshoot, and a nudge that collapses
    two adjacent radii raises instead of silently requesting duplicate targets.
  - The azimuth unwrap was one-sided and built for increasing azimuth, but the
    ingoing-KS chart azimuth of a prograde rain worldline drifts NEGATIVE
    (`|dr/dtau| > 2M/r`, so the chart twist beats the frame dragging). Now
    unwraps in both directions.
  - `counts` categories are now disjoint: `physicalCapture` is separated from
    `darkPastHorizon`, `hamiltonianRejected` and `otherFailure`, so a reviewer
    can decompose the shadow and detect a blank keyframe.
  - `KsGpuTraceConfig` now requires `disk_r_in` to clear `r_+` by `0.25 M`,
    because the BL azimuth/time shifts used to report a crossing diverge
    logarithmically there and would emit a large finite garbage value.
  - WGSL stride constants are substituted from the Python constants and pinned
    by a test; previously the readback buffer was sized in Python while the
    shader wrote at a hardcoded literal, so a desync would silently offset
    every field rather than fail.
- References: `doran2000newKerrForm` for the rain congruence (indexed with the
  previous commit). No new sources.
- Open issues / next steps: the tetrad is algebraic rather than parallel
  transported, so `azimuthDeg` records a rotation of the observer position, not
  of the frame; disk edges carry no sub-texel coverage in this path; and
  `disk_phi_m` from the KS tracer is wrapped-then-offset rather than the
  unwrapped integrated azimuth the BL tracer stores.

### 2026-08-05 - Kerr-Schild rain observer frame and Stage B gate

- Goal: Add the first observer frame in this project that is defined on both
  sides of the outer horizon, and gate it against an independent closed form
  rather than against its own residuals.
- Changed files / components: extended `src/gr_bh_xr/observers.py` and
  `src/gr_bh_xr/metric_ks.py`; added
  `src/gr_bh_xr/validate_rain_observer.py`; extended
  `tests/test_observers.py`; indexed `doran2000newKerrForm` and
  `hamiltonLisle2008riverModel` with
  `references/source_notes/2026-08-05-kerr-rain-observer.md`.
- Academic reason: The horizon-crossing descent camera cannot use a static or
  ZAMO frame - the static frame already fails at the ergosurface and the BL
  ZAMO helper is exterior-only. The Doran free-fall congruence is regular
  through `r_+` in the ingoing Kerr-Schild chart.
- Physical correspondence: `u_t = -1` (rest at infinity, chart independent
  because `t_KS` and `t_BL` share the same Killing vector); `L_z = 0` via the
  Cartesian axial Killing vector `xi = (0, -y, x, 0)`; `dtheta/dtau = 0`
  expressed as `r u^z = z (grad r . u_spatial)`; and `u.u = -1` taking the
  ingoing future-pointing root. `u^t > 0` is a valid causal test on both sides
  of the horizon because `g^tt = -(1 + 2H) < 0` everywhere in the ingoing
  chart, so `t` is a global time function.
- Assumptions and conventions: the four conditions are consistent, not
  overdetermined - with `E = 1` and `L = 0` the Carter polar potential reduces
  to `Theta = Q` identically, independent of `theta`, so `Q = 0` makes
  `theta = const` an exact solution at every polar angle. Validity is claimed
  between the inner and outer horizons; the mass-inflation region is out of
  scope. The frame is undefined on the symmetry axis and refuses there.
- Validation: `python -m gr_bh_xr.validate_rain_observer` (schema
  `gr-bh-xr.task8.rain_observer_gate.v1`) plus 14 new tests in
  `tests/test_observers.py`. Measured worst cases against thresholds of
  `1e-13`/`1e-12`/`1e-11`: `|u.u+1|` `1.11e-15` outside, `2.11e-15` at
  `r_+ +/- 1e-3`, `9.99e-16` inside; `|u_t+1|` `1.55e-15`; `|L_z|`
  `2.44e-15`; `|dtheta/dtau|` `4.85e-16`; Gram `1.11e-15`/`2.11e-15`/`9.99e-16`;
  `|u - u_analytic|` `3.36e-15`; Schwarzschild `|u^r + sqrt(2M/r)|` `6.66e-16`;
  and `8.88e-16` exactly at `r = r_+`.
- Audit findings acted on:
  - BLOCKER: the normalization quadratic is cancellation-unstable at the
    horizon. The outgoing rain branch diverges as `Delta -> 0` in the ingoing
    chart, driving the quadratic's leading coefficient to zero exactly at
    `r_+`, so the naive `(-b -/+ sqrt(disc)) / (2a)` form loses the solution:
    measured `|u - u_ref|` of `0.048` to `0.15` at `r = r_+`, and an outright
    "no ingoing future-pointing solution" raise at `a = 0`, `theta = pi/2`. The
    Vieta-stable form restores `<= 2.44e-15` everywhere, and the exact-horizon
    case is now a committed regression test.
  - The historical `~1e-10` Schwarzschild "error floor" is not conditioning and
    not physics: it was the worldline sampler recording radii up to `8.8e-7 M`
    off target, propagated through `d/dr[-sqrt(2M/r)]`. The algebraic solve is
    machine-exact at `6.66e-16`. The sampler now bisects onto the requested
    radius (within `4.8e-13`), so the gate no longer documents a defect as a
    tolerance.
  - The sampler previously clamped `samples = np.minimum(samples, r_start)`
    *after* validating strict monotonicity, which could silently merge distinct
    targets into duplicates. It now refuses instead. It also accumulated error
    on every already-passed target (measured up to 20x the target spacing) and
    its 2,000,000-step guard was ~7 minutes of wall clock; both are fixed.
  - `sin(theta)` is computed exactly as `rho / r`. The previous
    `sqrt(max(1 - cos^2, 1e-16))` silently floored for `theta < 1e-8` and
    produced a mis-oriented `e_theta` that still orthonormalized perfectly, so
    no Gram check could detect it (measured `1.2e-5 rad` misorientation with a
    Gram residual of `2.2e-16`). The frame now refuses near the axis, where the
    constraint matrix loses rank and `cond ~ 6/theta`.
  - The Kerr-Schild radius gradient was duplicated in `observers.py` and
    `metric_ks.py`; it is now a single exported `ks_radius_gradient`.
- References: `doran2000newKerrForm` for the constant-`theta` free-fall
  congruence and the consistency of the four conditions;
  `hamiltonLisle2008riverModel` as the interpretive river picture, classified as
  pedagogical and not used to justify any numerical threshold.
- Open issues / next steps: the tetrad is algebraic at each point, not parallel
  transported, so consecutive samples differ from a transported frame by an
  unrecorded rotation - the Stage B transported-frame requirement remains open
  for this frame.

### 2026-08-05 - Audited finite-observer roam keyframes

- Goal: Add the Task 7 `(r_obs, theta)` roam keyframe grid, with the
  near-horizon escape-radius fix it needs, and gate its physics claims with
  real invariants instead of prose.
- Changed files / components: added `src/gr_bh_xr/gpu/generate_roam_keyframes.py`,
  `tests/test_roam_keyframes.py`, `tests/test_roam_mirror_symmetry.py`,
  `validation/roam_keyframes/README.md`; extended `src/gr_bh_xr/gpu/trace.py`
  and `src/gr_bh_xr/gpu/generate_transfer_cubemap.py`; bumped the full-sky
  package schema to `v3`.
- Academic reason: Near-horizon roaming is the first observer-motion claim in
  the project. It must be labelled honestly (quasi-static, no aberration) and
  its two load-bearing claims - that the shadow grows as the observer
  approaches, and that the map respects Kerr's equatorial reflection isometry -
  must be tested rather than asserted.
- Physical correspondence: each keyframe is an independent finite-radius
  static-observer full-sky transfer map. The static tetrad exists only where
  `g_tt < 0`, so every grid point is validated against the outer ergosurface
  `r_E = M + sqrt(M^2 - a^2 cos^2 theta)` before any GPU time is spent. The
  static observer's background-sky blueshift `1/sqrt(-g_tt)` is recorded per
  keyframe. Azimuthal motion is exact by axisymmetry because both launchers
  start the ray at `phi = 0` at the observer.
- Assumptions and conventions: quasi-static roam, not a boosted worldline. The
  azimuthal exactness additionally assumes the disk model is axisymmetric; a
  consumer painting a non-axisymmetric feature from `phi_m` must add the
  observer azimuth back. Radii are geometric code lengths, `r/M` only at
  `M = 1`.
- Validation: `tests/test_roam_keyframes.py` and
  `tests/test_roam_mirror_symmetry.py` (36 tests with `test_gpu_task4.py`, all
  passing). A real face-32 grid at `a/M = 0.9` gives capture solid angle
  `0.000620` at `100M` rising monotonically to `0.551254` (theta = 30 and 150)
  and `0.673544` (theta = 90) at `2.5M`. Mirror symmetry measured over 10800
  ray pairs: 0 event mismatches, 0 one-sided disk records, escape-direction p50
  `0.00078 deg` / p99 `0.0183 deg`, `|delta r_m|` p99 `1.54e-4 M`,
  `|delta g_m|` p99 `1.19e-5`.
- Audit findings acted on:
  - The `[20, 160] deg` theta envelope and its "near-polar Bardeen mapping
    degrades" rationale were transplanted from `gr_bh_xr.gpu.preview`, which
    evaluates the `alpha`/`beta` screen map and its `1/sin(theta_obs)` factor.
    The roam path reaches the tracer through `initial_state_direction`, which
    contains no such factor. A measured sweep found no cliff at either endpoint
    (at most 1 invalid texel of 3456 across `theta = 2..178 deg`, count
    non-monotonic in theta). The envelope is now `[30, 150] deg` - exactly the
    tested grid - and is labelled a tested range rather than a failure
    boundary. A test pins that the Bardeen rationale is not repeated.
  - The shadow gate now uses a solid-angle-weighted capture fraction rather
    than a raw texel count (cube texels do not subtend equal solid angle, and
    the docstring claimed "solid angle" while the code counted texels), reads
    it from the raw pre-repair classification so image repairs cannot move a
    physics gate, and carries a `3 / sqrt(total_pixels)` tolerance because the
    outer keyframes are quantization-limited and a strict comparison would turn
    a multi-hour grid into a spurious failure.
  - The ergosphere margin is `0.1 * M`, not an absolute `0.1`. With the
    absolute value the admitted worst-case static tetrad boost silently
    tightened from `4.58` at `M = 1` to `14.2` at `M = 10`.
  - The WGSL disk-crossing 16x refinement from the snapshot was NOT ported. It
    moves the `disk_order` increment inside a `crossing_found` guard, so a
    dropped crossing silently relabels image order and a secondary (`m = 1`)
    image is written into the primary (`m = 0`) slot with no failure code. Its
    `0.35 rad` trigger is also unreachable for a valid trajectory: the
    spherical-photon-orbit bound at `a/M = 0.9` gives
    `sup |dtheta/dlambda| = 0.8753`, so a normal substep moves at most
    `0.0438 rad`, a factor of 8 below the threshold. It fires only on
    already-diverged states.
  - `_fill_disk_recording_gaps` was NOT ported: it is a heuristic image filter
    whose stated purpose is to paper over crossings the tracer lost, i.e. the
    downstream band-aid for the refinement above.
  - The Kerr-Schild polar-band retrace was NOT ported here: it requires the KS
    tracer's equatorial disk-crossing outputs, which land with the Kerr-Schild
    work. Polar-band texels are counted and flagged `repaired: false` instead of
    being silently left unmarked. Schema is therefore `v3`, not the snapshot's
    `v4`, which claimed a `v3` encoding that never existed in this repository.
  - Fail-closed metadata: every post-trace stage reports `applied`, notes are
    conditional on the stage having run, and `eventCounts` (raw) is separated
    from `shippedEventCounts` (the bytes actually written), which the repair
    stages can legitimately make disagree.
- References: no new sources. The escape-radius and envelope conclusions are
  measurements against this repository's own tracer.
- Open issues / next steps: near-horizon keyframes carry an irreducible
  `~0.13 deg` escape-direction error from accumulated f32 RK4 along the longer
  path, which no escape radius removes. The polar-band retrace and the
  `lambda_budget` rescaling by `1/E` remain open. Widening the theta envelope
  requires a committed near-polar keyframe artifact.

### 2026-08-05 - Dimensionless disk spectrum LUT v2 (inverse Planck locus)

- Goal: Give the Unity disk/sky color path a physically defined *inverse*
  blackbody map, and make both LUT metadata files dimensionally self-describing
  so a consumer cannot silently misread a shape function as a physical flux.
- Changed files / components: `src/gr_bh_xr/disk_spectrum.py`,
  `tests/test_disk_spectrum.py`, `docs/validation_targets.md`,
  `validation/thin_disk_transfer/README.md`.
- Academic reason: Applying a redshift to a broadband RGB source needs an
  emitter temperature. Fitting each source pixel's own chromaticity to the
  Planck locus makes the emitter model explicit and, because the same LUT is
  used forward and backward, makes the map an exact identity at `g = 1`: the
  fit cannot distort an unshifted source color. Previously the alpha channel
  was a constant `1` and unused.
- Physical correspondence: The forward direction is unchanged - max-normalized
  linear sRGB chromaticity of a Planck spectrum, integrated against the Wyman,
  Sloan & Shirley analytic CIE 1931 fits, indexed by log temperature. The new
  inverse uses the dimensionless chromaticity coordinate `u = R / (R + B)`,
  which decreases monotonically along the locus once the cold plateau is
  removed, and returns the log-normalized temperature
  `s = log(T/T_min) / log(T_max/T_min)`. Page-Thorne flux, `T_obs = g T_emit`,
  `g^3` specific-intensity and `g^4` bolometric conventions are untouched.
- Assumptions and conventions: The inversion is a project chromaticity
  heuristic, not a literature-derived spectral fit, and is labelled as such in
  `docs/equations.md`; it ignores the green channel and minimizes no residual.
  Below roughly `1.9e3 K` the clipped sRGB blue channel is exactly zero, so
  `u = 1` on a plateau and chromaticity carries no temperature information.
  Only the hottest plateau member is kept (`44` of `256` rows dropped for the
  default range, emitted as `plateauRowsDropped`), and the writer now fails
  closed when fewer than two rows survive - previously a range such as
  `1000-1800 K`, reachable from the CLI, emitted a silently constant alpha.
  Consequently the inverse SATURATES on the cold side and can never return
  `temperatureMinK`; the reachable floor is published as
  `alphaAnchorTemperatureK`. Alpha is resampled at texel centers of `u`; the
  RGB rows stay endpoint-inclusive in `s`, so the two channels use different
  texture coordinates and both are now written into the metadata.
- Validation: `tests/test_disk_spectrum.py` (20 tests, all passing) adds a
  direct monotonicity/plateau test tied to the blue-clip row, error-path and
  fail-closed tests for `blackbody_locus_inverse`, a chromaticity -> alpha ->
  temperature round trip through an emulated bilinear fetch with clamp
  addressing, explicit hot-end and cold-saturation boundary tests, a producer
  contract test for the exact texel coordinate, and dimensional metadata
  assertions for both LUTs. Measured round-trip worst case on the five-point
  set is `2.52e-4` at `25000 K`, so the deterministic regression bound was set
  to `1e-3` (about `4x` headroom) rather than the loose `3%` per-point
  tolerance, which is retained as the user-facing bound. Hot end: `40000 K`
  recovers as `39652.60 K` (rel `8.68e-3`, the dense worst case). Cold end:
  `1000 K` and `1500 K` both return `1933.06 K` against a `1889.88 K` anchor.
- Corrections found by audit and fixed here: (1) `fluxPeakShape` is NOT
  dimensionless. It carries geometric dimension `length^-2` and scales as
  `M^-2` at fixed `r/M` - measured `peak * M^2 = 4.260486e-3` for
  `M = 1, 2, 10`. The omitted `Mdot / (4 pi)` factor is itself dimensionless in
  `G = c = 1`, so dropping it cannot remove the dimension, and an earlier draft
  of this metadata claimed otherwise, contradicting the existing closed-form
  `M^-2` scaling test three functions away. A numeric `M^-2` gate now ties the
  asset metadata to that test. (2) The metadata must not publish a texel
  coordinate the consumer violates: the exact endpoint-row coordinate
  `(s (samples-1) + 0.5) / samples` is tested on the producer side, while the
  current Unity shader samples with `u = s`. That half-texel offset is worth
  `0.72%` in effective temperature at `samples = 256` and `0.027 M` in radius
  (`0.048` in normalized flux) at `samples = 512`; it is recorded in the
  emitted metadata for the Unity worktree to reconcile rather than silently
  asserted. The alpha channel needs no correction because it is resampled at
  texel centers.
- References: `wyman2013cieMatchingFits`, `cie2019xyz1931Dataset` (already
  indexed); Page & Thorne / Novikov & Thorne entries for the unchanged flux
  conventions. No new sources were needed for this change.
- Open issues / next steps: The color LUT remains broadband RGB chromaticity,
  not a per-star spectral shift, and absolute luminosity still needs
  accretion-rate and distance normalization. The `g = 1` identity is exact in
  the producer but depends on the consumer's division guard, which is Task 9-10
  work. The Unity-side consumer of the v2 alpha channel, and the `u = s`
  sampling reconciliation, are both owned by the Unity worktree.

### 2026-07-09 - Stage B-2 transported free-fall tetrad seed

- Goal: Add the first transported observer tetrad for near-horizon keyframe
  work without using a static-observer frame where it is physically invalid.
- Changed files / components: Extended `src/gr_bh_xr/observers.py` and
  `tests/test_observers.py`.
- Academic reason: Near-horizon playback needs a camera frame attached to an
  observer worldline. A static or merely pushed exterior tetrad is not enough
  once the observer moves or approaches domains where static observers fail.
- Physical correspondence: The seed case is Schwarzschild radial free fall from
  rest at infinity. The initial frame is a Lorentz boost of the static
  Schwarzschild tetrad with local velocity `v = -sqrt(2M/r)`, then pushed into
  ingoing Cartesian Kerr-Schild coordinates. The frame is parallel transported
  along the timelike geodesic using the Kerr-Schild connection.
- Assumptions and conventions: This first transported-frame gate is
  Schwarzschild-only and is not yet a general Kerr/ZAMO/free-fall worldline
  library. Christoffel symbols are computed by finite differencing the
  covariant KS metric, which is acceptable for the CPU reference gate.
- Validation: Tests assert the initial boosted `e_time` equals the geodesic
  four-velocity, Gram matrices remain orthonormal along the path, transported
  `e_time` remains equal to the worldline velocity, and the BL radial velocity
  satisfies `dr/dtau = -sqrt(2M/r)` down to `r = 3M`.
- References: No new literature; this is the analytic Schwarzschild radial
  free-fall limit used as a Stage B transport anchor.
- Open issues / next steps: Extend observer worldlines to Kerr ZAMO, circular,
  and free-fall frames; replace finite-difference connection with analytic
  derivatives if the transported-frame gate becomes a performance path.

### 2026-07-09 - Disk transfer coverage encoding

- Goal: Remove blocky disk-edge artifacts in Unity disk playback without
  changing the underlying Kerr geodesic or disk-transfer physics.
- Changed files / components: Updated
  `src/gr_bh_xr/gpu/generate_transfer_cubemap.py`,
  `xr/unity_frontend/Runtime/BlackHoleLensMap.cs`,
  `xr/unity_frontend/Runtime/BlackHoleLensStaticPreview.shader`,
  `xr/unity_frontend/Editor/GRBHXRGateAutomation.cs`,
  `tests/test_xr_export.py`, and `validation/quest_pcvr/README.md`.
- Academic reason: A binary disk-hit validity texture becomes a display
  artifact when a strong-lensing region magnifies one cubemap texel into many
  screen pixels.  That artifact should not be confused with a physical disk
  feature.
- Physical correspondence: Disk-hit validity is now treated as sub-texel
  coverage at valid/invalid boundaries.  The transfer cube stores
  coverage-premultiplied `r_m`, `sin(phi_m)`, `cos(phi_m)`, and coverage, while
  a companion redshift cube stores coverage-premultiplied `g_m`.  Unity divides
  by coverage before using transfer quantities and uses coverage as opacity.
- Assumptions and conventions: Four-by-four sub-rays are traced only for disk
  validity boundary texels.  Legacy disk cubes without redshift companions still
  fall back to the older `r_m, sin(phi_m), cos(phi_m), g_m` interpretation.
- Validation: Added pure Python packing/boundary tests and Unity source tests
  for the new redshift-cube and shader decoding path.
- References: No new literature; this is a renderer sampling/asset-format
  correction built on the existing disk-transfer validation.
- Open issues / next steps: Regenerate display disk cubemaps before formal
  Quest screenshots.  Stage B transported observer tetrads remain the next
  physics track.

### 2026-07-09 - Unity Page-Thorne disk LUT path

- Goal: Move the Unity disk visual path from a hard-coded color proxy toward
  the validated Page-Thorne/blackbody asset pipeline.
- Changed files / components: Extended `src/gr_bh_xr/disk_spectrum.py`,
  `src/gr_bh_xr/generate_disk_color_lut.py`,
  `xr/unity_frontend/Runtime/BlackHoleLensStaticPreview.shader`,
  `xr/unity_frontend/Runtime/BlackHoleLensMap.cs`,
  `xr/unity_frontend/Editor/GRBHXRGateAutomation.cs`, and related tests/docs.
- Academic reason: A headset-facing disk image should derive its baseline
  color and brightness from auditable transfer quantities, not only from a
  hand-tuned `g` color ramp.
- Physical correspondence: The new Unity path consumes a blackbody color LUT
  indexed by `log(T_obs)` and a radial Page-Thorne table storing normalized
  `F(r)` and `F(r)^(1/4)`.  The shader computes `T_obs = g T_emit` and
  baseline bolometric weight `F(r) g^4`; absolute luminosity remains a
  separate display normalization.
- Assumptions and conventions: The LUTs are one-dimensional RGBA32F textures
  with JSON metadata.  If either LUT is absent, Unity falls back to the older
  documented proxy.  The hot spot remains a transfer-map shortcut on the
  equatorial disk and does not yet consume `Delta t_m`.
- Validation: Targeted tests check raw LUT byte sizes, metadata, monotonic
  log-temperature/radius conventions, `T_shape^4 = F_norm`, and Unity source
  wiring for the shader, loader, and gate automation.
- References: Existing `page1974diskAccretionStructure` and
  `wyman2013cieMatchingFits`.
- Open issues / next steps: Generate a display package with these LUT assets
  and capture a Unity A/B gate against the previous proxy; add `Delta t_m`
  disk cubemap channels before claiming time-delay-aware hot-spot animation.

### 2026-07-09 - Page-Thorne mass scaling and KS shift dedupe

- Goal: Fix the hidden non-`M=1` Page-Thorne closed-form scaling error found in
  review and remove duplicated BL-to-KS shift formulae from the observer bridge.
- Changed files / components: Updated `src/gr_bh_xr/disk_spectrum.py`,
  `src/gr_bh_xr/geodesic_ks.py`, `src/gr_bh_xr/observers.py`,
  `tests/test_disk_spectrum.py`, and thin-disk validation docs.
- Academic reason: The project defaults to `M=1` for validation, but formulas
  that carry physical dimensions must remain correct when asset generation or
  parameter scans choose another mass scale.
- Physical correspondence: The Page-Thorne flux has dimension `M^-2`; the
  root/log closed form now divides by `M^2`, matching the numerical integral.
  The ZAMO-to-KS bridge now reuses the canonical BL-to-KS time and azimuth
  shift helpers from `geodesic_ks.py`.
- Validation: Targeted tests check `M=2`, `a/M=0.9` against the numerical
  integral and require the closed-form value to scale by `1/4` relative to the
  same `r/M` at `M=1`.
- References: Existing `page1974diskAccretionStructure`.
- Open issues / next steps: Integrate the LUT into a Unity disk audit mode and
  keep the flux normalization choices explicit before physical luminosity
  claims.

### 2026-07-09 - Redshifted blackbody LUT generator

- Goal: Finish the CPU-side color asset seed by separating redshifted thermal
  chromaticity from physical brightness weighting.
- Changed files / components: Extended `src/gr_bh_xr/disk_spectrum.py`; added
  `src/gr_bh_xr/generate_disk_color_lut.py`; extended disk-spectrum tests and
  thin-disk validation notes.
- Academic reason: The disk shader needs an auditable route from transfer-map
  redshift `g_m` and disk temperature to displayed color before the current
  visual proxy can be replaced.
- Physical correspondence: The helper applies `T_obs = g T_emit`, records
  `g^3` for specific intensity and `g^4` for bolometric blackbody weighting,
  and writes a blackbody chromaticity LUT in max-normalized linear sRGB.
- Assumptions and conventions: The LUT stores hue/chromaticity only. Brightness
  must remain a separate channel such as `F(r) * g^p`; this prevents the
  max-normalized color table from discarding physical luminosity information.
- Validation: `tests/test_disk_spectrum.py` checks the redshift law, `g^3` and
  `g^4` weights, monotonic LUT temperatures, finite colors, and `.npz` output
  shape.
- References: Existing `wyman2013cieMatchingFits` and CIE 1931 data reference.
- Open issues / next steps: Package the LUT into Unity texture assets and add a
  disk shader audit mode that displays Page-Thorne color/brightness against the
  CPU transfer plots.

### 2026-07-09 - Page-Thorne closed-form flux gate

- Goal: Add an independent analytic reference for the CPU Page-Thorne flux
  shape instead of validating the disk color seed only by limiting cases.
- Changed files / components: Extended `src/gr_bh_xr/disk_spectrum.py` and
  `tests/test_disk_spectrum.py`; updated disk equations, validation targets,
  thin-disk transfer notes, and the disk-color source note.
- Academic reason: The numerical radial integral should be checked against the
  Page-Thorne closed form before it is used for disk color LUTs or Unity
  shader replacement work.
- Physical correspondence: The closed form uses `x = sqrt(r/M)` and the three
  roots of `x^3 - 3 x + 2 a = 0`, matching the zero-torque Page-Thorne flux
  shape for nonzero Kerr spin.
- Assumptions and conventions: The root/log helper is currently the nonzero
  spin analytic gate. The Schwarzschild limit remains covered by its own
  circular-orbit and ISCO/flux tests.
- Validation: `tests/test_disk_spectrum.py` compares the numerical integral
  and closed form for `a = 0.9` across radii from just outside ISCO to `20M`
  with relative tolerance `3e-6`; it also verifies the `a = 0.998`
  radiative-efficiency anchor `1-E_ISCO = 0.320994`.
- References: Existing `page1974diskAccretionStructure` source note.
- Open issues / next steps: Add the redshifted temperature/intensity LUT output
  and then wire it into the Unity disk shader as a separate visual gate.

### 2026-07-09 - ZAMO near-horizon probe and KS chart bridge

- Goal: Add the first Stage B-2 bridge from exterior BL observer frames to
  Cartesian Kerr-Schild coordinates without claiming a transported worldline
  tetrad.
- Changed files / components: Extended `src/gr_bh_xr/observers.py`,
  exposed `bl_to_ks_jacobian` from `src/gr_bh_xr/geodesic_ks.py`, expanded
  `tests/test_observers.py`, and updated equation/validation notes.
- Academic reason: Near-horizon keyframes will launch rays in Kerr-Schild
  coordinates, but the reviewed ZAMO/LNRF frame is currently formulated in BL
  exterior coordinates. The chart bridge lets those facts coexist explicitly.
- Physical correspondence: The exterior probe records
  `omega -> Omega_H = a/(2 M r_+)` and `lapse proportional to sqrt(r-r_+)`.
  The pushed tetrad uses `partial x_KS^mu / partial x_BL^nu` and is verified
  against the Kerr-Schild metric.
- Assumptions and conventions: The pushed tetrad is a coordinate transform of
  an exterior observer basis. It is not a Fermi-Walker or parallel-transported
  camera frame and is not a formal horizon-crossing gate.
- Validation: `tests/test_observers.py` checks the horizon-limit scaling probe
  and the Kerr-Schild Gram matrix of the pushed ZAMO tetrad.
- References: Existing `bardeen1972rotatingBlackHoles` and Kerr-Schild
  validation references.
- Open issues / next steps: Add actual observer worldlines and transported
  tetrads before near-horizon roaming keyframe claims.

### 2026-07-09 - Page-Thorne disk color CPU seed

- Goal: Start the physically stronger disk-color path that will eventually
  replace the Unity power-law disk emissivity proxy.
- Changed files / components: Added `src/gr_bh_xr/disk_spectrum.py` and
  `tests/test_disk_spectrum.py`; updated equation, validation, thin-disk
  transfer, and reference documentation.
- Academic reason: The visual disk shader should not become the permanent disk
  emission model. A Page-Thorne flux shape and blackbody/CIE color path provide
  auditable CPU-side asset-generation primitives before Unity integration.
- Physical correspondence: The helper implements circular-orbit `E`, `L_z`,
  Keplerian `Omega`, a Page-Thorne-style zero-torque radial flux integral,
  `T_eff proportional to F^(1/4)`, Planck spectra, analytic CIE 1931 XYZ fits,
  and max-normalized linear sRGB chromaticity.
- Assumptions and conventions: The flux helper returns a dimensionless shape;
  accretion-rate normalization, black-hole mass scaling, absolute luminosity,
  limb darkening, optical depth, and Page-Thorne returning radiation are not
  included in this seed.
- Validation: `tests/test_disk_spectrum.py` checks the Schwarzschild circular
  orbit anchor `E(r=6M)=sqrt(8/9)`, `L_z(r=6M)=sqrt(12)`, zero flux at ISCO,
  positive Schwarzschild/Kerr flux outside ISCO, and a `6504K` blackbody
  chromaticity near the expected D65-like Planckian locus.
- References: Added `page1974diskAccretionStructure`,
  `wyman2013cieMatchingFits`, `cie2019xyz1931Dataset`, and
  `references/source_notes/2026-07-09-disk-color-sources.md`.
- Open issues / next steps: Export a display LUT and replace the Unity disk
  proxy in a separate audited gate; add Page-Thorne normalization choices before
  making physical luminosity claims.

### 2026-07-09 - Stage B ZAMO observer tetrad seed

- Goal: Start Stage B observer work with an exterior ZAMO / LNRF tetrad before
  implementing worldline transport or near-horizon keyframe playback.
- Changed files / components: Added `src/gr_bh_xr/observers.py` and
  `tests/test_observers.py`; updated equations, validation targets, and the
  Kerr-Schild validation README.
- Academic reason: Static observers fail in the Kerr ergoregion. Near-horizon
  transfer-map keyframes need observer frames whose physical domain is explicit
  before any roaming or falling-camera claim.
- Physical correspondence: The ZAMO angular velocity is
  `omega = -g_tphi / g_phiphi = 2 M a r / A`, the lapse is
  `alpha = sqrt(Sigma Delta / A)`, and the BL exterior tetrad is checked by
  `g_mu nu e_(a)^mu e_(b)^nu = eta_(a)(b)`.
- Validation: `tests/test_observers.py` verifies the analytic `omega` and
  lapse formulae, tetrad orthonormality, static-tetrad failure inside the
  equatorial ergoregion at `a = 0.9`, `r = 1.8M`, and far-field convergence
  between ZAMO and static tetrads at `r = 1e4M`.
- References: Existing `bardeen1972rotatingBlackHoles` LNRF reference.
- Open issues / next steps: Add circular/free-fall worldlines and transported
  tetrads; the current BL ZAMO helper is not yet a full near-horizon roaming
  camera or Kerr-Schild transported frame.

### 2026-07-09 - Finite-sphere lens gate detection repair

- Goal: Repair the finite-distance weak-lens gate after review showed that a
  large DOP853 step could pass through a finite target without an endpoint
  sign change.
- Changed files / components: Updated `src/gr_bh_xr/geodesic_ks.py` sphere
  target detection, `src/gr_bh_xr/validate_ks_finite_lens.py`,
  `src/gr_bh_xr/gpu/trace_ks.py`, finite-lens/GPU tests, references, and
  Kerr-Schild validation documentation.
- Academic reason: A finite-distance object gate must test the physical
  geodesic path, not an artifact of accepted solver step endpoints. The
  previous weak-lens number underreported the real offset from the first-order
  Einstein angle because true sphere hits were being missed.
- Physical correspondence: The CPU reference now records closest approach and
  bisects dense output to the front sphere surface. The GPU path checks the
  closest point on each RK4 segment. The weak-field lens anchor now compares
  the refined hit-band center against both the Schneider/Ehlers/Falco
  first-order Einstein angle and Keeton/Petters' second-order Schwarzschild
  bending correction.
- Validation: Formal `D_L = 10000M`, `D_LS = 5000M`, target-radius `5M` run
  reported `object_hit = 33`, `escape = 48`, refined center
  `0.011695993464709488 rad`, first-order relative offset `1.290e-2`, and
  second-order residual `1.49e-4`. A scaled `D_L = 40000M`,
  `D_LS = 20000M` run reported first-order offset `6.414e-3` and
  second-order residual `3.73e-5`. The GPU finite-object gate now has CPU/GPU
  counts `object_hit = 35`, `escape = 46`, total mismatch `0`, stable
  agreement `1.0`, and GPU `max |H| = 6.37e-6`.
- References: Added `keeton2005testingGravityLensingI`; updated
  `references/source_notes/2026-07-08-finite-distance-lensing-anchor.md`.
- Open issues / next steps: The finite-sphere target is still a static sphere.
  Moving finite objects and near-horizon observer redshift require the Stage B
  observer worldline/tetrad work.

### 2026-07-08 - Kerr-Schild frustum realtime benchmark

- Goal: Add the Task 4 decision gate that measures whether the current WGSL
  Kerr-Schild kernel can support headset-rate near-horizon realtime tracing.
- Changed files / components: Extended `src/gr_bh_xr/gpu/benchmark_latency.py`
  with `--mode ks-frustum`; added parser/frustum-direction tests; updated
  `docs/validation_targets.md` and `validation/kerr_schild/README.md`.
- Academic reason: The project must not infer realtime near-horizon feasibility
  from offline transfer-map screenshots. The pass/fail quantity is measured
  milliseconds per frustum, not whether an image can be generated eventually.
- Physical correspondence: The benchmark launches finite-observer KS tetrad
  rays through a `100 deg` frustum at `r_obs = 20, 10, 5, 3, 2M`, using the
  horizon-penetrating f32 KS kernel. Disk crossings are explicitly disabled in
  this shader path; sphere targets are available but off in the formal timing
  runs.
- Assumptions and conventions: The timings include WGPU dispatch/readback and
  event summary, but exclude Python initial-state construction and Unity upload.
  Single-eye median `< 11 ms` is required before claiming 90 Hz low-resolution
  realtime tracing.
- Validation: On the RTX 5080 Laptop GPU, `a = 0.9`, `i = 60 deg`, `100 deg`
  FOV runs measured `17.3-22.4 ms` at `128x128`, `67.9-79.6 ms` at `256x256`,
  and `266.1-301.6 ms` at `512x512` across `r_obs = 20, 10, 5, 3, 2M`.
- References: Existing KS and validation references; no new source added.
- Open issues / next steps: Treat current KS tracing as keyframe/offline or
  parameter-update infrastructure. Headset-rate free flight needs foveated
  tracing, lower resolution, keyframe playback, or an audited surrogate.

### 2026-07-08 - Kerr-Schild GPU finite-sphere intersection gate

- Goal: Finish Task 3's first GPU path by validating WGSL finite-sphere
  intersections against the CPU Kerr-Schild reference.
- Changed files / components: Extended `src/gr_bh_xr/gpu/trace_ks.py` with an
  optional sphere target and `object_hit` event; added
  `src/gr_bh_xr/gpu/validate_ks_finite_object.py`; extended GPU tests and
  validation documentation.
- Academic reason: A finite-distance object path is only useful for MR/local
  objects if the GPU kernel can classify the same object hits as the CPU
  reference and report boundary differences honestly.
- Physical correspondence: The WGSL kernel evaluates the same Cartesian
  condition `|x - c| <= R` during KS RK4 integration. The event is distinct
  from capture/escape and preserves the existing event-code meanings for older
  buffers.
- Assumptions and conventions: The first GPU comparison is Schwarzschild and
  static. A one-sample object-edge band is excluded from the stable pass/fail
  metric because fixed-step f32 endpoint detection and CPU root finding can
  disagree exactly at the finite sphere limb.
- Validation: Formal `D_L = 1000M`, `D_LS = 500M`, target-radius `10M`,
  `81`-sample run produced CPU events `object_hit = 34`, `escape = 47`; GPU
  events `object_hit = 35`, `escape = 46`; total event mismatch `1`;
  edge-band mismatch `1`; stable-event mismatch `0`; stable-event agreement
  `1.0`; GPU failures `0`; GPU `max |H| = 6.49e-6`.
- References: Uses the existing finite-distance lensing source note; no new
  source added.
- Open issues / next steps: Extend from spherical static targets to richer
  finite objects and use the KS kernel in the frustum realtime benchmark.

### 2026-07-08 - Kerr-Schild finite-distance weak-field lens anchor

- Goal: Add the Task 3 weak-field finite-distance lensing equation anchor for
  the KS sphere-target path.
- Changed files / components: Added `src/gr_bh_xr/validate_ks_finite_lens.py`
  and `tests/test_validate_ks_finite_lens.py`; updated `references/`,
  `docs/validation_targets.md`, and `validation/kerr_schild/README.md`.
- Academic reason: A local object-hit event is not enough by itself; the
  finite-distance target path needs a standard weak-field point-lens limit
  before it can support claims about local-object lensing.
- Physical correspondence: In geometric units, the aligned point-mass Einstein
  angle is `theta_E^2 = 4M D_LS / (D_L D_S)`. The formal gate uses
  `D_L = 10000M`, `D_LS = 5000M`, and a finite sphere of radius `5M`, then
  compares the center of the hit-angle band with the point-source `theta_E`.
- Assumptions and conventions: The Schneider/Ehlers/Falco equation is used as
  a far-field weak-lens anchor. The closer `D_L = 200M`, `D_LS = 100M` case is
  not treated as a strict one-line formula gate because higher-order
  finite-distance/strong-field corrections are already visible.
- Validation: Formal run produced `theta_E = 0.011547005383792516 rad`,
  measured hit-band center `0.011622782606623652 rad`, relative error
  `6.56e-3`, and event counts `object_hit = 18`, `escape = 63`.
- References: Added `schneider1992gravitationalLenses` and
  `references/source_notes/2026-07-08-finite-distance-lensing-anchor.md`.
- Open issues / next steps: Migrate finite sphere intersections to WGSL and
  run CPU/GPU comparison; later extend from static sphere targets to moving
  finite objects and MR environment proxies.

### 2026-07-08 - Kerr-Schild finite-distance sphere target seed

- Goal: Start Task 3 by adding a CPU Kerr-Schild finite-distance object event
  before weak-field lens-equation and GPU migration gates.
- Changed files / components: Updated `src/gr_bh_xr/geodesic_ks.py` with
  `KSSphereTarget`, object-hit diagnostics, and a static-object redshift helper;
  added KS geodesic regression tests; updated `docs/validation_targets.md` and
  `validation/kerr_schild/README.md`.
- Academic reason: Local finite-distance objects are a separate physical path
  from background cubemap lensing. The tracer needs an explicit object-hit
  event before MR room objects, sphere targets, or finite-source lensing can be
  claimed.
- Physical correspondence: A sphere target is represented in Cartesian
  Kerr-Schild coordinates by `|x - c| - R = 0`. For a static object outside the
  ergoregion, the recorded redshift uses
  `g = E / (-p_mu u_static^mu)` with `u_static^t = 1 / sqrt(-g_tt)`. Static
  worldlines inside `g_tt >= 0` are rejected with `NaN` rather than treated as
  physical emitters.
- Assumptions and conventions: This is a CPU reference seed only. It does not
  yet implement the weak-field finite-distance lens-equation anchor, GPU sphere
  intersections, or generic moving-object tetrads.
- Validation: Added a Schwarzschild straight-through sphere-hit test from
  `r_obs = 50M` to a target centered at `20M`, confirming the front-surface hit
  and `sqrt(1 - 2M/r_hit)` static redshift, plus a test that static observers
  inside the Schwarzschild horizon are rejected.
- References: Existing Kerr-Schild and lensing references; no new source added
  in this seed step.
- Open issues / next steps: Add the weak-field finite-distance lens equation
  reference and anchor, then migrate sphere intersections to the WGSL KS kernel
  for CPU/GPU comparison.

### 2026-07-08 - Kerr-Schild photon-shell f32 floor policy

- Goal: Record the post-review reinterpretation of the KS GPU photon-shell
  direction tail and prevent future tuning work from treating it as a simple
  step-size truncation problem.
- Changed files / components: Updated `validation/kerr_schild/README.md`,
  `docs/validation_targets.md`, and this log.
- Academic reason: The validation layer must distinguish ordinary weak-field
  transfer accuracy from near-critical photon-shell behavior, where small f32
  trajectory differences are exponentially amplified.
- Physical correspondence: Step-size scans showed the shell-band direction
  error worsens as the effective f32 RK4 step is made smaller:
  `h = 0.001` fixed gave `3.42e-1 rad`, `h = 0.005` with floor `1.82e-2 rad`,
  current `h = 0.01` with floor `9.66e-3 rad`, and the previous no-floor
  shell step `h ~= 0.024` `1.83e-3 rad`. This is consistent with f32 roundoff
  random walk amplified by photon-shell Lyapunov sensitivity.
- Assumptions and conventions: `photon_shell_proxy` remains a diagnostic band,
  not a hard f32 direction threshold. Offline near-critical keyframes should
  CPU-f64 retrace texels near the analytic critical curve; realtime paths
  should document `~1e-3` to `~1e-2 rad` photon-ring direction noise.
- Validation: No solver code changed. The policy is based on the reviewed
  local step-scan artifacts generated under ignored `outputs/tier2/`.
- References: Existing Kerr photon-shell and Kerr-Schild references; no new
  source added.
- Open issues / next steps: Implement finite-distance object intersection, then
  use this mixed-precision policy when the frustum realtime benchmark and
  transfer-keyframe path reach the photon-ring band.

### 2026-07-08 - Kerr-Schild GPU low-radius observer gate

- Goal: Add the dedicated low-`r_obs` finite-observer gate needed before using
  the KS GPU kernel for realtime-cost or near-horizon transfer-map claims.
- Changed files / components: Added
  `src/gr_bh_xr/gpu/validate_ks_near_horizon.py`; extended
  `src/gr_bh_xr/gpu/validate_ks.py` with explicit `r_escape`; updated GPU
  tests, `docs/validation_targets.md`, and `validation/kerr_schild/README.md`.
- Academic reason: The default `r_obs = 100M` Task 2 gate had too little
  statistical power in the near-horizon exterior band. Low-radius observers
  must be checked directly before frustum benchmarks can be interpreted as
  near-horizon evidence.
- Physical correspondence: The gate samples finite-observer full-sky directions
  at `r_obs = 10M, 5M, 3M` using the same static-observer tetrad initializer,
  then compares CPU f64 KS traces with GPU f32 KS traces while keeping the
  escape sphere fixed at `r_escape = 200M`.
- Assumptions and conventions: This remains a transfer-map validation, not
  free-flight. It validates event classification and escaped momentum
  directions for static low-radius observers; arbitrary worldlines and moving
  observers remain Stage B/C work.
- Validation: Formal `a = 0.9`, `i = 60 deg`, `256`-direction-per-radius gate
  produced minimum resolved/stable event agreement `1.0`, total
  both-unclassified max-lambda samples `0`, total GPU failures outside
  exclusions `0`, and `10` near-horizon-exterior escaped-direction samples.
  Median/max escaped-direction errors were `7.52e-7/1.23e-5 rad` at `10M`,
  `1.23e-6/1.02e-4 rad` at `5M`, and `2.57e-6/4.56e-5 rad` at `3M`.
- References: Existing Kerr-Schild and Kerr geodesic references; no new source
  added.
- Open issues / next steps: Proceed to finite-distance object intersections and
  then the frustum-only realtime benchmark that measures `r_obs = 20, 10, 5,
  3, 2M` cost curves.

### 2026-07-08 - Kerr-Schild GPU photon-shell step audit

- Goal: Fix the Task 2 WGSL Kerr-Schild adaptive-step rule after the new
  min-radius band report showed a photon-shell direction-error regression.
- Changed files / components: Updated `src/gr_bh_xr/gpu/trace_ks.py`,
  `src/gr_bh_xr/gpu/validate_ks.py`, `tests/test_gpu_task4.py`,
  `docs/validation_targets.md`, and `validation/kerr_schild/README.md`.
- Academic reason: The GPU KS gate must not claim ordinary weak-field
  direction accuracy for Lyapunov-sensitive photon-shell grazing rays, and it
  must avoid a step rule that silently enlarges the strong-field RK4 step.
- Physical correspondence: The shader now uses
  `h = h0 * max(1, r / r_ref)` with `r_ref = 5M`; rays with `r <= 5M` keep the
  strong-field step floor `h0 = 0.01M`, while weak-field rays still receive the
  intended acceleration. The validator now reports a weak-outer band
  (`min_r > 5.5M`) separately from a photon-shell proxy band
  (`r_+ + max(0.1M, 2 horizon_eps) < min_r <= 5.5M`).
- Assumptions and conventions: Photon-shell proxy direction errors are
  diagnostic evidence for the f32 fixed-step kernel, not the same pass/fail
  quantity as weak-outer escaped-direction accuracy. Event classification,
  failure accounting, and Hamiltonian residuals remain part of the formal gate.
- Validation: The formal `a = 0.9`, `i = 60 deg`, `677`-sample gate with
  `max_lambda = 800M` produced `both_unclassified_max_lambda = 0`,
  `resolved_event_agreement = 1.0`, `stable_event_agreement = 1.0`, and
  `gpu_failure_outside_exclusions = 0`. Weak-outer escaped-direction errors
  were median `1.15e-6 rad` and max `7.49e-5 rad`; weak-outer GPU `max |H|`
  was `8.63e-6`. The photon-shell proxy band had `50` escaped-direction
  samples, median `7.55e-5 rad`, max `9.66e-3 rad`, and GPU `max |H| =
  6.07e-6`, confirming that the remaining direction tail is a near-critical
  f32 sensitivity rather than a Hamiltonian blow-up.
- References: Existing Kerr-Schild and Kerr photon-shell references; no new
  source added.
- Open issues / next steps: Add the dedicated low-`r_obs` near-horizon fan
  gate before using this kernel for realtime-cost claims, then proceed to
  finite-distance object intersections and frustum latency benchmarking.

### 2026-07-08 - WGSL Kerr-Schild tracer gate

- Goal: Start Task 2 by validating a WGPU f32 Kerr-Schild Hamiltonian RK4
  kernel against the CPU f64 KS reference.
- Changed files / components: Added `src/gr_bh_xr/gpu/trace_ks.py`,
  `src/gr_bh_xr/gpu/validate_ks.py`, and GPU tests; updated
  `docs/validation_targets.md` and `validation/kerr_schild/README.md`.
- Academic reason: Near-horizon keyframes and any future realtime tracer need a
  GPU path that removes BL horizon/axis coordinate failures while remaining
  comparable to the audited CPU reference.
- Physical correspondence: The shader integrates explicit Cartesian
  Kerr-Schild canonical states with the same inverse metric and analytic
  derivative structure as `geodesic_ks.py`. Initial states are still generated
  on the CPU, so this gate isolates the GPU metric/RHS migration from camera
  initialization.
- Assumptions and conventions: The path is f32 fixed-step RK4 and is not yet
  arbitrary observer-worldline tracing, finite-distance object intersection, or
  headset-rate near-horizon free flight. Horizon-crossing Hamiltonian residuals
  are reported as f32 diagnostics, not compared to the CPU exterior `1e-8`
  target.
- Validation: The first fixed-budget gate exposed that `303/677` samples were
  both-side max-lambda unclassified. The revised adaptive-step `a = 0.9`,
  `i = 60 deg`, `max_lambda = 800M` gate with `55`-sample screen fans at
  `beta = 0, +4, -4` plus deterministic full-sky directions produced
  `sample_count = 677`, `both_unclassified_max_lambda = 0`,
  `resolved_event_agreement = 1.0`, `stable_event_agreement = 1.0`,
  `gpu_failure_outside_exclusions = 0`, escaped-direction median/RMS/max
  errors of `1.98e-6`, `1.05e-4`, and `1.83e-3 rad`, and GPU `max |H|` bands
  of `2.92e-6` outer, `4.39e-6` near-horizon exterior, and `5.08e-5`
  horizon-crossing. GPU step distribution was median `223`, p95 `905.2`, and
  max `1218`, replacing the previous far-zone many-thousand-step waste.
- References: Existing Kerr-Schild and Kerr geodesic references; no new source
  added.
- Open issues / next steps: Add a dedicated low-`r_obs` near-horizon fan
  because the formal gate has only `3` near-horizon exterior escaped-direction
  samples. Then add finite-distance object intersections and a frustum-only
  latency benchmark before deciding whether Tier 2.5 can use live GPU tracing
  or must remain keyframe/surrogate based.

### 2026-07-08 - Unity disk hot-spot lookup controls

- Goal: Add a first interactive disk hot-spot visual mode over the existing
  transfer cubemap without claiming runtime geodesic integration.
- Changed files / components: Extended the Unity preview shader, runtime disk
  settings, XR controller controls, settings panel, Unity README, and validation
  target notes.
- Academic reason: A localized disk feature is the simplest finite-distance
  source that can be moved interactively while staying inside the validated
  stationary axisymmetric transfer-map contract.
- Physical correspondence: The hot spot is evaluated in disk coordinates using
  `(r_m, sin(phi_m), cos(phi_m), g_m)`. Its observed brightness follows the
  existing `g^p` convention and optional Keplerian phase advection
  `phi0 + Omega(r0) t`.
- Assumptions and conventions: This Unity texture path currently lacks a
  separate `Delta t_m` channel, so the visual hot-spot animation does not yet
  include light-travel-time delay. The HDF5 transfer buffers remain the audit
  source for delayed disk variability.
- Validation: Shader/C# changes are scoped to existing material properties and
  runtime controls. Full Unity batch screenshots remain the required gate before
  using this as a visual claim.
- References: Existing disk-transfer references; no new source added.
- Open issues / next steps: Add a display texture channel for `Delta t_m`, then
  capture four hot-spot desktop screenshots covering direct/secondary,
  approaching, and receding disk features.

### 2026-07-08 - Kerr-Schild critical-curve regression

- Goal: Close the KS Stage A shadow-boundary gate by comparing the KS
  capture/escape boundary with the analytic Kerr critical curve.
- Changed files / components: Added `src/gr_bh_xr/validate_ks_critical_curve.py`
  and `tests/test_validate_ks_critical_curve.py`; updated
  `docs/validation_targets.md` and `validation/kerr_schild/README.md`.
- Academic reason: The horizon-penetrating tracer must recover the same
  spherical-photon-orbit shadow boundary as the validated BL solver before it
  can be used as the reference path for near-horizon keyframes.
- Physical correspondence: The analytic curve is still the Bardeen/Gralla
  spherical photon orbit screen curve. Only the numerical classifier changes
  from BL exterior capture to KS horizon-penetrating capture.
- Assumptions and conventions: The gate tests fixed-observer screen
  coordinates at `r_obs = 100M`; it does not yet validate arbitrary observer
  worldlines or finite-distance objects.
- Validation: Formal `a = 0.9`, `i = 60 deg`, `48`-angle KS gate passed with
  `center alpha = 0.9359348514M`, `max_abs_error = 0.0027052051M`,
  `rms_error = 0.0004011217M`, `invalid = 0`, `max |H|_KS = 4.77e-8`, and
  `min_r = 1.4158898944M`.
- References: Existing Kerr critical-curve references
  (`bardeen1973kerrGeodesics`, `gralla2020nullGeodesicsKerr`); no new source
  added.
- Open issues / next steps: Add the denser full-sky KS/BL exterior gate, then
  migrate the KS RHS to WGSL for Task 2.

### 2026-07-08 - Kerr-Schild exterior Carter diagnostic

- Goal: Add a Carter `Q` drift diagnostic to the KS tracer without pretending
  that BL coordinates remain valid through the horizon.
- Changed files / components: Extended `src/gr_bh_xr/geodesic_ks.py`,
  `tests/test_geodesic_ks.py`, `docs/validation_targets.md`, and
  `validation/kerr_schild/README.md`.
- Academic reason: Carter drift is an independent integrator diagnostic for
  Kerr null geodesics, but the scalar is easiest to evaluate in BL coordinates.
  The diagnostic therefore needs an explicit exterior-only contract.
- Physical correspondence: KS states are converted back to BL only when the
  sample radius is safely outside `r_+` and away from the axis. Samples inside
  the horizon are skipped and counted, while `H`, `E`, and `L_z` remain native
  KS diagnostics across the crossing.
- Assumptions and conventions: `q_drift_abs` is an exterior diagnostic. It is
  not used to validate the interior segment of a horizon-penetrating ray.
- Validation: `tests/test_geodesic_ks.py` passed. Representative `a = 0.9`,
  `i = 60 deg`, escaped ray had `q_drift_abs = 1.60e-10` over `307` exterior
  samples. A Schwarzschild captured equatorial ray had `q_drift_abs = 1.37e-31`,
  `q_sample_count = 127`, and `q_skipped_count = 3`.
- References: Existing Carter/Kerr geodesic references; no new source added.
- Open issues / next steps: Add KS critical-curve regression and then migrate
  the KS RHS into WGSL.

### 2026-07-08 - Kerr-Schild disk-transfer cross-check

- Goal: Add the first KS equatorial disk-crossing gate and compare it against
  the existing BL thin-disk transfer semantics.
- Changed files / components: Extended `src/gr_bh_xr/geodesic_ks.py` with
  non-terminal `z = 0` crossing records, added
  `src/gr_bh_xr/validate_ks_disk_transfer.py`, and added unit coverage for KS
  disk crossings and the BL-vs-KS disk-transfer comparison.
- Academic reason: Near-horizon keyframes and finite-distance transfer maps
  need the horizon-penetrating tracer to preserve the same `(r_m, phi_m, g_m,
  Delta t_m)` contract as the audited BL disk-transfer pipeline before GPU or
  Unity consumers use the data.
- Physical correspondence: Crossing order `m` remains the true equatorial
  crossing order. KS crossing states are converted back to exterior BL
  coordinates only for ring hits where the disk transfer is defined; the BL
  azimuth removes the ingoing Kerr-Schild `_phi_shift`.
- Assumptions and conventions: The current disk gate is an exterior annulus
  comparison and does not claim BL validity through the horizon. Carter `Q` and
  KS critical-curve regression remain separate Stage A gates.
- Validation: Small Kerr grid smoke test passed with
  `disk_validity_mismatch_count = 0`, `compare_sample_count = 35`,
  `max |Delta r_m| = 2.23e-8 M`, `max |Delta phi_m| = 2.10e-10 rad`,
  `max |Delta t_m| = 5.11e-9 M`, `max |Delta g_m| = 1.10e-10`, and
  `max |H|_KS = 6.56e-10`. Formal `64x64`, `a = 0.9`, `i = 60 deg` gate with
  `workers = 8` passed with `event_mismatch_count = 0`,
  `disk_validity_mismatch_count = 0`, `valid_by_order = [1900, 60]`,
  `compare_sample_count = 1960`, `max |Delta r_m| = 2.37e-7 M`,
  `max |Delta phi_m| = 4.80e-9 rad`, `max |Delta t_m| = 2.47e-7 M`,
  `max |Delta g_m| = 4.34e-9`, and `max |H|_KS = 9.58e-9`.
- References: Existing disk-transfer references (`bardeen1972rotatingBlackHoles`
  and `cunningham1975kerrDiskSpectrum`); no new source added.
- Open issues / next steps: Run the formal `64x64` disk gate, add exterior
  Carter `Q` diagnostics, and add the KS critical-curve regression.

### 2026-07-08 - Kerr-Schild BL cross-chart fan gate

- Goal: Version the reviewed BL-vs-KS fan cross-check as a reproducible
  validation command rather than leaving it as an external audit note.
- Changed files / components: Added `src/gr_bh_xr/validate_ks_bl_crosscheck.py`,
  `tests/test_validate_ks_bl_crosscheck.py`, and
  `validation/kerr_schild/README.md`; updated `docs/validation_targets.md`.
- Academic reason: The KS tracer must prove that it agrees with the already
  validated BL exterior solver on event classification and the escaped momentum
  direction consumed by transfer maps before it can be used for keyframes.
- Physical correspondence: The validation samples a screen-coordinate fan,
  traces each ray in both charts, transforms escaped KS final states back to BL
  only in the exterior, and compares momentum-derived escape directions.
- Assumptions and conventions: This gate tests exterior rays and explicitly
  separates hard event disagreements from BL coordinate failures that KS
  resolves. It does not yet test disk crossings, Carter `Q`, or the Kerr
  critical curve with the KS tracer.
- Validation: `python -m pytest tests/test_validate_ks_bl_crosscheck.py -q`
  passed with `3 passed`. Formal fan runs for `a = 0.9`, `i = 60 deg` and
  `i = 90 deg`, `alpha in [-8M, 8M]`, `beta = 0`, and `55` rays produced
  `both_valid_event_mismatches = 0` and maximum escaped-direction error
  `2.1073424255447017e-08 rad` in both cases. The non-equatorial
  `beta = +4` / `beta = -4`, `25`-ray fans had one `bl_invalid_ks_valid` sample
  each, zero hard event mismatches, zero `ks_invalid_bl_valid` samples, and
  bounded KS residuals (`6.13e-9` and `3.43e-9` maximum `|H|`). This records the
  first automated evidence that KS cures BL polar-axis chart failure for
  `L_z = 0` rays.
- References: Existing BL/Kerr and Kerr-Schild references; no new source added.
- Open issues / next steps: Add disk events and Carter diagnostics to the KS
  tracer, then run KS critical-curve regression.

### 2026-07-08 - Kerr-Schild escape-direction gate

- Goal: Strengthen the Kerr-Schild seed tracer with end-state diagnostics and
  the first BL-vs-KS escaped-ray direction comparison.
- Changed files / components: Extended `src/gr_bh_xr/geodesic_ks.py` with
  final state/momentum output, `ks_state_to_bl_state`, and a capture-surface
  clamp that stays outside the Cauchy horizon for near-extremal spins; extended
  `tests/test_geodesic_ks.py`.
- Academic reason: Event classification alone is too weak for cross-chart
  validation. Escaped-ray momentum direction is the transfer-map quantity that
  Unity consumes for background lensing, so KS must agree with the existing BL
  reference there before it can support future keyframes.
- Physical correspondence: The KS final state is transformed back to BL
  coordinates only in the exterior escape region, where the BL chart is valid
  for diagnostics. Horizon-crossing evidence remains native KS. The inner
  capture surface is now `max(r_- + margin, r_+ - eps)` rather than blindly
  stepping toward the Cauchy horizon when the spin is near extremal.
- Assumptions and conventions: The first escape-direction test is a single
  representative Kerr ray. Dense full-sky KS-vs-BL sampling and critical-curve
  regression are still separate gates.
- Validation: `python -m pytest tests/test_geodesic_ks.py -q` passed with
  `5 passed`; full-suite validation is recorded in the commit checklist.
- References: Same Kerr-Schild and Kerr geodesic references as previous Stage A
  entries.
- Open issues / next steps: Add dense exterior BL-vs-KS sampling, disk crossing
  in KS coordinates, Carter `Q` diagnostics, and Kerr critical-curve regression.

### 2026-07-08 - Kerr-Schild Hamiltonian tracer seed

- Goal: Add the first CPU Kerr-Schild Hamiltonian tracer and cross-chart state
  transform after the metric primitive review passed.
- Changed files / components: Added `src/gr_bh_xr/geodesic_ks.py`; extended
  `tests/test_metric_ks.py` with determinant/Killing-norm invariants; added
  `tests/test_geodesic_ks.py`; updated `docs/equations.md` and
  `docs/validation_targets.md`.
- Academic reason: The next near-horizon gate needs a horizon-penetrating
  integrator whose first evidence is exterior agreement with the existing
  Boyer-Lindquist reference and bounded Hamiltonian residuals through the
  Schwarzschild horizon.
- Physical correspondence: The tracer evolves canonical Kerr-Schild
  `(x^mu, p_mu)` using `dx^mu/dlambda = g^{mu nu} p_nu` and
  `dp_i/dlambda = -1/2 p_mu partial_i g^{mu nu} p_nu`. The BL-to-KS state
  transform preserves the canonical one-form and includes the radial time and
  azimuth shifts for ingoing Kerr-Schild coordinates.
- Assumptions and conventions: The first capture event is classified after
  continuing inside `r_+` by the configured margin. Disk-crossing events,
  Carter `Q`, and full critical-curve regression are intentionally deferred to
  the next Stage A validation pass.
- Validation: `python -m pytest tests/test_metric_ks.py tests/test_geodesic_ks.py
  -q` passed with `11 passed`. The tests cover `det(g) = -1`, Killing-norm
  agreement with the BL metric outside the horizon, BL-to-KS null-Hamiltonian
  preservation, Schwarzschild escape classification/minimum-radius agreement,
  and a capture ray that continues inside the outer horizon with bounded
  Hamiltonian residual.
- References: Same Kerr-Schild and Kerr geodesic references as the previous
  entry; no new source added.
- Open issues / next steps: Add disk crossing in Cartesian KS coordinates,
  transform/diagnose Carter `Q`, compare asymptotic escape directions against
  BL in the exterior, and run Kerr critical-curve regression through the KS
  tracer.

### 2026-07-08 - Kerr-Schild metric primitives for Tier 2 planning

- Goal: Start the true near-horizon roaming track with coordinate-regular
  Kerr-Schild metric primitives while preserving the distinction between
  precomputed transfer-map playback and future horizon-penetrating tracing.
- Changed files / components: Added `src/gr_bh_xr/metric_ks.py` and
  `tests/test_metric_ks.py`; updated `docs/equations.md`,
  `docs/validation_targets.md`, `references/references.md`,
  `references/references.bib`, and
  `references/source_notes/2026-07-08-kerr-schild-near-horizon.md`; adjusted
  Quest control labels in `xr/unity_frontend/Runtime/` to call current stick
  input observer-basis rotation rather than black-hole parameter control.
- Academic reason: Near-horizon work must remove Boyer-Lindquist horizon/axis
  coordinate failures before making any claim about event-horizon proximity.
  The first auditable step is metric-level validation, not a visual navigation
  demo.
- Physical correspondence: The new module implements Cartesian Kerr-Schild
  `g_mu_nu = eta_mu_nu + 2 H l_mu l_nu`, the inverse metric, analytic
  Cartesian derivatives, Hamiltonian evaluation, and BL/Kerr-Schild spatial
  coordinate conversion. Current VR yaw/pitch/roll controls rotate the
  observer basis of a static transfer map; changing spin, inclination,
  observer radius, apparent size, or worldline still requires regenerated
  transfer maps or the future Tier 2 keyframe pipeline.
- Assumptions and conventions: Signature remains `(-,+,+,+)`, geometric units
  remain `G = c = 1`, and existing BL/Carter/Kerr critical-curve gates remain
  authoritative until a KS geodesic solver has its own BL-vs-KS cross-validation.
- Validation: `python -m pytest tests/test_metric_ks.py -q` passed with
  `6 passed`, covering Schwarzschild limit, null Kerr-Schild vector,
  covariant/inverse metric identity, BL/Kerr-Schild spatial roundtrip, analytic
  derivative comparison with finite differences, and finite metric behavior at
  the outer horizon.
- References: Added `bakun2024kerrHorizonPenetrating` as a modern
  horizon-penetrating Kerr geodesic reference; existing Carter/Bardeen/Gralla
  references remain the exterior analytic cross-check sources.
- Open issues / next steps: Implement `geodesic_ks.py`, add BL-vs-KS exterior
  ray comparison, recover the Kerr critical curve with the KS tracer, then add
  observer worldlines/tetrad transport before GPU keyframe generation.

### 2026-07-07 - Quest disk visual mode and VR settings panel

- Goal: Add a first headset-usable thin-disk visual layer and replace the
  oversized text status display with a world-space settings panel.
- Changed files / components: Extended `BlackHoleLensStaticPreview.shader`
  with disk visual compositing over the existing full-sky transfer map; added
  `BlackHoleLensRuntimeSettings` for live-safe material parameters; added
  `BlackHoleLensSettingsPanel` as a world-space Canvas with selectable buttons;
  extended XR controller controls and Unity gate automation to bind the panel,
  disk settings, and generated disk cubemaps.
- Academic reason: Disk visuals must consume validated transfer quantities
  rather than overlaying a decorative texture. Runtime controls also need to
  distinguish safe Tier 0 display parameters from physical parameters that
  require Tier 1 transfer-map regeneration.
- Physical correspondence: The disk visual mode samples the first two disk
  crossing cubemaps storing `(r_m, sin(phi_m), cos(phi_m), g_m)`. The first
  visual model uses a documented emissivity proxy with observed weighting
  `g^3` by default. It is not yet a Page-Thorne flux model, radiative transfer
  result, or time-delay-aware disk animation.
- Assumptions and conventions: The settings panel is a Unity world-space UI
  object. Opening it places it in front of the headset; afterwards it remains
  world locked and can be repositioned with controller grip. The panel exposes
  live-safe controls such as disk visual/audit mode, opacity, brightness, and
  `g` power. Requests to change observer radius are marked as stale-transfer
  requests because `a`, inclination, `r_obs`, apparent size, and observer
  translation require a new transfer map in Tier 1.
- Validation: `python -m pytest -q` passed with `59 passed`. `git diff --check`
  passed. `python -m gr_bh_xr.gpu.generate_transfer_cubemap --spin 0.9
  --inclination-deg 60 --face-size 1024 --r-obs 100 --steps 8000` generated a
  local full-sky disk package with `6291456` texels, `capture = 2023`,
  `escape = 6289433`, `invalid = 0`, and disk valid counts `[47289, 1316]`.
  Unity batch Player build using
  `Assets/GRBHXR/FullSkyTransferDisk1024` exited with code `0` and confirmed
  `fullSkyTransfer=True`.
- References: Existing Cunningham/Luminet/Bardeen disk-transfer references in
  `references/references.md`; no new emissivity reference is introduced yet.
- Open issues / next steps: Add Page-Thorne emissivity and time-delay-aware
  Keplerian pattern advection after the current Quest control path is stable.
  Implement Tier 1 GPU regeneration for physical parameters before exposing
  real spin, inclination, observer-radius, or near-horizon navigation controls
  as active physics.

### 2026-07-07 - Quest interaction control scaffold

- Goal: Add a first interaction layer for Quest/desktop debugging without
  violating the static-transfer-map boundary.
- Changed files / components: Added `BlackHoleLensAnchorControls` for
  yaw/pitch drag, independent roll control, reset, and stale-transfer marking;
  added `BlackHoleLensFloatingPanel` as a lightweight world-space status HUD;
  extended Unity gate automation to attach the controls and panel to the
  PCVR sky-shell scene.
- Academic reason: Moving a distant black-hole transfer map on the sky is a
  rigid rotation of the observer basis, not a new geodesic solve. The UI must
  make this distinction visible before exposing more ambitious parameter
  controls.
- Physical correspondence: Dragging changes the Unity lens basis
  `(right, up, forward)` and therefore re-aims the fixed full-sky transfer
  map. Roll changes the position angle around the line of sight. Spin,
  inclination, observer radius, apparent size, and binary phase remain locked
  unless a matching transfer map is generated or selected.
- Assumptions and conventions: Legacy mouse/keyboard bindings are development
  aids only; XR controller rays or UI buttons should call the same public
  methods. Apparent-size requests only set a stale flag and log that Tier 1
  regeneration is required.
- Validation: Source tests assert that the control methods, stale-transfer
  guard, floating panel, and editor scene wiring are present. Unity batch
  recompilation is still required in the formal project before headset use.
- References: Existing static-Kerr transfer-map boundary in
  `docs/physical_scope.md`.
- Open issues / next steps: Wire controller ray/button input in the OpenXR
  scene and record headset behavior with the panel visible.

### 2026-07-07 - Quest PCVR sky-shell first-run scaffold

- Goal: Start the Quest PCVR line without overstating mixed-reality
  passthrough physics.
- Changed files / components: Added a Unity `BlackHoleXrSkyShell` runtime
  helper, extended gate automation with a PCVR sky-shell configuration entry,
  added a read-only Quest PCVR preflight script, and expanded the XR/MR scope
  documentation.
- Academic reason: The verified full-sky transfer cubemap should be consumed
  as an angular radiance field around the observer, not as a flat near-field
  billboard. Mixed-reality claims also need an explicit distinction between
  compositor overlay, cached room radiance, depth/mesh reprojection, and
  camera-frame lensing.
- Physical correspondence: The sky shell follows the camera position while
  the lens basis is refreshed from a separate black-hole anchor, so head
  rotation changes the sampled view direction without creating artificial
  billboard perspective. This remains Tier 0 static transfer-map playback for
  one observer; it does not trace geodesics per frame and does not bend real
  passthrough camera pixels.
- Assumptions and conventions: PCVR first-run is MR-0. MR-1 uses a static room
  cubemap captured on standalone Quest, MR-2 adds finite-distance depth/mesh
  reprojection, and MR-3 may add calibrated rear or external cameras. A forward
  passthrough camera cannot observe the behind-the-user radiance that a real
  black hole can lens into the Einstein ring.
- Validation: Source-level tests check that the sky-shell runtime is versioned
  and that editor automation exposes the batch first-run configuration. The
  `quest_pcvr_preflight.ps1` script performs local read-only checks for Unity,
  the formal project, transfer-map assets, ADB, and Quest USB visibility.
- References: Existing Task 5 full-sky transfer validation and Quest PCVR
  validation notes; no new physics reference is introduced.
- Open issues / next steps: Run the preflight and OpenXR headset protocol with
  the device connected; separately continue disk visual-mode shader work.

### 2026-07-07 - Full-sky thin-disk audit cubemaps

- Goal: Start the Unity thin-disk path with an audit visualization before any
  visual emissivity or animation shader is added.
- Changed files / components: Extended the full-sky transfer cubemap exporter
  to write optional `disk_order0/1_transfer_cube_rgba16f.bytes`; extended the
  Unity loader to bind optional disk cubemaps; added shader-side disk audit
  mode and Unity batch capture automation for `m = 0` and `m = 1` disk-transfer
  views.
- Academic reason: Thin-disk rendering must consume transfer quantities
  `(r_m, phi_m, g_m)` rather than painting a visual disk over the shadow. The
  first Unity gate should therefore show `g_m` false color and equal-`r_m`
  bands that can be compared against CPU Luminet-style transfer plots.
- Physical correspondence: The disk cubemap is indexed by finite-observer
  view direction and stores `(r_m, sin(phi_m), cos(phi_m), g_m)` for the first
  two true equatorial crossing orders. Zero texels mean no finite annulus hit
  for that order. The package remains a static transfer-map cache for one Kerr
  observer, not per-frame geodesic integration.
- Assumptions and conventions: `r_in` is the Kerr ISCO from the GPU trace
  configuration and `r_out = 30M`; `g_m` is the Cunningham redshift factor from
  the existing disk-transfer shader path. Visual intensity weighting `g^p`,
  blackbody color, Keplerian pattern advection, and time-delay use are deferred.
- Validation: `python -m gr_bh_xr.gpu.generate_transfer_cubemap --spin 0.9
  --inclination-deg 60 --face-size 512 --r-obs 100 --steps 8000` produced
  `1572864` texels with `capture = 510`, `escape = 1572354`, `invalid = 0`,
  and disk valid counts `[11826, 335]` for `m = 0, 1`. Unity batch disk audit
  captured `unity_gate_fullsky_disk_audit_m0_square_1024.png` and
  `unity_gate_fullsky_disk_audit_m1_square_1024.png`; the `m = 0` image shows
  continuous equal-radius bands and the `m = 1` image isolates the secondary
  band near the shadow edge.
- References: Existing Luminet/Cunningham/Bardeen disk-transfer references in
  `references/references.md`; no new disk emissivity model is introduced here.
- Open issues / next steps: Add a formal CPU-vs-Unity audit comparison for the
  disk cubemap, then implement the visual disk shader with documented `g^p`
  weighting and Page-Thorne emissivity.

### 2026-07-07 - Full-sky tetrad and seam validation

- Goal: Close the post-full-sky P1 evidence gaps before using the cubemap path
  for Quest first-run claims.
- Changed files / components: Added `trace_state()` for explicit CPU
  `RayState` tracing, added `gr_bh_xr.gpu.validate_full_sky_transfer`,
  extended the Unity full-sky protractor batch capture, extended
  `validation/quest_pcvr/scripts/compare_protractor_gate.py` to read full-sky
  cubemap direction bytes, and updated Task 5 validation documentation.
- Academic reason: The finite-observer tetrad path is a different physical
  initialization from the Bardeen `alpha,beta` screen path, so it needs its own
  CPU reference comparison. The removal of the square seam also needs a
  quantitative regression rather than a screenshot-only claim.
- Physical correspondence: CPU and GPU both launch rays from the same
  finite-radius static-observer tetrad at `r_obs = 100M`, `i = 60 deg`, Kerr
  `a = 0.9M`. The Unity seam gate compares protractor bands generated from the
  momentum-derived escaped direction stored in the full-sky cubemap.
- Assumptions and conventions: This remains Tier 0 static transfer-map
  playback; no per-frame geodesic integration or Quest runtime claim is made
  in this step. Full-sky capture/invalid edge dilation remains a deferred
  display-polish item for full-sky-only modes.
- Validation: `python -m gr_bh_xr.gpu.validate_full_sky_transfer --spin 0.9
  --inclination-deg 60 --samples 4096 --r-obs 100` produced CPU/GPU event
  counts `capture = 2`, `escape = 4094`, `invalid = 0`, stable agreement
  `1.0`, full-grid agreement `1.0`, and `0` GPU failures outside exclusions.
  Stable escaped-ray direction errors were median `1.57e-6 rad`, RMS
  `3.84e-5 rad`, and max `1.60e-3 rad`. Unity batch protractor captures at
  yaw `0/2/4 deg` compared against `escape_dir_unity_cube_rgba32f.bytes` had
  old-window seam violations `0`; yaw `2/4 deg` had max adjacent band jump
  `1`.
- References: Existing Kerr geodesic and Unity texture-contract references;
  this entry validates an implementation path rather than introducing a new
  metric model.
- Open issues / next steps: Run the Quest/OpenXR first-run protocol and keep
  Task 6 display-level disk-transfer export moving in parallel.

### 2026-07-07 - Full-sky background transfer cubemap

- Goal: Remove the unphysical square boundary discovered in the Unity yaw gate,
  where the finite `alpha,beta in [-8M, 8M]` lens patch fell back directly to an
  unlensed skybox outside the patch.
- Changed files / components: Added the GPU full-sky transfer cubemap exporter,
  finite-radius static-observer direction initialization, WGSL direction-input
  tracing, Unity full-sky cubemap loading, full-sky shader sampling, editor
  automation flags, tests, and validation documentation.
- Academic reason: A physics-auditable renderer cannot present a model-switch
  edge as gravitational lensing. At `r_obs = 100M`, the `8M` patch edge remains
  strongly deflected, so direct skybox fallback creates a visible square
  discontinuity unrelated to the Kerr geometry.
- Physical correspondence: Each full-sky cubemap texel is traced from a
  finite-radius static observer tetrad. Unity now samples this traced cubemap
  for the whole view and blends the 4K local `alpha,beta` patch over the
  central angular window only to preserve shadow-edge resolution.
- Assumptions and conventions: This remains Tier 0 static transfer-map playback
  for one Kerr metric and observer. It does not perform per-frame geodesic
  integration, and it must not be reused for BBH, multi-black-hole, or
  gravitational-wave lensing without time-dependent maps or validated
  surrogates.
- Validation: `python -m gr_bh_xr.gpu.generate_transfer_cubemap --spin 0.9
  --inclination-deg 60 --face-size 1024 --r-obs 100 --steps 8000` wrote
  `6291456` cubemap texels with `capture = 2023`, `escape = 6289433`, and
  `invalid = 0`. Formal Unity batch captures with
  `-grbhxrFullSkyTransferDir Assets/GRBHXR/FullSkyTransfer1024` produced yaw
  `0/2/4 deg` screenshots; the `4 deg` capture no longer shows the square hard
  boundary from unlensed-skybox fallback.
- References: Same Kerr geodesic and Task 5 Unity texture-contract references;
  this is a renderer-domain transfer-map fix, not a new metric model.
- Open issues / next steps: Native 4K or tiled full-sky transfer generation and
  catalog/procedural star layers are still needed for higher VR angular
  fidelity. Quest runtime frame pacing and stereo validation remain pending.

### 2026-07-07 - Tier 1 GPU trace latency benchmark

- Goal: Quantify whether the WGPU Vulkan tracer is currently a slider-update,
  progressive-update, or per-frame geodesic integration path.
- Changed files / components: Added `gr_bh_xr.gpu.benchmark_latency`, GPU task
  tests for its parser/summary helper, and GPU validation/physical-scope
  documentation for the measured update budget.
- Academic reason: The project must not confuse Tier 0 static texture playback
  with true real-time geodesic integration. Measured latency is needed before
  deciding when neural or reduced-order surrogates become necessary.
- Physical correspondence: The benchmark measures a full Kerr transfer-map
  update for fixed Boyer-Lindquist screen bounds and observer metadata. It
  includes GPU dispatch, readback, momentum-derived escape directions,
  event/debug texture assembly, and disk-transfer buffers, but excludes HDF5
  writes and Unity texture upload.
- Assumptions and conventions: The benchmark case is Kerr `a = 0.9`,
  `i = 60 deg`, `r_obs = 100M`, `alpha,beta in [-8M, 8M]`, `h = 0.05`, and
  `8000` fixed RK4 steps on the local NVIDIA GeForce RTX 5080 Laptop GPU.
- Validation: Raw `trace_lens_map` timings were `49.09 ms` at `256x256`,
  `185.94 ms` at `512x512`, and `652.51 ms` at `1024x1024`. With the existing
  `0.25M` critical-band `2x2` refinement, timings were `113.48 ms`,
  `345.96 ms`, and `1243.98 ms`. The JSON reports are stored under ignored
  `outputs/task5/`.
- References: Existing Task 4 GPU validation notes in
  `validation/gpu_kerr_lensing/README.md`.
- Open issues / next steps: Use these numbers to keep Quest Tier 0 static
  playback separate from Tier 1 update controls; start Quest first-pass
  validation with a higher-resolution skybox while disk-transfer texture export
  continues.

### 2026-07-07 - Static playback boundary and Quest yaw semantics

- Goal: Clarify the Task 5 Unity path after desktop angular-window testing
  showed that a yawed camera only moves a fixed distant lens window across the
  view; it does not simulate orbiting around the black hole.
- Changed files / components: `docs/physical_scope.md`,
  `docs/validation_targets.md`, `validation/quest_pcvr/README.md`,
  `validation/quest_pcvr/2026-07-06-unity-editor-desktop-gate.md`, and
  `xr/unity_frontend/README.md`.
- Academic reason: The project target includes eventual dynamic scenes,
  including BBH, multi-black-hole, and gravitational-wave lensing. A fixed
  single-Kerr transfer map must not be allowed to masquerade as the final
  real-time ray-tracing architecture.
- Physical correspondence: The current Unity bridge renders a precomputed
  transfer map in real time:
  `view ray or screen coordinate -> escape direction -> cubemap sample`. It
  remains tied to the metadata observer and metric parameters. Changing spin,
  inclination, observer position, or binary phase requires a new selected,
  interpolated, progressively updated, or re-traced transfer map.
- Assumptions and conventions: The renderer architecture is now documented in
  three tiers: static transfer-map playback for the Quest gate, real-time or
  near-real-time GPU transfer-map updates for parameter changes, and
  dynamic-metric cache/surrogate methods for BBH or gravitational-wave lensing.
- Validation: The 2026-07-07 Unity yaw captures remain useful only as a desktop
  head-rotation anchoring precheck. The right-side blur in yawed captures is
  separately attributed to all-sky background resolution: a 4096-wide sky map
  contributes only about 100 source pixels across the current `9.1478 deg`
  gate FOV, independent of the 4K lens-map display texture.
- References: Existing Task 5 Unity texture-contract notes and the NASA Deep
  Star Maps 2020 source note in the Unity project.
- Open issues / next steps: Use a higher-resolution all-sky map, local
  high-resolution sky patch, or procedural/catalog starfield for VR-quality
  backgrounds; keep Quest first-pass validation focused on static-lens
  stereo/frame-pacing/anchoring while the separate GPU real-time and surrogate
  tracks are planned.

### 2026-07-07 - GPU thin-disk transfer hooks v3

- Goal: Start the Task 6 GPU-side disk-transfer path by adding first-crossing
  buffers to the existing Vulkan/WGPU lens-map shader without changing the
  Task 4 capture/escape validation gate.
- Changed files / components: GPU trace shader, GPU HDF5 writer, GPU schema
  version, GPU tests, GPU validation documentation, and validation targets.
- Academic reason: Real-time disk rendering should consume auditable transfer
  quantities rather than infer disk appearance from RGB. The first Unity disk
  shader needs `(r_m, phi_m, g_m, Delta t_m)`-style buffers before it can
  advect emissivity patterns or apply redshift weights.
- Physical correspondence: The f32 RK4 shader now records the first two true
  equatorial crossings by crossing order, filtered to `r_ISCO(a) <= r <=
  r_out`. It stores `gpu_disk_r_m`, `gpu_disk_phi_m`,
  `gpu_disk_sin_phi_m`, `gpu_disk_cos_phi_m`, `gpu_disk_t_m`, and
  `gpu_disk_g_m`. The redshift uses the same Cunningham-style Keplerian
  emitter form as the CPU disk helper, evaluated at the interpolated crossing.
- Assumptions and conventions: This is a geometric transfer-buffer extension,
  not a full observed-intensity model. Event classification remains
  capture/escape/invalid; disk crossings do not stop the ray and do not enter
  the Task 4 event-agreement gate. The GPU values are f32 and will need CPU
  band validation before display-grade disk claims.
- Validation: Added a GPU smoke test that writes schema
  `gr-bh-xr.phase2.gpu_lens_map.v3`, confirms the disk datasets have shape
  `(2, grid, grid)`, and checks finite disk hits are inside the Schwarzschild
  `[r_ISCO, r_out]` annulus with positive `g_m` and unit
  `sin(phi)^2 + cos(phi)^2`. A 33 by 33 Schwarzschild `i = 80 deg` CLI smoke
  run wrote `outputs/task6/gpu_disk_transfer_smoke_33.h5` with
  `disk_valid_by_order = [667, 110]`, `capture = 140`, `escape = 924`, and
  only the expected 25 Boyer-Lindquist axis invalid samples.
- References: `bardeen1972rotatingBlackHoles` for ISCO and
  `cunningham1975kerrDiskSpectrum` for the Keplerian redshift convention.
- Open issues / next steps: Add CPU-vs-GPU disk-transfer comparison masks,
  then export display textures for `r_m`, `phi_m`/`sin,cos`, `g_m`, and
  `Delta t_m` for Unity audit and visual disk modes.

### 2026-07-07 - GPU disk-transfer CPU comparison

- Goal: Add the first matched CPU-vs-GPU validation path for the v3 disk
  transfer buffers before treating them as display-texture source data.
- Changed files / components: GPU disk-transfer validator CLI, GPU tests,
  disk redshift tests, Unity binder guard, GPU validation documentation, and
  validation targets.
- Academic reason: Disk rendering needs a quantitative transfer-buffer gate,
  not only event-code agreement. The redshift chain also needs cheap analytic
  invariants that catch sign or block-inversion regressions.
- Physical correspondence: The validator compares matched CPU DOP853 and GPU
  f32 RK4 disk layers by true crossing order and reports validity mismatch,
  `|Delta r_m|`, `phi_m` angular error, `|Delta t_m|`, and `|Delta g_m|`.
  Stable masks exclude failures, the critical curve, near-capture pixels, and
  a disk-annulus edge band. The Schwarzschild redshift tests now include
  `g(r_ISCO, L_z = 0) = 1/sqrt(2)` and the mirror invariant
  `1/g(+L_z) + 1/g(-L_z) = 2 u^t`.
- Assumptions and conventions: GPU disk buffers are valid independently of
  final ray event code; a ray may record a physically prior disk crossing and
  later terminate at an axis-coordinate failure. CPU and GPU both use
  sign-change equatorial crossing detection, so exact tangential double
  crossings remain a documented boundary case.
- Validation: A matched 16 by 16 Schwarzschild `i = 80 deg`,
  `alpha,beta in [-30M, 30M]`, `r_obs = 100M` comparison wrote
  `outputs/task6/gpu_disk_compare_schwarzschild_16.h5` with zero validity
  mismatches, `max |Delta r_m| = 2.33e-4 M`,
  `max |Delta g_m| = 2.73e-6`, `max phi_m error = 6.67e-6 rad`, and
  `max |Delta t_m| = 5.84e-4`. The formal 64 by 64 gate wrote
  `outputs/task6/gpu_disk_compare_schwarzschild_64.h5` with zero validity
  mismatches, `max |Delta r_m| = 0.00362 M`,
  `max |Delta g_m| = 2.31e-5`, `max phi_m error = 1.05e-5 rad`, and
  `max |Delta t_m| = 0.00376`.
- References: Same Bardeen/Press/Teukolsky ISCO and Cunningham redshift
  references as the CPU Task 6 transfer path.
- Open issues / next steps: Run the formal 64 by 64 gate, then export
  display-grade disk transfer textures for Unity audit/visual modes.

### 2026-07-07 - Unity basis refresh and static-Kerr boundary

- Goal: Close the remaining Task 5 Unity P2 items and record the physical
  boundary of the static single-Kerr real-time shortcut before disk animation
  and later BBH planning.
- Changed files / components: Unity runtime lens-map loader/binder, the
  protractor comparison script, XR export tests, Quest validation notes,
  physical-scope documentation, and validation targets.
- Academic reason: The Unity bridge must preserve sky directions under runtime
  recentering or anchor rotation, and future dynamic-metric work must not infer
  more from the single-Kerr cache than stationarity and axisymmetry allow.
- Physical correspondence: `BlackHoleLensMaterialBinder` refreshes the
  explicit lens-screen world basis every `LateUpdate` by default, so material
  vectors no longer go stale when the lens anchor rotates. The disk-animation
  plan is documented as static transfer-map consumption:
  `e(r_m, phi_m - Omega(r_m) * (t - Delta t_m)) * g_m^p`, with the power `p`
  still to be chosen by the intensity convention.
- Assumptions and conventions: The shortcut applies to a fixed observer in a
  stationary axisymmetric Kerr spacetime. BBH, multi-black-hole, and
  gravitational-wave lensing require time-dependent transfer maps, cache
  playback, adaptive tracing, or validated surrogates tied to a documented
  metric.
- Validation: Versioned the 61 by 61 protractor comparison script so Unity
  screenshots can be compared against `escape_dir_unity_rgba32f.bytes` and the
  old non-uniform-scale skew hypothesis. Added tests that the Unity binder
  refreshes basis vectors at runtime and that the protractor comparison rejects
  the old scale-skew failure mode.
- References: Task 5 Unity texture-contract notes and existing Kerr
  transfer-map references in `docs/equations.md`.
- Open issues / next steps: Run desktop angular-window yaw captures at
  `0 deg`, `2 deg`, and `4 deg`; then proceed to Quest PCVR static-lens
  validation while Task 6 advances GPU disk-transfer export.

### 2026-07-07 - Unity direction-basis scale guard

- Goal: Fix the Task 5 Unity gate P0 where a scale-bearing object matrix could
  skew escaped-ray directions before cubemap lookup.
- Changed files / components: Unity preview shader, runtime lens-map loader,
  Unity Editor gate automation, XR export tests, Unity package README, and the
  Quest desktop-gate validation note.
- Academic reason: A physics-auditable renderer must not pass a sign-only
  handedness test while silently changing the angular amplitude of the
  background transfer direction. The display bridge must preserve the
  `escape_dir_unity` vector as a direction on the sky, not as a scaled mesh
  vector.
- Physical correspondence: `BlackHoleLensMap` now writes explicit pure
  rotation basis vectors (`_LensWorldRight`, `_LensWorldUp`,
  `_LensWorldForward`) into the material. The shader uses those basis vectors
  for both angular-window view rays and escaped-direction cubemap lookup,
  instead of deriving direction transforms from `unity_ObjectToWorld` or
  `unity_WorldToObject` scale-bearing matrices.
- Assumptions and conventions: The formal desktop gate still uses a uniform
  `(20, 20, 20)` LensScreen scale, but correctness no longer depends on object
  scale being physically meaningful. The screen-space gate remains the accepted
  desktop path; angular-window head-motion validation is still pending.
- Validation: Ran the formal Unity project
  `F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate` through batchmode NASA,
  quadrant, and protractor captures. The protractor PNG was decoded from sRGB
  to linear and compared against `escape_dir_unity_rgba32f.bytes` on a 61 by
  61 lattice with `u = x`, `v = 1 - y`: raw no-skew direction had
  `exact = 2004/2058`, `closer = 2048/2058`,
  `mean_abs_band_error = 0.027`; the old `(x,y)*20` skew had
  `exact = 10/2058`, `closer = 10/2058`, `mean_abs_band_error = 3.255`.
- References: `validation/quest_pcvr/2026-07-06-unity-editor-desktop-gate.md`.
- Open issues / next steps: Validate `_UseAngularWindow` with yawed desktop
  captures before Quest head-rotation claims.

### 2026-07-06 - Unity desktop gate reproducibility and handedness evidence

- Goal: Close the Unity desktop gate evidence gaps found after the square
  screen-space preview was accepted conditionally.
- Changed files / components: Unity preview shader, runtime lens-map loader,
  versioned Unity Editor gate automation, XR export tests, Quest validation
  notes, and Unity package documentation.
- Academic reason: The Unity bridge must be reproducible from tracked source,
  and a screenshot-based validation path must prove that the display layer has
  not introduced a hidden vertical mirror into physics textures.
- Physical correspondence: The default desktop gate remains a screen-space
  square sampling path, preserving the square `alpha/beta` transfer-map aspect.
  The opt-in angular-window path now rejects back-facing rays with
  `localRay.z <= 0` and documents its tangent-plane
  `alpha = r_obs x / z`, `beta = -r_obs y / z` approximation and no
  non-uniform-scale assumption. Missing `r_obs` metadata now emits a Unity
  warning before falling back to `100M`.
- Validation: Added repository-tracked Unity Editor automation under
  `xr/unity_frontend/Editor/`. The formal Unity project executed
  `GRBHXR.EditorTools.GRBHXRGateAutomation.BatchConfigureAndCapture` and
  `BatchCaptureQuadrantHandedness` successfully from the package path. A
  procedural quadrant cubemap screenshot was checked against
  `escape_dir_unity_rgba32f.bytes`: `matches_no_vflip = 6/6`,
  `matches_vflip = 0/6`. Python tests and `git diff --check` are part of the
  closeout.
- References: Existing Task 5 Unity texture-contract documentation and
  `validation/quest_pcvr/2026-07-06-unity-editor-desktop-gate.md`.
- Open issues / next steps: The angular-window / full-camera path still needs
  yawed-camera desktop tests before Quest head-motion claims; physical head
  translation remains outside the static baked-map model.

### 2026-07-06 - Unity cubemap direction and Luminet equal-radius gate

- Goal: Fix the Unity static-preview coordinate consumption path and add the
  first Luminet-style thin-disk geometry validation figure.
- Changed files / components: Unity preview shader/C# loader/docs/tests,
  `plot_disk_transfer`, disk-transfer tests, Quest validation notes, and
  thin-disk validation documentation.
- Academic reason: The headset/Unity bridge must not introduce display-only
  coordinate rotations or aspect-ratio distortions, and Task 6 needs a
  direct/secondary disk-image diagnostic before adding emissivity or intensity.
- Physical correspondence: The accepted Unity desktop preview now uses a
  screen-space square gate so the square `alpha/beta` transfer map is not
  stretched into the Game-view aspect ratio. Pixels outside the square gate
  sample the same cubemap directly, while escaped-ray directions inside the
  gate are transformed by the lens-screen object-to-world rotation before
  cubemap sampling. The experimental angular-window path remains in the shader
  behind `_UseAngularWindow`, but it is not yet accepted as a head-motion
  validation result. The disk-transfer plot reads `r_m(alpha,beta)` and `g_m`
  from schema v2, flips the raw solver beta rows into visual beta, and draws
  separate `m = 0` direct and `m = 1` secondary equal-radius curves.
- Assumptions and conventions: Square `alpha/beta` maps must be consumed as
  square gates unless the source HDF5 was generated with matching non-square
  screen bounds. The current Unity texture is still a static observer
  approximation: the screen-space desktop gate does not close Quest
  head-motion stability, and head translation would require a different
  transfer map. The Luminet-style plot is a geometric transfer diagnostic, not
  yet a full observed-intensity image. The exact `alpha = 0` column can expose
  the Boyer-Lindquist polar-axis coordinate limitation for far-side secondary
  disk arcs.
- Validation: Added tests that the Unity shader keeps the screen-space square
  gate, includes the opt-in angular path, samples cubemaps in world space, that
  the C# loader injects `r_obs` and screen bounds into the material, that raw
  texture loading stays linear, and that the disk-transfer plotting CLI writes
  a visually beta-flipped PDF from CPU transfer buffers.
- References: `luminet1979blackHoleImage`, `cunningham1975kerrDiskSpectrum`,
  and the existing Task 5 Unity texture-contract references.
- Open issues / next steps: Re-run the Unity desktop gate with a real skybox
  and the screen-space square gate, then develop a full-camera or
  angular-window path for head-motion stability before Quest claims. Add disk
  emissivity / observed intensity buffers for a full Luminet morphology
  comparison. A future axis-regular or Kerr-Schild tracer should remove the
  thin `alpha = 0` disk-arc gap.

### 2026-07-06 - Task 6 thin-disk crossing semantics v2

- Goal: Fix thin-disk transfer crossing semantics found during review before
  using the buffers as Task 6 validation ground truth.
- Changed files / components: `trace_ray` disk-crossing events,
  `RayDiagnostics`, `generate_disk_transfer`, disk-transfer tests, schema docs,
  and validation targets.
- Academic reason: Cunningham/Luminet disk-image order is the true equatorial
  crossing order. It must not be collapsed by post-filtering to the emitting
  annulus, otherwise secondary images can be mislabeled as direct images.
- Physical correspondence: Startup disk-event guarding now preserves the sign
  of the initial equatorial offset, exact coplanar equatorial rays are excluded
  from thin-disk event recording, and schema v2 stores emitting-annulus hits in
  their true zero-based crossing-order layer.
- Assumptions and conventions: `disk_crossing_count` counts stored emitting
  annulus hits, while the `disk_m` axis is the true equatorial crossing order.
  Edge-on coplanar rays require separate treatment and are not used as thin-disk
  transfer records.
- Validation: Added north/south startup pseudo-crossing regression coverage,
  exact-coplanar skip coverage, and a true-order HDF5 regression where `m = 1`
  remains populated while `m = 0` is absent for the same pixel.
- References: Same `bardeen1972rotatingBlackHoles`,
  `cunningham1975kerrDiskSpectrum`, and `luminet1979blackHoleImage` disk
  transfer references used by Task 6 v1.
- Open issues / next steps: Generate Luminet-style direct and secondary
  image diagnostics, then decide which disk-transfer channels should enter the
  GPU/Unity texture contract.

### 2026-07-06 - Task 6 CPU thin-disk transfer v1

- Goal: Start the formal thin-disk transfer-function path while Unity Editor
  setup is pending.
- Changed files / components: `src/gr_bh_xr/disk.py`,
  `src/gr_bh_xr/generate_disk_transfer.py`, `trace_ray` disk-crossing records,
  tests, and validation documentation.
- Academic reason: The next physics milestone after background lensing is the
  Cunningham/Luminet thin-disk transfer map: per-crossing disk radius, azimuth,
  time, and redshift must be auditable before any bright disk image is rendered.
- Physical correspondence: The CPU transfer v1 records equatorial disk
  crossings inside `r_ISCO(a) <= r_m <= r_out`, using `r_ISCO(a)` from
  Bardeen/Press/Teukolsky and a Keplerian emitter redshift
  `g = E / (u^t (E - Omega L_z))` following the Cunningham transfer-function
  convention. The disk is geometrically thin, equatorial, and co-rotating with
  the black-hole spin by default.
- Assumptions and conventions: The camera remains asymptotic, so the observer
  frequency is `E = -p_t`. The schema stores `disk_r_m`, `disk_phi_m`,
  `disk_t_m`, and `disk_g_m`; emissivity, optical depth, observed intensity,
  and GPU/Unity integration are deferred.
- Validation: Added unit tests for Schwarzschild `r_ISCO = 6M`, the
  `g(L_z = 0) = sqrt(1 - 3M/r)` redshift limit, per-ray crossing records, and
  a small HDF5 disk-transfer map with finite positive `g_m` values.
- References: `bardeen1972rotatingBlackHoles`,
  `cunningham1975kerrDiskSpectrum`, and `luminet1979blackHoleImage`.
- Open issues / next steps: Reproduce a Luminet-style direct/secondary
  thin-disk diagnostic, then expose selected disk-transfer channels to the GPU
  and Unity texture contract.

### 2026-07-06 - Task 6 photon-ring zoom pre-transfer diagnostic

- Goal: Start the Task 6 physics track with a cheap visualization of
  high-order image / photon-ring structure before adding disk emissivity.
- Changed files / components: CPU lens-map schema, `RayDiagnostics`,
  `generate_lens_map`, `plot_lensing_band_zoom`, tests, and validation
  documentation.
- Academic reason: Gralla-Holz-Wald 2019 and Gralla-Lupsasca 2020 explain why
  higher-order image bands are exponentially compressed toward the critical
  curve. A full-screen background lens map hides these bands at ordinary
  resolution, so the first auditable deliverable is a zoomed transfer-buffer
  diagnostic rather than a visual-only claim.
- Physical correspondence: Added `azimuthal_winding = |Delta phi| / (2 pi)`
  and `image_order = floor(2 * azimuthal_winding)` as a screen-ray winding
  proxy. This is not the final thin-disk crossing order `m`; it is the
  pre-transfer diagnostic that makes winding bands visible near the critical
  curve.
- Assumptions and conventions: The tracer remains the Phase 1 CPU
  Boyer-Lindquist exterior solver. The lens-map generator now supports
  asymmetric screen windows such as `alpha in [4.8M, 5.6M]`, `beta in
  [-0.4M, 0.4M]`.
- Validation: Added tests for schema v6, winding/image-order datasets,
  asymmetric screen-window attributes, and rendering a lensing-band zoom PDF.
- References: `gralla2019shadowsPhotonRings`, `gralla2020lensingKerr`, and
  the existing Phase 1 Bardeen/Gralla-Lupsasca Kerr geodesic sources.
- Open issues / next steps: Implement thin-disk transfer records
  `(r_m, phi_m, g_m, Delta t_m, n_m)` and reproduce a Luminet-style direct /
  secondary image validation target.

### 2026-07-06 - Unity direction-resample audit fields

- Goal: Tighten the display-resampled Unity texture package after review of the
  1024-to-4K flow.
- Changed files / components: `src/gr_bh_xr/xr/export_unity_textures.py`,
  Unity metadata parsing, XR export tests, and Task 5 documentation.
- Academic reason: Direction textures are continuous only within escaped-ray
  regions. A display resample must not create NaN-prone or physically
  nonexistent directions at valid/invalid or near-critical boundaries.
- Physical correspondence: No ray tracing or metric equations changed.
  Resampled direction vectors are still bilinear display approximations of the
  source escape-direction map, then renormalized. If interpolation cancels to a
  near-zero vector, the texel is marked invalid instead of being normalized.
- Assumptions and conventions: Metadata now separates source escaped-pixel
  count from exported valid direction-texel count through `sourceEscapePixels`
  and `escapePixels`.
- Validation: Added synthetic export tests for display-resampled source/export
  escape counts and for a constructed opposite-direction cancellation case.
- References: Same Task 5 Unity texture contract and Task 4 escape-direction
  map convention.
- Open issues / next steps: Real Unity Editor validation is still required on a
  machine with Unity installed; Python-equivalent rendering does not exercise
  Unity asset import or material state.

### 2026-07-06 - Task 5 VR texture resolution path

- Goal: Separate low-resolution interactive debug preview from headset-facing
  Unity texture packages after preview artifacts and VR blur were observed.
- Changed files / components: `src/gr_bh_xr/xr/export_unity_textures.py`,
  `xr/unity_frontend/`, XR export tests, and Quest validation documentation.
- Academic reason: A 256x256 debug texture is useful for failure
  classification, but it is not a headset-resolution product. Conversely,
  display upsampling must not be mislabeled as higher physical ray-tracing
  resolution.
- Physical correspondence: No geodesic equations changed. The exporter can now
  write a larger display texture with `--target-size`, recording both source
  and exported dimensions and marking whether the package is native trace
  resolution. Event/capture/failure colors remain categorical; escaped
  direction textures are normalized after display resampling.
- Assumptions and conventions: A 4096x4096 display texture is the minimum
  recommended PCVR inspection target, but native 4096x4096 physical tracing is
  deferred to a tiled/offline generator. Unity loads event textures with point
  filtering and escape-direction textures with bilinear filtering.
- Validation: Added a synthetic target-size export test that verifies raw byte
  counts, metadata, and unit-length resampled Unity directions.
- References: Same Task 4/5 transfer-map convention; this is a packaging and
  display-resolution change, not a new physics model.
- Open issues / next steps: Generate and inspect 4K display packages for
  in-envelope Kerr/Schwarzschild cases. Do not use near-polar high-spin preview
  artifacts as Quest validation samples until an axis-regular or Kerr-Schild
  tracer exists.

### 2026-07-06 - GPU preview operating envelope

- Goal: Make the interactive GPU preview explicit about known f32 fixed-step
  limits found during near-polar high-spin exploration.
- Changed files / components: `src/gr_bh_xr/gpu/preview.py`,
  `validation/gpu_kerr_lensing/README.md`, GPU tests, and this log.
- Academic reason: A physics-auditable renderer should label numerical
  operating limits instead of letting a visually dramatic artifact be mistaken
  for a new physical feature or a silent renderer bug.
- Physical correspondence: No equations or shader integration rules changed.
  The default preview now warns outside the documented envelope
  `20 deg <= i <= 160 deg`, `|a| <= 0.95`. In the reproduced non-gating
  near-polar case `a = 0.95`, `i = 5 deg`, the observed red solver failures,
  magenta polar-step overshoots, and near-critical misclassification band are
  attributed to the Bardeen polar screen degeneracy, Boyer-Lindquist axis
  terms, and f32 fixed-step growth on winding rays.
- Assumptions and conventions: Preview warnings do not clamp user-controlled
  parameters and do not hide invalid pixels. Stronger near-polar claims remain
  deferred to an axis-regular or Kerr-Schild tracer.
- Validation: Added a regression test for title-bar warning behavior; full
  test results are recorded with the corresponding commit.
- References: Same Task 4 GPU validation notes and Phase 1 Bardeen/Kerr
  screen-coordinate sources.
- Open issues / next steps: Continue Unity Editor desktop validation using the
  in-envelope static packages; reserve near-polar high-spin preview artifacts
  as documented non-gating stress cases.

### 2026-07-06 - Task 5 desktop validation package prep

- Goal: Prepare the Unity Editor desktop-validation inputs after the texture
  vertical-handedness fix passed review.
- Changed files / components: `validation/quest_pcvr/README.md`; generated
  local packages under ignored `outputs/task5/`.
- Academic reason: Desktop validation should use concrete, reproducible
  texture packages and a documented visual protocol before moving to Quest
  runtime debugging.
- Physical correspondence: Prepared two static lens-map packages:
  Schwarzschild `a = 0`, `i = 90 deg`, and Kerr `a = 0.9`, `i = 60 deg`. The
  Kerr package uses `step_size = 0.025`, `steps = 16000` so the high-spin 256x256
  center-sample map has no invalid/failure pixels.
- Assumptions and conventions: Generated HDF5/raw texture artifacts remain
  local under ignored `outputs/task5/`. The Unity package source remains tracked
  under `xr/unity_frontend/`.
- Validation: Generated both 256x256 GPU maps and exported Unity texture
  packages. Schwarzschild package had `escape_pixels = 43988`;
  Kerr `a = 0.9`, `i = 60 deg` package had `escape_pixels = 45554`.
  Metadata inspection confirmed `verticalFlipApplied = true` and
  `vToBeta = beta_max - v * (beta_max - beta_min)`.
- References: Same Task 4/5 transfer-buffer convention; this is preparation for
  Unity Editor validation, not headset validation.
- Open issues / next steps: User-side Unity Editor desktop test with a
  recognizable real-sky cubemap, then screenshots and a dated validation note
  in `validation/quest_pcvr/`.

### 2026-07-06 - Task 5 texture vertical-handedness fix

- Goal: Fix the Unity export row convention before Quest or Unity Editor
  consumption so the background sky is not vertically mirrored.
- Changed files / components: `src/gr_bh_xr/xr/export_unity_textures.py`,
  `tests/test_xr_export.py`, `xr/unity_frontend/README.md`,
  `validation/quest_pcvr/README.md`, and validation targets.
- Academic reason: A single-axis mirror can look visually plausible while
  reversing the physical handedness of the lens map. The texture contract must
  preserve screen orientation before any headset runtime validation.
- Physical correspondence: The solver's `+beta` convention increases
  Boyer-Lindquist `theta`, which is visually downward on the observer screen.
  The export layer now applies `np.flipud` to every texture buffer so Unity
  texture `+V` points visually upward and the texture top corresponds to
  `beta_min`.
- Assumptions and conventions: Metadata now records
  `vToBeta = beta_max - v * (beta_max - beta_min)` and
  `verticalFlipApplied = true`. BH-to-Unity vector basis remains unchanged:
  positive `alpha` maps to Unity `+X`, and camera-to-black-hole maps to Unity
  `+Z`.
- Validation: Added a synthetic row-flip test and a 17x17 weak-deflection GPU
  directional regression with `r_obs = 300M`, `alpha = +/-30M`, `beta =
  +/-60M`. The weak-deflection export asserts right-up pixels have
  `x_unity > 0`, `y_unity > 0`, right-down pixels have `x_unity > 0`,
  `y_unity < 0`, and left-up pixels have `x_unity < 0`, `y_unity > 0`.
- References: Same Task 4 momentum escape-direction buffers; this fixes
  coordinate packaging, not ray physics.
- Open issues / next steps: Proceed to Unity Editor desktop validation with a
  recognizable cubemap before Quest PCVR runtime checks.

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
- Physical correspondence: The initial bridge stored both BH-Cartesian and
  Unity-space escape direction textures and fixed the BH-to-Unity basis. The
  later vertical-handedness entry above supersedes the initial unflipped
  `beta` row convention. BH axes use `+Z_BH` as the Kerr spin axis and the
  observer at `phi = 0`, `theta = inclination_deg`. Unity `+Z` points from the
  camera to the black hole, Unity `+Y` is the projected spin axis, and Unity
  `+X` is positive `alpha`.
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
