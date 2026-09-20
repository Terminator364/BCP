@echo off
setlocal
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\Tunnel_PC_G4\runtime\python.exe"
if not exist "%PY%" (
  echo HOLD: ChatGPT-PC Python runtime introuvable.
  pause
  exit /b 20
)
"%PY%" "%~dp0offline_install_6034.py" --package "%~dp0Tunnel_PC_G6_6.0.34_2003_RECOVERY_DRIVEFS_RESULT_HOTFIX.zip"
set RC=%ERRORLEVEL%
echo.
if "%RC%"=="0" (echo RESULTAT: OK) else (echo RESULTAT: HOLD/ECHEC code %RC%)
echo.
pause
exit /b %RC%
