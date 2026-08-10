# Native NPGS XR And MR Interface Gate

Status: interface passed on 2026-08-10; runtime/device gate open.

## Scope

This gate validates the source-level boundary between the accepted NPGS native
renderer and future OpenXR/MR backends. It does not claim a working headset
session, stereo presentation, camera delivery, or depth registration.

The reviewed fork revision is
`Zhen-WushuiLingchun/NPGS@6c9a3aaf76ccc52b8c67e25d4eb7141bea06502d`.
The public upstream was refreshed on 2026-08-10 and remained at
`baopinshui/NPGS@a039e6417b28d53cbd413ee8f6d64543e755aa3e`.

## Interface Evidence

- `XR_KHR_vulkan_enable2` is declared as the OpenXR Vulkan ownership path.
- Desktop GLFW and OpenXR are distinct render sinks.
- OpenXR rejects NPGS-owned Vulkan handles.
- Stereo input is exactly two ordered views with asymmetric FOV, rigid poses,
  recommended extents, and positive `meters_per_M`.
- OpenXR extension probing uses an injected loader function table and cannot
  silently create an XR lifecycle in the desktop executable.
- MR color input requires freshness, calibration, sequence/timestamps, native
  image, intrinsics, rigid capture pose, color encoding, and measured coverage.
- Environment depth is independently optional; it cannot certify RGB.
- Forward-camera and cached-room inputs cannot claim live full-sphere radiance.

The same definitions are serialized by:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.npgs_contract `
  --out outputs/npgs/integration_manifest.json
```

## Reproduction

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_npgs_contract.py `
  tests/test_npgs_audit.py `
  tests/test_npgs_integration_contract.py

.\tools\npgs\build.ps1 -Configuration Release
git diff --check
```

The 2026-08-10 Release build completed with zero errors. A 640x480 desktop
smoke run preserved the existing GLFW renderer. These checks prove that the
new contract compiles without replacing the desktop lifecycle; they are not
OpenXR performance evidence.

The focused contract/audit suite passed `31` tests, and the complete repository
suite passed `271` tests in `153.07 s`.

## Device Gate Still Required

Acceptance remains closed until a later device run records all of:

1. OpenXR instance/session and `XR_KHR_vulkan_enable2` device creation;
2. acquire/wait/render/release for both stereo swapchain views;
3. predicted poses, world-lock, controller input, and frame timing;
4. a fresh calibrated camera frame satisfying
   `gr-bh-xr.npgs.mr-frame.v1`;
5. explicit coverage classification and, when used, independently registered
   environment depth.

Fallback imagery or a compositor passthrough underlay remains a display mode,
not proof that live camera radiance has been bent by the geodesic renderer.

## Dynamic BBH Time And Camera-History Contract

The pre-device Task 9 contract extends each stereo frame with an explicit map
from OpenXR predicted-display time to metric time and binary phase. Physical GW
signal and `visual_gain` are stored separately. Each view retains its own
predicted pose and eye origin; equal left/right origins fail validation.

MR source selection is causal. A bounded camera history selects the newest
calibrated frame captured no later than `observer_time - Delta t_ray`; a current
frame cannot satisfy a delayed ray. Stale history, absent rear/side coverage,
unknown color encoding, duplicate sequence provenance, and missing depth
registration all fail closed. Finite room radiance additionally requires an
explicit scene hit tied to the selected source-frame sequence.

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_npgs_contract.py `
  tests/test_npgs_bbh_mr_contract.py

.\tools\npgs\build.ps1 -Configuration Release -SkipDependencyInstall
```

The 2026-08-10 focused Python contract suite passed `22` tests and the native
Release build completed with zero errors. These are interface and causality
gates only. Fresh RGB delivery, registered depth, world lock, stereo display,
and total-frame 72/90 Hz still require an OpenXR device run.
