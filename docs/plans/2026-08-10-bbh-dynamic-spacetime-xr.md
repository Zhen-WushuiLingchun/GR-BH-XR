# BBH Dynamic Spacetime And XR Implementation Plan

> **Execution rule:** Implement task-by-task with independent commits and
> review checkpoints. Do not dispatch external agents unless the user explicitly
> reauthorizes them.

**Goal:** Add a physics-auditable binary-black-hole track that supports a fast
approximate dynamic metric, full four-dimensional null-geodesic tracing, an
offline numerical-relativity truth path, and time-correct OpenXR/MR rendering.

**Architecture:** GR-BH-XR keeps Python f64 as the independent scientific
oracle and uses the native NPGS Vulkan renderer for production GPU tracing.
Every ray consumes an interchangeable time-dependent metric provider. The first
interactive provider is a documented superposed Kerr-Schild approximation; the
high-fidelity provider consumes offline ADM snapshots from a numerical-
relativity code. The headset frame loop never solves the full Einstein system.

**Tech Stack:** Python 3.13, NumPy, SciPy DOP853, h5py, pytest, C++20, GLSL,
Vulkan, NPGS, OpenXR 1.1, HDF5/openPMD/ADIOS2-compatible metadata, Einstein
Toolkit/CarpetX for later offline evolutions.

---

## Status And Authority

- Plan date: 2026-08-10.
- Status: `IMPLEMENTED_WITH_OPEN_PRODUCTION_GATES`; Tasks 0-10 have independent
  commits and their bounded acceptance checks pass. A complete merger
  keyframe asset, native OpenXR device refresh, calibrated MR delivery, and any
  surrogate training corpus remain separate open production gates.
- Canonical source note:
  `references/source_notes/2026-08-10-bbh-dynamic-spacetime-foundations.md`.
- Existing single-hole regression baseline: `docs/current_status.md`.
- Existing long-range boundary: `docs/physical_scope.md` and
  `docs/validation_targets.md`.
- NPGS upstream/fork state must be refreshed before each native implementation
  batch; showcase media is never accepted as source evidence.

## Non-Negotiable Claim Boundaries

1. `real_time_metric_evaluation` means evaluating a prescribed metric at
   `(t,x)` during rendering. It does not mean solving Einstein's equations.
2. `real_time_ray_tracing` means integrating null geodesics through that metric
   on the GPU. It does not upgrade an approximate metric to an exact solution.
3. `nr_snapshot_truth` means tracing through versioned output of an offline
   Einstein evolution with recorded formulation, gauge, grid, interpolation,
   constraints, and producer commit.
4. In a generic dynamic metric, do not report `E`, `L_z`, or Carter `Q` as
   conserved unless the selected metric has the corresponding symmetry.
5. Runtime capture uses apparent horizons or explicit worldtubes. Event-horizon
   reconstruction is offline because the event horizon is future-global.
6. Any amplified GW displacement or deflection in XR records a dimensionless
   `visual_gain`; the unamplified physical value remains in the audit output.
7. A single current passthrough frame cannot represent delayed light from all
   directions. Missing camera history or angular coverage fails closed.

## Definition Of Real-Time

The performance report must keep these budgets separate:

| Budget | 72 Hz | 90 Hz |
| --- | ---: | ---: |
| Total frame p95 | `< 13.89 ms` | `< 11.11 ms` |
| Physics render target p95 | `< 11.0 ms` | `< 9.0 ms` |
| CPU frame submission p95 | recorded separately | recorded separately |
| GPU readback | forbidden in visual fast path | forbidden in visual fast path |

Passing 4K mono is not evidence for stereo XR. The first gate uses simulated
OpenXR views before a headset is required.

## Core Data Contracts

### `MetricSample`

The CPU and native interfaces expose the same physical fields:

```python
@dataclass(frozen=True)
class MetricSample:
    t: float
    x: np.ndarray                 # shape (3,)
    g_cov: np.ndarray             # shape (4, 4)
    g_inv: np.ndarray             # shape (4, 4)
    d_g_inv: np.ndarray           # shape (4, 4, 4), d_mu g^{ab}
    lapse: float
    shift: np.ndarray             # shape (3,)
    gamma_cov: np.ndarray         # shape (3, 3)
    gamma_inv: np.ndarray         # shape (3, 3)
    validity: str
    evidence_label: str
    source_revision: str
```

Native equivalent:

