# Native NPGS Migration

Updated: 2026-08-10

## Decision

The future interactive runtime is a native C++/Vulkan fork of NPGS. NPGS is not
copied into the Unity package. GR-BH-XR remains the orchestration, scientific
reference, validation, and documentation repository; the fork is pinned as the
`runtime/NPGS` submodule.

The reviewed public upstream snapshot is
`a039e6417b28d53cbd413ee8f6d64543e755aa3e`. On 2026-08-10, a fresh
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

The first pinned integration baseline was
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

The current pinned fork revision is
`Zhen-WushuiLingchun/NPGS@6c9a3aaf76ccc52b8c67e25d4eb7141bea06502d`.
It adds device-independent native OpenXR/Vulkan and MR input contracts while
leaving the existing GLFW desktop lifecycle unchanged.

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

## Integration Contract And MR Repair

`gr-bh-xr.npgs.integration.v1` is the centralized compatibility matrix. Native
audit conversion now fails closed on coordinate/mass drift and writes only the
features supported by both native metadata and independent gates. It prevents
accepted Kerr/Kerr-Newman geometry from silently legitimizing Stokes transport,
charged-disk matter, maximal-extension astrophysics, OpenXR, MR, or BBH/GW.

The native fork exposes separate desktop and OpenXR render sinks. An OpenXR
sink requires OpenXR-owned Vulkan handles, exactly two ordered views,
asymmetric per-eye FOV tangents, per-eye poses, and a positive
`meters_per_M`. Extension enumeration is injected through an OpenXR function
table so the normal desktop executable does not accidentally own or initialize
an XR lifecycle.

The passthrough repair is definition-level rather than a fallback-texture hack.
`gr-bh-xr.npgs.mr-frame.v1` and the matching C++ contract require a fresh frame,
monotonic sequence, capture/receive timestamps, native image, calibrated
intrinsics, rigid capture pose, color encoding, and measured radiance coverage.
Environment depth is optional and independently validated. A forward camera,
even when combined with a cached room map, can support only a
`forward_camera_only` claim; only an explicitly calibrated full-sphere source
can claim full-sphere radiance. No real camera frame or depth registration has
yet passed this contract on a device.

This is compatible with the existing accepted NPGS physics because the
measurement contract supplies initial view rays and background radiance; it
does not replace the shared Kerr/Kerr-Newman geodesic core. GR-BH-XR retains
the CPU f64 oracle, Page-Thorne/LUT emission model, HDF5 audit format, and
fail-closed claim policy.

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

## Native Audit Transport

Fork commit `6631537fdbb9b23a89c5268065ae6a2405a4db7a` added an opt-in
offscreen audit capture without changing the normal visual SPIR-V. Both the
visual and audit fragment shaders call the same `TraceRay` implementation. The
native process originally wrote one 128-byte little-endian float32 record per
pixel. Fork commit `20acb4a0c25d1b6899625d9ceda6d8e97b93a906` advances the raw
transport to v2: 48 float32 fields / 192 bytes per pixel, adding exact initial
and final ingoing Cartesian Kerr-Schild positions and covariant momenta. The
Python converter remains backward-compatible with raw v1 and writes both to
final schema `gr-bh-xr.npgs.audit.v1`.

The converter fails closed on a mismatched schema or byte length, non-finite
records, unknown or non-integral event/failure codes, inconsistent escape flags,
non-unit escaped directions, or a disagreement between the binary and native
summary. It preserves the raw 32-field record in HDF5 and writes normalized
`M=1` datasets. NPGS native distance/time values are divided by
`M_internal=0.5`; dimensionless Hamiltonian, correction, redshift, direction,
and conserved-quantity fields are not rescaled. Reserved disk slots become NaN
unless their explicit validity flag is set.

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.npgs_audit `
  --raw outputs/npgs/audit_kerr_a09_i60_33.bin `
  --out-h5 outputs/npgs/audit_kerr_a09_i60_33.h5 `
  --out-json outputs/npgs/audit_kerr_a09_i60_33.json `
  --npgs-root runtime/NPGS
```

The final artifact records official-upstream, fork, and compiled-audit-shader
revisions together with adapter/driver and every physical launch parameter.
This is a transport and provenance gate only; accepting Kerr physics still
requires the independent CPU-f64 comparison below.

## Q=0 Kerr Cross-Check

The first physics replacement slice passes for native quality 2. The native
canonical contract is `(x,y,z,t)` with spin `+y` and negative affine marching.
The CPU reference rotates spatial components as
`(x,y,z)_N -> (x,-z,y)_P`, reorders to `(t,x,y,z)`, and negates the full
covector to replay the same null ray with positive affine parameter. BL f64 is
used for exterior event classification, while ingoing Cartesian KS f64 is used
for escaped-ray direction so the angular comparison stays in one regular chart.

Command:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_npgs_kerr `
  --raw outputs/npgs/audit_kerr_a09_i60_33_q2_stable_carter_axis.bin `
  --samples 257 --critical-band-pixels 1 `
  --out outputs/npgs/npgs_kerr_accepted_a09_i60_q2.json `
  --h5 outputs/npgs/npgs_kerr_accepted_a09_i60_q2.h5
```

At `a/M=0.9`, `Q=0`, `i=60 deg`, `r_obs=100M`, 33x33, the native result is
`104 capture / 985 escape / 0 invalid`. Stable and all-resolved event agreement
are `1.0`. Escaped-direction median/RMS/max errors are
`1.39e-5 / 2.77e-5 / 9.51e-5 rad`, below the `1e-4 / 5e-4` acceptance limits.
Quality 1 remains a visual fast mode; quality 2 is the minimum scientific/audit
mode because quality-1 same-chart direction errors exceed the RMS target.

