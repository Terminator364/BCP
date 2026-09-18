param([int]$Port = 8765)

$ErrorActionPreference = "Stop"
$Root = Join-Path $env:LOCALAPPDATA "BCP"
$StateDir = Join-Path $Root "state"
$TelemetryDir = Join-Path $Root "telemetry"
$StateFile = Join-Path $StateDir "project_state.json"
$TokenFile = Join-Path $StateDir "bcp_token.txt"
$PairedFile = Join-Path $StateDir "paired_edge.json"
$EventFile = Join-Path $StateDir "events.jsonl"
$PhoneTelemetry = Join-Path $TelemetryDir "phone-events.jsonl"

New-Item -ItemType Directory -Force -Path $StateDir,$TelemetryDir | Out-Null

function New-Token {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
}

if (-not (Test-Path $TokenFile)) {
    $token = New-Token
    [IO.File]::WriteAllText($TokenFile,$token,[Text.UTF8Encoding]::new($false))
} else {
    $token = (Get-Content $TokenFile -Raw).Trim()
}
if (-not (Test-Path $StateFile)) {
    [IO.File]::WriteAllText($StateFile,'{"projects":{}}',[Text.UTF8Encoding]::new($false))
}

function Load-State {
    $raw = Get-Content $StateFile -Raw
    $obj = $raw | ConvertFrom-Json
    $projects = @{}
    if ($obj.projects) {
        foreach ($p in $obj.projects.PSObject.Properties) { $projects[$p.Name] = $p.Value }
    }
    return @{projects=$projects}
}
function Save-State($state) {
    $tmp = "$StateFile.tmp"
    $json = $state | ConvertTo-Json -Depth 16
    [IO.File]::WriteAllText($tmp,$json,[Text.UTF8Encoding]::new($false))
    Move-Item -Force $tmp $StateFile
}
function Sha256([string]$s) {
    $sha=[Security.Cryptography.SHA256]::Create()
    try {
        $b=[Text.Encoding]::UTF8.GetBytes($s)
        return ([BitConverter]::ToString($sha.ComputeHash($b))).Replace('-','').ToLowerInvariant()
    } finally { $sha.Dispose() }
}
function Send-Json($stream,[int]$status,$obj) {
    $json=$obj|ConvertTo-Json -Depth 20
    $body=[Text.Encoding]::UTF8.GetBytes($json)
    $reason = if($status -eq 200){"OK"}elseif($status -eq 400){"Bad Request"}elseif($status -eq 401){"Unauthorized"}elseif($status -eq 404){"Not Found"}else{"Error"}
    $crlf=[Environment]::NewLine
    $head="HTTP/1.1 $status $reason$crlf" +
          "Content-Type: application/json; charset=utf-8$crlf" +
          "Content-Length: $($body.Length)$crlf" +
          "Cache-Control: no-store$crlf" +
          "Connection: close$crlf$crlf"
    $hb=[Text.Encoding]::ASCII.GetBytes($head)
    $stream.Write($hb,0,$hb.Length)
    $stream.Write($body,0,$body.Length)
}
function Read-Request($stream) {
    $reader = New-Object IO.StreamReader($stream,[Text.Encoding]::UTF8,$false,4096,$true)
    $line=$reader.ReadLine()
    if(-not $line){return $null}
    $parts=$line.Split(' ')
    if($parts.Count -lt 2){throw "Malformed request"}
    $headers=@{}
    while($true){
        $h=$reader.ReadLine()
        if($null -eq $h -or $h -eq ""){break}
        $i=$h.IndexOf(':')
        if($i -gt 0){$headers[$h.Substring(0,$i).Trim().ToLowerInvariant()]=$h.Substring($i+1).Trim()}
    }
    $len=0
    if($headers.ContainsKey("content-length")){[int]::TryParse($headers["content-length"],[ref]$len)|Out-Null}
    $body=""
    if($len -gt 0){
        $chars=New-Object char[] $len
        $read=0
        while($read -lt $len){
            $n=$reader.Read($chars,$read,$len-$read)
            if($n -le 0){break}
            $read += $n
        }
        if($read -gt 0){$body=-join $chars[0..($read-1)]}
    }
    return @{method=$parts[0];path=$parts[1];headers=$headers;body=$body}
}
function Authorized($headers) {
    if(-not $headers.ContainsKey("authorization")){return $false}
    return $headers["authorization"] -eq "Bearer $token"
}

$listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Any,$Port)
$listener.Start()
Write-Host "[BCP] Windows native server v0.2.1 listening on TCP $Port"
Write-Host "[BCP] Pairing open: $(-not (Test-Path $PairedFile))"

