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
- PDF path: `references/pdfs/2016-odyssey-gpu-kerr-grrt.pdf`
- Code review path: `references/code_reviews/2026-06-28-reference-code-baseline.md`
- BibTeX key: `pu2016odyssey`; code key `pu2026odysseycode`
- Stable locator: https://arxiv.org/abs/1601.02063 (paper);
  https://github.com/hungyipu/Odyssey (code)
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
- Archived snapshot: Pending; Wayback save requested 2026-06-29 but no snapshot
  confirmed yet. Re-archive before any release milestone.
- Accessed: 2026-06-28
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
- Archived snapshot: http://web.archive.org/web/20260523153034/https://developers.meta.com/horizon/documentation/native/android/mobile-passthrough-over-link/
- Accessed: 2026-06-28
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
- Archived snapshot: http://web.archive.org/web/20260227043113/https://docs.unity3d.com/Packages/com.unity.xr.meta-openxr@2.2/manual/features/camera.html
- Accessed: 2026-06-28
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
- Archived snapshot: http://web.archive.org/web/20260616003018/https://developers.meta.com/horizon/documentation/unity/unity-depthapi-overview/
- Accessed: 2026-06-28
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
- PDF path: `references/pdfs/2017-ipole-polarized-radiative-transfer.pdf`
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
- PDF path: `references/pdfs/2016-grtrans-public-polarized-grrt.pdf`
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

### RAPTOR II - Polarized Radiative Transfer

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: `references/pdfs/2020-raptor-ii-polarized-radiative-transfer.pdf`
- Code review path: `references/code_reviews/2026-06-28-reference-code-baseline.md`
- BibTeX key: `bronzwaer2020raptorii`
- Stable locator: https://arxiv.org/abs/2007.03045
- Search date: 2026-06-28
- Search terms: RAPTOR II polarized radiative transfer curved spacetime
- Why added: Extends the scalar GRRT baseline toward polarized transfer.
- Short summary: Formulates polarized radiative transfer in curved spacetime in
  the RAPTOR family.
- Relevant equations / assumptions / methods: Stokes transport, observer
  tetrads, curved-spacetime transfer conventions.
- Project use: Later polarization benchmark after scalar transfer is validated.
- Limitations / open questions: Not a Phase 1 dependency.

### grtrans Paper - Public Polarized GRRT

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: `references/pdfs/2016-grtrans-public-polarized-grrt.pdf`
- Code review path: `references/code_reviews/2026-06-28-reference-code-baseline.md`
- BibTeX key: `dexter2016grtrans`
- Stable locator: https://arxiv.org/abs/1602.03184
- Search date: 2026-06-28
- Search terms: Dexter public code general relativistic polarised radiative transfer
- Why added: Links the reviewed grtrans repository to its public paper.
- Short summary: Public polarized GRRT code paper for spinning black-hole
  imaging.
- Relevant equations / assumptions / methods: Kerr geodesics, polarized
  radiative transfer, camera and fluid model choices.
- Project use: Long-range benchmark and diagnostic-output reference.
- Limitations / open questions: Too broad for the first CPU Kerr solver.

### ipole Paper - Relativistic Polarized Transport

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: `references/pdfs/2017-ipole-polarized-radiative-transfer.pdf`
- Code review path: `references/code_reviews/2026-06-28-reference-code-baseline.md`
- BibTeX key: `moscibrodzka2018ipole`
- Stable locator: https://arxiv.org/abs/1712.03057
- Search date: 2026-06-28
- Search terms: ipole polarized relativistic radiative transport
- Why added: Adds a paper-level reference for later Stokes transport.
- Short summary: Semianalytic scheme for relativistic polarized radiative
  transport.
- Relevant equations / assumptions / methods: Polarized transfer along
  relativistic rays through fluid models.
- Project use: Later benchmark after scalar GRRT and ray diagnostics exist.
- Limitations / open questions: Polarization remains deferred.

