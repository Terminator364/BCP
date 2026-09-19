param(
    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TargetVersion = "0.4.4"
$PinnedCommit = "c0d10a286a5a4e18d755a31811e7b479f7ad9cff"
$InstallerSha256 = "3ad1594a948768b15f583a7806eb7fb084935ecbcd1ccac0079ce88e43f6d53e"
$ServerSha256 = "c23e9d79262884b399cfb3abba382dae3c4b18ccbe158fe818e6497f7a493993"
$Base = "https://raw.githubusercontent.com/Terminator364/BCP/$PinnedCommit/windows"
$TempRoot = Join-Path $env:TEMP "BCP_PC_MIGRATE_0_4_4"
$LegacyRoot = Join-Path $env:LOCALAPPDATA "BCP"
$LegacyState = Join-Path $LegacyRoot "state"
$ManagedRoot = Join-Path $env:LOCALAPPDATA "ChatGPT_ManagedApps\bcp"
$ManagedState = Join-Path $ManagedRoot "state"
$ManagedReceipts = Join-Path $ManagedRoot "receipts"
$RuleName = "BCP Local LAN 8765"
$Port = 8765

function UtcNow { [DateTime]::UtcNow.ToString("o") }

function Write-JsonAtomic($Object, [string]$Path) {
    $dir = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $tmp = Join-Path $dir (".tmp-" + [Guid]::NewGuid().ToString("N") + ".json")
    try {
        $json = $Object | ConvertTo-Json -Depth 20
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($tmp, $json, $utf8NoBom)
        Move-Item -Force -LiteralPath $tmp -Destination $Path
    } finally {
        Remove-Item -Force -LiteralPath $tmp -ErrorAction SilentlyContinue
    }
}

function Get-DriveReceiptRoots {
    $candidates = @(
        "G:\Mon Drive\CHATGPT_PC_AGENT\04_RECEIPTS",
        "G:\My Drive\CHATGPT_PC_AGENT\04_RECEIPTS",
        (Join-Path $HOME "Mon Drive\CHATGPT_PC_AGENT\04_RECEIPTS"),
        (Join-Path $HOME "My Drive\CHATGPT_PC_AGENT\04_RECEIPTS")
    )
    $out = New-Object System.Collections.Generic.List[string]
    foreach ($p in $candidates) {
        $parent = Split-Path -Parent $p
        if (Test-Path -LiteralPath $parent -PathType Container) {
            try {
                New-Item -ItemType Directory -Force -Path $p | Out-Null
                $out.Add($p)
            } catch {}
        }
    }
    return @($out)
}

function Write-MigrationReceipt([string]$Status, [hashtable]$Extra = @{}) {
    $obj = [ordered]@{
        schema = "bcp.pc_migration.receipt/2"
        status = $Status
        target_version = $TargetVersion
        pinned_commit = $PinnedCommit
        pc_name = $env:COMPUTERNAME
        ts = UtcNow
    }
    foreach ($k in $Extra.Keys) { $obj[$k] = $Extra[$k] }
    New-Item -ItemType Directory -Force -Path $ManagedReceipts | Out-Null
    Write-JsonAtomic $obj (Join-Path $ManagedReceipts "BCP_PC_MIGRATION_LATEST.json")
    foreach ($root in (Get-DriveReceiptRoots)) {
        try { Write-JsonAtomic $obj (Join-Path $root "BCP_PC_MIGRATION_LATEST.json") } catch {}
    }
}

function Disable-LegacySupervisor {
    $stopped = @()
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        [string]$_.CommandLine -match "(?i)bcp_supervisor\.ps1"
    } | ForEach-Object {
        try {
            Stop-Process -Id ([int]$_.ProcessId) -Force -ErrorAction Stop
            $stopped += [int]$_.ProcessId
        } catch {}
    }

    $disabledTasks = @()
    try {
        Get-ScheduledTask -ErrorAction Stop | ForEach-Object {
            $task = $_
            $match = $false
            foreach ($a in @($task.Actions)) {
                if (([string]$a.Arguments -match "(?i)bcp_supervisor\.ps1") -or
                    ([string]$a.Execute -match "(?i)bcp_supervisor\.ps1")) {
                    $match = $true
                }
            }
            if ($match) {
                try {
                    Disable-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath -ErrorAction Stop | Out-Null
                    $disabledTasks += ($task.TaskPath + $task.TaskName)
                } catch {}
            }
        }
    } catch {}

    return [ordered]@{stopped_processes=$stopped;disabled_tasks=$disabledTasks}
}

