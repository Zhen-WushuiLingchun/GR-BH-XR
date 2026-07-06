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

Acceptance for this gate:

- `lens_map_metadata.json` records the source schema, dimensions, screen
  bounds, and Unity basis vectors.
- `event_rgba8.bytes` has exactly `width * height * 4` bytes.
- `escape_dir_unity_rgba32f.bytes` has exactly `width * height * 16` bytes and
  stores `(x_unity, y_unity, z_unity, valid_escape)`.
- The documented screen convention is `UV(0,0) -> (alpha_min, beta_min)` and
  `UV(1,1) -> (alpha_max, beta_max)`.
- The documented world convention maps positive `alpha` to Unity `+X` and the
  camera-to-black-hole direction to Unity `+Z`.
- The Unity package under `xr/unity_frontend/` can load the raw bytes into
  `TextureFormat.RGBA32` and `TextureFormat.RGBAFloat` textures.

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
