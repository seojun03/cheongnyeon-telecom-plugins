[CmdletBinding()]
param(
    [string]$CodexPath = $env:CHEONGNYEON_CODEX_PATH,
    [string]$EditableRoot = $(if ($env:CHEONGNYEON_EDITABLE_ROOT) { $env:CHEONGNYEON_EDITABLE_ROOT } else { Join-Path $HOME "CheongnyeonTelecomPlugin" })
)

# Keep this file ASCII-only so Windows PowerShell 5.1 can run it reliably.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$MarketplaceName = "cheongnyeon-telecom"
$PluginName = "cheongnyeon-telecom-blog"
$PluginSelector = "$PluginName@$MarketplaceName"
$TaskName = $(if ($env:CHEONGNYEON_AUTO_UPDATE_TASK_NAME) { $env:CHEONGNYEON_AUTO_UPDATE_TASK_NAME } else { "CheongnyeonTelecomPluginUpdate" })
$SourceRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path

function Write-Step([string]$Message) {
    Write-Host "[Cheongnyeon installer] $Message" -ForegroundColor Cyan
}

function Test-PluginTree([string]$Root) {
    $marketplace = Join-Path $Root ".agents\plugins\marketplace.json"
    $manifest = Join-Path $Root "plugins\$PluginName\.codex-plugin\plugin.json"
    $skill = Join-Path $Root "plugins\$PluginName\skills\$PluginName\SKILL.md"
    return ((Test-Path -LiteralPath $marketplace) -and (Test-Path -LiteralPath $manifest) -and (Test-Path -LiteralPath $skill))
}

function Find-CodexInRoot([string]$Root) {
    if (-not $Root -or -not (Test-Path -LiteralPath $Root)) { return $null }
    $found = Get-ChildItem -LiteralPath $Root -Filter "codex.exe" -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { return $found.FullName }
    return $null
}

function Get-CodexCommand {
    if ($CodexPath -and (Test-Path -LiteralPath $CodexPath)) {
        return (Resolve-Path -LiteralPath $CodexPath).Path
    }

    foreach ($name in @("codex.exe", "codex.cmd", "codex")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command) { return $command.Source }
    }

    $packages = @(Get-AppxPackage -ErrorAction SilentlyContinue)
    $matchingPackages = @($packages | Where-Object {
        $identity = "$($_.Name) $($_.PackageFamilyName) $($_.PackageFullName) $($_.InstallLocation)"
        $identity -match "ChatGPT|OpenAI|Codex"
    })
    foreach ($package in $matchingPackages) {
        $embedded = Find-CodexInRoot -Root $package.InstallLocation
        if ($embedded) { return $embedded }
    }

    $knownRoots = @()
    if ($env:LOCALAPPDATA) {
        $knownRoots += (Join-Path $env:LOCALAPPDATA "Programs\ChatGPT")
        $knownRoots += (Join-Path $env:LOCALAPPDATA "Programs\OpenAI")
        $knownRoots += (Join-Path $env:LOCALAPPDATA "Programs\Codex")
    }
    if ($env:ProgramFiles) {
        $knownRoots += (Join-Path $env:ProgramFiles "ChatGPT")
        $knownRoots += (Join-Path $env:ProgramFiles "OpenAI")
        $knownRoots += (Join-Path $env:ProgramFiles "Codex")
    }
    foreach ($root in $knownRoots) {
        $embedded = Find-CodexInRoot -Root $root
        if ($embedded) { return $embedded }
    }
    return $null
}

function Invoke-Codex([string[]]$Arguments, [switch]$IgnoreFailure, [switch]$Capture) {
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        if ($Capture) {
            $output = & $script:CodexExecutable @Arguments 2>&1
        } else {
            & $script:CodexExecutable @Arguments
            $output = $null
        }
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($exitCode -ne 0 -and -not $IgnoreFailure) {
        $details = if ($output) { "`n$($output -join [Environment]::NewLine)" } else { "" }
        throw "Codex command failed: codex $($Arguments -join ' ')$details"
    }
    if ($Capture) { return ($output -join [Environment]::NewLine) }
}

function Disable-AutoUpdate {
    if (-not (Get-Command "Get-ScheduledTask" -ErrorAction SilentlyContinue)) { return }
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Step "Disabled the central automatic updater."
    }
}

