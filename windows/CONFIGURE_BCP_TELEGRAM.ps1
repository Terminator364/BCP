param(
    [switch]$SelfTest,
    [switch]$Disable
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Windows PowerShell 5.1 can inherit legacy TLS defaults on some machines.
# Force TLS 1.2 for Telegram HTTPS without changing any system-wide setting.
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch {
    throw "TELEGRAM_TLS12_INITIALIZATION_FAILED"
}

$AppRoot = Join-Path $env:LOCALAPPDATA "ChatGPT_ManagedApps\bcp"
$StateDir = Join-Path $AppRoot "state"
$LogsDir = Join-Path $AppRoot "logs"
$InstalledBot = Join-Path $AppRoot "telegram_observability.py"
$TokenPath = Join-Path $StateDir "telegram_bot_token.txt"
$ConfigPath = Join-Path $StateDir "telegram_observability.json"
$ReceiptPath = Join-Path $StateDir "telegram_setup_receipt.json"
$SourceBot = Join-Path (Split-Path -Parent $PSCommandPath) "bcp_telegram_observability.py"
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$RunName = "BlessingControlPlaneTelegram"

function UtcNow { [DateTime]::UtcNow.ToString("o") }

function Write-JsonAtomic($Object, [string]$Path) {
    $dir = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $tmp = Join-Path $dir (".tmp-" + [Guid]::NewGuid().ToString("N") + ".json")
    try {
        $json = $Object | ConvertTo-Json -Depth 16
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($tmp, $json, $utf8)
        Move-Item -Force -LiteralPath $tmp -Destination $Path
    } finally {
        Remove-Item -Force -LiteralPath $tmp -ErrorAction SilentlyContinue
    }
}

function Protect-LocalFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return }
    $user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $aclGrant = $user + ":(R,W)"
    & icacls.exe $Path /inheritance:r /grant:r $aclGrant /c | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "LOCAL_SECRET_ACL_HARDENING_FAILED" }
}

function Convert-SecureToPlain([Security.SecureString]$Secure) {
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

function Invoke-Telegram([string]$Token, [string]$Method, $Body, [int]$TimeoutSec = 20) {
    $uri = "https://api.telegram.org/bot" + $Token + "/" + $Method
    $attempts = 3
    for ($attempt = 1; $attempt -le $attempts; $attempt++) {
        try {
            return Invoke-RestMethod -Method Post -Uri $uri -ContentType "application/json" -Body ($Body | ConvertTo-Json -Compress -Depth 12) -TimeoutSec $TimeoutSec
        } catch [System.Net.WebException] {
            $ex = $_.Exception
            $response = $ex.Response
            if ($response) {
                $http = $null
                try { $http = [int]$response.StatusCode } catch {}
                $apiCode = $null
                $apiDescription = $null
                try {
                    $stream = $response.GetResponseStream()
                    $reader = New-Object System.IO.StreamReader($stream)
                    try {
                        $payload = $reader.ReadToEnd()
                        if ($payload) {
                            $parsed = $payload | ConvertFrom-Json -ErrorAction SilentlyContinue
                            if ($parsed) {
                                $apiCode = $parsed.error_code
                                $apiDescription = [string]$parsed.description
                            }
                        }
                    } finally {
                        if ($reader) { $reader.Dispose() }
                        if ($stream) { $stream.Dispose() }
                    }
                } catch {}
                $safe = "TELEGRAM_API_HTTP_ERROR method=" + $Method
                if ($http) { $safe += " http=" + $http }
                if ($apiCode) { $safe += " api_code=" + $apiCode }
                if ($apiDescription) { $safe += " description=" + $apiDescription }
                throw $safe
            }

            $status = [string]$ex.Status
            if (-not $status) { $status = "UNKNOWN_WEBEXCEPTION" }

            if ($attempt -lt $attempts -and $status -in @(
                "ConnectFailure",
                "ConnectionClosed",
                "KeepAliveFailure",
                "NameResolutionFailure",
                "PipelineFailure",
                "ProxyNameResolutionFailure",
                "ReceiveFailure",
                "SecureChannelFailure",
                "SendFailure",
                "Timeout",
                "TrustFailure",
                "UnknownError"
            )) {
                $delay = 2 * $attempt
                Write-Host ("Telegram transport retry " + $attempt + "/" + $attempts + " after " + $status + " (" + $delay + "s)")
                Start-Sleep -Seconds $delay
                continue
            }
            throw ("TELEGRAM_API_TRANSPORT_FAILED method=" + $Method + " status=" + $status + " attempts=" + $attempt)
        } catch {
            $kind = $_.Exception.GetType().Name
            throw ("TELEGRAM_API_CALL_FAILED method=" + $Method + " class=" + $kind)
        }
    }
}

function Find-Python {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Tunnel_PC_G4\runtime\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe")
    )
    foreach ($p in $candidates) {
        if (Test-Path -LiteralPath $p -PathType Leaf) { return $p }
    }
    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "PYTHON_RUNTIME_NOT_FOUND"
}

