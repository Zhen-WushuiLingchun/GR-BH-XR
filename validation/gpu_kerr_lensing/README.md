# GPU Kerr Lensing Validation

This directory documents the Task 4 WGPU Vulkan compute prototype. It is a
real-time-oriented f32 fixed-step RK4 implementation of the Phase 1
Boyer-Lindquist screen-ray model. The CPU DOP853 solver remains the scientific
reference.

## Commands

Use source-tree execution on Windows:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.check_backend
python -m gr_bh_xr.gpu.generate_lens_map --spin 0.5 --inclination-deg 60 --grid 256 --alpha-max 8 --beta-max 8 --out outputs/phase2/gpu_lensmap_kerr_a0.5_i60.h5
python -m gr_bh_xr.gpu.validate --spin 0 --inclination-deg 90 --grid 65 --alpha-max 8 --beta-max 8 --out outputs/phase2/gpu_compare_schwarzschild.h5
python -m gr_bh_xr.gpu.validate --spin 0.5 --inclination-deg 60 --grid 65 --alpha-max 8 --beta-max 8 --out outputs/phase2/gpu_compare_kerr_a0.5_i60.h5
python -m gr_bh_xr.gpu.preview --spin 0.5 --inclination-deg 60 --grid 256 --alpha-max 8 --beta-max 8
```

The preview is an interactive PC debug view of the texture contract intended
for later Unity/OpenXR integration. `--save-and-exit <path>` writes the same
HDF5 schema without opening a window.

## Tier 1 Latency Benchmark

Use this benchmark to separate static Tier 0 texture playback from Tier 1
near-real-time transfer-map updates. It measures `trace_lens_map` after a small
warmup run, including GPU dispatch, readback, escape-direction postprocessing,
event/debug texture assembly, disk-transfer buffer extraction, and optional
critical-band refinement. It excludes HDF5 writes and Unity texture upload.

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.benchmark_latency --spin 0.9 --inclination-deg 60 --grids 256 512 1024 --alpha-max 8 --beta-max 8 --r-obs 100 --step-size 0.05 --steps 8000 --out outputs/task5/gpu_trace_latency_kerr_a0.9_i60_raw.json
python -m gr_bh_xr.gpu.benchmark_latency --spin 0.9 --inclination-deg 60 --grids 256 512 1024 --alpha-max 8 --beta-max 8 --r-obs 100 --step-size 0.05 --steps 8000 --critical-refine-band 0.25 --critical-refine-factor 2 --out outputs/task5/gpu_trace_latency_kerr_a0.9_i60_refined.json
```

On 2026-07-07, the local NVIDIA GeForce RTX 5080 Laptop GPU produced these
warm-pipeline timings for Kerr `a = 0.9`, `i = 60 deg`, `r_obs = 100M`,
`h = 0.05`, and `8000` steps:

| grid | raw trace | refined trace (`band=0.25`, `2x2`) | refined pixels |
| ---: | ---: | ---: | ---: |
| 256x256 | 49.09 ms | 113.48 ms | 4,000 |
| 512x512 | 185.94 ms | 345.96 ms | 16,032 |
| 1024x1024 | 652.51 ms | 1,243.98 ms | 64,216 |

This is fast enough for slider-release or progressive parameter updates, and
possibly for coarse live preview at 256x256. It is not evidence for 72/90 Hz
per-frame geodesic integration. Quest Tier 0 still consumes cached textures;
Tier 1 must explicitly report update latency whenever spin, inclination,
observer, or screen-window controls trigger a new transfer map.

## Full-Sky Transfer Cubemap

The finite `alpha,beta` lens maps are local transfer patches. They are useful
for shadow validation and high-resolution central rendering, but they are not a
complete background-lensing model. A Unity shader that falls back from the edge
of `alpha,beta in [-8M, 8M]` to an unlensed skybox creates a square hard
boundary because the edge is still strongly deflected at `r_obs = 100M`.

