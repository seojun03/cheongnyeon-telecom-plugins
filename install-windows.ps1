[CmdletBinding()]
param(
    [string]$RepositorySource = $(if ($env:CHEONGNYEON_REPOSITORY_SOURCE) { $env:CHEONGNYEON_REPOSITORY_SOURCE } else { "seojun03/cheongnyeon-telecom-plugins" }),
    [string]$Ref = $(if ($env:CHEONGNYEON_REPOSITORY_REF) { $env:CHEONGNYEON_REPOSITORY_REF } else { "main" }),
    [string]$CodexPath = $env:CHEONGNYEON_CODEX_PATH,
    [switch]$SkipAppInstall = ($env:CHEONGNYEON_SKIP_APP_INSTALL -eq "1"),
    [switch]$SkipDependencyInstall = ($env:CHEONGNYEON_SKIP_DEPENDENCY_INSTALL -eq "1"),
    [switch]$DisableAutoUpdate = ($env:CHEONGNYEON_DISABLE_AUTO_UPDATE -eq "1"),
    [switch]$SkipAutoUpdateSetup = ($env:CHEONGNYEON_SKIP_AUTO_UPDATE_SETUP -eq "1"),
    [switch]$SkipSchedulerActivation = ($env:CHEONGNYEON_SKIP_SCHEDULER_ACTIVATION -eq "1"),
    [switch]$NoLaunch = ($env:CHEONGNYEON_NO_LAUNCH -eq "1")
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$MarketplaceName = "cheongnyeon-telecom"
$PluginName = "cheongnyeon-telecom-blog"
$LegacyMarketplaceName = "cheongnyeon-telecom-share"
$AutoUpdateTaskName = $(if ($env:CHEONGNYEON_AUTO_UPDATE_TASK_NAME) { $env:CHEONGNYEON_AUTO_UPDATE_TASK_NAME } else { "CheongnyeonTelecomPluginUpdate" })
$AutoUpdateRoot = $(if ($env:CHEONGNYEON_AUTO_UPDATE_ROOT) { $env:CHEONGNYEON_AUTO_UPDATE_ROOT } else { Join-Path $env:LOCALAPPDATA "CheongnyeonTelecom" })

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
        $details = if ($output) { "`n$($output -join [Environment]::NewLine)" } else { "" }
        throw "Codex 명령에 실패했습니다: codex $($Arguments -join ' ') (종료 코드 $exitCode)$details"
    }
    if ($Capture) {
        return ($output -join [Environment]::NewLine)
    }
}

function ConvertTo-SingleQuotedLiteral([string]$Value) {
    return "'$(($Value -replace "'", "''"))'"
}

function Install-AutoUpdate {
    if ($DisableAutoUpdate) {
        Write-Step "자동 업데이트 등록을 건너뜁니다."
        return
    }
    if ($SkipAutoUpdateSetup) {
        return
    }

    New-Item -ItemType Directory -Path $AutoUpdateRoot -Force | Out-Null
    $bootstrapPath = Join-Path $AutoUpdateRoot "run-update.ps1"
    $logPath = Join-Path $AutoUpdateRoot "plugin-update.log"
    $updaterUrl = "https://raw.githubusercontent.com/$RepositorySource/$Ref/scripts/update-windows.ps1"
    $codeHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
    $bootstrapLines = @(
        '$ErrorActionPreference = "Stop"',
        '$ProgressPreference = "SilentlyContinue"',
        "`$env:CODEX_HOME = $(ConvertTo-SingleQuotedLiteral $codeHome)",
        "`$env:CHEONGNYEON_CODEX_PATH = $(ConvertTo-SingleQuotedLiteral $script:CodexExecutable)",
        "`$env:CHEONGNYEON_REPOSITORY_SOURCE = $(ConvertTo-SingleQuotedLiteral $RepositorySource)",
        "`$env:CHEONGNYEON_REPOSITORY_REF = $(ConvertTo-SingleQuotedLiteral $Ref)",
        "`$source = Invoke-RestMethod -Uri $(ConvertTo-SingleQuotedLiteral $updaterUrl)",
        '& ([scriptblock]::Create([string]$source))'
    )
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($bootstrapPath, ($bootstrapLines -join [Environment]::NewLine) + [Environment]::NewLine, $encoding)

    if ($SkipSchedulerActivation) {
        Write-Step "자동 업데이트 실행 파일을 만들었습니다."
        return
    }

    $powerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $scheduledCommand = "& $(ConvertTo-SingleQuotedLiteral $bootstrapPath) *> $(ConvertTo-SingleQuotedLiteral $logPath)"
    $actionArgs = "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -Command `"$scheduledCommand`""
    $action = New-ScheduledTaskAction -Execute $powerShell -Argument $actionArgs
    $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
    $periodicTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Hours 6)
    $principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
    Register-ScheduledTask -TaskName $AutoUpdateTaskName -Action $action -Trigger @($logonTrigger, $periodicTrigger) -Principal $principal -Settings $settings -Force | Out-Null
    Write-Step "자동 업데이트를 등록했습니다: 로그인 시 및 6시간마다 확인"
}

if ($PSVersionTable.PSEdition -eq "Core" -and -not $IsWindows) {
    throw "이 설치기는 Windows PowerShell용입니다. macOS에서는 install-macos.sh를 사용하세요."
}

if ($env:CODEX_HOME -and -not (Test-Path -LiteralPath $env:CODEX_HOME)) {
    New-Item -ItemType Directory -Path $env:CODEX_HOME -Force | Out-Null
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

Install-AutoUpdate

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
