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
- Exterior-only Carter `Q` diagnostics are reported by the KS tracer. The
  diagnostic converts KS states back to BL only for samples safely outside the
  outer horizon and away from the axis; horizon-interior samples are counted as
  skipped instead of forcing a singular BL conversion.

Current representative values:

```text
a = 0.9, i = 60 deg, escape ray (alpha=8, beta=2):
  q_drift_abs = 1.60e-10
  q_sample_count = 307
  q_skipped_count = 0

a = 0, captured equatorial ray:
  q_drift_abs = 1.37e-31
  q_sample_count = 127
  q_skipped_count = 3
```

### Exterior fan cross-check

The formal CLI compares a deterministic screen-coordinate fan in BL and KS:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_ks_bl_crosscheck --spin 0.9 --inclination-deg 60 --alpha-min -8 --alpha-max 8 --beta 0 --samples 55 --out outputs/tier2/ks_bl_crosscheck_a0.9_i60.json
python -m gr_bh_xr.validate_ks_bl_crosscheck --spin 0.9 --inclination-deg 90 --alpha-min -8 --alpha-max 8 --beta 0 --samples 55 --out outputs/tier2/ks_bl_crosscheck_a0.9_i90.json
python -m gr_bh_xr.validate_ks_bl_crosscheck --spin 0.9 --inclination-deg 60 --alpha-min -8 --alpha-max 8 --beta 4 --samples 25 --out outputs/tier2/ks_bl_crosscheck_a0.9_i60_b4.json
python -m gr_bh_xr.validate_ks_bl_crosscheck --spin 0.9 --inclination-deg 90 --alpha-min -8 --alpha-max 8 --beta -4 --samples 25 --out outputs/tier2/ks_bl_crosscheck_a0.9_i90_b-4.json
```

Current reviewed result:

```text
a = 0.9, i = 60 deg, beta = 0:
  event_mismatches = 0
  both_valid_event_mismatches = 0
  max escape-dir error = 2.11e-8 rad

a = 0.9, i = 90 deg, beta = 0:
  event_mismatches = 0
  both_valid_event_mismatches = 0
  max escape-dir error = 2.11e-8 rad

a = 0.9, i = 60 deg, beta = +4:
  event_mismatches = 1
  both_valid_event_mismatches = 0
  bl_invalid_ks_valid = 1
  ks_invalid_bl_valid = 0
  bl_invalid_ks_valid_max_h = 6.13e-9

a = 0.9, i = 90 deg, beta = -4:
  event_mismatches = 1
  both_valid_event_mismatches = 0
  bl_invalid_ks_valid = 1
  ks_invalid_bl_valid = 0
  bl_invalid_ks_valid_max_h = 3.43e-9
```

The `2.1e-8 rad` escaped-direction value is the double-precision `acos`
resolution floor when the dot product differs from `1` by one ulp; it should
not be interpreted as a physical error plateau.

The v2 event fields intentionally separate:

- `both_invalid_count`: a gate-hardening count for rays where both chart
  implementations fail; the formal fan gates require this to stay zero so
  simultaneous failures cannot pass silently as `same`;
- `both_valid_event_mismatches`: hard failures where BL and KS both classify a
  ray but disagree;
- `ks_invalid_bl_valid`: hard failures where the new KS path fails where the
  validated BL exterior path remains valid;
- `bl_invalid_ks_valid`: improvement evidence where the BL chart reaches an
  axis/horizon coordinate pathology but KS continues with bounded residuals.

The output JSON files are generated artifacts under ignored `outputs/tier2/`.

### Disk-transfer cross-check

The KS tracer also records non-terminal equatorial `z = 0` crossings and
converts those crossing states back to exterior BL coordinates for comparison
with the existing thin-disk transfer buffers. The emitted `phi_m` is the BL
azimuth after removing the ingoing Kerr-Schild `_phi_shift`, so it is directly
comparable to the Phase 4 disk-transfer schema.

Formal command:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_ks_disk_transfer --spin 0.9 --inclination-deg 60 --grid 64 --alpha-max 30 --beta-max 30 --r-obs 100 --max-lambda 1400 --r-escape 200 --horizon-eps 0.05 --max-step 1 --r-out 30 --max-order 2 --workers 8 --out outputs/tier2/ks_disk_transfer_a0.9_i60_64.json --h5 outputs/tier2/ks_disk_transfer_a0.9_i60_64.h5 --quiet
```

Acceptance:

- `disk_validity_mismatch_count = 0`;
- `event_mismatch_count = 0` for the matched exterior grid;
- matched samples report `|Delta r_m|`, wrapped `|Delta phi_m|`,
  `|Delta t_m|`, and `|Delta g_m|` in the JSON/HDF5 artifacts.

Current reviewed result for `a = 0.9`, `i = 60 deg`, `64x64`:

```text
event_mismatch_count = 0
disk_validity_mismatch_count = 0
valid_by_order = [1900, 60]
compare_sample_count = 1960
max |Delta r_m| = 2.37e-7 M
max |Delta phi_m| = 4.80e-9 rad
max |Delta t_m| = 2.47e-7 M
max |Delta g_m| = 4.34e-9
max |H|_KS = 9.58e-9
```

## Remaining Stage A Gates

- Run Kerr critical-curve regression with the KS tracer.
- Add a denser full-sky KS/BL exterior cross-check before any keyframe transfer
  map claims.
- Add analytic-horizon-crossing comparison from the indexed
  horizon-penetrating literature when the formula contract is selected.