function Stop-LegacyListener {
    @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) | ForEach-Object {
        $pidValue = [int]$_.OwningProcess
        if ($pidValue -le 0) { return }
        $proc = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $pidValue) -ErrorAction SilentlyContinue
        $cmd = if ($proc) { [string]$proc.CommandLine } else { "" }
        if ($cmd -match "(?i)\\BCP\\bin\\bcp_server\.ps1|bcp_server\.ps1|ChatGPT_ManagedApps\\bcp|server\.py") {
            Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
        }
    }
}

function Migrate-LegacyIdentity {
    New-Item -ItemType Directory -Force -Path $ManagedState | Out-Null
    $backup = Join-Path $ManagedState ("migration_backup_" + [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ"))
    New-Item -ItemType Directory -Force -Path $backup | Out-Null

    $copied = @()
    foreach ($name in @("bcp_token.txt","paired_edge.json")) {
        $src = Join-Path $LegacyState $name
        $dst = Join-Path $ManagedState $name
        if (Test-Path -LiteralPath $src -PathType Leaf) {
            if (Test-Path -LiteralPath $dst -PathType Leaf) {
                Copy-Item -Force -LiteralPath $dst -Destination (Join-Path $backup $name)
            }
            Copy-Item -Force -LiteralPath $src -Destination $dst
            $copied += $name
        }
    }

    foreach ($name in @("project_state.json","events.jsonl")) {
        $src = Join-Path $LegacyState $name
        if (Test-Path -LiteralPath $src -PathType Leaf) {
            Copy-Item -Force -LiteralPath $src -Destination (Join-Path $backup ("legacy_" + $name))
        }
    }

    return [ordered]@{copied=$copied;backup=$backup}
}

function Wait-Health([int]$Seconds = 30) {
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        try {
            $h = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
            if ($h.ok -eq $true -and [string]$h.version -eq $TargetVersion) { return $h }
        } catch {}
        Start-Sleep -Milliseconds 600
    } while ([DateTime]::UtcNow -lt $deadline)
    return $null
}

function Verify-ManagedListener {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop | Select-Object -First 1
    if (-not $listener) { throw "NO_BCP_LISTENER_AFTER_MIGRATION" }
    $pidValue = [int]$listener.OwningProcess
    $proc = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $pidValue) -ErrorAction Stop
    $cmd = [string]$proc.CommandLine
    if ($cmd -notmatch "(?i)ChatGPT_ManagedApps\\bcp\\server\.py") {
        throw "PORT_8765_NOT_MANAGED_BCP pid=$pidValue cmd=$cmd"
    }
    return [ordered]@{pid=$pidValue;name=[string]$proc.Name;managed=$true}
}

function Verify-AuthenticatedDiagnostics {
    $tokenPath = Join-Path $ManagedState "bcp_token.txt"
    if (-not (Test-Path -LiteralPath $tokenPath -PathType Leaf)) { throw "MANAGED_TOKEN_MISSING" }
    $token = (Get-Content -Raw -LiteralPath $tokenPath).Trim()
    $headers = @{ Authorization = "Bearer $token" }
    $d = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:$Port/v1/diagnostics" -Headers $headers -TimeoutSec 4
    if ($d.ok -ne $true) { throw "AUTH_DIAGNOSTICS_NOT_OK" }
    if ([string]$d.server_version -ne $TargetVersion) { throw "AUTH_DIAGNOSTICS_VERSION_MISMATCH" }
    return $true
}

