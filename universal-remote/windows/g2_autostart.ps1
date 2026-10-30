# BCP Universal Remote G2 - quiet auto-start, limited pilot
$ErrorActionPreference="Stop"
$root=Join-Path $env:LOCALAPPDATA 'BCP-Universal-Remote'
$state=Join-Path $root 'state'
New-Item -ItemType Directory -Force -Path $state|Out-Null
$log=Join-Path $state 'g2-launch.json'
function report($status,$detail){
  [ordered]@{utc=(Get-Date).ToUniversalTime().ToString('o');status=$status;detail=$detail}|
  ConvertTo-Json -Compress|Set-Content -LiteralPath $log -Encoding utf8
}
try {
  $existing=@(Get-NetTCPConnection -State Listen -LocalPort 8898 -ErrorAction SilentlyContinue)
  if($existing.Count -gt 0){
    $mine=$true
    foreach($l in $existing){
      $p=Get-CimInstance Win32_Process -Filter ("ProcessId="+$l.OwningProcess) -ErrorAction SilentlyContinue
      if(-not $p -or $p.CommandLine -notmatch 'g2_tls_bridge\.py'){$mine=$false}
    }
    if($mine){report "ALREADY_RUNNING" "Listening on 8898";exit 0}
    report "PORT_CONFLICT" "Non-BCP process owns TCP 8898";exit 4
  }
  $p=Join-Path $root 'g2_tls_bridge.py'
  if(-not (Test-Path $p)){report "MISSING_SOURCE" $p;exit 2}
  $cmd=Get-Command python -ErrorAction Stop
  $exe=Join-Path (Split-Path $cmd.Source -Parent) 'pythonw.exe'
  if(-not (Test-Path $exe)){report "MISSING_PYTHONW" $exe;exit 3}
  $bindings=@('127.0.0.1')
  $wifi=Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4 -ErrorAction SilentlyContinue|
    Where-Object {$_.IPAddress -match '^192\.168\.|^10\.|^172\.'}|Select-Object -First 1
  if($wifi){$bindings+=([string]$wifi.IPAddress)}
  $tail='C:\Program Files\Tailscale\tailscale.exe'
  if(Test-Path $tail){
    $tailscaleIP=& $tail ip -4 2>$null|Select-Object -First 1
    if($tailscaleIP -match '^100\.'){$bindings+=[string]$tailscaleIP}
  }
  $arguments='"'+$p+'" '+(($bindings|Select-Object -Unique|ForEach-Object {'--bind '+$_}) -join ' ')
  $proc=Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -PassThru
  report "STARTED" ('pid='+$proc.Id+';bindings='+($bindings -join ','))
}catch{
  report "FAILED" $_.Exception.GetType().Name
  exit 1
}
