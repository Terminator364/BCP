@echo off
setlocal
title BCP Final Acceptance Campaign
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BCP_FINAL_ACCEPTANCE_CURRENT.ps1"
exit /b %errorlevel%
