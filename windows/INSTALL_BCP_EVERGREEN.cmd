@echo off
setlocal EnableExtensions
title BCP Evergreen Installer 0.2.0

net session >nul 2>&1
if %errorlevel% neq 0 (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

set "ROOT=%LOCALAPPDATA%\BCP"
set "BIN=%ROOT%\bin"
set "TELEM=%ROOT%\telemetry"
set "SERVER=%BIN%\bcp_server.ps1"
set "SUPERVISOR=%BIN%\bcp_supervisor.ps1"
set "SERVER_URL=https://raw.githubusercontent.com/Terminator364/BCP/d85747e243270c44f722c88da72c5c761fb9640b/pc-node/bcp_server.ps1"
set "SUP_URL=https://raw.githubusercontent.com/Terminator364/BCP/d85747e243270c44f722c88da72c5c761fb9640b/pc-node/bcp_supervisor.ps1"

if not exist "%BIN%" mkdir "%BIN%"
if not exist "%TELEM%" mkdir "%TELEM%"

echo [1/6] Downloading BCP resident components...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing '%SERVER_URL%' -OutFile '%SERVER%.new'; Invoke-WebRequest -UseBasicParsing '%SUP_URL%' -OutFile '%SUPERVISOR%.new'; Move-Item -Force '%SERVER%.new' '%SERVER%'; Move-Item -Force '%SUPERVISOR%.new' '%SUPERVISOR%'"
if errorlevel 1 (
  echo [FAIL] Download failed.
  pause
  exit /b 1
)

echo [2/6] Setting active Windows network to Private...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$c=Get-NetIPConfiguration ^| Where-Object {$_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up'} ^| Select-Object -First 1; if(-not $c){throw 'No active IPv4 interface'}; $p=Get-NetConnectionProfile -InterfaceIndex $c.InterfaceIndex; if($p.NetworkCategory -ne 'Private'){Set-NetConnectionProfile -InterfaceIndex $c.InterfaceIndex -NetworkCategory Private}"
if errorlevel 1 (
  echo [WARN] Could not change network profile automatically.
)

echo [3/6] Installing local firewall rule...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetFirewallRule -DisplayName 'BCP Local LAN 8765' -ErrorAction SilentlyContinue ^| Remove-NetFirewallRule -ErrorAction SilentlyContinue; New-NetFirewallRule -DisplayName 'BCP Local LAN 8765' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765 -Profile Private -RemoteAddress LocalSubnet ^| Out-Null"
if errorlevel 1 (
  echo [FAIL] Firewall rule could not be installed.
  pause
  exit /b 1
)

echo [4/6] Registering resident agent...
schtasks /Delete /TN "BCP Resident Agent" /F >nul 2>nul
schtasks /Create /TN "BCP Resident Agent" /SC ONLOGON /RL HIGHEST /F /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%SUPERVISOR%"" >nul
if errorlevel 1 (
  echo [FAIL] Scheduled task registration failed.
  pause
  exit /b 1
)

echo [5/6] Starting resident agent now...
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%SUPERVISOR%"
timeout /t 3 /nobreak >nul

echo [6/6] Local health check...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try{$r=Invoke-RestMethod -UseBasicParsing 'http://127.0.0.1:8765/health' -TimeoutSec 4; if(-not $r.ok){exit 2}; Write-Host '[PASS] BCP resident node is healthy'}catch{Write-Host '[WARN] health not ready yet:' $_.Exception.Message}"
echo.
echo ============================================================
echo BCP EVERGREEN INSTALLED
echo ============================================================
echo Future PC BCP server updates are automatic.
echo Telemetry lives under:
echo %LOCALAPPDATA%\BCP\telemetry
echo.
echo BCP Edge v0.2 will discover and pair automatically.
echo No IP or token typing in normal mode.
echo.
pause