function Copy-EditableTree {
    if (Test-Path -LiteralPath $EditableRoot) {
        if (-not (Test-PluginTree -Root $EditableRoot)) {
            throw "The existing destination is not a valid editable plugin folder: $EditableRoot"
        }
        Write-Step "Keeping the existing editable copy and reconnecting it."
        return
    }

    if (-not (Test-PluginTree -Root $SourceRoot)) {
        throw "Required plugin files are missing. Extract the whole ZIP before running INSTALL-WINDOWS.cmd."
    }

    $parent = Split-Path -Parent $EditableRoot
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $staging = "$EditableRoot.installing.$([Guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Path $staging -Force | Out-Null
    try {
        foreach ($directory in @(".agents", "plugins", "scripts")) {
            Copy-Item -LiteralPath (Join-Path $SourceRoot $directory) -Destination $staging -Recurse -Force
        }
        foreach ($file in @("README.md", "INSTALL-WINDOWS.cmd", "install-from-download-windows.ps1")) {
            $source = Join-Path $SourceRoot $file
            if (Test-Path -LiteralPath $source) {
                Copy-Item -LiteralPath $source -Destination $staging -Force
            }
        }
        if (-not (Test-PluginTree -Root $staging)) {
            throw "The copied plugin folder is incomplete."
        }
        Move-Item -LiteralPath $staging -Destination $EditableRoot
    } finally {
        if (Test-Path -LiteralPath $staging) {
            Remove-Item -LiteralPath $staging -Recurse -Force
        }
    }
    Write-Step "Created an editable copy at $EditableRoot"
}

function Set-UniqueLocalVersion {
    $manifestPath = Join-Path $EditableRoot "plugins\$PluginName\.codex-plugin\plugin.json"
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $baseVersion = ([string]$manifest.version -split "\+", 2)[0]
    $cacheBuster = [DateTime]::UtcNow.ToString("yyyyMMddHHmmss")
    $manifest.version = "$baseVersion+codex.local.install.$cacheBuster"
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 100) + [Environment]::NewLine, $encoding)
    return $manifest.version
}

function Create-DesktopShortcut {
    if ($env:CHEONGNYEON_SKIP_DESKTOP_SHORTCUT -eq "1") { return }
    $desktop = [Environment]::GetFolderPath("Desktop")
    if (-not $desktop) { return }
    $shortcut = Join-Path $desktop "Cheongnyeon_Plugin_Apply_My_Edits.cmd"
    $applyScript = Join-Path $EditableRoot "scripts\apply-local-edits-windows.ps1"
    $content = "@echo off`r`npowershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$applyScript`"`r`npause`r`n"
    $encoding = New-Object System.Text.UTF8Encoding($true)
    [IO.File]::WriteAllText($shortcut, $content, $encoding)
}

function Install-DownloadedPlugin {
    Write-Step "Installing only the plugin. ChatGPT, winget, Git, and Python will not be installed or upgraded."
    Disable-AutoUpdate
    Copy-EditableTree

    $script:CodexExecutable = Get-CodexCommand
    if (-not $script:CodexExecutable) {
        throw "The ChatGPT desktop app with Codex was not found. Install or update it from https://chatgpt.com/download/ and run this file again."
    }
    Write-Step "Found Codex at $script:CodexExecutable"

    $localVersion = Set-UniqueLocalVersion
    Invoke-Codex -Arguments @("plugin", "remove", $PluginSelector, "--json") -IgnoreFailure -Capture | Out-Null
    Invoke-Codex -Arguments @("plugin", "marketplace", "remove", $MarketplaceName, "--json") -IgnoreFailure -Capture | Out-Null
    Invoke-Codex -Arguments @("plugin", "marketplace", "add", $EditableRoot, "--json") -Capture | Out-Null
    Invoke-Codex -Arguments @("plugin", "add", $PluginSelector, "--json") -Capture | Out-Null

    $json = Invoke-Codex -Arguments @("plugin", "list", "--json") -Capture
    $plugins = $json | ConvertFrom-Json
    $installed = $plugins.installed | Where-Object { $_.pluginId -eq $PluginSelector } | Select-Object -First 1
    if (-not $installed -or -not $installed.enabled) {
        throw "The plugin was not enabled after installation."
    }
    if ($installed.marketplaceSource.sourceType -ne "local") {
        throw "The installed plugin is not connected to the editable local copy."
    }
    if ([string]$installed.version -ne [string]$localVersion) {
        throw "The installed version does not match the downloaded local copy."
    }

    $skillPath = Join-Path $EditableRoot "plugins\$PluginName\skills\$PluginName\SKILL.md"
    Create-DesktopShortcut
    Write-Host ""
    Write-Step "INSTALLATION COMPLETE"
    Write-Step "Open ChatGPT, start a new task, and select the Cheongnyeon plugin."
    Write-Step "Editable instructions: $skillPath"
    Write-Step "After editing, run Cheongnyeon_Plugin_Apply_My_Edits.cmd from the Desktop."
}

try {
    Install-DownloadedPlugin
    exit 0
} catch {
    Write-Host ""
    Write-Host "[INSTALLATION FAILED] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Keep this window open and send a screenshot to the plugin author." -ForegroundColor Yellow
    exit 1
}
