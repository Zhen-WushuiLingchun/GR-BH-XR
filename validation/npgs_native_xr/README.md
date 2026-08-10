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
