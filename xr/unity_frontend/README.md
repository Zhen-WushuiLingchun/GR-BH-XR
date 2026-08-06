# Unity PCVR/MR Kerr Renderer

This directory is the `com.grbhxr.lensing` Unity package. It is no longer a
static texture bridge: it carries two distinct runtime paths.

- **Baked transfer playback.** Unity loads exported full-sky / local transfer
  textures and does a real-time lookup of offline-traced geodesics. This
  remains the deterministic audit and fallback path.
- **Live tracing (Task 9).** `BlackHoleLiveTracer.compute` integrates
  single-precision Cartesian Kerr-Schild null geodesics inside Unity for the
  current observer state. `BlackHoleLiveTracer.cs` dispatches a bounded ray
  budget per display frame and hard-swaps only a completed pass, so the view
  is always exactly one complete solution at one observer state. Geodesic
  integration therefore does happen inside Unity — but it is amortized over
  several display frames, and the package does **not** claim a newly converged
  full-resolution sky at every 72/90 Hz frame, nor per-eye per-frame solving.
  The per-eye per-frame cost is a texture lookup.
- **Roam/descent playback (Tasks 7-8).** Unity loads finite-observer
  keyframes. The rain-frame horizon-descent assets and their gates are owned
  by the Task 7-8 physics worktree; this package plays them back and makes no
  claim about their physics.
- **MR camera/depth (Task 10).** The Meta MRUK camera backend and
  environment-depth acquisition are implemented and late-bound. Live
  camera-pixel lensing is **unaccepted**: no calibrated RGB frame delivery has
  been demonstrated on a device.

The validated editor baseline is Unity `6000.0.76f1`, URP `17.0.4`, OpenXR
`1.17.1`, D3D11, and Meta MRUK `85.0.0` for PCVR. `package.json` declares
`"unity": "6000.0"` — the generation this package is actually tested against.
No backward compatibility with earlier Unity generations is claimed or
verified; the previously declared `2022.3` had never been tested.

Every asset in this package carries a committed `.meta` file. That is
deliberate: this is a UPM package consumed by an out-of-repo Unity project,
and an absent `.meta` makes Unity mint a fresh random GUID per clone, silently
breaking every material, scene and prefab reference to the affected asset.
The committed GUIDs match the formal embedded package, which is
content-identical to this directory modulo line endings.
`Runtime/link.xml.meta` is the sole exception with no upstream provenance,
because `link.xml` is new here.

## Export From Python

