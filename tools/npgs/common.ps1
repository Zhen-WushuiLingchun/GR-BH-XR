function Get-GrBhXrPhysicalRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Get-GrBhXrBuildRoot {
    param([switch]$Create)

    $physical = Get-GrBhXrPhysicalRoot
    if ($physical -notmatch "[^\x00-\x7F]") { return $physical }

    $aliasParent = Join-Path $env:LOCALAPPDATA "GRBHXR"
    $alias = Join-Path $aliasParent "native-build-root"
    if (Test-Path -LiteralPath $alias) {
        $item = Get-Item -LiteralPath $alias
        $targets = @($item.Target)
        if ($item.LinkType -ne "Junction" -or $targets -notcontains $physical) {
            throw "ASCII build alias exists but does not target this repository: $alias"
        }
        return $alias
    }

    if (-not $Create) {
        throw "The repository path contains non-ASCII characters. Run tools/npgs/bootstrap.ps1 to create the local ASCII build alias."
    }

    New-Item -ItemType Directory -Force -Path $aliasParent | Out-Null
    New-Item -ItemType Junction -Path $alias -Target $physical | Out-Null
    return $alias
}
