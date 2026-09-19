param(
    [switch]$SelfTest,
    [string]$WorkerName = "bcp-nexus",
    [string]$DatabaseName = "bcp-nexus",
    [string]$DeviceId = "pc-worker"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$AppRoot = Join-Path $env:LOCALAPPDATA "ChatGPT_ManagedApps\bcp"
$StateDir = Join-Path $AppRoot "state"
$DeployRoot = Join-Path $AppRoot "nexus-deploy"
$TokenPath = Join-Path $StateDir "telegram_bot_token.txt"
$TelegramConfigPath = Join-Path $StateDir "telegram_observability.json"
$ReceiptPath = Join-Path $StateDir "nexus_bootstrap_receipt.json"
$InstalledBot = Join-Path $AppRoot "telegram_observability.py"
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$RunName = "BlessingControlPlaneTelegram"

function UtcNow { [DateTime]::UtcNow.ToString("o") }

function Write-JsonAtomic($Object, [string]$Path) {
    $dir = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $tmp = Join-Path $dir (".tmp-" + [Guid]::NewGuid().ToString("N") + ".json")
    try {
        [IO.File]::WriteAllText($tmp, ($Object | ConvertTo-Json -Depth 16), (New-Object Text.UTF8Encoding($false)))
        Move-Item -Force -LiteralPath $tmp -Destination $Path
    } finally {
        Remove-Item -Force -LiteralPath $tmp -ErrorAction SilentlyContinue
    }
}

function Protect-LocalFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return }
    $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    & icacls.exe $Path /inheritance:r /grant:r ($user + ":(R,W)") /c | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "LOCAL_SECRET_ACL_HARDENING_FAILED" }
}

function New-Base64UrlSecret([int]$Bytes = 32) {
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $buffer = New-Object byte[] $Bytes
        $rng.GetBytes($buffer)
        return [Convert]::ToBase64String($buffer).TrimEnd("=").Replace("+","-").Replace("/","_")
    } finally { $rng.Dispose() }
}

function Find-SourceFile([string]$Name) {
    $roots = @($PSScriptRoot, (Split-Path -Parent $PSScriptRoot), (Join-Path $PSScriptRoot "..\nexus\cloudflare-worker"))
    foreach ($root in $roots) {
        if (-not $root -or -not (Test-Path -LiteralPath $root)) { continue }
        $direct = Join-Path $root $Name
        if (Test-Path -LiteralPath $direct -PathType Leaf) { return (Resolve-Path $direct).Path }
        $found = Get-ChildItem -LiteralPath $root -Recurse -File -Filter $Name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    return $null
}

function Find-WranglerLauncher {
    foreach ($name in @("wrangler.cmd","wrangler.exe","wrangler")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return [pscustomobject]@{ File = $cmd.Source; Prefix = @() } }
    }
    foreach ($name in @("npx.cmd","npx.exe","npx")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return [pscustomobject]@{ File = $cmd.Source; Prefix = @("wrangler") } }
    }
    return $null
}

function Invoke-Wrangler($Launcher, [string[]]$Arguments, [switch]$AllowFailure) {
    $all = @()
    foreach ($p in @($Launcher.Prefix)) { $all += [string]$p }
    foreach ($a in @($Arguments)) { $all += [string]$a }
    $out = & $Launcher.File @all 2>&1
    $code = $LASTEXITCODE
    $text = (($out | ForEach-Object { [string]$_ }) -join [Environment]::NewLine)
    if ($code -ne 0 -and -not $AllowFailure) { throw ("WRANGLER_FAILED exit=" + $code) }
    return [pscustomobject]@{ ExitCode = $code; Text = $text }
}

function Invoke-WranglerSecret($Launcher, [string]$ConfigPath, [string]$Name, [string]$Value) {
    $all = @()
    foreach ($p in @($Launcher.Prefix)) { $all += [string]$p }
    $all += @("secret","put",$Name,"--config",$ConfigPath)
    $Value | & $Launcher.File @all 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw ("WRANGLER_SECRET_PUT_FAILED name=" + $Name) }
}

function Get-D1Database($Launcher, [string]$Name) {
    $r = Invoke-Wrangler $Launcher @("d1","list","--json") -AllowFailure
    if ($r.ExitCode -ne 0) { return $null }
    $raw = [string]$r.Text
    $start = $raw.IndexOf("[")
    $end = $raw.LastIndexOf("]")
    if ($start -lt 0 -or $end -le $start) { return $null }
    try { $items = $raw.Substring($start, $end - $start + 1) | ConvertFrom-Json } catch { return $null }
    foreach ($item in @($items)) { if ([string]$item.name -eq $Name) { return $item } }
    return $null
}

