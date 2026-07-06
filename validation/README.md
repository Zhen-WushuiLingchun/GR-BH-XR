# Validation Entry Points

This directory will hold reproducible validation notes and scripts as the
renderer implementation appears.

## Phase 0 Gate

Phase 0 is documentation and source-baseline only. It is complete when:

- open PDFs are stored under `references/pdfs/`;
- citations are indexed in `references/references.bib`;
- every kept reference is navigable through `references/references.md`;
- reference code reviews are stored under `references/code_reviews/`;
- no third-party source code has been vendored into this repository.

## Phase 1 CPU Kerr Solver Gate

The first implementation validation target will be the CPU Kerr/Schwarzschild
reference solver. It must record:

- null Hamiltonian residual per sampled ray;
- drift of `E = -p_t`;
- drift of `L_z = p_phi`;
- Carter constant drift where applicable;
- event class: horizon capture, sky escape, disk crossing, or invalid state;
- Schwarzschild shadow critical impact parameter `b_c = 3 sqrt(3) M`.

Current analytic-derivative tolerance target:

```text
outer grouped max |H| < 1e-8 for default Kerr critical-curve runs
```

Near-capture Boyer-Lindquist residuals and polar-axis coordinate singularities
remain separate audit categories rather than global pass/fail gates.

Tracked Phase 1 validation entry points:

- `schwarzschild_shadow/README.md`: Schwarzschild critical impact parameter
  `b_c = 3 sqrt(3) M`.
- `kerr_critical_curve/README.md`: Kerr analytic critical-curve comparison for
  finite spin and inclination.
- `lens_map/README.md`: HDF5 persistence of per-pixel diagnostic buffers and
  basic validation figures.
- `ray_examples/README.md`: illustrative capture, near-critical, and escape ray
  paths for visual sanity checking.
