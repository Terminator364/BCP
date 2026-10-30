# Install fast G2 starter without changing device secrets, trust, or signed APK.
param([switch]$Apply)
$ErrorActionPreference="Stop"
$root=Join-Path $env:LOCALAPPDATA 'BCP-Universal-Remote'
$source=Join-Path $root 'build-repo\universal-remote\windows\g2_autostart_fast.py'
$fast=Join-Path $root 'g2_autostart_fast.py'
$ps1=Join-Path $root 'g2_autostart.ps1'
if(-not(Test-Path $source)){throw 'FAST_START_SOURCE_NOT_AVAILABLE'}
$python=(Get-Command python.exe -ErrorAction Stop).Source
& $python -m py_compile $source
if($LASTEXITCODE -ne 0){throw 'FAST_START_SYNTAX_INVALID'}
$prior=Test-Path $ps1
Write-Output ('BCP_G2_FAST_PREFLIGHT_PASS; CURRENT_WRAPPER='+$prior)
if(-not $Apply){exit 0}
$backup=Join-Path $root ('backups\G2_FAST_START_'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $backup -Force|Out-Null
if($prior){Copy-Item $ps1 (Join-Path $backup 'g2_autostart.ps1') -Force}
if(Test-Path $fast){Copy-Item $fast (Join-Path $backup 'g2_autostart_fast.py') -Force}
Copy-Item $source $fast -Force
$script=@'
# Quiet fast BCP G2 autostart, no WMI/Get-NetTCPConnection
$ErrorActionPreference="Stop"
$root=Join-Path $env:LOCALAPPDATA 'BCP-Universal-Remote'
$python=(Get-Command python.exe -ErrorAction Stop).Source
$fast=Join-Path $root 'g2_autostart_fast.py'
if(-not(Test-Path $fast)){exit 2}
& $python -u $fast
exit $LASTEXITCODE
'@
$temp=$ps1+'.new'
$script|Set-Content -LiteralPath $temp -Encoding UTF8
Move-Item -LiteralPath $temp -Destination $ps1 -Force
Write-Output ('BCP_FAST_AUTOSTART_INSTALLED; backup='+$backup)
