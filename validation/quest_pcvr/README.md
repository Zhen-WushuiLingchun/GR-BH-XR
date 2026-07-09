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

For background-lensing validation, also generate a full-sky transfer cubemap.
The finite `alpha,beta` map alone is only a local high-resolution patch around
the shadow. At `r_obs = 100M`, the edge of the `[-8M, 8M]` patch is still
strongly lensed, so falling back to an unlensed skybox creates a square
discontinuity. The full-sky transfer cubemap traces every cubemap texel from
the finite-radius static observer tetrad and removes that unphysical fallback:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.generate_transfer_cubemap --spin 0.9 --inclination-deg 60 --face-size 1024 --r-obs 100 --steps 8000 --out-dir outputs/task5/fullsky_kerr_a0.9_i60_1024
```

The 2026-07-07 local run on the NVIDIA GeForce RTX 5080 Laptop GPU wrote
`outputs/task5/fullsky_kerr_a0.9_i60_1024` with `faceSize = 1024`,
`totalPixels = 6291456`, `capture = 2023`, `escape = 6289433`,
`invalid = 0`, `event_cube_rgba8.bytes = 25165824` bytes, and
`escape_dir_unity_cube_rgba32f.bytes = 100663296` bytes.

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
- The Unity preview shader can use the finite `alpha,beta` lens map as a
  screen-space square gate for import/handedness debugging, but background
  lensing claims require the full-sky transfer cubemap. In full-sky mode, the
  shader samples the traced cubemap everywhere and blends the high-resolution
  4K local patch over the central angular window for shadow-edge sharpness.
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
- Use the full-sky transfer cubemap path for background-lensing desktop and
  Quest validation. The finite square lens map remains useful as the central
  high-resolution patch, but pixels outside that patch must keep sampling the
  traced full-sky transfer cubemap rather than an unlensed skybox. Do not
  stretch the square lens map itself to the display aspect ratio; that turns a
  circular or weakly D-shaped shadow into an artificial ellipse.
- The quad material uses `GR-BH-XR/Kerr Lens Static Preview`; the scene skybox
  uses the same cubemap directly. The main camera clear flags should be
  `Skybox`, not `Solid Color`, otherwise the area outside any preview mesh can
  appear black even when the material is correctly bound.
- A recognizable constellation should keep its handedness inside the lens-map
  quad.
- The Kerr package should show the expected asymmetric/D-shaped shadow and
  horizontal displacement relative to the Schwarzschild package.
- Far from the shadow, the background distortion should decrease smoothly.

Do not accept a hard square boundary as a physical result. The earlier
`alpha_max = beta_max = 8M` angular-window fallback was useful for discovering
the problem, but it cut a strongly lensed boundary directly to an unlensed
skybox. The accepted desktop precheck now uses the same yaw capture path with
`-grbhxrFullSkyTransferDir`, so the whole camera ray field is lensed by the
full-sky transfer cubemap while the central patch supplies higher local
resolution.

This is still not a Quest headset runtime result. It verifies the Unity desktop
texture contract and head-rotation anchoring for a distant fixed observer. Any
head translation remains outside the baked-map model: the texture still
assumes the single observer radius and inclination recorded in
`lens_map_metadata.json` and `full_sky_transfer_metadata.json`.

Record the result as a dated note in this directory. Store screenshots beside
the note when they are produced; generated Unity project state should stay out
of Git unless it is a deliberately minimal source asset.

Current desktop gate note:

- `2026-07-06-unity-editor-desktop-gate.md`

The repository also provides `GRBHXR.EditorTools.GRBHXRGateAutomation` under
`xr/unity_frontend/Editor/` for reproducible batch captures. The quadrant
handedness batch command should be run whenever the screen-space sampling path
or Unity render target path changes.
The full-sky yaw batch command should be run before Quest/OpenXR runtime work.
It uses `_UseAngularWindow = 1` to position the high-resolution central patch,
but `-grbhxrFullSkyTransferDir` keeps the background path on the traced
full-sky transfer cubemap.

```powershell
$unity = 'D:\unity\Hub\Editor\6000.5.2f1\Editor\Unity.exe'
$proj = 'F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate'
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRGateAutomation.BatchCaptureAngularWindowYawGate -grbhxrCaptureDir 'F:\UnityProjects\GRBHXR_PCVR_Gate\unity_gate_fullsky_hybrid_1024' -grbhxrFullSkyTransferDir Assets/GRBHXR/FullSkyTransfer1024
```

The full-sky protractor gate uses the same Unity project path but switches the
skybox/probe to the 10-degree protractor bands:

```powershell
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRGateAutomation.BatchCaptureFullSkyProtractorYawGate -grbhxrCaptureDir 'F:\UnityProjects\GRBHXR_PCVR_Gate\unity_gate_fullsky_protractor_1024' -grbhxrFullSkyTransferDir Assets/GRBHXR/FullSkyTransfer1024
```

Compare the captured protractor bands against the full-sky cubemap direction
bytes, not against the old 2D local-patch direction texture:

```powershell
python validation\quest_pcvr\scripts\compare_protractor_gate.py --full-sky-package-dir 'F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate\Assets\GRBHXR\FullSkyTransfer1024' --screenshot 'F:\UnityProjects\GRBHXR_PCVR_Gate\unity_gate_fullsky_protractor_1024\unity_gate_fullsky_protractor_yaw_004_square_1024.png' --fov-deg 9.1478 --yaw-deg 4 --r-obs 100 --alpha-max 8 --beta-max 8 --samples 61 --json
```

On 2026-07-07 the full-sky protractor run wrote yaw `0/2/4 deg` screenshots
under `F:\UnityProjects\GRBHXR_PCVR_Gate\unity_gate_fullsky_protractor_1024`.
The quantitative comparison reported no former-window seam violations:
`seam_pair_count = 101`, `seam_max_observed_band_jump = 1`, and
`seam_violations = 0` at yaw `2 deg` and `4 deg`. The yaw `4 deg` screenshot
had `valid = 2684`, `exact_raw = 2432`, and mean band error `0.114` band.
These numbers turn the "no square seam" visual claim into a reproducible
regression over the actual full-sky transfer cubemap bytes.

The 2026-07-07 full-sky Unity-project run wrote yaw `0 deg`, `2 deg`, and
`4 deg` screenshots under
`F:\UnityProjects\GRBHXR_PCVR_Gate\unity_gate_fullsky_hybrid_1024`. The `4 deg`
capture no longer has the square hard boundary from unlensed-skybox fallback:
the right side is still sampled through the traced full-sky transfer map, while
the center keeps the 4K local patch for shadow-edge clarity. This closes the
desktop precheck for the current static full-sky texture path, but it is not
yet a headset runtime result.

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

## Thin-Disk Unity Audit Gate

Task 6 disk transfer enters Unity first as an audit visualization, not as a
finished accretion-disk beauty shader. The full-sky transfer package may include
two optional `RGBAHalf` cubemaps:

- `disk_order0_transfer_cube_rgba16f.bytes`
- `disk_order1_transfer_cube_rgba16f.bytes`

Their channels are `(r_m, sin(phi_m), cos(phi_m), g_m)`. A zero `r_m` / `g_m`
texel means that order has no finite emitting-annulus hit. The shader audit
mode renders `g_m` as a blue-to-red false color and overlays equal-`r_m` bands,
so it can be compared against CPU Luminet-style transfer plots before any
emissivity, color temperature, or animation is added.

Local 2026-07-07 disk audit commands:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.generate_transfer_cubemap --spin 0.9 --inclination-deg 60 --face-size 512 --r-obs 100 --steps 8000 --out-dir outputs/task6/fullsky_disk_kerr_a0.9_i60_512

$unity = 'D:\unity\Hub\Editor\6000.5.2f1\Editor\Unity.exe'
$proj = 'F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate'
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRGateAutomation.BatchCaptureFullSkyDiskAuditGate -grbhxrCaptureDir 'F:\UnityProjects\GRBHXR_PCVR_Gate\unity_gate_fullsky_disk_audit_512' -grbhxrFullSkyTransferDir Assets/GRBHXR/FullSkyTransferDisk512
```

