# Current Implementation Status

Updated: 2026-08-10

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
| Native NPGS fork | Accepted for neutral exterior Kerr/Kerr-Newman rays, Kerr `Q=0` disk transfer, and geometric polarization transport at quality 2; native XR/MR interfaces are candidates | Complete official history is pinned through the GPL fork. Exact native states pass independent CPU f64 event/direction/disk gates, and raw v3 camera bases plus the complete Walker-Penrose scalar pass direct f64 parallel transport. OpenXR/Vulkan ownership, stereo-view, calibrated-camera, and depth provenance contracts now compile, but no native OpenXR session or delivered MR camera frame has passed a device gate. |

The repository suite passed `273` tests on 2026-08-10 after the BBH dynamic-
spacetime plan and its fail-closed documentation contracts were registered.
The centralized NPGS integration/MR contracts, preceding Task 9/10 baseline,
complete Unity `.meta` coverage, native Kerr/Kerr-Newman/disk gates, and raw-v3
polarization-geometry gates remain in the same regression.

## NPGS Native Migration

The selected future runtime is a native fork of NPGS rather than a Unity port
of its GPL shader. The public upstream baseline reviewed for this decision is
`baopinshui/NPGS@a039e6417b28d53cbd413ee8f6d64543e755aa3e`.
The current pinned integration revision is
`Zhen-WushuiLingchun/NPGS@6c9a3aaf76ccc52b8c67e25d4eb7141bea06502d`.
The complete public ref set was refreshed on 2026-08-10; no public BBH/GW
source was found.

### Reuse And Compatibility Matrix

| Capability | Decision | Reason |
| --- | --- | --- |
| Native Vulkan renderer, prepass/composite/TAA, shared Kerr/Kerr-Newman tracer | Reuse NPGS directly | This is the higher-performance runtime and its accepted slices already pass independent replay gates. |
| Neutral Kerr/Kerr-Newman ray geometry, Kerr disk crossings, Walker-Penrose geometry | Accepted NPGS implementation | Native quality-2 evidence meets the existing CPU-f64 thresholds. GR-BH-XR keeps the oracle and audit artifacts, not a competing production implementation. |
| Python f64 BL/KS solvers, HDF5 validators, Page-Thorne/blackbody model | Retain in GR-BH-XR | These provide independent scientific definitions and validated emission physics that NPGS must consume rather than self-certify. |
| Native Page-Thorne rendering and Stokes transport | Not yet merged | Page-Thorne assets are validated but not wired into native NPGS; geometric polarization does not establish emissivity, absorption, Faraday, or Stokes correctness. |
| Charged disk matter | Blocked | Neutral photons in a charged spacetime do not define a charged-plasma disk model. |
| Maximal extension | Visual/mathematical only | Exact stationary Kerr-Newman continuation is not an astrophysical collapse-interior prediction. |
| Native OpenXR and MR | Interface complete, runtime candidate | The render-sink and measured-frame contracts exist without changing desktop GLFW. Session/swapchain and real camera-frame delivery remain device gates. |
| BBH/GW | Tasks 0-4 plus the Task 5a CPU approximation are accepted; no dynamic native renderer yet | The analytic gates and an equal-mass, nonspinning, fixed-circular-orbit Combi-Ressler Eq. 11 provider now pass derivative, symmetry, isolated-hole, and ADM-constraint gates. It remains a `physics_approximation`; PN inspiral, merger/remnant, native GLSL, and NR snapshots remain open. |

The migration does not treat NPGS screenshots or feature claims as scientific
validation. GR-BH-XR retains its Python f64 reference solvers, audit schemas,
Page-Thorne disk model, validation gates, and Unity baseline while the native
renderer is checked. NPGS becomes the default runtime only after:

1. its `Q_charge = 0` Kerr output passes the existing CPU-reference gates
   (**passed at native quality 2 on 2026-08-06**);
2. Kerr-Newman behavior has an independent CPU/reference validation path
   (**neutral exterior rays passed on 2026-08-06**);
3. native Kerr disk transfer matches the CPU reference
   (**`Q=0`, first two crossings passed on 2026-08-06**);
4. native camera-basis and Walker-Penrose geometric transport match direct f64
   parallel transport (**passed on 2026-08-06; Stokes/emission remain open**);
5. its fast path has a reproducible same-hardware performance baseline;
6. native OpenXR interface/build contract passes (**passed on 2026-08-10**),
   then stereo, world-lock, control, and headset frame-time device gates pass;
7. a fresh calibrated camera frame with measured angular coverage passes the
   native MR provenance gate before any passthrough-pixel claim.

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
- BBH dynamic-spacetime track: the active post-migration roadmap in
  `docs/plans/2026-08-10-bbh-dynamic-spacetime-xr.md`, not an accepted runtime
  capability.

## Open Gates

- Polarized emission/Stokes validation; geometric Walker-Penrose transport is
  accepted, but magnetic/emission/Faraday models, charged particles, and
  maximal extension are not.
- NPGS Kerr `Q=0` disk-transfer parity has passed; charged-disk physics and
  Page-Thorne integration remain open.
- Native Vulkan/OpenXR session, swapchain, and PCVR device integration. The
  source-level ownership/stereo interface gate is complete.
- Device proof of fresh calibrated MR RGB delivery before any
  passthrough-lensing claim. Environment depth remains an independent input and
  cannot substitute for RGB evidence.
- BBH/GW implementation is active. The simulated-stereo baseline, Python f64
  time-dependent Hamiltonian oracle, native stationary-provider extraction,
  analytic TT plane-GW gates, and the constraint-audited equal-mass CPU SKS
  approximation are accepted. No dynamic NPGS ray path, PN inspiral,
  merger-to-remnant transition, or NR snapshot provider is accepted yet. No
  public BBH/GW source branch was available in the
  reviewed NPGS repository; showcase media is not implementation evidence.
  See `docs/plans/2026-08-10-bbh-dynamic-spacetime-xr.md`.
