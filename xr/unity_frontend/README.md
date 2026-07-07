# Unity PCVR Static Texture Bridge

This directory is a Unity package scaffold for Task 5. It consumes exported
GPU lens-map textures; it does not run geodesic integration inside Unity or on
the headset.

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
