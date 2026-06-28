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
- Code review path:
- BibTeX key:
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
- PDF path: `references/pdfs/2018-raptor-i-time-dependent-grrt.pdf`
- Code review path: `references/code_reviews/2026-06-28-reference-code-baseline.md`
- BibTeX key: `bronzwaer2018raptor`
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
- PDF path: Not stored; open original PDF not confirmed in Phase 0.
- Code review path: `references/code_reviews/2026-06-28-reference-code-baseline.md`
- BibTeX key: `pu2016odyssey`; code key `pu2026odysseycode`
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
- PDF path: `references/pdfs/2016-bhac-black-hole-accretion-code.pdf`
- Code review path: Not reviewed in Phase 0; used as GRMHD paper baseline.
- BibTeX key: `porth2017bhac`
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
- PDF path: `references/pdfs/2022-aart-adaptive-analytical-ray-tracing.pdf`
- Code review path: `references/code_reviews/2026-06-28-reference-code-baseline.md`
- BibTeX key: `cardenas2023aart`; code key `cardenas2026aartcode`
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
- PDF path: `references/pdfs/2018-davelaar-supermassive-black-holes-vr.pdf`
- Code review path: Not applicable; paper precedent only.
- BibTeX key: `davelaar2018vr`
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
- Code review path: Not applicable.
- BibTeX key: Not applicable.
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
- Code review path: Not applicable.
- BibTeX key: Not applicable.
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
- Code review path: Not applicable.
- BibTeX key: Not applicable.
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
- Code review path: Not applicable.
- BibTeX key: Not applicable.
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

### RAPTOR Public Code Repository

- Source path: `references/source_notes/2026-06-28-phase0-download-log.md`
- PDF path: Not applicable; code repository.
- Code review path: `references/code_reviews/2026-06-28-reference-code-baseline.md`
- BibTeX key: `bronzwaer2026raptorcode`
- Stable locator: https://github.com/tbronzwaer/raptor
- Search date: 2026-06-28
- Search terms: RAPTOR GRRT code GitHub
- Why added: Reference implementation for time-dependent GRRT structure and
  dependencies.
- Short summary: C implementation with metric, integrator, emission, and
  radiative-transfer modules; default branch outputs image and spectrum data.
- Relevant equations / assumptions / methods: Ray integration plus scalar GRRT;
  polarization branch exists but has redistribution caveats.
- Project use: Benchmark target after local simplified GRRT exists.
- Limitations / open questions: Do not vendor code because default branch is
  GPL-3.0 and polarization branch is not treated as redistributable.

### AART Public Code Repository

- Source path: `references/source_notes/2026-06-28-phase0-download-log.md`
- PDF path: Not applicable; code repository.
- Code review path: `references/code_reviews/2026-06-28-reference-code-baseline.md`
- BibTeX key: `cardenas2026aartcode`
- Stable locator: https://github.com/iAART/aart
- Search date: 2026-06-28
- Search terms: AART photon ring code GitHub
- Why added: Reference for lensing-band construction and adaptive treatment near
  photon-ring/critical-curve structure.
- Short summary: Python implementation separating lensing bands, analytical ray
  tracing, image construction, visibility amplitudes, redshift, and
  polarization helpers.
- Relevant equations / assumptions / methods: Kerr integrability, Bardeen screen
  coordinates, nonuniform image-plane sampling.
- Project use: Design reference for Phase 1/2 sampling and validation outputs.
- Limitations / open questions: Use as conceptual benchmark; do not copy code.

### ipole Public Code Repository

- Source path: `references/source_notes/2026-06-28-phase0-download-log.md`
- PDF path: Not applicable; code repository.
- Code review path: `references/code_reviews/2026-06-28-reference-code-baseline.md`
- BibTeX key: `moscibrodzka2018ipole`; code key `gammie2026ipolecode`
- Stable locator: https://github.com/AFD-Illinois/ipole
- Search date: 2026-06-28
- Search terms: ipole polarized GRRT code GitHub
- Why added: Later polarized-GRRT benchmark and trace-output design reference.
- Short summary: C code for polarized covariant radiative transfer with HDF5
  image and trace-output workflows.
- Relevant equations / assumptions / methods: Polarized radiative transfer,
  geodesic diagnostics, model-specific GRMHD imaging.
- Project use: Later benchmark after scalar GRRT is validated; trace diagnostics
  inspire Phase 1 selected-ray outputs.
- Limitations / open questions: Not a Phase 1 dependency and not a
  general-purpose imaging substitute.

### grtrans Public Code Repository

- Source path: `references/source_notes/2026-06-28-phase0-download-log.md`
- PDF path: Not applicable; code repository.
- Code review path: `references/code_reviews/2026-06-28-reference-code-baseline.md`
- BibTeX key: `dexter2016grtrans`; code key `dexter2026grtranscode`
- Stable locator: https://github.com/jadexter/grtrans
- Search date: 2026-06-28
- Search terms: grtrans polarized GRRT code GitHub
- Why added: Later benchmark for model-rich polarized GRRT and scriptable
  geodesic/radiative-transfer tests.
- Short summary: Fortran/Python code covering camera coordinates, geodesic
  integration, radiative transfer, multiple fluid models, and debug outputs.
- Relevant equations / assumptions / methods: Kerr geodesics, Stokes-capable
  outputs, thin disk/HARM/hotspot/fluid-model pathways.
- Project use: Long-range benchmark for GRRT and diagnostic-output conventions.
- Limitations / open questions: Too broad for the first CPU Kerr solver and not
  vendored into this repository.
