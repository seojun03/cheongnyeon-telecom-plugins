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

function Get-CodexCommand {
    if ($CodexPath -and (Test-Path -LiteralPath $CodexPath)) {
        return (Resolve-Path -LiteralPath $CodexPath).Path
    }
    foreach ($name in @("codex.exe", "codex.cmd", "codex")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command) { return $command.Source }
    }
    $package = Get-ChatGPTPackage
    if ($package -and $package.InstallLocation) {
        $embedded = Get-ChildItem -LiteralPath $package.InstallLocation -Filter "codex.exe" -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($embedded) { return $embedded.FullName }
    }
    return $null
}

function Invoke-Codex([string[]]$Arguments, [switch]$IgnoreFailure, [switch]$Capture) {
    if ($Capture) { $output = & $script:CodexExecutable @Arguments 2>&1 } else { & $script:CodexExecutable @Arguments; $output = $null }
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0 -and -not $IgnoreFailure) {
        $details = if ($output) { "`n$($output -join [Environment]::NewLine)" } else { "" }
        throw "Codex 명령에 실패했습니다: codex $($Arguments -join ' ')$details"
    }
    if ($Capture) { return ($output -join [Environment]::NewLine) }
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

function Create-DesktopShortcut {
    if ($env:CHEONGNYEON_SKIP_DESKTOP_SHORTCUT -eq "1") { return }
    $desktop = [Environment]::GetFolderPath("Desktop")
    if (-not $desktop) { return }
    $shortcut = Join-Path $desktop "청년통신_플러그인_내수정적용.cmd"
    $applyScript = Join-Path $EditableRoot "scripts\apply-local-edits-windows.ps1"
    $content = "@echo off`r`npowershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$applyScript`"`r`npause`r`n"
    $encoding = New-Object System.Text.UTF8Encoding($true)
    [IO.File]::WriteAllText($shortcut, $content, $encoding)
}

Disable-AutoUpdate
$env:CHEONGNYEON_DISABLE_AUTO_UPDATE = "1"
$env:CHEONGNYEON_NO_LAUNCH = "1"
$env:CHEONGNYEON_SKIP_APP_INSTALL = "1"
Write-Step "ChatGPT 앱은 변경하지 않고 플러그인만 설치합니다."
$cacheBuster = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$baseInstallerUrl = "https://raw.githubusercontent.com/$RepositorySource/$Ref/install-windows.ps1?cachebust=$cacheBuster"
$baseInstallerSource = Invoke-RestMethod -Uri $baseInstallerUrl
& ([scriptblock]::Create([string]$baseInstallerSource))

Download-EditableCopy
$script:CodexExecutable = Get-CodexCommand
if (-not $script:CodexExecutable) { throw "플러그인 기능이 있는 Codex 실행 파일을 찾지 못했습니다." }

Invoke-Codex -Arguments @("plugin", "remove", $PluginSelector, "--json") -IgnoreFailure -Capture | Out-Null
Invoke-Codex -Arguments @("plugin", "marketplace", "remove", $MarketplaceName, "--json") -IgnoreFailure -Capture | Out-Null
Invoke-Codex -Arguments @("plugin", "marketplace", "add", $EditableRoot, "--json") -Capture | Out-Null
Invoke-Codex -Arguments @("plugin", "add", $PluginSelector, "--json") -Capture | Out-Null

$plugins = (Invoke-Codex -Arguments @("plugin", "list", "--json") -Capture) | ConvertFrom-Json
$installed = $plugins.installed | Where-Object { $_.pluginId -eq $PluginSelector } | Select-Object -First 1
if (-not $installed -or -not $installed.enabled -or $installed.marketplaceSource.sourceType -ne "local") {
    throw "설치된 플러그인이 로컬 수정본에 연결되지 않았습니다."
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
