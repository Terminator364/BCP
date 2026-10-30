# BCP G4.1 individual identity deployment; safe by default (dry run).
# Does not enroll/approve any owner. Keeps the live signed Android v1.3 stable.
param([switch]$Apply)
$ErrorActionPreference="Stop"
$root=Join-Path $env:LOCALAPPDATA 'BCP-Universal-Remote'
$repo=Join-Path $root 'build-repo\universal-remote'
$source=Join-Path $repo 'windows'
$tests=Join-Path $repo 'tests'
$autostart=Join-Path $root 'g2_autostart.ps1'
$files=@('g2_tls_bridge.py','g4_owner_gateway.py','g4_owner_center.py','g4_device_identity.py',
        'g4_full_files.py','g4_owner_transactions.py','g4_owner_file_rpc.py')
$checked=@()
foreach($name in $files){
  $item=Join-Path $source $name
  if(-not(Test-Path -LiteralPath $item)){throw ('SOURCE_MISSING_'+$name)}
  $checked+=$item
}
$env:PYTHONPATH=$source
python -m py_compile @checked
if($LASTEXITCODE -ne 0){throw 'G4_INDIVIDUAL_COMPILE_FAILED'}
python -u (Join-Path $tests 'g4_device_identity_test.py')
if($LASTEXITCODE -ne 0){throw 'IDENTITY_LAB_FAILED'}
python -u (Join-Path $tests 'g4_owner_gateway_unit_test.py')
if($LASTEXITCODE -ne 0){throw 'OWNER_POLICY_LAB_FAILED'}
python -u (Join-Path $tests 'g4_owner_transactions_test.py')
if($LASTEXITCODE -ne 0){throw 'OWNER_TRANSACTIONS_LAB_FAILED'}
python -u (Join-Path $tests 'g4_owner_file_rpc_test.py')
if($LASTEXITCODE -ne 0){throw 'OWNER_FILE_RPC_LAB_FAILED'}
python -u (Join-Path $tests 'g4_owner_files_tls_e2e_test.py')
if($LASTEXITCODE -ne 0){throw 'OWNER_FILES_TLS_E2E_FAILED'}
if(-not $Apply){
  Write-Output 'BCP_G4_INDIVIDUAL_DRY_RUN_PASS'
  Write-Output 'No BCP production files or owner profiles have been changed'
  exit 0
}
$backup=Join-Path $root ('backups\G4_1_INDIVIDUAL_'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $backup -Force|Out-Null
$manifest=@()
foreach($name in $files){
  $current=Join-Path $root $name
  $present=Test-Path -LiteralPath $current
  if($present){
    Copy-Item -LiteralPath $current -Destination (Join-Path $backup $name) -Force
  }
  $manifest+=@{file=$name;present_before=$present}
}
$manifest|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $backup 'manifest.json') -Encoding utf8

function Stop-BCP {
  $owners=@(Get-NetTCPConnection -State Listen -LocalPort 8898 -ErrorAction SilentlyContinue|
     Select-Object -ExpandProperty OwningProcess -Unique)
  if($owners.Count -ne 1){throw ('BCP_LISTENER_COUNT_'+$owners.Count)}
  $cmd=Get-CimInstance Win32_Process -Filter ("ProcessId="+$owners[0])
  if(-not $cmd -or $cmd.CommandLine -notmatch 'BCP-Universal-Remote\\g2_tls_bridge[.]py'){
    throw 'LISTENER_NOT_BCP'
  }
  Stop-Process -Id $owners[0] -Force
}
function Start-BCP {
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $autostart
  if($LASTEXITCODE -ne 0){throw 'BCP_AUTOSTART_FAILED'}
  for($i=0;$i -lt 30;$i++){
    Start-Sleep -Milliseconds 700
    $live=@(Get-NetTCPConnection -State Listen -LocalPort 8898 -ErrorAction SilentlyContinue)
    if(@($live|Where-Object LocalAddress -eq '127.0.0.1').Count -ge 1 -and $live.Count -ge 2){return}
  }
  throw 'BCP_LISTENER_NOT_READY'
}
$modified=$false
try {
  Stop-BCP
  $modified=$true
  foreach($name in $files){
    Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $root $name) -Force
  }
  $warm=Join-Path $root 'state\g4-startup-state.json'
  if(Test-Path $warm){Remove-Item -LiteralPath $warm -Force}
  Start-BCP
  $ready=$false
  for($i=0;$i -lt 90;$i++){
    Start-Sleep -Seconds 1
    if(Test-Path $warm){
      $data=Get-Content -LiteralPath $warm -Raw | ConvertFrom-Json
      if($data.status -eq 'FAILED'){
        Write-Output ('G4_WARMUP_ATTEMPTS_FAILED='+$data.error_type)
        break
      }
      if($data.status -eq 'READY'){$ready=$true;break}
    }
  }
  if(-not $ready){
    Write-Output 'G4_WARMUP_NOT_READY_VERIFYING_REAL_AUTHENTICATED_API'
  }
  # The server may recover lazily after a transient warmup lock. The real
  # authenticated negative-security and G2 regression checks are decisive.
  python -u (Join-Path $root 'g4_owner_production_gate.py')
  if($LASTEXITCODE -ne 0){throw 'G4_OWNER_NEGATIVE_GATE_FAILED'}
  python -u (Join-Path $root 'g2_serve_test.py')
  if($LASTEXITCODE -ne 0){throw 'G2_TAILSCALE_REGRESSION'}
  python -u (Join-Path $root 'g2_pairing_proxy_probe.py')
  if($LASTEXITCODE -ne 0){throw 'G2_PAIRING_REGRESSION'}
  python -u (Join-Path $tests 'g4_owner_files_loopback_negative_test.py') --port 8898
  if($LASTEXITCODE -ne 0){throw 'G4_OWNER_FILE_REMOTE_NEGATIVE_GATE_FAILED'}
  Write-Output 'BCP_G4_INDIVIDUAL_PRODUCTION_NEGATIVE_GATE_PASS'
  Write-Output 'No device enrolled, no owner trust granted, no Windows user files changed'
  Write-Output ('BCP_G4_PREDEPLOY_BACKUP='+$backup)
}catch{
  $reason=$_.Exception.Message
  Write-Output ('BCP_G4_DEPLOY_ERROR='+$reason)
  if($modified){
    try{Stop-BCP}catch{Write-Output ('BCP_STOP_RETRY='+$_.Exception.Message)}
    foreach($entry in $manifest){
      $target=Join-Path $root $entry.file
      if($entry.present_before){
        Copy-Item -LiteralPath (Join-Path $backup $entry.file) -Destination $target -Force
      }elseif(Test-Path $target){
        Remove-Item -LiteralPath $target -Force
      }
    }
    $warm=Join-Path $root 'state\\g4-startup-state.json'
    if(Test-Path $warm){Remove-Item -LiteralPath $warm -Force}
    try{
      Start-BCP
      python -u (Join-Path $root 'g4_owner_production_gate.py')
      if($LASTEXITCODE -ne 0){throw 'RESTORED_G4_GATE_FAILED'}
      Write-Output 'BCP_PREVIOUS_PRODUCTION_RESTORED_AND_VALIDATED'
    }catch{Write-Output ('BCP_RESTORE_FAILED='+$_.Exception.Message)}
  }
  throw
}
