# Source Notes: Physics-Auditable Renderer Baseline

Search/use date: 2026-06-28.

These notes index the initial sources used to shape the GR-BH-XR roadmap. They
are not a substitute for reading the papers or official documentation before
making detailed claims.

PDF originals, when stored, belong in `references/pdfs/` and must be linked from
`references/references.md`. Restricted or oversized PDFs belong in
`references/pdfs/local_only/` and should be marked as local-only in the index.

## RAPTOR I

- Stable locator: https://arxiv.org/abs/1801.10452
- Why added: Baseline reference for time-dependent general relativistic
  radiative transfer.
- Summary: RAPTOR is relevant as a benchmark family for ray integration plus
  radiative-transfer image, movie, and spectrum generation in strong gravity.
- Project use: Compare simplified GRRT outputs and terminology.
- Limitation: Benchmark setups must be selected explicitly once local GRRT code
  exists.

## Odyssey

- Stable locator: https://github.com/hungyipu/Odyssey
- Why added: Public GPU-based Kerr GRRT implementation relevant to real-time or
  near-real-time engineering choices.
- Summary: Odyssey is a CUDA/C++-oriented GRRT codebase for Kerr ray tracing and
  radiative transfer.
- Project use: Reference GPU layout, transfer formulation, and possible
  benchmark cases.
- Limitation: Its assumptions and supported models must be checked before direct
  numerical comparison.

## BHAC

- Stable locator: https://arxiv.org/abs/1611.09720
- Why added: Reference for black-hole accretion GRMHD simulations and later
  snapshot-based workflows.
- Summary: BHAC is relevant for multidimensional GRMHD simulation data that can
  be post-processed by GRRT.
- Project use: Later GRMHD snapshot ingestion and field naming assumptions.
- Limitation: Running GRMHD is out of first-version scope.

## Quest Device Optimization

- Stable locator: https://developers.meta.com/horizon/resources/device-optimization-comparison/
- Why added: Establishes Quest performance constraints and why high-precision
  GRRT should not start as headset-native computation.
- Summary: Use for target refresh-rate and frame-budget planning.
- Project use: PCVR-first architecture and headset validation gates.
- Limitation: Device guidance may change; re-check before release milestones.

## Meta Passthrough Over Link

- Stable locator: https://developers.meta.com/horizon/documentation/native/android/mobile-passthrough-over-link/
- Why added: Relevant to rapid PC-hosted passthrough iteration.
- Summary: Supports a PCVR/MR development route where the host PC remains
  central to heavy computation.
- Project use: Quest Link/Air Link development plan.
- Limitation: Developer feature behavior may change; verify on local hardware.

## Unity OpenXR Meta Camera / Passthrough

- Stable locator: https://docs.unity3d.com/Packages/com.unity.xr.meta-openxr%402.2/manual/features/camera.html
- Why added: Documents passthrough camera/pixel-access constraints in the Unity
  OpenXR Meta route.
- Summary: Important for separating MR overlay from true passthrough pixel
  lensing.
- Project use: MR-1/MR-2/MR-3 staging.
- Limitation: Package behavior is version-dependent; re-check against the exact
  Unity package version.

## Meta Depth API

- Stable locator: https://developers.meta.com/horizon/documentation/unity/unity-depthapi-overview/
- Why added: Supports MR depth occlusion for virtual black-hole layers.
- Summary: Real-time depth can be used to make physical objects occlude virtual
  content.
- Project use: MR-1 depth-aware compositing.
- Limitation: Runtime support and quality must be validated on device.

## AART

- Stable locator: https://arxiv.org/abs/2211.07469
- Why added: Reference for adaptive analytical ray tracing of Kerr photon rings.
- Summary: Motivates nonuniform/adaptive sampling near the critical curve and
  high-order image regions.
- Project use: Critical-curve sampling strategy and photon-ring validation.
- Limitation: Need to identify comparable local output quantities before using
  it as a benchmark.

## Davelaar VR Black-Hole Work

- Stable locator: https://arxiv.org/abs/1811.08369
- Why added: Prior example of GRMHD plus GRRT data used for black-hole VR.
- Summary: Shows a viable offline/post-processed route from GRMHD simulations to
  immersive black-hole visualization.
- Project use: Later GRMHD snapshot plus Quest playback/query architecture.
- Limitation: It is a precedent for offline VR, not proof that Quest-native
  real-time GRRT is practical.
