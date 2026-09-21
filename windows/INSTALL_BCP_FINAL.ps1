param(
    [switch]$SelfTest,
    [switch]$IntegrationTest,
    [string]$ChatRootOverride = "",
    [string]$ChatPythonOverride = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$InstallerVersion = "0.7.14"
# Keep this target synchronized with release/server.json.
$RuleName = "BCP Local LAN 8765"
$Port = 8765
$ScriptRoot = Split-Path -Parent $PSCommandPath
$BundledServer = Join-Path $ScriptRoot "bcp_server.py"

function UtcNow { [DateTime]::UtcNow.ToString("o") }
function Is-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
function Write-JsonAtomic($Object, [string]$Path) {
    $dir = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $tmp = Join-Path $dir (".tmp-" + [Guid]::NewGuid().ToString("N") + ".json")
    try {
        $json = $Object | ConvertTo-Json -Depth 20
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($tmp, $json, $utf8NoBom)
        Move-Item -Force -LiteralPath $tmp -Destination $Path
    } finally { Remove-Item -Force -LiteralPath $tmp -ErrorAction SilentlyContinue }
}
function Wait-Health([string]$Url, [int]$Seconds = 12) {
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        try {
            $r = Invoke-RestMethod -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($r.ok -eq $true) { return $r }
        } catch {}
        Start-Sleep -Milliseconds 450
    } while ([DateTime]::UtcNow -lt $deadline)
    return $null
}
function Get-ChatGptPcCli([string]$ChatRoot) {
    $candidates = New-Object System.Collections.Generic.List[string]
    $pointer = Join-Path $ChatRoot "state\active_release.json"
    if (Test-Path -LiteralPath $pointer -PathType Leaf) {
        try {
            $p = Get-Content -Raw -LiteralPath $pointer -Encoding UTF8 | ConvertFrom-Json
            if ($p.release_root) { $candidates.Add((Join-Path ([string]$p.release_root) "app\cli.py")) }
        } catch {}
    }
    $candidates.Add((Join-Path $ChatRoot "app\cli.py"))
    $releaseRoot = Join-Path $ChatRoot "releases"
    if (Test-Path -LiteralPath $releaseRoot -PathType Container) {
        Get-ChildItem -LiteralPath $releaseRoot -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending | ForEach-Object {
            $candidates.Add((Join-Path $_.FullName "app\cli.py"))
        }
    }
    foreach ($c in $candidates) { if (Test-Path -LiteralPath $c -PathType Leaf) { return $c } }
    return $null
}
function Stop-OldBcpListener {
    $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    foreach ($l in $listeners) {
        $pidValue = [int]$l.OwningProcess
        if ($pidValue -le 0) { continue }
        $proc = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $pidValue) -ErrorAction SilentlyContinue
        $cmd = if ($proc) { [string]$proc.CommandLine } else { "" }
        $name = if ($proc) { [string]$proc.Name } else { "" }
        $isBcp = ($cmd -match "(?i)bcp_server|ChatGPT_ManagedApps\\bcp|BCP PC Node|server.py") -or (($name -match "(?i)python|powershell") -and ($cmd -match "(?i)8765"))
        if (-not $isBcp) { throw "PORT_8765_IN_USE_BY_NON_BCP pid=$pidValue name=$name" }
        Stop-Process -Id $pidValue -Force -ErrorAction Stop
    }
}
function Ensure-NetworkAndFirewall {
    if ($IntegrationTest) {
        return [pscustomobject]@{ InterfaceAlias="CI_LOOPBACK"; InterfaceIndex=0; NetworkCategory="Private"; IPv4="127.0.0.1" }
    }
    $cfg = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" } | Select-Object -First 1
    if (-not $cfg) { throw "NO_ACTIVE_IPV4_INTERFACE" }
    $profile = Get-NetConnectionProfile -InterfaceIndex $cfg.InterfaceIndex -ErrorAction Stop
    if ($profile.NetworkCategory -eq "Public") {
        Set-NetConnectionProfile -InterfaceIndex $cfg.InterfaceIndex -NetworkCategory Private -ErrorAction Stop
        $profile = Get-NetConnectionProfile -InterfaceIndex $cfg.InterfaceIndex -ErrorAction Stop
    }
    if ($profile.NetworkCategory -notin @("Private","DomainAuthenticated")) { throw "NETWORK_PROFILE_NOT_TRUSTED category=$($profile.NetworkCategory)" }
    Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    try {
        New-NetFirewallRule -DisplayName $RuleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Private,Domain -RemoteAddress LocalSubnet -EdgeTraversalPolicy Block -ErrorAction Stop | Out-Null
    } catch {
        $netsh = Join-Path $env:WINDIR "System32\netsh.exe"
        if (-not (Test-Path -LiteralPath $netsh)) { throw }
        & $netsh advfirewall firewall delete rule name="$RuleName" | Out-Null
        & $netsh advfirewall firewall add rule name="$RuleName" dir=in action=allow protocol=TCP localport=$Port profile=private remoteip=localsubnet edge=no | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "FIREWALL_RULE_CREATE_FAILED" }
    }
    $ip = ($cfg.IPv4Address | Select-Object -First 1).IPAddress
    if (-not $ip) { throw "ACTIVE_INTERFACE_HAS_NO_IPV4" }
    return [pscustomobject]@{ InterfaceAlias=$cfg.InterfaceAlias; InterfaceIndex=$cfg.InterfaceIndex; NetworkCategory=[string]$profile.NetworkCategory; IPv4=[string]$ip }
}

