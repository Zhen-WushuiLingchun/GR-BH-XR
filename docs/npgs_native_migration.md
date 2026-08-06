# Native NPGS Migration

Updated: 2026-08-06

## Decision

The future interactive runtime is a native C++/Vulkan fork of NPGS. NPGS is not
copied into the Unity package. GR-BH-XR remains the orchestration, scientific
reference, validation, and documentation repository; the fork is pinned as the
`runtime/NPGS` submodule.

The reviewed public upstream snapshot is
`a039e6417b28d53cbd413ee8f6d64543e755aa3e`. On 2026-08-06, a fresh
`git ls-remote`, GitHub branch query, tag query, and release query found:

- `master` at that SHA;
- tag and prerelease `v-114514-test` at the same SHA;
- one closed draft PR, `#1 Add Windows cloud build`, containing CI and one
  dependency-manifest edit but no newer renderer or physics implementation;
- no other public branch and no public BBH/GW implementation.

The local submodule was converted from a shallow checkout to a complete
history, fetched from both the fork and official upstream, and passed
`git fsck --full --strict`. The integration branch explicitly merged
`upstream/master` (already up to date). Showcase media is therefore not an
implementation input.

## Repository Topology

```text
baopinshui/NPGS master
        |
        +-- Zhen-WushuiLingchun/NPGS codex/npgs-integration
                    |
                    +-- GR-BH-XR runtime/NPGS (pinned commit)

GR-BH-XR/src + tests + validation
        = independent CPU/GPU truth and audit consumers
```

Upstream synchronization uses explicit merge commits into the fork integration
branch. The submodule pointer moves only after the new fork commit passes its
documented build, physics, and performance gates. History is never squashed.

The first pinned integration baseline is
`Zhen-WushuiLingchun/NPGS@d39c7d78d34273c683bf558fdff3364b5a547d28`.
Its four commits after upstream are deliberately limited to reproducible vcpkg
integration, fail-closed shader asset/startup repair, deterministic launch
controls, and exact-framebuffer benchmark instrumentation. The active
Kerr-Newman common shader was not replaced by GR-BH-XR physics code. This is a
build/performance baseline, not a successful physics-replacement gate.

The repository lives under a path containing Chinese characters. The current
vcpkg/CMake tool acquisition path is not Unicode-safe, so the bootstrap creates
`%LOCALAPPDATA%\GRBHXR\native-build-root`, an ASCII junction to the same checkout,
and all native build paths go through that alias. It is not a second source
copy and is never committed.

## What Is Reused

- NPGS native Vulkan renderer, prepass/composite/TAA architecture, observer
  controls, Kerr-Newman candidate kernel, maximal-extension visualization, and
  polarization candidate path.
- GR-BH-XR CPU f64 Boyer-Lindquist/Kerr-Schild solvers, WGPU comparison tools,
  audit schemas, Page-Thorne/blackbody disk model, time-delay/image-order data,
  XR behavior requirements, and evidence boundaries.

NPGS's jet, heat-haze, inner-horizon, antiverse, and polarization outputs remain
visual or exploratory until the corresponding independent gates exist. The
stationary Kerr-Newman maximal extension is a mathematical spacetime model, not
a claim about a perturbed astrophysical Cauchy horizon.

## Reproducible Native Baseline

The clean upstream source snapshot did not start reproducibly from the checked
in project: current pipeline names required SPIR-V assets absent from the
repository, and missing shader stages reached an unsafe `.front()` path. The
fork therefore first restored generated shader assets, validated them with
`spirv-val`, and made missing assets fail closed. The recorded zero point is the
minimum repaired integration fork, not an unmodified-upstream performance
claim.

Commands:

```powershell
.\tools\npgs\bootstrap.ps1 -BootstrapVcpkg
.\tools\npgs\doctor.ps1
.\tools\npgs\build.ps1 -Configuration Release
.\tools\npgs\benchmark.ps1 -Width 1920 -Height 1080
.\tools\npgs\benchmark.ps1 -Width 3840 -Height 2160
```

The benchmark mode creates a hidden, borderless, no-VSync Vulkan surface and
reads the actual framebuffer extent from NPGS itself. A mismatch between
requested and actual dimensions fails the run. On the local RTX 5080 Laptop GPU
(driver 591.74), fork `d39c7d7`, 12-second warmup and ten one-second samples:

| Framebuffer | Median FPS | Mean FPS | Range | Median frame time |
| --- | ---: | ---: | ---: | ---: |
| 1920 x 1080 | 200 | 201.3 | 198-211 | 4.97 ms |
| 3840 x 2160 | 76 | 79.7 | 75-93 | 12.99 ms |

This measures the upstream visual prepass/composite/TAA path with no audit pass
or readback. It closes the clean-build and same-hardware visual zero-point gate
and meets the provisional desktop 4K/60 target. It does not establish the
future audit-path regression limit, Kerr correctness, OpenXR performance, or
Quest acceptance. Full evidence and commands are in
`validation/npgs_native_baseline/README.md`.

## Migration Gates

1. Reproduce the unmodified NPGS desktop build and record same-machine timing.
2. Add a separate audit output path without slowing the default fast path by
   more than five percent.
3. Set charge to zero and pass the existing Kerr CPU-reference gates.
4. Add an independent CPU Kerr-Newman reference before accepting nonzero charge.
5. Add native OpenXR/Vulkan rendering and pass desktop plus Quest PCVR gates.
6. Only then archive the Unity frontend outside the default branch.

## Licensing Boundary

The native NPGS fork and combined source distribution use GPL version 3. The
legacy Unity frontend remains source-only during migration and is not linked
with NPGS or distributed as a combined executable. This note records the chosen
project policy; it is not legal advice.
