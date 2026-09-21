param()
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$StateDir = Join-Path $env:LOCALAPPDATA "ChatGPT_ManagedApps\bcp\state"
$TokenPath = Join-Path $StateDir "bcp_token.txt"
$Endpoint = "http://127.0.0.1:8765/v1/system/nexus/retry-auth"

if (-not (Test-Path -LiteralPath $TokenPath -PathType Leaf)) {
    Write-Host "HOLD BCP_TOKEN_MISSING"
    exit 20
}

$token = (Get-Content -Raw -LiteralPath $TokenPath).Trim()
if ([string]::IsNullOrWhiteSpace($token)) {
    Write-Host "HOLD BCP_TOKEN_EMPTY"
    exit 20
}

$headers = @{ Authorization = ("Bearer " + $token) }
$body = @{ confirm = $true } | ConvertTo-Json -Compress

try {
    $result = Invoke-RestMethod -Uri $Endpoint -Method Post -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec 12
} catch {
    Write-Host ("HOLD NEXUS_RETRY_REQUEST_FAILED :: " + $_.Exception.Message)
    exit 20
}

$json = $result | ConvertTo-Json -Depth 8 -Compress
Write-Host $json

$status = [string]$result.result
if ($status -eq "LAUNCHED") {
    Write-Host "NEXUS_FRESH_DEVICE_FLOW_STARTED"
    exit 0
}
if ($status -eq "NETWORK_RECOVERY_PENDING") {
    Write-Host "NEXUS_NETWORK_RECOVERY_PENDING :: aucune action requise, BCP retente automatiquement quand le reseau/DNS revient"
    exit 0
}
if ($status -eq "NO_HUMAN_AUTH_RETRY_NEEDED" -or $status -eq "ALREADY_CONFIGURED") {
    Write-Host ("NEXUS_NO_RETRY_NEEDED :: " + $status + " :: aucune action manuelle necessaire")
    exit 0
}

Write-Host ("HOLD NEXUS_UNEXPECTED_RESULT :: " + $status)
exit 20
