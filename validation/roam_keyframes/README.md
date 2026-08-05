# Task 7 Finite-Observer Roam Keyframes

Quasi-static roaming over an `(r_obs, theta)` grid of finite-radius
static-observer full-sky transfer cubemaps. Each keyframe is an independent
`generate_transfer_cubemap` product; the runtime binds the keyframe nearest in
`(log r_obs, theta)`.

This is a **physics approximation**, not a boosted worldline: no kinematic
aberration is modeled between keyframes. The observer is a sequence of
momentarily static observers.

## Producing a grid

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.generate_roam_keyframes `
  --spin 0.9 --theta-list-deg 30,60,90,120,150 `
  --face-size 512 --out-dir outputs/task7/roam_a0.9 `
  --r-max 100 --r-min 2.5 --keyframes 12 --steps 28000
```

## What is validated

### Escape radius floor

The legacy escape rule `r_escape = 2 r_obs` is not asymptotic for a
near-horizon observer, so momentum-direction extraction is taken at a radius
that is not yet flat. Measured escape-direction extraction error against a
`3200M` reference (`a/M = 0.9`, `i = 60 deg`, 128 escaping rays):

```text
r_obs = 2.5M, r_escape = 2 r_obs :  6.695 deg mean / 22.79 deg max
r_obs = 2.5M, r_escape = 20      :  0.162 / 0.347
r_obs = 2.5M, r_escape = 50      :  0.133 / 0.241
r_obs = 2.5M, r_escape = 200     :  0.132 / 0.239
r_obs = 100M, r_escape = 2 r_obs :  0.021 / 0.050
```

`r_escape >= 20` holds truncation under `0.35 deg`; by `50` the curve has
reached its floor. `DEFAULT_R_ESCAPE_MIN = 200` is deliberately conservative.

The residual floor (`0.13 deg` at `r_obs = 2.5M`, `0.08` at `5M`, `0.05` at
`10M`, `0.007` at `100M`) is **not** escape-radius truncation - it is
accumulated f32 RK4 error along the longer near-horizon path, and no escape
radius removes it. Near-horizon keyframes therefore carry an irreducible
`~0.13 deg` direction error.

`r_escape_min` defaults to `0.0`, which reproduces `2 r_obs` exactly, so no
existing gate moves.

### Shadow growth (physics gate, per theta row)

The gate is on `captureSolidAngleFraction`, the fraction of the observer's
`4 pi` sky captured by the horizon, weighted by cube-texel solid angle. Cube
texels do not subtend equal solid angle, so a raw texel count is a distorted
measure of the quantity the physics claim is about. It is computed from the
**raw pre-repair** classification so image-repair stages cannot move a physics
gate.

Measured, `a/M = 0.9`, face 32, 6 log-spaced radii:

```text
theta =  30 deg : 0.000620 0.002465 0.010800 0.043831 0.164488 0.551254
theta =  90 deg : 0.000620 0.002465 0.011296 0.045690 0.178816 0.673544
theta = 150 deg : 0.000620 0.002465 0.010800 0.043831 0.164488 0.551254
r_obs           : 100.0    47.818   22.865   10.934   5.228    2.500
```

The gate carries a tolerance of `3 / sqrt(total_pixels)`. At the outer
keyframes the per-step signal is comparable to boundary quantization noise
(at face 512 the capture region at `100M` is about 470 texels against
quantization noise of about 77), and a strict comparison turns a multi-hour
grid into a spurious failure. The tolerance is far below the near-horizon
growth where the gate has to bite. The whole `(theta, radius)` grid is
validated for ergosphere clearance *before* any GPU time is spent.

### Mirror symmetry (invariant, not prose)

`theta -> pi - theta` is an isometry of Kerr. The claim is tested at two
levels, both committed:

1. `tests/test_roam_mirror_symmetry.py` - the real per-ray invariant. Escape
   directions must satisfy `(dx, dy, dz) -> (dx, -dy, dz)` in Unity components
   between a ray at `theta` and its y-flipped counterpart at `180 - theta`, and
   `r_m`, `g_m` are reflection scalars. Measured over 10800 ray pairs
   (`a/M = 0.9`, `theta` in 20/30/60/90 deg, `r_obs` in 2.5/6/30M):

```text
event-code mismatches        : 0 / 10800
one-sided disk records       : 0
escape direction (n = 5375)  : p50 0.00078 deg, p99 0.0183 deg, max 1.676 deg
|delta r_m| (n = 1635)       : p99 1.54e-4 M, max 6.31e-3 M
|delta g_m|                  : p99 1.19e-5,   max 5.01e-4
```

