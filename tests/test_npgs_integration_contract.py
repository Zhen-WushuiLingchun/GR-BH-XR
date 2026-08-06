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


def test_repository_includes_gpl_v3_text() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf8")
    assert "GNU GENERAL PUBLIC LICENSE" in license_text
    assert "Version 3, 29 June 2007" in license_text
