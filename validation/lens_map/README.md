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
- Escaped rays record momentum-derived sky direction buffers `escape_theta`,
  `escape_phi`, and `escape_dir_{x,y,z}` for later background
  lensing/cubemap sampling. The direction is computed from `u^mu = g^{mu nu}
  p_nu` at the escape sphere, not from the finite-radius escape position.
- The HDF5 file records `failure_code`, separating trace exceptions, solver
  failures, rays that reached `max_lambda` without a classified event, and
  Boyer-Lindquist polar-axis coordinate singularities. The shared codebook also
  reserves `polar_step_overshoot = 5` for GPU fixed-step near-polar artifacts;
  Phase 1 CPU lens maps are not expected to emit that code.
- The event-code grid contains both capture and escape samples for the default
  Schwarzschild `alpha_max = beta_max = 8M` run.
- On odd grids, invalid pixels in the central `alpha = 0` column are expected
  when `L_z = 0` rays reach the Boyer-Lindquist polar axis. They are recorded as
  `axis_coordinate_singularity`; this is a coordinate limitation, not a
  near-critical `max_lambda` budget failure.
- The plotting command renders a readable PDF with event-class and Hamiltonian
  residual panels; invalid pixels are colored separately from escape pixels.
- These buffers remain Phase 1 diagnostic products only. Disk transfer,
  redshift, time delay, GRRT intensity, and XR rendering are later stages.
