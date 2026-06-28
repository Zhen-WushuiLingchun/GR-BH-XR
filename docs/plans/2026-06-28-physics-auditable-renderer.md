# Physics-Auditable Renderer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build GR-BH-XR as a physics-auditable XR renderer for Kerr black-hole lensing, disk transfer functions, and later GRRT/BBH extensions, rather than as a visual-only shader demo.

**Architecture:** The first-year system centers on a Kerr null-geodesic transfer map that exposes physics buffers, validation metrics, and XR-ready render outputs. Quest 3 is introduced early as a PCVR/MR viewer, while heavy geodesic/GRRT work remains on PC GPU or offline caches. BBH, GRMHD, and neural acceleration are treated as later layers after the Kerr transfer map is validated.

**Tech Stack:** Python or C++ reference solver, C++/CUDA or Vulkan compute for real-time kernels, Unity/OpenXR for Quest 3 PCVR/MR integration, HDF5 or equivalent structured files for lens maps and validation data, Markdown/BibTeX for auditable documentation.

---

## Non-Negotiable Project Position

The project output is not just RGB imagery. Every renderer milestone must be able
to expose or record the relevant transfer quantities:

```text
(alpha, beta) ->
  escape/capture,
  r_m, phi_m,
  g_m,
  Delta t_m,
  n_m,
  tau_m,
  I_nu_o
```

Any image-only path is considered a prototype unless it preserves traceability
to the physics buffers above.

## Stage Roadmap

1. Kerr ray tracing.
2. Disk transfer function and simplified GRRT.
3. GRMHD snapshot plus GRRT cache.
4. Time-dependent BBH plus accretion surrogate.

The first-year target is a single-Kerr PCVR/MR system with background lensing,
shadow, thin disk transfer function, redshift/Doppler terms, time-delay-aware
disk variability, higher-order images, and Quest 3 display through PCVR/MR
overlay. BBH and full GRMHD are second-year or later work.

## First-Version Exclusions

Do not start with:

- full GRMHD;
- BBH numerical relativity;
- Quest-native GRRT;
- neural networks that directly generate black-hole images;
- unvalidated GLSL-only black-hole shaders;
- RGB-only output without `g`, `Delta t`, `n`, `tau`, capture mask, or image
  order buffers.

