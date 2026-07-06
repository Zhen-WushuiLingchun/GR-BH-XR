# 2026-07-06 Unity Editor Desktop Gate

## Scope

This note records the desktop Unity Editor gate for the Task 5 static texture
bridge. It uses the formal Unity project:

```text
F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate
```

No temporary Unity project or lightweight copy is used for this gate.

## Configuration

- Unity: `6000.5.2f1`
- Unity executable: `D:\unity\Hub\Editor\6000.5.2f1\Editor\Unity.exe`
- Scene: `Assets/Scenes/GRBHXR_KerrLensPreview.unity`
- Lens package: `Assets/GRBHXR/LensMaps/Kerr_a09_i60_1024_to_4k_display`
- Skybox: `Assets/GRBHXR/Skyboxes/NASA_DeepStarMap2020.cubemap`
- Preview material: `Assets/GRBHXR/Materials/M_KerrLensPreview.mat`
- Shader: `GR-BH-XR/Kerr Lens Static Preview`
- Preview mode: screen-space square gate, `_UseAngularWindow = 0`
- LensScreen scale: `(20, 20, 20)` uniform in the formal gate scene. The shader
  does not rely on scale-bearing object matrices for physics directions:
  `BlackHoleLensMap` writes explicit pure rotation basis vectors
  `_LensWorldRight`, `_LensWorldUp`, and `_LensWorldForward`.
- Runtime basis refresh: `BlackHoleLensMaterialBinder` refreshes those basis
  vectors in `LateUpdate` by default, so a later recenter or anchor rotation
  does not leave stale material vectors.
- Camera clear flags: `Skybox`
- Camera vertical FOV: `2 atan(8 / 100) = 9.1478 deg`

The screen-space gate is the accepted desktop check for import, cubemap
binding, square-map aspect, handedness, and Kerr shadow morphology. It is not a
head-motion-stability result.

## Commands

```powershell
$unity = 'D:\unity\Hub\Editor\6000.5.2f1\Editor\Unity.exe'
$proj = 'F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate'
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRGateAutomation.BatchConfigureAndCapture -logFile (Join-Path $proj 'Logs\gate_batch_final_nasa.log')
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRGateAutomation.BatchCaptureQuadrantHandedness -logFile (Join-Path $proj 'Logs\gate_batch_final_quadrant.log')
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXR.EditorTools.GRBHXRGateAutomation.BatchCaptureProtractorBands -logFile (Join-Path $proj 'Logs\gate_batch_protractor_final3.log')
```

Latest log marker for the NASA gate:

```text
GR-BH-XR gate configured: fov=9.1478 deg, r_obs=100.000, beta=[-8.000,8.000], skyboxKind=Nasa, angularWindow=False, lossyScale=(20.00, 20.00, 20.00), probeMode=0.0, basisR=(1.00, 0.00, 0.00, 0.00), basisU=(0.00, 1.00, 0.00, 0.00), basisF=(0.00, 0.00, 1.00, 0.00).
Application will terminate with return code 0
```

The capture method is versioned in the Unity package as:

```text
xr/unity_frontend/Editor/GRBHXRGateAutomation.cs
```

## Outputs

Generated screenshots are kept under ignored `outputs/`:

```text
F:\学习和研究\GR-BH-XR\outputs\task5\unity_gate\unity_gate_square_2048.png
F:\学习和研究\GR-BH-XR\outputs\task5\unity_gate\unity_gate_wide_1920x1080.png
F:\学习和研究\GR-BH-XR\outputs\task5\unity_gate\unity_gate_quadrant_square_1024.png
F:\学习和研究\GR-BH-XR\outputs\task5\unity_gate\unity_gate_quadrant_wide_1920x1080.png
F:\学习和研究\GR-BH-XR\outputs\task5\unity_gate\unity_gate_protractor_square_1024.png
F:\学习和研究\GR-BH-XR\outputs\task5\unity_gate\unity_gate_protractor_wide_1920x1080.png
```