if ($SelfTest) {
    if (-not (Test-Path -LiteralPath $BundledServer -PathType Leaf)) { throw "SELFTEST_BUNDLED_SERVER_MISSING" }
    $raw = Get-Content -Raw -LiteralPath $BundledServer -Encoding UTF8
    $expectedServerPattern = 'SERVER_VERSION = "' + [regex]::Escape($InstallerVersion) + '"'
    if ($raw -notmatch $expectedServerPattern) { throw "SELFTEST_SERVER_VERSION_MISMATCH expected=$InstallerVersion" }
    if ($raw -notmatch '/pair' -or $raw -notmatch '/v1/telemetry') { throw "SELFTEST_REQUIRED_ENDPOINTS_MISSING" }

    $probeDir = Join-Path ([System.IO.Path]::GetTempPath()) ("bcp-json-selftest-" + [Guid]::NewGuid().ToString("N"))
    $probePath = Join-Path $probeDir "probe.json"
    try {
        Write-JsonAtomic ([ordered]@{schema=1;probe="utf8-no-bom"}) $probePath
        $bytes = [System.IO.File]::ReadAllBytes($probePath)
        if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
            throw "SELFTEST_JSON_UTF8_BOM_PRESENT"
        }
        [System.Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json | Out-Null
    } finally {
        Remove-Item -Recurse -Force -LiteralPath $probeDir -ErrorAction SilentlyContinue
    }
    Write-Host "BCP_INSTALLER_SELFTEST=PASS"
    exit 0
}

if (-not $IntegrationTest -and -not (Is-Admin)) {
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File",$PSCommandPath) | Out-Null
    exit 0
}

$startedAt = UtcNow
$ChatRoot = if ($ChatRootOverride) { $ChatRootOverride } else { Join-Path $env:LOCALAPPDATA "Tunnel_PC_G4" }
$ChatPython = if ($ChatPythonOverride) { $ChatPythonOverride } else { Join-Path $ChatRoot "runtime\python.exe" }
$ManagedRoot = Join-Path $env:LOCALAPPDATA "ChatGPT_ManagedApps"
$AppRoot = Join-Path $ManagedRoot "bcp"
$Logs = Join-Path $AppRoot "logs"
$State = Join-Path $AppRoot "state"
$Telemetry = Join-Path $AppRoot "telemetry"
$ReceiptDir = Join-Path $AppRoot "receipts"
$ServerTarget = Join-Path $AppRoot "server.py"
$ApprovalMarker = Join-Path $AppRoot "PCA_MANAGED_APP_APPROVED.json"
$ManifestPath = Join-Path $AppRoot "PCA_APP_MANIFEST.json"
$InstallLog = Join-Path $Logs "install.jsonl"
New-Item -ItemType Directory -Force -Path $AppRoot,$Logs,$State,$Telemetry,$ReceiptDir | Out-Null

function Stage([string]$Name, [string]$Status, [string]$Detail = "") {
    $o = [ordered]@{ ts=UtcNow; installer_version=$InstallerVersion; stage=$Name; status=$Status; detail=$Detail }
    $line = ($o | ConvertTo-Json -Compress -Depth 8) + [Environment]::NewLine
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::AppendAllText($InstallLog, $line, $utf8NoBom)
    Write-Host ("[{0}] {1} {2}" -f $Status,$Name,$Detail)
}