Raw-v2 endpoint states also expose independent `E`, `L_z`, and angular-form
Carter `Q` drift. The full-grid maxima are `0`, `6.71e-4`, and `1.02e-3`,
respectively. Escaped endpoint `abs(H)` is at most `1.90e-7`. Captured endpoint
covectors can reach `O(1e4)` at the horizon, so re-evaluating H from serialized
f32 components is cancellation-conditioned and is recorded but not gated. The
native per-step Carter maximum includes one transient `0.099` spike; endpoint
drift for that ray remains `O(1e-4)`, so both diagnostics are retained with
distinct labels rather than hiding or pooling them.

The exact-geometry visual fast path at fork `20acb4a` measured 189 median FPS at
1080p and 71 at exact 4K on the same RTX 5080 Laptop configuration, compared
with the pre-audit 183/69 FPS run. The five-percent regression gate therefore
passes.

## Nonzero-Charge Kerr-Newman Cross-Check

The native runtime is used directly; the Python implementation is a small f64
oracle that replays the exact raw-v2 launch states. It follows the
Kerr-Newman metric of `li2026kerrNewmanPolarizedTransfer`, with

```text
Delta = r^2 - 2 M r + a^2 + Q^2
H_KS = (M r^3 - Q^2 r^2 / 2) / (r^4 + a^2 z^2)
```

and validates neutral null geodesics only. Unit gates require the `Q -> 0`
Kerr limit, the `a -> 0` Reissner-Nordstrom limit, the analytic horizons,
`det(g_KS)=-1`, BL/KS tensor equivalence, analytic metric derivatives, and
conserved `E`, `L_z`, and Carter `Q`.

Native commands produced two quality-2 raw-v2 captures at `r_obs=100M`,
`i=60 deg`, 33x33:

- generic KN: `a/M=0.6`, `Q/M=0.5`, `101 capture / 988 escape / 0 invalid`;
- RN limit: `a=0`, `Q/M=0.6`, `97 capture / 992 escape / 0 invalid`.

The deterministic f64 replay measured:

| Case | Samples | Stable event agreement | Direction median | Direction RMS | Native/CPU stable failures |
| --- | ---: | ---: | ---: | ---: | ---: |
| KN `a/M=0.6, Q/M=0.5` | 257 | 1.0 | `1.43e-5 rad` | `2.99e-5 rad` | 0 / 0 |
| RN `a=0, Q/M=0.6` | 129 | 1.0 | `1.62e-5 rad` | `4.07e-5 rad` | 0 / 0 |

Past-directed camera rays serialized in the ingoing chart become
cancellation-conditioned as they approach the future horizon. The CPU gate
therefore classifies capture at `r_+ + 0.02M`; capture `H` is retained but is
not presented as horizon-penetration evidence. Escaped-ray direction and
residuals remain regular and are the continuous-quantity gate.

Commands and full interpretation are in
`validation/npgs_kerr_newman/README.md`. This closes only neutral,
sub-extremal, exterior Kerr-Newman ray geometry. It does not validate charged
particles, Walker-Penrose polarization, disk/jet emission, Cauchy-horizon
continuation, or maximal extension.

## Native Kerr Disk Transfer

NPGS now records the first two true equatorial crossings from the same shared
`TraceRay` invocation used by its visual path. The native runtime remains the
implementation; Python f64 only replays a deterministic subset of the exact
serialized launch states.

For `a/M=0.9`, `Q=0`, `i=60 deg`, `r_obs=100M`, quality 2, 65x65, the native
capture produced `60 capture / 4165 escape / 0 invalid` and disk-valid counts
`[1439,41]`. A 318-ray replay, including all `m=1` slots, found zero
crossing-presence, validity, flag, or order mismatches. Maximum errors were
`0.0199722M` for `r_m`, `3.4780e-4 rad` for `phi_m`, `0.0207713M` for
`Delta t_m`, and `2.0221e-4` for `g_m`, all within preregistered limits.

The gate corrected one genuine definition error. `E` and spin-axis `L` are
Killing invariants and must come from the exact initial canonical state.
Computing `L` from separately interpolated crossing position and momentum does
not preserve the bilinear invariant and biased inner-disk redshift. No
tolerance was relaxed.

The native `g_m` is `nu_observer_local/nu_emitter`, with local camera launch
frequency normalized to one. It is intentionally not the asymptotic-observer
helper. See `validation/npgs_disk_transfer/README.md` for commands, the
Unicode-safe capture wrapper, thresholds, and the single-chart CPU
horizon-guard boundary.

## Migration Gates

1. Reproduce the unmodified NPGS desktop build and record same-machine timing.
2. Add a separate audit output path without slowing the default fast path by
   more than five percent.
3. Set charge to zero and pass the existing Kerr CPU-reference gates. **Passed
   at native quality 2 on 2026-08-06.**
4. Add an independent CPU Kerr-Newman reference before accepting nonzero charge.
   **Neutral exterior ray geometry passed on 2026-08-06; polarization and
   maximal extension remain open.**
5. Validate native disk semantics before consuming them in the replacement
   runtime. **Kerr `Q=0` first/second crossings passed on 2026-08-06; charged
   disk and Page-Thorne emission remain open.**
6. Add native OpenXR/Vulkan rendering and pass desktop plus Quest PCVR gates.
   **The ownership/stereo/MR-input interface and Release-build gate passed on
   2026-08-10; session creation, swapchain submission, and device evidence
   remain open.**
7. Only then archive the Unity frontend outside the default branch.

## Licensing Boundary

The native NPGS fork and combined source distribution use GPL version 3. The
legacy Unity frontend remains source-only during migration and is not linked
with NPGS or distributed as a combined executable. This note records the chosen
project policy; it is not legal advice.
