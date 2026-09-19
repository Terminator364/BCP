param(
    [switch]$SelfTest,
    [switch]$Disable
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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
    try {
        return Invoke-RestMethod -Method Post -Uri $uri -ContentType "application/json" -Body ($Body | ConvertTo-Json -Compress -Depth 12) -TimeoutSec $TimeoutSec
    } catch {
        $kind = $_.Exception.GetType().Name
        throw ("TELEGRAM_API_CALL_FAILED method=" + $Method + " class=" + $kind)
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

$secure = Read-Host "Paste the BotFather token here locally" -AsSecureString
$token = Convert-SecureToPlain $secure
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

    Copy-Item -Force -LiteralPath $SourceBot -Destination $InstalledBot
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($TokenPath, $token + [Environment]::NewLine, $utf8)
    Protect-LocalFile $TokenPath

    Write-Host ""
    Write-Host ("Bot verified: @" + $username)
    Write-Host ("Open Telegram -> @" + $username + " -> Start, then send /status.")
    Write-Host "BCP will detect only a PRIVATE chat. No chat ID copy/paste is needed."
    Write-Host ""

    $nextOffset = 0
    $candidate = $null
    $deadline = [DateTime]::UtcNow.AddMinutes(3)
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
        throw "HUMAN_GATE_NO_PRIVATE_TELEGRAM_MESSAGE_OBSERVED"
    }

    $chatId = [int64]$candidate.chat.id
    $display = ([string]$candidate.from.first_name + " " + [string]$candidate.from.last_name).Trim()
    $tgUser = [string]$candidate.from.username
    Write-Host ("Detected private Telegram identity: " + $display + " @" + $tgUser)
    $confirm = Read-Host "Authorize this PRIVATE chat for READ-ONLY BCP observability? Type YES"
    if ($confirm -ne "YES") {
        throw "HUMAN_GATE_CHAT_ID_NOT_AUTHORIZED"
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

    $chatHash = [Convert]::ToHexString(
        [Security.Cryptography.SHA256]::HashData(
            [Text.Encoding]::UTF8.GetBytes([string]$chatId)
        )
    ).ToLowerInvariant().Substring(0,16)

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
