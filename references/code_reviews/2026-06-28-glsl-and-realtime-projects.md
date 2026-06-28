# GLSL And Real-Time Black-Hole Project Review

Date: 2026-06-28.

Purpose: record lessons from real-time shader and WebGL/Vulkan projects without
confusing them with physics-validation references. These sources can guide
interactive renderer structure, cache layout, and UI controls, but validation
must still come from equations, invariant checks, and peer-reviewed benchmarks.

## Review Boundary

- Repositories were shallow-cloned into a temporary directory only for
  inspection.
- The Zhihu article was fetched into a temporary directory using `opencli`
  because direct page scraping returned HTTP 403. The article text was not
  stored in this repository.
- No third-party source code was copied into this repository.
- License notes below are for planning hygiene, not legal advice.

## Zhihu Kerr-Newman GLSL Article

- Stable locator: https://zhuanlan.zhihu.com/p/2003513260645830673
- Access method: `opencli zhihu download`, 2026-06-28.
- Article date observed by `opencli`: edited 2026-06-17.
- BibTeX key: `zhihu2026kerrNewmanRealtime`
- License / redistribution: not treated as redistributable; no article text or
  code snippets are stored here.
- Relevant content summary: the article describes a real-time Kerr-Newman black
  hole renderer using ingoing Kerr-Schild coordinates, Hamiltonian-style photon
  equations, local observer tetrads, redshift/Doppler/beaming terms, disk/jet
  visual layers, and aggressive shader optimizations.
- Useful engineering lessons: keep observer mode, charge/spin, disk, jet,
  redshift, culling, and quality parameters explicit in the renderer UI; expose
  intermediate buffers instead of hiding all physics inside final RGB.
- Physics boundary: Kerr-Newman charge and extended region/white-hole style
  visualization are not first-year validated goals. They can be tracked as
  exploratory visualization features only after Kerr validation exists.

## NPGS

- Repository: https://github.com/baopinshui/NPGS
- Reviewed commit: `40acedaebf31743ef44dad428117d39b8f22f324`
- BibTeX key: `baopinshui2026npgscode`
- License observed: GPL-3.0.
- Language / dependencies: C++ Visual Studio project, Vulkan/OpenGL-adjacent
  shader assets, ImGui, GLFW, GLM, Boost.Multiprecision, stb, spdlog,
  nlohmann-json, and related vcpkg dependencies.
- Relevant shader files: `NPGS/Sources/Engine/Shaders/BlackHole.comp.glsl`,
  `BlackHole.frag.glsl`, `BlackHole_common.glsl`,
  `BlackHole_composite.frag.glsl`, and `BlackHole_prepass.frag.glsl`.
- Relevant UI controls observed: debug/prepass switches, white-hole and
  universe mode controls, observer mode, polarization mode, quality, mass,
  spin, charge, accretion rate, disk radii/thickness, redshift color/intensity
  exponents, photon-ring boost, jet controls, and shadow culling.
- Useful engineering lessons: a real-time renderer benefits from a structured
  uniform block for physics-facing parameters, separate prepass/composite
  stages, and explicit debug modes. These map well to GR-BH-XR audit buffers.
- Physics boundary: this is a GPL real-time project and not a peer-reviewed
  benchmark. It should not be copied, vendored, or used to justify physics
  claims without independent equation checks.

## Bruneton Black-Hole Shader

- Paper: https://arxiv.org/abs/2010.08735
- Repository: https://github.com/ebruneton/black_hole_shader
- Reviewed commit: `e72b3f293409893a6fa25528b29572c96fc57f57`
- BibTeX keys: `bruneton2020realtimeBlackHoleShader`,
  `bruneton2026blackHoleShaderCode`
- License observed: BSD-style license.
- Scope: real-time high-quality rendering of a non-rotating black hole with
  accretion disk and background stars.
- Relevant structure: GLSL definitions/functions/model files, WebGL2 demo
  panels, and preprocessing/test code for deflection and disk-intersection
  texture tables.
- Useful engineering lessons: precomputed ray-deflection and inverse-radius
  textures are a strong pattern for headset-friendly rendering once a CPU
  reference map exists. The project also demonstrates a good split between
  shader runtime, preprocessing, and tests.
- Physics boundary: Schwarzschild-only cache ideas are useful, but they do not
  solve Kerr transfer maps or polarized GRRT.

## Oseiskar WebGL Black Hole

- Repository: https://github.com/oseiskar/black-hole
- Reviewed commit: `74bdf38cb822605a5d3411f1561c965fe5fd5c0f`
- BibTeX key: `oseiskar2026blackHoleCode`
- License observed: MIT for project files, with separate third-party asset and
  library notices.
- Scope: browser-based Schwarzschild black-hole simulation using GLSL ODE
  integration with WebGL/three.js.
- Useful engineering lessons: GUI toggles for relativistic effects and quality
  modes are valuable for demonstrations and debugging. Its documentation also
  makes a useful habit of listing known artifacts explicitly.
- Physics boundary: the project itself records visual/numerical artifacts and
  arbitrary spectrum assumptions. Use it as a real-time interaction reference,
  not as a benchmark for GR-BH-XR numerical claims.

## GR-BH-XR Design Implications

- Keep the Phase 1 CPU solver as the authority for Kerr ray events,
  Hamiltonian residuals, conserved quantities, and disk crossings.
- When a GPU shader is added, mirror shader parameters into documented physical
  quantities and record their units/ranges.
- Separate benchmarkable buffers from visual styling: capture mask, image
  order, redshift, time delay, and disk-hit buffers should not be fused into
  final color too early.
- Treat real-time shader papers/projects as acceleration and UX references.
  Treat RAPTOR/AART/grtrans/ipole/HARM-family papers as validation references.
- Do not copy GPL shader code from NPGS into this repository. If comparison is
  needed later, use clean benchmark outputs and documented parameter cases.