function Stop-ExistingBot {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            ([string]$_.CommandLine -match "telegram_observability\.py") -and
            ([string]$_.Name -match "(?i)python")
        } |
        ForEach-Object {
            Stop-Process -Id ([int]$_.ProcessId) -Force -ErrorAction SilentlyContinue
        }
}

if ($SelfTest) {
    if (-not (Test-Path -LiteralPath $SourceBot -PathType Leaf)) {
        throw "SELFTEST_BOT_SOURCE_MISSING"
    }
    $raw = Get-Content -Raw -LiteralPath $SourceBot -Encoding UTF8
    foreach ($required in @(
        "OBSERVED_CHAT_ACTION",
        "CHAT_WAITING",
        "CHAT_PLATFORM_HOLD_REPORTED",
        "UNKNOWN_INTERNAL_CHAT_STATE",
        '"/status"',
        '"/project"',
        '"/job"',
        '"/last"',
        '"/ci"',
        '"/holds"',
        "getUpdates"
    )) {
        if ($raw -notmatch [regex]::Escape($required)) {
            throw ("SELFTEST_REQUIRED_CONTRACT_MISSING " + $required)
        }
    }
    if ($raw -match '\b\d{6,12}:[A-Za-z0-9_-]{20,}\b') {
        throw "SELFTEST_HARDCODED_TELEGRAM_TOKEN_DETECTED"
    }
    if ($raw -match '(?i)import\s+(requests|telegram|telebot|aiohttp)') {
        throw "SELFTEST_UNEXPECTED_HEAVY_DEPENDENCY"
    }
    Write-Host "BCP_TELEGRAM_CONFIGURATOR_SELFTEST=PASS"
    exit 0
}

if ($Disable) {
    Stop-ExistingBot
    if (Test-Path $RunKey) {
        Remove-ItemProperty -Path $RunKey -Name $RunName -ErrorAction SilentlyContinue
    }
    Write-Host "BCP Telegram startup disabled. Local secret/config were preserved."
    exit 0
}

if (-not (Test-Path -LiteralPath $SourceBot -PathType Leaf)) {
    throw "BOT_SOURCE_MISSING"
}

$Python = Find-Python
New-Item -ItemType Directory -Force -Path $AppRoot,$StateDir,$LogsDir | Out-Null

Write-Host ""
Write-Host "BCP Telegram Observability MVP - local secret setup"
Write-Host "The BotFather token will stay on this PC only."
Write-Host "Do NOT paste it into ChatGPT, GitHub, Drive, source files, issues, or PRs."
Write-Host ""

