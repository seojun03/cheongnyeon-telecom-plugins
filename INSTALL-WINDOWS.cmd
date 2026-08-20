@echo off
setlocal
chcp 65001 >nul
title Cheongnyeon Telecom Blog Plugin Installer

set "LOCAL_INSTALLER=%~dp0install-from-download-windows.ps1"

if exist "%LOCAL_INSTALLER%" (
  powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%LOCAL_INSTALLER%"
) else (
  echo.
  echo Complete ZIP contents were not found next to INSTALL-WINDOWS.cmd.
  echo Downloading and extracting a complete copy before installation...
  powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference = 'Stop';" ^
    "$archiveSource = $env:CHEONGNYEON_BOOTSTRAP_ARCHIVE;" ^
    "$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('cheongnyeon-telecom-bootstrap-' + [Guid]::NewGuid().ToString('N'));" ^
    "try {" ^
    "  New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null;" ^
    "  $archive = Join-Path $tempRoot 'source.zip';" ^
    "  if (-not [string]::IsNullOrWhiteSpace($archiveSource) -and (Test-Path -LiteralPath $archiveSource -PathType Leaf)) {" ^
    "    Copy-Item -LiteralPath $archiveSource -Destination $archive -Force;" ^
    "  } else {" ^
    "    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
    "    Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/seojun03/cheongnyeon-telecom-plugins/archive/refs/heads/main.zip' -OutFile $archive;" ^
    "  };" ^
    "  $expanded = Join-Path $tempRoot 'expanded';" ^
    "  Expand-Archive -LiteralPath $archive -DestinationPath $expanded -Force;" ^
    "  $installer = Join-Path $expanded 'cheongnyeon-telecom-plugins-main\install-from-download-windows.ps1';" ^
    "  if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) { throw 'Downloaded ZIP is missing install-from-download-windows.ps1.' };" ^
    "  & $installer;" ^
    "} finally {" ^
    "  if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue };" ^
    "}"
)
set "INSTALL_RESULT=%ERRORLEVEL%"

echo.
if not "%INSTALL_RESULT%"=="0" (
  echo Installation failed. Please send a screenshot of this window to the plugin author.
) else (
  echo Installation completed. You can close this window and open ChatGPT.
)
echo.
if not "%CHEONGNYEON_SKIP_PAUSE%"=="1" pause
exit /b %INSTALL_RESULT%