The 512-face package had disk valid counts `[11826, 335]` for `m = 0, 1` and
zero invalid rays. The Unity audit run wrote
`unity_gate_fullsky_disk_audit_m0_square_1024.png` and
`unity_gate_fullsky_disk_audit_m1_square_1024.png`. The `m = 0` image shows a
continuous equal-radius field around the Kerr shadow; the `m = 1` image isolates
the secondary-image band near the shadow edge. These screenshots are still
audit artifacts. The Unity shader can now use Page-Thorne/blackbody LUT assets
when they are present in the full-sky transfer directory, with baseline
`F(r) g^4` weighting and `T_obs = g T_emit` color. Keplerian pattern advection
and time-delay use still require exporting `Delta t_m` into Unity disk textures.

For the desktop disk-color A/B gate, first place the four LUT files in the same
full-sky transfer directory as the disk cubemaps, then run:

```powershell
$unity = 'D:\unity\Hub\Editor\6000.5.2f1\Editor\Unity.exe'
$proj = 'F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate'
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRGateAutomation.BatchCaptureFullSkyDiskVisualLutGate -grbhxrCaptureDir 'F:\UnityProjects\GRBHXR_PCVR_Gate\unity_gate_fullsky_disk_visual_lut' -grbhxrFullSkyTransferDir Assets/GRBHXR/FullSkyTransferDisk1024
```

