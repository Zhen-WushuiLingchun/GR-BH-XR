# NPGS OpenXR And MR Contract Source Note

Date: 2026-08-10

## Sources Reviewed

- NPGS public repository: https://github.com/baopinshui/NPGS
- Reviewed upstream commit:
  `a039e6417b28d53cbd413ee8f6d64543e755aa3e`
- Reviewed fork commit:
  `6c9a3aaf76ccc52b8c67e25d4eb7141bea06502d`
- OpenXR 1.1 specification:
  https://registry.khronos.org/OpenXR/specs/1.1/html/xrspec.html
- `XR_KHR_vulkan_enable2` reference:
  https://registry.khronos.org/OpenXR/specs/1.1/man/html/XR_KHR_vulkan_enable2.html

Search terms: `NPGS OpenXR Vulkan enable2 stereo swapchain passthrough camera
intrinsics environment depth`.

The complete public NPGS ref set was refreshed before this work. Official
`master`, `v-114514-test`, and the published prerelease still resolve to the
same upstream commit. No public BBH/GW implementation was found.

## Technical Conclusions

1. The existing GLFW desktop lifecycle must remain distinct from OpenXR.
   `XR_KHR_vulkan_enable2` is the native ownership route for XR Vulkan
   requirements and device creation.
2. XR ray generation needs each eye's pose and asymmetric FOV. A symmetric
   desktop FOV plus a duplicated camera is not a valid stereo substitute.
3. Tracked-space translation requires an explicit `meters_per_M`; otherwise
   stereo scale and observer motion can be silently exaggerated.
4. Passthrough-pixel lensing requires a delivered camera frame, calibrated
   intrinsics, capture pose, timestamps, native image, and color encoding.
   Extension enumeration or depth acquisition alone proves none of these.
5. A forward camera cannot measure radiance behind the observer. Cached room
   radiance is a static approximation, not live full-sphere coverage.

## Project Use And Claim Boundary

The fork implements device-independent render-input and MR-frame contracts.
The GR-BH-XR Python side serializes the same feature/measurement boundaries and
rejects metadata that overclaims blocked physics or runtime capabilities.

This source review supports an interface gate only. A working OpenXR session,
stereo swapchain submission, delivered Quest camera frame, RGB/depth
registration, and headset timing remain future device evidence.