### Younsi Wu Fuerst - GRRT Formulation

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: `references/pdfs/2012-grrt-formulation-younsi-wu-fuerst.pdf`
- Code review path: Not applicable; paper reference.
- BibTeX key: `younsi2012grrt`
- Stable locator: https://arxiv.org/abs/1207.4234
- Search date: 2026-06-28
- Search terms: general relativistic radiative transfer Younsi Wu Fuerst
- Why added: Provides formulation-level GRRT background.
- Short summary: Derives and applies GRRT to structured tori around black
  holes.
- Relevant equations / assumptions / methods: Invariant transfer, emission
  model choices, strong-field ray tracing.
- Project use: Equation and convention reference for simplified GRRT.
- Limitations / open questions: Choose narrower benchmark cases later.

### HARM - Numerical GRMHD Scheme

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: `references/pdfs/2003-harm-grmhd-scheme.pdf`
- Code review path: Not applicable; paper reference.
- BibTeX key: `gammie2003harm`
- Stable locator: https://arxiv.org/abs/astro-ph/0301509
- Search date: 2026-06-28
- Search terms: HARM general relativistic magnetohydrodynamics
- Why added: Foundational GRMHD scheme behind many black-hole accretion
  workflows.
- Short summary: Conservative GRMHD numerical scheme for relativistic accretion
  simulations.
- Relevant equations / assumptions / methods: GRMHD conservation form, finite
  volume evolution, HARM-family terminology.
- Project use: Later snapshot provenance and field-name interpretation.
- Limitations / open questions: Implementing GRMHD is outside first-year scope.

### Noble et al. - Primitive Variable Solvers

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: `references/pdfs/2005-primitive-variable-solvers-grmhd.pdf`
- Code review path: Not applicable; paper reference.
- BibTeX key: `noble2006primitive`
- Stable locator: https://arxiv.org/abs/astro-ph/0512420
- Search date: 2026-06-28
- Search terms: primitive variable solvers conservative GRMHD
- Why added: Primitive recovery is central to interpreting conservative GRMHD
  data products.
- Short summary: Compares primitive-variable inversion methods for conservative
  GRMHD.
- Relevant equations / assumptions / methods: Conservative-to-primitive
  recovery and failure modes.
- Project use: Later GRMHD snapshot ingestion and validation notes.
- Limitations / open questions: Not needed before snapshot ingestion exists.

### EHT GRMHD Code Comparison

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: `references/pdfs/2019-eht-grmhd-code-comparison.pdf`
- Code review path: Not applicable; paper reference.
- BibTeX key: `porth2019ehtgrmhdcomparison`
- Stable locator: https://arxiv.org/abs/1904.04923
- Search date: 2026-06-28
- Search terms: Event Horizon GRMHD code comparison project
- Why added: Establishes cross-code comparison practice for black-hole GRMHD.
- Short summary: Compares multiple GRMHD codes in Event Horizon Telescope
  contexts.
- Relevant equations / assumptions / methods: Code-to-code comparison,
  benchmark setup, accretion-flow evolution diagnostics.
- Project use: Later benchmark culture and snapshot provenance target.
- Limitations / open questions: Not a renderer validation by itself.

### iharm3D - Vectorized GRMHD

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: `references/pdfs/2021-iharm3d-vectorized-grmhd.pdf`
- Code review path: Not applicable; paper reference.
- BibTeX key: `prather2021iharm3d`
- Stable locator: https://arxiv.org/abs/2110.10191
- Search date: 2026-06-28
- Search terms: iharm3D vectorized GRMHD
- Why added: Modern HARM-family implementation reference.
- Short summary: Vectorized GRMHD code in the HARM lineage.
- Relevant equations / assumptions / methods: GRMHD evolution and code
  implementation metadata.
- Project use: Later data provenance and snapshot compatibility context.
- Limitations / open questions: Not a first implementation target.

