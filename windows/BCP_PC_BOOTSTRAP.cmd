@echo off
setlocal EnableExtensions
title BCP PC Bootstrap
set "BCP_DIR=%LOCALAPPDATA%\BCP\pc-node"
set "SERVER=%BCP_DIR%\bcp_server.py"
set "RAW_URL=https://raw.githubusercontent.com/Terminator364/BCP/main/pc-node/bcp_server.py"

echo.
echo ============================================================
echo   BCP PC Bootstrap - POC V0.1
echo ============================================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    set "PY=python"
  ) else (
    echo [FAIL] Python 3 is not installed or not in PATH.
    echo Install Python 3, then run this file again.
    pause
    exit /b 1
  )
)

if not exist "%BCP_DIR%" mkdir "%BCP_DIR%" >nul 2>nul

echo [1/4] Downloading current BCP PC node...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing '%RAW_URL%' -OutFile '%SERVER%'"
if errorlevel 1 (
  echo [FAIL] Could not download bcp_server.py
  pause
  exit /b 1
)

echo [2/4] Starting BCP PC node...
start "BCP PC Node" cmd /k "%PY% "%SERVER%" --bind 0.0.0.0 --port 8765"
timeout /t 3 /nobreak >nul

set "TOKEN_FILE=%BCP_DIR%\state\bcp_token.txt"
if not exist "%TOKEN_FILE%" (
  echo [FAIL] BCP token file was not created.
  echo Look at the "BCP PC Node" window for the error.
  pause
  exit /b 1
)

set /p BCP_TOKEN=<"%TOKEN_FILE%"

echo [3/4] Detecting LAN IPv4...
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command ^
  "$ips=Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue ^| Where-Object {$_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254*'} ^| Select-Object -ExpandProperty IPAddress; $ips -join ', '"`) do set "BCP_IPS=%%I"

set "INFO=%USERPROFILE%\Desktop\BCP_FIELD_INFO.txt"
(
  echo BCP FIELD TEST INFO
  echo ===================
  echo.
  echo Server port: 8765
  echo LAN IPv4 candidates: %BCP_IPS%
  echo Bearer token: %BCP_TOKEN%
  echo.
  echo Phone server URL:
  echo http://YOUR_PC_LAN_IP:8765
  echo.
  echo Health check:
  echo http://YOUR_PC_LAN_IP:8765/health
  echo.
  echo Project for first test:
  echo buildhub-test
) > "%INFO%"

echo [4/4] Ready.
echo.
echo LAN IPv4 candidates: %BCP_IPS%
echo Bearer token: %BCP_TOKEN%
echo.
echo A copy was saved to:
echo %INFO%
echo.
echo On the old phone:
echo   1. Install BCP Edge APK.
echo   2. Server = http://ONE_OF_THE_IPS_ABOVE:8765
echo   3. Token  = value above
echo   4. Project = buildhub-test
echo   5. Tap "Tester /health"
echo.
echo IMPORTANT: Keep this test on your trusted LAN. Do not port-forward 8765.
echo.
pause
endlocal
