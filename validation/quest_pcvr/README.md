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

The current high-spin desktop package prepared for Unity is:

```powershell
python -m gr_bh_xr.xr.export_unity_textures --input outputs/task5/gpu_lensmap_kerr_a0.9_i60_1024_h00125.h5 --out-dir outputs/task5/unity_lensmap_kerr_a0.9_i60_1024_to_4k_display --target-size 4096
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
- The Unity preview shader defaults to a screen-space square gate for the
  desktop validation pass. It samples the square lens map without stretching it
  to the display aspect ratio; pixels outside the square gate sample the same
  cubemap directly.
- The shader also contains an opt-in angular-window path through
  `_UseAngularWindow`, but that path is still experimental and must not be used
  as evidence for headset head-motion stability until it has its own Unity
  desktop and Quest runtime validation.
- In the angular path, the shader only accepts signed forward rays with
  `localRay.z > 0`; back-facing rays are intentionally rejected to avoid a
  parity-flipped ghost window. The mapping is gnomonic,
  `alpha = r_obs * x / z`, `beta = -r_obs * y / z`. Direction transforms use
  explicit pure rotation basis vectors, not scale-bearing object matrices, so
  object scale cannot skew the physical sky direction.
- The Unity preview shader transforms stored local Unity escape directions by
  the lens-screen world basis before cubemap sampling, so the background sky
  does not silently rotate with raw texture rows. `BlackHoleLensMaterialBinder`
  refreshes that basis in `LateUpdate` by default so runtime recentering or
  anchor rotation cannot leave stale vectors in the material.
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
- Use the screen-space square preview gate for the current desktop validation
  pass. A deliberately oversized screen mesh is acceptable because pixels
  outside the square gate fall back to the cubemap directly. Do not stretch the
  square lens map itself to the display aspect ratio; that turns a circular or
  weakly D-shaped shadow into an artificial ellipse.
- The quad material uses `GR-BH-XR/Kerr Lens Static Preview`; the scene skybox
  uses the same cubemap directly. The main camera clear flags should be
  `Skybox`, not `Solid Color`, otherwise the area outside any preview mesh can
  appear black even when the material is correctly bound.
- A recognizable constellation should keep its handedness inside the lens-map
  quad.
- The Kerr package should show the expected asymmetric/D-shaped shadow and
  horizontal displacement relative to the Schwarzschild package.
- Far from the shadow, the background distortion should decrease smoothly.

Do not require quad-edge continuity for the current `alpha_max = beta_max = 8M`
packages. At `r_obs = 100M`, rays at the map edge are still significantly
deflected, so the lensed square-gate interior is not expected to match the
unlensed skybox outside the gate. Edge-continuity checks require either a much
wider map, such as `alpha_max ~= 40-60M`, with the camera angular size
calibrated to `2 atan(alpha_max / r_obs)`, or a full-camera transfer map.

The current accepted desktop gate is a screen-space static preview, not a
Quest head-motion result. The angular-window / full-camera path is the intended
next step for head rotation, but it remains pending until verified in Unity and
on the headset. Any head translation remains outside the baked-map model: the
texture still assumes the single observer radius and inclination recorded in
`lens_map_metadata.json`.

Record the result as a dated note in this directory. Store screenshots beside
the note when they are produced; generated Unity project state should stay out
of Git unless it is a deliberately minimal source asset.

Current desktop gate note:

- `2026-07-06-unity-editor-desktop-gate.md`

The repository also provides `GRBHXR.EditorTools.GRBHXRGateAutomation` under
`xr/unity_frontend/Editor/` for reproducible batch captures. The quadrant
handedness batch command should be run whenever the screen-space sampling path
or Unity render target path changes.
The angular-window yaw batch command should be run before Quest/OpenXR runtime
work because the headset path uses `_UseAngularWindow = 1`, not the accepted
screen-space desktop gate.

```powershell
$unity = 'D:\unity\Hub\Editor\6000.5.2f1\Editor\Unity.exe'
$proj = 'F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate'
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRGateAutomation.BatchCaptureAngularWindowYawGate -grbhxrCaptureDir 'F:\学习和研究\GR-BH-XR\outputs\task5\unity_gate'
```

The 2026-07-07 formal Unity-project run wrote yaw `0 deg`, `2 deg`, and
`4 deg` angular-window screenshots under ignored `outputs/task5/unity_gate/`.
The `0 deg` capture centers the Kerr lens window; the `4 deg` capture moves the
window consistently with the yawed camera and falls back to direct skybox
sampling outside the angular bounds. This closes the desktop precheck for the
Quest path, but it is not yet a headset runtime result.

Interpret this yaw gate narrowly. It verifies head-rotation anchoring for a
distant, fixed-observer black hole: when the camera turns, the fixed angular
window moves across the view without billboard perspective distortion. It is
not a simulation of orbiting around the black hole or changing the observer
inclination. Any real change of spin, inclination, observer position, or binary
phase requires a newly generated, selected, interpolated, or progressively
updated transfer map.

The current NASA skybox is also a validation background, not a VR-quality sky
asset by itself. A full-sky 4096-wide map contributes only about 100 source
pixels across the current `~9.15 deg` camera FOV, so narrow-field captures can
look blurred even when the lens transfer map is sharp. VR-quality inspection
needs either a much higher-resolution all-sky map, such as 32K/64K class, a
high-resolution local sky patch, or a procedural/catalog starfield designed for
the chosen angular FOV.

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
- Shader compatibility with single-pass instanced stereo: both eyes must render
  the same world-anchored angular window without one-eye black output or
  eye-dependent offset.
- PCVR Link resource note: a 4096x4096 `RGBAFloat` escape-direction texture is
  about 256 MiB before mipmaps or driver overhead. Under PCVR this is a desktop
  GPU resource, not a Quest-native compute target; record the actual GPU,
  render scale, and frame timing during runtime validation.
- Angular size: field of view, black-hole apparent radius, and screen
  half-width mapping are recorded.
- PC-to-Quest latency is measured or qualitatively documented.

These runtime checks belong in this directory as dated notes once Unity/OpenXR
is exercised on the headset.