function Find-Python {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Tunnel_PC_G4\runtime\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe")
    )
    foreach ($p in $candidates) { if (Test-Path -LiteralPath $p -PathType Leaf) { return $p } }
    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Stop-ExistingTelegramWorker {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { ([string]$_.CommandLine -match "telegram_observability\.py") -and ([string]$_.Name -match "(?i)python") } |
        ForEach-Object { Stop-Process -Id ([int]$_.ProcessId) -Force -ErrorAction SilentlyContinue }
}

function Invoke-Telegram([string]$Token, [string]$Method, $Body, [int]$TimeoutSec = 25) {
    $uri = "https://api.telegram.org/bot" + $Token + "/" + $Method
    return Invoke-RestMethod -Method Post -Uri $uri -ContentType "application/json" -Body ($Body | ConvertTo-Json -Compress -Depth 12) -TimeoutSec $TimeoutSec
}

function Read-NexusUrl([string]$DeployText, [string]$OutputFile) {
    $joined = [string]$DeployText
    if (Test-Path -LiteralPath $OutputFile -PathType Leaf) {
        try { $joined += [Environment]::NewLine + [IO.File]::ReadAllText($OutputFile) } catch {}
    }
    $m = [regex]::Match($joined, 'https://[A-Za-z0-9.-]+\.workers\.dev')
    if ($m.Success) { return $m.Value.TrimEnd("/") }
    return ""
}

if ($SelfTest) {
    $a = New-Base64UrlSecret 32
    $b = New-Base64UrlSecret 48
    if ($a.Length -lt 40 -or $b.Length -lt 60) { throw "SELFTEST_SECRET_LENGTH" }
    if ($a -notmatch '^[A-Za-z0-9_-]+$' -or $b -notmatch '^[A-Za-z0-9_-]+$') { throw "SELFTEST_SECRET_ALPHABET" }
    $raw = [IO.File]::ReadAllText($PSCommandPath)
    foreach ($required in @("CLOUDFLARE_LOGIN_REQUIRED","TELEGRAM_BOT_TOKEN","TELEGRAM_WEBHOOK_SECRET","BCP_DEVICE_TOKEN","ALLOWED_CHAT_ID","--remote","setWebhook","CONFIGURE_BCP_NEXUS","WRANGLER_OUTPUT_FILE_PATH","nexus_bootstrap_receipt.json")) {
        if ($raw -notmatch [regex]::Escape($required)) { throw ("SELFTEST_CONTRACT_MISSING " + $required) }
    }
    if ($raw -match '\b\d{6,12}:[A-Za-z0-9_-]{20,}\b') { throw "SELFTEST_HARDCODED_TELEGRAM_TOKEN" }
    Write-Host "BCP_NEXUS_BOOTSTRAP_SELFTEST=PASS"
    exit 0
}

if (-not (Test-Path -LiteralPath $TokenPath -PathType Leaf)) { throw "LOCAL_TELEGRAM_TOKEN_NOT_FOUND_RUN_TELEGRAM_BOOTSTRAP_ONCE" }
if (-not (Test-Path -LiteralPath $TelegramConfigPath -PathType Leaf)) { throw "LOCAL_TELEGRAM_CONFIG_NOT_FOUND_RUN_TELEGRAM_BOOTSTRAP_ONCE" }
if (-not (Test-Path -LiteralPath $InstalledBot -PathType Leaf)) { throw "LOCAL_TELEGRAM_WORKER_NOT_FOUND_WAIT_FOR_BCP_0_6_2_COMPANION_DELIVERY" }

$token = ([IO.File]::ReadAllText($TokenPath)).Trim()
if ($token -notmatch '^\d{6,12}:[A-Za-z0-9_-]{20,}$') { throw "LOCAL_TELEGRAM_TOKEN_FORMAT_INVALID" }
$tgConfig = Get-Content -Raw -LiteralPath $TelegramConfigPath | ConvertFrom-Json
$chatId = [int64]0
if ($tgConfig -and ($tgConfig.PSObject.Properties.Name -contains "allowed_chat_id")) { $chatId = [int64]$tgConfig.allowed_chat_id }
if ($chatId -eq 0) { throw "LOCAL_TELEGRAM_CHAT_NOT_AUTHORIZED" }

