# BBH Dynamic-Spacetime Validation

This directory records the gates for the time-dependent metric and native XR
track. An image is not sufficient evidence: timing, metric source, ray state,
events, and residuals remain separate audit products.

## Task 1: Synthetic Stereo Performance

The native NPGS executable now has a device-independent sequential stereo mode.
It uses two OpenXR-shaped views with:

- distinct eye origins derived from `IPD / meters_per_M`;
- asymmetric per-eye FOV tangents;
- one native render at the requested per-eye extent for each eye;
- four Vulkan timestamps per eye: begin, prepass end, composite end, frame end;
- no image or physics-buffer readback in timed frames.

The existing NPGS history image is mono. Sequential mode therefore sets the
temporal blend weight to one so left-eye history cannot contaminate the right
eye. The composite shader and its history fetch remain in the timed path, but
temporal accumulation is disabled. Vulkan multiview and separate per-eye
histories remain an explicit follow-up; this gate does not call sequential
rendering multiview.

Run one case:

```powershell
.\tools\npgs\build.ps1 -Configuration Release -SkipDependencyInstall
.\tools\npgs\benchmark_stereo.ps1 `
  -EyeWidth 1832 -EyeHeight 1920 -WarmupPairs 20 -SamplePairs 80 `
  -Disk 1 -Polarization 0
```

Validate an existing native log:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_npgs_stereo_performance `
  --input outputs/bbh_stereo/run.stdout.log `
  --out outputs/bbh_stereo/run.json `
  --warmup-pairs 20 --max-pairs 80
```

### 2026-08-10 RTX 5080 Laptop Baseline

Environment: NVIDIA GeForce RTX 5080 Laptop GPU, driver 591.74, NPGS fork
`9b68f5318b8edd0056a740e8ac086ef10a2eb141`. Values are
sequential stereo-pair GPU p95 across 80 measured pairs after 20 warmup pairs.
Every one of the 16 cases had valid timestamps for 80/80 pairs.

| Per-eye extent | disk/polarization range | pair GPU p95 | physics 72 Hz (`<11 ms`) | physics 90 Hz (`<9 ms`) |
| --- | --- | ---: | --- | --- |
| 1600x1728 | all four combinations | 7.80-8.11 ms | pass | pass |
| 1832x1920 | all four combinations | 9.95-10.23 ms | pass | fail |
| 2064x2208 | all four combinations | 12.51-12.92 ms | fail | fail |
| 2464x2592 | all four combinations | 16.26-16.65 ms | fail | fail |

These are native GPU-render budgets, not headset refresh results. OpenXR frame
wait, predicted poses, swapchain acquire/release, compositor overhead, and
display timing are absent, so the total-frame 72/90 Hz gates remain `null` in
the JSON. CPU submission and prepass/composite/post GPU timings are reported
separately.

Ray-step distributions are unavailable in this visual fast path because they
would require diagnostic-buffer readback. WDDM does not provide reliable
per-process VRAM attribution through the current script; GPU model and driver
are recorded, while VRAM is marked unavailable rather than inferred. Dynamic
resolution and VRS are disabled in this baseline.

## Gate Boundary

Task 1 closes the sequential-stereo measurement path. It does not validate an
OpenXR session, Vulkan multiview, headset refresh, or a dynamic BBH metric.
Those claims remain closed until their later plan tasks pass.

## Task 2: Python f64 Dynamic Hamilton Oracle

The generic reference path samples a `TimeDependentMetricProvider` at every
DOP853 RHS evaluation and integrates all eight canonical variables.  In
particular,

```text
dp_t/dlambda = -1/2 partial_t(g^alpha beta) p_alpha p_beta
```

is never suppressed by the generic solver.  Event surfaces are supplied by the
caller and carry their own provenance; they are not hidden inside the metric
provider.  The audit record contains the null-Hamiltonian residual, provider
validity counts, interpolation-error maximum, source revision, final state, and
initial/final `p_t`.  It deliberately has no generic `E/L_z/Q drift` fields.