Generate a GPU lens map, then export a Unity texture package:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.gpu.generate_lens_map --spin 0.5 --inclination-deg 60 --grid 256 --alpha-max 8 --beta-max 8 --out outputs/phase2/gpu_lensmap_kerr_a0.5_i60.h5
python -m gr_bh_xr.xr.export_unity_textures --input outputs/phase2/gpu_lensmap_kerr_a0.5_i60.h5 --out-dir outputs/task5/unity_lensmap_kerr_a0.5_i60
```

For a headset-facing desktop/PCVR check, export at least a 4096x4096 display
texture:

```powershell
python -m gr_bh_xr.xr.export_unity_textures --input outputs/phase2/gpu_lensmap_kerr_a0.5_i60.h5 --out-dir outputs/task5/unity_lensmap_kerr_a0.5_i60_4k --target-size 4096
```

`--target-size` is a display resample. It reduces visible texture pixelation in
VR, but it does not add physical ray-tracing resolution beyond the source HDF5
grid. The metadata records both source and exported dimensions; use native
high-resolution traced maps for physics-resolution claims.
`sourceEscapePixels` records the escaped-pixel count in the source HDF5 grid;
`escapePixels` records the exported texels whose escape-direction alpha channel
is valid after any display resampling.

The exporter writes:

- `event_rgba8.bytes`: raw `RGBA32` event/debug texture.
- `escape_dir_bh_rgba32f.bytes`: raw `RGBAFloat` direction in black-hole
  Cartesian axes, with alpha channel `1` for escaped rays and `0` otherwise.
- `escape_dir_unity_rgba32f.bytes`: the same direction pre-rotated into the
  Unity world basis documented below.
- `lens_map_metadata.json`: schema, dimensions, screen bounds, and basis
  vectors.
- `event_preview.png`: human preview only; the raw `.bytes` files are the
  authoritative Unity inputs.

For background-lensing validation, also export a full-sky transfer cubemap:

```powershell
python -m gr_bh_xr.gpu.generate_transfer_cubemap --spin 0.9 --inclination-deg 60 --face-size 1024 --r-obs 100 --steps 8000 --out-dir outputs/task5/fullsky_kerr_a0.9_i60_1024
```

The full-sky package writes `full_sky_transfer_metadata.json`,
`event_cube_rgba8.bytes`, and `escape_dir_unity_cube_rgba32f.bytes`. It traces
one finite-radius static-observer ray per Unity cubemap texel. This is the
background path for Quest validation; the finite `alpha,beta` texture is only a
high-resolution local patch around the shadow.

## Unity Import

Install this directory as a local Unity Package Manager package:

```text
Window > Package Manager > + > Add package from disk...
xr/unity_frontend/package.json
```

For the first PCVR pass:

1. Create or open a Unity project with OpenXR enabled for PCVR.
2. Copy the exported `.bytes` and `.json` files into the Unity project.
3. Rename the raw files with a `.bytes` extension if Unity does not import them
   as `TextAsset`.
4. Add `BlackHoleLensMap` to a scene object and assign:
   - `lens_map_metadata.json`;
   - `event_rgba8.bytes`;
   - `escape_dir_unity_rgba32f.bytes`;
   - optionally, for full-sky background lensing,
     `full_sky_transfer_metadata.json`, `event_cube_rgba8.bytes`, and
     `escape_dir_unity_cube_rgba32f.bytes`.
   - optionally, for Page-Thorne/blackbody disk color,
     `disk_color_lut_metadata.json`, `disk_color_lut_rgba32f.bytes`,
     `disk_radial_lut_metadata.json`, and `disk_radial_lut_rgba32f.bytes`.
5. Add `BlackHoleLensMaterialBinder` and assign a material using
   `GR-BH-XR/Kerr Lens Static Preview`.
6. Assign a test cubemap to `_SkyboxCubemap`.

The preview shader supports three paths. The screen-space square gate is a
debug path for import, cubemap binding, handedness, and Kerr shadow morphology.
The angular-window path maps world rays into local `(alpha,beta)` coordinates.
The full-sky path is the background-lensing path: it samples a traced full-sky
transfer cubemap everywhere, then blends the high-resolution local
`alpha/beta` texture over the central angular window for shadow-edge clarity.
Pixels outside the local patch must not fall back to the raw skybox for
background-lensing claims.

Disk visual mode has two layers. If the disk LUT assets are absent, the shader
keeps the documented proxy color ramp. If both LUT assets are assigned, the
baseline disk emission samples the Page-Thorne radial table and blackbody color
table: `T_obs = g T_scale F_norm^(1/4)` and brightness is proportional to
`F_norm g^4`. This is still a display normalization, not an absolute
luminosity claim.

The shader still contains an opt-in `_UseAngularWindow` mode that computes the
world view ray, transforms that ray into the lens-screen object's local basis,
maps the local angular coordinates to `(alpha, beta)`, and samples the lens map
only inside the metadata screen bounds. Treat standalone angular-window
fallback to raw skybox as a debug path, not a background-lensing result. The
current desktop background-lensing precheck uses this angular mapping only to
position the high-resolution local patch while the full-sky transfer cubemap
remains active outside it.
The angular path uses the signed local forward component and ignores fragments
with `localRay.z <= 0`, so a back-facing screen cannot show a parity-flipped
ghost lens. Its screen mapping is the tangent-plane relation
`alpha = r_obs * x / z`, `beta = -r_obs * y / z`; this is a gnomonic
small-angle approximation to the Bardeen screen and differs at order
`(alpha / r_obs)^3`. It is acceptable for the current `8M / 100M` desktop
window but must be documented if a wider field is used. The shader does not use
scale-bearing object matrices for physical directions. `BlackHoleLensMap`
writes explicit pure rotation basis vectors (`_LensWorldRight`,
`_LensWorldUp`, `_LensWorldForward`) into the material, and the shader uses
those vectors for both angular-window view rays and escaped-direction cubemap
lookup.

For capture/invalid pixels inside the active gate, the shader falls back to
`event_rgba8`. For escaped rays, the sampled Unity-local escape direction is
transformed by the explicit lens-screen world basis before the cubemap lookup,
so the cubemap axis stays tied to the scene instead of to raw texture rows.
`BlackHoleLensMaterialBinder` refreshes the basis each `LateUpdate` by default,
so runtime recentering or anchor rotation does not leave stale direction
vectors in the material.

This is still a static-observer approximation. The texture assumes the metadata
`r_obs`, spin, inclination, and screen bounds used when it was generated. The
current accepted desktop precheck for background lensing uses the full-sky
transfer cubemap with yaw `0/2/4 deg` captures. It still does not close the
Quest headset-runtime requirement; physical head translation would require
regenerating or interpolating a different transfer map.

The optional disk hot-spot mode is also a transfer-map lookup. It uses the
validated disk cubemap channels `(r_m, sin(phi_m), cos(phi_m), g_m)` to draw a
Gaussian feature at disk coordinates `(r0, phi0)`, with brightness multiplied by
the same documented `g^p` convention as the disk visual mode. Orbit animation
advects the feature with the Keplerian `Omega(r0)` parameter written by the
runtime settings. The current Unity disk cubemap does not yet carry a separate
`Delta t_m` texture channel, so this first hot-spot display does not include
light-travel-time delay; the Python/HDF5 transfer buffers remain the audit
source for `Delta t_m`.

The package does not perform real-time geodesic integration. It renders a
precomputed transfer map in real time:

```text
view ray or screen coordinate -> precomputed escape direction -> cubemap sample
```

This is valid only for the baked observer/metric configuration. It is not a
general solution for changing spin, changing inclination, moving the observer,
BBH, multi-black-hole systems, or gravitational-wave lensing. Those cases need
runtime GPU tracing, progressive/tiled transfer-map updates, a sequence of
time-indexed transfer maps, or a validated surrogate model. A yawed camera in
the angular-window gate tests head-rotation anchoring for a distant fixed
black-hole window; it does not simulate orbiting around the black hole.

The background cubemap has its own resolution budget. A 4096-wide all-sky map
contains only about 100 source pixels across the current `~9.15 deg` gate FOV,
so direct skybox regions can look blurred even when the 4K lens-map texture is
working correctly. A higher-resolution lens-map display texture sharpens the
black-hole mask and transfer lookup, but it cannot recover detail that is not
present in the sampled skybox. VR-quality visual checks need a 32K/64K-class
all-sky map, a local high-resolution sky patch, or a procedural/catalog
starfield matched to the chosen angular field of view.

During display resampling, direction vectors are bilinearly interpolated and
renormalized. If interpolation cancels to a near-zero vector, the exporter marks
that texel invalid instead of writing a direction that would normalize to NaN.

`BlackHoleLensMap` loads the event texture with point sampling so categorical
capture/failure colors are not blurred. The escape-direction texture uses
bilinear sampling for smooth cubemap lookup between escaped rays. Both raw
textures are loaded with `linear: true`; the event colors are categorical debug
values and must not be altered by sRGB decoding.

## Coordinate Convention

The HDF5 source grid stores rows in increasing `beta`, but the exporter
vertically flips every texture buffer before writing Unity raw bytes:

```text
exported pixel(x, y) = y * width + x
x = 0                    -> alpha_min
x = width - 1            -> alpha_max
y = 0                    -> beta_max
y = height - 1           -> beta_min
Unity UV (0, 0)          -> alpha_min, beta_max
Unity UV (1, 1)          -> alpha_max, beta_min
alpha(u)                 = alpha_min + u * (alpha_max - alpha_min)
beta(v)                  = beta_max - v * (beta_max - beta_min)
```

This flip is deliberate. The solver's `+beta` convention increases
Boyer-Lindquist `theta`, which is visually downward on the observer screen.
Unity texture `+V` should move upward on screen, so the exported texture top is
`beta_min`. Unity world `+Y` below is a separate sky-direction basis vector
used for cubemap sampling.

Black-hole Cartesian axes are:

```text
+Z_BH = Kerr spin axis
+X_BH = Boyer-Lindquist phi = 0 equatorial direction
+Y_BH = Boyer-Lindquist phi = pi/2 equatorial direction
observer = (sin i, 0, cos i), with i = inclination_deg
```

Unity basis vectors are stored in `lens_map_metadata.json` and are defined as:

```text
forward_BH = -observer_BH
up_BH      = normalized projection of +Z_BH onto the observer screen
right_BH   = normalized cross(up_BH, forward_BH)
```

The vector mapping is:

```text
dir_unity.x = dot(dir_BH, right_BH)
dir_unity.y = dot(dir_BH, up_BH)
dir_unity.z = dot(dir_BH, forward_BH)
```

With the observer at `phi = 0`, `right_BH` is the positive-`alpha` screen
direction. For `i = 60 deg`, this makes `right_BH = (0, -1, 0)`. This explicit
choice prevents silent left-right mirror errors when the texture is consumed in
Unity.

Square exported screen windows, such as `alpha,beta in [-8M, 8M]`, should not
be stretched to a 16:9 display; that turns the shadow into an artificial
ellipse and is not a physics result. For background lensing, the finite square
window is only the central high-resolution patch. The full-sky cubemap remains
active outside that patch so the renderer does not introduce a square
unlensed-skybox discontinuity.

## Current Scope

This package is a static texture bridge:

- geodesics are generated offline by the Python GPU/CPU tools;
- Task 5 uses the texture contract for PCVR/MR display experiments;
- stereo disparity, head-motion stability, 72/90 Hz timing, black-hole angular
  size, and PC-to-Quest latency are validation tasks, not claims made by this
  package.

## URP Asset Version Lock And Repair

The formal Unity project is locked to Unity `6000.0.76f1` with URP `17.0.4`.
Opening it with a newer editor rewrites the render pipeline assets to a schema
this editor cannot read back down. That already happened once: Unity `6000.5` /
URP `17.5.0` wrote `m_AssetVersion: 10` into
`Assets/Settings/UniversalRenderPipelineGlobalSettings.asset` and
`k_AssetVersion: 13` into both `*_RPAsset.asset` files, where URP 17.0.4 expects
`8` and `12`.

This does not surface as a load error. URP's migration code is a ladder of
`if (version < N)` branches with no else, so a higher serialized version is a
silent no-op: the assets load, nothing throws, and `IsAtLastVersion()` stays
false forever. The damage only appears at build time, where URP's own
`URPBuildDataValidator` raises `BuildFailedException`. The global settings asset
additionally carried nine `[SerializeReference]` entries for types that do not
exist in URP 17.0.4 at all, two of them naming assemblies
(`Unity.UnifiedRayTracing.Runtime`, `Unity.PathTracing.Runtime`) that Unity
6000.0.76f1 does not ship.

`Editor/GRBHXRUrpAssetRepair.cs` handles this. It never edits a serialized
version field, in YAML or through `SerializedProperty`. It builds a pristine
asset with the public factory for the installed URP
(`RenderPipelineGlobalSettingsUtils.Create` and
`UniversalRenderPipelineAsset.Create`), carries the project's settings across it
without carrying the version and identity fields, and then copies that pristine
object over the existing asset with
`EditorUtility.CopySerialized`. The corrected version arrives as a property of a
correctly constructed object. Because the existing asset object is rewritten in
place, its GUID and path survive and the `GraphicsSettings` /
`QualitySettings` registrations are untouched.

The global settings container needs an extra migration step. The repair first
creates a data-source clone from the damaged asset. Unity drops the unavailable
17.5-only managed-reference types from that clone while retaining the 26 types
that exist in URP 17.0.4. Those compatible settings are copied into the pristine
17.0.4 object by managed-reference type with `EditorJsonUtility`, including
scalar fields and project object references. Every copied setting is serialized
again and compared byte-for-byte before the registered asset is overwritten.
This gate was added after an earlier implementation silently reset
`URPShaderStrippingSetting.m_StripUnusedPostProcessingVariants`; that rejected
run is retained as audit evidence and is not an accepted repair.

`UniversalRenderPipelineGlobalSettings` and its `Ensure()` overload are
`internal` in URP 17.0.4, so neither is callable from this assembly; the public
`RenderPipelineGlobalSettingsUtils.Create(Type, path)` overload is used instead,
with the concrete type taken from the loaded asset rather than by reflection.
The expected version is discovered by constructing one throwaway instance and
reading its version field, so no version number is hardcoded.

Three entry points, all under `GR-BH-XR/URP Asset Repair/`:

```powershell
$unity = 'D:\unity\Hub\Editor\6000.0.76f1\Editor\Unity.exe'
$proj = 'F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate'

