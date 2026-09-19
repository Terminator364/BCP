@echo off
setlocal EnableExtensions
title BCP PC Legacy Migration 0.3.x to 0.4.4

set "PIN=c0d10a286a5a4e18d755a31811e7b479f7ad9cff"
set "BASE=https://raw.githubusercontent.com/Terminator364/BCP/%PIN%/windows"
set "TMP=%TEMP%\BCP_PC_MIGRATE_0_4_4"
set "INSTALLER_SHA=3ad1594a948768b15f583a7806eb7fb084935ecbcd1ccac0079ce88e43f6d53e"
set "SERVER_SHA=c23e9d79262884b399cfb3abba382dae3c4b18ccbe158fe818e6497f7a493993"

powershell.exe -NoProfile -Command "$p=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent()); if($p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){exit 0}else{exit 1}"
if errorlevel 1 (
  echo Demande d'autorisation Windows...
  powershell.exe -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo.
echo ============================================================
echo  BCP PC migration 0.3.x -^> 0.4.4
echo ============================================================
echo.

if exist "%TMP%" rmdir /s /q "%TMP%"
mkdir "%TMP%" || goto :fail

echo [1/4] Telechargement des fichiers pinnes...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue';" ^
  "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
  "Invoke-WebRequest -UseBasicParsing -Uri '%BASE%/INSTALL_BCP_FINAL.ps1' -OutFile '%TMP%\INSTALL_BCP_FINAL.ps1';" ^
  "Invoke-WebRequest -UseBasicParsing -Uri '%BASE%/bcp_server.py' -OutFile '%TMP%\bcp_server.py';" ^
  "$ih=(Get-FileHash -Algorithm SHA256 '%TMP%\INSTALL_BCP_FINAL.ps1').Hash.ToLowerInvariant();" ^
  "$sh=(Get-FileHash -Algorithm SHA256 '%TMP%\bcp_server.py').Hash.ToLowerInvariant();" ^
  "if($ih -ne '%INSTALLER_SHA%'){throw 'INSTALLER_SHA256_MISMATCH '+$ih};" ^
  "if($sh -ne '%SERVER_SHA%'){throw 'SERVER_SHA256_MISMATCH '+$sh};" ^
  "Write-Host 'HASH_READBACK=PASS'"
if errorlevel 1 goto :fail

echo [2/4] Installation transactionnelle BCP 0.4.4...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TMP%\INSTALL_BCP_FINAL.ps1"
if errorlevel 1 goto :fail

echo [3/4] Verification runtime local...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; $deadline=(Get-Date).AddSeconds(25); do { try { $h=Invoke-RestMethod -UseBasicParsing -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2; if($h.ok -eq $true -and [string]$h.version -eq '0.4.4'){Write-Host ('RUNTIME_READBACK=PASS version='+$h.version); exit 0} } catch {}; Start-Sleep -Milliseconds 600 } while((Get-Date) -lt $deadline); throw 'BCP_0_4_4_HEALTH_TIMEOUT'"
if errorlevel 1 goto :fail

echo [4/4] Nettoyage temporaire...
rmdir /s /q "%TMP%" >nul 2>&1

echo.
echo ============================================================
echo  BCP 0.4.4 = ACTIF SUR CE PC
echo  Ouvre simplement BCP Edge sur le telephone.
echo ============================================================
echo.
timeout /t 8 >nul
exit /b 0

:fail
echo.
echo ============================================================
echo  MIGRATION BCP = ECHEC
echo  Aucun second essai automatique n'est lance.
echo  Le receipt/log BCP permettra le diagnostic.
echo ============================================================
echo.
pause
exit /b 1