Focused gate:

```powershell
$env:PYTHONPATH='src'
python -m pytest -q tests/test_dynamic_metric.py tests/test_geodesic_dynamic.py
```

Observed f64 anchors on 2026-08-10:

- Minkowski straight ray: exact final Cartesian state at the tested endpoint,
  `max|H| = 5.55e-17`;
- accepted stationary Kerr-Schild derivative versus an independent central
  finite difference: maximum absolute difference `6.09e-12`;
- stationary Kerr-Schild escape/capture zero regression: both event classes
  agree, with dynamic-path `max|H| = 1.55e-12` and `1.71e-11` respectively;
- analytic time-dependent scale-factor oracle: `p_t` changes by
  `4.653741e-2` while `max|H| = 1.67e-16`;
- a provider-domain exit fails closed with metric-provider provenance.

The scale-factor provider is an analytic solver oracle, not a BBH model.  BBH
claims remain closed until the approximate provider and its constraint gates
pass.

## Task 3: Native Metric-Provider Interface

The native renderer now exposes the same provider concepts needed by a dynamic
metric without changing the accepted stationary Kerr-Newman arithmetic.  The
C++ contract records `(t,x,y,z)` covariant/inverse metrics, all four
`partial_mu g^alpha_beta`, ADM lapse/shift/spatial metric, validity, evidence,
interpolation error, and source revision.  The historical GLSL state remains
`(x,y,z,t)` and its stationary adapter explicitly fixes `p_t` only because
`partial_t g^alpha_beta` is identically zero.

The raw-v3 binary zero-regression used the same 17x17 Kerr case before and
after extraction (`a/M=0.9`, `Q/M=0`, `i=60 deg`, `r_obs=100M`, `FOV=40 deg`,
quality 2).  Both files have SHA-256
`3C8B5F371DDD781D76DE58C95BE63509E04000A58CD1914A256C592978A82B33`.
All 73,984 bytes are identical: 4 capture, 285 escape, 0 invalid, and 0
nonfinite records.  The JSON sidecar additionally identifies
`npgs.kerr-newman-ks.v1`, `analytic_exact`, `stationary=true`, metric time,
validity domain, and zero interpolation error.

The representative stationary fast-path check at 1832x1920 per eye, disk off
and geometric polarization on, measured 10.188 ms stereo-pair GPU p95 over 80
pairs after 20 warmup pairs.  The pre-refactor baseline was 10.164 ms, a
0.24-percent increase and below the two-percent task threshold.  This remains
sequential synthetic stereo rather than an OpenXR total-frame result.

## Task 4: Analytic Dynamic-Spacetime Gates

The first genuinely time-dependent metric gate is a linear transverse-
traceless plane gravitational wave based on `angelil2015gwOptics` Eq. 2 and
Eq. 14. It tests the full dynamic Hamilton solver before the approximate BBH
provider is introduced.

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_dynamic_analytic `
  --amplitude 1e-3 --angular-frequency 0.7 --distance 7 `
  --visual-gain 1 `
  --out outputs/bbh_dynamic/plane_gw_analytic.json
```

Observed f64 evidence on 2026-08-10:

- zero amplitude is exactly Minkowski;
- analytic inverse-metric derivatives agree with an independent finite-
  difference oracle to `6.69e-11` maximum absolute difference;
- the numerical arrival delay is `1.290025e-3`, versus the first-order result
  `1.290536e-3`;
- halving strain changes the higher-order residual by a factor `3.99982`, an
  observed convergence order of `1.99994`;
- `max|H| = 1.05e-15`, while `p_t` changes by `-3.8567e-4` as required for a
  time-dependent metric;
- physical angular displacement is `1.01793e-4 rad`; `visual_gain=1` leaves it
  unchanged exactly.