### Athena++ Radiation-GRMHD Extension

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: `references/pdfs/2023-athena-radiation-grmhd.pdf`
- Code review path: Not applicable; paper reference.
- BibTeX key: `white2023athenaRadiationGRMHD`
- Stable locator: https://arxiv.org/abs/2302.04283
- Search date: 2026-06-28
- Search terms: Athena++ radiation magnetohydrodynamics general relativity
- Why added: Broader relativistic radiation-fluid context for future stages.
- Short summary: Extends Athena++ for radiation-MHD in general relativity using
  finite-solid-angle discretization.
- Relevant equations / assumptions / methods: Radiation-MHD and angular
  discretization in GR.
- Project use: Long-range context for radiative-fluid simulation outputs.
- Limitations / open questions: No first-year dependency.

### KORAL M1 Radiation-GRHD Scheme

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: `references/pdfs/2012-koral-m1-radiation-grhd.pdf`
- Code review path: Not applicable; paper reference.
- BibTeX key: `sadowski2013koralM1`
- Stable locator: https://arxiv.org/abs/1212.5050
- Search date: 2026-06-28
- Search terms: KORAL M1 radiation general relativistic conservative fluid dynamics
- Why added: Adds radiation-fluid context beyond ideal GRMHD.
- Short summary: Semi-implicit M1 radiation scheme for conservative relativistic
  fluid dynamics.
- Relevant equations / assumptions / methods: M1 closure and semi-implicit
  source treatment.
- Project use: Long-range radiative-fluid vocabulary and limitations.
- Limitations / open questions: Not needed for first scalar GRRT.

### Bruneton - Real-time Black-Hole Shader Paper

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: `references/pdfs/2020-bruneton-realtime-black-hole-shader.pdf`
- Code review path: `references/code_reviews/2026-06-28-glsl-and-realtime-projects.md`
- BibTeX key: `bruneton2020realtimeBlackHoleShader`
- Stable locator: https://arxiv.org/abs/2010.08735
- Search date: 2026-06-28
- Search terms: real-time high-quality black-hole shader GLSL
- Why added: Peer-reviewed-style real-time shader reference with documented
  precomputation strategy.
- Short summary: High-quality real-time Schwarzschild black-hole rendering with
  precomputed deflection/inverse-radius tables.
- Relevant equations / assumptions / methods: Schwarzschild ray-deflection
  cache, disk intersections, Doppler/beaming shader model.
- Project use: Cache and test-structure inspiration after CPU reference maps
  exist.
- Limitations / open questions: Non-rotating only; not a Kerr GRRT benchmark.

### Li et al. - Kerr-Newman Polarized Radiative Transfer

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: `references/pdfs/2026-kerr-newman-polarized-radiative-transfer.pdf`
- Code review path: Not applicable; paper reference.
- BibTeX key: `li2026kerrNewmanPolarizedTransfer`
- Stable locator: https://arxiv.org/abs/2601.14785
- Search date: 2026-06-28
- Search terms: Kerr-Newman polarized radiative transfer black hole
- Why added: New Kerr-Newman/polarization literature relevant to the user's
  GLSL reference request.
- Short summary: Treats polarized radiative transfer around Kerr-Newman black
  holes.
- Relevant equations / assumptions / methods: Kerr-Newman charge and polarized
  transfer.
- Project use: Watchlist for future exploratory Kerr-Newman visualization.
- Limitations / open questions: Electric charge is outside the first-year
  validated Kerr scope.

### Zhihu Kerr-Newman GLSL Article

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: Not applicable; web article not stored.
- Code review path: `references/code_reviews/2026-06-28-glsl-and-realtime-projects.md`
- BibTeX key: `zhihu2026kerrNewmanRealtime`
- Stable locator: https://zhuanlan.zhihu.com/p/2003513260645830673
- Search date: 2026-06-28
- Search terms: Kerr-Newman real-time GLSL renderer Zhihu
- Why added: User-requested new GLSL/real-time black-hole rendering reference.
- Short summary: Gray-literature article describing a Kerr-Newman-oriented
  shader renderer with observer modes, redshift, disk/jet effects, and
  performance-oriented approximations.