$launcher = Find-WranglerLauncher
if (-not $launcher) {
    Write-Host "BCP_NEXUS_HUMAN_GATE=WRANGLER_RUNTIME_REQUIRED"
    Write-Host "Install Node.js/Wrangler once, then rerun this same script. No Telegram token re-entry will be needed."
    exit 3
}

$who = Invoke-Wrangler $launcher @("whoami","--json") -AllowFailure
if ($who.ExitCode -ne 0) {
    Write-Host "BCP_NEXUS_HUMAN_GATE=CLOUDFLARE_LOGIN_REQUIRED"
    Write-Host "One-time gate only: run 'npx wrangler login' in this PowerShell, finish browser authorization, then rerun this script."
    Write-Host "No Telegram token, chat ID, or device secret must be copied into chat."
    exit 4
}

$workerSource = Find-SourceFile "worker.mjs"
$migrationSource = Find-SourceFile "0001_init.sql"
$configurator = Find-SourceFile "CONFIGURE_BCP_NEXUS.ps1"
if (-not $workerSource -or -not $migrationSource -or -not $configurator) { throw "NEXUS_SOURCE_BUNDLE_INCOMPLETE" }

New-Item -ItemType Directory -Force -Path $DeployRoot,(Join-Path $DeployRoot "src"),(Join-Path $DeployRoot "migrations") | Out-Null
Copy-Item -Force -LiteralPath $workerSource -Destination (Join-Path $DeployRoot "src\worker.mjs")
Copy-Item -Force -LiteralPath $migrationSource -Destination (Join-Path $DeployRoot "migrations\0001_init.sql")

$db = Get-D1Database $launcher $DatabaseName
if (-not $db) {
    Write-Host "BCP Nexus: creating D1 database..."
    Invoke-Wrangler $launcher @("d1","create",$DatabaseName) | Out-Null
    $db = Get-D1Database $launcher $DatabaseName
}
if (-not $db) { throw "NEXUS_D1_DATABASE_ID_NOT_RESOLVED" }
$dbId = ""
if ($db.PSObject.Properties.Name -contains "uuid") { $dbId = [string]$db.uuid }
if (-not $dbId -and ($db.PSObject.Properties.Name -contains "id")) { $dbId = [string]$db.id }
if (-not $dbId) { throw "NEXUS_D1_DATABASE_ID_NOT_RESOLVED" }

$wranglerConfig = Join-Path $DeployRoot "wrangler.toml"
$toml = @"
name = "$WorkerName"
main = "src/worker.mjs"
compatibility_date = "2026-09-19"
workers_dev = true

[[d1_databases]]
binding = "DB"
database_name = "$DatabaseName"
database_id = "$dbId"

[vars]
BCP_DEVICE_ID = "$DeviceId"
"@
[IO.File]::WriteAllText($wranglerConfig, $toml, (New-Object Text.UTF8Encoding($false)))

$deviceToken = New-Base64UrlSecret 48
$webhookSecret = New-Base64UrlSecret 32

Write-Host "BCP Nexus: provisioning locally generated secrets directly to Cloudflare..."
Invoke-WranglerSecret $launcher $wranglerConfig "TELEGRAM_BOT_TOKEN" $token
Invoke-WranglerSecret $launcher $wranglerConfig "TELEGRAM_WEBHOOK_SECRET" $webhookSecret
Invoke-WranglerSecret $launcher $wranglerConfig "BCP_DEVICE_TOKEN" $deviceToken
Invoke-WranglerSecret $launcher $wranglerConfig "ALLOWED_CHAT_ID" ([string]$chatId)

Write-Host "BCP Nexus: applying D1 schema..."
Invoke-Wrangler $launcher @("d1","execute",$DatabaseName,"--remote","--file",(Join-Path $DeployRoot "migrations\0001_init.sql"),"--yes","--config",$wranglerConfig) | Out-Null

$outputFile = Join-Path $DeployRoot "wrangler-deploy-output.ndjson"
Remove-Item -Force -LiteralPath $outputFile -ErrorAction SilentlyContinue
$oldOutput = $env:WRANGLER_OUTPUT_FILE_PATH
try {
    $env:WRANGLER_OUTPUT_FILE_PATH = $outputFile
    Write-Host "BCP Nexus: deploying Worker..."
    $deploy = Invoke-Wrangler $launcher @("deploy","--config",$wranglerConfig)
} finally { $env:WRANGLER_OUTPUT_FILE_PATH = $oldOutput }

