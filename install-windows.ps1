[CmdletBinding()]
param(
    [string]$RepositorySource = $(if ($env:CHEONGNYEON_REPOSITORY_SOURCE) { $env:CHEONGNYEON_REPOSITORY_SOURCE } else { "seojun03/cheongnyeon-telecom-plugins" }),
    [string]$Ref = $(if ($env:CHEONGNYEON_REPOSITORY_REF) { $env:CHEONGNYEON_REPOSITORY_REF } else { "main" }),
    [string]$CodexPath = $env:CHEONGNYEON_CODEX_PATH,
    [switch]$SkipAppInstall = ($env:CHEONGNYEON_SKIP_APP_INSTALL -eq "1"),
    [switch]$SkipDependencyInstall = ($env:CHEONGNYEON_SKIP_DEPENDENCY_INSTALL -eq "1"),
    [switch]$DisableAutoUpdate = ($env:CHEONGNYEON_DISABLE_AUTO_UPDATE -eq "1"),
    [switch]$DependenciesOnly = ($env:CHEONGNYEON_DEPENDENCIES_ONLY -eq "1"),
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
    # Keep process-only entries as well as newly installed machine/user entries.
    # Replacing PATH outright can hide an existing Git, Python, Node, or Codex
    # command that was added only for the current PowerShell session.
    $pathEntries = (@($machine, $user, $env:Path) -join ";").Split(";", [System.StringSplitOptions]::RemoveEmptyEntries) |
        Select-Object -Unique
    $env:Path = $pathEntries -join ";"
}

function Get-ChatGPTPackage {
    Get-AppxPackage | Where-Object {
        $identity = "$($_.Name) $($_.PackageFamilyName) $($_.PackageFullName) $($_.InstallLocation)"
        $identity -match "ChatGPT|OpenAI|Codex"
    } | Select-Object -First 1
}

function Test-WingetPackageInstalled([string]$Id, [string]$Source = "winget") {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        return $false
    }

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        & winget list --id $Id --exact --source $Source --accept-source-agreements *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

function Install-WingetPackage([string]$Id, [string]$Source = "winget") {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget을 찾을 수 없습니다. Microsoft Store에서 '앱 설치 관리자'를 설치한 뒤 다시 실행하세요."
    }

    Write-Step "$Id 설치를 확인합니다."
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $global:LASTEXITCODE = $null
        & winget install --id $Id --exact --source $Source --accept-package-agreements --accept-source-agreements --silent
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
        $global:LASTEXITCODE = 0
    }

    # winget returns non-zero HRESULTs when the requested package is already
    # installed and current. Those are successful no-op outcomes for this installer.
    $alreadyCurrentExitCodes = @(
        -1978335189, # 0x8A15002B: no applicable update found
        -1978335153, # 0x8A15004F: upgrade version is not newer
        -1978335135  # 0x8A150061: package already installed
    )
    if ($null -eq $exitCode -or ($exitCode -ne 0 -and $alreadyCurrentExitCodes -notcontains $exitCode)) {
        throw "$Id 설치에 실패했습니다. winget 종료 코드: $exitCode"
    }
    if ($alreadyCurrentExitCodes -contains $exitCode) {
        Write-Step "$Id 최신 버전이 이미 설치되어 있어 계속합니다."
    }
    Refresh-ProcessPath
}

function Test-PythonAvailable {
    foreach ($name in @("py.exe", "python.exe")) {
        foreach ($command in @(Get-Command $name -All -ErrorAction SilentlyContinue)) {
            if (-not $command.Source) { continue }
            $previousErrorActionPreference = $ErrorActionPreference
            try {
                # Windows' Microsoft Store execution alias can write a NativeCommandError
                # while Python is not installed. Treat that alias as unavailable instead of
                # aborting the entire plugin installer.
                $ErrorActionPreference = "Continue"
                $global:LASTEXITCODE = $null
                & $command.Source --version *> $null
                if ($LASTEXITCODE -eq 0) {
                    return $true
                }
            } catch {
                continue
            } finally {
                $ErrorActionPreference = $previousErrorActionPreference
                $global:LASTEXITCODE = 0
            }
        }
    }
    return $false
}