```cpp
struct MetricSample {
    double t;
    glm::dvec3 x;
    glm::dmat4 gCov;
    glm::dmat4 gInv;
    std::array<glm::dmat4, 4> dGInv;
    double lapse;
    glm::dvec3 shift;
    glm::dmat3 gammaCov;
    glm::dmat3 gammaInv;
    MetricValidity validity;
    EvidenceLabel evidence;
    MetricSourceId source;
};
```

The GPU form may omit redundant fields only when the omitted values are
algebraically reconstructed from the same shared metric implementation.

### Dynamic Hamiltonian

Use the covariant canonical momentum and the project signature `(-,+,+,+)`:

```text
H(t,x,p) = 1/2 g^mu_nu(t,x) p_mu p_nu = 0
dx^mu/dlambda = g^mu_nu p_nu
dp_mu/dlambda = -1/2 partial_mu(g^alpha_beta) p_alpha p_beta
```

Because `partial_t g != 0` in a BBH metric, `dp_t/dlambda` must be integrated.
The null constraint, provider constraints, and interpolation convergence replace
stationary Kerr conservation laws as the primary dynamic audit.

### `gr-bh-xr.bbh.ray-audit.v1`

Required fields:

- metric source ID, source/fork commit, evidence label, coordinates, gauge,
  units, and `meters_per_M`;
- observer event, four-velocity, tetrad, frame time, and OpenXR predicted time;
- initial/final `(x^mu,p_mu)`, affine interval, steps, rejected steps;
- event code: escape, apparent-horizon/worldtube hit, emitter hit, invalid,
  budget exhaustion;
- `max_abs_H`, initial/final `H`, null-projection count;
- metric interpolation order and local error estimate;
- Hamiltonian and momentum-constraint samples when the provider supplies them;
- apparent-horizon/worldtube source and timestamp;
- escape direction, redshift, time delay, and source/emitter intersections;
- raw physical GW effect and optional `visual_gain`-scaled display effect.

### `gr-bh-xr.bbh.adm-snapshot.v1`

Required datasets:

- axes/times in geometric units and the mapping to producer coordinates;
- `alpha`, `beta^i`, `gamma_ij`, `K_ij`;
- optional `partial_t alpha`, `partial_t beta^i`, `partial_t gamma_ij`;
- Hamiltonian/momentum constraints or enough fields to recompute them;
- apparent-horizon surfaces/worldtubes and gauge metadata;
- refinement hierarchy, ghost zones, interpolation order, and boundary mask;
- producer code, formulation, gauge, parameter file, commit, resolution, and
  checksum.

Waveform modes `h_lm(t)` or `Psi4_lm(t)` alone do not satisfy this schema.

### `gr-bh-xr.bbh.mr-timing.v1`

Required fields:

- `predicted_display_time`, `metric_time`, `binary_phase`;
- camera `capture_time`, exposure interval, capture pose, intrinsics, image
  sequence, and color encoding;
- depth/scene timestamp and pose independently from RGB;
- temporal camera-buffer span and interpolation policy;
- per-eye pose/origin/tetrad and `meters_per_M`;
- observed angular coverage and missing-radiance policy;
- physical effect, display effect, and `visual_gain`.

## Dependency Graph

```text
Task 0 literature freeze
  -> Task 1 simulated stereo performance gate
  -> Task 2 Python dynamic Hamilton oracle
  -> Task 3 metric-provider abstraction and Kerr zero regression
  -> Task 4 analytic dynamic metrics
  -> Task 5 approximate BBH CPU provider
  -> Task 6 approximate BBH GLSL provider and stereo benchmark
  -> Task 7 ADM snapshot schema and NR ingest
  -> Task 8 offline NR production pilot
  -> Task 9 dynamic MR/XR timing and finite-room intersections
  -> Task 10 surrogate/foveated acceleration decision
```

Tasks 1 and 2 may proceed in parallel after Task 0. Task 9 interface work may
begin after Task 3, but no dynamic-MR claim is allowed before Task 6 or Task 7
provides an accepted metric source.

---

### Task 0: Freeze The BBH Literature And Equation Baseline

**Files:**
- Modify: `references/references.md`
- Modify: `references/references.bib`
- Modify: `references/pdfs/README.md`
- Create/extend: `references/source_notes/2026-08-10-bbh-dynamic-spacetime-foundations.md`
- Modify: `docs/equations.md`
- Modify: `docs/validation_targets.md`
- Test: `tests/test_documentation_status.py`

