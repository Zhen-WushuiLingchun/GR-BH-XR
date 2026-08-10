# BBH Dynamic-Spacetime And Ray-Tracing Foundations

Date: 2026-08-10

## Purpose

This note establishes the literature baseline for a time-dependent binary
black-hole (BBH) metric provider, four-dimensional null-geodesic integration,
numerical-relativity snapshot ingestion, and later XR/MR rendering. It does not
claim that a BBH solver exists in GR-BH-XR or in the reviewed public NPGS refs.

## Search Protocol

- Sources searched: arXiv, journal metadata linked by arXiv, the Einstein
  Toolkit documentation, CarpetX documentation, and the SXS public data
  documentation.
- Search date: 2026-08-10.
- Search terms:
  - `binary black hole numerical relativity ray tracing`;
  - `3+1 null geodesic numerical spacetime`;
  - `boosted superposed Kerr-Schild BBH metric`;
  - `BSSN moving puncture binary black holes`;
  - `apparent horizon dynamical black hole event horizon nonlocal`;
  - `plane gravitational wave Hamiltonian light propagation`;
  - `Einstein Toolkit CarpetX BSSN Z4c TwoPuncturesX`;
  - `SXS metric data horizon waveform documentation`.
- Inclusion rule: primary research papers or official project/data
  documentation with equations, numerical methods, validation results, or a
  directly usable data contract.
- Exclusion rule: showcase videos, screenshots, uncited shader behavior, and
  waveform-only assets presented as if they contained the near-zone metric.

## Evidence Layers

### Layer A - Null geodesics in time-dependent 3+1 spacetimes

1. `vincent2012geodesic3p1` derives null and timelike geodesic equations in
   3+1 form and includes photon-energy/redshift evolution. It is the primary
   equation reference for an ADM snapshot provider.
2. `vincent2011gyoto` demonstrates a modular ray tracer that consumes analytic
   Kerr metrics or numerical metrics in the 3+1 formalism. It is an
   architecture precedent, not a numerical oracle for this project.
3. `bohn2015bbhAppearance` traces light through fully numerical BBH
   spacetimes. Its normalized-momentum formulation, capture handling, redshift,
   and nested eyebrow/self-similar shadow structure define the principal BBH
   imaging benchmark family.

Project consequence: the first reference implementation must evolve the full
time-dependent Hamilton system. It may also implement the 3+1 normalized
momentum formulation as an independent cross-check. In a generic dynamic
metric, `p_t`, `L_z`, and the Kerr Carter constant are not assumed conserved.

### Layer B - Fast approximate BBH metrics

1. `combi2021superposedMetric` superposes boosted spinning black-hole metrics
   along 3.5PN inspiral trajectories and evaluates the resulting vacuum
   approximation and GRMHD use.
2. `combi2026bbhMetricApproximation` extends the approach from inspiral through
   merger using boosted Kerr-Schild terms, fourth-order PN trajectories, and a
   transition to a fitted remnant. The 2026 arXiv revision reports comparison
   with full numerical relativity and explicitly remains an approximate metric.

Project consequence: this is the preferred first interactive BBH metric source
because it is fast and differentiable. It must be labeled
`physics_approximation`, persist its constraint residuals, and must never be
called a real-time solution of the Einstein equations.

### Layer C - Full numerical-relativity truth path

1. `baumgarte1998bssn` establishes the conformal-traceless formulation that
   became the BSSN family.
2. `campanelli2006movingPuncture` demonstrates stable non-excision BBH
   evolution with the BSSN moving-puncture method.
3. `pretorius2005bbhEvolution` demonstrates BBH merger evolution with a
   generalized-harmonic formulation.
4. `einsteinToolkit2026hypatia` documents GPU-enabled BSSNOK/Z4c components,
   CarpetX support, exact test data, and TwoPuncturesX in the 2026_05 release.
5. `carpetx2026manual` documents output through openPMD, HDF5/ADIOS2-backed
   formats, and interpolation infrastructure.
6. `sxs2026waveformDocs` documents public asymptotic waveforms, apparent
   horizons, and initial-data fields. The public documentation does not promise
   a complete evolved four-dimensional near-zone metric for each catalog run.

Project consequence: the high-fidelity path is an offline BSSN/Z4c or
generalized-harmonic evolution that exports time-indexed ADM fields. Public
SXS waveform modes alone are not accepted as a strong-field ray-tracing metric.

### Layer D - Horizons and dynamic claim boundaries

1. `ashtekar2004dynamicalHorizons` provides the quasi-local isolated/dynamical
   horizon framework used in numerical relativity.

Project consequence: runtime capture uses documented apparent-horizon or
worldtube data. An event horizon is global and future-dependent; it may be
reconstructed offline but cannot be advertised as a locally known runtime
surface.

### Layer E - Analytic regression metrics

1. `angelil2015gwOptics` derives plane-gravitational-wave effects using both
   Hamiltonian geometric optics and wave optics.
2. `cunha2018exactBinaryShadows` studies exact stationary double-black-hole
   solutions and separates quasi-static binary-shadow morphology from a true
   dynamical merger spacetime.

Project consequence: Minkowski, stationary Kerr, and a linear plane GW are the
first analytic time-dependent gates. Exact stationary double-black-hole
solutions can test image morphology but cannot validate orbital inspiral or
merger dynamics.

## Required Implementation Distinctions

The project must keep these claims separate in metadata and UI:

| Label | Meaning | Allowed source |
| --- | --- | --- |
| `validated_stationary_exact` | Exact stationary metric with independent ray gates | Kerr/Kerr-Newman, selected exact stationary binary metrics |
| `validated_dynamic_analytic` | Exact or perturbative analytic dynamic test metric | Minkowski, linear plane GW |
| `physics_approximation` | Fast BBH metric not satisfying the full Einstein system exactly | Combi-Ressler superposed metric |
| `nr_snapshot_truth` | Interpolated output of a documented NR evolution | Einstein Toolkit/CarpetX or another versioned NR producer |
| `visual_enhancement` | Deliberate visibility scaling with no physical-amplitude claim | amplified GW displacement in XR |

## Open Questions For Task 0 Completion

- The reviewed arXiv PDFs and extracted text remain under ignored
  `outputs/bbh_literature/`; redistribution status was not assumed, so none was
  committed.
- The Combi-Ressler source archive is now identified by Zenodo DOI
  `10.5281/zenodo.10841021`, version 1, and MD5
  `ecc4d1268342520f29e4537d5f3ab183`. Its structure and mixed file-level
  licensing are recorded in
  `references/code_reviews/2026-08-10-combi-ressler-bbh-metric.md`. The archive
  is evidence only and is not vendored.
- Choose the ADM snapshot interpolation basis and quantify whether metric
  derivatives are stored or reconstructed.
- The covariant four-dimensional Hamilton system is the primary dynamic
  oracle. Vincent's Eulerian-energy equations and Bohn's normalized covariant
  momentum are the independent 3+1 cross-checks; the frozen formulas and sign
  conventions are in `docs/equations.md`.
- Pre-register the constraint norms and convergence orders for the first
  approximate and NR metric providers.
