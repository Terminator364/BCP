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
$ManagedToolsRoot = Join-Path $AppRoot "toolchains"
$NodeVersion = "24.21.0"
$NodeArchiveName = "node-v24.21.0-win-x64.zip"
$NodeArchiveUrl = "https://nodejs.org/download/release/v24.21.0/node-v24.21.0-win-x64.zip"
$NodeArchiveSha256 = "158f7685b44de51f6c0df1d153526cbcd3e1bc739a8dfc607721cef75de9e541"
$WranglerVersion = "4.135.0"
$script:ManagedRuntimeFailure = ""

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

function Get-SafeFailureDetail([string]$Value) {
    $safe = ([string]$Value -replace '\b\d{6,12}:[A-Za-z0-9_-]{20,}\b', '<REDACTED_TELEGRAM_TOKEN>')
    $safe = ($safe -replace '(?i)(Bearer\s+)[A-Za-z0-9._~+/-]{12,}', '$1<REDACTED>')
    $safe = ($safe -replace '[\r\n\t]+', ' ')
    $safe = ($safe -replace '[^A-Za-z0-9_: .\\/()\[\]-]', '_')
    if ($safe.Length -gt 240) { $safe = $safe.Substring(0, 240) }
    return $safe
}

function Write-RuntimePrepReceipt([string]$Status, [string]$ErrorClass, [string]$Stage, [string]$Detail) {
    $receipt = [ordered]@{
        schema = "bcp.nexus_bootstrap_receipt/1"
        status = $Status
        error_class = (Get-SafeFailureDetail $ErrorClass)
        error_detail = (Get-SafeFailureDetail $Detail)
        stage = (Get-SafeFailureDetail $Stage)
        retryable = $true
        failed_at = UtcNow
        spend_policy = "ZERO_USD"
        spend_usd = 0.0
    }
    Write-JsonAtomic $receipt $ReceiptPath
    Protect-LocalFile $ReceiptPath
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

function Get-FileSha256([string]$Path) {
    return ([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([IO.File]::ReadAllBytes($Path)))).Replace("-","").ToLowerInvariant()
}

function Invoke-ResilientDownload([string]$Uri, [string]$Destination) {
    $partial = $Destination + ".partial"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
    for ($attempt = 1; $attempt -le 4; $attempt++) {
        Remove-Item -Force -LiteralPath $partial -ErrorAction SilentlyContinue
        try {
            $bits = Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue
            if ($bits) {
                Start-BitsTransfer -Source $Uri -Destination $partial -DisplayName "BCP managed runtime" -Description "BCP Nexus portable runtime" -ErrorAction Stop
            } else {
                Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $partial -TimeoutSec 120
            }
            if (-not (Test-Path -LiteralPath $partial -PathType Leaf)) { throw "DOWNLOAD_FILE_MISSING" }
            Move-Item -Force -LiteralPath $partial -Destination $Destination
            return
        } catch {
            Remove-Item -Force -LiteralPath $partial -ErrorAction SilentlyContinue
            if ($attempt -ge 4) { throw }
            Start-Sleep -Seconds ([Math]::Min(30, [Math]::Pow(2, $attempt + 1)))
        }
    }
}

function Ensure-ManagedWranglerLauncher {
    $toolRoot = Join-Path $ManagedToolsRoot ("wrangler-" + $WranglerVersion)
    $nodeHome = Join-Path $toolRoot ("node-v" + $NodeVersion + "-win-x64")
    $npx = Join-Path $nodeHome "npx.cmd"
    if (-not (Test-Path -LiteralPath $npx -PathType Leaf)) {
        New-Item -ItemType Directory -Force -Path $toolRoot | Out-Null
        $archive = Join-Path $toolRoot $NodeArchiveName
        if (Test-Path -LiteralPath $archive -PathType Leaf) {
            if ((Get-FileSha256 $archive) -ne $NodeArchiveSha256) {
                Remove-Item -Force -LiteralPath $archive
            }
        }
        if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
            Write-Host ("BCP Nexus: downloading portable Node.js " + $NodeVersion + " once...")
            Invoke-ResilientDownload $NodeArchiveUrl $archive
        }
        if ((Get-FileSha256 $archive) -ne $NodeArchiveSha256) {
            Remove-Item -Force -LiteralPath $archive -ErrorAction SilentlyContinue
            throw "MANAGED_NODE_SHA256_MISMATCH"
        }

        $extractRoot = Join-Path $toolRoot ("extract-" + [Guid]::NewGuid().ToString("N"))
        try {
            Expand-Archive -LiteralPath $archive -DestinationPath $extractRoot -Force
            $candidate = Join-Path $extractRoot ("node-v" + $NodeVersion + "-win-x64")
            if (-not (Test-Path -LiteralPath (Join-Path $candidate "npx.cmd") -PathType Leaf)) {
                throw "MANAGED_NODE_ARCHIVE_LAYOUT_INVALID"
            }
            Remove-Item -Recurse -Force -LiteralPath $nodeHome -ErrorAction SilentlyContinue
            Move-Item -LiteralPath $candidate -Destination $nodeHome
        } finally {
            Remove-Item -Recurse -Force -LiteralPath $extractRoot -ErrorAction SilentlyContinue
        }
    }

    $npmCache = Join-Path $AppRoot "cache\npm"
    New-Item -ItemType Directory -Force -Path $npmCache | Out-Null
    $env:NPM_CONFIG_CACHE = $npmCache
    $env:NPM_CONFIG_AUDIT = "false"
    $env:NPM_CONFIG_FUND = "false"
    $env:NPM_CONFIG_UPDATE_NOTIFIER = "false"
    $env:NPM_CONFIG_FETCH_RETRIES = "5"
    $env:NPM_CONFIG_FETCH_RETRY_MINTIMEOUT = "2000"
    $env:NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT = "30000"
    $env:NPM_CONFIG_FETCH_TIMEOUT = "120000"
    $env:NPM_CONFIG_PREFER_OFFLINE = "true"
    return [pscustomobject]@{ File = $npx; Prefix = @("--yes", ("wrangler@" + $WranglerVersion)); Managed = $true }
}