**Steps:**

1. Download only redistribution-safe PDFs for the indexed arXiv sources.
2. Read the full equations used by Vincent 2012, Bohn 2015, Combi-Ressler v3,
   and the selected horizon reference.
3. Add the explicit 3+1-to-four-metric reconstruction and Hamilton equations to
   `docs/equations.md`, including all sign/index conventions.
4. Record the Combi-Ressler implementation repository and reviewed commit; do
   not port from a paper summary.
5. Pre-register analytic, approximate-metric, and NR-snapshot gates.
6. Run:

```powershell
python -m pytest -q tests/test_documentation_status.py
git diff --check
```

Expected: all indexed files/keys resolve and no whitespace errors.

**Commit:**

```text
docs: add BBH dynamic spacetime foundations
```

### Task 1: Add A Device-Independent Stereo Performance Gate

**Files:**
- Create: `runtime/NPGS/NPGS/Sources/Engine/Core/Runtime/XR/SyntheticStereoSink.h`
- Create: `runtime/NPGS/NPGS/Sources/Engine/Core/Runtime/XR/SyntheticStereoSink.cpp`
- Modify: `runtime/NPGS/NPGS/Sources/Engine/Core/Runtime/Graphics/Renderers/PipelineManager.cpp`
- Create: `tools/npgs/benchmark_stereo.ps1`
- Create: `src/gr_bh_xr/validate_npgs_stereo_performance.py`
- Create: `tests/test_validate_npgs_stereo_performance.py`
- Create: `validation/bbh_dynamic_spacetime/README.md`

**Steps:**

1. Write a parser test for per-eye GPU timestamp output and p50/p95/p99.
2. Add a synthetic render sink using asymmetric per-eye projection matrices but
   no OpenXR runtime.
3. Support sequential stereo first, then Vulkan multiview when available.
4. Benchmark per-eye resolutions `1600x1728`, `1832x1920`, `2064x2208`, and
   `2464x2592` with static Kerr, disk on/off, and polarization on/off.
5. Record GPU renderer time, composite/TAA time, CPU submission, VRAM, ray-step
   statistics, and dynamic-resolution/VRS settings. No readback in timed runs.
6. Persist JSON as `gr-bh-xr.npgs.stereo-performance.v1`.
7. Fail closed if fewer than 99% of timed frames have valid GPU timestamps.

**Acceptance:**

- No claim above the measured p95 refresh budget.
- Establish whether the current renderer reaches 72 Hz and 90 Hz before adding
  dynamic metric cost.
- Same-camera sequential and multiview images match within the configured
  numeric tolerance.

**Commit:**

```text
perf: add synthetic stereo NPGS gate
```

### Task 2: Implement The Python f64 Time-Dependent Hamilton Oracle

**Files:**
- Create: `src/gr_bh_xr/dynamic_metric.py`
- Create: `src/gr_bh_xr/geodesic_dynamic.py`
- Create: `src/gr_bh_xr/dynamic_types.py`
- Create: `tests/test_dynamic_metric.py`
- Create: `tests/test_geodesic_dynamic.py`

**Steps:**

1. Write a failing test proving that a stationary provider reproduces the
   current Kerr-Schild initial derivative and event classification.
2. Define `TimeDependentMetricProvider.sample(t, x) -> MetricSample`.
3. Implement the full eight-dimensional canonical RHS, including `dp_t`.
4. Integrate with DOP853 f64 and dense output; keep event evaluation separate
   from the metric provider.
5. Record `max_abs_H`, provider validity, interpolation diagnostics, and event
   provenance. Do not populate stationary conservation fields by default.
6. Add finite-difference derivative oracle checks for every provider analytic
   derivative.
7. Run:

```powershell
python -m pytest -q tests/test_dynamic_metric.py tests/test_geodesic_dynamic.py
```

**Acceptance:**

- Minkowski straight-line state agrees to `1e-11` in f64.
- Stationary Kerr adapter agrees with `geodesic_ks.py` on event and escape
  direction within existing f64 tolerance.
- A deliberately time-dependent test metric produces nonzero `dp_t` and does
  not report energy conservation.

**Commit:**

```text
feat: add time-dependent Hamilton reference solver
```

### Task 3: Add The Native Time-Dependent Metric Provider Interface

