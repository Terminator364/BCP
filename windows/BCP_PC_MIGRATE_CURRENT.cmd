@echo off
setlocal
title BCP PC Migration
powershell.exe -NoProfile -Command "$p=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent()); if($p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){exit 0}else{exit 1}"
if errorlevel 1 (
  powershell.exe -NoProfile -Command "Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','%~dp0BCP_PC_MIGRATE_CURRENT.ps1')"
  exit /b
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BCP_PC_MIGRATE_CURRENT.ps1"
exit /b %errorlevel%
