# Physical Scope

GR-BH-XR is a physics-auditable renderer. Its purpose is to compute, cache,
visualize, and inspect relativistic transfer quantities for black-hole scenes,
not merely to produce visually plausible images.

## Core Transfer Map

The central object is the null-geodesic transfer map:

```text
(alpha, beta) ->
  escape/capture,
  r_m, phi_m,
  g_m,
  Delta t_m,
  n_m,
  tau_m,
  I_nu_o
```

Where:

- `(alpha, beta)` are observer-screen coordinates.
- `m` is image order or disk-crossing order.
- `g_m = nu_o / nu_e` is the redshift factor.
- `Delta t_m` is the time delay.
- `n_m` is winding or orbit number.
- `tau_m` is optical depth.
- `I_nu_o` is observed specific intensity.

## First-Year Scope

The first-year target is:

```text
single Kerr black hole
+ background lensing
+ shadow
+ thin disk transfer function
+ redshift/Doppler effects
+ time-delay-aware disk variability
+ direct, secondary, and higher-order images
+ Quest 3 PCVR/MR display
+ benchmark comparisons with AART, RAPTOR, and Odyssey where applicable
```

## Deferred Scope

The following are deferred until the Kerr pipeline and validation path are
stable:

- full GRMHD;
- BBH numerical relativity;
- Kerr-Newman charge as a validated physical model;
- Quest-native GRRT;
- neural networks that directly generate final black-hole images;
- true passthrough-pixel lensing in MR unless camera-frame access is available.

## Static Kerr Real-Time Boundary

For the first single-Kerr PCVR path, the metric is stationary and axisymmetric.
That permits a static transfer-map workflow: geodesics, escape directions, disk
crossing positions, redshift factors, and time delays can be computed offline
for one observer configuration, then consumed by a real-time shader.

This is a display and integration shortcut, not the final renderer model. It is
acceptable for the Task 5 fixed-observer Quest gate and for the first animated
thin-disk demo, because only the emissivity pattern changes in time. It is not
acceptable as the general answer to parameter changes, observer motion, BBH,
multi-black-hole scenes, or gravitational-wave lensing.

Use three separate renderer tiers:

```text
Tier 0: static transfer-map playback
  fixed metric + fixed observer + fixed screen bounds
  Unity/Quest consumes precomputed textures only

Tier 1: real-time or near-real-time GPU transfer-map update
  spin / inclination / observer / screen-window changes trigger GPU tracing,
  tiled updates, progressive refinement, or cached parameter interpolation

Tier 2: dynamic-metric cache or surrogate
  BBH, multi-black-hole, or gravitational-wave lensing uses time-indexed maps,
  adaptive tracing, reduced-order models, or neural surrogates validated against
  exact data and audit buffers
```

Do not describe Tier 0 as real-time geodesic integration. It is real-time
rendering of an offline geodesic transfer map. Any UI that exposes spin,
inclination, observer position, or binary phase must either regenerate/select a
matching transfer map or visibly mark the output as a stale/approximate preview.

This shortcut is valid only for the stated model. A non-axisymmetric thin-disk
emissivity pattern can rotate without re-tracing geodesics by advecting the
emission coordinates in the disk frame:

```text
I_pixel(t) ~ e(r_m, phi_m - Omega(r_m) * (t - Delta t_m)) * g_m^p
```

where `p = 3` or `p = 4` must be chosen and documented with the intensity
convention. The transfer map stays fixed; the disk texture is sampled at the
retarded emission time.

This is not a general recipe for BBH, multi-black-hole, or gravitational-wave
lensing. Time-dependent or non-axisymmetric metrics break the static-Kerr
cache assumption and require a documented metric source plus time-dependent
transfer maps, offline/cache playback, adaptive GPU tracing, or validated
surrogates. A static Kerr map must not be reused as evidence for those future
systems.

## Visual And Academic Claims

Use these labels consistently:

- `validated physics`: backed by equations, invariants, and benchmark checks.
- `physics approximation`: documented approximation with known limitations.
- `visual prototype`: interaction or rendering prototype not suitable for
  academic claims.

For BBH visual toys, the UI and documentation must state:

```text
Approximate visual model, not a solution of Einstein equations.
```

## Real-Time Shader Reference Boundary

Real-time GLSL/WebGL/Vulkan black-hole projects are useful engineering
references for shader interfaces, precomputed ray maps, debug toggles, and
frame-budget tradeoffs. They are not automatically physics references.

Use these sources as follows:

- citable papers with equations and tests may inform validation targets;
- code repositories may inform architecture only after their license and commit
  are recorded;
- blog or column articles are gray literature and must be summarized, not
  copied;
- Kerr-Newman, white-hole, other-universe, and stylized jet/disk modes are
  exploratory visuals until the project has independent validation for them.

## Required Vocabulary

The shadow / critical curve / lensing ring / photon ring distinction follows
`gralla2019shadowsPhotonRings`; the Kerr higher-order image scaling follows
`gralla2020lensingKerr` (see `references/references.bib`).

- `shadow`: screen region whose rays are captured by the horizon.
- `critical curve`: boundary on the observer screen separating capture and
  escape in the idealized limit.
- `lensing ring`: strongly lensed image structure near the critical curve.
- `photon ring`: contribution associated with rays that orbit near the photon
  region before reaching the observer.
- `direct image`: disk or source image with the lowest crossing/order.
- `secondary image`: next-order lensed image after additional bending.
- `higher-order image`: images with larger disk-crossing or winding order.
- `ISCO`: innermost stable circular orbit for the chosen Kerr spin.
- `disk inner edge`: model-dependent disk cutoff, initially set to `r_ISCO(a)`
  unless documented otherwise.

## XR Scope

Quest 3 is introduced first as a PCVR/MR viewer:

```text
PC GPU -> stereo textures -> Quest Link/Air Link -> head-pose feedback
```

MR is staged:

- MR-1: passthrough background plus virtual black-hole layer plus Depth API
  occlusion.
- MR-2: approximate environment-texture or room-mesh lensing.
- MR-3: true camera-frame lensing only when passthrough camera-frame access is
  available.
