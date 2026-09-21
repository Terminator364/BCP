@echo off
setlocal
cd /d "%~dp0"
echo BCP Nexus - nouvelle autorisation Cloudflare (one-shot)
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0NEXUS_AUTH_RETRY_CURRENT.ps1"
set RC=%ERRORLEVEL%
echo.
if "%RC%"=="0" (
  echo RESULTAT: OK
) else if "%RC%"=="10" (
  echo RESULTAT: ATTENTE RESEAU - reprise automatique, rien a refaire
) else (
  echo RESULTAT: HOLD/ECHEC code %RC%
)
echo.
pause
exit /b %RC%
