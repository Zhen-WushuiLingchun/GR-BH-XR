param(
    [string]$NpgsExe = "$env:LOCALAPPDATA\GRBHXR\native-build-root\runtime\NPGS\x64\Release\NPGS.exe",
    [string]$OutDir = "outputs\task11\native_playback_probe",
    [int]$FaceSize = 8
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
if ($FaceSize -le 0) { throw "FaceSize must be positive" }

$OutputRoot = Join-Path $RepoRoot $OutDir
$env:PYTHONPATH = Join-Path $RepoRoot "src"
& $Python (Join-Path $PSScriptRoot "build_native_playback_fixture.py") `
    --out-dir $OutputRoot --face-size $FaceSize --spatial-probe
if ($LASTEXITCODE -ne 0) { throw "spatial probe fixture generation failed" }

$Manifest = Join-Path $OutputRoot "manifest.json"
$Raw = Join-Path $OutputRoot "native_transfer_probe.bin"
$Summary = Join-Path $OutputRoot "native_transfer_probe_summary.json"
$DataRoot = Join-Path $RepoRoot "runtime\NPGS\NPGS"
Push-Location $DataRoot
try {
    & $NpgsExe --windowed --width (6 * $FaceSize) --height $FaceSize `
        --transfer-keyframes $Manifest --transfer-time-M 0.5 `
        --transfer-probe-out $Raw
    if ($LASTEXITCODE -ne 0) { throw "native transfer probe failed" }
}
finally {
    Pop-Location
}

& $Python (Join-Path $PSScriptRoot "compare_native_playback_probe.py") `
    --raw $Raw --manifest $Manifest --out $Summary
if ($LASTEXITCODE -ne 0) { throw "native transfer probe comparison failed" }
Write-Output "NPGS_TRANSFER_PROBE_GATE_OK face_size=$FaceSize summary=$Summary"
