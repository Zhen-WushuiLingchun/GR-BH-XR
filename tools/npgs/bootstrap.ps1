[CmdletBinding()]
param(
    [switch]$InstallVulkanSdk,
    [switch]$BootstrapVcpkg
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
$RepoRoot = Get-GrBhXrBuildRoot -Create
$ToolsRoot = Join-Path $RepoRoot ".tools"
$VcpkgRoot = Join-Path $ToolsRoot "vcpkg"
$VcpkgCommit = "782419385291ae2db643c928314efe626853c702"
$NpgsRoot = Join-Path $RepoRoot "runtime\NPGS"

& git -C $RepoRoot submodule update --init --recursive
if ($LASTEXITCODE -ne 0) { throw "Unable to initialize the NPGS submodule." }

$upstreamUrl = "https://github.com/baopinshui/NPGS.git"
$upstreamRemote = & git -C $NpgsRoot remote get-url upstream 2>$null
if ($LASTEXITCODE -ne 0) {
    & git -C $NpgsRoot remote add upstream $upstreamUrl
    if ($LASTEXITCODE -ne 0) { throw "Unable to add the official NPGS upstream remote." }
}
elseif ($upstreamRemote.Trim() -ne $upstreamUrl) {
    throw "The NPGS upstream remote has an unexpected URL: $($upstreamRemote.Trim())"
}

$isShallow = (& git -C $NpgsRoot rev-parse --is-shallow-repository).Trim()
if ($isShallow -eq "true") {
    & git -C $NpgsRoot fetch --unshallow origin --tags
}
else {
    & git -C $NpgsRoot fetch origin --tags --prune
}
if ($LASTEXITCODE -ne 0) { throw "Unable to fetch the complete NPGS fork history." }
& git -C $NpgsRoot fetch upstream --tags --prune
if ($LASTEXITCODE -ne 0) { throw "Unable to fetch the official NPGS upstream refs." }

if ($InstallVulkanSdk) {
    $winget = Get-Command winget -ErrorAction Stop
    & $winget.Source install --id KhronosGroup.VulkanSDK --exact --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "Vulkan SDK installation failed with exit code $LASTEXITCODE." }
}

if ($BootstrapVcpkg) {
    New-Item -ItemType Directory -Force -Path $ToolsRoot | Out-Null
    if (-not (Test-Path -LiteralPath (Join-Path $VcpkgRoot ".git"))) {
        & git init $VcpkgRoot
        & git -C $VcpkgRoot remote add origin https://github.com/microsoft/vcpkg.git
    }
    & git -C $VcpkgRoot fetch --depth 1 origin $VcpkgCommit
    if ($LASTEXITCODE -ne 0) { throw "Unable to fetch pinned vcpkg commit." }
    & git -C $VcpkgRoot checkout --detach FETCH_HEAD
    & (Join-Path $VcpkgRoot "bootstrap-vcpkg.bat") -disableMetrics
    if ($LASTEXITCODE -ne 0) { throw "vcpkg bootstrap failed." }
}

& (Join-Path $PSScriptRoot "doctor.ps1")
exit $LASTEXITCODE