## Task 1: Lock The Documentation Baseline

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/development_log.md`
- Create or maintain: `docs/physical_scope.md`
- Create or maintain: `docs/equations.md`
- Create or maintain: `docs/validation_targets.md`
- Modify: `references/references.md`

**Step 1: Check repository status**

Run:

```bash
git status --short --branch
```

Expected: no unrelated user edits are mixed with this planning work.

**Step 2: Confirm documentation contains physics-audit rules**

Check that `AGENTS.md` requires:

- physical buffers for renderer outputs;
- explicit coordinates, units, sign conventions, and normalizations;
- stage gates before adding disk, Quest, GRRT, GRMHD, BBH, or neural modules;
- literature entries in `references/references.md`;
- development-log entries explaining academic and physical correspondence.

**Step 3: Verify documentation consistency**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

**Step 4: Commit**

```bash
git add AGENTS.md README.md docs references
git commit -m "docs: define physics-auditable renderer plan"
```

## Task 2: Phase 0 Literature And Benchmark Baseline

**Files:**
- Modify: `references/references.md`
- Create or maintain: `references/pdfs/README.md`
- Create: `references/source_notes/YYYY-MM-DD-physics-auditable-renderer-sources.md`
- Create or update: `docs/physical_scope.md`
- Create or update: `docs/equations.md`
- Create or update: `docs/validation_targets.md`

**Step 1: Add required first-pass references**

Record at least these source families:

- AART for Kerr photon-ring adaptive analytical ray tracing.
- RAPTOR for time-dependent GRRT.
- Odyssey for public GPU-based Kerr GRRT.
- Davelaar et al. for GRMHD plus RAPTOR plus VR precedent.
- Meta Quest 3 optimization and Passthrough over Link documentation.
- Unity OpenXR Meta passthrough camera limitation.
- Meta Depth API documentation.

If a source has an original PDF that is open-access or safe to keep in Git,
store it under `references/pdfs/` and add its path to
`references/references.md`. If the PDF is restricted or too large, store it
under `references/pdfs/local_only/` and mark the index entry as local-only.

**Step 2: Define required vocabulary**

In `docs/physical_scope.md`, distinguish:

- shadow;
- critical curve;
- lensing ring;
- photon ring;
- direct image;
- secondary image;
- higher-order image;
- ISCO;
- disk inner edge.

**Step 3: Define equations and conventions**

In `docs/equations.md`, document:

- observer screen coordinates `(alpha, beta)`;
- null geodesic Hamiltonian;
- Schwarzschild and Kerr support scope;
- Kerr-Schild implementation preference near the horizon;
- Boyer-Lindquist/Carter-constant validation role;
- disk transfer function;
- intensity transform with `g^3` and bolometric `g^4` approximation;
- simplified invariant radiative transfer equation.

**Step 4: Define validation targets**

In `docs/validation_targets.md`, require:

- Hamiltonian/null drift tracking;
- conserved `E`, `L_z`, and Carter `Q` drift;
- Schwarzschild shadow critical impact parameter `b_c = 3 sqrt(3) M`;
- disk-crossing event checks;
- redshift and time-delay sanity checks;
- benchmark comparison with AART/RAPTOR/Odyssey once implementation exists.

**Step 5: Commit**

```bash
git add references docs
git commit -m "docs: add phase 0 physics benchmark baseline"
```

## Task 3: CPU Reference Kerr Ray Tracer

**Files:**
- Create: `physics/metric/schwarzschild.hpp`
- Create: `physics/metric/kerr_schild.hpp`
- Create: `physics/tetrad/observer_tetrad.hpp`
- Create: `physics/tetrad/screen_camera.hpp`
- Create: `physics/geodesic/hamiltonian_cpu.cpp`
- Create: `physics/geodesic/event_detection.cpp`
- Create: `physics/geodesic/validation.cpp`
- Create: `validation/schwarzschild_shadow/README.md`
- Create: `validation/kerr_critical_curve/README.md`

**Step 1: Write the failing invariant tests**

Add tests or a validation executable that samples a small grid of screen rays
and asserts:

```text
abs(g^{mu nu} p_mu p_nu) < configured_tolerance
```

Expected before implementation: the validation executable is missing or fails.

**Step 2: Implement observer tetrad and screen mapping**

Implement the mapping from observer pose and `(alpha, beta)` to initial
covariant momentum. Document the frame, units, and sign convention before the
code is considered complete.

**Step 3: Implement Hamiltonian integration**

Implement a conservative reference integrator for Schwarzschild first, then
Kerr. This phase prioritizes correctness and diagnostics over speed.

**Step 4: Implement events**

Classify each ray as:

- horizon capture;
- sky escape;
- equatorial disk crossing;
- invalid numerical state.

**Step 5: Write output files**

Expected outputs:

```text
data/lens_maps/lensmap_schwarzschild.h5
data/lens_maps/lensmap_kerr_a0.5_i60.h5
figures/shadow_validation.pdf
figures/ray_examples.pdf
```

These files may remain ignored until the data policy is explicit; record their
generation commands in validation notes.

**Step 6: Validate and commit**

Run the reference validation command chosen by the implementation. Expected:

- Hamiltonian drift is recorded per ray;
- Schwarzschild shadow recovers `3 sqrt(3) M` within the documented tolerance.

Commit:

```bash
git add physics validation docs
git commit -m "feat: add CPU reference Kerr ray tracer"
```

## Task 4: GPU Real-Time Kerr Lensing

**Files:**
- Create: `renderer/cuda_renderer/` or `renderer/vulkan_compute/`
- Create: `renderer/adaptive_sampler/`
- Create: `renderer/debug_views/`
- Modify: `docs/validation_targets.md`
- Modify: `docs/development_log.md`

**Step 1: Port only validated quantities**

Move the reference solver outputs to GPU representation only after the CPU
solver has stable invariant checks.

**Step 2: Produce physics buffers**

The GPU path must expose at least:

- RGBA image;
- capture mask;
- image or ray order;
- redshift map where applicable;
- time-delay map where applicable;
- diagnostic residuals or validation samples.

**Step 3: Add adaptive sampling around the critical curve**

Use the AART motivation: photon-ring and higher-order structures should not be
treated as uniform screen features.

**Step 4: Validate against CPU reference**

Run CPU-vs-GPU comparison on fixed camera/spin/inclination cases. Expected:
differences are documented, bounded, and explainable.

**Step 5: Commit**

```bash
git add renderer physics validation docs
git commit -m "feat: add GPU Kerr lensing prototype"
```

## Task 5: Quest 3 PCVR Viewer Gate

**Files:**
- Create: `xr/unity_frontend/`
- Create: `xr/openxr_bridge/`
- Create: `xr/quest_link_mode/`
- Modify: `docs/validation_targets.md`
- Modify: `docs/development_log.md`

**Step 1: Build stereo PCVR viewer**

Connect the PC-rendered Kerr lensing texture to a stereo camera view. Do not
move GRRT or high-precision geodesic integration onto the headset.

**Step 2: Validate headset behavior**

Record:

- whether stereo disparity is correct;
- whether lens map is stable under head motion;
- whether 72 Hz or 90 Hz can be maintained;
- whether angular size and scale are comfortable;
- PC-to-Quest latency observations.

**Step 3: Minimum success condition**

Quest 3 shows a head-stable Kerr shadow plus background lensing through
Quest Link or Air Link.

**Step 4: Commit**

```bash
git add xr docs
git commit -m "feat: add Quest PCVR Kerr viewer"
```

## Task 6: Thin Disk Transfer Function

**Files:**
- Create: `physics/transfer/disk_intersection.cpp`
- Create: `physics/transfer/redshift.cpp`
- Create: `physics/transfer/time_delay.cpp`
- Create: `physics/transfer/image_order.cpp`
- Create: `validation/disk_redshift/README.md`
- Modify: `docs/equations.md`
- Modify: `docs/validation_targets.md`

**Step 1: Add disk crossing records**

For every crossing order `m`, record:

```text
T_m(alpha, beta) = (r_m, phi_m, g_m, Delta t_m, n_m)
```

**Step 2: Implement disk model**

Use an optically thick thin-disk surface with:

```text
theta = pi / 2
r_in = r_ISCO(a)
r_out = R_out
```

**Step 3: Implement redshift and intensity transform**

Track frequency shift and intensity:

```text
I_nu_o = sum_m g_m^3 I_nu_e(r_m, phi_m, t_o - Delta t_m, nu_o / g_m)
I_o approx sum_m g_m^4 I_e
```

**Step 4: Validate higher-order behavior**

Render direct, secondary, and higher-order images separately and record which
buffer distinguishes them.

**Step 5: Commit**

```bash
git add physics/transfer validation docs
git commit -m "feat: add thin disk transfer function"
```

## Task 7: Quest 3 MR Overlay And Depth Occlusion

**Files:**
- Create: `xr/depth_occlusion/`
- Create: `xr/spatial_anchor/`
- Modify: `docs/physical_scope.md`
- Modify: `docs/validation_targets.md`

**Step 1: Implement MR-1 only**

The first MR milestone is:

```text
passthrough background
+ black-hole disk/shadow virtual layer
+ Depth API occlusion
```

Do not claim true passthrough pixel lensing at this stage.

**Step 2: Add parameter panel**

Expose:

- mass scale or angular-size control;
- spin `a`;
- inclination `i`;
- observer radius `r_obs`;
- disk emissivity;
- image-order cutoff.

**Step 3: Validate occlusion**

Record a screenshot or video where a real hand/controller or depth-tested object
occludes the virtual black-hole layer.

**Step 4: Commit**

```bash
git add xr docs
git commit -m "feat: add Quest MR overlay gate"
```

## Task 8: Simplified GRRT

**Files:**
- Create: `physics/grrt/invariant_rt.cpp`
- Create: `physics/grrt/synchrotron.cpp`
- Create: `physics/grrt/opacity.cpp`
- Create: `physics/grrt/polarization_later.cpp`
- Create: `validation/raptor_comparison/README.md`
- Create: `validation/odyssey_comparison/README.md`
- Modify: `docs/equations.md`
- Modify: `docs/validation_targets.md`

**Step 1: Implement unpolarized emission/absorption first**

Use analytic RIAF or torus fields:

```text
j_nu = j_nu(rho, T_e, B, nu)
alpha_nu = alpha_nu(rho, T_e, B, nu)
dIcal / dlambda = Jcal - Acal Ical
```

**Step 2: Defer polarization**

Do not implement Stokes transport until the scalar invariant intensity path is
validated.

**Step 3: Benchmark**

Compare at least one setup against RAPTOR, Odyssey, ipole, grtrans, or a
documented analytical limit.

**Step 4: Commit**

```bash
git add physics/grrt validation docs
git commit -m "feat: add simplified GRRT path"
```

## Task 9: GRMHD Snapshot And Cache Path

**Files:**
- Create: `data/grmhd_snapshots/README.md`
- Create: `data/cached_radiance_fields/README.md`
- Create: `validation/grmhd_snapshot/README.md`
- Modify: `docs/physical_scope.md`

**Step 1: Use existing snapshots**

Do not implement a GRMHD solver. Read existing BHAC/HARM/Athena++-like snapshot
fields:

```text
rho, u^mu, b^mu, u_gas, T_e, p
```

**Step 2: Convert snapshots to cached radiance**

Pipeline:

```text
GRMHD snapshot
-> interpolation
-> j_nu, alpha_nu
-> GRRT
-> movie/cache
-> Quest playback/query
```

**Step 3: Keep Quest as query/playback**

Quest 3 should query cached radiance or play constrained 360/6DoF-limited media,
not run full real-time GRRT.

**Step 4: Commit**

```bash
git add data validation docs
git commit -m "feat: add GRMHD cache integration path"
```

## Task 10: BBH Long-Range Track

**Files:**
- Create: `physics/metric/adm_metric.hpp`
- Create: `validation/bbh_vacuum_lensing/README.md`
- Modify: `docs/physical_scope.md`
- Modify: `docs/equations.md`

**Step 1: Start with BBH-1 visual toy only after Kerr pipeline is stable**

The UI must label this as:

```text
Approximate visual model, not a solution of Einstein equations.
```

**Step 2: Move to BBH-2 only with an explicit metric source**

Time-dependent vacuum lensing must use a documented numerical-relativity or
approximate ADM metric source.

**Step 3: Add toy accretion only after vacuum lensing**

Phenomenological accretion is allowed for interaction and visualization, but it
must not be described as full GRMHD.

**Step 4: Treat BBH + GRMHD + GRRT as offline/cache/surrogate**

The realistic architecture is:

```text
HPC/PC offline
-> neural/cache representation
-> Quest real-time query
```

**Step 5: Commit**

```bash
git add physics/metric validation docs
git commit -m "docs: define BBH extension gates"
```

## Neural Acceleration Policy

Neural networks may learn transfer functions or cached radiance fields only
after exact data exists. They must not replace audit buffers.

Allowed targets:

```text
(alpha, beta, a, i, r_obs) -> (r_m, phi_m, g_m, Delta t_m, n_m)
(alpha, beta, t, params) -> (I_nu, tau, g, order)
```

Preferred hybrid:

```text
NN coarse prediction + exact geodesic correction near critical curve
```

## Milestone Table

| Time | Target | Quest status | Academic value |
| ---: | --- | --- | --- |
| 1-2 weeks | Literature, equations, benchmarks | No | Required foundation |
| 3-5 weeks | CPU Kerr geodesic solver | No | Medium |
| 6-8 weeks | GPU Kerr lensing plus Quest PCVR first look | Yes, PCVR | Medium |
| 2-3 months | Thin disk transfer function plus high-order images | Yes | High |
| 3-4 months | Quest MR overlay plus depth occlusion | Yes | Medium-high |
| 4-8 months | Simplified GRRT | PC plus Quest playback | High |
| 8-12 months | GRMHD snapshot plus GRRT cache | Quest query/playback | Very high |
| 12-18 months | BBH vacuum lensing prototype | PCVR | Research-grade |
| 18-24 months | BBH toy accretion plus time delay | PCVR/offline | Very high |
| 24+ months | BBH plus GRMHD plus GRRT surrogate | Quest query | Research-topic scale |

## Execution Rule

Each phase must end with:

- updated development log;
- updated validation notes;
- updated references when new literature is used;
- a reproducible command or recorded reason why automated validation is not yet
  possible;
- a focused commit.