Use `generate_transfer_cubemap` when the renderer needs a full camera sky:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.generate_transfer_cubemap --spin 0.9 --inclination-deg 60 --face-size 1024 --r-obs 100 --steps 8000 --out-dir outputs/task5/fullsky_kerr_a0.9_i60_1024
```

This traces one ray per Unity cubemap texel from the finite-radius static
observer tetrad and writes:

- `full_sky_transfer_metadata.json`;
- `event_cube_rgba8.bytes`;
- `escape_dir_unity_cube_rgba32f.bytes`.
- optional Task 6 disk-transfer cubemaps
  `disk_order0_transfer_cube_rgba16f.bytes` and
  `disk_order1_transfer_cube_rgba16f.bytes`.

The 2026-07-07 local RTX 5080 Laptop GPU run at `face-size = 1024` produced
`6291456` cubemap texels with `capture = 2023`, `escape = 6289433`, and
`invalid = 0`. The event cube was `25165824` bytes and the Unity escape-
direction cube was `100663296` bytes.

When the disk-transfer cubemaps are present, each order stores one raw
little-endian `RGBAHalf` cubemap with channels
`(r_m, sin(phi_m), cos(phi_m), g_m)`. A zero texel means there was no finite
annulus hit for that true equatorial crossing order. The order index is the
crossing order `m`, not the count of hits that survived the annulus filter.
This keeps the full-sky package compatible with the thin-disk shader path
without introducing a second finite `alpha,beta` window.

The first local disk-capable full-sky smoke/display package used
`face-size = 512`, Kerr `a = 0.9`, `i = 60 deg`, and `r_obs = 100M`:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.generate_transfer_cubemap --spin 0.9 --inclination-deg 60 --face-size 512 --r-obs 100 --steps 8000 --out-dir outputs/task6/fullsky_disk_kerr_a0.9_i60_512
```

It produced `1572864` cubemap texels with `capture = 510`, `escape = 1572354`,
`invalid = 0`, disk valid counts `[11826, 335]` for `m = 0, 1`, one
`25165824` byte escape-direction cube, and two `12582912` byte disk cubes.

