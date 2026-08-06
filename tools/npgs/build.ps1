[CmdletBinding()]
param(
    [ValidateSet("Debug", "Release", "Package")]
    [string]$Configuration = "Release",
    [ValidateSet("x64")]
    [string]$Platform = "x64",
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
$RepoRoot = Get-GrBhXrBuildRoot -Create
$DoctorJson = Join-Path $RepoRoot "outputs\npgs\doctor.json"
& (Join-Path $PSScriptRoot "doctor.ps1") -JsonOut $DoctorJson | Out-Null
if ($LASTEXITCODE -ne 0) { throw "NPGS doctor failed. See $DoctorJson" }

$Doctor = Get-Content -LiteralPath $DoctorJson -Raw | ConvertFrom-Json
function Check-Value([string]$Name) {
    return ($Doctor.checks | Where-Object name -eq $Name | Select-Object -First 1).value
}

$MSBuild = Check-Value "msbuild"
$VulkanSdk = Check-Value "vulkan_sdk"
$VcpkgExe = Check-Value "vcpkg"
$VcpkgRoot = Split-Path -Parent $VcpkgExe
$ManifestRoot = Join-Path $RepoRoot "runtime\NPGS\NPGS"
$VcpkgInstalledDir = Join-Path $ManifestRoot "vcpkg_installed"
$Solution = Join-Path $RepoRoot "runtime\NPGS\NPGS.sln"

$env:VULKAN_SDK = $VulkanSdk
$env:VCPKG_ROOT = $VcpkgRoot

if (-not $SkipDependencyInstall) {
    & $VcpkgExe install --triplet x64-windows --x-manifest-root=$ManifestRoot
    if ($LASTEXITCODE -ne 0) { throw "vcpkg dependency installation failed." }
}

& $MSBuild $Solution /m /t:Build `
    "/p:Configuration=$Configuration" `
    "/p:Platform=$Platform" `
    "/p:VcpkgRoot=$VcpkgRoot" `
    "/p:VcpkgInstalledDir=$VcpkgInstalledDir\" `
    "/p:VcpkgManifestInstall=false"
if ($LASTEXITCODE -ne 0) { throw "NPGS build failed with exit code $LASTEXITCODE." }
