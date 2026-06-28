# References Index

This file is the required index for literature and source material stored in
`references/`. Add or update an entry whenever a paper, source note, exported
citation, dataset description, or literature-search result is added.

Original PDFs should go under `references/pdfs/` when they are safe to keep in
Git. Restricted, license-unclear, oversized, or temporary PDFs should go under
`references/pdfs/local_only/`, which is ignored by Git.

## Entry Template

### citation-key-or-short-title

- Source path:
- PDF path:
- Stable locator:
- Search date:
- Search terms:
- Why added:
- Short summary:
- Relevant equations / assumptions / methods:
- Project use:
- Limitations / open questions:

## References

### RAPTOR I - Time-dependent GRRT

- Source path: `references/source_notes/2026-06-28-physics-auditable-renderer-sources.md`
- PDF path: Not stored yet.
- Stable locator: https://arxiv.org/abs/1801.10452
- Search date: 2026-06-28
- Search terms: RAPTOR time-dependent GRRT benchmark
- Why added: Baseline for time-dependent GRRT benchmark and terminology.
- Short summary: Public literature reference for image/movie/spectrum
  generation through geodesic and radiative-transfer integration in strong
  gravity.
- Relevant equations / assumptions / methods: Ray integration plus invariant
  radiative transfer.
- Project use: Benchmark simplified GRRT and validate transfer terminology.
- Limitations / open questions: Choose exact comparison cases after local GRRT
  implementation exists.

### Odyssey - GPU-based Kerr GRRT

- Source path: `references/source_notes/2026-06-28-physics-auditable-renderer-sources.md`
- PDF path: Not stored yet.
- Stable locator: https://github.com/hungyipu/Odyssey
- Search date: 2026-06-28
- Search terms: Odyssey GPU Kerr GRRT CUDA C++
- Why added: Public GPU-based GRRT code relevant to implementation strategy.
- Short summary: CUDA/C++-oriented Kerr GRRT codebase for ray tracing and
  radiative transfer.
- Relevant equations / assumptions / methods: Kerr ray tracing, radiative
  transfer formulation, GPU implementation.
- Project use: Possible benchmark and GPU architecture reference.
- Limitations / open questions: Need to inspect supported assumptions before
  direct numerical comparison.

### BHAC - Black Hole Accretion Code

- Source path: `references/source_notes/2026-06-28-physics-auditable-renderer-sources.md`
- PDF path: Not stored yet.
- Stable locator: https://arxiv.org/abs/1611.09720
- Search date: 2026-06-28
- Search terms: BHAC black hole accretion GRMHD
- Why added: Later GRMHD snapshot source and terminology reference.
- Short summary: GRMHD code reference for black-hole accretion simulations.
- Relevant equations / assumptions / methods: GRMHD conservation laws,
  multidimensional accretion simulations, arbitrary-spacetime support.
- Project use: Later snapshot ingestion and GRRT post-processing path.
- Limitations / open questions: Running GRMHD is outside first-version scope.

### AART - Adaptive Analytical Ray Tracing

- Source path: `references/source_notes/2026-06-28-physics-auditable-renderer-sources.md`
- PDF path: Not stored yet.
- Stable locator: https://arxiv.org/abs/2211.07469
- Search date: 2026-06-28
- Search terms: AART Kerr photon ring adaptive analytical ray tracing
- Why added: Motivates adaptive treatment near critical curves and photon rings.
- Short summary: Kerr photon-ring ray-tracing reference using adaptive,
  nonuniform treatment for high-order image structure.
- Relevant equations / assumptions / methods: Kerr integrability, photon-ring
  and high-order image analysis.
- Project use: Critical-curve sampling design and validation target.
- Limitations / open questions: Need comparable local quantities before formal
  benchmark use.

### Davelaar et al. - Black-hole VR Precedent

- Source path: `references/source_notes/2026-06-28-physics-auditable-renderer-sources.md`
- PDF path: Not stored yet.
- Stable locator: https://arxiv.org/abs/1811.08369
- Search date: 2026-06-28
- Search terms: black hole virtual reality GRMHD RAPTOR Davelaar
- Why added: Prior route from GRMHD plus GRRT to immersive black-hole
  visualization.
- Short summary: Demonstrates offline/post-processed black-hole VR based on
  simulation and GRRT rendering.
- Relevant equations / assumptions / methods: GRMHD simulation, RAPTOR
  post-processing, 360-degree VR visualization.
- Project use: Justifies later GRMHD cache/playback route for XR.
- Limitations / open questions: Precedent for offline VR, not headset-native
  real-time GRRT.

### Meta Quest Device Optimization

- Source path: `references/source_notes/2026-06-28-physics-auditable-renderer-sources.md`
- PDF path: Not applicable; official web documentation.
- Stable locator: https://developers.meta.com/horizon/resources/device-optimization-comparison/
- Search date: 2026-06-28
- Search terms: Quest 3 optimization refresh rate frame budget
- Why added: Establishes headset performance constraints.
- Short summary: Meta device guidance for Quest performance targets.
- Relevant equations / assumptions / methods: Refresh rate and frame-budget
  planning.
- Project use: PCVR-first architecture and headset validation gate.
- Limitations / open questions: Re-check before release because device guidance
  can change.

### Meta Passthrough Over Link

- Source path: `references/source_notes/2026-06-28-physics-auditable-renderer-sources.md`
- PDF path: Not applicable; official web documentation.
- Stable locator: https://developers.meta.com/horizon/documentation/native/android/mobile-passthrough-over-link/
- Search date: 2026-06-28
- Search terms: Meta passthrough over Link host PC
- Why added: Supports PC-hosted Quest MR iteration.
- Short summary: Developer path for passthrough-enabled Link iteration.
- Relevant equations / assumptions / methods: PCVR/MR deployment path.
- Project use: Quest Link/Air Link development workflow.
- Limitations / open questions: Verify behavior on local hardware and current
  SDK.

### Unity OpenXR Meta Camera / Passthrough

- Source path: `references/source_notes/2026-06-28-physics-auditable-renderer-sources.md`
- PDF path: Not applicable; official web documentation.
- Stable locator: https://docs.unity3d.com/Packages/com.unity.xr.meta-openxr%402.2/manual/features/camera.html
- Search date: 2026-06-28
- Search terms: Unity OpenXR Meta passthrough camera pixel data
- Why added: Defines MR passthrough pixel-access limits.
- Short summary: Important for distinguishing MR overlay from true passthrough
  pixel lensing.
- Relevant equations / assumptions / methods: API limitation and compositor
  behavior rather than physics equations.
- Project use: MR-1/MR-2/MR-3 staging and claim control.
- Limitations / open questions: Package-version dependent; re-check against the
  exact Unity/OpenXR package in use.

### Meta Depth API

- Source path: `references/source_notes/2026-06-28-physics-auditable-renderer-sources.md`
- PDF path: Not applicable; official web documentation.
- Stable locator: https://developers.meta.com/horizon/documentation/unity/unity-depthapi-overview/
- Search date: 2026-06-28
- Search terms: Meta Depth API Unity occlusion
- Why added: Basis for MR depth occlusion.
- Short summary: Provides a route for real-world objects to occlude virtual
  content.
- Relevant equations / assumptions / methods: Real-time depth map use in MR
  compositing.
- Project use: MR-1 depth-aware black-hole overlay.
- Limitations / open questions: Validate quality and support on target device.
