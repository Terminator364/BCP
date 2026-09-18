@echo off
setlocal
title BCP Final Bootstrap 0.3.1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_BCP_FINAL.ps1"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo BCP bootstrap returned code %RC%.
  pause
)
exit /b %RC%
