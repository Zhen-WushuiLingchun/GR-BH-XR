# Kerr-Schild Stage A Validation

This directory tracks the horizon-penetrating Kerr-Schild reference-solver
gates. The current code is still a Stage A CPU reference path, not a
near-horizon roaming renderer.

## Implemented Gates

### Metric primitives

Covered by `tests/test_metric_ks.py`:

- Schwarzschild Kerr-Schild limit on the Cartesian `x` axis.
- Kerr-Schild null covector is null against the flat background.
- `g_mu nu g^nu rho = delta_mu^rho`.
- BL / Kerr-Schild spatial-coordinate roundtrip.
- Analytic Cartesian derivatives of `g^mu nu` match finite differences.
- The metric stays finite at the outer horizon.
- `det(g) = -1` inside/outside the outer horizon.
- Stationary/axisymmetric Killing norms match the existing BL metric outside
  the horizon.

### Hamiltonian tracer seed

Covered by `tests/test_geodesic_ks.py`:

- BL -> KS canonical state transform preserves the null Hamiltonian.
- Schwarzschild escape ray matches BL event classification and minimum-radius
  scale.
- Schwarzschild captured ray continues inside the outer horizon with bounded
  Hamiltonian residual.
- Representative Kerr escaped-ray direction matches BL to `< 2e-6 rad`.
- Near-extremal capture surface remains between `r_-` and `r_+`.

### Exterior fan cross-check

The formal CLI compares a deterministic screen-coordinate fan in BL and KS:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_ks_bl_crosscheck --spin 0.9 --inclination-deg 60 --alpha-min -8 --alpha-max 8 --beta 0 --samples 55 --out outputs/tier2/ks_bl_crosscheck_a0.9_i60.json
python -m gr_bh_xr.validate_ks_bl_crosscheck --spin 0.9 --inclination-deg 90 --alpha-min -8 --alpha-max 8 --beta 0 --samples 55 --out outputs/tier2/ks_bl_crosscheck_a0.9_i90.json
```

Current reviewed result:

```text
a = 0.9, i = 60 deg: event_mismatches = 0, max escape-dir error = 2.11e-8 rad
a = 0.9, i = 90 deg: event_mismatches = 0, max escape-dir error = 2.11e-8 rad
```

The output JSON files are generated artifacts under ignored `outputs/tier2/`.

## Remaining Stage A Gates

- Add equatorial disk-crossing events in Cartesian KS coordinates.
- Convert KS states to BL only where valid and record Carter `Q` drift.
- Run Kerr critical-curve regression with the KS tracer.
- Add a denser full-sky KS/BL exterior cross-check before any keyframe transfer
  map claims.
- Add analytic-horizon-crossing comparison from the indexed
  horizon-penetrating literature when the formula contract is selected.
