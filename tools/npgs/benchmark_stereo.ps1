[CmdletBinding()]
param(
    [ValidateRange(1, 16384)] [int]$EyeWidth = 1832,
    [ValidateRange(1, 16384)] [int]$EyeHeight = 1920,
    [ValidateRange(0, 10000)] [int]$WarmupPairs = 30,
    [ValidateRange(10, 10000)] [int]$SamplePairs = 120,
    [ValidateRange(1.0, 178.0)] [double]$VerticalFovDegrees = 96.0,
    [ValidateRange(0.0, 0.2)] [double]$IpdMeters = 0.064,
    [ValidateRange(1.0e-9, 1.0e30)] [double]$MetersPerM = 1.0,
    [ValidateSet(0, 1)] [int]$Disk = 1,
    [ValidateSet(0, 1)] [int]$Polarization = 0,
    [string]$JsonOut
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
$BuildRoot = Get-GrBhXrBuildRoot -Create
$PhysicalRoot = Get-GrBhXrPhysicalRoot
$NpgsRoot = Join-Path $BuildRoot "runtime\NPGS"
$WorkingDirectory = Join-Path $NpgsRoot "NPGS"
$Executable = Join-Path $NpgsRoot "x64\Release\NPGS.exe"
$Python = Join-Path $BuildRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Executable)) {
    throw "NPGS Release executable was not found. Run tools/npgs/build.ps1 first."
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Workspace Python was not found at $Python."
}
if (-not $JsonOut) {
    $JsonOut = Join-Path $PhysicalRoot (
        "outputs\bbh_stereo\npgs_stereo_{0}x{1}_disk{2}_pol{3}.json" -f `
        $EyeWidth, $EyeHeight, $Disk, $Polarization)
}
$JsonOut = [System.IO.Path]::GetFullPath($JsonOut, $PhysicalRoot)
$OutputDirectory = Split-Path -Parent $JsonOut
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$Stem = [System.IO.Path]::GetFileNameWithoutExtension($JsonOut)
$StdoutPath = Join-Path $OutputDirectory "$Stem.stdout.log"
$StderrPath = Join-Path $OutputDirectory "$Stem.stderr.log"
Remove-Item -LiteralPath $StdoutPath, $StderrPath -Force -ErrorAction SilentlyContinue

$Arguments = @(
    "--width", "$EyeWidth", "--height", "$EyeHeight",
    "--synthetic-stereo",
    "--stereo-vfov-deg", "$VerticalFovDegrees",
    "--stereo-ipd-m", "$IpdMeters",
    "--meters-per-M", "$MetersPerM",
    "--stereo-disk", "$Disk",
    "--stereo-polarization", "$Polarization"
)
$Process = Start-Process -FilePath $Executable -ArgumentList $Arguments `
    -WorkingDirectory $WorkingDirectory -RedirectStandardOutput $StdoutPath `
    -RedirectStandardError $StderrPath -PassThru

try {
    $NeededPairs = $WarmupPairs + $SamplePairs
    $Deadline = [DateTime]::UtcNow.AddMinutes(15)
    do {
        Start-Sleep -Milliseconds 250
        $Process.Refresh()
        if ($Process.HasExited) {
            $Tail = if (Test-Path $StderrPath) { Get-Content $StderrPath -Tail 30 } else { @() }
            throw "NPGS exited with code $($Process.ExitCode): $($Tail -join ' | ')"
        }
        $PairCount = @(
            Get-Content -LiteralPath $StdoutPath -ErrorAction SilentlyContinue |
            Select-String '^NPGS_STEREO_GPU pair=(\d+) eye=1 ' |
            ForEach-Object { [int]$_.Matches[0].Groups[1].Value } |
            Sort-Object -Unique
        ).Count
    } until ($PairCount -ge $NeededPairs -or [DateTime]::UtcNow -ge $Deadline)
    if ($PairCount -lt $NeededPairs) {
        throw "Only $PairCount complete stereo pairs were observed; expected $NeededPairs."
    }
}
finally {
    if ($Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force
        $Process.WaitForExit()
    }
}

& $Python -m gr_bh_xr.validate_npgs_stereo_performance `
    --input $StdoutPath --out $JsonOut --warmup-pairs $WarmupPairs --max-pairs $SamplePairs | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Synthetic stereo validation failed. See $JsonOut and $StdoutPath."
}

$Result = Get-Content -LiteralPath $JsonOut -Raw | ConvertFrom-Json
$NvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
$GpuName = $null
$DriverVersion = $null
if ($NvidiaSmi) {
    $GpuRow = (& $NvidiaSmi.Source --query-gpu=name,driver_version --format=csv,noheader 2>$null | Select-Object -First 1)
    if ($GpuRow) {
        $Parts = $GpuRow -split ',', 2
        $GpuName = $Parts[0].Trim()
        $DriverVersion = $Parts[1].Trim()
    }
}
$Result | Add-Member -NotePropertyName timestampUtc -NotePropertyValue ([DateTime]::UtcNow.ToString("o"))
$Result | Add-Member -NotePropertyName upstreamSha -NotePropertyValue ((& git -C $NpgsRoot rev-parse upstream/master).Trim())
$Result | Add-Member -NotePropertyName forkSha -NotePropertyValue ((& git -C $NpgsRoot rev-parse HEAD).Trim())
$Result | Add-Member -NotePropertyName gpu -NotePropertyValue $GpuName
$Result | Add-Member -NotePropertyName driver -NotePropertyValue $DriverVersion
$Result | Add-Member -NotePropertyName evidence -NotePropertyValue ([ordered]@{
    warmupPairs = $WarmupPairs
    samplePairs = $SamplePairs
    stdout = $StdoutPath
    stderr = $StderrPath
    framebuffer = "one desktop swapchain at the per-eye extent, alternating left/right views"
    gpuReadback = "timestamp query results only; no image or physics-buffer readback in timed frames"
    rayStepDistribution = "unavailable in visual fast path without diagnostic-buffer readback"
    processVram = "unavailable: current Windows WDDM tooling does not provide reliable per-process attribution"
    dynamicResolution = $false
    vrs = $false
    multiview = "not implemented; this result is sequential stereo"
})
$Result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $JsonOut -Encoding utf8
$Result | ConvertTo-Json -Depth 12
