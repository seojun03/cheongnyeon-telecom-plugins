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
$CacheBuster = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$ManifestUrl = "https://raw.githubusercontent.com/$RepositorySource/$Ref/plugins/$PluginName/.codex-plugin/plugin.json?cachebust=$CacheBuster"
$InstallerUrl = "https://raw.githubusercontent.com/$RepositorySource/$Ref/install-windows.ps1?cachebust=$CacheBuster"

function Write-UpdateLog([string]$Message) {
    Write-Host "[청년통신 자동 업데이트] $Message"
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
    if ($env:LOCALAPPDATA) { $candidates += (Join-Path $env:LOCALAPPDATA "Programs\OpenAI\Codex\bin\codex.exe") }
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

function Invoke-Codex([string[]]$Arguments, [switch]$Capture) {
    $stderrPath = Join-Path ([IO.Path]::GetTempPath()) ("cheongnyeon-codex-stderr-" + [Guid]::NewGuid().ToString("N") + ".log")
    $previousNativeErrorActionPreference = $ErrorActionPreference
    try {
        try {
            $ErrorActionPreference = "Continue"
            $global:LASTEXITCODE = $null
            $output = @(& $script:CodexExecutable @Arguments 2>$stderrPath)
            $exitCode = $LASTEXITCODE
        } catch {
            throw "Codex 실행 파일을 시작하지 못했습니다: $script:CodexExecutable. $($_.Exception.Message)"
        }
        $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue } else { "" }
        if ($null -eq $exitCode) { throw "Codex 실행 파일을 시작하지 못했습니다: $script:CodexExecutable" }
        if ($exitCode -ne 0) {
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

if (-not (Test-Path -LiteralPath $CodexHome)) {
    New-Item -ItemType Directory -Path $CodexHome -Force | Out-Null
}
$env:CODEX_HOME = $CodexHome
$script:CodexExecutable = Get-CodexCommand
if (-not $script:CodexExecutable) {
    throw "플러그인 기능이 있는 Codex 실행 파일을 찾지 못했습니다."
}
$env:CHEONGNYEON_CODEX_PATH = $script:CodexExecutable

$remoteManifest = Invoke-RestMethod -Uri $ManifestUrl
$remoteVersion = [string]$remoteManifest.version
if (-not $remoteVersion) {
    throw "최신 플러그인 버전을 읽지 못했습니다."
}

$pluginData = (Invoke-Codex -Arguments @("plugin", "list", "--json") -Capture) | ConvertFrom-Json
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

$updatedData = (Invoke-Codex -Arguments @("plugin", "list", "--json") -Capture) | ConvertFrom-Json
$updated = $updatedData.installed | Where-Object { $_.pluginId -eq $PluginSelector } | Select-Object -First 1
if (-not $updated -or -not $updated.enabled -or [string]$updated.version -ne $remoteVersion) {
    throw "업데이트 후 버전 또는 활성 상태를 확인하지 못했습니다."
}

Write-UpdateLog "업데이트 완료: $($updated.version)"
if ($env:CHEONGNYEON_NO_NOTIFICATION -ne "1" -and (Get-Command msg.exe -ErrorAction SilentlyContinue)) {
    & msg.exe $env:USERNAME "청년통신 플러그인이 업데이트되었습니다. ChatGPT 앱을 다시 열면 최신 버전이 적용됩니다." 2>$null | Out-Null
}
