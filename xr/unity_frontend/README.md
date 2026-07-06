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

The preview shader samples the Unity-space direction texture for escaped rays
and falls back to `event_rgba8` for capture or invalid pixels.

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

## Current Scope

This package is a static texture bridge:

- geodesics are generated offline by the Python GPU/CPU tools;
- Task 5 uses the texture contract for PCVR/MR display experiments;
- stereo disparity, head-motion stability, 72/90 Hz timing, black-hole angular
  size, and PC-to-Quest latency are validation tasks, not claims made by this
  package.
