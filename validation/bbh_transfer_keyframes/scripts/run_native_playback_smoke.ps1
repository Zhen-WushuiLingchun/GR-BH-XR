param(
    [string]$NpgsExe = "$env:LOCALAPPDATA\GRBHXR\native-build-root\runtime\NPGS\x64\Release\NPGS.exe",
    [string]$OutDir = "outputs\task11\native_playback_fixture"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "project Python environment is missing: $Python"
}
if (-not (Test-Path -LiteralPath $NpgsExe -PathType Leaf)) {
    throw "NPGS Release executable is missing: $NpgsExe"
}

$OutputRoot = Join-Path $RepoRoot $OutDir
$env:PYTHONPATH = Join-Path $RepoRoot "src"
& $Python (Join-Path $PSScriptRoot "build_native_playback_fixture.py") `
    --out-dir $OutputRoot --frames 4
if ($LASTEXITCODE -ne 0) {
    throw "native playback fixture generation failed with exit code $LASTEXITCODE"
}

$Manifest = Join-Path $OutputRoot "manifest.json"
$DataRoot = Join-Path $RepoRoot "runtime\NPGS\NPGS"
Push-Location $DataRoot
try {
    $Output = & $NpgsExe --windowed --width 64 --height 64 `
        --transfer-keyframes $Manifest --transfer-time-M 0.5 `
        --transfer-keyframe-smoke 2>&1
    $ExitCode = $LASTEXITCODE
    $Output | Set-Content -LiteralPath (Join-Path $OutputRoot "native_smoke.log")
    if ($ExitCode -ne 0) {
        throw "native playback smoke failed with exit code $ExitCode"
    }
    $Text = $Output -join "`n"
    $Required = @(
        "NPGS_TRANSFER_RESIDENT slot=0 frame=0",
        "NPGS_TRANSFER_RESIDENT slot=1 frame=1",
        "NPGS_TRANSFER_PREFETCH frame=2",
        "NPGS_TRANSFER_UPLOAD slot=2 frame=2 role=event role_index=0",
        "NPGS_TRANSFER_UPLOAD slot=2 frame=2 role=disk_order1_redshift role_index=5",
        "NPGS_TRANSFER_RESIDENT slot=2 frame=2",
        "NPGS_TRANSFER_STALL requested_metric_time_M=1.5 applied_metric_time_M=1 waiting_frame=2",
        "NPGS_TRANSFER_PREFETCH frame=3",
        "NPGS_TRANSFER_UPLOAD slot=0 frame=3 role=event role_index=0",
        "NPGS_TRANSFER_UPLOAD slot=0 frame=3 role=disk_order1_redshift role_index=5",
        "NPGS_TRANSFER_RESIDENT slot=0 frame=3",
        "NPGS_TRANSFER_PLAYBACK_READY face_size=4 resident_frames=2 resident_bytes=9984",
        "NPGS_TRANSFER_PLAYBACK_OK left=2 right=3 alpha=0.5 resident_frames=3 resident_bytes=14976"
    )
    foreach ($Marker in $Required) {
        if (-not $Text.Contains($Marker)) {
            throw "native playback smoke did not emit required marker: $Marker"
        }
    }

    $Rejected = & $NpgsExe --windowed --width 64 --height 64 `
        --transfer-keyframes $Manifest --transfer-time-M 4 `
        --transfer-keyframe-smoke 2>&1
    $RejectedExitCode = $LASTEXITCODE
    $Rejected | Set-Content -LiteralPath (Join-Path $OutputRoot "native_out_of_range.log")
    if ($RejectedExitCode -ne 1 -or
        -not (($Rejected -join "`n").Contains("extrapolation is forbidden"))) {
        throw "out-of-range playback did not fail closed with exit code 1"
    }
}
finally {
    Pop-Location
}

Write-Output "NPGS_TRANSFER_PLAYBACK_GATE_OK resident_frames=3 final_bracket=2/3 alpha=0.5"
