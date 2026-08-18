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

function Refresh-ProcessPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $entries = (@($machine, $user, $env:Path) -join ";").Split(";", [System.StringSplitOptions]::RemoveEmptyEntries) |
        Select-Object -Unique
    $env:Path = $entries -join ";"
}

function Test-PythonAvailable {
    foreach ($name in @("py.exe", "python.exe")) {
        foreach ($command in @(Get-Command $name -All -ErrorAction SilentlyContinue)) {
            if (-not $command.Source) { continue }
            $previousErrorActionPreference = $ErrorActionPreference
            try {
                $ErrorActionPreference = "Continue"
                $global:LASTEXITCODE = $null
                & $command.Source --version *> $null
                if ($LASTEXITCODE -eq 0) { return $true }
            } catch {
            } finally {
                $ErrorActionPreference = $previousErrorActionPreference
                $global:LASTEXITCODE = 0
            }
        }
    }
    return $false
}

function Install-WingetPackage([string]$Id) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw "Python is required. Install Python from https://www.python.org/downloads/windows/ and run this installer again."
    }
    Write-Step "Installing required package $Id."
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $global:LASTEXITCODE = $null
        & winget.exe install --id $Id --exact --source winget --accept-package-agreements --accept-source-agreements --silent
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
        $global:LASTEXITCODE = 0
    }
    $alreadyCurrentExitCodes = @(-1978335189, -1978335153, -1978335135)
    if ($null -eq $exitCode -or ($exitCode -ne 0 -and $alreadyCurrentExitCodes -notcontains $exitCode)) {
        throw "$Id installation failed with winget exit code $exitCode."
    }
    Refresh-ProcessPath
}

function Ensure-Python {
    if (Test-PythonAvailable) {
        Write-Step "Python is available."
        return
    }
    Install-WingetPackage -Id "Python.Python.3.14"
    if (-not (Test-PythonAvailable)) {
        throw "Python was installed but is not available yet. Close this window, reopen PowerShell, and run INSTALL-WINDOWS.cmd again."
    }
}

function Test-PluginTree([string]$Root) {
    $marketplace = Join-Path $Root ".agents\plugins\marketplace.json"
    $manifest = Join-Path $Root "plugins\$PluginName\.codex-plugin\plugin.json"
    $skill = Join-Path $Root "plugins\$PluginName\skills\$PluginName\SKILL.md"
    return ((Test-Path -LiteralPath $marketplace) -and (Test-Path -LiteralPath $manifest) -and (Test-Path -LiteralPath $skill))
}

function Test-CodexExecutable([string]$Candidate) {
    if ([string]::IsNullOrWhiteSpace($Candidate)) { return $false }
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        if (-not (Test-Path -LiteralPath $Candidate -PathType Leaf)) { return $false }
        $resolved = (Resolve-Path -LiteralPath $Candidate).Path
        $ErrorActionPreference = "Continue"
        $global:LASTEXITCODE = $null
        & $resolved plugin --help *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
        $global:LASTEXITCODE = 0
    }
}

function Get-CodexCommand {
    $candidates = @()
    foreach ($candidate in @($CodexPath, $env:CHEONGNYEON_CODEX_PATH)) {
        if (-not [string]::IsNullOrWhiteSpace($candidate)) { $candidates += $candidate }
    }
    if ($env:LOCALAPPDATA) {
        $candidates += (Join-Path $env:LOCALAPPDATA "Programs\OpenAI\Codex\bin\codex.exe")
    }
    foreach ($name in @("codex.cmd", "codex.exe", "codex")) {
        foreach ($command in @(Get-Command $name -All -ErrorAction SilentlyContinue)) {
            if ($command.Source) { $candidates += $command.Source }
        }
    }
    if ($env:APPDATA) { $candidates += (Join-Path $env:APPDATA "npm\codex.cmd") }
    if ($env:LOCALAPPDATA) { $candidates += (Join-Path $env:LOCALAPPDATA "npm\codex.cmd") }

    $seen = @{}
    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace([string]$candidate)) { continue }
        $key = ([string]$candidate).ToLowerInvariant()
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true
        if (Test-CodexExecutable -Candidate ([string]$candidate)) {
            return (Resolve-Path -LiteralPath ([string]$candidate)).Path
        }
    }
    return $null
}

