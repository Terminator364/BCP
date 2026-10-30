# BCP G2: consolidate duplicate listeners and fix blocking TLS accept.
# Only BCP g2_tls_bridge.py pythonw.exe processes are eligible for stopping.
# Never stops Desktop Commander, BCP GUI, Tailscale or other Python scripts.
param([switch]$Apply)
$ErrorActionPreference="Stop"
$root=Join-Path $env:LOCALAPPDATA 'BCP-Universal-Remote'
$src=Join-Path $root 'build-repo\universal-remote\windows'
$tests=Join-Path $root 'build-repo\universal-remote\tests'
$python=(Get-Command python.exe -ErrorAction Stop).Source
$files=@('g2_tls_bridge.py','g4_device_identity.py')
foreach($name in $files){
  if(-not(Test-Path -LiteralPath (Join-Path $src $name))){throw ('MISSING_'+$name)}
  & $python -m py_compile (Join-Path $src $name)
  if($LASTEXITCODE -ne 0){throw ('BAD_SOURCE_'+$name)}
}
& $python -u (Join-Path $tests 'g2_tls_stalled_client_test.py')
if($LASTEXITCODE -ne 0){throw 'TLS_NONBLOCKING_LAB_FAILED'}
$exact=Join-Path $root 'g2_tls_bridge.py'
$targets=@(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction Stop |
  Where-Object { $_.CommandLine -and
    $_.CommandLine.Contains($exact) -and
    $_.CommandLine -match 'g2_tls_bridge[.]py' })
$ids=@($targets | Select-Object -ExpandProperty ProcessId -Unique)
Write-Output ('BCP_VERIFIED_G2_SERVER_PROCESSES='+$ids.Count)
if($ids.Count -gt 24){throw 'TOO_MANY_PROCESSES_FAIL_CLOSED'}
if(-not $Apply){Write-Output 'BCP_EXCLUSIVE_G2_DRY_RUN_PASS';exit 0}
$backup=Join-Path $root ('backups\G2_EXCLUSIVE_FIX_'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Force -Path $backup|Out-Null
$manifest=@()
foreach($name in $files){
  $dst=Join-Path $root $name
  $exists=Test-Path -LiteralPath $dst
  if($exists){Copy-Item -LiteralPath $dst -Destination (Join-Path $backup $name) -Force}
  $manifest+=@{name=$name;was_present=$exists}
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $backup 'manifest.json') -Encoding utf8
function StopOnlyBCP {
  $live=@(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction Stop|
    Where-Object { $_.CommandLine -and $_.CommandLine.Contains($exact) -and
                   $_.CommandLine -match 'g2_tls_bridge[.]py' })
  foreach($p in $live){
    Write-Output ('BCP_STOP_DUPLICATE_PID='+$p.ProcessId)
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
  }
}
function StartWithFast {
  $fast=Join-Path $root 'g2_autostart_fast.py'
  if(-not(Test-Path -LiteralPath $fast)){throw 'FAST_STARTER_MISSING'}
  & $python -u $fast
  if($LASTEXITCODE -ne 0){throw 'FAST_G2_LAUNCH_FAILED'}
  Start-Sleep -Seconds 2
}
$modified=$false
try{
  foreach($name in $files){Copy-Item -LiteralPath (Join-Path $src $name) -Destination (Join-Path $root $name) -Force}
  $modified=$true
  StopOnlyBCP
  # Let Windows release exclusive addresses before starting one server.
  Start-Sleep -Seconds 2
  StartWithFast
  & $python -u (Join-Path $root 'g4_owner_production_gate.py')
  if($LASTEXITCODE -ne 0){throw 'G4_AUTHENTICATED_GATE_FAILED'}
  & $python -u (Join-Path $root 'g2_serve_test.py')
  if($LASTEXITCODE -ne 0){throw 'G2_SIGNED_TAILSCALE_FAILED'}
  & $python -u (Join-Path $root 'g2_pairing_proxy_probe.py')
  if($LASTEXITCODE -ne 0){throw 'G2_PAIRING_GATE_FAILED'}
  Write-Output 'BCP_SINGLE_G2_SERVER_RESTORED_AND_AUTHENTICATED_PASS'
  Write-Output ('BCP_BACKUP='+$backup)
}catch{
  Write-Output ('BCP_EXCLUSIVE_DEPLOY_FAILED='+$_.Exception.Message)
  if($modified){
    try{
      StopOnlyBCP
      foreach($entry in $manifest){
        $dst=Join-Path $root $entry.name
        if($entry.was_present){Copy-Item -LiteralPath (Join-Path $backup $entry.name) -Destination $dst -Force}
        elseif(Test-Path $dst){Remove-Item -LiteralPath $dst -Force}
      }
      Start-Sleep -Seconds 2
      StartWithFast
      Write-Output 'BCP_PREVIOUS_SOURCE_RESTORED_AND_STARTED'
    }catch{Write-Output ('BCP_ROLLBACK_RECOVERY_ERROR='+$_.Exception.Message)}
  }
  throw
}