The `p99` of `0.0183 deg` is the f32 *representation* floor of the
`arccos(dot)` metric itself - a unit f32 vector dotted with itself already
yields up to `0.0428 deg`. The invariant therefore holds as tightly as f32 can
express it. The tail (2 pairs above `0.2 deg`) is chaotic near-critical rays
whose `min_r` sat on the photon ring (`1.56-3.91 M` for `a/M = 0.9`), where
exponential sensitivity to f32 rounding is physical. A max-based gate would be
flaky, so the committed gate is a percentile plus a bounded-outlier fraction.

2. The closed-form basis identity `right' = R right`, `up' = -R up`,
   `forward' = R forward` with `R = diag(1, 1, -1)`, verified to `2.8e-16`.

Note that comparing two capture-fraction *table rows* is a much weaker check
than it looks: the cubemap texel set is itself invariant under the Unity
y-flip, so aggregate counts are largely forced to agree. The grid run above
does show `theta = 30` and `theta = 150` agreeing digit-for-digit, which is
consistent, but the per-ray test is the one carrying the evidence.

### Theta and radius envelope

`ROAM_THETA_MIN_DEG = 30`, `ROAM_THETA_MAX_DEG = 150`. This is exactly the grid
the committed tests exercise. It is **not** a measured failure boundary: a
full-sky sweep at `r_obs = 2.5M` and `6M` shows at most 1 invalid texel of 3456
anywhere in `theta = 2..178 deg`, with no cliff at either end and a
non-monotonic invalid count that tracks which texel happens to land on the
polar axis rather than any degradation in `theta`. Widening the envelope
requires a committed near-polar keyframe artifact, not just a wider default.

The envelope must not be justified by the Bardeen `1/sin(theta_obs)` screen-map
degeneracy. That argument is correct for `gr_bh_xr.gpu.preview`, which
evaluates the `alpha`/`beta` screen map, and it is the origin of that module's
`[20, 160]` warning. The roam generator reaches the tracer through
`initial_state_direction`, which builds the observer tetrad from a Unity unit
vector and never evaluates that map, so the rationale does not transfer. A test
pins that the rationale is not repeated.

Radii are geometric code lengths, equal to `r/M` only when `M = 1`. The
`r_max = 100` / `r_min = 2.5` defaults are conventions, not validated bounds;
accuracy-gated observer radii elsewhere in the repo are `{3, 5, 10, 50, 80,
100, 300}M`. The ergosphere margin is `0.1 * M` rather than an absolute `0.1`,
so the admitted worst-case static tetrad boost `1 / sqrt(-g_tt)` is scale
invariant at `4.58`; with an absolute margin it would silently tighten to
`14.2` at `M = 10`.

### Azimuthal motion

Exact by axisymmetry. Both launchers start the ray at `phi = 0` at the
observer, so every recorded azimuth is already relative to the observer and
orbiting in `phi` is a rigid rotation of the map basis about the spin axis.
This exactness is structural - there is no `phi` parameter to vary, so no
Python-side test is possible - and it **assumes the disk model is
axisymmetric**. A consumer painting a non-axisymmetric feature (hot spot,
spiral) from `phi_m` must add the observer azimuth back, or the pattern will
co-rotate with the observer.

## Known caveats

- **Polar band is reported, not repaired.** Texels whose Boyer-Lindquist
  trajectory approached the axis closer than `polarBandThreshold` are counted
  in `polarBand.texels` with `repaired: false`. The chart-regular fix is a
  Cartesian Kerr-Schild retrace, which needs the KS tracer's equatorial
  disk-crossing outputs and so lands with the Kerr-Schild work. Treat a large
  count as a quality caveat on that keyframe.
- **Metadata separates pre- and post-repair statistics.** `eventCounts` is the
  raw per-ray classification accumulated during tracing; `shippedEventCounts`
  classifies the bytes actually written. The repair stages rewrite event codes,
  so the two can legitimately disagree, and a reviewer reading only the
  manifest would otherwise not be reading the shipped array.
- **Every post-trace stage reports whether it ran.** `stages.*.applied` is
  false when a stage is configured off (for example
  `disk_coverage_subsamples <= 1` disables coverage anti-aliasing and the
  jittered retrace), and the accompanying note says so rather than advertising
  a stage that did not execute.
- **`invalidInpaint` is a heuristic repair, not traced physics.** Its texel
  count is recorded so a reviewer can bound how much of the cube it touched.
- **`lambda_budget` is not comparable across the grid.** The launcher
  normalizes `-p.u = 1` in the observer frame, so `E = -p_t = sqrt(-g_tt)`
  falls from `0.9899` at `r_obs = 100M` to `0.2990` at `2.1M`; a fixed
  `step_size * steps` buys roughly `3.3x` less coordinate path at the inner
  keyframes.