while($true){
    $client=$listener.AcceptTcpClient()
    $stream=$null
    try{
        $remote=$client.Client.RemoteEndPoint.Address.ToString()
        $stream=$client.GetStream()
        $req=Read-Request $stream
        if($null -eq $req){continue}
        $path=($req.path -split '\?')[0]

        if($req.method -eq "GET" -and $path -eq "/health"){
            Send-Json $stream 200 @{
                ok=$true
                service="BCP PC Node Windows Native"
                version="0.2.1"
                pairing_open=(-not (Test-Path $PairedFile))
                pc_name=$env:COMPUTERNAME
                time=(Get-Date).ToUniversalTime().ToString("o")
            }
            continue
        }

        if($req.method -eq "POST" -and $path -eq "/pair"){
            if(Test-Path $PairedFile){
                if(Authorized $req.headers){
                    Send-Json $stream 200 @{paired=$true;token=$token;pc_name=$env:COMPUTERNAME}
                } else {
                    Send-Json $stream 401 @{error="already_paired"}
                }
                continue
            }
            $body=@{}
            if($req.body){$body=$req.body|ConvertFrom-Json}
            $pair=[ordered]@{
                paired_at=(Get-Date).ToUniversalTime().ToString("o")
                remote_ip=$remote
                device_name=[string]$body.device_name
                edge_version=[string]$body.edge_version
            }
            $pair|ConvertTo-Json -Depth 8|Set-Content $PairedFile -Encoding UTF8
            Send-Json $stream 200 @{paired=$true;token=$token;pc_name=$env:COMPUTERNAME}
            continue
        }

        if(-not (Authorized $req.headers)){
            Send-Json $stream 401 @{error="unauthorized"}
            continue
        }

        if($req.method -eq "GET" -and $path -eq "/v1/diagnostics"){
            $heartbeatPath=Join-Path $TelemetryDir "heartbeat.json"
            $heartbeat=$null
            if(Test-Path $heartbeatPath){
                try{$heartbeat=Get-Content $heartbeatPath -Raw|ConvertFrom-Json}catch{}
            }
            $phone=@()
            if(Test-Path $PhoneTelemetry){
                try{$phone=@(Get-Content $PhoneTelemetry -Tail 30 | ForEach-Object {try{$_|ConvertFrom-Json}catch{}})}catch{}
            }
            Send-Json $stream 200 @{
                ok=$true
                server_version="0.2.1"
                pc_name=$env:COMPUTERNAME
                paired=(Test-Path $PairedFile)
                heartbeat=$heartbeat
                recent_phone_events=$phone
            }
            continue
        }

        if($req.method -eq "POST" -and $path -eq "/v1/telemetry"){
            if($req.body){
                $obj=$req.body|ConvertFrom-Json
                if($obj.events){
                    foreach($e in $obj.events){
                        $rec=[ordered]@{received_at=(Get-Date).ToUniversalTime().ToString("o");remote_ip=$remote;event=$e}
                        Add-Content $PhoneTelemetry ($rec|ConvertTo-Json -Compress -Depth 12) -Encoding UTF8
                    }
                }
            }
            Send-Json $stream 200 @{ok=$true}
            continue
        }

        $seg=@($path.Trim('/').Split('/'))
        if($seg.Count -eq 4 -and $seg[0] -eq "v1" -and $seg[1] -eq "projects"){
            $project=[Uri]::UnescapeDataString($seg[2])
            $action=$seg[3]
            $state=Load-State
            $head=$null
            if($state.projects.ContainsKey($project)){$head=$state.projects[$project]}

            if($req.method -eq "GET" -and ($action -eq "head" -or $action -eq "resume")){
                Send-Json $stream 200 @{project_id=$project;head=$head}
                continue
            }

            if($req.method -eq "POST" -and $action -eq "events"){
                $body=$req.body|ConvertFrom-Json
                $idem=""
                if($req.headers.ContainsKey("idempotency-key")){$idem=$req.headers["idempotency-key"]}
                if([string]::IsNullOrWhiteSpace($idem)){throw "Idempotency-Key required"}

                if($head -and $head.last_idempotency_key -eq $idem){
                    Send-Json $stream 200 @{result="ALREADY_COMMITTED";project_id=$project;revision=$head.revision;event_hash=$head.last_event_hash}
                    continue
                }

                $revision=if($head){[int]$head.revision+1}else{1}
                $prev=if($head){[string]$head.last_event_hash}else{"GENESIS"}
                $created=(Get-Date).ToUniversalTime().ToString("o")
                $payload=$body.payload
                $payloadJson=$payload|ConvertTo-Json -Compress -Depth 10
                $hash=Sha256 "$project|$revision|$payloadJson|$idem|$created|$prev"

                $newHead=[ordered]@{
                    project_id=$project
                    revision=$revision
                    last_event_hash=$hash
                    last_idempotency_key=$idem
                    status=$(if($payload.status){[string]$payload.status}else{"ACTIVE"})
                    last_completed_action=$(if($payload.last_completed_action){[string]$payload.last_completed_action}else{""})
                    next_action=$(if($payload.next_action){[string]$payload.next_action}else{""})
                    updated_at=$created
                }
                $event=[ordered]@{project_id=$project;revision=$revision;payload=$payload;idempotency_key=$idem;created_at=$created;prev_hash=$prev;event_hash=$hash}
                Add-Content $EventFile ($event|ConvertTo-Json -Compress -Depth 12) -Encoding UTF8
                $state.projects[$project]=$newHead
                Save-State $state
                Send-Json $stream 200 @{result="COMMITTED";project_id=$project;revision=$revision;event_hash=$hash;created_at=$created}
                continue
            }
        }

        Send-Json $stream 404 @{error="not_found"}
    } catch {
        if($stream){try{Send-Json $stream 400 @{error="server_error";detail=$_.Exception.Message}}catch{}}
    } finally {
        if($stream){$stream.Dispose()}
        $client.Close()
    }
}
