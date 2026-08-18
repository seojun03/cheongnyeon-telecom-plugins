[CmdletBinding()]
param(
    [string]$RepositorySource = $(if ($env:CHEONGNYEON_REPOSITORY_SOURCE) { $env:CHEONGNYEON_REPOSITORY_SOURCE } else { "seojun03/cheongnyeon-telecom-plugins" }),
    [string]$Ref = $(if ($env:CHEONGNYEON_REPOSITORY_REF) { $env:CHEONGNYEON_REPOSITORY_REF } else { "main" }),
    [string]$CodexPath = $env:CHEONGNYEON_CODEX_PATH,
    [string]$EditableRoot = $(if ($env:CHEONGNYEON_EDITABLE_ROOT) { $env:CHEONGNYEON_EDITABLE_ROOT } else { Join-Path $HOME "CheongnyeonTelecomPlugin" }),
    [switch]$NoLaunch = ($env:CHEONGNYEON_NO_LAUNCH -eq "1")
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$MarketplaceName = "cheongnyeon-telecom"
$PluginName = "cheongnyeon-telecom-blog"
$PluginSelector = "$PluginName@$MarketplaceName"
$TaskName = $(if ($env:CHEONGNYEON_AUTO_UPDATE_TASK_NAME) { $env:CHEONGNYEON_AUTO_UPDATE_TASK_NAME } else { "CheongnyeonTelecomPluginUpdate" })

function Write-Step([string]$Message) {
    Write-Host "[청년통신 편집용 설치] $Message" -ForegroundColor Cyan
}

function Get-ChatGPTPackage {
    Get-AppxPackage | Where-Object {
        $identity = "$($_.Name) $($_.PackageFamilyName) $($_.PackageFullName) $($_.InstallLocation)"
        $identity -match "ChatGPT|OpenAI|Codex"
    } | Select-Object -First 1
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

function Get-NpmCommand {
    foreach ($name in @("npm.cmd", "npm")) {
        foreach ($command in @(Get-Command $name -All -ErrorAction SilentlyContinue)) {
            if ($command.Source -and (Test-Path -LiteralPath $command.Source -PathType Leaf)) { return $command.Source }
        }
    }
    foreach ($candidate in @(
        $(if ($env:ProgramFiles) { Join-Path $env:ProgramFiles "nodejs\npm.cmd" }),
        $(if (${env:ProgramFiles(x86)}) { Join-Path ${env:ProgramFiles(x86)} "nodejs\npm.cmd" }),
        $(if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA "Programs\nodejs\npm.cmd" })
    )) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    return $null
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
    $npm = Get-NpmCommand
    if ($npm) {
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "SilentlyContinue"
            $prefixOutput = @(& $npm prefix --global 2>$null)
            if ($LASTEXITCODE -eq 0 -and $prefixOutput.Count -gt 0) {
                $prefix = [string]$prefixOutput[-1]
                if (-not [string]::IsNullOrWhiteSpace($prefix)) { $candidates += (Join-Path $prefix.Trim() "codex.cmd") }
            }
        } catch {
        } finally {
            $ErrorActionPreference = $previousErrorActionPreference
            $global:LASTEXITCODE = 0
        }
    }
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
            throw "Codex 실행 파일을 시작하지 못했습니다: $script:CodexExecutable. $($_.Exception.Message)"
        }
        $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue } else { "" }
        if ($null -eq $exitCode) {
            if ($IgnoreFailure) { return $null }
            throw "Codex 실행 파일을 시작하지 못했습니다: $script:CodexExecutable"
        }
        if ($exitCode -ne 0 -and -not $IgnoreFailure) {
            $details = if ($stderr) { "`n$stderr" } elseif ($output) { "`n$($output -join [Environment]::NewLine)" } else { "" }
            throw "Codex 명령에 실패했습니다: codex $($Arguments -join ' ') (종료 코드 $exitCode)$details"
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
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    Write-Step "중앙 자동 업데이트를 해제했습니다."
}

