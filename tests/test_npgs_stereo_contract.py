from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NPGS = ROOT / "runtime" / "NPGS" / "NPGS"


def test_native_project_builds_synthetic_stereo_scheduler() -> None:
    project = (NPGS / "NPGS.vcxproj").read_text(encoding="utf-8")
    assert "Runtime\\XR\\SyntheticStereoSink.cpp" in project
    assert "Runtime\\XR\\SyntheticStereoSink.h" in project


def test_stereo_shader_uses_distinct_projection_and_eye_origin() -> None:
    common = (NPGS / "Sources/Engine/Shaders/BlackHole_common.glsl").read_text(
        encoding="utf-8"
    )
    data = (NPGS / "Sources/Program/DataStructures.h").read_text(encoding="utf-8")
    app = (NPGS / "Sources/Program/Application.cpp").read_text(encoding="utf-8")

    for token in ("StereoFovTangents", "StereoEyeOffsetRs", "StereoMeta"):
        assert token in data
        assert f'i{token}' in common
    assert "mix(iStereoFovTangents.x, iStereoFovTangents.y" in common
    assert "RayPosWorld = -CamToBHVecVisual + EyeOffsetWorld" in common
    assert "InternalMassM /" in app
    assert "Config().MetersPerM" in app


def test_sequential_gate_disables_cross_eye_temporal_accumulation() -> None:
    app = (NPGS / "Sources/Program/Application.cpp").read_text(encoding="utf-8")
    assert "BlackHoleArgs.BlendWeight = 1.0f" in app
    assert "taa=per_eye_disabled" in app
    assert "StereoTimestampCount = 4" in app
    assert "vkGetQueryPoolResults" in app
