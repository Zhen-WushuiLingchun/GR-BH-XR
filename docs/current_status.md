# Current Implementation Status

Updated: 2026-08-06

This file is the canonical status summary. Dated plans describe the intent at
the time they were written; `docs/development_log.md` records chronological
evidence. Neither should be used alone to infer the current runtime.

## Accepted Physics And Runtime Paths

| Path | Current role | Claim boundary |
| --- | --- | --- |
| CPU f64 Boyer-Lindquist and Kerr-Schild solvers | Scientific reference | Validated null geodesics, conserved quantities, critical curves, disk crossings, redshift, time delay, finite observers, and horizon-penetrating Kerr tests. |
| Python WGPU/Vulkan f32 solvers | GPU comparison and asset generation | Audited against CPU f64. Fixed-step and photon-shell precision limits remain recorded in the validation notes. |
| Unity baked transfer playback | Deterministic Quest fallback | Real-time lookup of an offline transfer map. It is not runtime geodesic integration and is valid only for its baked metric and observer. |
| Unity Task 9 live tracer | Live single-Kerr integration | Cartesian Kerr-Schild rays are integrated in Unity compute in bounded batches. A completed map is hard-swapped after several display frames; this is not a newly converged full-resolution per-eye solution every headset frame. |
| Unity Tasks 7-8 roam/descent | Worldline-keyframe playback | Uses audited finite-observer and rain-frame keyframes. Playback is distinct from unrestricted six-degree-of-freedom tracing. |
| Unity Task 10 MR | Experimental, unaccepted | Camera/depth integration code exists, but calibrated RGB delivery and registration have not been demonstrated on the device. Enumeration, compilation, or depth acquisition alone is not acceptance. |
| Native NPGS fork | Accepted for the `Q_charge=0` Kerr slice at quality 2; broader migration candidate | Complete official history is pinned through the GPL fork. Exact native launch states pass independent CPU f64 event/direction gates. Kerr-Newman charge, polarization, disk parity, OpenXR, and MR remain independently blocked. |

The repository suite passed `232` tests on 2026-08-06 after the Task 9/10
baseline was fast-forwarded to `main`, complete Unity `.meta` coverage was
restored, and the native NPGS raw-v2 conversion and exact-state Kerr
cross-check were added.

## NPGS Native Migration

The selected future runtime is a native fork of NPGS rather than a Unity port
of its GPL shader. The public upstream baseline reviewed for this decision is
`baopinshui/NPGS@a039e6417b28d53cbd413ee8f6d64543e755aa3e`.
The current pinned integration revision is
`Zhen-WushuiLingchun/NPGS@20acb4a0c25d1b6899625d9ceda6d8e97b93a906`.
The complete public ref set was refreshed on 2026-08-06; no public BBH/GW
source was found.

The migration does not treat NPGS screenshots or feature claims as scientific
validation. GR-BH-XR retains its Python f64 reference solvers, audit schemas,
Page-Thorne disk model, validation gates, and Unity baseline while the native
renderer is checked. NPGS becomes the default runtime only after:

1. its `Q_charge = 0` Kerr output passes the existing CPU-reference gates
   (**passed at native quality 2 on 2026-08-06**);
2. Kerr-Newman behavior has an independent CPU/reference validation path;
3. its fast path has a reproducible same-hardware performance baseline;
4. native OpenXR passes stereo, world-lock, control, and headset frame-time
   gates.

Until those gates pass, NPGS is an integration candidate and the Unity runtime
remains the Quest regression oracle. After native PCVR parity, Unity will be
removed from the default branch in a dedicated commit but retained in a
permanent legacy branch/tag.

The native build/performance zero-point gate is now closed. Exact hidden Vulkan
framebuffers measured 200 median FPS at 1920 x 1080 and 76 median FPS at
3840 x 2160 on the RTX 5080 Laptop GPU. This result excludes the future audit
pass, OpenXR, and readback, so it is not a physics or headset acceptance claim.

## Task Number Crosswalk

The dated 2026-06-28 plan used Tasks 1-10 as a forward-looking roadmap. Later
development-log entries reused Task numbers for concrete execution slices.
Current status should therefore be read by capability, not by number:

- historical Tasks 1-3: repository, literature, and CPU reference baseline;
- execution Task 4: WGPU/Vulkan Kerr validation;
- execution Tasks 5-6: Unity transfer playback and thin-disk transfer;
- execution Tasks 7-8: finite-observer roaming and horizon descent keyframes;
- execution Task 9: Unity HLSL Kerr-Schild live tracing;
- execution Task 10: MR camera/depth experiment;
- NPGS native migration: a new runtime track, not the historical BBH Task 10.

## Open Gates

- Independent Kerr-Newman and Walker-Penrose validation.
- NPGS disk-transfer parity and Page-Thorne integration.
- Native Vulkan/OpenXR PCVR integration.
- Device proof of calibrated MR RGB delivery before any passthrough-lensing
  claim.
- BBH/GW work remains deferred. No public BBH/GW source branch was available
  in the reviewed NPGS repository; showcase media is not implementation
  evidence.