function Download-EditableCopy {
    if (Test-Path -LiteralPath $EditableRoot) {
        $marketplace = Join-Path $EditableRoot ".agents\plugins\marketplace.json"
        $skill = Join-Path $EditableRoot "plugins\$PluginName\skills\$PluginName\SKILL.md"
        if (-not (Test-Path -LiteralPath $marketplace) -or -not (Test-Path -LiteralPath $skill)) {
            throw "기존 폴더가 편집용 플러그인 구조가 아닙니다: $EditableRoot"
        }
        Write-Step "기존 로컬 수정본을 보존하고 다시 연결합니다."
        return
    }

    $tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("cheongnyeon-editable-" + [Guid]::NewGuid().ToString("N"))
    $archive = Join-Path $tempRoot "plugin.zip"
    $unpacked = Join-Path $tempRoot "unpacked"
    New-Item -ItemType Directory -Path $tempRoot, $unpacked -Force | Out-Null
    try {
        $cacheBuster = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $archiveUrl = "https://codeload.github.com/$RepositorySource/zip/$Ref`?cachebust=$cacheBuster"
        Write-Step "자동 업데이트와 분리된 로컬 수정본을 다운로드합니다."
        Invoke-WebRequest -Uri $archiveUrl -OutFile $archive -UseBasicParsing
        Expand-Archive -LiteralPath $archive -DestinationPath $unpacked -Force
        $sourceRoot = Get-ChildItem -LiteralPath $unpacked -Directory | Select-Object -First 1
        if (-not $sourceRoot) { throw "다운로드 압축에서 플러그인 폴더를 찾지 못했습니다." }
        $parent = Split-Path -Parent $EditableRoot
        if ($parent -and -not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        Move-Item -LiteralPath $sourceRoot.FullName -Destination $EditableRoot
    } finally {
        if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
    }
}

function Refresh-EditableSupportFiles {
    # Preserve the user's SKILL.md and all other local content, but replace the
    # maintenance script so retries also receive installer bug fixes. Download
    # and validate it beside the destination before replacing a working copy.
    $applyPath = Join-Path $EditableRoot "scripts\apply-local-edits-windows.ps1"
    $cacheBuster = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    $applyUrl = "https://raw.githubusercontent.com/$RepositorySource/$Ref/scripts/apply-local-edits-windows.ps1?cachebust=$cacheBuster"
    $parent = Split-Path -Parent $applyPath
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $tempPath = Join-Path $parent (".apply-local-edits-windows." + [Guid]::NewGuid().ToString("N") + ".tmp.ps1")
    $backupPath = Join-Path $parent (".apply-local-edits-windows." + [Guid]::NewGuid().ToString("N") + ".backup.ps1")
    # Windows PowerShell 5.1 opens script files using the active ANSI code page
    # unless UTF-8 has a BOM. Write the installed helper with a BOM so it can
    # be executed directly after validation, including on Korean Windows.
    $helperUtf8Bom = New-Object System.Text.UTF8Encoding($true)
    try {
        $source = Invoke-RestMethod -Uri $applyUrl
        [IO.File]::WriteAllText($tempPath, [string]$source, $helperUtf8Bom)

        # Windows PowerShell 5.1 treats UTF-8 files without a BOM as the local
        # ANSI code page when ParseFile is used. Read explicit UTF-8 first and
        # parse the in-memory text so Korean messages cannot create false errors.
        $validatedSource = Get-Content -LiteralPath $tempPath -Raw -Encoding UTF8
        $tokens = $null
        $parseErrors = $null
        [System.Management.Automation.Language.Parser]::ParseInput($validatedSource, [ref]$tokens, [ref]$parseErrors) | Out-Null
        if (@($parseErrors).Count -gt 0) {
            throw "다운로드한 로컬 수정 적용기의 PowerShell 문법이 올바르지 않습니다. 기존 적용기는 보존했습니다."
        }
        foreach ($requiredFunction in @("Test-CodexExecutable", "Get-CodexCommand", "Invoke-Codex")) {
            if ($validatedSource -notmatch ("function\s+" + [regex]::Escape($requiredFunction) + "\b")) {
                throw "다운로드한 로컬 수정 적용기에 $requiredFunction 함수가 없습니다. 기존 적용기는 보존했습니다."
            }
        }

        if (Test-Path -LiteralPath $applyPath -PathType Leaf) {
            [IO.File]::Replace($tempPath, $applyPath, $backupPath)
        } else {
            [IO.File]::Move($tempPath, $applyPath)
        }
    } finally {
        if (Test-Path -LiteralPath $tempPath) {
            Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $backupPath) {
            if (-not (Test-Path -LiteralPath $applyPath -PathType Leaf)) {
                Move-Item -LiteralPath $backupPath -Destination $applyPath -Force
            } else {
                Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Write-Step "로컬 수정 적용기를 최신 버전으로 정비했습니다."
}

function Create-DesktopShortcut {
    if ($env:CHEONGNYEON_SKIP_DESKTOP_SHORTCUT -eq "1") { return }
    $desktop = [Environment]::GetFolderPath("Desktop")
    if (-not $desktop) { return }
    $shortcut = Join-Path $desktop "청년통신_플러그인_내수정적용.cmd"
    $applyScript = Join-Path $EditableRoot "scripts\apply-local-edits-windows.ps1"
    $content = "@echo off`r`npowershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$applyScript`" -CodexPath `"$script:CodexExecutable`"`r`npause`r`n"
    $encoding = New-Object System.Text.UTF8Encoding($true)
    [IO.File]::WriteAllText($shortcut, $content, $encoding)
}

Disable-AutoUpdate
$env:CHEONGNYEON_DISABLE_AUTO_UPDATE = "1"
$env:CHEONGNYEON_NO_LAUNCH = "1"
$env:CHEONGNYEON_SKIP_APP_INSTALL = "1"
$previousDependenciesOnly = $env:CHEONGNYEON_DEPENDENCIES_ONLY
$env:CHEONGNYEON_DEPENDENCIES_ONLY = "1"
Write-Step "ChatGPT 앱은 변경하지 않고 플러그인만 설치합니다."
$cacheBuster = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$baseInstallerUrl = "https://raw.githubusercontent.com/$RepositorySource/$Ref/install-windows.ps1?cachebust=$cacheBuster"
try {
    $baseInstallerSource = Invoke-RestMethod -Uri $baseInstallerUrl
    & ([scriptblock]::Create([string]$baseInstallerSource))
} finally {
    if ($null -eq $previousDependenciesOnly) {
        Remove-Item Env:CHEONGNYEON_DEPENDENCIES_ONLY -ErrorAction SilentlyContinue
    } else {
        $env:CHEONGNYEON_DEPENDENCIES_ONLY = $previousDependenciesOnly
    }
}

Download-EditableCopy
Refresh-EditableSupportFiles
$script:CodexExecutable = Get-CodexCommand
if (-not $script:CodexExecutable) { throw "플러그인 기능이 있는 Codex 실행 파일을 찾지 못했습니다." }
$env:CHEONGNYEON_CODEX_PATH = $script:CodexExecutable

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

    $plugins = (Invoke-Codex -Arguments @("plugin", "list", "--json") -Capture) | ConvertFrom-Json
    $installed = $plugins.installed | Where-Object { $_.pluginId -eq $PluginSelector } | Select-Object -First 1
    if (-not $installed -or -not $installed.enabled -or $installed.marketplaceSource.sourceType -ne "local") {
        throw "설치된 플러그인이 로컬 수정본에 연결되지 않았습니다."
    }
} catch {
    $installError = $_.Exception
    if ($canRestoreConnection) {
        Write-Warning "재연결에 실패해 기존 플러그인 연결을 복구합니다."
        try {
            Invoke-Codex -Arguments @("plugin", "marketplace", "remove", $MarketplaceName, "--json") -IgnoreFailure -Capture | Out-Null
            Invoke-Codex -Arguments @("plugin", "marketplace", "add", $previousMarketplaceSource, "--json") -Capture | Out-Null
            Invoke-Codex -Arguments @("plugin", "add", $PluginSelector, "--json") -Capture | Out-Null
        } catch {
            Write-Warning "기존 플러그인 연결을 자동으로 복구하지 못했습니다: $($_.Exception.Message)"
        }
    }
    throw $installError
}
$skillPath = Join-Path $EditableRoot "plugins\$PluginName\skills\$PluginName\SKILL.md"
$probe = Get-Item -LiteralPath $skillPath
if ($probe.IsReadOnly) { throw "설치된 SKILL.md가 읽기 전용입니다." }

Create-DesktopShortcut
if (-not $NoLaunch) {
    $package = Get-ChatGPTPackage
    if ($package) {
        try {
            [xml]$manifest = Get-Content -LiteralPath (Join-Path $package.InstallLocation "AppxManifest.xml")
            $applicationId = @($manifest.Package.Applications.Application)[0].Id
            Start-Process explorer.exe "shell:AppsFolder\$($package.PackageFamilyName)!$applicationId"
        } catch { Write-Warning "설치는 완료됐지만 ChatGPT 앱 자동 실행은 건너뜁니다." }
    }
}

Write-Host ""
Write-Step "설치 완료: 이 PC는 중앙 자동 업데이트를 받지 않습니다."
Write-Step "수정 파일: $skillPath"
Write-Step "수정 후 바탕화면의 '청년통신_플러그인_내수정적용.cmd'를 실행하세요."
