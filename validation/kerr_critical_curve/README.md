# Kerr Critical Curve Validation

Phase: 1 CPU Kerr reference solver.

Purpose: compare the numerical capture/escape boundary of the
Boyer-Lindquist exterior reference tracer against the analytic Kerr critical
curve from `gralla2020nullGeodesicsKerr`, `gralla2020lensingKerr`, and
`bardeen1973kerrGeodesics`.

## Analytic Curve

For `0 < a < M`, bound spherical photon orbits are parameterized by
`r_tilde` in the photon shell:

```text
r_ph_minus = 2M [1 + cos((2/3) arccos(-a/M))]
r_ph_plus  = 2M [1 + cos((2/3) arccos(+a/M))]
```

The critical constants are:

```text
Delta(r) = r^2 - 2 M r + a^2
lambda_tilde(r) = a + (r/a) [r - 2 Delta(r)/(r - M)]
eta_tilde(r) = (r^3/a^2) [4 M Delta(r)/(r - M)^2 - r]
```

The distant-observer screen map is:

```text
alpha = -lambda / sin(theta_o)
beta = +/- sqrt(eta + a^2 cos^2(theta_o) - lambda^2 cot^2(theta_o))
```

Only samples with real `beta` are visible to the selected observer.

## Commands

From the source tree:

```text
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_kerr_critical_curve --spin 0.5 --inclination-deg 60 --angles 48 --out outputs/phase1/kerr_critical_curve_a0.5_i60.json
python -m gr_bh_xr.validate_kerr_critical_curve --spin 0.9 --inclination-deg 60 --angles 48 --out outputs/phase1/kerr_critical_curve_a0.9_i60.json
```

Generated JSON files are written under `outputs/phase1/`, which is ignored by
Git. They record max/RMS/median boundary errors, event counts, worst
diagnostics, and per-angle samples.

## Acceptance

Default validation runs should satisfy:

```text
max_abs_error < 0.05 M
rms_error < 0.02 M
invalid == 0
```

The validator uses an explicit `horizon_eps = 0.02 M` so high-spin prograde
critical-curve comparisons are not biased by the safer general tracing default
of `r_+ + 0.3 M`. The worst Hamiltonian and conserved-quantity diagnostics are
recorded for audit, but near-capture Boyer-Lindquist residuals are not the
primary pass/fail condition for this curve comparison.
