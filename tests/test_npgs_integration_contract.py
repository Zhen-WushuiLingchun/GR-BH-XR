from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_npgs_is_a_pinned_submodule_with_documented_upstream() -> None:
    modules = (ROOT / ".gitmodules").read_text(encoding="utf8")
    notice = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf8")
    migration = (ROOT / "docs" / "npgs_native_migration.md").read_text(encoding="utf8")

    assert "runtime/NPGS" in modules
    assert "Zhen-WushuiLingchun/NPGS.git" in modules
    assert "codex/npgs-integration" in modules
    assert "a039e6417b28d53cbd413ee8f6d64543e755aa3e" in notice
    assert "baopinshui/NPGS" in migration
    assert "showcase media" in migration.lower()


def test_npgs_build_tools_fail_closed_and_stay_local() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf8")
    doctor = (ROOT / "tools" / "npgs" / "doctor.ps1").read_text(encoding="utf8")
    build = (ROOT / "tools" / "npgs" / "build.ps1").read_text(encoding="utf8")
    benchmark = (ROOT / "tools" / "npgs" / "benchmark.ps1").read_text(encoding="utf8")
    audit = (ROOT / "tools" / "npgs" / "audit.ps1").read_text(encoding="utf8")
    common = (ROOT / "tools" / "npgs" / "common.ps1").read_text(encoding="utf8")

    assert ".tools/" in ignore
    assert 'schema = "gr-bh-xr.npgs.doctor.v1"' in doctor
    assert "if (-not $Ready) { exit 1 }" in doctor
    assert 'Add-Check "npgs_full_history"' in doctor
    assert 'Add-Check "npgs_reviewed_upstream_ref"' in doctor
    assert 'Add-Check "npgs_upstream_ancestry"' in doctor
    bootstrap = (ROOT / "tools" / "npgs" / "bootstrap.ps1").read_text(encoding="utf8")
    assert "KhronosGroup.VulkanSDK" in bootstrap
    assert "git -C $NpgsRoot fetch --unshallow origin --tags" in bootstrap
    assert "git -C $NpgsRoot fetch upstream --tags --prune" in bootstrap
    assert "vcpkg dependency installation failed" in build
    assert '"/p:VcpkgInstalledDir=$VcpkgInstalledDir\\"' in build
    assert '"/p:VcpkgManifestInstall=false"' in build
    assert 'schema = "gr-bh-xr.npgs.performance.v1"' in benchmark
    assert '"--benchmark"' in benchmark
    assert "NPGS_BENCHMARK_FRAMEBUFFER" in benchmark
    assert "NPGS_BENCHMARK_FPS" in benchmark
    assert "Framebuffer mismatch" in benchmark
    assert "upstreamSha" in benchmark
    assert "forkSha" in benchmark
    assert "verifiedExact = $true" in benchmark
    assert '"GRBHXR\\audit"' in audit
    assert "NPGS exited without producing both" in audit
    assert "Native audit byte length mismatch" in audit
    assert "framebufferWidthEstimate" not in benchmark
    assert "native-build-root" in common
    assert 'LinkType -ne "Junction"' in common


def test_npgs_native_benchmark_mode_reports_internal_metrics() -> None:
    main = (
        ROOT
        / "runtime"
        / "NPGS"
        / "NPGS"
        / "Sources"
        / "Program"
        / "main.cpp"
    ).read_text(encoding="utf8")
    application = (
        ROOT
        / "runtime"
        / "NPGS"
        / "NPGS"
        / "Sources"
        / "Program"
        / "Application.cpp"
    ).read_text(encoding="utf8")

    assert 'Argument == "--benchmark"' in main
    assert '_putenv_s("NPGS_HIDDEN_WINDOW", "1")' in main
    assert '_putenv_s("NPGS_LOG_FPS", "1")' in main
    assert "glfwWindowHint(GLFW_VISIBLE, GLFW_FALSE)" in application
    assert '"NPGS_BENCHMARK_FRAMEBUFFER "' in application
    assert '"NPGS_BENCHMARK_FPS "' in application


def test_npgs_disk_audit_uses_killing_constants_for_redshift() -> None:
    shader = (
        ROOT
        / "runtime"
        / "NPGS"
        / "NPGS"
        / "Sources"
        / "Engine"
        / "Shaders"
        / "BlackHole_common.glsl"
    ).read_text(encoding="utf8")

    assert "AuditAngularMomentumY(\n        gAudit.InitialIngoingX, gAudit.InitialIngoingP)" in shader
    assert "float killingEnergy = -gAudit.InitialIngoingP.w;" in shader
    assert "float angularMomentum = hitX.z * hitP.x - hitX.x * hitP.z;" not in shader


def test_repository_includes_gpl_v3_text() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf8")
    assert "GNU GENERAL PUBLIC LICENSE" in license_text
    assert "Version 3, 29 June 2007" in license_text


def test_npgs_native_xr_contract_is_device_independent_and_fail_closed() -> None:
    npgs = ROOT / "runtime" / "NPGS" / "NPGS"
    manifest = (npgs / "vcpkg.json").read_text(encoding="utf8")
    render_contract = (
        npgs / "Sources" / "Engine" / "Core" / "Runtime" / "XR" / "RenderContract.h"
    ).read_text(encoding="utf8")
    openxr_header = (
        npgs / "Sources" / "Engine" / "Core" / "Runtime" / "XR" / "OpenXrRuntime.h"
    ).read_text(encoding="utf8")
    openxr_source = (
        npgs / "Sources" / "Engine" / "Core" / "Runtime" / "XR" / "OpenXrRuntime.cpp"
    ).read_text(encoding="utf8")
    application = (npgs / "Sources" / "Program" / "Application.cpp").read_text(encoding="utf8")

    assert '"name": "openxr-loader"' in manifest
    assert '"vulkan"' in manifest
    assert "RequiredViewCount = 2" in render_contract
    assert "FViewFovTangents" in render_contract
    assert "MetersPerM" in render_contract
    assert "OpenXrOwned" in render_contract
    assert "OpenXR render sink requires OpenXR-owned Vulkan handles" in (
        npgs / "Sources" / "Engine" / "Core" / "Runtime" / "XR" / "RenderContract.cpp"
    ).read_text(encoding="utf8")
    assert "PFN_xrEnumerateInstanceExtensionProperties" in openxr_header
    assert "EnumerateExtensions(nullptr" in openxr_source
    assert "xrEnumerateInstanceExtensionProperties(nullptr" not in openxr_source
    assert "glfwCreateWindowSurface" in application
    assert "_VulkanContext->CreateDevice(0)" in application


def test_npgs_mr_contract_requires_measured_calibrated_frame_provenance() -> None:
    source = (
        ROOT
        / "runtime"
        / "NPGS"
        / "NPGS"
        / "Sources"
        / "Engine"
        / "Core"
        / "Runtime"
        / "XR"
        / "MixedRealityContract.cpp"
    ).read_text(encoding="utf8")
    docs = (ROOT / "runtime" / "NPGS" / "docs" / "GRBHXR_OPENXR.md").read_text(
        encoding="utf8"
    )

    assert "!Fresh || !Calibrated" in source
    assert "NativeImage == 0" in source
    assert '"forward_camera_only"' in source
    assert '"calibrated_full_sphere"' in source
    assert "cannot provide the radiance behind the observer" in " ".join(docs.lower().split())
    normalized_docs = " ".join(docs.split())
    assert "Depth acquisition does not prove RGB delivery" in normalized_docs
