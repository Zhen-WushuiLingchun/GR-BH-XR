# NPGS Native Build And Performance Baseline

Status: **build/performance baseline and the quality-2 `Q_charge=0` Kerr slice
passed; Kerr-Newman, polarization, disk parity, and native XR remain open**.

## Source Boundary

- Official repository: https://github.com/baopinshui/NPGS
- Reviewed official SHA:
  `a039e6417b28d53cbd413ee8f6d64543e755aa3e`
- Integration fork:
  https://github.com/Zhen-WushuiLingchun/NPGS
- Current audited fork SHA:
  `20acb4a0c25d1b6899625d9ceda6d8e97b93a906`
- Submodule path: `runtime/NPGS`

The 2026-08-06 refresh fetched complete, non-shallow histories from the fork
and official upstream. `git fsck --full --strict` passed. Public GitHub refs
contained only `master`, tag/prerelease `v-114514-test` at the reviewed SHA,
and closed draft PR #1 for Windows CI. No public BBH/GW source was present.

The checked-in upstream source could not reproduce startup unchanged because
current pipeline names referred to SPIR-V assets absent from the repository and
missing stages reached an unsafe container access. The fork baseline therefore
contains only dependency/build wiring, generated validated shader assets,
fail-closed startup handling, deterministic launch controls, and benchmark
instrumentation. It is not an unmodified-upstream timing claim.

## Reproduction

```powershell
.\tools\npgs\bootstrap.ps1 -BootstrapVcpkg
.\tools\npgs\doctor.ps1 -JsonOut outputs\npgs\doctor.json
.\tools\npgs\build.ps1 -Configuration Release

.\tools\npgs\benchmark.ps1 `
  -Width 1920 -Height 1080 `
  -WarmupSeconds 12 -SampleSeconds 10 `
  -JsonOut outputs\npgs\baseline_1920x1080.json

.\tools\npgs\benchmark.ps1 `
  -Width 3840 -Height 2160 `
  -WarmupSeconds 12 -SampleSeconds 10 `
  -JsonOut outputs\npgs\baseline_3840x2160.json
```

The benchmark executable emits its actual
`NPGS_BENCHMARK_FRAMEBUFFER width height` before creating the Vulkan
swapchain. The harness rejects any mismatch. This prevents Windows DPI
virtualization or work-area clamping from masquerading as a requested
resolution.

## Measured Zero Point

Machine:

- GPU: NVIDIA GeForce RTX 5080 Laptop GPU
- driver: 591.74
- backend: native Vulkan
- launch: hidden borderless window, VSync disabled
- path: upstream visual prepass/composite/TAA
- excluded: audit pass, GPU readback, OpenXR, MR, and CPU validation

| Framebuffer | FPS samples | Median | Mean | Range | Median ms | P95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1920 x 1080 | 199, 198, 199, 201, 200, 200, 201, 201, 203, 211 | 200 | 201.3 | 198-211 | 4.97 | 5.05 |
| 3840 x 2160 | 93, 75, 77, 76, 84, 76, 76, 80, 85, 75 | 76 | 79.7 | 75-93 | 12.99 | 13.33 |

The provisional desktop 4K/60 visual target passes. These values are a
same-machine zero point for the fork before audit extraction. They do not prove
that NPGS's Kerr/Kerr-Newman geodesics, polarization, disk, maximal extension,
or observer models agree with GR-BH-XR references.

After exact-state raw v2 instrumentation and exact Kerr geometry through the
finite escape boundary, the same fast path measured 189 median FPS at 1080p
and 71 at exact 4K. Against the same-machine pre-audit 183/69 comparison this
does not regress, so the five-percent performance gate remains closed.

## Q=0 Kerr Replay

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_npgs_kerr `
  --raw outputs/npgs/audit_kerr_a09_i60_33_q2_stable_carter_axis.bin `
  --samples 257 --critical-band-pixels 1 `
  --out outputs/npgs/npgs_kerr_accepted_a09_i60_q2.json `
  --h5 outputs/npgs/npgs_kerr_accepted_a09_i60_q2.h5
```

The raw-v2 capture contains 48 little-endian float32 fields / 192 bytes per
pixel, including exact initial/final ingoing KS canonical states. At
`a/M=0.9`, `Q=0`, `i=60 deg`, `r_obs=100M`, quality 2, 33x33:

- events: `104 capture / 985 escape / 0 invalid`;
- stable and all-resolved CPU f64 event agreement: `1.0`;
- escaped-direction median/RMS/max: `1.39e-5 / 2.77e-5 / 9.51e-5 rad`;
- endpoint max drift: `E=0`, `L_z=6.71e-4`, `Q=1.02e-3`;
- escaped endpoint `abs(H)` max: `1.90e-7`.

Quality 2 is the minimum audit/scientific mode. Quality 1 is retained as the
visual fast path. Captured endpoint H is recorded but not accepted as an
independent residual because f32 covector components become cancellation-
conditioned at the horizon. Stepwise and endpoint Carter diagnostics are also
kept separate; the former has one `0.099` transient while the latter remains
at most `1.02e-3` over the full grid.

## Remaining Gates

1. Independent Kerr-Newman and Walker-Penrose validation.
2. NPGS disk-transfer parity with the accepted GR-BH-XR schema.
3. Native OpenXR stereo and Quest PCVR frame-time validation.

Generated JSON, logs, and screenshots remain under ignored `outputs/npgs/`.
