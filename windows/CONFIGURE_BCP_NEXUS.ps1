param(
  [string]$NexusUrl = "",
  [string]$DeviceId = "pc-worker",
  [SecureString]$DeviceToken,
  [switch]$Direct,
  [switch]$SelfTest
)

$ErrorActionPreference = "Stop"

function Convert-SecureToPlain([SecureString]$Value) {
  if ($null -eq $Value) { return "" }
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
  try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

function Write-AtomicUtf8([string]$Path, [string]$Text) {
  $dir = Split-Path -Parent $Path
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  $tmp = $Path + ".tmp"
  [IO.File]::WriteAllText($tmp, $Text, (New-Object Text.UTF8Encoding($false)))
  Move-Item -LiteralPath $tmp -Destination $Path -Force
}

function Protect-LocalFile([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return }
  $user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
  $aclGrant = $user + ":(R,W)"
  & icacls.exe $Path /inheritance:r /grant:r $aclGrant /c | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "LOCAL_SECRET_ACL_HARDENING_FAILED" }
}

function Set-JsonProperty($Object, [string]$Name, $Value) {
  if ($Object.PSObject.Properties.Name -contains $Name) {
    $Object.$Name = $Value
  } else {
    $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
  }
}

if ($SelfTest) {
  $x = [pscustomobject]@{ allowed_chat_id = 123; transport = [pscustomobject]@{ mode = "DIRECT_TELEGRAM" } }
  Set-JsonProperty $x "transport" ([pscustomobject]@{ mode = "NEXUS"; nexus_url = "https://example.workers.dev"; device_id = "pc-worker"; poll_seconds = 15 })
  if ($x.transport.mode -ne "NEXUS") { throw "SELFTEST_MODE" }
  if (-not $x.transport.nexus_url.StartsWith("https://")) { throw "SELFTEST_HTTPS" }
  Write-Output "BCP_NEXUS_CONFIG_SELFTEST=PASS"
  exit 0
}

$local = [Environment]::GetFolderPath("LocalApplicationData")
$root = Join-Path $local "ChatGPT_ManagedApps\bcp"
$state = Join-Path $root "state"
$configPath = Join-Path $state "telegram_observability.json"
$tokenPath = Join-Path $state "nexus_device_token.txt"

if (-not (Test-Path $configPath)) {
  throw "BCP_TELEGRAM_CONFIG_NOT_FOUND"
}

$config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json

if ($Direct) {
  Set-JsonProperty $config "transport" ([pscustomobject]@{ mode = "DIRECT_TELEGRAM" })
  Write-AtomicUtf8 $configPath (($config | ConvertTo-Json -Depth 12) + [Environment]::NewLine)
  Protect-LocalFile $configPath
  Write-Output "BCP_TRANSPORT=DIRECT_TELEGRAM"
  exit 0
}

if ([string]::IsNullOrWhiteSpace($NexusUrl) -or -not $NexusUrl.StartsWith("https://")) {
  throw "NEXUS_HTTPS_URL_REQUIRED"
}
if ([string]::IsNullOrWhiteSpace($DeviceId)) {
  throw "NEXUS_DEVICE_ID_REQUIRED"
}

$plain = Convert-SecureToPlain $DeviceToken
if ([string]::IsNullOrWhiteSpace($plain)) {
  if (-not (Test-Path $tokenPath)) {
    throw "NEXUS_DEVICE_TOKEN_REQUIRED_OR_PREPROVISIONED"
  }
  $plain = (Get-Content -Raw -LiteralPath $tokenPath).Trim()
}
if ($plain.Length -lt 24) {
  throw "NEXUS_DEVICE_TOKEN_TOO_SHORT"
}

Write-AtomicUtf8 $tokenPath ($plain + [Environment]::NewLine)
Protect-LocalFile $tokenPath
Set-JsonProperty $config "transport" ([pscustomobject]@{
  mode = "NEXUS"
  nexus_url = $NexusUrl.TrimEnd("/")
  device_id = $DeviceId
  poll_seconds = 15
})
Write-AtomicUtf8 $configPath (($config | ConvertTo-Json -Depth 12) + [Environment]::NewLine)
Protect-LocalFile $configPath

Write-Output "BCP_TRANSPORT=NEXUS"
Write-Output ("BCP_NEXUS_URL=" + $NexusUrl.TrimEnd("/"))
Write-Output ("BCP_NEXUS_DEVICE_ID=" + $DeviceId)
Write-Output "BCP_NEXUS_SECRET=LOCAL_ONLY"
