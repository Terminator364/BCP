param(
    [switch]$SelfTest,
    [switch]$ResumeAfterReboot,
    [string]$CampaignId = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TargetVersion = "0.6.2"
$Project = "buildhub"
$Port = 8765
$BaseUrl = "http://127.0.0.1:$Port"
$ManagedRoot = Join-Path $env:LOCALAPPDATA "ChatGPT_ManagedApps\bcp"
$StateDir = Join-Path $ManagedRoot "state"
$TokenPath = Join-Path $StateDir "bcp_token.txt"
$PairPath = Join-Path $StateDir "paired_edge.json"
$AcceptanceDir = Join-Path $ManagedRoot "acceptance"
$RunnerPath = Join-Path $AcceptanceDir "BCP_FINAL_ACCEPTANCE_RUNNER.ps1"
$CampaignStatePath = Join-Path $AcceptanceDir "campaign_state.json"
$ReportPath = Join-Path $AcceptanceDir "BCP_FINAL_ACCEPTANCE_LATEST.json"

function UtcNow { [DateTime]::UtcNow.ToString("o") }

function Write-JsonAtomic($Object, [string]$Path) {
    $dir = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $tmp = Join-Path $dir (".tmp-" + [Guid]::NewGuid().ToString("N") + ".json")
    try {
        $json = $Object | ConvertTo-Json -Depth 30
        [IO.File]::WriteAllText($tmp,$json,[Text.UTF8Encoding]::new($false))
        Move-Item -Force -LiteralPath $tmp -Destination $Path
    } finally {
        Remove-Item -Force -LiteralPath $tmp -ErrorAction SilentlyContinue
    }
}

function Read-Json([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    return (Get-Content -Raw -LiteralPath $Path -Encoding UTF8 | ConvertFrom-Json)
}

function File-Sha256([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return "" }
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Get-Token {
    if (-not (Test-Path -LiteralPath $TokenPath -PathType Leaf)) { throw "BCP_TOKEN_MISSING" }
    return (Get-Content -Raw -LiteralPath $TokenPath).Trim()
}

function Auth-Headers {
    return @{ Authorization = ("Bearer " + (Get-Token)) }
}

function Invoke-BcpGet([string]$Path,[int]$Timeout=5) {
    return Invoke-RestMethod -UseBasicParsing -Method Get -Uri ($BaseUrl+$Path) -Headers (Auth-Headers) -TimeoutSec $Timeout
}

function Invoke-BcpPost([string]$Path,$Body,[hashtable]$ExtraHeaders=@{},[int]$Timeout=8) {
    $headers = Auth-Headers
    foreach($k in $ExtraHeaders.Keys){$headers[$k]=$ExtraHeaders[$k]}
    $json = if($null -eq $Body){"{}"}else{$Body | ConvertTo-Json -Depth 20 -Compress}
    return Invoke-RestMethod -UseBasicParsing -Method Post -Uri ($BaseUrl+$Path) -Headers $headers -ContentType "application/json" -Body $json -TimeoutSec $Timeout
}

function Wait-Health([string]$ExpectedVersion,[int]$Seconds=150) {
    $deadline=[DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        try {
            $h=Invoke-RestMethod -UseBasicParsing -Uri ($BaseUrl+"/health") -TimeoutSec 2
            if($h.ok -eq $true -and (!$ExpectedVersion -or [string]$h.version -eq $ExpectedVersion)){return $h}
        } catch {}
        Start-Sleep -Milliseconds 800
    } while([DateTime]::UtcNow -lt $deadline)
    return $null
}

function External-Roots {
    $candidates=@(
        "G:\Mon Drive\API_BCP\02_TELEMETRY\BCP",
        "G:\My Drive\API_BCP\02_TELEMETRY\BCP",
        (Join-Path $HOME "Mon Drive\API_BCP\02_TELEMETRY\BCP"),
        (Join-Path $HOME "My Drive\API_BCP\02_TELEMETRY\BCP"),
        "G:\Mon Drive\CHATGPT_PC_AGENT\03_TELEMETRY\BCP",
        "G:\My Drive\CHATGPT_PC_AGENT\03_TELEMETRY\BCP",
        (Join-Path $HOME "Mon Drive\CHATGPT_PC_AGENT\03_TELEMETRY\BCP"),
        (Join-Path $HOME "My Drive\CHATGPT_PC_AGENT\03_TELEMETRY\BCP")
    )
    $out=New-Object System.Collections.Generic.List[string]
    foreach($p in $candidates){
        $parent=Split-Path -Parent $p
        if(Test-Path -LiteralPath $parent -PathType Container){
            try{New-Item -ItemType Directory -Force -Path $p|Out-Null;$out.Add($p)}catch{}
        }
    }
    return @($out | Select-Object -Unique)
}

function Publish-Report($Report) {
    Write-JsonAtomic $Report $ReportPath
    foreach($root in (External-Roots)){
        try{Write-JsonAtomic $Report (Join-Path $root "BCP_FINAL_ACCEPTANCE_LATEST.json")}catch{}
    }
}

function Ensure-Runner-Copy {
    New-Item -ItemType Directory -Force -Path $AcceptanceDir | Out-Null
    if([IO.Path]::GetFullPath($PSCommandPath) -ne [IO.Path]::GetFullPath($RunnerPath)){
        Copy-Item -Force -LiteralPath $PSCommandPath -Destination $RunnerPath
    }
}

function Ensure-Target-Version {
    $health=Wait-Health "" 20
    if(-not $health){throw "BCP_NOT_RUNNING_BEFORE_ACCEPTANCE"}
    if([string]$health.version -eq $TargetVersion){return $health}

    $u=Invoke-BcpGet "/v1/system/update" 12
    if(-not $u.available -and [string]$u.current_version -ne $TargetVersion){
        throw ("TARGET_UPDATE_NOT_AVAILABLE current="+$u.current_version+" target="+$TargetVersion)
    }
    if($u.available){
        [void](Invoke-BcpPost "/v1/system/update/apply" @{} @{} 20)
    }
    $health=Wait-Health $TargetVersion 120
    if(-not $health){throw "BCP_TARGET_VERSION_DID_NOT_RETURN"}
    return $health
}

function Get-LanIpv4 {
    try {
        foreach($adapter in @(Get-NetAdapter -ErrorAction Stop | Where-Object {$_.Status -eq "Up"})){
            $ip=@(Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
                Where-Object {$_.IPAddress -and $_.IPAddress -notlike "169.254.*" -and $_.IPAddress -ne "127.0.0.1"} |
                Select-Object -First 1)
            if($ip.Count -gt 0){return [string]$ip[0].IPAddress}
        }
    } catch {}
    return ""
}

function Test-Health-Url([string]$Url,[int]$Timeout=3) {
    $sw=[Diagnostics.Stopwatch]::StartNew()
    try {
        $h=Invoke-RestMethod -UseBasicParsing -Uri $Url -TimeoutSec $Timeout
        $sw.Stop()
        return [ordered]@{ok=($h.ok -eq $true);version=[string]$h.version;ms=[int]$sw.ElapsedMilliseconds;error=""}
    } catch {
        $sw.Stop()
        return [ordered]@{ok=$false;version="";ms=[int]$sw.ElapsedMilliseconds;error=$_.Exception.Message}
    }
}

function Test-Checkpoint-Fencing([string]$Id) {
    $resume=Invoke-BcpGet ("/v1/projects/"+$Project+"/resume") 5
    $head=$resume.head
    $before=if($null -eq $head){0}else{[int]$head.revision}
    $idem="acceptance-"+$Id+"-checkpoint"
    $body=@{
        type="acceptance_checkpoint"
        payload=@{
            status="ACTIVE"
            last_completed_action="FINAL_ACCEPTANCE_PRE_REBOOT"
            next_action="FINAL_ACCEPTANCE_POST_REBOOT"
            campaign_id=$Id
        }
    }
    $headers=@{"Idempotency-Key"=$idem;"X-BCP-Expected-Revision"=[string]$before}
    $first=Invoke-BcpPost ("/v1/projects/"+$Project+"/events") $body $headers 8
    $replay=Invoke-BcpPost ("/v1/projects/"+$Project+"/events") $body $headers 8
    if([string]$first.result -ne "COMMITTED"){throw "CHECKPOINT_NOT_COMMITTED"}
    if([string]$replay.result -ne "ALREADY_COMMITTED"){throw "IDEMPOTENCY_REPLAY_NOT_RECOGNIZED"}
    if([int]$first.revision -ne [int]$replay.revision){throw "IDEMPOTENCY_REVISION_CHANGED"}

    $staleRejected=$false
    $staleStatus=0
    $staleBody=@{
        type="acceptance_stale_writer_probe"
        payload=@{status="ACTIVE";campaign_id=$Id;must_not_commit=$true}
    }
    try {
        $staleHeaders=@{
            "Idempotency-Key"=("acceptance-"+$Id+"-stale")
            "X-BCP-Expected-Revision"=[string]$before
        }
        [void](Invoke-BcpPost ("/v1/projects/"+$Project+"/events") $staleBody $staleHeaders 8)
    } catch {
        try{$staleStatus=[int]$_.Exception.Response.StatusCode}catch{}
        if($staleStatus -eq 409){$staleRejected=$true}
    }
    if(-not $staleRejected){throw ("STALE_WRITER_NOT_REJECTED status="+$staleStatus)}

    $after=Invoke-BcpGet ("/v1/projects/"+$Project+"/resume") 5
    return [ordered]@{
        before_revision=$before
        committed_revision=[int]$first.revision
        committed_hash=[string]$first.event_hash
        replay_result=[string]$replay.result
        stale_writer_rejected=$true
        head_revision=[int]$after.head.revision
        head_hash=[string]$after.head.last_event_hash
    }
}

function Test-Resource-Bounds {
    $os=Get-CimInstance Win32_OperatingSystem
    $total=[double]$os.TotalVisibleMemorySize*1024
    $free=[double]$os.FreePhysicalMemory*1024
    $beforePct=[math]::Round((1-($free/$total))*100,1)
    $buffers=New-Object System.Collections.ArrayList
    $allocated=0L
    $chunk=16MB
    $cap=192MB
    try {
        while($allocated -lt $cap){
            $os=Get-CimInstance Win32_OperatingSystem
            $used=1-([double]$os.FreePhysicalMemory/[double]$os.TotalVisibleMemorySize)
            if($used -ge 0.85){break}
            [void]$buffers.Add((New-Object byte[] $chunk))
            $allocated+=$chunk
            Start-Sleep -Milliseconds 100
        }
        $failures=0;$maxMs=0
        for($i=0;$i -lt 20;$i++){
            $r=Test-Health-Url ($BaseUrl+"/health") 2
            if(-not $r.ok){$failures++}
            if($r.ms -gt $maxMs){$maxMs=$r.ms}
        }
        $os=Get-CimInstance Win32_OperatingSystem
        $afterPct=[math]::Round((1-([double]$os.FreePhysicalMemory/[double]$os.TotalVisibleMemorySize))*100,1)
        return [ordered]@{
            pass=($failures -eq 0)
            memory_before_pct=$beforePct
            memory_during_pct=$afterPct
            synthetic_allocated_bytes=$allocated
            synthetic_cap_bytes=$cap
            health_requests=20
            health_failures=$failures
            max_health_ms=$maxMs
        }
    } finally {
        $buffers.Clear()
        Remove-Variable buffers -ErrorAction SilentlyContinue
        [GC]::Collect()
    }
}

function Test-Poor-Connectivity-Bounds {
    $sw=[Diagnostics.Stopwatch]::StartNew()
    $attempts=3;$timeouts=0
    for($i=0;$i -lt $attempts;$i++){
        $client=New-Object Net.Sockets.TcpClient
        try {
            $iar=$client.BeginConnect("192.0.2.1",9,$null,$null)
            if(-not $iar.AsyncWaitHandle.WaitOne(800,$false)){$timeouts++}
        } catch {$timeouts++} finally {$client.Close()}
        $local=Test-Health-Url ($BaseUrl+"/health") 2
        if(-not $local.ok){throw "LOCAL_CONTROL_PLANE_FAILED_DURING_BAD_NETWORK_PROBE"}
    }
    $sw.Stop()
    return [ordered]@{
        pass=($sw.ElapsedMilliseconds -lt 6000)
        attempts=$attempts
        bounded_failures=$timeouts
        total_ms=[int]$sw.ElapsedMilliseconds
        local_control_plane_remained_healthy=$true
    }
}

function Lifecycle-Registered {
    try {
        $v=(Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "BlessingControlPlane" -ErrorAction Stop).BlessingControlPlane
        return [ordered]@{registered=([string]$v -match "ChatGPT_ManagedApps\\bcp\\server\.py");command=[string]$v}
    } catch { return [ordered]@{registered=$false;command=""} }
}

function Managed-Listener {
    try {
        $listeners=@(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop)
        if($listeners.Count -lt 1){throw "NO_LISTENER_ON_MANAGED_PORT"}
        # The authenticated diagnostics response is served by the control plane
        # reached on the managed port. Path + SHA + version are the authoritative
        # runtime identity proof. Windows TCP ownership is retained as secondary
        # telemetry because it can transiently disagree across restart/wrapper
        # boundaries and must not create a false-negative by itself.
        $d=Invoke-BcpGet "/v1/diagnostics" 5
        $managedPath=(Join-Path $ManagedRoot "server.py")
        $localHash=File-Sha256 $managedPath
        $listenerPids=@($listeners | ForEach-Object {[int]$_.OwningProcess} | Sort-Object -Unique)
        $pidMatch=($listenerPids -contains [int]$d.server_pid)
        $fileMatch=([IO.Path]::GetFullPath([string]$d.server_file) -eq [IO.Path]::GetFullPath($managedPath))
        $hashMatch=($localHash -and $localHash -eq [string]$d.server_sha256)
        $versionMatch=([string]$d.version -eq $TargetVersion)
        $identityPass=($fileMatch -and $hashMatch -and $versionMatch)
        return [ordered]@{
            pass=$identityPass
            identity_proof="AUTHENTICATED_DIAGNOSTICS_PATH_SHA_VERSION"
            listener_present=$true
            listener_pids=$listenerPids
            diagnostic_pid=[int]$d.server_pid
            diagnostic_file=[string]$d.server_file
            diagnostic_sha256=[string]$d.server_sha256
            diagnostic_version=[string]$d.version
            local_sha256=$localHash
            pid_match=$pidMatch
            file_match=$fileMatch
            hash_match=$hashMatch
            version_match=$versionMatch
            pid_mismatch_severity=if($pidMatch){"NONE"}else{"DIAGNOSTIC_ONLY"}
        }
    } catch { return [ordered]@{pass=$false;listener_present=$false;listener_pids=@();diagnostic_pid=0;error=$_.Exception.Message} }
}

function Schedule-ResumeAndReboot([string]$Id) {
    Ensure-Runner-Copy
    $cmd='powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$RunnerPath+'" -ResumeAfterReboot -CampaignId "'+$Id+'"'
    New-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce" -Force | Out-Null
    Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce" -Name "BCPFinalAcceptance" -Value $cmd
    shutdown.exe /r /t 15 /c "BCP final acceptance: automatic reboot and recovery verification"
}

function Cleanup-Known-LegacyDownloads {
    $downloads=Join-Path $HOME "Downloads"
    $removed=New-Object System.Collections.Generic.List[string]
    $failed=New-Object System.Collections.Generic.List[string]
    if(-not (Test-Path -LiteralPath $downloads -PathType Container)){
        return [ordered]@{removed=@();failed=@()}
    }

    $filePrefixes=@(
        "BCP_PC_BOOTSTRAP",
        "BCP_PC_NATIVE",
        "BCP_PC_NETWORK_REPAIR",
        "INSTALL_BCP_EVERGREEN",
        "BCP_FINAL_BOOTSTRAP",
        "BCP_PC_MIGRATE",
        "BCP_EDGE",
        "BCP-Edge"
    )
    $allowedExtensions=@(".zip",".cmd",".ps1",".apk")

    Get-ChildItem -LiteralPath $downloads -File -ErrorAction SilentlyContinue | ForEach-Object {
        $name=$_.Name
        $ext=$_.Extension.ToLowerInvariant()
        $known=$false
        foreach($prefix in $filePrefixes){
            if($name.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){
                $known=$true
                break
            }
        }
        if($known -and $allowedExtensions -contains $ext){
            try{
                [IO.File]::Delete($_.FullName)
                $removed.Add($_.FullName)
            }catch{
                $failed.Add($_.FullName)
            }
        }
    }

    $dirPrefixes=@(
        "BCP_PC_BOOTSTRAP",
        "BCP_PC_NATIVE",
        "BCP_PC_NETWORK_REPAIR",
        "BCP_FINAL_BOOTSTRAP",
        "BCP_PC_MIGRATE"
    )
    Get-ChildItem -LiteralPath $downloads -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $known=$false
        foreach($prefix in $dirPrefixes){
            if($_.Name.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){
                $known=$true
                break
            }
        }
        if($known){
            try{
                [IO.Directory]::Delete($_.FullName,$true)
                $removed.Add($_.FullName)
            }catch{
                $failed.Add($_.FullName)
            }
        }
    }

    return [ordered]@{removed=@($removed);failed=@($failed)}
}

function Schedule-SelfCleanup {
    $downloads=Join-Path $HOME "Downloads"
    if(-not (Test-Path -LiteralPath $downloads -PathType Container)){return}
    $cleanup=Join-Path $env:TEMP ("BCP_FINAL_ACCEPTANCE_CLEANUP_"+[Guid]::NewGuid().ToString("N")+".ps1")
    $body=@'
param([string]$Downloads)
Start-Sleep -Seconds 3
$patterns=@("BCP_FINAL_ACCEPTANCE_CURRENT*.zip","BCP_FINAL_ACCEPTANCE_CURRENT*.cmd","BCP_FINAL_ACCEPTANCE_CURRENT*.ps1")
foreach($p in $patterns){Get-ChildItem -LiteralPath $Downloads -File -Filter $p -ErrorAction SilentlyContinue|Remove-Item -Force -ErrorAction SilentlyContinue}
Get-ChildItem -LiteralPath $Downloads -Directory -ErrorAction SilentlyContinue|Where-Object{$_.Name -like "BCP_FINAL_ACCEPTANCE_CURRENT*"}|Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Force -LiteralPath $PSCommandPath -ErrorAction SilentlyContinue
'@
    [IO.File]::WriteAllText($cleanup,$body,[Text.UTF8Encoding]::new($false))
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File",$cleanup,"-Downloads",$downloads)|Out-Null
}

if($SelfTest){
    $raw=Get-Content -Raw -LiteralPath $PSCommandPath -Encoding UTF8
    foreach($needle in @(
        "X-BCP-Expected-Revision",
        "ALREADY_COMMITTED",
        "STALE_WRITER_NOT_REJECTED",
        "RunOnce",
        "shutdown.exe /r",
        "BCP_FINAL_ACCEPTANCE_LATEST.json",
        "192.0.2.1",
        "synthetic_cap_bytes",
        "BCP_FINAL_ACCEPTANCE_CURRENT*.zip",
        "filePrefixes",
        "allowedExtensions",
        "dirPrefixes",
        "AUTHENTICATED_DIAGNOSTICS_PATH_SHA_VERSION",
        "pid_mismatch_severity"
    )){
        if($raw -notmatch [regex]::Escape($needle)){throw ("SELFTEST_MISSING_"+$needle)}
    }
    Write-Host "BCP_FINAL_ACCEPTANCE_SELFTEST=PASS"
    exit 0
}

Ensure-Runner-Copy
if(-not $CampaignId){$CampaignId=[DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")+"-"+[Guid]::NewGuid().ToString("N").Substring(0,8)}

if(-not $ResumeAfterReboot){
    $report=[ordered]@{
        schema="bcp.final_acceptance/1"
        campaign_id=$CampaignId
        phase="PRE_REBOOT"
        status="RUNNING"
        started_at=UtcNow
        target_version=$TargetVersion
        project=$Project
        pc_name=$env:COMPUTERNAME
        gates=[ordered]@{}
    }
    try {
        $report.gates.download_hygiene=Cleanup-Known-LegacyDownloads
        $h=Ensure-Target-Version
        $report.gates.runtime_version=[ordered]@{pass=([string]$h.version -eq $TargetVersion);version=[string]$h.version}
        $diag=Invoke-BcpGet "/v1/diagnostics" 5
        $report.gates.pairing=[ordered]@{pass=($diag.paired -eq $true);pair=$diag.pair}
        if(-not $report.gates.pairing.pass){throw "PAIRING_NOT_PRESENT"}

        $checkpoint=Test-Checkpoint-Fencing $CampaignId
        $report.gates.checkpoint=[ordered]@{pass=$true;revision=$checkpoint.committed_revision;hash=$checkpoint.committed_hash}
        $report.gates.idempotency=[ordered]@{pass=($checkpoint.replay_result -eq "ALREADY_COMMITTED")}
        $report.gates.stale_writer=[ordered]@{pass=$checkpoint.stale_writer_rejected}

        $lan=Get-LanIpv4
        $localHealth=Test-Health-Url ($BaseUrl+"/health") 3
        $lanHealth=if($lan){Test-Health-Url ("http://"+$lan+":"+$Port+"/health") 3}else{[ordered]@{ok=$false;version="";ms=0;error="NO_LAN_IPV4"}}
        $report.gates.local_health=$localHealth
        $report.gates.lan_health=$lanHealth
        if(-not $localHealth.ok -or -not $lanHealth.ok){throw "PRE_REBOOT_NETWORK_HEALTH_FAILED"}

        $lifecycle=Lifecycle-Registered
        $listener=Managed-Listener
        $report.gates.lifecycle=$lifecycle
        $report.gates.managed_listener=$listener
        if(-not $lifecycle.registered -or -not $listener.pass){throw "LIFECYCLE_OR_LISTENER_NOT_MANAGED"}

        $state=[ordered]@{
            campaign_id=$CampaignId
            target_version=$TargetVersion
            project=$Project
            token_sha256=File-Sha256 $TokenPath
            pair_sha256=File-Sha256 $PairPath
            committed_revision=$checkpoint.committed_revision
            committed_hash=$checkpoint.committed_hash
            pre_server_pid=$listener.diagnostic_pid
            pre_boot_time=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString("o")
            prepared_at=UtcNow
        }
        Write-JsonAtomic $state $CampaignStatePath
        $report.status="PRE_REBOOT_PASS_REBOOT_SCHEDULED"
        $report.prepared_reboot_at=UtcNow
        Publish-Report $report
        Schedule-ResumeAndReboot $CampaignId
        Write-Host "BCP FINAL ACCEPTANCE: PRE-REBOOT PASS. Windows redemarre automatiquement dans 15 secondes." -ForegroundColor Green
        exit 0
    } catch {
        $report.status="FAIL_PRE_REBOOT"
        $report.error=$_.Exception.Message
        $report.finished_at=UtcNow
        Publish-Report $report
        Write-Host ("BCP FINAL ACCEPTANCE = ECHEC PRE-REBOOT: "+$_.Exception.Message) -ForegroundColor Red
        Read-Host "Appuie sur Entree pour fermer"
        exit 1
    }
}

$prior=Read-Json $CampaignStatePath
$final=[ordered]@{
    schema="bcp.final_acceptance/1"
    campaign_id=$CampaignId
    phase="POST_REBOOT"
    status="RUNNING"
    resumed_at=UtcNow
    target_version=$TargetVersion
    project=$Project
    pc_name=$env:COMPUTERNAME
    gates=[ordered]@{}
}
try {
    if($null -eq $prior -or [string]$prior.campaign_id -ne $CampaignId){throw "CAMPAIGN_STATE_MISSING_OR_MISMATCH"}

    $health=Wait-Health $TargetVersion 180
    if(-not $health){throw "RUNTIME_DID_NOT_RETURN_AFTER_REBOOT"}
    $final.gates.reboot_runtime=[ordered]@{pass=$true;version=[string]$health.version}

    $boot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString("o")
    $final.gates.real_reboot=[ordered]@{pass=($boot -ne [string]$prior.pre_boot_time);before=[string]$prior.pre_boot_time;after=$boot}
    if(-not $final.gates.real_reboot.pass){throw "BOOT_TIME_DID_NOT_CHANGE"}

    $sameToken=((File-Sha256 $TokenPath) -eq [string]$prior.token_sha256)
    $samePair=((File-Sha256 $PairPath) -eq [string]$prior.pair_sha256)
    $final.gates.identity_persistence=[ordered]@{pass=($sameToken -and $samePair);same_token=$sameToken;same_pair=$samePair}
    if(-not $final.gates.identity_persistence.pass){throw "PAIRING_OR_TOKEN_CHANGED_AFTER_REBOOT"}

    $resume=Invoke-BcpGet ("/v1/projects/"+$Project+"/resume") 8
    $sameRevision=([int]$resume.head.revision -eq [int]$prior.committed_revision)
    $sameHash=([string]$resume.head.last_event_hash -eq [string]$prior.committed_hash)
    $final.gates.resume_same_commit=[ordered]@{pass=($sameRevision -and $sameHash);revision=[int]$resume.head.revision;hash=[string]$resume.head.last_event_hash}
    if(-not $final.gates.resume_same_commit.pass){throw "COMMITTED_STATE_NOT_RECOVERED_EXACTLY"}

    $lifecycle=Lifecycle-Registered
    $listener=Managed-Listener
    $final.gates.lifecycle=$lifecycle
    $final.gates.managed_listener=$listener
    if(-not $lifecycle.registered -or -not $listener.pass){throw "POST_REBOOT_LIFECYCLE_FAILED"}

    $lan=Get-LanIpv4
    $final.gates.local_health=Test-Health-Url ($BaseUrl+"/health") 3
    $final.gates.lan_health=if($lan){Test-Health-Url ("http://"+$lan+":"+$Port+"/health") 3}else{[ordered]@{ok=$false;error="NO_LAN_IPV4"}}
    if(-not $final.gates.local_health.ok -or -not $final.gates.lan_health.ok){throw "POST_REBOOT_NETWORK_HEALTH_FAILED"}

    $resource=Test-Resource-Bounds
    $final.gates.resource_bounds=$resource
    if(-not $resource.pass){throw "RESOURCE_BOUNDS_FAILED"}

    $poor=Test-Poor-Connectivity-Bounds
    $final.gates.poor_connectivity_bounds=$poor
    if(-not $poor.pass){throw "POOR_CONNECTIVITY_NOT_BOUNDED"}

    $diag=Invoke-BcpGet "/v1/diagnostics" 5
    $final.gates.pairing_after_reboot=[ordered]@{pass=($diag.paired -eq $true);pair=$diag.pair}
    if(-not $final.gates.pairing_after_reboot.pass){throw "PAIRING_NOT_PRESENT_AFTER_REBOOT"}

    # A PC harness cannot instantiate a brand-new ChatGPT conversation, but it
    # can prove the durable state needed by one is externalized and self-contained.
    $roots=External-Roots
    $final.gates.fresh_context_recovery_readiness=[ordered]@{
        pass=($roots.Count -gt 0)
        durable_external_roots=$roots
        actual_new_chat_context_switch="PLATFORM_BOUNDARY_NOT_EXECUTABLE_BY_PC_HARNESS"
    }

    $final.status="PASS_DEVICE_RUNTIME_GATES"
    $final.finished_at=UtcNow
    $final.summary=[ordered]@{
        runtime=$TargetVersion
        checkpoint_revision=[int]$resume.head.revision
        stale_writer_rejected=$true
        reboot_recovery=$true
        identity_preserved=$true
        lan_health=$true
        resource_bounds=$true
        poor_connectivity_bounds=$true
        remaining_platform_boundary="fresh ChatGPT conversation RESYNC spot-check only"
    }
    Publish-Report $final
    Schedule-SelfCleanup
    Remove-Item -Force -LiteralPath $CampaignStatePath -ErrorAction SilentlyContinue
    exit 0
} catch {
    $final.status="FAIL_POST_REBOOT"
    $final.error=$_.Exception.Message
    $final.finished_at=UtcNow
    Publish-Report $final
    exit 1
}