function Find-WranglerLauncher {
    foreach ($name in @("npx.cmd","npx.exe","npx")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            $env:NPM_CONFIG_AUDIT = "false"
            $env:NPM_CONFIG_FUND = "false"
            $env:NPM_CONFIG_UPDATE_NOTIFIER = "false"
            $env:NPM_CONFIG_FETCH_RETRIES = "5"
            $env:NPM_CONFIG_FETCH_RETRY_MINTIMEOUT = "2000"
            $env:NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT = "30000"
    $env:NPM_CONFIG_FETCH_TIMEOUT = "120000"
    $env:NPM_CONFIG_PREFER_OFFLINE = "true"
            return [pscustomobject]@{ File = $cmd.Source; Prefix = @("--yes", ("wrangler@" + $WranglerVersion)); Managed = $false }
        }
    }
    foreach ($name in @("wrangler.cmd","wrangler.exe","wrangler")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return [pscustomobject]@{ File = $cmd.Source; Prefix = @(); Managed = $false } }
    }
    try {
        return Ensure-ManagedWranglerLauncher
    } catch {
        $script:ManagedRuntimeFailure = Get-SafeFailureDetail ([string]$_.Exception.Message)
        Write-Host ("BCP_NEXUS_MANAGED_RUNTIME_DEFERRED=" + $script:ManagedRuntimeFailure)
        return $null
    }
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

function Classify-WranglerProbeFailure($Probe) {
    if (-not $Probe) { return "WRANGLER_RUNTIME_PROBE_FAILED" }
    $raw = [string]$Probe.Text
    if ($raw -match '(?i)ENOTFOUND|EAI_AGAIN|ETIMEDOUT|ECONNRESET|ECONNREFUSED|ENETUNREACH|network|registry\\.npmjs\\.org') {
        return "NPM_NETWORK_OR_REGISTRY_UNAVAILABLE"
    }
    if ($raw -match '(?i)CERT_|SELF_SIGNED_CERT|UNABLE_TO_VERIFY_LEAF_SIGNATURE|certificate') {
        return "NPM_TLS_CERTIFICATE_FAILURE"
    }
    if ($raw -match '(?i)EPERM|EACCES|permission denied|access is denied') {
        return "NPM_CACHE_PERMISSION_FAILURE"
    }
    if ($raw -match '(?i)not recognized|cannot find|MODULE_NOT_FOUND') {
        return "MANAGED_NPX_OR_WRANGLER_LAUNCH_FAILURE"
    }
    return "WRANGLER_RUNTIME_PROBE_FAILED"
}

function Get-WranglerProbeDetail($Probe) {
    if (-not $Probe) { return "No probe result captured." }
    $exitCode = [int]$Probe.ExitCode
    $safeText = Get-SafeFailureDetail ([string]$Probe.Text)
    if (-not $safeText) { $safeText = "no stdout/stderr captured" }
    return Get-SafeFailureDetail ("WRANGLER_PROBE_EXIT=" + $exitCode + " " + $safeText)
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
    foreach ($required in @("CLOUDFLARE_LOGIN_REQUIRED","TELEGRAM_BOT_TOKEN","TELEGRAM_WEBHOOK_SECRET","BCP_DEVICE_TOKEN","ALLOWED_CHAT_ID","--remote","setWebhook","CONFIGURE_BCP_NEXUS","WRANGLER_OUTPUT_FILE_PATH","nexus_bootstrap_receipt.json","24.21.0","4.135.0","MANAGED_NODE_SHA256_MISMATCH","NPM_CONFIG_FETCH_RETRIES","NPM_CONFIG_PREFER_OFFLINE","RUNTIME_PREP_DEFERRED","error_detail","MANAGED_RUNTIME_DOWNLOAD_OR_EXTRACT","WRANGLER_PROBE_EXIT","NPM_NETWORK_OR_REGISTRY_UNAVAILABLE")) {
        if ($raw -notmatch [regex]::Escape($required)) { throw ("SELFTEST_CONTRACT_MISSING " + $required) }
    }
    if ($raw -match '\b\d{6,12}:[A-Za-z0-9_-]{20,}\b') { throw "SELFTEST_HARDCODED_TELEGRAM_TOKEN" }
    Write-Host "BCP_NEXUS_BOOTSTRAP_SELFTEST=PASS"
    exit 0
}