if ($SelfTest) {
    $self = Get-Content -Raw -LiteralPath $PSCommandPath -Encoding UTF8
    foreach ($needle in @(
        "bcp_supervisor.ps1",
        "bcp_token.txt",
        "paired_edge.json",
        "PORT_8765_NOT_MANAGED_BCP",
        "BCP_PC_MIGRATION_LATEST.json",
        $PinnedCommit,
        $InstallerSha256,
        $ServerSha256
    )) {
        if ($self -notmatch [regex]::Escape($needle)) { throw "SELFTEST_MISSING_$needle" }
    }
    Write-Host "BCP_PC_MIGRATION_SELFTEST=PASS"
    exit 0
}

$started = UtcNow
try {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host " BCP legacy 0.3.x -> managed 0.4.4" -ForegroundColor Cyan
    Write-Host "============================================================"

    Write-Host "[1/7] Neutralisation du superviseur legacy..."
    $legacy = Disable-LegacySupervisor
    Stop-LegacyListener

    Write-Host "[2/7] Migration du token et de l'appairage..."
    $identity = Migrate-LegacyIdentity

    Write-Host "[3/7] Telechargement pinne + verification SHA-256..."
    if (Test-Path -LiteralPath $TempRoot) { Remove-Item -Recurse -Force -LiteralPath $TempRoot }
    New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $installer = Join-Path $TempRoot "INSTALL_BCP_FINAL.ps1"
    $server = Join-Path $TempRoot "bcp_server.py"
    $ProgressPreference = "SilentlyContinue"
    Invoke-WebRequest -UseBasicParsing -Uri "$Base/INSTALL_BCP_FINAL.ps1" -OutFile $installer -TimeoutSec 30
    Invoke-WebRequest -UseBasicParsing -Uri "$Base/bcp_server.py" -OutFile $server -TimeoutSec 30
    $ih = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash.ToLowerInvariant()
    $sh = (Get-FileHash -Algorithm SHA256 -LiteralPath $server).Hash.ToLowerInvariant()
    if ($ih -ne $InstallerSha256) { throw "INSTALLER_SHA256_MISMATCH:$ih" }
    if ($sh -ne $ServerSha256) { throw "SERVER_SHA256_MISMATCH:$sh" }

    Write-Host "[4/7] Installation BCP managed 0.4.4..."
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer
    if ($LASTEXITCODE -ne 0) { throw "INSTALLER_FAILED_RC_$LASTEXITCODE" }

    Write-Host "[5/7] Verification runtime 0.4.4..."
    $health = Wait-Health 30
    if (-not $health) { throw "BCP_0_4_4_HEALTH_TIMEOUT" }

    Write-Host "[6/7] Verification du processus et de l'identite..."
    $listener = Verify-ManagedListener
    $auth = Verify-AuthenticatedDiagnostics

    Write-Host "[7/7] Receipt durable..."
    Write-MigrationReceipt "PASS" @{
        started_at=$started
        finished_at=(UtcNow)
        runtime_version=[string]$health.version
        listener_pid=$listener.pid
        listener_managed=$listener.managed
        authenticated_diagnostics=$auth
        legacy_supervisor_stopped=$legacy.stopped_processes
        legacy_tasks_disabled=$legacy.disabled_tasks
        migrated_identity_files=$identity.copied
        identity_backup=$identity.backup
    }

    Remove-Item -Recurse -Force -LiteralPath $TempRoot -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Host "BCP 0.4.4 = ACTIF / MANAGED / AUTH OK" -ForegroundColor Green
    Write-Host "Tu peux rouvrir BCP Edge." -ForegroundColor Green
    Start-Sleep -Seconds 6
    exit 0
}
catch {
    $message = $_.Exception.Message
    try {
        Write-MigrationReceipt "FAIL" @{
            started_at=$started
            finished_at=(UtcNow)
            error=$message
        }
    } catch {}
    Write-Host ""
    Write-Host ("MIGRATION BCP = ECHEC: " + $message) -ForegroundColor Red
    Write-Host "Aucun retry automatique n'est lance."
    Read-Host "Appuie sur Entree pour fermer"
    exit 1
}