function Install-OfficialCodexCli {
    Write-Step "Installing the official OpenAI Codex CLI."
    $previousNonInteractive = $env:CODEX_NON_INTERACTIVE
    $previousErrorActionPreference = $ErrorActionPreference
    $tempInstaller = Join-Path ([IO.Path]::GetTempPath()) ("openai-codex-installer-" + [Guid]::NewGuid().ToString("N") + ".ps1")
    try {
        $env:CODEX_NON_INTERACTIVE = "1"
        $source = Invoke-RestMethod -Uri "https://chatgpt.com/codex/install.ps1"
        $encoding = New-Object System.Text.UTF8Encoding($false)
        [IO.File]::WriteAllText($tempInstaller, [string]$source, $encoding)
        $tokens = $null
        $parseErrors = $null
        [System.Management.Automation.Language.Parser]::ParseFile($tempInstaller, [ref]$tokens, [ref]$parseErrors) | Out-Null
        if (@($parseErrors).Count -gt 0) {
            throw "The official OpenAI Codex CLI installer is not valid PowerShell."
        }
        $windowsPowerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
        if (-not (Test-Path -LiteralPath $windowsPowerShell -PathType Leaf)) {
            throw "Windows PowerShell was not found."
        }
        $ErrorActionPreference = "Continue"
        $global:LASTEXITCODE = $null
        $installOutput = @(& $windowsPowerShell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $tempInstaller 2>&1)
        $installExitCode = $LASTEXITCODE
        if ($null -eq $installExitCode -or $installExitCode -ne 0) {
            $details = if ($installOutput) { "`n$($installOutput -join [Environment]::NewLine)" } else { "" }
            throw "The official OpenAI Codex CLI installer failed with exit code $installExitCode.$details"
        }
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
        $global:LASTEXITCODE = 0
        if (Test-Path -LiteralPath $tempInstaller) {
            Remove-Item -LiteralPath $tempInstaller -Force -ErrorAction SilentlyContinue
        }
        if ($null -eq $previousNonInteractive) {
            Remove-Item Env:CODEX_NON_INTERACTIVE -ErrorAction SilentlyContinue
        } else {
            $env:CODEX_NON_INTERACTIVE = $previousNonInteractive
        }
    }
    Refresh-ProcessPath
}

function Invoke-Codex([string[]]$Arguments, [switch]$IgnoreFailure, [switch]$Capture) {
    $stderrPath = Join-Path ([IO.Path]::GetTempPath()) ("cheongnyeon-codex-stderr-" + [Guid]::NewGuid().ToString("N") + ".log")
    $previousNativeErrorActionPreference = $ErrorActionPreference
    try {
        try {
            $ErrorActionPreference = "Continue"
            $global:LASTEXITCODE = $null
            $output = @(& $script:CodexExecutable @Arguments 2>$stderrPath)
            $exitCode = $LASTEXITCODE
        } catch {
            if ($IgnoreFailure) { return $null }
            throw "Could not start Codex at $script:CodexExecutable. $($_.Exception.Message)"
        }
        $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue } else { "" }
        if ($null -eq $exitCode) {
            if ($IgnoreFailure) { return $null }
            throw "Could not start Codex at $script:CodexExecutable."
        }
        if ($exitCode -ne 0 -and -not $IgnoreFailure) {
            $details = if ($stderr) { "`n$stderr" } elseif ($output) { "`n$($output -join [Environment]::NewLine)" } else { "" }
            throw "Codex command failed: codex $($Arguments -join ' ') (exit code $exitCode)$details"
        }
        if ($Capture) { return ($output -join [Environment]::NewLine) }
        if ($output) { $output | Write-Output }
    } finally {
        $ErrorActionPreference = $previousNativeErrorActionPreference
        Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue
        $global:LASTEXITCODE = 0
    }
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

