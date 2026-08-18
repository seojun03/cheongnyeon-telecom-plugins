@echo off
setlocal
chcp 65001 >nul
title Cheongnyeon Telecom Blog Plugin Installer

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-from-download-windows.ps1"
set "INSTALL_RESULT=%ERRORLEVEL%"

echo.
if not "%INSTALL_RESULT%"=="0" (
  echo Installation failed. Please send a screenshot of this window to the plugin author.
) else (
  echo Installation completed. You can close this window and open ChatGPT.
)
echo.
pause
exit /b %INSTALL_RESULT%
