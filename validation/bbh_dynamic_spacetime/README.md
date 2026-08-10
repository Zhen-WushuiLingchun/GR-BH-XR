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
