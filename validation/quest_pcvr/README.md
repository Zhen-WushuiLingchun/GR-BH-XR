# Quest PCVR Validation

Phase: Task 5 Unity/OpenXR bridge.

This validation entry starts with the static texture bridge. It does not yet
claim a headset-runtime result.

## Static Texture Bridge Gate

Generate a GPU lens map and export Unity raw textures:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.generate_lens_map --spin 0.5 --inclination-deg 60 --grid 256 --alpha-max 8 --beta-max 8 --out outputs/phase2/gpu_lensmap_kerr_a0.5_i60.h5
python -m gr_bh_xr.xr.export_unity_textures --input outputs/phase2/gpu_lensmap_kerr_a0.5_i60.h5 --out-dir outputs/task5/unity_lensmap_kerr_a0.5_i60
```

Local desktop-validation packages prepared on 2026-07-06:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.generate_lens_map --spin 0 --inclination-deg 90 --grid 256 --alpha-max 8 --beta-max 8 --out outputs/task5/gpu_lensmap_schwarzschild_i90_256.h5
python -m gr_bh_xr.xr.export_unity_textures --input outputs/task5/gpu_lensmap_schwarzschild_i90_256.h5 --out-dir outputs/task5/unity_lensmap_schwarzschild_i90_256
python -m gr_bh_xr.gpu.generate_lens_map --spin 0.9 --inclination-deg 60 --grid 256 --alpha-max 8 --beta-max 8 --step-size 0.025 --steps 16000 --out outputs/task5/gpu_lensmap_kerr_a0.9_i60_256.h5
python -m gr_bh_xr.xr.export_unity_textures --input outputs/task5/gpu_lensmap_kerr_a0.9_i60_256.h5 --out-dir outputs/task5/unity_lensmap_kerr_a0.9_i60_256
```

For VR headset inspection, generate a 4096x4096 display package from the same
validated HDF5 source:

```powershell
python -m gr_bh_xr.xr.export_unity_textures --input outputs/task5/gpu_lensmap_kerr_a0.9_i60_256.h5 --out-dir outputs/task5/unity_lensmap_kerr_a0.9_i60_4k_display --target-size 4096
```

This 4K package is intended to prevent obvious headset pixelation. It is not a
native 4096x4096 geodesic trace; `lens_map_metadata.json` records
`nativeTraceResolution = false` when `--target-size` resamples a lower-source
grid. Native 4K tracing needs a later tiled/offline generator and is required
before making claims about 4K physical transfer-map resolution.

The generated package directories are intentionally under ignored `outputs/`.
They should be copied into a Unity project for desktop validation.

Acceptance for this gate:

- `lens_map_metadata.json` records the source schema, dimensions, screen
  bounds, and Unity basis vectors.
- If `--target-size` was used, `lens_map_metadata.json` records both source and
  export dimensions and marks the package as display-resampled.
- `sourceEscapePixels` is the escaped-pixel count on the source traced grid;
  `escapePixels` is the exported texel count with valid escape-direction alpha
  after any display resample.
- `event_rgba8.bytes` has exactly `width * height * 4` bytes.
- `escape_dir_unity_rgba32f.bytes` has exactly `width * height * 16` bytes and
  stores `(x_unity, y_unity, z_unity, valid_escape)`.
- The documented screen convention is `UV(0,0) -> (alpha_min, beta_max)` and
  `UV(1,1) -> (alpha_max, beta_min)` because exported textures are vertically
  flipped relative to solver row order.
- The export metadata states that solver `+beta` points visually downward
  while Unity texture `+V` points visually upward after the flip.
- The documented world convention maps positive `alpha` to Unity `+X` and the
  camera-to-black-hole direction to Unity `+Z`.
- The Unity package under `xr/unity_frontend/` can load the raw bytes into
  `TextureFormat.RGBA32` and `TextureFormat.RGBAFloat` textures.
- A weak-deflection directional regression test confirms the right/top screen
  signs: right-up exported pixels have `x_unity > 0`, `y_unity > 0`, while
  right-down pixels have `x_unity > 0`, `y_unity < 0`.

## Unity Editor Desktop Gate

Before Quest runtime validation, verify the static texture contract in the
Unity Editor on a normal desktop display:

- Use two exported packages: Schwarzschild `a = 0`, `i = 90 deg`, and Kerr
  `a = 0.9`, `i = 60 deg`.
- Use a recognizable real-sky cubemap or equirectangular sky converted to a
  cubemap. Do not use random stars or procedural noise for the coordinate
  check because those can hide mirror errors.
- Put a quad in front of the camera. The quad material uses
  `GR-BH-XR/Kerr Lens Static Preview`; the scene skybox uses the same cubemap
  directly.
- In weak-deflection regions near the quad edge, stars should continue across
  the quad boundary without a vertical flip, horizontal mirror, transpose, or
  rotation.
- A recognizable constellation should keep its handedness inside the lens-map
  quad.
- The Kerr package should show the expected asymmetric/D-shaped shadow and
  horizontal displacement relative to the Schwarzschild package.

Record the result as a dated note in this directory. Store screenshots beside
the note when they are produced; generated Unity project state should stay out
of Git unless it is a deliberately minimal source asset.

## Headset Runtime Protocol

The following checks are still pending and must be recorded before claiming a
Quest PCVR result:

- Quest 3 connection path: Link or Air Link, runtime version, GPU, refresh
  rate, and render scale.
- 72 Hz / 90 Hz frame pacing with the static texture shader active.
- Head-motion stability: the black-hole texture remains world/head stable
  according to the selected scene anchoring.
- Stereo behavior: astronomical-distance mode should not invent physical
  binocular disparity; any usability scaling must be documented.
- Angular size: field of view, black-hole apparent radius, and screen
  half-width mapping are recorded.
- PC-to-Quest latency is measured or qualitatively documented.

These runtime checks belong in this directory as dated notes once Unity/OpenXR
is exercised on the headset.
