# Lens Map Persistence Validation

Phase: 1 CPU Kerr reference solver.

Purpose: verify that the reference tracer can persist physics-auditable screen
buffers instead of treating an RGB image as the only renderer product.

## Commands

From the source tree:

```text
$env:PYTHONPATH='src'
python -m gr_bh_xr.generate_lens_map --spin 0 --inclination-deg 90 --grid 129 --alpha-max 8 --beta-max 8 --out outputs/phase1/lensmap_schwarzschild.h5
python -m gr_bh_xr.generate_lens_map --spin 0.5 --inclination-deg 60 --grid 129 --alpha-max 8 --beta-max 8 --out outputs/phase1/lensmap_kerr_a0.5_i60.h5
python -m gr_bh_xr.plot_lens_map --input outputs/phase1/lensmap_schwarzschild.h5 --out outputs/phase1/shadow_validation.pdf
```

Generated HDF5 and PDF outputs are intentionally written under
`outputs/phase1/`, which is ignored by Git. The tracked schema is documented in
`data/lens_maps/README.md`.

## Acceptance

- The HDF5 file contains screen axes, event codes, per-pixel minimum radius,
  Hamiltonian residuals, conserved-quantity drift diagnostics, and disk-crossing
  counts.
- The event-code grid contains both capture and escape samples for the default
  Schwarzschild `alpha_max = beta_max = 8M` run.
- Near-critical samples may appear as `invalid` when the fixed `max_lambda`
  budget ends before a capture or escape event; the count is part of the audit
  output and should decrease under later adaptive or longer integrations.
- The plotting command renders a readable PDF with capture mask and Hamiltonian
  residual panels.
- These buffers remain Phase 1 diagnostic products only. Disk transfer,
  redshift, time delay, GRRT intensity, and XR rendering are later stages.
