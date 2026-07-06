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
diagnostics, grouped diagnostics, and per-angle samples.

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

The pass/fail criterion for this validator is the capture/escape boundary error
and invalid-event count. The JSON keeps the legacy aggregate
`worst_diagnostics` field and also writes `diagnostic_groups.outer` and
`diagnostic_groups.near_capture`, split at:

```text
min_r <= r_+ + max(0.1 M, 2 horizon_eps)
```

The outer group is the place to review Hamiltonian residuals separately from
capture-side termination. With analytic inverse-metric derivatives, the default
outer-group residual should satisfy `max |H| < 1e-8`. The near-capture group is
expected to degrade as rays approach the Boyer-Lindquist coordinate
singularity, especially for high-spin prograde samples. Near-capture
exceedances are recorded as a numerical limitation and motivation for the
deferred Kerr-Schild horizon-penetrating solver, not a failure of the
critical-curve boundary comparison.

For this implementation, `E = -p_t` and `L_z = p_phi` drift are structural
zeroes because `t` and `phi` are cyclic coordinates and the Hamiltonian right
hand side does not update `p_t` or `p_phi`. They remain in the JSON for schema
completeness, but the informative drift checks are the Hamiltonian residual and
Carter `Q`.
