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

## HDF5 Schema

Generated GPU maps use schema `gr-bh-xr.phase2.gpu_lens_map.v1`.

- axes: `alpha`, `beta`
- GPU buffers: `gpu_event_code`, `gpu_failure_code`, `gpu_min_r`,
  `gpu_h_max_abs`, `gpu_q_drift_abs`, `gpu_steps`
- texture buffers: `event_rgba8`, `debug_rgba8`
- comparison-only CPU buffers: `cpu_event_code`, `cpu_failure_code`,
  `cpu_min_r`
- comparison masks: `stable_comparison_mask`,
  `full_grid_event_agreement_mask`, `excluded_critical_band`,
  `excluded_near_capture`
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
solver_failure=3, axis_coordinate_singularity=4
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

## Limitations

The shader uses f32 arithmetic and fixed-step RK4. It is not expected to match
the CPU solver near the critical curve, near the Boyer-Lindquist horizon
cutoff, or at coordinate-axis singularities. The HDF5 buffers expose these
limits rather than hiding them. Thin-disk transfer, redshift, time delay,
GRRT, adaptive sampling, and headset runtime integration are deferred.

The default GPU affine-parameter budget is `steps * step_size = 8000 * 0.05 =
400`, while the CPU validation reference uses `max_lambda = 1200`. On the
reviewed 65x65 validation cases this did not hide any event disagreement, but
near-polar winding rays can reach the GPU budget first on finer grids.

For the documented 256x256 Kerr example, the even grid has no exact
`alpha = 0` column. A post-implementation review found 25 `solver_failure`
pixels at `|alpha| ~= 0.0314` with `min_r` between roughly `2.2M` and `4.0M`,
plus 4 nearby `unclassified_max_lambda` pixels. These are small-`|L_z|`
near-polar fixed-step artifacts: f32 RK4 with `h = 0.05` can step over the
narrow centrifugal barrier near the Boyer-Lindquist polar axis. They are not a
new physical failure of Kerr lensing, and CPU DOP853 handles the same class
with adaptive steps. Future GPU work should give this case an explicit failure
code such as `polar_step_overshoot`, reduce/subdivide steps near the pole, or
add adaptive refinement.

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
