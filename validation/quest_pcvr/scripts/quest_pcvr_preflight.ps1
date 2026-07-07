param(
    [string] $UnityExe = "D:\unity\Hub\Editor\6000.5.2f1\Editor\Unity.exe",
    [string] $UnityProject = "F:\UnityProjects\GRBHXR_PCVR_Gate\GRBHXR_PCVR_Gate",
    [string] $FullSkyTransferDir = "Assets\GRBHXR\FullSkyTransfer1024",
    [switch] $Json
)

$ErrorActionPreference = "Stop"

function Resolve-ExistingCommand {
    param([string[]] $Candidates)
    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    $command = Get-Command adb.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    return $null
}

function Add-Check {
    param(
        [System.Collections.Specialized.OrderedDictionary] $Target,
        [string] $Name,
        [bool] $Ok,
        [string] $Detail
    )
    $Target[$Name] = [ordered]@{
        ok = $Ok
        detail = $Detail
    }
}

$checks = [ordered]@{}

Add-Check $checks "unity_exe" (Test-Path -LiteralPath $UnityExe) $UnityExe
Add-Check $checks "unity_project" (Test-Path -LiteralPath $UnityProject) $UnityProject

$packagePath = Join-Path $UnityProject $FullSkyTransferDir
Add-Check $checks "full_sky_transfer_dir" (Test-Path -LiteralPath $packagePath) $packagePath

$requiredPackageFiles = @(
    "full_sky_transfer_metadata.json",
    "event_cube_rgba8.bytes",
    "escape_dir_unity_cube_rgba32f.bytes"
)
foreach ($fileName in $requiredPackageFiles) {
    $path = Join-Path $packagePath $fileName
    Add-Check $checks "full_sky_$fileName" (Test-Path -LiteralPath $path) $path
}

$androidHomeAdb = if ($env:ANDROID_HOME) {
    Join-Path $env:ANDROID_HOME "platform-tools\adb.exe"
} else {
    $null
}
$localSdkAdb = Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools\adb.exe"
$adb = Resolve-ExistingCommand @($androidHomeAdb, $localSdkAdb)
$adbDetail = if ($adb) { $adb } else { "adb.exe not found on PATH or common SDK locations" }
Add-Check $checks "adb_found" ($adb -ne $null) $adbDetail

$adbDevices = @()
if ($adb) {
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $adbDevices = & $adb devices -l 2>&1 | ForEach-Object { $_.ToString() }
        $adbOk = $LASTEXITCODE -eq 0
        Add-Check $checks "adb_devices" $adbOk (($adbDevices -join "`n").Trim())
    } finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }
} else {
    Add-Check $checks "adb_devices" $false "Skipped because adb.exe was not found."
}

$questUsb = @()
try {
    $questUsb = Get-PnpDevice -ErrorAction Stop |
        Where-Object {
            $_.InstanceId -like "*VID_2833*" -or
            $_.FriendlyName -match "Quest|Meta|Oculus|XRSP"
        } |
        Select-Object -First 10 -Property Status, Class, FriendlyName, InstanceId
    Add-Check $checks "quest_usb_pnp" ($questUsb.Count -gt 0) (($questUsb | Format-List | Out-String).Trim())
} catch {
    Add-Check $checks "quest_usb_pnp" $false "Get-PnpDevice failed: $($_.Exception.Message)"
}

$result = [ordered]@{
    timestamp = (Get-Date).ToString("s")
    unityExe = $UnityExe
    unityProject = $UnityProject
    fullSkyTransferDir = $FullSkyTransferDir
    adb = $adb
    checks = $checks
}

if ($Json) {
    $result | ConvertTo-Json -Depth 6
} else {
    "GR-BH-XR Quest PCVR preflight"
    "Unity: $UnityExe"
    "Project: $UnityProject"
    "Full-sky transfer: $packagePath"
    ""
    foreach ($key in $checks.Keys) {
        $status = if ($checks[$key].ok) { "OK" } else { "WARN" }
        "[$status] $key"
        "  $($checks[$key].detail)"
    }
}
