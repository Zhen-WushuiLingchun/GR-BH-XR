# Task 8 Rain-Frame Descent Keyframes

Full-sky transfer maps for the Doran rain observer (`E = 1`, `L = 0`, `Q = 0`,
released from rest at infinity) sampled along the actual infall worldline,
traced in the Cartesian ingoing Kerr-Schild chart, which is regular at the
outer horizon.

Images are built from **past-directed** rays. Inside the horizon the future
cone points inward, so what a camera sees is the history of the light that fell
in with it.

## Producing keyframes

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.generate_descent_keyframes `
  --spin 0.9 --theta-list-deg 60,90 --face-size 512 `
  --out-dir outputs/task8/descent_a0.9 --r-start 9.0 --r-min 0.75 --keyframes 20
```

## Committed validation gate

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.validate_descent_frames --out outputs/task8/descent_frames.json
```

Deterministic by construction: directions come from a Fibonacci sphere and the
observer position from the deterministic rain worldline integrator. There is no
RNG in the module. Rays whose Hamiltonian residual exceeds `1e-2` are excluded
and **counted**, never silently dropped, and the gate raises rather than
reporting a statistic if fewer than 256 rays survive, if any direction is
non-finite, or if more than 35% of escaping rays are excluded.

Current reviewed result (`a/M = 0.9`, `theta = 60 deg`, `r_obs = 2.35M`, 4096
directions, 3658 compared, 10.6% excluded by Hamiltonian residual):

```text
chart direction, r_escape = 200M : max 3.251e-4 deg, median 2.180e-4 deg
  same rays with no rotation     : max 1.333e-3 deg, median 1.165e-3 deg
chart direction, r_escape =  20M : max 7.543e-2 deg, median 2.709e-2 deg
  same rays with no rotation     : max 1.587e-1 deg, median 1.261e-1 deg
observer factor, float64         : 6.66e-16
observer factor, float32         : 1.196e-7   (1 f32 ULP at E ~ 1 = 1.192e-7)
  negative control, permuted legs: 1.575
  negative control, prose sign   : 1.812
launcher null residual g(q, q)   : 3.00e-15
```

### Why two escape radii

At `r_escape = 200M` the analytic azimuth correction
`delta = atan2(a, r) + shift(r)` is only about `1.3e-3 deg`, which is *larger
than the measured agreement itself*. A threshold gate there passes whether the
rotation is applied correctly, omitted entirely, or applied with the wrong
sign - it cannot discriminate, which is precisely how a sign error survived in
the original implementation. The `r_escape = 20M` pair separates the cases, and
the gate additionally asserts `rotationIsImprovement`: applying the rotation
must beat not applying it. That comparison is dimensionless and
self-calibrating.

The sign itself is subtle. The momentum-direction azimuth of an outgoing ray is
`phi_bl + shift + arctan(eps r / (1 - eps a))` with `eps = a / Delta`, which is
`phi_bl + a M / r^2` to `O(r^-2)`, whereas `delta` is `-a M / r^2`. The
position-space offset and the momentum-direction offset carry **opposite
signs**, so the correction is `+delta`. Rotating by `-delta` is worse than
doing nothing at every radius tested.

### Why the float32 energy threshold is 4 ULP, not 1e-7

The observer-factor check compares the shader form
`E_inf(d) = w + dot(d, xyz)` against the conserved `p_t`. Over this direction
set `E_inf` spans `[0.095, 1.905]`, so the smallest representable nonzero
float32 difference near `E ~ 1` is `2^-23 = 1.192e-7`. **A threshold below one
ULP is unachievable in principle**, and the measured value `1.196e-7` is
exactly that floor. The gate therefore uses `4 ULP = 4.8e-7`, which absorbs
different sampling and observer radii without admitting a real regression.

An earlier manifest claimed this agreement was `2.7e-8`. That number is not
merely unreproduced, it is arithmetically impossible for a float32 max-abs over
this range; it was never computed by any committed code. The archived probe
value `5.96e-8` is `2^-24`, consistent with a float64-vs-float32 comparison
rather than the float32-vs-float32 one the manifest described. Both are
representation artifacts rather than physics, and neither is used as a gate.

