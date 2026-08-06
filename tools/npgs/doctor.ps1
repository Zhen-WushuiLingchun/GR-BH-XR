[CmdletBinding()]
param(
    [string]$JsonOut
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
$PhysicalRoot = Get-GrBhXrPhysicalRoot
$RepoRoot = Get-GrBhXrBuildRoot -Create
$Checks = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [object]$Value,
        [bool]$Required = $true,
        [string]$Hint = ""
    )
    $Checks.Add([ordered]@{
        name = $Name
        ok = $Ok
        required = $Required
        value = $Value
        hint = $Hint
    })
}

function Find-MSBuild {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path -LiteralPath $vswhere) {
        $found = & $vswhere -latest -products * -requires Microsoft.Component.MSBuild -find "MSBuild\**\Bin\MSBuild.exe" | Select-Object -First 1
        if ($found) { return $found }
    }
    $fallbacks = @(
        "D:\VS2022BuildTools\MSBuild\Current\Bin\MSBuild.exe",
        "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe"
    )
    return $fallbacks | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

function Find-VulkanSdk {
    if ($env:VULKAN_SDK -and (Test-Path -LiteralPath $env:VULKAN_SDK)) {
        return (Resolve-Path -LiteralPath $env:VULKAN_SDK).Path
    }
    $roots = @("C:\VulkanSDK", "D:\VulkanSDK")
    $versions = foreach ($root in $roots) {
        if (Test-Path -LiteralPath $root) {
            Get-ChildItem -LiteralPath $root -Directory | Sort-Object Name -Descending
        }
    }
    return $versions | Select-Object -First 1 -ExpandProperty FullName
}

function Find-Vcpkg {
    $candidates = @()
    if ($env:VCPKG_ROOT) { $candidates += (Join-Path $env:VCPKG_ROOT "vcpkg.exe") }
    $candidates += (Join-Path $RepoRoot ".tools\vcpkg\vcpkg.exe")
    $command = Get-Command vcpkg -ErrorAction SilentlyContinue
    if ($command) { $candidates += $command.Source }
    return $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

$Submodule = Join-Path $RepoRoot "runtime\NPGS"
$ExpectedUpstream = "a039e6417b28d53cbd413ee8f6d64543e755aa3e"
$SubmoduleHead = $null
$UpstreamHead = $null
$IsShallow = $null
$ContainsReviewedUpstream = $false
if (Test-Path -LiteralPath (Join-Path $Submodule ".git")) {
    $value = & git -C $Submodule rev-parse HEAD 2>$null
    if ($LASTEXITCODE -eq 0) { $SubmoduleHead = $value.Trim() }
    $value = & git -C $Submodule rev-parse upstream/master 2>$null
    if ($LASTEXITCODE -eq 0) { $UpstreamHead = $value.Trim() }
    $value = & git -C $Submodule rev-parse --is-shallow-repository 2>$null
    if ($LASTEXITCODE -eq 0) { $IsShallow = $value.Trim() }
    if ($SubmoduleHead) {
        & git -C $Submodule merge-base --is-ancestor $ExpectedUpstream $SubmoduleHead 2>$null
        $ContainsReviewedUpstream = $LASTEXITCODE -eq 0
    }
}
Add-Check "npgs_submodule" ($null -ne $SubmoduleHead) $SubmoduleHead $true "Run git submodule update --init --recursive."
Add-Check "npgs_full_history" ($IsShallow -eq "false") $IsShallow $true "Fetch the complete NPGS history with git -C runtime/NPGS fetch --unshallow --tags."
Add-Check "npgs_reviewed_upstream_ref" ($UpstreamHead -eq $ExpectedUpstream) $UpstreamHead $true "Fetch upstream, review new refs, and update the recorded baseline before continuing."
Add-Check "npgs_upstream_ancestry" $ContainsReviewedUpstream $SubmoduleHead $true "The integration commit must descend from the reviewed upstream baseline."

$MSBuild = Find-MSBuild
Add-Check "msbuild" ($null -ne $MSBuild) $MSBuild $true "Install Visual Studio 2022 C++ Build Tools."

$WindowsSdkRoots = @(
    "C:\Program Files (x86)\Windows Kits\10\Include",
    "D:\Windows Kits\10\Include"
)
$WindowsSdk = $WindowsSdkRoots | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
Add-Check "windows_sdk" ($null -ne $WindowsSdk) $WindowsSdk $true "Install a Windows 10/11 SDK with the C++ toolchain."

$VulkanSdk = Find-VulkanSdk
Add-Check "vulkan_sdk" ($null -ne $VulkanSdk) $VulkanSdk $true "Install KhronosGroup.VulkanSDK with winget or LunarG."

$Vcpkg = Find-Vcpkg
Add-Check "vcpkg" ($null -ne $Vcpkg) $Vcpkg $true "Run tools/npgs/bootstrap.ps1 -BootstrapVcpkg."

$VulkanInfo = $null
if ($VulkanSdk) {
    $candidate = Join-Path $VulkanSdk "Bin\vulkaninfo.exe"
    if (Test-Path -LiteralPath $candidate) { $VulkanInfo = $candidate }
}
if (-not $VulkanInfo) {
    $command = Get-Command vulkaninfo -ErrorAction SilentlyContinue
    if ($command) { $VulkanInfo = $command.Source }
}
$AdapterSummary = $null
if ($VulkanInfo) {
    $AdapterSummary = (& $VulkanInfo --summary 2>$null | Select-String -Pattern "deviceName" | ForEach-Object { $_.Line.Trim() }) -join "; "
}
Add-Check "vulkan_adapter" (-not [string]::IsNullOrWhiteSpace($AdapterSummary)) $AdapterSummary $true "Verify the NVIDIA Vulkan driver and vulkaninfo."

$Ready = -not ($Checks | Where-Object { $_.required -and -not $_.ok })
$Result = [ordered]@{
    schema = "gr-bh-xr.npgs.doctor.v1"
    ready = $Ready
    repository = $RepoRoot
    physicalRepository = $PhysicalRoot
    checks = $Checks
}
$Json = $Result | ConvertTo-Json -Depth 6
$Json

if ($JsonOut) {
    $Parent = Split-Path -Parent $JsonOut
    if ($Parent) { New-Item -ItemType Directory -Force -Path $Parent | Out-Null }
    Set-Content -LiteralPath $JsonOut -Value $Json -Encoding utf8
}

if (-not $Ready) { exit 1 }