function Refresh-EditableSupportFiles {
    $source = Join-Path $SourceRoot "scripts\apply-local-edits-windows.ps1"
    $destination = Join-Path $EditableRoot "scripts\apply-local-edits-windows.ps1"
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "The ZIP is missing scripts\apply-local-edits-windows.ps1."
    }
    $destinationParent = Split-Path -Parent $destination
    if (-not (Test-Path -LiteralPath $destinationParent -PathType Container)) {
        New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
    }

    $validatedSource = Get-Content -LiteralPath $source -Raw -Encoding UTF8
    $tokens = $null
    $parseErrors = $null
    [System.Management.Automation.Language.Parser]::ParseInput($validatedSource, [ref]$tokens, [ref]$parseErrors) | Out-Null
    if (@($parseErrors).Count -gt 0) {
        throw "The ZIP contains an invalid local edit helper. The existing helper was preserved."
    }
    foreach ($requiredFunction in @("Test-CodexExecutable", "Get-CodexCommand", "Invoke-Codex")) {
        if ($validatedSource -notmatch ("function\s+" + [regex]::Escape($requiredFunction) + "\b")) {
            throw "The ZIP local edit helper is missing $requiredFunction. The existing helper was preserved."
        }
    }

    # Always rewrite the helper with a UTF-8 BOM. Windows PowerShell 5.1 reads
    # UTF-8 script files without a BOM as the active ANSI code page, which can
    # turn Korean messages into parser errors when the helper runs directly.
    $tempPath = Join-Path $destinationParent (".apply-local-edits-windows." + [Guid]::NewGuid().ToString("N") + ".tmp.ps1")
    $backupPath = Join-Path $destinationParent (".apply-local-edits-windows." + [Guid]::NewGuid().ToString("N") + ".backup.ps1")
    $utf8Bom = New-Object System.Text.UTF8Encoding($true)
    try {
        [IO.File]::WriteAllText($tempPath, $validatedSource, $utf8Bom)
        if (Test-Path -LiteralPath $destination -PathType Leaf) {
            [IO.File]::Replace($tempPath, $destination, $backupPath)
        } else {
            [IO.File]::Move($tempPath, $destination)
        }
    } finally {
        if (Test-Path -LiteralPath $tempPath) {
            Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $backupPath) {
            if (-not (Test-Path -LiteralPath $destination -PathType Leaf)) {
                Move-Item -LiteralPath $backupPath -Destination $destination -Force
            } else {
                Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Write-Step "Refreshed the local edit helper without replacing SKILL.md."
}

function Set-UniqueLocalVersion {
    $manifestPath = Join-Path $EditableRoot "plugins\$PluginName\.codex-plugin\plugin.json"
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $baseVersion = ([string]$manifest.version -split "\+", 2)[0]
    $cacheBuster = [DateTime]::UtcNow.ToString("yyyyMMddHHmmssfff")
    $manifest.version = "$baseVersion+codex.local.install.$cacheBuster.$PID"
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
    $content = "@echo off`r`npowershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$applyScript`" -CodexPath `"$script:CodexExecutable`"`r`npause`r`n"
    $encoding = New-Object System.Text.UTF8Encoding($true)
    [IO.File]::WriteAllText($shortcut, $content, $encoding)
}

function Install-DownloadedPlugin {
    Write-Step "Installing the editable plugin without changing the ChatGPT app or Git."
    Disable-AutoUpdate
    Copy-EditableTree
    Refresh-EditableSupportFiles
    Ensure-Python

    if ($env:CODEX_HOME -and -not (Test-Path -LiteralPath $env:CODEX_HOME)) {
        New-Item -ItemType Directory -Path $env:CODEX_HOME -Force | Out-Null
    }

    $script:CodexExecutable = Get-CodexCommand
    if (-not $script:CodexExecutable) {
        Install-OfficialCodexCli
        $script:CodexExecutable = Get-CodexCommand
    }
    if (-not $script:CodexExecutable) {
        throw "The official Codex CLI could not be installed or verified."
    }
    $env:CHEONGNYEON_CODEX_PATH = $script:CodexExecutable
    Write-Step "Found Codex at $script:CodexExecutable"

    $localVersion = Set-UniqueLocalVersion
    $before = (Invoke-Codex -Arguments @("plugin", "list", "--json") -Capture) | ConvertFrom-Json
    $beforeInstalled = $before.installed | Where-Object { $_.pluginId -eq $PluginSelector } | Select-Object -First 1
    $previousSourceType = if ($beforeInstalled) { [string]$beforeInstalled.marketplaceSource.sourceType } else { "" }
    $previousMarketplaceSource = if ($beforeInstalled) { [string]$beforeInstalled.marketplaceSource.source } else { "" }
    $canRestoreConnection = $beforeInstalled -and (@("local", "git") -contains $previousSourceType) -and (-not [string]::IsNullOrWhiteSpace($previousMarketplaceSource))
    try {
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
    } catch {
        $installError = $_.Exception
        if ($canRestoreConnection) {
            Write-Warning "Install failed. Restoring the previous plugin connection."
            try {
                Invoke-Codex -Arguments @("plugin", "marketplace", "remove", $MarketplaceName, "--json") -IgnoreFailure -Capture | Out-Null
                Invoke-Codex -Arguments @("plugin", "marketplace", "add", $previousMarketplaceSource, "--json") -Capture | Out-Null
                Invoke-Codex -Arguments @("plugin", "add", $PluginSelector, "--json") -Capture | Out-Null
            } catch {
                Write-Warning "Could not restore the previous plugin connection: $($_.Exception.Message)"
            }
        }
        throw $installError
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
} catch {
    Write-Host ""
    Write-Host "[INSTALLATION FAILED] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Keep this window open and send a screenshot to the plugin author." -ForegroundColor Yellow
    throw
}