- Relevant equations / assumptions / methods: Ingoing Kerr-Schild coordinates,
  Hamiltonian-style photon integration, tetrad observers, Doppler/beaming terms.
- Project use: Engineering and UI inspiration only.
- Limitations / open questions: Not peer-reviewed and not redistributed here.

### NPGS Public Code Repository

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: Not applicable; code repository.
- Code review path: `references/code_reviews/2026-06-28-glsl-and-realtime-projects.md`
- BibTeX key: `baopinshui2026npgscode`
- Stable locator: https://github.com/baopinshui/NPGS
- Search date: 2026-06-28
- Search terms: NPGS black hole GLSL Kerr-Newman GitHub
- Why added: User-requested code project for real-time GLSL black-hole
  rendering.
- Short summary: C++/Vulkan-oriented project with black-hole GLSL shader files
  and many physics-facing UI controls.
- Relevant equations / assumptions / methods: Shader-side Kerr/Kerr-Newman
  parameters, observer modes, disk/jet styling, shadow culling, debug toggles.
- Project use: GPU parameter layout and debug-control inspiration.
- Limitations / open questions: GPL-3.0; do not vendor or copy code.

### Bruneton Black-Hole Shader Repository

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: `references/pdfs/2020-bruneton-realtime-black-hole-shader.pdf`
- Code review path: `references/code_reviews/2026-06-28-glsl-and-realtime-projects.md`
- BibTeX key: `bruneton2026blackHoleShaderCode`
- Stable locator: https://github.com/ebruneton/black_hole_shader
- Search date: 2026-06-28
- Search terms: black hole shader WebGL2 GitHub Bruneton
- Why added: Real-time shader reference with paper, preprocessing, and tests.
- Short summary: WebGL2 Schwarzschild black-hole shader implementation with
  precomputed ray tables.
- Relevant equations / assumptions / methods: Precomputed deflection and
  inverse-radius textures.
- Project use: Cache-generation and shader-test design reference.
- Limitations / open questions: Schwarzschild only.

### Oseiskar WebGL Black-Hole Repository

- Source path: `references/source_notes/2026-06-28-expanded-grrt-fluid-glsl-sources.md`
- PDF path: Not applicable; code repository.
- Code review path: `references/code_reviews/2026-06-28-glsl-and-realtime-projects.md`
- BibTeX key: `oseiskar2026blackHoleCode`
- Stable locator: https://github.com/oseiskar/black-hole
- Search date: 2026-06-28
- Search terms: black hole WebGL Schwarzschild GLSL ODE GitHub
- Why added: Additional real-time WebGL project with explicit artifact notes.
- Short summary: GLSL/three.js Schwarzschild simulation integrating geodesic
  ODEs on the GPU.
- Relevant equations / assumptions / methods: Normalized Schwarzschild units,
  relativistic effect toggles, quality/performance modes.
- Project use: Interaction and artifact-disclosure reference.
- Limitations / open questions: Visual demo; not a Kerr or GRRT benchmark.

## Foundational Analytic References

These are the primary sources behind the equations in `docs/equations.md` and the
vocabulary in `docs/physical_scope.md`. Pre-arXiv classics have no open-access
PDF; they are indexed by DOI/bibcode and a personal copy may be placed under the
ignored `references/pdfs/local_only/`.

### Carter 1968 - Kerr Separability And Carter Constant

- Source path: `references/source_notes/2026-06-29-foundational-analytic-references.md`
- PDF path: Not stored; pre-arXiv classic, no open-access PDF (see DOI).
- Code review path: Not applicable; paper reference.
- BibTeX key: `carter1968kerr`
- Stable locator: https://doi.org/10.1103/PhysRev.174.1559
- Search date: 2026-06-29
- Search terms: Carter 1968 global structure Kerr family Carter constant
- Why added: Primary source for separability of Kerr geodesics and the Carter
  constant `Q` that `docs/validation_targets.md` requires tracking.
- Short summary: Establishes the fourth integral of motion (Carter constant) and
  global structure of the Kerr family.
