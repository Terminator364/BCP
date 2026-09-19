@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_BCP_PRODUCT_CURRENT.ps1"
set RC=%ERRORLEVEL%
if not "%RC%"=="0" (
  echo.
  echo BCP PRODUCT INSTALL FAILED - code %RC%
  pause
)
exit /b %RC%
