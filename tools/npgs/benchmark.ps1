[CmdletBinding()]
param(
    [ValidateRange(1, 16384)]
    [int]$Width = 1920,
    [ValidateRange(1, 16384)]
    [int]$Height = 1080,
    [ValidateRange(1, 300)]
    [int]$WarmupSeconds = 12,
    [ValidateRange(3, 300)]
    [int]$SampleSeconds = 10,
    [string]$JsonOut,
    [string]$ScreenshotOut
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
$RepoRoot = Get-GrBhXrBuildRoot -Create
$PhysicalRoot = Get-GrBhXrPhysicalRoot
$NpgsRoot = Join-Path $RepoRoot "runtime\NPGS"
$WorkingDirectory = Join-Path $NpgsRoot "NPGS"
$Executable = Join-Path $NpgsRoot "x64\Release\NPGS.exe"

if (-not (Test-Path -LiteralPath $Executable)) {
    throw "NPGS Release executable was not found. Run tools/npgs/build.ps1 first."
}

if (-not $JsonOut) {
    $JsonOut = Join-Path $PhysicalRoot "outputs\npgs\baseline_$($Width)x$($Height).json"
}
$JsonOut = [System.IO.Path]::GetFullPath($JsonOut, $PhysicalRoot)
if ($ScreenshotOut) {
    $ScreenshotOut = [System.IO.Path]::GetFullPath($ScreenshotOut, $PhysicalRoot)
}

$OutputDirectory = Split-Path -Parent $JsonOut
if ($OutputDirectory) {
    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
}
$LogStem = [System.IO.Path]::GetFileNameWithoutExtension($JsonOut)
$StdoutPath = Join-Path $OutputDirectory "$LogStem.stdout.log"
$StderrPath = Join-Path $OutputDirectory "$LogStem.stderr.log"
Remove-Item -LiteralPath $StdoutPath, $StderrPath -Force -ErrorAction SilentlyContinue

function Get-Percentile([double[]]$Values, [double]$Percentile) {
    if ($Values.Count -eq 0) { return $null }
    $sorted = @($Values | Sort-Object)
    $index = [math]::Ceiling(($Percentile / 100.0) * $sorted.Count) - 1
    $index = [math]::Max(0, [math]::Min($sorted.Count - 1, $index))
    return [double]$sorted[$index]
}

function Read-BenchmarkLog([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return @() }
    return @(Get-Content -LiteralPath $Path -ErrorAction SilentlyContinue)
}

function Get-BenchmarkFramebuffer([string[]]$Lines) {
    foreach ($line in $Lines) {
        if ($line -match '^NPGS_BENCHMARK_FRAMEBUFFER\s+(\d+)\s+(\d+)\s*$') {
            return [pscustomobject]@{
                Width = [int]$Matches[1]
                Height = [int]$Matches[2]
            }
        }
    }
    return $null
}

function Get-BenchmarkFps([string[]]$Lines) {
    $values = [System.Collections.Generic.List[double]]::new()
    foreach ($line in $Lines) {
        if ($line -match '^NPGS_BENCHMARK_FPS\s+(\d+(?:\.\d+)?)\s*$') {
            $values.Add([double]$Matches[1])
        }
    }
    return @($values)
}

function Get-ProcessFailureDetail([System.Diagnostics.Process]$Process, [string]$ErrorLog) {
    $detail = "NPGS exited with code $($Process.ExitCode)."
    if (Test-Path -LiteralPath $ErrorLog) {
        $tail = @(Get-Content -LiteralPath $ErrorLog -Tail 20 -ErrorAction SilentlyContinue)
        if ($tail.Count -gt 0) {
            $detail += " stderr: " + ($tail -join " | ")
        }
    }
    return $detail
}

function Save-VisibleEvidenceScreenshot(
    [string]$NpgsExecutable,
    [string]$NpgsWorkingDirectory,
    [int]$RequestedWidth,
    [int]$RequestedHeight,
    [string]$Path
) {
    if (-not ("GrBhXrWindowCapture" -as [type])) {
        Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class GrBhXrWindowCapture {
    [StructLayout(LayoutKind.Sequential)]
    public struct Rect { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")]
    public static extern bool GetClientRect(IntPtr hWnd, out Rect rect);
    [DllImport("user32.dll")]
    public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
}
"@
    }
    Add-Type -AssemblyName System.Drawing

    $arguments = @(
        "--width", "$RequestedWidth",
        "--height", "$RequestedHeight",
        "--windowed",
        "--no-vsync"
    )
    $process = Start-Process -FilePath $NpgsExecutable -ArgumentList $arguments -WorkingDirectory $NpgsWorkingDirectory -PassThru
    try {
        $deadline = [DateTime]::UtcNow.AddSeconds(45)
        do {
            Start-Sleep -Milliseconds 250
            $process.Refresh()
            if ($process.HasExited) {
                throw "NPGS exited before the evidence screenshot with code $($process.ExitCode)."
            }
        } until (($process.MainWindowHandle -ne 0 -and $process.MainWindowTitle -match 'NPGS FPS:\s*\d+') -or [DateTime]::UtcNow -ge $deadline)

        if ($process.MainWindowHandle -eq 0) {
            throw "NPGS did not create a visible evidence window within 45 seconds."
        }

        $rect = New-Object GrBhXrWindowCapture+Rect
        if (-not [GrBhXrWindowCapture]::GetClientRect($process.MainWindowHandle, [ref]$rect)) {
            throw "Unable to query the NPGS evidence window client area."
        }
        $captureWidth = $rect.Right - $rect.Left
        $captureHeight = $rect.Bottom - $rect.Top
        if ($captureWidth -le 0 -or $captureHeight -le 0) {
            throw "The NPGS evidence window has an invalid client size."
        }

        $bitmap = New-Object System.Drawing.Bitmap($captureWidth, $captureHeight)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $hdc = $graphics.GetHdc()
        try {
            if (-not [GrBhXrWindowCapture]::PrintWindow($process.MainWindowHandle, $hdc, 2)) {
                throw "PrintWindow failed for the NPGS evidence window."
            }
        }
        finally {
            $graphics.ReleaseHdc($hdc)
            $graphics.Dispose()
        }

        $parent = Split-Path -Parent $Path
        if ($parent) {
            New-Item -ItemType Directory -Force -Path $parent | Out-Null
        }
        $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
        $bitmap.Dispose()

        return [ordered]@{
            path = $Path
            requestedWidth = $RequestedWidth
            requestedHeight = $RequestedHeight
            capturedClientWidth = $captureWidth
            capturedClientHeight = $captureHeight
            note = "Separate visible evidence run; not the hidden performance measurement."
        }
    }
    finally {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit()
        }
    }
}

$Arguments = @(
    "--width", "$Width",
    "--height", "$Height",
    "--benchmark"
)
$Process = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -RedirectStandardOutput $StdoutPath -RedirectStandardError $StderrPath -PassThru

$Framebuffer = $null
$FpsSamples = @()
try {
    $startupDeadline = [DateTime]::UtcNow.AddSeconds(60)
    do {
        Start-Sleep -Milliseconds 250
        $Process.Refresh()
        if ($Process.HasExited) {
            throw (Get-ProcessFailureDetail $Process $StderrPath)
        }
        $Framebuffer = Get-BenchmarkFramebuffer (Read-BenchmarkLog $StdoutPath)
    } until ($null -ne $Framebuffer -or [DateTime]::UtcNow -ge $startupDeadline)

    if ($null -eq $Framebuffer) {
        throw "NPGS did not report its Vulkan framebuffer within 60 seconds."
    }
    if ($Framebuffer.Width -ne $Width -or $Framebuffer.Height -ne $Height) {
        throw "Framebuffer mismatch: requested $($Width)x$($Height), NPGS reported $($Framebuffer.Width)x$($Framebuffer.Height)."
    }

    Start-Sleep -Seconds $WarmupSeconds
    $WarmupSampleCount = @(Get-BenchmarkFps (Read-BenchmarkLog $StdoutPath)).Count
    $sampleDeadline = [DateTime]::UtcNow.AddSeconds($SampleSeconds + 15)
    do {
        Start-Sleep -Milliseconds 250
        $Process.Refresh()
        if ($Process.HasExited) {
            throw (Get-ProcessFailureDetail $Process $StderrPath)
        }
        $allSamples = @(Get-BenchmarkFps (Read-BenchmarkLog $StdoutPath))
        $newSampleCount = $allSamples.Count - $WarmupSampleCount
    } until ($newSampleCount -ge $SampleSeconds -or [DateTime]::UtcNow -ge $sampleDeadline)

    if ($newSampleCount -lt $SampleSeconds) {
        throw "Only $newSampleCount post-warmup FPS samples were collected; expected $SampleSeconds."
    }
    $FpsSamples = @($allSamples | Select-Object -Skip $WarmupSampleCount -First $SampleSeconds)
}
finally {
    if ($Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force
        $Process.WaitForExit()
    }
}

$Screenshot = $null
if ($ScreenshotOut) {
    $Screenshot = Save-VisibleEvidenceScreenshot $Executable $WorkingDirectory $Width $Height $ScreenshotOut
}

$FrameTimes = [double[]]@($FpsSamples | ForEach-Object { 1000.0 / $_ })
$NvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
$GpuName = $null
$DriverVersion = $null
if ($NvidiaSmi) {
    $gpuRow = (& $NvidiaSmi.Source --query-gpu=name,driver_version --format=csv,noheader 2>$null | Select-Object -First 1)
    if ($gpuRow) {
        $parts = $gpuRow -split ',', 2
        $GpuName = $parts[0].Trim()
        $DriverVersion = $parts[1].Trim()
    }
}

$Result = [ordered]@{
    schema = "gr-bh-xr.npgs.performance.v1"
    timestampUtc = [DateTime]::UtcNow.ToString("o")
    upstreamSha = (& git -C $NpgsRoot rev-parse upstream/master).Trim()
    forkSha = (& git -C $NpgsRoot rev-parse HEAD).Trim()
    gpu = $GpuName
    driver = $DriverVersion
    requestedResolution = [ordered]@{ width = $Width; height = $Height }
    framebuffer = [ordered]@{
        width = $Framebuffer.Width
        height = $Framebuffer.Height
        verifiedExact = $true
        source = "glfwGetFramebufferSize emitted by the native renderer before Vulkan swapchain creation"
    }
    launch = [ordered]@{
        benchmark = $true
        hiddenWindow = $true
        windowed = $true
        vsync = $false
    }
    renderPath = "upstream visual prepass/composite/TAA; no audit pass or readback"
    defaultPhysics = [ordered]@{
        massNormalization = "shader M=0.5 (Rs=1)"
        spinDimensionless = 0.998
        chargeDimensionless = 0.0
        prepass = 1
        quality = 1.0
        observerMode = 0
        polarization = 0
    }
    warmupSeconds = $WarmupSeconds
    sampleSeconds = $SampleSeconds
    fps = [ordered]@{
        samples = @($FpsSamples)
        median = Get-Percentile ([double[]]$FpsSamples) 50
        mean = ($FpsSamples | Measure-Object -Average).Average
        min = ($FpsSamples | Measure-Object -Minimum).Minimum
        max = ($FpsSamples | Measure-Object -Maximum).Maximum
    }
    frameTimeMs = [ordered]@{
        median = Get-Percentile $FrameTimes 50
        p95 = Get-Percentile $FrameTimes 95
        max = ($FrameTimes | Measure-Object -Maximum).Maximum
    }
    logs = [ordered]@{
        stdout = $StdoutPath
        stderr = $StderrPath
    }
    screenshot = $Screenshot
}

$Result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $JsonOut -Encoding utf8
$Result | ConvertTo-Json -Depth 8