The finite-observer tetrad path has its own CPU-vs-GPU gate because it does
not share the Bardeen screen initialization used by the local `alpha,beta`
validator:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.validate_full_sky_transfer --spin 0.9 --inclination-deg 60 --samples 4096 --r-obs 100 --out outputs/task5/fullsky_cpu_gpu_compare_kerr_a0.9_i60.json --h5 outputs/task5/fullsky_cpu_gpu_compare_kerr_a0.9_i60.h5
```

The 2026-07-07 local gate used the NVIDIA GeForce RTX 5080 Laptop GPU and
reported `capture = 2`, `escape = 4094`, `invalid = 0` on both CPU and GPU.
The full-grid event agreement was `1.0`; the stable event agreement was `1.0`
after excluding the two near-capture samples; GPU failures outside exclusions
were `0`. On the `4094` stable escaped samples, the median direction error was
`1.57e-6 rad`, RMS was `3.84e-5 rad`, and max was recorded as `1.60e-3 rad`.
The max error is audit metadata rather than the sole gate because it is most
sensitive near capture and cubemap face/sample boundaries.

## HDF5 Schema

Generated GPU maps use schema `gr-bh-xr.phase2.gpu_lens_map.v3`.

- axes: `alpha`, `beta`
- GPU buffers: `gpu_event_code`, `gpu_failure_code`, `gpu_min_r`,
  `gpu_h_max_abs`, `gpu_q_drift_abs`, `gpu_steps`,
  `gpu_refinement_level`, `gpu_subpixel_capture_fraction`, and
  `gpu_subpixel_invalid_fraction`
- escaped-ray momentum direction buffers: `gpu_escape_theta`,
  `gpu_escape_phi`, and `gpu_escape_dir_{x,y,z}`
- first two true equatorial crossing transfer layers:
  `gpu_disk_r_m`, `gpu_disk_phi_m`, `gpu_disk_sin_phi_m`,
  `gpu_disk_cos_phi_m`, `gpu_disk_t_m`, and `gpu_disk_g_m`
- texture buffers: `event_rgba8`, `debug_rgba8`
- comparison-only CPU buffers: `cpu_event_code`, `cpu_failure_code`,
  `cpu_min_r`, `cpu_escape_theta`, `cpu_escape_phi`, and
  `cpu_escape_dir_{x,y,z}`
- comparison masks: `stable_comparison_mask`,
  `full_grid_event_agreement_mask`, `excluded_critical_band`,
  `excluded_near_capture`
- continuous comparison buffer: `escape_direction_error_rad`
- metadata: backend, requested backend, adapter name, precision, RK method,
  step size, step count, metric parameters, screen bounds, observer radius,
  horizon epsilon, and generation command

Event codes match the Phase 1 lens-map schema:

```text
capture=0, escape=1, disk_crossing=2, invalid=3
```

Failure codes also match Phase 1:

```text
none=0, trace_exception=1, unclassified_max_lambda=2,
solver_failure=3, axis_coordinate_singularity=4,
polar_step_overshoot=5
```

## CPU-vs-GPU Gate

The validator excludes:

- CPU `failure_code != none`;
- pixels within `critical_band = 0.25 M` of the analytic shadow boundary;
- near-capture pixels with `cpu_min_r <= r_+ + max(0.1M, 2 horizon_eps)`.

The Task 4 acceptance target is stable-region event agreement of at least
`98%` and zero GPU failures outside those documented exclusions. On 2026-07-06
the local NVIDIA Vulkan adapter produced `100%` stable agreement for both
Schwarzschild and Kerr `a=0.5`, `i=60 deg` 65x65 validation runs, with matching
CPU/GPU capture fractions, full-grid event agreement of `100%`, and zero GPU
failures outside exclusions.

Escaped rays now carry an asymptotic sky direction map for background
lensing/cubemap lookup. The direction is computed from the endpoint momentum
`u^mu = g^{mu nu} p_nu` at the escape sphere, not from the finite-radius
position angle on that sphere. This avoids the `O(b / r_escape)` bias of using
escape-sphere position as a sky direction. The CPU-vs-GPU validator compares
the unit direction vectors on stable escaped pixels and records max/RMS/median
angular error in radians. On the reviewed Kerr `a=0.5`, `i=60 deg`, 65x65 case,
the direction comparison used 2746 escaped stable pixels with max error
`0.0029179 rad`, RMS `8.59e-5 rad`, and median `3.87e-6 rad`. The companion
Schwarzschild 65x65 case used 2722 escaped stable pixels with max error
`6.36e-4 rad`, RMS `3.33e-5 rad`, and median `3.74e-6 rad`.

The default GPU map generator and validator now supersample the analytic
critical-curve band with `critical_refine_band = 0.25 M` and
`critical_refine_factor = 2`. Center-sample event codes remain available for
CPU-vs-GPU comparison; the refinement data are stored separately as per-pixel
level and subpixel fractions.

## Limitations

The shader uses f32 arithmetic and fixed-step RK4. It is not expected to match
the CPU solver near the critical curve, near the Boyer-Lindquist horizon
cutoff, or at coordinate-axis singularities. The HDF5 buffers expose these
limits rather than hiding them. The v3 disk-crossing buffers are the first
geometric transfer hooks for Task 6 and do not alter the capture/escape event
gate. Full disk emissivity, observed intensity, optical depth, GRRT, adaptive
sampling, and headset runtime integration remain deferred.

The disk buffers are valid by buffer value, not by final event code alone. A
ray can cross the emitting annulus and later terminate at a Boyer-Lindquist
axis-coordinate failure; consumers should use finite `gpu_disk_r_m` / `g_m`
values to detect a valid disk sample and use `event_code` as a separate final
ray diagnostic.

## Disk-Transfer CPU-vs-GPU Gate

The disk validator uses matched CPU and GPU grids, screen bounds, observer
radius, disk annulus, and order count:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.validate_disk_transfer --spin 0 --inclination-deg 80 --grid 64 --alpha-max 30 --beta-max 30 --r-obs 100 --step-size 0.05 --steps 12000 --out outputs/task6/gpu_disk_compare_schwarzschild_64.h5
```