$secure = $null
$token = $null
if (Test-Path -LiteralPath $TokenPath -PathType Leaf) {
    try {
        $existingToken = ([System.IO.File]::ReadAllText($TokenPath)).Trim()
        if ($existingToken -match '^\d{6,12}:[A-Za-z0-9_-]{20,}$') {
            $token = $existingToken
            Write-Host "Reusing previously verified local BotFather token. No copy/paste needed."
        }
    } catch {}
}
if (-not $token) {
    $secure = Read-Host "Paste the BotFather token here locally" -AsSecureString
    $token = Convert-SecureToPlain $secure
}
try {
    if ($token -notmatch '^\d{6,12}:[A-Za-z0-9_-]{20,}$') {
        throw "TELEGRAM_TOKEN_FORMAT_INVALID"
    }

    $me = Invoke-Telegram $token "getMe" @{} 20
    if (-not $me.ok -or -not $me.result.username) {
        throw "TELEGRAM_GETME_FAILED"
    }
    $username = [string]$me.result.username

    $webhook = Invoke-Telegram $token "getWebhookInfo" @{} 20
    if ($webhook.ok -and [string]$webhook.result.url) {
        throw "TELEGRAM_WEBHOOK_ALREADY_CONFIGURED_REFUSING_TO_OVERRIDE"
    }

    $existingChatId = [int64]0
    if (Test-Path -LiteralPath $ConfigPath -PathType Leaf) {
        try {
            $existingConfig = Get-Content -Raw -LiteralPath $ConfigPath -Encoding UTF8 | ConvertFrom-Json
            if ($existingConfig -and $existingConfig.allowed_chat_id) {
                $existingChatId = [int64]$existingConfig.allowed_chat_id
            }
        } catch {}
    }

    Copy-Item -Force -LiteralPath $SourceBot -Destination $InstalledBot
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($TokenPath, $token + [Environment]::NewLine, $utf8)
    Protect-LocalFile $TokenPath

    Write-Host ""
    Write-Host ("Bot verified: @" + $username)
    Write-Host ("Open Telegram -> @" + $username + " -> Start, then send /status.")
    Write-Host "BCP will detect only a PRIVATE chat. No chat ID copy/paste is needed."
    Write-Host ""

    $chatId = [int64]0
    if ($existingChatId -ne 0) {
        $chatId = $existingChatId
        Write-Host "Reusing previously authorized PRIVATE Telegram chat. No new /start, /status, or YES confirmation is needed."
    } else {
        # Only one Telegram getUpdates consumer may exist per bot token.
        # Stop any previously installed local worker before the first-time authorization poll.
        Stop-ExistingBot

        $nextOffset = 0
        $candidate = $null
        $deadline = [DateTime]::UtcNow.AddMinutes(10)
        while ([DateTime]::UtcNow -lt $deadline -and -not $candidate) {
            $updates = Invoke-Telegram $token "getUpdates" @{
                offset = $nextOffset
                timeout = 20
                allowed_updates = @("message")
            } 30
            foreach ($update in @($updates.result)) {
                $uid = [int64]$update.update_id
                if ($uid -ge $nextOffset) { $nextOffset = $uid + 1 }
                if ($update.message -and $update.message.chat -and [string]$update.message.chat.type -eq "private") {
                    $candidate = $update.message
                }
            }
        }
        if (-not $candidate) {
            throw "HUMAN_GATE_NO_PRIVATE_TELEGRAM_MESSAGE_OBSERVED_RESUMABLE"
        }

        $chatId = [int64]$candidate.chat.id
        $firstName = ""
        $lastName = ""
        $tgUser = ""
        if ($candidate.from -and ($candidate.from.PSObject.Properties.Name -contains "first_name")) {
            $firstName = [string]$candidate.from.first_name
        }
        if ($candidate.from -and ($candidate.from.PSObject.Properties.Name -contains "last_name")) {
            $lastName = [string]$candidate.from.last_name
        }
        if ($candidate.from -and ($candidate.from.PSObject.Properties.Name -contains "username")) {
            $tgUser = [string]$candidate.from.username
        }
        $display = ($firstName + " " + $lastName).Trim()
        if (-not $display) { $display = "(no display name)" }
        if ($tgUser) {
            Write-Host ("Detected private Telegram identity: " + $display + " @" + $tgUser)
        } else {
            Write-Host ("Detected private Telegram identity: " + $display + " (no username)")
        }
        $confirm = Read-Host "Authorize this PRIVATE chat for READ-ONLY BCP observability? Type YES"
        if ($confirm -ne "YES") {
            throw "HUMAN_GATE_CHAT_ID_NOT_AUTHORIZED"
        }
    }

    $config = [ordered]@{
        schema = "bcp.telegram_observability_config/1"
        mode = "READ_ONLY"
        allowed_chat_id = $chatId
        default_project = "API/BCP"
        github_repo = "Terminator364/BCP"
        writer_branch = ""
        polling = [ordered]@{
            transport = "TELEGRAM_LONG_POLL"
            timeout_seconds = 50
            aggressive_polling = $false
        }
        presence = [ordered]@{
            auto_push = $true
            max_events_per_push = 6
            waiting_heartbeat_seconds = 300
            replay_old_backlog = $false
        }
        budget = [ordered]@{
            paid_spend_usd = 0.0
            auto_billing = $false
        }
        configured_at = UtcNow
    }
    Write-JsonAtomic $config $ConfigPath
    Protect-LocalFile $ConfigPath

    & $Python $InstalledBot --selftest
    if ($LASTEXITCODE -ne 0) { throw "BOT_SELFTEST_FAILED" }

    Stop-ExistingBot
    New-Item -ItemType Directory -Force -Path $RunKey | Out-Null
    $runCommand = '"' + $Python + '" "' + $InstalledBot + '"'
    Set-ItemProperty -Path $RunKey -Name $RunName -Value $runCommand

    $proc = Start-Process -FilePath $Python -ArgumentList @($InstalledBot) -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 2
    if ($proc.HasExited) { throw "BOT_PROCESS_EXITED_EARLY" }

    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        $chatHashBytes = $sha256.ComputeHash([Text.Encoding]::UTF8.GetBytes([string]$chatId))
    } finally {
        $sha256.Dispose()
    }
    $chatHash = ([BitConverter]::ToString($chatHashBytes)).Replace("-", "").ToLowerInvariant().Substring(0,16)

    $receipt = [ordered]@{
        schema = "bcp.telegram_setup_receipt/1"
        status = "CONFIGURED"
        bot_username = $username
        allowed_chat_id_sha256_prefix = $chatHash
        token_stored = "LOCAL_ONLY"
        token_logged = $false
        startup = "HKCU_RUN"
        python = $Python
        process_id = $proc.Id
        configured_at = UtcNow
        spend_usd = 0.0
        field_gate = "KINSHASA_LIVE_MESSAGE_PENDING"
    }
    Write-JsonAtomic $receipt $ReceiptPath

    Invoke-Telegram $token "sendMessage" @{
        chat_id = $chatId
        text = 'BCP Telegram Observability MVP connecté. Mode READ-ONLY. Teste /status, /ci et /holds. Spend: $0.00'
        disable_web_page_preview = $true
    } 20 | Out-Null

    Write-Host ""
    Write-Host "BCP_TELEGRAM_LOCAL_SETUP=PASS"
    Write-Host ("Bot: @" + $username)
    Write-Host "Mode: READ_ONLY"
    Write-Host 'Spend: $0.00'
    Write-Host "Final field gate: verify that /status replies over your normal Kinshasa connection."
} finally {
    $token = $null
    $secure = $null
}