The vacuum claim is linear in the physical strain amplitude. This is an
analytic dynamic-metric gate, not a binary-black-hole model and not a claim
that a display-amplified gravitational wave has physical amplitude.

## Task 5a: Equal-Mass Superposed Kerr-Schild Metric

The first approximate BBH metric is the smallest reviewable slice of
Combi-Ressler Eq. 11: equal masses, zero spin, fixed separation, and a
Newtonian circular orbit. It uses instantaneous Lorentz boosts and omits the
explicit acceleration term in the coordinate Jacobian exactly as documented
by the source. It is not the later 4PN inspiral-to-remnant model.

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_bbh_constraints `
  --stencil-step 0.04 `
  --out outputs/bbh_dynamic/bbh_constraints_equal_mass.json `
  --h5 outputs/bbh_dynamic/bbh_constraints_equal_mass.h5
```

Observed f64 evidence on 2026-08-10:

- inverse derivative complex-step versus centered finite difference:
  `6.37e-12` maximum absolute difference;
- half-period equal-mass exchange symmetry: `2.22e-16`;
- companion perturbation under separation doubling: `2.0044` and `2.0027`,
  consistent with the isolated-hole `1/d` limit;
- constraint stencil relative change: `8.09e-3`;
- near-hole `max|H|=5.47e-2`, bridge `max|H|=2.01e-3`, and far
  `max|H|=2.97e-7`;
- far Hamiltonian log2 slopes under radius doubling: `-5.67` and `-7.40`.

The JSON and HDF5 persist every constraint sample, separation, phase, region,
and momentum residual. These finite nonzero residuals are the expected quality
measure of a superposed metric. The provider is always labelled
`physics_approximation`; its excision worldtubes are not event horizons.

## Task 5b: Leading-Quadrupole Inspiral

The orbit layer next adds unequal masses and a shrinking nonspinning circular
orbit using `peters1964grMotionTwoPointMasses`. It is intentionally narrower
than the full 4PN trajectory used by Combi-Ressler.

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_bbh_orbit `
  --out outputs/bbh_dynamic/bbh_orbit_quadrupole.json
```

The gate covers `q=m1/m2` values `1` and `0.5`, center-of-mass cancellation,
the analytic separation and phase derivatives, Newtonian binding-energy /
quadrupole-flux balance, and fail-closed minimum separation. Full 4PN spin and
eccentric corrections remain open and cannot be inferred from this gate.

The formal run records zero center-of-mass residual, maximum relative errors
`2.20e-9` in `dr/dt`, `3.01e-9` in orbital frequency, and `3.09e-16` in
Newtonian energy balance.

## Task 5c: Aligned And Generic Spin

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_bbh_spin `
  --out outputs/bbh_dynamic/bbh_spin_gate.json
```

The gate compares a z-aligned single-hole term directly with the accepted
Cartesian Kerr metric, rotates a generic spin and field point together, checks
all four inverse-metric derivatives, and persists near/bridge/far ADM
constraint residuals. It validates the implemented superposed-Kerr
approximation; it does not promote that superposition to an Einstein solution.

## Task 5d: Merger To Kerr Remnant

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_bbh_remnant `
  --out outputs/bbh_dynamic/bbh_remnant_transition.json
```

This gate proves both hard endpoints, Appendix-B weight symmetry, state
continuity, derivative agreement, and pre/mid/post constraint behavior. The
remnant parameters are supplied explicitly; this is not yet a validation of
any numerical-relativity remnant fitting formula.

The formal gate records endpoint metric errors `0` and `2.22e-16`, transition
weight symmetry error `1.11e-16`, and inverse-derivative disagreement
`3.35e-9`. At the sampled bridge point, the Hamiltonian constraint rises from
`7.81e-5` before transition to `5.57e-4` mid-transition, then falls to
`6.46e-7` at the exact post-merger Kerr endpoint.