trap {
    $rawError = [string]$_.Exception.Message
    $safeError = ($rawError -replace '[^A-Za-z0-9_: .-]', '_')
    if ($safeError.Length -gt 180) { $safeError = $safeError.Substring(0, 180) }
    $failureStatus = "NEXUS_BOOTSTRAP_FAILED"
    if ($safeError -match '^CLOUDFLARE_BROWSER_AUTHORIZATION_FAILED_OR_CANCELLED' -or $safeError -match '^CLOUDFLARE_AUTHORIZATION_NOT_CONFIRMED') {
        $failureStatus = "HUMAN_AUTH_REQUIRED"
    }
    $failure = [ordered]@{
        schema = "bcp.nexus_bootstrap_receipt/1"
        status = $failureStatus
        error_class = $safeError
        failed_at = UtcNow
        spend_policy = "ZERO_USD"
        spend_usd = 0.0
    }
    try {
        Write-JsonAtomic $failure $ReceiptPath
        Protect-LocalFile $ReceiptPath
    } catch {}
    Write-Host ("BCP_NEXUS_BOOTSTRAP_FAILURE=" + $failureStatus + " " + $safeError)
    exit 4
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
    $detail = $script:ManagedRuntimeFailure
    if (-not $detail) { $detail = "Managed Node/Wrangler launcher unavailable after bounded preparation." }
    try { Write-RuntimePrepReceipt "RUNTIME_PREP_DEFERRED" "WRANGLER_RUNTIME_REQUIRED" "MANAGED_RUNTIME_DOWNLOAD_OR_EXTRACT" $detail } catch {}
    Write-Host "BCP_NEXUS_HUMAN_GATE=WRANGLER_RUNTIME_REQUIRED"
    Write-Host ("BCP_NEXUS_RUNTIME_DETAIL=" + (Get-SafeFailureDetail $detail))
    Write-Host "Managed portable Node/Wrangler could not finish yet. BCP will re-stage on the next qualified bundle revision; no manual Node/Wrangler install or Telegram token copy is required."
    exit 3
}

$runtimeReady = $false
$lastProbe = $null
for ($attempt = 1; $attempt -le 3; $attempt++) {
    $probe = Invoke-Wrangler $launcher @("--version") -AllowFailure
    $lastProbe = $probe
    if ($probe.ExitCode -eq 0) {
        $runtimeReady = $true
        break
    }
    if ($attempt -lt 3) { Start-Sleep -Seconds ([Math]::Min(20, [Math]::Pow(2, $attempt + 1))) }
}
if (-not $runtimeReady) {
    $probeClass = Classify-WranglerProbeFailure $lastProbe
    $probeDetail = Get-WranglerProbeDetail $lastProbe
    try { Write-RuntimePrepReceipt "RUNTIME_PROBE_FAILED" $probeClass "WRANGLER_VERSION_PROBE" $probeDetail } catch {}
    Write-Host "BCP_NEXUS_HUMAN_GATE=WRANGLER_RUNTIME_REQUIRED"
    Write-Host ("BCP_NEXUS_RUNTIME_CLASS=" + $probeClass)
    Write-Host ("BCP_NEXUS_RUNTIME_DETAIL=" + $probeDetail)
    Write-Host "Pinned Wrangler is not ready yet. BCP preserved the bounded diagnostic and will use the managed retry/update path; no manual install, token re-entry, or ZIP shuttle is required."
    exit 3
}

$who = Invoke-Wrangler $launcher @("whoami","--json") -AllowFailure
if ($who.ExitCode -ne 0) {
    Write-Host "BCP_NEXUS_HUMAN_GATE=CLOUDFLARE_LOGIN_REQUIRED"
    Write-Host "One-time human gate: your browser will open for Cloudflare authorization."
    Write-Host "No Telegram token, chat ID, or device secret must be copied into chat."
    $login = Invoke-Wrangler $launcher @("login") -AllowFailure
    if ($login.ExitCode -ne 0) {
        throw "CLOUDFLARE_BROWSER_AUTHORIZATION_FAILED_OR_CANCELLED"
    }
    $who = Invoke-Wrangler $launcher @("whoami","--json") -AllowFailure
    if ($who.ExitCode -ne 0) {
        throw "CLOUDFLARE_AUTHORIZATION_NOT_CONFIRMED"
    }
    Write-Host "BCP_NEXUS_CLOUDFLARE_AUTH=PASS"
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
