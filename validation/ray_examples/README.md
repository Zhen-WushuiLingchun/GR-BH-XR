# Ray Example Figure Validation

Phase: 1 CPU Kerr reference solver.

Purpose: generate a compact visual sanity check for representative
Schwarzschild equatorial rays without replacing the quantitative shadow and
critical-curve validators.

## Command

From the source tree:

```text
$env:PYTHONPATH='src'
python -m gr_bh_xr.plot_ray_examples --out figures/ray_examples.pdf
```

The generated PDF is ignored by Git under `figures/`. The figure shows one
capture ray, one near-critical ray at `b = 3 sqrt(3) M`, and one escaping ray,
with the horizon and photon sphere marked in the equatorial plane.

## Acceptance

- The command writes `figures/ray_examples.pdf`.
- Each plotted example uses the same Phase 1 Hamiltonian RHS and event
  conventions as the reference tracer.
- This figure is illustrative validation support only; numerical acceptance
  remains the Schwarzschild shadow radius, Kerr critical-curve comparison,
  Hamiltonian residuals, Carter `Q` drift, and event classification buffers.