function Test-CodexExecutable([string]$Candidate) {
    if ([string]::IsNullOrWhiteSpace($Candidate)) {
        return $false
    }

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        if (-not (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
            return $false
        }
        $resolved = (Resolve-Path -LiteralPath $Candidate).Path
        # Appx/WindowsApps can expose a Codex.exe that exists but cannot be
        # launched outside the app package. A real candidate must execute the
        # exact plugin command this installer needs.
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
            if ($command.Source -and (Test-Path -LiteralPath $command.Source -PathType Leaf)) {
                return $command.Source
            }
        }
    }
    foreach ($candidate in @(
        $(if ($env:ProgramFiles) { Join-Path $env:ProgramFiles "nodejs\npm.cmd" }),
        $(if (${env:ProgramFiles(x86)}) { Join-Path ${env:ProgramFiles(x86)} "nodejs\npm.cmd" }),
        $(if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA "Programs\nodejs\npm.cmd" })
    )) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

function Get-CodexCommand {
    $candidates = @()

    # Read the environment dynamically. The editable wrapper invokes this
    # installer in a child scope and then reuses the verified path it exports.
    foreach ($candidate in @($CodexPath, $env:CHEONGNYEON_CODEX_PATH)) {
        if (-not [string]::IsNullOrWhiteSpace($candidate)) {
            $candidates += $candidate
        }
    }

    # The official standalone installer uses this stable per-user path.
    if ($env:LOCALAPPDATA) {
        $candidates += (Join-Path $env:LOCALAPPDATA "Programs\OpenAI\Codex\bin\codex.exe")
    }

    # Prefer the npm wrapper over similarly named executable aliases, then
    # inspect every PATH match rather than accepting only the first one.
    foreach ($name in @("codex.cmd", "codex.exe", "codex")) {
        foreach ($command in @(Get-Command $name -All -ErrorAction SilentlyContinue)) {
            if ($command.Source) {
                $candidates += $command.Source
            }
        }
    }

    if ($env:APPDATA) {
        $candidates += (Join-Path $env:APPDATA "npm\codex.cmd")
    }
    if ($env:LOCALAPPDATA) {
        $candidates += (Join-Path $env:LOCALAPPDATA "npm\codex.cmd")
    }

    $npm = Get-NpmCommand
    if ($npm) {
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "SilentlyContinue"
            $prefixOutput = @(& $npm prefix --global 2>$null)
            if ($LASTEXITCODE -eq 0 -and $prefixOutput.Count -gt 0) {
                $prefix = [string]$prefixOutput[-1]
                if (-not [string]::IsNullOrWhiteSpace($prefix)) {
                    $candidates += (Join-Path $prefix.Trim() "codex.cmd")
                }
            }
        } catch {
            # npm is only an optional discovery source here.
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

function Install-OfficialCodexCli {
    Write-Step "OpenAI 공식 Codex CLI를 설치합니다."
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
            throw "OpenAI 공식 Codex CLI 설치기의 PowerShell 문법을 확인하지 못했습니다."
        }

        $windowsPowerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
        if (-not (Test-Path -LiteralPath $windowsPowerShell -PathType Leaf)) {
            throw "Windows PowerShell 실행 파일을 찾지 못했습니다."
        }
        $ErrorActionPreference = "Continue"
        $global:LASTEXITCODE = $null
        $installOutput = @(& $windowsPowerShell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $tempInstaller 2>&1)
        $installExitCode = $LASTEXITCODE
        if ($null -eq $installExitCode -or $installExitCode -ne 0) {
            $details = if ($installOutput) { "`n$($installOutput -join [Environment]::NewLine)" } else { "" }
            throw "OpenAI 공식 Codex CLI 설치기가 종료 코드 $installExitCode로 중단됐습니다.$details"
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

function Install-CodexWithNpm([string]$NpmCommand) {
    $stderrPath = Join-Path ([IO.Path]::GetTempPath()) ("cheongnyeon-npm-stderr-" + [Guid]::NewGuid().ToString("N") + ".log")
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        try {
            $ErrorActionPreference = "Continue"
            $global:LASTEXITCODE = $null
            $output = @(& $NpmCommand install --global "@openai/codex" 2>$stderrPath)
            $exitCode = $LASTEXITCODE
        } catch {
            throw "npm.cmd를 실행하지 못했습니다: $($_.Exception.Message)"
        }
        $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue } else { "" }
        if ($null -eq $exitCode -or $exitCode -ne 0) {
            $details = if ($stderr) { "`n$stderr" } elseif ($output) { "`n$($output -join [Environment]::NewLine)" } else { "" }
            throw "npm Codex CLI 설치에 실패했습니다. 종료 코드: $exitCode$details"
        }
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue
        $global:LASTEXITCODE = 0
    }
}

function Invoke-Codex([string[]]$Arguments, [switch]$IgnoreFailure, [switch]$Capture) {
    $stderrPath = Join-Path ([IO.Path]::GetTempPath()) ("cheongnyeon-codex-stderr-" + [Guid]::NewGuid().ToString("N") + ".log")
    $previousNativeErrorActionPreference = $ErrorActionPreference
    try {
        try {
            # Windows PowerShell 5.1 wraps native stderr as NativeCommandError.
            # Exit code, not a warning written to stderr, determines success.
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
        if ($Capture) {
            return ($output -join [Environment]::NewLine)
        }
        if ($output) {
            $output | Write-Output
        }
    } finally {
        $ErrorActionPreference = $previousNativeErrorActionPreference
        Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue
        $global:LASTEXITCODE = 0
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
        '$cacheBuster = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()',
        "`$source = Invoke-RestMethod -Uri ($(ConvertTo-SingleQuotedLiteral $updaterUrl) + '?cachebust=' + `$cacheBuster)",
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
    if (Get-ChatGPTPackage) {
        Write-Step "ChatGPT Windows 앱이 이미 설치되어 있습니다."
    } elseif (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Warning "winget을 찾을 수 없어 ChatGPT 앱 자동 설치만 건너뜁니다. 플러그인 설치는 계속합니다."
    } elseif (Test-WingetPackageInstalled -Id "9PLM9XGG6VKS" -Source "msstore") {
        Write-Step "ChatGPT Windows 앱이 이미 설치되어 있습니다."
    } else {
        try {
            Install-WingetPackage -Id "9PLM9XGG6VKS" -Source "msstore"
        } catch {
            Write-Warning "ChatGPT 앱 자동 설치를 건너뜁니다. 플러그인 설치는 계속합니다. 앱이 없다면 https://chatgpt.com/download/ 에서 별도로 설치하세요. 원인: $($_.Exception.Message)"
        }
    }
}

if (-not $SkipDependencyInstall) {
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
        Install-WingetPackage -Id "Git.Git"
    }
    if (-not (Test-PythonAvailable)) {
        Install-WingetPackage -Id "Python.Python.3.14"
        if (-not (Test-PythonAvailable)) {
            throw "Python 설치 후 실행 가능 상태를 확인하지 못했습니다. PowerShell을 닫고 다시 연 뒤 설치 명령을 다시 실행해주세요."
        }
    }
}

$script:CodexExecutable = Get-CodexCommand
if (-not $script:CodexExecutable) {
    if ($SkipDependencyInstall) {
        throw "플러그인 기능이 있는 Codex 실행 파일을 찾지 못했습니다."
    }
    $officialInstallError = $null
    try {
        Install-OfficialCodexCli
    } catch {
        $officialInstallError = $_.Exception.Message
        Write-Warning "OpenAI 공식 Codex CLI 설치를 완료하지 못해 npm 방식을 시도합니다. 원인: $officialInstallError"
    }
    $script:CodexExecutable = Get-CodexCommand

    if (-not $script:CodexExecutable) {
        $npm = Get-NpmCommand
        if (-not $npm) {
            Install-WingetPackage -Id "OpenJS.NodeJS.LTS"
            $npm = Get-NpmCommand
        }
        if (-not $npm) {
            throw "Node.js 설치 후에도 npm.cmd를 찾지 못했습니다."
        }
        Write-Step "보조 방식으로 Codex CLI를 설치합니다."
        try {
            Install-CodexWithNpm -NpmCommand $npm
        } catch {
            throw "Codex CLI 설치에 실패했습니다. 공식 설치기 원인: $officialInstallError`nnpm 원인: $($_.Exception.Message)"
        }
        Refresh-ProcessPath
        $script:CodexExecutable = Get-CodexCommand
    }
}

if (-not $script:CodexExecutable) {
    throw "플러그인 명령을 실행할 수 있는 Codex CLI를 설치하지 못했습니다."
}

$env:CHEONGNYEON_CODEX_PATH = $script:CodexExecutable
Invoke-Codex -Arguments @("plugin", "--help") -Capture | Out-Null
if ($DependenciesOnly) {
    Write-Step "의존성과 Codex CLI 준비를 완료했습니다. 기존 플러그인 연결은 변경하지 않습니다."
    return
}
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
