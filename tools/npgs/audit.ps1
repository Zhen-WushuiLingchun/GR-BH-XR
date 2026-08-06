[CmdletBinding()]
param(
    [ValidateRange(1, 16384)]
    [int]$Width = 65,
    [ValidateRange(1, 16384)]
    [int]$Height = 65,
    [Parameter(Mandatory = $true)]
    [string]$Out,
    [ValidateRange(-1.0, 1.0)]
    [double]$Spin = 0.9,
    [ValidateRange(-1.0, 1.0)]
    [double]$Charge = 0.0,
    [ValidateRange(0.01, 179.99)]
    [double]$InclinationDeg = 60.0,
    [ValidateRange(1.0, 1000000.0)]
    [double]$RObsM = 100.0,
    [ValidateRange(0.01, 179.0)]
    [double]$FovDeg = 40.0,
    [ValidateRange(0.1, 32.0)]
    [double]$Quality = 2.0,
    [ValidateRange(0.0, 1000000.0)]
    [double]$DiskRInM = 6.0,
    [ValidateRange(0.0, 1000000.0)]
    [double]$DiskROutM = 30.0
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
$BuildRoot = Get-GrBhXrBuildRoot -Create
$PhysicalRoot = Get-GrBhXrPhysicalRoot
$NpgsRoot = Join-Path $BuildRoot "runtime\NPGS"
$Executable = Join-Path $NpgsRoot "x64\Release\NPGS.exe"
$WorkingDirectory = Join-Path $NpgsRoot "NPGS"

if (-not (Test-Path -LiteralPath $Executable)) {
    throw "NPGS Release executable was not found. Run tools/npgs/build.ps1 first."
}
if ($Spin * $Spin + $Charge * $Charge -gt 1.0) {
    throw "The native audit requires spin^2 + charge^2 <= 1."
}
if ($DiskROutM -le $DiskRInM) {
    throw "DiskROutM must be greater than DiskRInM."
}

$Destination = [System.IO.Path]::GetFullPath($Out, $PhysicalRoot)
$DestinationParent = Split-Path -Parent $Destination
if ($DestinationParent) {
    New-Item -ItemType Directory -Force -Path $DestinationParent | Out-Null
}

# NPGS currently receives CLI paths through narrow strings. Generate in an
# ASCII-only local directory, verify both files, then copy to the requested
# project path so Chinese workspace names cannot silently retain stale data.
$TempRoot = Join-Path $env:LOCALAPPDATA "GRBHXR\audit"
New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
$TempRaw = Join-Path $TempRoot ("audit_" + [Guid]::NewGuid().ToString("N") + ".bin")
$Arguments = @(
    "--width", "$Width",
    "--height", "$Height",
    "--audit-out", $TempRaw,
    "--spin", "$Spin",
    "--charge", "$Charge",
    "--inclination-deg", "$InclinationDeg",
    "--r-obs", "$RObsM",
    "--fov-deg", "$FovDeg",
    "--quality", "$Quality",
    "--disk-r-in", "$DiskRInM",
    "--disk-r-out", "$DiskROutM"
)

Push-Location $WorkingDirectory
try {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "NPGS audit failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

$TempMetadata = "$TempRaw.json"
if (-not (Test-Path -LiteralPath $TempRaw) -or -not (Test-Path -LiteralPath $TempMetadata)) {
    throw "NPGS exited without producing both the raw audit and metadata sidecar."
}
$Metadata = Get-Content -LiteralPath $TempMetadata -Raw | ConvertFrom-Json
$ExpectedBytes = [int64]$Width * [int64]$Height * [int64]$Metadata.record_bytes
$ActualBytes = (Get-Item -LiteralPath $TempRaw).Length
if ($ActualBytes -ne $ExpectedBytes) {
    throw "Native audit byte length mismatch: expected $ExpectedBytes, got $ActualBytes."
}

Copy-Item -LiteralPath $TempRaw -Destination $Destination -Force
Copy-Item -LiteralPath $TempMetadata -Destination "$Destination.json" -Force
Remove-Item -LiteralPath $TempRaw, $TempMetadata -Force

[ordered]@{
    raw = $Destination
    metadata = "$Destination.json"
    schema = $Metadata.schema
    width = $Metadata.width
    height = $Metadata.height
    bytes = $ActualBytes
} | ConvertTo-Json
