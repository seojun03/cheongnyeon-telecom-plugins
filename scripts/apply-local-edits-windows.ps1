[CmdletBinding()]
param(
    [string]$CodexPath = $env:CHEONGNYEON_CODEX_PATH,
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" })
)

$ErrorActionPreference = "Stop"
$PluginName = "cheongnyeon-telecom-blog"
$MarketplaceName = "cheongnyeon-telecom"
$PluginSelector = "$PluginName@$MarketplaceName"
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$PluginRoot = Join-Path $RepoRoot "plugins\$PluginName"
$ManifestPath = Join-Path $PluginRoot ".codex-plugin\plugin.json"
$SkillPath = Join-Path $PluginRoot "skills\$PluginName\SKILL.md"

function Write-Step([string]$Message) {
    Write-Host "[청년통신 로컬 수정 적용] $Message" -ForegroundColor Cyan
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

if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "플러그인 매니페스트를 찾지 못했습니다: $ManifestPath"
}
if (-not (Test-Path -LiteralPath $SkillPath)) {
    throw "수정할 SKILL.md를 찾지 못했습니다: $SkillPath"
}
if (-not (Test-Path -LiteralPath $CodexHome)) {
    New-Item -ItemType Directory -Path $CodexHome -Force | Out-Null
}
$env:CODEX_HOME = $CodexHome
$codex = Get-CodexCommand
if (-not $codex) {
    throw "플러그인 기능이 있는 Codex 실행 파일을 찾지 못했습니다."
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$baseVersion = ([string]$manifest.version -split "\+", 2)[0]
$cacheBuster = [DateTime]::UtcNow.ToString("yyyyMMddHHmmss")
$newVersion = "$baseVersion+codex.local.$cacheBuster"
$manifest.version = $newVersion
$encoding = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($ManifestPath, ($manifest | ConvertTo-Json -Depth 100) + [Environment]::NewLine, $encoding)

Write-Step "로컬 지침을 재설치합니다: $newVersion"
& $codex plugin add $PluginSelector --json | Out-Null
if ($LASTEXITCODE -ne 0) { throw "플러그인 재설치에 실패했습니다." }

$plugins = (& $codex plugin list --json 2>&1 | Out-String) | ConvertFrom-Json
$installed = $plugins.installed | Where-Object { $_.pluginId -eq $PluginSelector } | Select-Object -First 1
if (-not $installed -or -not $installed.enabled -or [string]$installed.version -ne $newVersion) {
    throw "수정한 버전의 재설치를 확인하지 못했습니다."
}
if ($installed.marketplaceSource.sourceType -ne "local") {
    throw "로컬 편집본이 아닌 마켓플레이스에 연결되어 있습니다. 편집용 설치기를 다시 실행하세요."
}

Write-Step "적용 완료: ChatGPT에서 새 작업을 열어 테스트하세요."
Write-Step "수정 파일: $SkillPath"
