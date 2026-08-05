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
- `photon_ring_zoom/README.md`: Task 6 pre-transfer lensing-band zoom using
  azimuthal winding and image-order proxy buffers.
- `thin_disk_transfer/README.md`: Task 6 CPU equatorial thin-disk crossing and
  redshift transfer buffers.
- `roam_keyframes/README.md`: Task 7 finite-observer quasi-static roam
  keyframe grid, escape-radius floor, shadow solid-angle growth gate, and the
  equatorial mirror-symmetry invariant.
- `descent_keyframes/README.md`: Task 8 rain-frame horizon-crossing descent
  keyframes, the Hamiltonian-residual ray-validity criterion, and the
  two-radius chart-direction and observer-factor gates.

## Phase 3 Quest PCVR Gate

Tracked Task 5 validation entry points:

- `quest_pcvr/README.md`: Unity/OpenXR static texture bridge, coordinate
  convention checks, and headset validation protocol placeholders.