- Relevant equations / assumptions / methods: Hamilton-Jacobi separation, Carter
  constant `Q`, conserved `E` and `L_z`.
- Project use: Provenance for conserved-quantity validation in Phase 1.
- Limitations / open questions: None for citation; analytic foundation only.

### Bardeen Press Teukolsky 1972 - ISCO And LNRF

- Source path: `references/source_notes/2026-06-29-foundational-analytic-references.md`
- PDF path: Not stored; pre-arXiv classic, no open-access PDF (see DOI).
- Code review path: Not applicable; paper reference.
- BibTeX key: `bardeen1972rotatingBlackHoles`
- Stable locator: https://doi.org/10.1086/151796
- Search date: 2026-06-29
- Search terms: Bardeen Press Teukolsky 1972 rotating black holes ISCO LNRF
- Why added: Primary source for the innermost stable circular orbit `r_ISCO(a)`
  used as the default disk inner edge.
- Short summary: Derives locally nonrotating frames, energy extraction, and
  circular-orbit / ISCO relations for Kerr.
- Relevant equations / assumptions / methods: `r_ISCO(a)`, locally nonrotating
  frame (LNRF), marginally stable orbit conditions.
- Project use: Provenance for `r_in = r_ISCO(a)` in `docs/equations.md`.
- Limitations / open questions: None for citation.

### Bardeen 1973 - Kerr Null Geodesics And Screen Coordinates

- Source path: `references/source_notes/2026-06-29-foundational-analytic-references.md`
- PDF path: Not stored; Les Houches lecture notes, no open-access PDF.
- Code review path: Not applicable; book chapter reference.
- BibTeX key: `bardeen1973kerrGeodesics`
- Stable locator: Black Holes (Les Houches 1972), Gordon and Breach, pp. 215-239
- Search date: 2026-06-29
- Search terms: Bardeen 1973 timelike null geodesics Kerr metric impact parameters
- Why added: Primary source for the observer-screen impact parameters and the
  `(alpha, beta)` to initial-momentum mapping.
- Short summary: Classic derivation of timelike and null geodesics in Kerr,
  including the apparent-position impact parameters seen by a distant observer.
- Relevant equations / assumptions / methods: Kerr null geodesics, screen impact
  parameters, photon-region structure.
- Project use: Provenance for screen-camera mapping in `docs/equations.md`.
- Limitations / open questions: Book chapter; cite by page range.

### Cunningham 1975 - Kerr Disk Redshift Transfer

- Source path: `references/source_notes/2026-06-29-foundational-analytic-references.md`
- PDF path: Not stored; pre-arXiv classic, no open-access PDF (see DOI).
- Code review path: Not applicable; paper reference.
- BibTeX key: `cunningham1975kerrDiskSpectrum`
- Stable locator: https://doi.org/10.1086/154033
- Search date: 2026-06-29
- Search terms: Cunningham 1975 redshift focusing accretion disk Kerr black hole
- Why added: Primary source for the disk redshift factor `g` and the transfer
  function used in `docs/equations.md`.
- Short summary: Computes redshift and focusing effects on the spectrum of a Kerr
  accretion disk, defining the relativistic transfer function.
- Relevant equations / assumptions / methods: Redshift factor `g`, transfer
  function, flux conservation `I_nu / nu^3` invariance.
- Project use: Provenance for the redshift and intensity transform in Phase 4.
- Limitations / open questions: None for citation.

### Luminet 1979 - First Thin-Disk Black-Hole Image

- Source path: `references/source_notes/2026-06-29-foundational-analytic-references.md`
- PDF path: Not stored; pre-arXiv classic, no open-access PDF (see ADS bibcode).
- Code review path: Not applicable; paper reference.
- BibTeX key: `luminet1979blackHoleImage`
- Stable locator: https://ui.adsabs.harvard.edu/abs/1979A&A....75..228L/abstract
- Search date: 2026-06-29
- Search terms: Luminet 1979 image spherical black hole thin accretion disk
- Why added: Primary source for direct and secondary disk images and the thin-disk
  appearance the renderer targets.