**Files:**
- Create: `runtime/NPGS/NPGS/Sources/Engine/Physics/Metric/IMetricProvider.h`
- Create: `runtime/NPGS/NPGS/Sources/Engine/Physics/Metric/KerrStationaryProvider.h`
- Create: `runtime/NPGS/NPGS/Sources/Engine/Physics/Metric/KerrStationaryProvider.cpp`
- Create: `runtime/NPGS/NPGS/Sources/Engine/Shaders/Common/MetricProvider.glsl`
- Modify: `runtime/NPGS/NPGS/Sources/Engine/Shaders/BlackHole_common.glsl`
- Modify: `runtime/NPGS/NPGS/Sources/Engine/Shaders/BlackHole_audit.frag.glsl`
- Create: `tests/test_npgs_dynamic_metric_contract.py`

**Steps:**

1. Write a source-contract test that requires metric time, evidence label,
   validity, all inverse-metric derivatives, and provider revision.
2. Wrap the existing accepted Kerr/Kerr-Newman implementation behind the
   provider interface without changing shader arithmetic.
3. Add a compile-time stationary optimization that may keep `p_t` fixed only
   when the provider declares stationarity.
4. Run native raw audit before and after the refactor.

**Acceptance:**

- Existing native Kerr/Kerr-Newman event, escape, disk, and Walker-Penrose gates
  remain numerically unchanged within their frozen tolerances.
- Native fast-path performance regression is `< 2%` for the stationary adapter;
  the overall migration budget remains `< 5%`.

**Commit:**

```text
refactor: add NPGS metric provider interface
```

### Task 4: Add Analytic Dynamic Metric Gates

**Files:**
- Create: `src/gr_bh_xr/metrics/minkowski_dynamic.py`
- Create: `src/gr_bh_xr/metrics/plane_gw.py`
- Create: `src/gr_bh_xr/validate_dynamic_analytic.py`
- Create: `tests/test_dynamic_analytic_metrics.py`
- Modify: `docs/equations.md`
- Modify: `validation/bbh_dynamic_spacetime/README.md`

**Steps:**

1. Implement Minkowski through the same provider interface.
2. Implement one transverse-traceless plane GW with explicit polarization,
   wave vector, amplitude, phase, and analytic metric derivatives.
3. Compare numerical rays with the perturbative Hamiltonian result of
   `angelil2015gwOptics` in the small-amplitude regime.
4. Add amplitude-halving convergence and zero-amplitude limits.
5. Record physical angular displacement separately from display amplification.

**Acceptance:**

- Zero-amplitude plane GW is exactly the Minkowski provider.
- The residual from the first-order analytic result scales as `O(h^2)`.
- `visual_gain=1` is an exact identity in the rendering/audit conversion.

**Commit:**

```text
test: add analytic dynamic-spacetime gates
```

### Task 5: Implement The Approximate BBH CPU Provider

**Prerequisite:** Task 0 must record the reviewed source-code revision for the
Combi-Ressler implementation. If no usable licensed source exists, implement
from the paper equations with a second independent symbolic/numerical oracle.

**Files:**
- Create: `src/gr_bh_xr/metrics/bbh_superposed_ks.py`
- Create: `src/gr_bh_xr/metrics/bbh_orbit.py`
- Create: `src/gr_bh_xr/metrics/bbh_remnant.py`
- Create: `src/gr_bh_xr/validate_bbh_constraints.py`
- Create: `tests/test_bbh_superposed_ks.py`
- Create: `tests/test_bbh_constraints.py`
- Modify: `docs/physical_scope.md`

**Steps:**

1. Implement the smallest validated slice: equal mass, nonspinning, circular
   inspiral at fixed separation. Do not start with generic spin/eccentricity.
2. Add unequal mass, aligned spin, then generic spin only after each earlier
   slice passes.
3. Derive or generate all `partial_mu g^ab`; compare against high-accuracy
   finite differences and automatic differentiation where practical.
4. Reconstruct 3+1 fields and calculate Hamiltonian/momentum constraints.
5. Validate large-separation isolated-Kerr limits and exchange symmetry.
6. Add PN orbital evolution and merger/remnant interpolation only after the
   fixed-orbit constraints are understood.

**Acceptance:**

- Exact symmetry/limit tests pass to f64 tolerance.
- Constraint norms are persisted as functions of separation, time, and spatial
  region; thresholds are preregistered from the source paper and convergence
  study, not invented after seeing final images.
- Every output carries `evidence_label=physics_approximation`.

**Commit sequence:**

