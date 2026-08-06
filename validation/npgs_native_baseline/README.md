# NPGS Native Build And Performance Baseline

Status: **build/performance baseline passed; physics replacement not yet
accepted**.

## Source Boundary

- Official repository: https://github.com/baopinshui/NPGS
- Reviewed official SHA:
  `a039e6417b28d53cbd413ee8f6d64543e755aa3e`
- Integration fork:
  https://github.com/Zhen-WushuiLingchun/NPGS
- Measured fork SHA:
  `d39c7d78d34273c683bf558fdff3364b5a547d28`
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

## Remaining Gates

1. Shared visual/audit GLSL core and schema `gr-bh-xr.npgs.audit.v1`.
2. `Q_charge = 0` comparison with the independent Kerr CPU f64 reference.
3. Independent Kerr-Newman and Walker-Penrose validation.
4. Fast-path regression at or below five percent after audit integration.
5. Native OpenXR stereo and Quest PCVR frame-time validation.

Generated JSON, logs, and screenshots remain under ignored `outputs/npgs/`.