The gate writes `unity_gate_fullsky_disk_visual_proxy_square_1024.png` and
`unity_gate_fullsky_disk_visual_lut_square_1024.png`. The first screenshot
forces the historical proxy ramp; the second forces the Page-Thorne/blackbody
LUT path using the same transfer map.

Disk-transfer cubemap schema v2 stores boundary coverage explicitly. The
`disk_order*_transfer_cube_rgba16f.bytes` files contain coverage-premultiplied
`r_m`, `sin(phi_m)`, `cos(phi_m)`, and coverage; the companion
`disk_order*_redshift_cube_rgba16f.bytes` files contain coverage-premultiplied
`g_m` in the red channel. Unity divides the interpolated channels by coverage
and uses coverage as opacity. This is required because disk-hit validity is a
sub-texel coverage quantity near the lensed disk edge; a binary valid/invalid
gate produces blocky texel steps when the inner disk image is magnified around
the shadow. The historical proxy ramp can expose those steps strongly because
it stays bright at the inner edge, while the Page-Thorne LUT path partially
hides them by making the zero-torque ISCO edge dimmer. Formal Quest screenshots
should use v2 coverage assets, not legacy binary-validity disk cubes.

## PCVR Sky-Shell First-Run Scene

The Quest first-run scene should use the full-sky transfer map on a camera-
centered sky shell, not a flat near-field quad. `BlackHoleXrSkyShell` keeps the
mesh centered on the active camera position and refreshes the lens basis from a
separate `BlackHoleLensAnchor`. The shell does not follow camera rotation, so
head yaw/pitch samples new world directions instead of looking at a tilted
billboard.

This is still MR-0 / PCVR static playback. It shows a virtual, world-anchored
black-hole lens over the rendered skybox and does not bend real Quest
passthrough camera pixels.

Configure the formal Unity project:

```powershell
$unity = 'D:\unity\Hub\Editor\6000.5.2f1\Editor\Unity.exe'
$proj = 'F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate'
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRGateAutomation.BatchConfigurePcvrSkyShellFirstRun -grbhxrFullSkyTransferDir Assets/GRBHXR/FullSkyTransfer1024 -grbhxrUseSkyShell -logFile 'F:\UnityProjects\GRBHXR_PCVR_Gate\pcvr_sky_shell_setup.log'
```

Run the read-only local preflight before connecting a headset or starting the
OpenXR runtime:

```powershell
powershell -ExecutionPolicy Bypass -File validation\quest_pcvr\scripts\quest_pcvr_preflight.ps1
```

The preflight checks for the configured Unity executable, the formal Unity
project, required full-sky transfer bytes, ADB availability, and Quest USB PnP
presence. It does not install an APK, change headset settings, or modify the
Unity project.

Local 2026-07-07 preflight result: Unity `6000.5.2f1`, the formal Unity
project, and `Assets/GRBHXR/FullSkyTransfer1024` were present; ADB was found at
`C:\Users\hydro\AppData\Local\Android\Sdk\platform-tools\adb.exe`; Windows PnP
reported Quest USB interfaces with vendor ID `VID_2833`. `adb devices -l`
started the daemon but did not list an authorized device yet, so the headset
side USB-debugging authorization prompt still needs to be accepted during
runtime hookup.

## Interaction Scaffold

The first interaction layer treats the black hole as a distant, static transfer
map with a movable angular basis:

- Dragging calls `BlackHoleLensAnchorControls.ApplyScreenDrag()` and rotates
  the `BlackHoleLensAnchor` yaw/pitch basis. This is a rigid sky rotation, not
  a change in observer position.
- Rolling the black hole is a separate operation through `AddRollDegrees()` or
  `SetRollDegrees()`. Desktop development bindings use `Q/E`; an XR controller
  twist or floating-panel button can call the same public methods.
- `R` resets yaw, pitch, and roll.
- Apparent-size, `r_obs`, spin, inclination, and disk geometry are locked in
  the static package. Calling `RequestObserverRadiusChange()` only marks the
  current transfer map as stale; it does not rescale or pretend to update the
  physics.
- `BlackHoleLensFloatingPanel` is a lightweight world-space status panel. It is
  intended as a first Quest debug HUD and as the target for future controller
  buttons/sliders. It should display the current yaw/pitch/roll and the locked
  size / stale-transfer status.

For the first Quest run, use this as a debug and validation control surface.
Do not present it as a complete parameter editor: changing Kerr spin,
inclination, observer radius, or binary phase needs Tier 1 transfer-map
selection or regeneration.

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