- Short summary: First simulated optical appearance of a Schwarzschild thin
  accretion disk, including direct and secondary (higher-order) images.
- Relevant equations / assumptions / methods: Isoradial curves, direct/secondary
  image construction, flux asymmetry from Doppler beaming.
- Project use: Provenance and visual sanity check for direct/secondary images.
- Limitations / open questions: Schwarzschild only; no open-access PDF.

### Gralla Holz Wald 2019 - Shadows, Photon Rings, Lensing Rings

- Source path: `references/source_notes/2026-06-29-foundational-analytic-references.md`
- PDF path: `references/pdfs/2019-gralla-holz-wald-shadows-photon-lensing-rings.pdf`
- Code review path: Not applicable; paper reference.
- BibTeX key: `gralla2019shadowsPhotonRings`
- Stable locator: https://arxiv.org/abs/1906.00873
- Search date: 2026-06-29
- Search terms: Gralla Holz Wald black hole shadows photon rings lensing rings
- Why added: Primary source for the shadow / critical curve / lensing ring /
  photon ring vocabulary used in `docs/physical_scope.md`.
- Short summary: Distinguishes the shadow, lensing ring, and photon ring as
  separate observable features and their dependence on emission profile.
- Relevant equations / assumptions / methods: Photon-orbit analysis, image-order
  decomposition, emission-dependent ring brightness.
- Project use: Provenance for the photon-ring/lensing-ring definitions and a
  qualitative validation target for higher-order images.
- Limitations / open questions: Schwarzschild-focused exposition; Kerr extension
  via the Gralla-Lupsasca papers.

### Gralla Lupsasca 2020 - Lensing By Kerr Black Holes

- Source path: `references/source_notes/2026-06-29-foundational-analytic-references.md`
- PDF path: `references/pdfs/2020-gralla-lupsasca-lensing-by-kerr.pdf`
- Code review path: Not applicable; paper reference.
- BibTeX key: `gralla2020lensingKerr`
- Stable locator: https://arxiv.org/abs/1910.12873
- Search date: 2026-06-29
- Search terms: Gralla Lupsasca lensing by Kerr black holes photon ring
- Why added: Analytic theory of Kerr lensing and the demagnification / rotation /
  time-delay parameters of successive photon-ring images; theory AART builds on.
- Short summary: Derives the exponential demagnification, rotation, and time
  delay of higher-order images near the Kerr photon ring.
- Relevant equations / assumptions / methods: Lyapunov exponents of nearly bound
  photon orbits, image-order scaling parameters.
- Project use: Provenance for adaptive critical-curve sampling and higher-order
  image validation.
- Limitations / open questions: Analytic limit; numerical comparison deferred to
  Phase 2/4.

### Gralla Lupsasca 2020 - Null Geodesics Of The Kerr Exterior

- Source path: `references/source_notes/2026-06-29-foundational-analytic-references.md`
- PDF path: `references/pdfs/2020-gralla-lupsasca-null-geodesics-kerr.pdf`
- Code review path: Not applicable; paper reference.
- BibTeX key: `gralla2020nullGeodesicsKerr`
- Stable locator: https://arxiv.org/abs/1910.12881
- Search date: 2026-06-29
- Search terms: Gralla Lupsasca null geodesics Kerr exterior analytic
- Why added: Self-contained modern analytic treatment of Kerr null geodesics in
  terms of elliptic integrals; reference for the Phase 1 solver and cross-checks.
- Short summary: Provides closed-form null-geodesic solutions for the Kerr
  exterior using Boyer-Lindquist coordinates and conserved quantities.
- Relevant equations / assumptions / methods: Elliptic-integral geodesic
  solutions, conserved `E`, `L_z`, Carter `Q`, radial/angular potentials.
- Project use: Analytic cross-check target for the numerical Kerr integrator.
- Limitations / open questions: Boyer-Lindquist exterior; horizon-penetrating
  checks still use Kerr-Schild as in `docs/equations.md`.