The first formal gate used a 64x64 even grid with the same physical bounds and
reported zero disk-validity mismatches, `max |Delta r_m| = 0.00362 M`,
`max |Delta g_m| = 2.31e-5`, `max phi_m error = 1.05e-5 rad`, and
`max |Delta t_m| = 0.00376`. This satisfies the thresholds listed in
`docs/validation_targets.md`. A smaller 16x16 smoke run is kept in tests for
runtime cost.

Both CPU and GPU crossing detectors currently use sign changes through the
equatorial plane. A measure-zero tangent crossing at a theta turning point on
the disk plane can be missed by both paths and is not part of the current
acceptance set.

The default-step interactive preview is validated for ordinary Kerr inspection,
not for every screen coordinate chart limit. Its documented f32 operating
envelope is approximately `20 deg <= i <= 160 deg` and `|a| <= 0.95`. Outside
that envelope the preview title adds a warning but does not clamp parameters or
hide bad pixels. This is intentional: the event/debug textures should show the
prototype's numerical failure modes honestly.

A non-gating near-polar stress case was reproduced at Kerr `a = 0.95`,
`i = 5 deg`, `grid = 256`, and the default preview step budget. It produced
three expected artifact classes: 99 red `solver_failure` pixels on the shadow
edge (`min_r ~= 1.6M` to `3.7M`), 53 magenta `polar_step_overshoot` pixels, and
a near-critical black/blue misclassification band where CPU arbitration of a
small ring sample found 2/40 event mismatches. The same `a = 0.95` spin at
`i = 60 deg` produced only 4 invalid pixels, so this is a near-polar
Boyer-Lindquist/f32 fixed-step boundary. The causes are the Bardeen screen map
degenerating as `1 / sin(theta_obs)`, the polar-axis `1 / sin(theta)^2`
coordinate terms, and fixed-step f32 growth on multi-winding near-critical
rays. Smaller steps, such as `h = 0.025` with `16000` steps, can reduce the
visible artifacts but are not a coordinate-level fix; a future Kerr-Schild or
axis-regular tracer is the physical route for stronger near-polar claims.

The default GPU affine-parameter budget is `steps * step_size = 8000 * 0.05 =
400`, while the CPU validation reference uses `max_lambda = 1200`. On the
reviewed 65x65 validation cases this did not hide any event disagreement, but
near-polar winding rays can reach the GPU budget first on finer grids.

For the documented 256x256 Kerr example, the even grid has no exact
`alpha = 0` column. A post-implementation review found 25 `solver_failure`
pixels at `|alpha| ~= 0.0314` with `min_r` between roughly `2.2M` and `4.0M`,
plus 4 nearby `unclassified_max_lambda` pixels. These were small-`|L_z|`
near-polar fixed-step artifacts: f32 RK4 with `h = 0.05` could step over the
narrow centrifugal barrier near the Boyer-Lindquist polar axis. The follow-up
shader adds near-polar substepping and a reserved `polar_step_overshoot` code.
On the reviewed 256x256 Kerr case this reduced `solver_failure`,
`unclassified_max_lambda`, and invalid counts to zero while refining 4096
critical-band pixels after cKDTree acceleration of the critical-band mask.
Future GPU work may still use the new code if more
extreme parameters expose a polar overshoot.

Observed f32 residual scale on the accepted 65x65 validation cases is
diagnostic rather than pass/fail: escape-region `|H|` is around `2.4e-6`
median, `1e-4` at p99, and a few `1e-3` worst samples; Carter-Q drift can reach
the `1e-1` scale. CPU DOP853 remains the Hamiltonian accuracy reference.

## Preview Controls

- `A/Z`: decrease/increase spin.
- `I/K`: decrease/increase inclination.
- `+/-`: widen/narrow the screen half-widths.
- `D`: cycle event, minimum radius, Hamiltonian residual, and Carter-Q drift
  views.
- `S`: save the current HDF5 snapshot under `outputs/phase2/`.
- `Esc`: exit.