The square output is the primary physics-facing desktop gate. The wide output
shows the square gate centered in a 16:9 frame, with direct skybox sampling
outside the square gate; this avoids artificially stretching the square
`alpha/beta` transfer map.

## Handedness Check

The package automation generated a procedural four-quadrant cubemap and
captured the screen-space square gate through the same Unity batchmode
RenderTexture path.

The quadrant cubemap encodes Unity direction signs:

```text
x >= 0, y >= 0 -> red
x <  0, y >= 0 -> green
x <  0, y <  0 -> blue
x >= 0, y <  0 -> yellow
```

Six off-boundary screenshot samples were compared against
`escape_dir_unity_rgba32f.bytes` using both possible vertical interpretations
of the RenderTexture screenshot path:

```text
matches_no_vflip = 6 / 6
matches_vflip    = 0 / 6
```

This closes the screen-space path evidence gap introduced by the switch from
quad UV sampling to `ComputeScreenPos`.

## Protractor Magnitude Check

The quadrant cubemap is a sign test and is blind to positive non-uniform
scales. The protractor gate sets `_ProbeMode = 1`, and the shader colors the
post-basis escaped direction by polar angle away from Unity `+Z` in 10 degree
bands. This directly tests the same direction path used for cubemap lookup,
without depending on cubemap face orientation.

Latest log marker:

```text
GR-BH-XR gate configured: fov=9.1478 deg, r_obs=100.000, beta=[-8.000,8.000], skyboxKind=Protractor, angularWindow=False, lossyScale=(20.00, 20.00, 20.00), probeMode=1.0, basisR=(1.00, 0.00, 0.00, 0.00), basisU=(0.00, 1.00, 0.00, 0.00), basisF=(0.00, 0.00, 1.00, 0.00).
Application will terminate with return code 0
```

The screenshot was sampled at escaped pixels and compared with the expected
10-degree band from `escape_dir_unity_rgba32f.bytes`. The PNG was decoded from
sRGB back to linear before reading the encoded band. The correct screenshot row
mapping is `u = x`, `v = 1 - y`, matching the exported texture convention.
The comparison is versioned as:

```powershell
$env:PYTHONPATH='src'
python validation/quest_pcvr/scripts/compare_protractor_gate.py --package-dir F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate\Assets\GRBHXR\LensMaps\Kerr_a09_i60_1024_to_4k_display --screenshot F:\学习和研究\GR-BH-XR\outputs\task5\unity_gate\unity_gate_protractor_square_1024.png --samples 61 --json
```

Two hypotheses were tested on a 61 by 61 screen lattice:

```text
raw direction, no scale skew:
  valid = 2058, exact = 2004, closer = 2048, mean_abs_band_error = 0.027

old non-uniform scale (x,y)*20 skew:
  valid = 2058, exact = 10, closer = 10, mean_abs_band_error = 3.255
```

This closes the magnitude evidence gap: the screen-space gate now preserves the
direction-vector amplitude, not only the sign. The shader uses explicit pure
rotation basis vectors rather than `unity_ObjectToWorld` scale-bearing matrix
columns, so non-uniform object scale cannot skew escaped-ray directions.

## Result

- The Unity material binds the real-sky cubemap rather than a gray fallback.
- The black-hole shadow is not stretched into the Game-view aspect ratio.
- The high-spin Kerr shadow keeps the expected horizontal asymmetry and
  frame-dragging distortion.
- The square gate removes the billboard perspective ellipse seen in earlier
  screenshots.
- The batchmode screenshot path preserves the vertical screen-space direction
  for the new `ComputeScreenPos` sampling path.
- The protractor check confirms that escaped-ray direction amplitudes are not
  skewed before cubemap lookup.

## Open Items

- The opt-in `_UseAngularWindow` / full-camera path still needs separate Unity
  and Quest validation before head-rotation stability can be claimed.
- Quest PCVR runtime checks remain pending: frame pacing, stereo behavior,
  headset anchoring, angular-size recording, and latency observations.