# Report only. Does not modify any render pipeline asset.
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRUrpAssetRepair.BatchAuditUrpAssets

# Fail closed. Exit code 1 when the assets do not match the installed editor.
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRUrpAssetRepair.BatchPreflightUrpAssets

# The only entry point that writes. Explicit operator action.
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRUrpAssetRepair.BatchRepairUrpAssets
```

Unity.exe is a GUI-subsystem process on Windows, so `&` returns before the run
finishes. Use `Start-Process -Wait -PassThru` when the exit code matters.

`GRBHXRQuestPcvrSetup.BuildWindowsOpenXrPlayer` calls the preflight as its first
statement, before `ConfigureOpenXrLoader` saves XR settings assets, before the
scene is overwritten, and before the `PlayerSettings` writes. Setup and build
never repair anything; an incompatible project fails with the asset paths, the
serialized and expected versions, the missing serialized reference types, and
the exact repair command to run.

Each run writes a machine-readable report and pre-repair copies of every asset
it touches under `<project>/Logs/GRBHXR/urp_asset_repair/`. `Logs/` is not
imported by the Unity asset database and is covered by this repository's
`[Ll]ogs/` ignore rule. Override with `-grbhxrUrpRepairReportDir <path>`.
All incompatible assets are backed up before the first write. Any exception
restores every backup, reimports the assets synchronously, and emits a schema-v2
failure report with `rollbackPerformed`. The validation-only
`-grbhxrUrpRepairTestFailAfterAssets N` argument deliberately fails after `N`
repairs so this rollback path can be exercised under the locked editor; do not
use it for a normal repair. Post-repair compatibility, pipeline registrations,
and deletion of URP's transient construction asset are inside that transaction:
failure of any of those checks also rolls back the render-pipeline assets.

Two behaviours worth knowing:

- Constructing any URP global settings object makes URP 17.0.4 unconditionally
  write `Assets/DefaultVolumeProfile.asset`, replacing whatever is there and
  issuing a new GUID. Every entry point brackets its work: it refuses to run if
  that path is already occupied, and removes the transient asset afterwards.
- `m_RuntimeSettings` is empty in the authored asset by design. URP clears it on
  every editor serialize and only fills it when `BuildPipeline.isBuildingPlayer`.

Known limitation: the preflight checks the default render pipeline asset and
every quality level. It does not expand the `IncludeAdditionalRPAssets`
label/scene inclusion set, which is disabled in this project. If that is ever
enabled, an asset reachable only through it would be caught by URP's own build
validator with a less specific message rather than by this preflight.

**A repaired, compiling project is not a validated one.** Everything above shows
that the project opens, compiles, and passes URP's version contract under
`6000.0.76f1`. It says nothing about headset behaviour, and nothing at all about
MR passthrough RGB. Device-side claims still require the Quest validation
protocol and remain ungated by this work.

## Editor Gate Automation

The package includes editor-only batch helpers under `Editor/` so Unity desktop
validation is reproducible from the repository rather than from local project
scripts. In a Unity project that has copied or linked the exported lens-map
package and skybox assets, run:

```powershell
$unity = 'D:\unity\Hub\Editor\6000.5.2f1\Editor\Unity.exe'
$proj = 'F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate'
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRGateAutomation.BatchConfigureAndCapture
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRGateAutomation.BatchCaptureQuadrantHandedness
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRGateAutomation.BatchCaptureAngularWindowYawGate -grbhxrFullSkyTransferDir Assets/GRBHXR/FullSkyTransfer1024
```

The second command generates a procedural four-quadrant cubemap and captures a
screen-space square-gate image used to check that the RenderTexture screenshot
path has not flipped the new `ComputeScreenPos` sampling vertically.

The third command is the current background-lensing desktop precheck. The
`-grbhxrFullSkyTransferDir` package supplies the traced cubemap for every view
ray, while the angular window positions the high-resolution local patch.

For a magnitude-sensitive direction check, run:

```powershell
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRGateAutomation.BatchCaptureProtractorBands
```

This enables `_ProbeMode` and colors the post-basis escaped direction with
10-degree polar-angle bands away from Unity `+Z`. It is designed to catch
transform-scale bugs that a quadrant sign test cannot see. The formal desktop
gate keeps the screen object at uniform `(20, 20, 20)` scale, but the physics
direction path is also protected by explicit pure rotation basis vectors rather
than `unity_ObjectToWorld` scale-bearing matrix columns.

The matching screenshot comparison script is:

```powershell
python validation/quest_pcvr/scripts/compare_protractor_gate.py --package-dir F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate\Assets\GRBHXR\LensMaps\Kerr_a09_i60_1024_to_4k_display --screenshot F:\学习和研究\GR-BH-XR\outputs\task5\unity_gate\unity_gate_protractor_square_1024.png --samples 61 --json
```

Replace the output path with the local repository path if a console renders
non-ASCII directory names incorrectly; the command is otherwise identical.
