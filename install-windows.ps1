[CmdletBinding()]
param(
    [string]$RepositorySource = "seojun03/cheongnyeon-telecom-plugins",
    [string]$Ref = "main",
    [string]$CodexPath = "",
    [switch]$SkipAppInstall,
    [switch]$SkipDependencyInstall,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$MarketplaceName = "cheongnyeon-telecom"
$PluginName = "cheongnyeon-telecom-blog"
$LegacyMarketplaceName = "cheongnyeon-telecom-share"

function Write-Step([string]$Message) {
    Write-Host "[청년통신 설치] $Message" -ForegroundColor Cyan
}

function Refresh-ProcessPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Get-ChatGPTPackage {
    Get-AppxPackage | Where-Object {
        $_.Name -match "ChatGPT" -or $_.PackageFamilyName -match "ChatGPT"
    } | Select-Object -First 1
}

function Install-WingetPackage([string]$Id, [string]$Source = "winget") {
    Write-Step "$Id 설치를 확인합니다."
    & winget install --id $Id --exact --source $Source --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        throw "$Id 설치에 실패했습니다. winget 종료 코드: $LASTEXITCODE"
    }
    Refresh-ProcessPath
}

function Test-PythonAvailable {
    foreach ($name in @("py.exe", "python.exe")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command) {
            & $command.Source --version *> $null
            if ($LASTEXITCODE -eq 0) {
                return $true
            }
        }
    }
    return $false
}

function Get-CodexCommand {
    if ($CodexPath) {
        if (-not (Test-Path -LiteralPath $CodexPath)) {
            throw "지정한 CodexPath를 찾을 수 없습니다: $CodexPath"
        }
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

function Invoke-Codex([string[]]$Arguments, [switch]$IgnoreFailure, [switch]$Capture) {
    if ($Capture) {
        $output = & $script:CodexExecutable @Arguments 2>&1
    } else {
        & $script:CodexExecutable @Arguments
        $output = $null
    }
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0 -and -not $IgnoreFailure) {
        throw "Codex 명령에 실패했습니다: codex $($Arguments -join ' ') (종료 코드 $exitCode)"
    }
    if ($Capture) {
        return ($output -join [Environment]::NewLine)
    }
}

if ($PSVersionTable.PSEdition -eq "Core" -and -not $IsWindows) {
    throw "이 설치기는 Windows PowerShell용입니다. macOS에서는 install-macos.sh를 사용하세요."
}

if (-not $SkipAppInstall) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget을 찾을 수 없습니다. Microsoft Store에서 '앱 설치 관리자'를 설치한 뒤 다시 실행하세요."
    }
    if (-not (Get-ChatGPTPackage)) {
        Install-WingetPackage -Id "9PLM9XGG6VKS" -Source "msstore"
    } else {
        Write-Step "ChatGPT Windows 앱이 이미 설치되어 있습니다."
    }
}

if (-not $SkipDependencyInstall) {
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
        Install-WingetPackage -Id "Git.Git"
    }
    if (-not (Test-PythonAvailable)) {
        Install-WingetPackage -Id "Python.Python.3.14"
    }
}

$script:CodexExecutable = Get-CodexCommand
if (-not $script:CodexExecutable) {
    if ($SkipDependencyInstall) {
        throw "플러그인 기능이 있는 Codex 실행 파일을 찾지 못했습니다."
    }
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        Install-WingetPackage -Id "OpenJS.NodeJS.LTS"
    }
    Write-Step "Codex CLI를 설치합니다."
    & npm.cmd install --global "@openai/codex"
    if ($LASTEXITCODE -ne 0) {
        throw "Codex CLI 설치에 실패했습니다."
    }
    Refresh-ProcessPath
    $script:CodexExecutable = Get-CodexCommand
}

if (-not $script:CodexExecutable) {
    throw "Codex 실행 파일을 찾지 못했습니다."
}

Invoke-Codex -Arguments @("plugin", "--help") -Capture | Out-Null
Write-Step "기존 청년통신 플러그인 연결을 정리합니다."
Invoke-Codex -Arguments @("plugin", "remove", "$PluginName@$LegacyMarketplaceName", "--json") -IgnoreFailure -Capture | Out-Null
Invoke-Codex -Arguments @("plugin", "marketplace", "remove", $LegacyMarketplaceName, "--json") -IgnoreFailure -Capture | Out-Null
Invoke-Codex -Arguments @("plugin", "remove", "$PluginName@$MarketplaceName", "--json") -IgnoreFailure -Capture | Out-Null
Invoke-Codex -Arguments @("plugin", "marketplace", "remove", $MarketplaceName, "--json") -IgnoreFailure -Capture | Out-Null

Write-Step "공개 GitHub 마켓플레이스를 등록합니다."
Invoke-Codex -Arguments @("plugin", "marketplace", "add", $RepositorySource, "--ref", $Ref, "--json") -Capture | Out-Null
Write-Step "청년통신 블로그 플러그인을 설치합니다."
Invoke-Codex -Arguments @("plugin", "add", "$PluginName@$MarketplaceName", "--json") -Capture | Out-Null

$pluginData = (Invoke-Codex -Arguments @("plugin", "list", "--json") -Capture) | ConvertFrom-Json
$installed = $pluginData.installed | Where-Object { $_.pluginId -eq "$PluginName@$MarketplaceName" } | Select-Object -First 1
if (-not $installed -or -not $installed.enabled) {
    throw "설치 후 플러그인 활성 상태를 확인하지 못했습니다."
}

if (-not $NoLaunch) {
    $package = Get-ChatGPTPackage
    if ($package) {
        try {
            [xml]$manifest = Get-Content -LiteralPath (Join-Path $package.InstallLocation "AppxManifest.xml")
            $applicationId = @($manifest.Package.Applications.Application)[0].Id
            Start-Process explorer.exe "shell:AppsFolder\$($package.PackageFamilyName)!$applicationId"
        } catch {
            Write-Warning "설치는 완료됐지만 ChatGPT 앱 자동 실행은 건너뜁니다. 시작 메뉴에서 직접 열어주세요."
        }
    }
}

Write-Host ""
Write-Host "설치 완료: $($installed.pluginId) $($installed.version)" -ForegroundColor Green
Write-Host "ChatGPT 앱에서 '청년통신 블로그 글을 자동모드로 작성해줘'라고 입력하세요."
