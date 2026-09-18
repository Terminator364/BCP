param()

$ErrorActionPreference = "Continue"
$AgentVersion = "0.2.0"
$Root = Join-Path $env:LOCALAPPDATA "BCP"
$Bin = Join-Path $Root "bin"
$State = Join-Path $Root "state"
$Telemetry = Join-Path $Root "telemetry"
$Server = Join-Path $Bin "bcp_server.ps1"
$Heartbeat = Join-Path $Telemetry "heartbeat.json"
$Events = Join-Path $Telemetry "events.jsonl"
$LastError = Join-Path $Telemetry "last_error.json"
$ManifestUrl = "https://raw.githubusercontent.com/Terminator364/BCP/main/release/stable.json"
$RuleName = "BCP Local LAN 8765"
$Port = 8765

New-Item -ItemType Directory -Force -Path $Bin,$State,$Telemetry | Out-Null

function Event([string]$type,[hashtable]$data=@{}) {
    $o=[ordered]@{ts=(Get-Date).ToUniversalTime().ToString("o");type=$type;agent_version=$AgentVersion}
    foreach($k in $data.Keys){$o[$k]=$data[$k]}
    Add-Content $Events ($o|ConvertTo-Json -Compress -Depth 8) -Encoding UTF8
}
function Err([string]$stage,[string]$msg) {
    $o=[ordered]@{ts=(Get-Date).ToUniversalTime().ToString("o");stage=$stage;message=$msg}
    $o|ConvertTo-Json -Depth 6|Set-Content $LastError -Encoding UTF8
    Event "ERROR" @{stage=$stage;message=$msg}
}
function ActiveConfig {
    Get-NetIPConfiguration | Where-Object {$_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up"} | Select-Object -First 1
}
function Ensure-Network {
    try {
        $cfg=ActiveConfig
        if(-not $cfg){throw "No active IPv4 interface"}
        $profile=Get-NetConnectionProfile -InterfaceIndex $cfg.InterfaceIndex -ErrorAction Stop
        if($profile.NetworkCategory -ne "Private"){
            Set-NetConnectionProfile -InterfaceIndex $cfg.InterfaceIndex -NetworkCategory Private -ErrorAction Stop
            Event "NETWORK_PROFILE_REPAIRED" @{interface=$cfg.InterfaceAlias}
        }
        if(-not (Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue)){
            New-NetFirewallRule -DisplayName $RuleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Private -RemoteAddress LocalSubnet | Out-Null
            Event "FIREWALL_RULE_CREATED" @{port=$Port}
        }
        return $cfg
    } catch { Err "network_preflight" $_.Exception.Message; return $null }
}
function Ensure-Server {
    try {
        $l=Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
        if(-not $l){
            if(-not (Test-Path $Server)){throw "Server payload missing"}
            Start-Process powershell -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-WindowStyle","Hidden","-File",$Server,"-Port",$Port) -WindowStyle Hidden
            Start-Sleep -Seconds 2
            Event "SERVER_START" @{port=$Port}
        }
    } catch { Err "server_start" $_.Exception.Message }
}
function Health([string]$url) {
    try { $r=Invoke-RestMethod -UseBasicParsing $url -TimeoutSec 3; return [bool]$r.ok } catch { return $false }
}
function HashFile([string]$p) { (Get-FileHash -Algorithm SHA256 $p).Hash.ToLowerInvariant() }

function Update-IfNeeded {
    try {
        $m=Invoke-RestMethod -UseBasicParsing $ManifestUrl -TimeoutSec 8
        if(-not $m.server_url){return}
        $tmp=Join-Path $Bin "bcp_server.ps1.new"
        Invoke-WebRequest -UseBasicParsing $m.server_url -OutFile $tmp -TimeoutSec 15
        $got=HashFile $tmp
        $want=([string]$m.server_sha256).ToLowerInvariant()
        if($got -ne $want){
            Remove-Item $tmp -Force -ErrorAction SilentlyContinue
            throw "server SHA256 mismatch"
        }
        $current=if(Test-Path $Server){HashFile $Server}else{""}
        if($current -ne $got){
            Copy-Item $Server "$Server.bak" -Force -ErrorAction SilentlyContinue
            Move-Item $tmp $Server -Force
            Event "UPDATE_STAGED" @{component="server";sha256=$got}
            Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | ForEach-Object {
                try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
            }
            Start-Sleep -Milliseconds 500
            Ensure-Server
            if(Health "http://127.0.0.1:$Port/health"){
                Event "UPDATE_COMMITTED" @{component="server";sha256=$got}
            } else {
                if(Test-Path "$Server.bak"){Copy-Item "$Server.bak" $Server -Force}
                Event "UPDATE_ROLLBACK" @{component="server"}
                Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | ForEach-Object {Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue}
                Start-Sleep -Milliseconds 500
                Ensure-Server
            }
        } else {
            Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        }
    } catch { Err "update_check" $_.Exception.Message }
}

Event "AGENT_START"
$nextUpdate=Get-Date
while($true){
    $cfg=Ensure-Network
    if((Get-Date) -ge $nextUpdate){Update-IfNeeded;$nextUpdate=(Get-Date).AddMinutes(15)}
    Ensure-Server

    $local=Health "http://127.0.0.1:$Port/health"
    $ip=$null;$lan=$false;$profile=$null
    try{
        if($cfg){
            $ip=($cfg.IPv4Address|Select-Object -First 1).IPAddress
            $profile=(Get-NetConnectionProfile -InterfaceIndex $cfg.InterfaceIndex).NetworkCategory.ToString()
            if($ip){$lan=Health ("http://"+$ip+":"+$Port+"/health")}
        }
    }catch{}

    $mem="UNKNOWN"
    try{
        $os=Get-CimInstance Win32_OperatingSystem
        $used=1-([double]$os.FreePhysicalMemory/[double]$os.TotalVisibleMemorySize)
        if($used -ge .95){$mem="CRITICAL"}elseif($used -ge .85){$mem="HIGH"}else{$mem="NORMAL"}
    }catch{}

    [ordered]@{
        ts=(Get-Date).ToUniversalTime().ToString("o")
        agent_version=$AgentVersion
        process_up=$true
        local_health=$local
        lan_health=$lan
        pc_ip=$ip
        network_profile=$profile
        firewall_rule_state=[bool](Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue)
        memory_pressure_class=$mem
    }|ConvertTo-Json -Depth 8|Set-Content $Heartbeat -Encoding UTF8

    Start-Sleep -Seconds 30
}
