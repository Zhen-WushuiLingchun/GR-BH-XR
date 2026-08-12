from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NPGS = ROOT / "runtime" / "NPGS" / "NPGS"
CONTRACT = NPGS / "Sources/Engine/Core/Runtime/XR/TransferKeyframeContract.cpp"
HEADER = NPGS / "Sources/Engine/Core/Runtime/XR/TransferKeyframeContract.h"


def test_native_project_builds_transfer_keyframe_contract() -> None:
    project = (NPGS / "NPGS.vcxproj").read_text(encoding="utf-8")
    filters = (NPGS / "NPGS.vcxproj.filters").read_text(encoding="utf-8")
    for path in (
        "Runtime\\XR\\TransferKeyframeContract.cpp",
        "Runtime\\XR\\TransferKeyframeContract.h",
    ):
        assert path in project
        assert path in filters


def test_native_loader_repeats_content_and_gate_validation() -> None:
    implementation = CONTRACT.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    for token in (
        "BCryptOpenAlgorithmProvider",
        "Sha256File",
        "byte count changed",
        "SHA-256 changed",
        "ValidateGate",
        "gr-bh-xr.validation.transfer-frame.v1",
        "gr-bh-xr.validation.transfer-sequence.v1",
        "runtimeAssetReady is false",
        "actualMaxGapM is inconsistent",
    ):
        assert token in implementation
    assert "The Python builder remains the schema authority" in header


def test_native_bracketing_and_cli_fail_closed() -> None:
    implementation = CONTRACT.read_text(encoding="utf-8")
    main = (NPGS / "Sources/Program/main.cpp").read_text(encoding="utf-8")
    assert "extrapolation is forbidden" in implementation
    assert "--validate-transfer-keyframes" in main
    assert "LoadTransferKeyframeManifest" in main
    assert "SelectBracket" in main
    assert "ExitWithoutStaticDestruction(3)" in main
    assert "std::_Exit" not in main
    assert "::ExitProcess" in main
