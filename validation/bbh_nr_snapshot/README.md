# BBH ADM Snapshot Validation

This gate defines the first numerical-relativity volume contract used by the
dynamic Hamiltonian tracer. It validates ingestion and interpolation; it does
not claim that a production BBH evolution has been run.

## Schema

`gr-bh-xr.bbh.adm-snapshot.v1` stores:

- a strictly increasing coordinate-time axis;
- one or more uniform Cartesian AMR levels;
- ADM lapse `alpha`, contravariant shift `beta^i`, and `gamma_ij` in
  `(time,x,y,z,...)` order;
- explicit parent IDs and per-level interpolation-valid coordinate bounds;
- one spatial error bound per time slice and one temporal error bound per
  interval;
- producer name/version/commit, formulation, gauge, coordinates, units,
  constraint-history provenance, and source kind;
- SHA-256 for every numeric dataset, including dtype and shape.

The provider reconstructs `g_mu_nu`, `g^mu_nu`, and all four derivatives of
`g^mu_nu` from the interpolated ADM fields. It uses trilinear space and linear
time interpolation. A fine level is selected only when its complete stencil
lies inside its declared validity box; otherwise selection falls back to an
explicit parent or returns `outside_domain`.

## Synthetic Gate

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_nr_snapshot `
  --output-dir outputs/bbh_nr_snapshot/synthetic `
  --out outputs/bbh_nr_snapshot/summary.json `
  --producer-commit (git rev-parse --short HEAD)
python -m pytest -q tests/test_nr_snapshot.py
```

Observed on 2026-08-10:

- Minkowski metric/derivative maximum errors:
  `4.44e-16 / 3.33e-16`;
- linear TT plane-GW metric RMS error:
  `2.48e-4 -> 6.20e-5`, convergence ratio `3.996`;
- plane-GW inverse-metric derivative RMS error:
  `1.97e-3 -> 9.95e-4`, convergence ratio `1.979`;
- sampled stationary Kerr node metric and inverse-identity errors:
  `3.33e-16 / 3.33e-16`;
- AMR selections for fine interior, fine guard/coarse fallback, and outside
  all levels: `[1, 0, null]`;
- an SXS-shaped waveform-only probe is rejected as
  `waveform_only_asset`.

The metric converges at second order and its piecewise-linear derivative at
first order, as preregistered. The stored synthetic error bound is deliberately
conservative (`0.2`) and exceeds every observed metric/derivative error.

## CarpetX Conversion

`python -m gr_bh_xr.convert_carpetx_snapshot` requires both a provenance JSON
and an explicit field-map JSON. It does not guess thorn names or component
order. The converter records the source-file SHA-256 and exact field map in the
output metadata. A real CarpetX export is not accepted until Task 8 pins the
release, thorn list, parameter file, gauge, constraint history, and two-
resolution evolution evidence.

Public SXS waveform/horizon products remain useful waveform evidence, but
they are not silently treated as a complete evolved near-zone four-metric.