```text
feat: add equal-mass superposed KS metric
feat: add PN BBH trajectories
feat: add merger-to-remnant metric transition
```

Do not squash these commits.

### Task 6: Port The Approximate BBH Provider To GLSL

**Files:**
- Create: `runtime/NPGS/NPGS/Sources/Engine/Shaders/Common/MetricBBH.glsl`
- Modify: `runtime/NPGS/NPGS/Sources/Engine/Shaders/Common/MetricProvider.glsl`
- Modify: `runtime/NPGS/NPGS/Sources/Engine/Shaders/BlackHole_common.glsl`
- Extend: `runtime/NPGS/NPGS/Sources/Engine/Shaders/BlackHole_audit.frag.glsl`
- Create: `src/gr_bh_xr/validate_npgs_bbh.py`
- Create: `tests/test_validate_npgs_bbh.py`

**Steps:**

1. Port the accepted minimal equal-mass provider first.
2. Use full dynamic canonical integration; do not keep `p_t` frozen.
3. Emit metric-time, apparent-horizon/worldtube hit, `max_abs_H`, steps,
   provider validity, and sampled constraint residuals in audit mode.
4. Compare CPU f64 and GPU f32 rays at identical initial states.
5. Re-run the synthetic stereo matrix from Task 1 with dynamic metric on/off.
6. Add critical/eyebrow adaptive sampling based on audit gradients, not RGB
   edge detection.

**Acceptance:**

- Stable-region event agreement `>= 98%`.
- Escaped-ray direction median `< 1e-4 rad`, RMS `< 5e-4 rad` for the first
  approved parameter slice.
- Both-invalid rays are excluded from headline agreement and reported
  separately.
- No 72/90 Hz claim unless dynamic p95 meets Task 1 budgets.

**Commit:**

```text
feat: add audited dynamic BBH tracing to NPGS
```

### Task 7: Define And Ingest Numerical-Relativity ADM Snapshots

**Files:**
- Create: `src/gr_bh_xr/nr_snapshot.py`
- Create: `src/gr_bh_xr/metrics/adm_snapshot.py`
- Create: `src/gr_bh_xr/convert_carpetx_snapshot.py`
- Create: `tests/test_nr_snapshot.py`
- Create: `validation/bbh_nr_snapshot/README.md`
- Modify: `docs/equations.md`

**Steps:**

1. Implement `gr-bh-xr.bbh.adm-snapshot.v1` with synthetic analytic data.
2. Reconstruct `g_mu_nu`, `g^mu_nu`, and derivatives from ADM fields.
3. Implement spatial interpolation with explicit refinement-level selection and
   a temporal interpolation strategy with stored error estimates.
4. Validate against analytic Minkowski, linear GW, and sampled Kerr data written
   through the schema.
5. Add a CarpetX/openPMD conversion path only after the synthetic schema gate.
6. Reject waveform-only SXS assets with a structured failure reason.

**Acceptance:**

- Analytic round trips recover metric and derivatives at the preregistered
  convergence order.
- Interpolation never crosses invalid AMR boundaries silently.
- Producer/gauge/checksum metadata is mandatory.

**Commit:**

```text
feat: add audited ADM snapshot ingestion
```

### Task 8: Run An Offline NR Production Pilot

**Files:**
- Create: `nr/einstein_toolkit/README.md`
- Create: `nr/einstein_toolkit/par/bbh_equal_mass.par`
- Create: `nr/einstein_toolkit/export_manifest.py`
- Create: `validation/bbh_nr_pilot/README.md`
- Modify: `references/references.md`

**Steps:**

1. Pin an Einstein Toolkit release and full thorn-list revision.
2. Pass Apples-with-Apples/Minkowski/linear-wave tests before BBH.
3. Generate TwoPuncturesX equal-mass nonspinning initial data.
4. Run a bounded low-resolution convergence pilot with BSSNOK or Z4c.
5. Export ADM snapshots, constraints, apparent horizons, and `Psi4`.
6. Trace the same camera through two resolutions and quantify image/transfer
   convergence.

**Acceptance:**

- No full-NR claim without at least two resolutions and constraint history.
- Apparent-horizon tracks and waveform timing agree with the producer output.
- NR ray results are compared with, but not forced to equal, the approximate
  metric.

**Commit:**

```text
feat: add first BBH numerical-relativity snapshot pilot
```

### Task 9: Add Dynamic-Spacetime OpenXR And MR Time Semantics

