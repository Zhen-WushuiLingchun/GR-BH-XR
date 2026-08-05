# Meta Passthrough Camera Backend Review

- Review date: 2026-07-18
- Search terms: Meta Quest passthrough camera API Unity MRUK Horizon Link
- Classification: official engineering documentation and official sample code

## Sources

- Meta Passthrough Camera API overview:
  https://developers.meta.com/horizon/documentation/unity/unity-pca-overview/
- Official Unity sample repository:
  https://github.com/oculus-samples/Unity-PassthroughCameraApiSamples
- Reviewed sample commit:
  https://github.com/oculus-samples/Unity-PassthroughCameraApiSamples/commit/ea3ae8367046d16029206aba5fb03e917a177aca
- Unity 6000.0.76f1 release:
  https://unity.com/releases/editor/whats-new/6000.0.76f1
- License: Oculus SDK License for the Meta sample and MRUK package unless a
  file states otherwise. No Meta source is copied into this repository.

## Why This Source Was Added

The Windows virtual camera named `Meta Quest 3` could be enumerated through
Unity `WebCamTexture`, but repeated device runs never produced a real frame:
the texture stayed at Unity's 16-pixel placeholder. The official sample uses
MRUK `Meta.XR.PassthroughCameraAccess`, which consumes the Meta passthrough
camera extension and exposes the frame texture together with capture-time pose
and calibrated intrinsics. Raw `WebCamTexture` enumeration is therefore not an
acceptance signal and is retained only as a diagnostic fallback.

## Reviewed Interface

The reviewed MRUK 85 implementation exposes:

- `IsPlaying` and `IsUpdatedThisFrame` frame-delivery state;
- `GetTexture()` for the GPU camera texture;
- `CurrentResolution`;
- `CameraIntrinsics.FocalLength`, `PrincipalPoint`, `SensorResolution`, and
  `LensOffset`;
- `GetCameraPose()` evaluated at the camera frame timestamp;
- left/right camera selection and requested resolution/frame rate.

These values support a calibrated directional projection. They do not by
themselves provide missing radiance behind the user, nor do they make acquired
environment depth equivalent to depth-aware shader occlusion.

## Local Compatibility Result

- Unity editor: `6000.0.76f1`.
- MRUK: `85.0.0`.
- Official sample: clean batch compile at reviewed commit.
- Formal project: clean batch compile after migration from Unity `6000.5.2f1`
  to `6000.0.76f1` and package alignment (`URP 17.0.4`, `UGUI 2.0.0`).
- Reflection contract gate: found `Meta.XR.PassthroughCameraAccess` and all
  required fields, properties, and methods.
- Local ignored logs:
  `outputs/task10/unity_compile_official_pca_sample_mruk85_6000.0.76.log`,
  `outputs/task10/unity_compile_formal_mruk85_6000.0.76_retry2.log`, and
  `outputs/task10/unity_validate_mruk85_contract_6000.0.76.log`.

MRUK 85 and 203 were also tested under Unity `6000.5.2f1`; package-owned code
failed on Unity APIs made hard-obsolete in that editor line. The project does
not patch or vendor the package to bypass this incompatibility.

## Remaining Gate

The implementation cannot claim live camera-pixel lensing until a connected
Quest/Link run records a delivered MRUK frame and a calibrated target verifies
orientation, principal-point alignment, and stability under head rotation.
Environment-depth shader consumption and compositor underlay registration are
separate later gates.
