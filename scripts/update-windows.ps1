[CmdletBinding()]
param(
    [string]$RepositorySource = $(if ($env:CHEONGNYEON_REPOSITORY_SOURCE) { $env:CHEONGNYEON_REPOSITORY_SOURCE } else { "seojun03/cheongnyeon-telecom-plugins" }),
    [string]$Ref = $(if ($env:CHEONGNYEON_REPOSITORY_REF) { $env:CHEONGNYEON_REPOSITORY_REF } else { "main" }),
    [string]$CodexPath = $env:CHEONGNYEON_CODEX_PATH,
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" })
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$MarketplaceName = "cheongnyeon-telecom"
$PluginName = "cheongnyeon-telecom-blog"
$PluginSelector = "$PluginName@$MarketplaceName"
$ManifestUrl = "https://raw.githubusercontent.com/$RepositorySource/$Ref/plugins/$PluginName/.codex-plugin/plugin.json"
$InstallerUrl = "https://raw.githubusercontent.com/$RepositorySource/$Ref/install-windows.ps1"

function Write-UpdateLog([string]$Message) {
    Write-Host "[청년통신 자동 업데이트] $Message"
}

function Get-ChatGPTPackage {
    Get-AppxPackage | Where-Object {
        $_.Name -match "ChatGPT" -or $_.PackageFamilyName -match "ChatGPT"
    } | Select-Object -First 1
}

function Get-CodexCommand {
    if ($CodexPath -and (Test-Path -LiteralPath $CodexPath)) {
        return (Resolve-Path -LiteralPath $CodexPath).Path
    }
    foreach ($name in @("codex.exe", "codex.cmd", "codex")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command) {
            return $command.Source
        }
    }
    $package = Get-ChatGPTPackage
    if ($package -and $package.InstallLocation) {
        $embedded = Get-ChildItem -LiteralPath $package.InstallLocation -Filter "codex.exe" -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($embedded) {
            return $embedded.FullName
        }
    }
    return $null
}

if (-not (Test-Path -LiteralPath $CodexHome)) {
    New-Item -ItemType Directory -Path $CodexHome -Force | Out-Null
}
$env:CODEX_HOME = $CodexHome
$script:CodexExecutable = Get-CodexCommand
if (-not $script:CodexExecutable) {
    throw "플러그인 기능이 있는 Codex 실행 파일을 찾지 못했습니다."
}

$remoteManifest = Invoke-RestMethod -Uri $ManifestUrl
$remoteVersion = [string]$remoteManifest.version
if (-not $remoteVersion) {
    throw "최신 플러그인 버전을 읽지 못했습니다."
}

$pluginData = (& $script:CodexExecutable plugin list --json 2>&1 | Out-String) | ConvertFrom-Json
$installed = $pluginData.installed | Where-Object { $_.pluginId -eq $PluginSelector } | Select-Object -First 1
$currentVersion = if ($installed) { [string]$installed.version } else { "" }
if ($currentVersion -eq $remoteVersion) {
    Write-UpdateLog "최신 버전입니다: $remoteVersion"
    exit 0
}

Write-UpdateLog "업데이트를 시작합니다: $(if ($currentVersion) { $currentVersion } else { '미설치' }) → $remoteVersion"
$env:CHEONGNYEON_CODEX_PATH = $script:CodexExecutable
$env:CHEONGNYEON_REPOSITORY_SOURCE = $RepositorySource
$env:CHEONGNYEON_REPOSITORY_REF = $Ref
$env:CHEONGNYEON_SKIP_APP_INSTALL = "1"
$env:CHEONGNYEON_SKIP_DEPENDENCY_INSTALL = "1"
$env:CHEONGNYEON_NO_LAUNCH = "1"
$env:CHEONGNYEON_SKIP_AUTO_UPDATE_SETUP = "1"
$installerSource = Invoke-RestMethod -Uri $InstallerUrl
& ([scriptblock]::Create([string]$installerSource))

$updatedData = (& $script:CodexExecutable plugin list --json 2>&1 | Out-String) | ConvertFrom-Json
$updated = $updatedData.installed | Where-Object { $_.pluginId -eq $PluginSelector } | Select-Object -First 1
if (-not $updated -or -not $updated.enabled -or [string]$updated.version -ne $remoteVersion) {
    throw "업데이트 후 버전 또는 활성 상태를 확인하지 못했습니다."
}

Write-UpdateLog "업데이트 완료: $($updated.version)"
if ($env:CHEONGNYEON_NO_NOTIFICATION -ne "1" -and (Get-Command msg.exe -ErrorAction SilentlyContinue)) {
    & msg.exe $env:USERNAME "청년통신 플러그인이 업데이트되었습니다. ChatGPT 앱을 다시 열면 최신 버전이 적용됩니다." 2>$null | Out-Null
}