**Files:**
- Modify: `runtime/NPGS/NPGS/Sources/Engine/Core/Runtime/XR/RenderContract.h`
- Modify: `runtime/NPGS/NPGS/Sources/Engine/Core/Runtime/XR/MixedRealityContract.h`
- Create: `runtime/NPGS/NPGS/Sources/Engine/Core/Runtime/XR/CameraHistory.h`
- Create: `runtime/NPGS/NPGS/Sources/Engine/Core/Runtime/XR/CameraHistory.cpp`
- Modify: `src/gr_bh_xr/npgs_contract.py`
- Create: `tests/test_npgs_bbh_mr_contract.py`
- Modify: `validation/npgs_native_xr/README.md`

**Steps:**

1. Add `metric_time`, `binary_phase`, and predicted-display-time mapping.
2. Store a bounded calibrated camera-frame history keyed by capture time.
3. Add finite-distance intersections against depth/scene geometry; do not treat
   room pixels as radiance at infinity.
4. Select source frames by retarded arrival time when coverage exists.
5. Fail closed for stale frames, absent rear/side coverage, unknown color
   encoding, or inconsistent poses.
6. Emit physical and display-amplified GW effects separately.

**Acceptance before device access:**

- Synthetic moving-camera/moving-metric timing tests pass.
- Left/right eye rays use distinct eye origins and predicted poses.
- A stale current frame cannot satisfy a delayed-ray request in tests.

**Acceptance on device later:**

- Fresh calibrated RGB delivery is demonstrated independently of depth.
- World lock, stereo, 72/90 Hz timing, and camera-history behavior are recorded.
- Unobserved angular regions remain explicit rather than silently copied.

**Commit:**

```text
feat: add dynamic metric timing to native XR and MR
```

### Task 10: Decide Foveation, Keyframes, Or Surrogate From Measured Data

**Files:**
- Create: `docs/bbh_runtime_decision.md`
- Create: `src/gr_bh_xr/benchmark_bbh_runtime.py`
- Create: `tests/test_bbh_runtime_decision.py`
- Modify: `docs/physical_scope.md`

**Steps:**

1. Compare full-resolution dynamic tracing, foveated tracing, progressive
   transfer updates, time-indexed keyframes, and a hybrid mode.
2. Use Task 1/6 p95 data and Task 8 interpolation/convergence data.
3. Select one default runtime path per hardware class.
4. Only if exact buffers are sufficient, define a surrogate target over metric
   or transfer quantities. Do not train on final RGB as the sole target.

**Acceptance:**

- Decision thresholds are fixed before training.
- The surrogate, if selected, preserves event, direction, redshift, delay,
  image-order, and uncertainty outputs.
- Out-of-distribution metric/observer states fail closed to exact or keyframe
  fallback.

**Commit:**

```text
docs: select measured BBH runtime architecture
```

## Final Program Gates

The BBH/XR track is not complete until all applicable gates pass:

1. Literature and equation keys are indexed.
2. Stationary Kerr zero regression remains green.
3. Dynamic analytic metrics pass f64 convergence gates.
4. Approximate BBH constraints and limits are persisted and labeled.
5. CPU/GPU ray agreement passes on at least one preregistered BBH slice.
6. The measured stereo p95 determines, rather than marketing language, the
   refresh-rate claim.
7. NR snapshot interpolation passes analytic and resolution convergence gates.
8. Runtime horizons are labeled apparent/worldtube; event horizon is offline.
9. MR uses metric/display/capture time and camera history correctly.
10. Any GW visibility amplification records the unscaled physical result and
    `visual_gain`.

## Deferred Work

- Full GRMHD evolution in the headset frame loop.
- Charged plasma around Kerr-Newman or BBH without an independent matter model.
- Polarized BBH GRRT before scalar dynamic transfer is validated.
- Event-horizon reconstruction in real time.
- Generic six-degree-of-freedom near-merger motion before observer tetrads and
  metric-domain validity are solved.
- Neural final-image generation without audit buffers.

## Completion Record

Tasks 0-10 were completed as independent commits. The selected runtime decision
is evidence-driven: full-resolution dynamic NPGS tracing remains the offline
audit path, while time-indexed NR transfer keyframes are the qualified PCVR
architecture. The bounded `0..1M` Task 8 pilot proves the pinned production and
ingestion path but is not a complete merger asset, converged waveform, event
horizon, or surrogate training corpus. Device-only OpenXR/MR gates remain open
until hardware evidence is recorded.
