# Vulkan Compute Architecture Note

Task 4 uses WGPU's Vulkan backend instead of raw Vulkan bindings. The local
machine has Vulkan-capable NVIDIA and Intel adapters, but no local SPIR-V
toolchain such as `glslc`, `glslangValidator`, `dxc`, or `spirv-val`.

WGPU gives this project a practical Vulkan-backed compute path while keeping
shader source in WGSL and avoiding a separate shader-compilation toolchain.
The implementation still records `requested_backend=vulkan`, adapter metadata,
precision, RK method, and texture/debug buffers in HDF5 so the output remains
auditable.

Current implementation:

- package: `gr_bh_xr.gpu`
- backend selection: `gr_bh_xr.gpu.backend`
- compute shader and texture buffers: `gr_bh_xr.gpu.trace`
- map generation CLI: `python -m gr_bh_xr.gpu.generate_lens_map`
- CPU-vs-GPU validation CLI: `python -m gr_bh_xr.gpu.validate`
- interactive PC preview CLI: `python -m gr_bh_xr.gpu.preview`

The compute shader is a fixed-step f32 RK4 prototype following the Phase 1
Boyer-Lindquist inverse metric, analytic inverse-metric derivatives, Bardeen
screen constants, and event/failure-code meanings. It is a Task 4 baseline for
real-time texture generation, not a replacement for the CPU reference solver.
The Python wrapper caches the WGPU adapter/device/pipeline for repeated map
generation inside a process, and uses the current `set_bind_group` call
signature. The same compute pipeline traces both center screen samples and
subpixel samples in the critical-curve refinement band.

Deferred work:

- raw Vulkan or SPIR-V pipeline once a shader toolchain is part of the project;
- fully adaptive or higher-order GPU integration;
- Kerr-Schild or axis-regular continuation;
- Unity/OpenXR texture import and stereo/head-tracking integration;
- thin-disk transfer, redshift, time delay, and GRRT.
