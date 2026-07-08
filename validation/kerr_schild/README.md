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

### Critical-curve regression

The KS tracer reuses the analytic Kerr critical-curve polygon and the same
radial bisection method as the BL validator, but the capture/escape events are
classified by the horizon-penetrating KS integrator.

Formal command:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_ks_critical_curve --spin 0.9 --inclination-deg 60 --angles 48 --r-obs 100 --max-lambda 1200 --horizon-eps 0.02 --curve-samples 2048 --refine-steps 14 --out outputs/tier2/ks_critical_curve_a0.9_i60.json
```

Current reviewed result:

```text
center alpha = 0.9359348514 M
max_abs_error = 0.0027052051 M
rms_error = 0.0004011217 M
invalid = 0
max |H|_KS = 4.77e-8
min_r = 1.4158898944 M
```

## Remaining Stage A Gates

- Add analytic-horizon-crossing comparison from the indexed
  horizon-penetrating literature when the formula contract is selected.

## Task 2 WGSL Kerr-Schild Tracer Gate

The first GPU KS path validates the horizon-penetrating Hamiltonian RHS and RK4
kernel in WGPU/WGSL. Initial canonical states are generated on the CPU and
passed to the shader so the gate isolates the metric/RHS migration from camera
initialization. It is a fixed-step f32 test kernel, not yet a headset-rate
near-horizon free-flight renderer.

Formal command:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.validate_ks --spin 0.9 --inclination-deg 60 --fan-samples 55 --fan-alpha-max 8 --fan-betas 0,4,-4 --full-sky-samples 512 --step-size 0.01 --steps 20000 --max-lambda 800 --max-step 1 --step-r-ref 5 --out outputs/tier2/ks_gpu_a0.9_i60_rref5.json --h5 outputs/tier2/ks_gpu_a0.9_i60_rref5.h5
```

The JSON/HDF5 artifacts record:

- CPU f64 KS event/failure codes and GPU f32 KS event/failure codes;
- resolved-event agreement after separating both-side max-lambda
  unclassified samples from actual resolved samples;
- stable-event agreement after excluding near-capture samples;
- escaped-ray asymptotic momentum-direction error for stable escaped rays;
- escaped-direction errors and GPU `max |H|` grouped by `min_r` bands:
  legacy outer, near-horizon exterior, horizon-crossing, weak outer
  (`min_r > 5.5M`), and a photon-shell proxy band
  (`r_+ + max(0.1M, 2 horizon_eps) < min_r <= 5.5M`).

Acceptance:

- stable-event agreement `>= 98%`;
- both-side max-lambda unclassified samples are reported separately and should
  be zero for the formal `max_lambda = 800M` gate;
- GPU failures outside CPU-invalid / near-capture exclusions equal `0`;
- weak-outer escaped-direction median below `5e-6 rad` and max below
  `1e-4 rad`;
- photon-shell proxy escaped-direction errors are recorded separately because
  near-critical Kerr rays are Lyapunov sensitive in f32 fixed-step RK4;
- horizon-crossing `max |H|` is reported as f32 diagnostic evidence rather
  than compared to the CPU f64 exterior `1e-8` target.

Current `a = 0.9`, `i = 60 deg` result:

```text
sample_count = 677
full_event_agreement = 1.0
resolved_event_agreement = 1.0
stable_event_agreement = 1.0
both_unclassified_max_lambda = 0
gpu_failure_outside_exclusions = 0
escape_direction_sample_count = 602
escape_direction_median_error = 1.29e-6 rad
escape_direction_rms_error = 6.04e-4 rad
escape_direction_max_error = 9.66e-3 rad
escape direction error by min_r band:
  weak_outer: count = 552, median = 1.15e-6 rad, max = 7.49e-5 rad
  photon_shell_proxy: count = 50, median = 7.55e-5 rad, max = 9.66e-3 rad
  legacy outer: count = 599, median = 1.29e-6 rad, max = 9.66e-3 rad
  near_horizon_exterior: count = 3, median = 5.54e-3 rad, max = 6.81e-3 rad
  horizon_crossing: count = 0
gpu max |H| by min_r band:
  weak_outer = 8.63e-6
  photon_shell_proxy = 6.07e-6
  legacy outer = 8.63e-6
  near_horizon_exterior = 6.07e-6
  horizon_crossing = 2.38e-5
```

The adaptive step is `h = h0 * max(1, r / r_ref)` with `r_ref = 5M`.  An
earlier `h = h0 * r` rule accelerated weak-field rays but enlarged the step in
the photon-shell band.  The current rule keeps the strong-field floor at
`h0 = 0.01M`, preserves weak-field acceleration, and reports the remaining
near-critical f32 direction tail as a separate photon-shell diagnostic instead
of mixing it into ordinary weak-outer accuracy claims.

### Near-horizon finite-observer GPU gate

The default Task 2 gate starts at `r_obs = 100M`, so it has limited statistical
power for rays launched by observers already close to the hole.  The
near-horizon gate reuses the same CPU-vs-GPU KS comparison but samples
finite-observer full-sky directions at smaller radii while keeping the escape
sphere in the far zone.

Formal command:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.validate_ks_near_horizon --spin 0.9 --inclination-deg 60 --r-obs-values 10,5,3 --samples 256 --r-escape 200 --step-size 0.01 --steps 20000 --max-lambda 800 --max-step 1 --step-r-ref 5 --out outputs/tier2/ks_gpu_near_horizon_a0.9_i60.json
```

Current result:

```text
r_obs values = 10M, 5M, 3M
samples per r_obs = 256
r_escape = 200M
min_resolved_event_agreement = 1.0
min_stable_event_agreement = 1.0
total_both_unclassified_max_lambda = 0
total_gpu_failure_outside_exclusions = 0
total_near_horizon_exterior_direction_samples = 10

r_obs = 10M:
  event counts = capture 9, escape 247, invalid 0
  escape-direction median/max = 7.52e-7 / 1.23e-5 rad
  max |H| horizon-crossing = 1.75e-5

r_obs = 5M:
  event counts = capture 51, escape 205, invalid 0
  escape-direction median/max = 1.23e-6 / 1.02e-4 rad
  max |H| horizon-crossing = 6.97e-6

r_obs = 3M:
  event counts = capture 122, escape 134, invalid 0
  escape-direction median/max = 2.57e-6 / 4.56e-5 rad
  max |H| horizon-crossing = 4.70e-6
```

This gate is still a finite-observer transfer-map comparison, not headset-rate
free flight.  It provides the low-radius accuracy evidence needed before
frustum-only realtime benchmarks can be interpreted.