Note also what this check *is*: `rk4_step_ks` carries `p_t` through unmodified,
so comparing against the traced `p_t` is algebraically identical to comparing
against the launched one. It is a packing identity test, not an integrator
test. Its discriminating power comes entirely from the two negative controls -
a permuted leg order and the sign form that appeared in the original prose -
which must fail by more than `0.1` and measure `1.575` and `1.812`.

## Ray validity: Hamiltonian residual, not geometry heuristics

`H` is identically zero for a null geodesic, so `h_max_abs` is a
first-principles validity criterion. It is observer-radius independent and spin
independent. It replaces two geometric heuristics that were both defective:

- **Exterior `min_r < r_plus + 0.05`.** Applied regardless of the observer's
  own radius, so any exterior keyframe with `r_obs < r_plus + 0.05` had *every*
  ray - including ones launched straight outward - reclassified as dark. The
  default schedule hits this: at `a/M = 0.9`, `r_start = 9`, `r_min = 0.75`,
  20 keyframes, index 14 lands at `r = 1.4423`, which is exterior but only
  `0.0064` above `r_plus`, and the horizon nudge misses it. That keyframe
  rendered **completely black** with no error and a printed `escape=0`.
- **Interior `lambda_end > 0.6 * max_lambda`.** Roughly 10x under-inclusive:
  it let 644-799 texels per interior keyframe through with `h_max_abs` up to
  `1.7e10`, i.e. chaotic directions from past-directed rays that numerically
  punched through the past horizon and were ejected by the backward
  `exp(kappa lambda)` instability.

On healthy exterior keyframes the two criteria agree set-for-set on all 4096
sampled texels, which is mutual validation that the residual criterion is not
over-aggressive.

Measured escape fraction across a full descent (`a/M = 0.9`, `theta = 60 deg`,
face 24, 20 keyframes):

```text
r_obs  9.0000  ->  escape 0.986,  h-rejected   47
r_obs  2.7736  ->  escape 0.920,  h-rejected  271
r_obs  1.6438  ->  escape 0.860,  h-rejected  476
r_obs  1.4423  ->  escape 0.847,  h-rejected  519   (was 0.000 before the fix)
r_obs  1.2655  ->  escape 0.835,  h-rejected  557   (interior)
r_obs  0.7500  ->  escape 0.801,  h-rejected  661   (interior)
```

The generator additionally **fails closed**: a keyframe keeping less than
`min_escape_fraction` (default `0.25`) of the sky raises rather than shipping a
blank frame, and the worldline sampler must return exactly one position per
requested radius.

## Frame dragging

The ingoing Kerr-Schild chart azimuth of a prograde rain worldline drifts
**negative**: `dphi_ks/dtau = (a/Delta)(2M/r + dr/dtau)` and `|dr/dtau| > 2M/r`
throughout, so the chart twist beats the Boyer-Lindquist frame dragging (which
is itself positive). Measured total for `a/M = 0.9` over the default schedule:
`-23.7 deg`, monotone, at both `theta = 60` and `90 deg`. The azimuth unwrap
handles both directions; the original one-sided form was built for increasing
azimuth and would have silently failed on this sequence.

## Known caveats

- **The tetrad is not parallel transported.** It is constructed algebraically
  at each sampled point, so consecutive keyframes differ from a transported
  frame by a rotation the manifest does not record. `azimuthDeg` records a
  rotation of the observer *position*, not of the frame. This is stated in the
  manifest as `tetradTransportNote` and remains the open Stage B item.
- **Disk crossings are recorded only outside the horizon.** The
  Boyer-Lindquist azimuth and time shifts used to report a crossing diverge
  logarithmically at `r_plus`, so `KsGpuTraceConfig` now refuses a
  `disk_r_in` that does not clear the horizon by `0.25 M`. In practice the
  inner edge is the ISCO, far outside; the guard makes that a property of the
  configuration rather than of every caller.
- **Recorded crossings whose redshift is rejected are counted**, not silently
  dropped (`counts.diskCrossingsDropped`).
- **Disk edges get no sub-texel coverage** in the descent path, unlike the
  static maps, so disk limbs are harder-edged here.
- **`disk_phi_m` from the KS tracer is wrapped then offset**, whereas the
  Boyer-Lindquist tracer stores an unwrapped integrated azimuth carrying full
  winding. The two interoperate only because both consumers immediately take
  `sin` and `cos`; a consumer using `delta phi` or winding order would break.
