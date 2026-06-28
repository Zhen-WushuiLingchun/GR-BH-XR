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

Initial reference tolerance target:

```text
abs(H) < 1e-8
```

The tolerance may be revised only with a documented numerical reason.

## Phase 2 GPU Kerr Lensing

Required checks:

- CPU-vs-GPU agreement on fixed camera/spin/inclination cases;
- capture mask agreement near the Schwarzschild shadow;
- visible diagnostic buffers for ray order, capture mask, redshift map, and time
  delay map when those quantities exist;
- adaptive sampling or refinement near the critical curve.

## Phase 3 Quest PCVR

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

- disk intersection events are recorded by crossing/image order `m`;
- `r_m`, `phi_m`, `g_m`, `Delta t_m`, and `n_m` are inspectable;
- direct, secondary, and higher-order images can be isolated;
- redshift and Doppler terms are tested in at least one limiting or benchmark
  case;
- time-delay sampling is tested with a simple time-dependent disk feature.

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