$nexusUrl = Read-NexusUrl ([string]$deploy.Text) $outputFile
if (-not $nexusUrl) { throw "NEXUS_DEPLOY_URL_NOT_DISCOVERED" }

$health = Invoke-RestMethod -Method Get -Uri ($nexusUrl + "/health") -TimeoutSec 20
if (-not $health -or [string]$health.status -ne "HEALTHY") { throw "NEXUS_HEALTH_CHECK_FAILED" }

$webhookApplied = $false
try {
    Stop-ExistingTelegramWorker
    $set = Invoke-Telegram $token "setWebhook" @{ url = ($nexusUrl + "/telegram/webhook"); secret_token = $webhookSecret; allowed_updates = @("message"); drop_pending_updates = $false } 30
    if (-not $set.ok) { throw "TELEGRAM_SET_WEBHOOK_FAILED" }
    $webhookApplied = $true

    $secureDevice = ConvertTo-SecureString $deviceToken -AsPlainText -Force
    & $configurator -NexusUrl $nexusUrl -DeviceId $DeviceId -DeviceToken $secureDevice

    $python = Find-Python
    if (-not $python) { throw "PYTHON_RUNTIME_NOT_FOUND" }
    New-Item -ItemType Directory -Force -Path $RunKey | Out-Null
    Set-ItemProperty -Path $RunKey -Name $RunName -Value ('"' + $python + '" "' + $InstalledBot + '"')
    $proc = Start-Process -FilePath $python -ArgumentList @($InstalledBot) -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 2
    if ($proc.HasExited) { throw "NEXUS_WORKER_PROCESS_EXITED_EARLY" }

    $headers = @{ Authorization = "Bearer " + $deviceToken; "X-BCP-Device-ID" = $DeviceId }
    $pushBody = @{ kind = "NEXUS_BOOTSTRAP"; text = '✅ BCP Nexus connecté. PC et ancien téléphone peuvent rester sur le Wi-Fi maison. Telegram direct du PC n''est plus le chemin critique. Coût: $0.00'; idempotency_key = ("bootstrap-" + [Guid]::NewGuid().ToString("N")) } | ConvertTo-Json -Compress
    $push = Invoke-RestMethod -Method Post -Uri ($nexusUrl + "/v1/device/push") -Headers $headers -ContentType "application/json" -Body $pushBody -TimeoutSec 25
    if (-not $push.ok) { throw "NEXUS_TELEGRAM_PUSH_SMOKE_FAILED" }

    $receipt = [ordered]@{
        schema = "bcp.nexus_bootstrap_receipt/1"
        status = "NEXUS_DEPLOYED_LOCAL_WORKER_RUNNING"
        worker_name = $WorkerName
        nexus_url = $nexusUrl
        database_name = $DatabaseName
        database_id = $dbId
        device_id = $DeviceId
        secrets = "LOCAL_AND_PROVIDER_ONLY_NOT_LOGGED"
        telegram_webhook = "SET"
        local_transport = "NEXUS"
        local_worker_pid = $proc.Id
        spend_policy = "ZERO_USD"
        spend_usd = 0.0
        configured_at = UtcNow
        field_gate = "SEND_STATUS_FROM_TELEGRAM_AND_VERIFY_HOME_WIFI_ROUNDTRIP"
    }
    Write-JsonAtomic $receipt $ReceiptPath
    Protect-LocalFile $ReceiptPath

    Write-Host "BCP_NEXUS_BOOTSTRAP=PASS"
    Write-Host ("Nexus: " + $nexusUrl)
    Write-Host "Telegram receiver: WEBHOOK_SINGLE_OWNER"
    Write-Host "PC transport: NEXUS"
    Write-Host 'Spend: $0.00'
    Write-Host "Final human field check: send /status once in BCP Cockpit while the PC remains on home Wi-Fi."
} catch {
    if ($webhookApplied) {
        try { Invoke-Telegram $token "deleteWebhook" @{ drop_pending_updates = $false } 20 | Out-Null } catch {}
        try { & $configurator -Direct | Out-Null } catch {}
    }
    throw
} finally {
    $deviceToken = $null
    $webhookSecret = $null
    $token = $null
}
