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
- Camera clear flags: `Skybox`
- Camera vertical FOV: `2 atan(8 / 100) = 9.1478 deg`

The screen-space gate is the accepted desktop check for import, cubemap
binding, square-map aspect, handedness, and Kerr shadow morphology. It is not a
head-motion-stability result.

## Command

```powershell
$unity = 'D:\unity\Hub\Editor\6000.5.2f1\Editor\Unity.exe'
$proj = 'F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate'
$log = 'F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate\Logs\gate_batch_regular.log'
& $unity -batchmode -quit -projectPath $proj -executeMethod GRBHXRGateAutomation.BatchConfigureAndCapture -logFile $log
```

Latest log markers:

```text
GR-BH-XR gate configured: fov=9.1478 deg, r_obs=100.000, beta=[-8.000,8.000].
GRBHXRGateAutomation:ConfigureScreenSpaceGatePreview ()
GR-BH-XR gate capture wrote F:/学习和研究/GR-BH-XR/outputs/task5/unity_gate\unity_gate_square_2048.png
GR-BH-XR gate capture wrote F:/学习和研究/GR-BH-XR/outputs/task5/unity_gate\unity_gate_wide_1920x1080.png
Application will terminate with return code 0
```

## Outputs

Generated screenshots are kept under ignored `outputs/`:

```text
F:\学习和研究\GR-BH-XR\outputs\task5\unity_gate\unity_gate_square_2048.png
F:\学习和研究\GR-BH-XR\outputs\task5\unity_gate\unity_gate_wide_1920x1080.png
```

The square output is the primary physics-facing desktop gate. The wide output
shows the square gate centered in a 16:9 frame, with direct skybox sampling
outside the square gate; this avoids artificially stretching the square
`alpha/beta` transfer map.

## Result

- The Unity material binds the real-sky cubemap rather than a gray fallback.
- The black-hole shadow is not stretched into the Game-view aspect ratio.
- The high-spin Kerr shadow keeps the expected horizontal asymmetry and
  frame-dragging distortion.
- The square gate removes the billboard perspective ellipse seen in earlier
  screenshots.

## Open Items

- The opt-in `_UseAngularWindow` / full-camera path still needs separate Unity
  and Quest validation before head-rotation stability can be claimed.
- Quest PCVR runtime checks remain pending: frame pacing, stereo behavior,
  headset anchoring, angular-size recording, and latency observations.