try {
    Stage "PREFLIGHT" "RUNNING"
    if (-not (Test-Path -LiteralPath $BundledServer -PathType Leaf)) { throw "BUNDLED_SERVER_MISSING" }
    if (-not (Test-Path -LiteralPath $ChatPython -PathType Leaf)) { throw "CHATGPT_PC_RUNTIME_MISSING expected=$ChatPython" }
    $cli = Get-ChatGptPcCli $ChatRoot
    if (-not $cli) { throw "CHATGPT_PC_CLI_NOT_FOUND" }
    Stage "PREFLIGHT" "PASS" ("ChatGPT-PC=" + $ChatRoot)

    Stage "PORT_CLEANUP" "RUNNING"
    Stop-OldBcpListener
    Stage "PORT_CLEANUP" "PASS"

    Stage "NETWORK_FIREWALL" "RUNNING"
    $net = Ensure-NetworkAndFirewall
    Stage "NETWORK_FIREWALL" "PASS" ("ip=" + $net.IPv4 + " profile=" + $net.NetworkCategory)

    Stage "INSTALL_PAYLOAD" "RUNNING"
    $tmpServer = Join-Path $AppRoot "server.py.new"
    Copy-Item -Force -LiteralPath $BundledServer -Destination $tmpServer
    & $ChatPython $tmpServer --selftest
    if ($LASTEXITCODE -ne 0) { throw "BCP_SERVER_SELFTEST_FAILED" }
    Move-Item -Force -LiteralPath $tmpServer -Destination $ServerTarget
    Write-JsonAtomic ([ordered]@{schema=1;approved=$true;app_id="bcp";approved_locally=$true;approved_at=UtcNow;approval_basis="explicit_local_installer_run_with_uac"}) $ApprovalMarker
    $manifest = [ordered]@{
        app_id="bcp"; display_name="Blessing Control Plane"; install_root=$AppRoot; executable="{app_root}/server.py";
        test_command=@("{python}","{app_root}/server.py","--selftest"); test_timeout=45;
        start_command=@("{python}","{app_root}/server.py","--bind","0.0.0.0","--port","8765");
        log_paths=@("logs/http.log","logs/install.jsonl","telemetry/phone-events.jsonl");
        resource_profile=[ordered]@{class="LOW_RAM_COMPAT";memory_limit_mb=96;background_qos="ECO";battery_policy="DEFER_WHEN_LOW"}
    }
    Write-JsonAtomic $manifest $ManifestPath
    Stage "INSTALL_PAYLOAD" "PASS"

    Stage "CHATGPT_PC_REGISTER" "RUNNING"
    $env:PCA_INSTALL_ROOT = $ChatRoot
    $env:PCA_PYTHON = $ChatPython
    $registerOut = & $ChatPython $cli register $ManifestPath 2>&1
    if ($LASTEXITCODE -ne 0) { throw ("CHATGPT_PC_REGISTER_FAILED " + ($registerOut -join " ")) }
    Stage "CHATGPT_PC_REGISTER" "PASS"

    Stage "START_SERVER" "RUNNING"
    $stdout = Join-Path $Logs "server.stdout.log"
    $stderr = Join-Path $Logs "server.stderr.log"
    Start-Process -FilePath $ChatPython -ArgumentList @($ServerTarget,"--bind","0.0.0.0","--port","8765") -WorkingDirectory $AppRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr | Out-Null
    $localHealth = Wait-Health "http://127.0.0.1:8765/health" 15
    if (-not $localHealth) { throw "LOCAL_HEALTH_TIMEOUT" }
    $lanHealth = Wait-Health ("http://" + $net.IPv4 + ":8765/health") 8
    if (-not $lanHealth) { throw "LAN_HEALTH_TIMEOUT" }
    Stage "START_SERVER" "PASS" ("server=" + $net.IPv4 + ":8765")

    $receipt = [ordered]@{
        schema="bcp.install.receipt/1";status="PASS";installer_version=$InstallerVersion;started_at=$startedAt;finished_at=UtcNow;
        chatgpt_pc_root=$ChatRoot;chatgpt_pc_python=$ChatPython;chatgpt_pc_cli=$cli;app_root=$AppRoot;pc_ipv4=$net.IPv4;
        network_profile=$net.NetworkCategory;firewall_rule=if($IntegrationTest){"CI_BYPASS"}else{$RuleName};local_health=$true;lan_health=$true;server_version=[string]$localHealth.version;
        scheduled_task_created=$false;manual_ip_token_required=$false;integration_test=[bool]$IntegrationTest;next="Open BCP Edge; automatic discovery/pairing should complete."
    }
    $receiptPath = Join-Path $ReceiptDir ("install-" + [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ") + ".json")
    Write-JsonAtomic $receipt $receiptPath
    Copy-Item -Force -LiteralPath $receiptPath -Destination (Join-Path $ChatRoot "logs\BCP_LAST_INSTALL_RECEIPT.json") -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " BCP INSTALLATION = PASS" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ("PC: " + $net.IPv4 + ":8765")
    Write-Host "ChatGPT-PC registration: PASS"
    Write-Host "Firewall: PASS"
    Write-Host "Local health: PASS"
    Write-Host "LAN health: PASS"
    Write-Host ""
    if (-not $IntegrationTest) { Write-Host "On the old phone: reopen BCP Edge. Do not type IP/token/project." }
    exit 0
}
catch {
    $message = $_.Exception.Message
    Stage "INSTALL" "FAIL" $message
    $receipt = [ordered]@{schema="bcp.install.receipt/1";status="FAIL";installer_version=$InstallerVersion;started_at=$startedAt;finished_at=UtcNow;error=$message;scheduled_task_created=$false;integration_test=[bool]$IntegrationTest;logs=$InstallLog}
    $receiptPath = Join-Path $ReceiptDir ("install-fail-" + [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ") + ".json")
    Write-JsonAtomic $receipt $receiptPath
    Copy-Item -Force -LiteralPath $receiptPath -Destination (Join-Path $ChatRoot "logs\BCP_LAST_INSTALL_RECEIPT.json") -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Host ("BCP INSTALLATION = FAIL: " + $message) -ForegroundColor Red
    Write-Host ("Receipt: " + $receiptPath)
    exit 1
}
