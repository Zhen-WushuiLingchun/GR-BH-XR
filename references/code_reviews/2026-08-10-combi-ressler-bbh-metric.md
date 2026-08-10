# Combi-Ressler BBH Metric Source Review

Date reviewed: 2026-08-10

## Source identity

- Paper: `combi2026bbhMetricApproximation`, arXiv `2403.13308` v3.
- Software record: Zenodo `10.5281/zenodo.10841021`, version 1.
- Archive: `public_repo.zip`, 446718 bytes.
- MD5 published by Zenodo and independently reproduced:
  `ecc4d1268342520f29e4537d5f3ab183`.
- Local ignored review copy:
  `outputs/bbh_literature/combi_ressler_10841021_v1/`.
- Record license metadata: CC BY 4.0.

The reviewed record is a dated archive rather than a Git repository, so there
is no source commit SHA to cite. The Zenodo DOI, version, file name, size, and
checksum together identify the reviewed source.

## Relevant structure

- `SuperposedBBH.c`: generated covariant-metric evaluator.
- `MetricBuilder/SKS_NoAcc_3D_spinarb.nb`: Mathematica construction notebook
  for superposed boosted Kerr-Schild terms.
- `MetricBuilder/CoordiantesToC.nb` and `EasyC.wl`: code-generation support.
- `CBwaves/`: external PN trajectory/waveform package and driver scripts.

The generated evaluator constructs a flat background plus two transformed
single-hole Kerr-Schild perturbations. In schematic form,

```text
g_mu_nu = eta_mu_nu
          + J1^alpha_mu J1^beta_nu h1_alpha_beta
          + J2^alpha_mu J2^beta_nu h2_alpha_beta.
```

The hole positions, velocities, spins, and masses are supplied through a
trajectory array. The generated C depends on external project macros and tensor
headers, so the archive is not a standalone library. It returns the covariant
metric; it does not expose inverse-metric derivatives, Hamiltonian/momentum
constraints, horizon worldtubes, or the complete v3 merger-to-remnant provider
contract needed by GR-BH-XR.

## License review and reuse decision

The archive is not license-homogeneous despite the Zenodo record-level CC BY
4.0 metadata:

- `CBwaves/cbwaves.spec` declares GPL;
- `MetricBuilder/Optimize.m` carries a separate historical permission notice
  with attribution and product-use conditions;
- selected CBwaves headers contain their own permissive notices.

GR-BH-XR therefore does **not** vendor this archive or copy its generated code
as a unit. The local archive is evidence for equations, data flow, and source
provenance. The project implementation will be written from the reviewed paper
equations, will cite this software record, and will be independently checked by
constraint residuals and analytic limits. Any later selective reuse requires a
file-level license decision and preserved notices.

## Physical and numerical observations

1. The superposition is a fast approximate metric, not an exact vacuum
   solution. It must retain the `physics_approximation` evidence label.
2. Time dependence enters through moving/boosted holes and the supplied
   trajectory. A ray tracer must integrate `p_t`; stationary Kerr constants do
   not survive generically.
3. The source's covariant-only API is insufficient for Hamilton tracing. The
   project provider must independently compute `g^mu_nu` and all four
   derivatives `partial_mu g^alpha_beta`.
4. Horizon/excision radii in a generated metric function are not a substitute
   for apparent-horizon data or an explicitly labelled worldtube.
5. The v3 paper's inspiral-to-remnant interpolation must be reviewed and
   implemented explicitly; the 2024 Zenodo archive alone is not evidence that
   the full revised model is present.

## Required gates before acceptance

- single-hole and infinite-separation limits;
- equal-mass symmetry and hole-label exchange;
- ADM reconstruction and inverse consistency;
- finite-difference derivative oracle;
- Hamiltonian and momentum-constraint residual maps with convergence;
- full dynamic null-Hamiltonian ray regression;
- no claim of exact Einstein evolution.
