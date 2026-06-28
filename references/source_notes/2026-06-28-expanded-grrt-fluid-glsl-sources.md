# Source Notes: Expanded GRRT, Relativistic-Fluid, And GLSL References

Search/use date: 2026-06-28.

Purpose: expand Phase 0 beyond the initial AART/RAPTOR/Odyssey/BHAC baseline
with additional GRRT, polarized-transfer, GRMHD/fluid, and real-time shader
sources. These notes record source provenance and project-use boundaries; they
do not replace reading the papers before implementing equations.

## Search Terms

- general relativistic radiative transfer black holes Dexter grtrans
- RAPTOR II polarized radiative transfer curved spacetime
- ipole polarized relativistic radiative transport
- general relativistic radiative transfer Younsi Wu Fuerst
- HARM general relativistic magnetohydrodynamics
- primitive variable solvers conservative GRMHD
- Event Horizon GRMHD code comparison project
- iharm3D vectorized GRMHD
- Athena++ radiation magnetohydrodynamics general relativity
- KORAL M1 radiation general relativistic conservative fluid dynamics
- real-time black-hole shader GLSL WebGL
- Kerr-Newman real-time GLSL renderer

## Open arXiv PDFs Added

| Key | PDF path | Stable locator | Project use |
| --- | --- | --- | --- |
| `bronzwaer2020raptorii` | `references/pdfs/2020-raptor-ii-polarized-radiative-transfer.pdf` | https://arxiv.org/abs/2007.03045 | Polarized-transfer and tetrad/sign-convention reference after scalar GRRT. |
| `dexter2016grtrans` | `references/pdfs/2016-grtrans-public-polarized-grrt.pdf` | https://arxiv.org/abs/1602.03184 | Public polarized-GRRT paper behind grtrans; later benchmark source. |
| `moscibrodzka2018ipole` | `references/pdfs/2017-ipole-polarized-radiative-transfer.pdf` | https://arxiv.org/abs/1712.03057 | Relativistic polarized transport reference for later Stokes work. |
| `younsi2012grrt` | `references/pdfs/2012-grrt-formulation-younsi-wu-fuerst.pdf` | https://arxiv.org/abs/1207.4234 | Formulation-level GRRT reference for invariant transfer and emission models. |
| `gammie2003harm` | `references/pdfs/2003-harm-grmhd-scheme.pdf` | https://arxiv.org/abs/astro-ph/0301509 | GRMHD conservation-law baseline and HARM terminology. |
| `noble2006primitive` | `references/pdfs/2005-primitive-variable-solvers-grmhd.pdf` | https://arxiv.org/abs/astro-ph/0512420 | Primitive recovery reference for future snapshot interpretation. |
| `porth2019ehtgrmhdcomparison` | `references/pdfs/2019-eht-grmhd-code-comparison.pdf` | https://arxiv.org/abs/1904.04923 | Cross-code GRMHD comparison and benchmark-culture reference. |
| `prather2021iharm3d` | `references/pdfs/2021-iharm3d-vectorized-grmhd.pdf` | https://arxiv.org/abs/2110.10191 | Modern HARM-family implementation reference for later data provenance. |
| `white2023athenaRadiationGRMHD` | `references/pdfs/2023-athena-radiation-grmhd.pdf` | https://arxiv.org/abs/2302.04283 | Radiation-GRMHD design reference, not a first-year dependency. |
| `sadowski2013koralM1` | `references/pdfs/2012-koral-m1-radiation-grhd.pdf` | https://arxiv.org/abs/1212.5050 | M1 radiation closure reference for long-range radiative-fluid context. |
| `bruneton2020realtimeBlackHoleShader` | `references/pdfs/2020-bruneton-realtime-black-hole-shader.pdf` | https://arxiv.org/abs/2010.08735 | Validated real-time Schwarzschild shader paper; useful for cache design. |
| `li2026kerrNewmanPolarizedTransfer` | `references/pdfs/2026-kerr-newman-polarized-radiative-transfer.pdf` | https://arxiv.org/abs/2601.14785 | Kerr-Newman/polarization watchlist; charge is outside first-year scope. |

## Web And Code Sources Reviewed

| Key | Stable locator | Review path | Project use |
| --- | --- | --- | --- |
| `zhihu2026kerrNewmanRealtime` | https://zhuanlan.zhihu.com/p/2003513260645830673 | `references/code_reviews/2026-06-28-glsl-and-realtime-projects.md` | Gray-literature GLSL/Kerr-Newman engineering ideas; not a validation source. |
| `baopinshui2026npgscode` | https://github.com/baopinshui/NPGS | `references/code_reviews/2026-06-28-glsl-and-realtime-projects.md` | Detailed real-time GLSL/Vulkan black-hole renderer review; no code copied. |
| `bruneton2026blackHoleShaderCode` | https://github.com/ebruneton/black_hole_shader | `references/code_reviews/2026-06-28-glsl-and-realtime-projects.md` | Precomputed texture and unit-test strategy for real-time rendering. |
| `oseiskar2026blackHoleCode` | https://github.com/oseiskar/black-hole | `references/code_reviews/2026-06-28-glsl-and-realtime-projects.md` | WebGL ODE-in-shader example with explicit artifact caveats. |

## Boundary Notes

- GRRT and GRMHD papers can define equations, conventions, validation targets,
  and benchmark culture.
- Shader projects can inform cache layout, shader interfaces, UI controls,
  debugging toggles, and performance tradeoffs.
- Kerr-Newman charge, visual white-hole/other-universe modes, and unvalidated
  GLSL approximations remain outside the first-year validated-physics scope.
- Zhihu content was accessed through a temporary `opencli zhihu download`
  because direct web retrieval returned HTTP 403. The downloaded article copy
  was not added to the repository.
- Third-party repositories were shallow-cloned only under a temporary directory.
  No source code from those projects was vendored into this repository.
