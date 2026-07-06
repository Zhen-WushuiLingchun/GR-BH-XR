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
   - `escape_dir_unity_rgba32f.bytes`.
5. Add `BlackHoleLensMaterialBinder` and assign a material using
   `GR-BH-XR/Kerr Lens Static Preview`.
6. Assign a test cubemap to `_SkyboxCubemap`.

The preview shader defaults to a screen-space square gate for the current
Unity Editor desktop validation pass. The lens screen mesh should be oversized
so it covers the camera; the shader then uses screen-space coordinates to
sample a square `alpha/beta` map without stretching it to the display aspect
ratio. Pixels outside the square gate sample the cubemap directly. This is the
accepted desktop gate for checking import, cubemap binding, handedness, and
Kerr shadow morphology.

The shader still contains an opt-in `_UseAngularWindow` mode that computes the
world view ray, transforms that ray into the lens-screen object's local basis,
maps the local angular coordinates to `(alpha, beta)`, and samples the lens map
only inside the metadata screen bounds. Treat this angular mode as
experimental until it has its own Unity desktop and Quest runtime validation.

For capture/invalid pixels inside the active gate, the shader falls back to
`event_rgba8`. For escaped rays, the sampled Unity-local escape direction is
transformed by the lens-screen object's world rotation before the cubemap
lookup, so the cubemap axis stays tied to the scene instead of to raw texture
rows.

This is still a static-observer approximation. The texture assumes the metadata
`r_obs`, spin, inclination, and screen bounds used when it was generated. The
current accepted desktop gate is screen-space and does not close the Quest
head-motion-stability requirement. A full-camera or angular-window pass must be
validated before making head-rotation claims; physical head translation would
require regenerating or interpolating a different transfer map.

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

Square exported screen windows, such as `alpha,beta in [-8M, 8M]`, should be
displayed through a square gate unless the HDF5 source was generated with
matching non-square screen bounds. Stretching a square lens map to a 16:9
display turns the shadow into an artificial ellipse and is not a physics
result. In the provided desktop setup, the mesh is deliberately oversized so it
acts as a screen-space pass; the shader's square gate decides where the lens map
is active.

## Current Scope

This package is a static texture bridge:

- geodesics are generated offline by the Python GPU/CPU tools;
- Task 5 uses the texture contract for PCVR/MR display experiments;
- stereo disparity, head-motion stability, 72/90 Hz timing, black-hole angular
  size, and PC-to-Quest latency are validation tasks, not claims made by this
  package.
