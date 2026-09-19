param(
    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ExpectedPcVersion = "0.6.0"
$ExpectedEdgeVersionCode = 120
$ExpectedEdgeVersion = "1.2.0-evergreen"
$ExpectedPackage = "com.blessing.bcpedge.evergreen"
$ExpectedCertSha256 = "0baad4749918f1b2430bbbf3f5ddbdb1de4908b017910d67aef2cb987ddeb617"
$Port = 8765
$Root = Split-Path -Parent $PSCommandPath
$PcRoot = Join-Path $Root "PC"
$PhoneRoot = Join-Path $Root "PHONE"
$ProductManifestPath = Join-Path $Root "PRODUCT_MANIFEST.json"
$PhoneManifestPath = Join-Path $PhoneRoot "BCP_EDGE_CURRENT.json"
$PhoneApkPath = Join-Path $PhoneRoot "BCP_EDGE_CURRENT.apk"
$PcInstallerPath = Join-Path $PcRoot "INSTALL_BCP_FINAL.ps1"
$ManagedRoot = Join-Path $env:LOCALAPPDATA "ChatGPT_ManagedApps\bcp"
$TokenPath = Join-Path $ManagedRoot "state\bcp_token.txt"
$LocalEdgeRoot = Join-Path $ManagedRoot "edge_distribution"

function File-Sha256([string]$Path) {
    if(-not (Test-Path -LiteralPath $Path -PathType Leaf)){ throw "FILE_MISSING: $Path" }
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Read-Json([string]$Path) {
    if(-not (Test-Path -LiteralPath $Path -PathType Leaf)){ throw "JSON_MISSING: $Path" }
    return Get-Content -Raw -LiteralPath $Path -Encoding UTF8 | ConvertFrom-Json
}

function Write-JsonAtomic($Object,[string]$Path) {
    $dir=Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $tmp=Join-Path $dir (".tmp-"+[Guid]::NewGuid().ToString("N")+".json")
    try {
        [IO.File]::WriteAllText($tmp,($Object|ConvertTo-Json -Depth 20),[Text.UTF8Encoding]::new($false))
        Move-Item -Force -LiteralPath $tmp -Destination $Path
    } finally {
        Remove-Item -Force -LiteralPath $tmp -ErrorAction SilentlyContinue
    }
}

function Copy-FileAtomic([string]$Source,[string]$Destination) {
    $dir=Split-Path -Parent $Destination
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $tmp=Join-Path $dir (".tmp-"+[Guid]::NewGuid().ToString("N")+"-"+[IO.Path]::GetFileName($Destination))
    try {
        Copy-Item -Force -LiteralPath $Source -Destination $tmp
        if((File-Sha256 $tmp) -ne (File-Sha256 $Source)){ throw "ATOMIC_COPY_HASH_MISMATCH" }
        Move-Item -Force -LiteralPath $tmp -Destination $Destination
    } finally {
        Remove-Item -Force -LiteralPath $tmp -ErrorAction SilentlyContinue
    }
}

function Wait-BcpHealth([int]$Seconds=90) {
    $deadline=[DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        try {
            $h=Invoke-RestMethod -UseBasicParsing -Uri ("http://127.0.0.1:"+$Port+"/health") -TimeoutSec 2
            if($h.ok -eq $true -and [string]$h.version -eq $ExpectedPcVersion){ return $h }
        } catch {}
        Start-Sleep -Milliseconds 700
    } while([DateTime]::UtcNow -lt $deadline)
    throw "BCP_0_6_DID_NOT_BECOME_HEALTHY"
}

function Drive-InstallerRoots {
    $candidates=@(
        "G:\Mon Drive\API_BCP\00_A_INSTALLER",
        "G:\My Drive\API_BCP\00_A_INSTALLER",
        (Join-Path $HOME "Mon Drive\API_BCP\00_A_INSTALLER"),
        (Join-Path $HOME "My Drive\API_BCP\00_A_INSTALLER")
    )
    return @($candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Container } | Select-Object -Unique)
}

function Verify-ProductPayload {
    $product=Read-Json $ProductManifestPath
    $edge=Read-Json $PhoneManifestPath
    if([string]$product.pc_version -ne $ExpectedPcVersion){throw "PRODUCT_PC_VERSION_MISMATCH"}
    if([string]$product.edge_version -ne $ExpectedEdgeVersion){throw "PRODUCT_EDGE_VERSION_MISMATCH"}
    if([int]$edge.version_code -ne $ExpectedEdgeVersionCode){throw "EDGE_VERSION_CODE_MISMATCH"}
    if([string]$edge.version_name -ne $ExpectedEdgeVersion){throw "EDGE_VERSION_NAME_MISMATCH"}
    if([string]$edge.package_id -ne $ExpectedPackage){throw "EDGE_PACKAGE_MISMATCH"}
    if(([string]$edge.signing_cert_sha256).ToLowerInvariant() -ne $ExpectedCertSha256){throw "EDGE_CERT_CONTRACT_MISMATCH"}
    $apkSha=File-Sha256 $PhoneApkPath
    if($apkSha -ne ([string]$edge.apk_sha256).ToLowerInvariant()){throw "EDGE_APK_HASH_MISMATCH"}
    if($apkSha -ne ([string]$product.edge_apk_sha256).ToLowerInvariant()){throw "PRODUCT_APK_HASH_MISMATCH"}
    if((File-Sha256 $PcInstallerPath) -ne ([string]$product.pc_installer_sha256).ToLowerInvariant()){throw "PRODUCT_PC_INSTALLER_HASH_MISMATCH"}
    return [ordered]@{product=$product;edge=$edge;apk_sha256=$apkSha}
}

function Stage-EdgeUpdate($Verified) {
    New-Item -ItemType Directory -Force -Path $LocalEdgeRoot | Out-Null
    Copy-FileAtomic $PhoneApkPath (Join-Path $LocalEdgeRoot "BCP_EDGE_CURRENT.apk")
    Write-JsonAtomic $Verified.edge (Join-Path $LocalEdgeRoot "BCP_EDGE_CURRENT.json")

    # Drive is a mirror/distribution convenience, never a runtime dependency.
    foreach($root in (Drive-InstallerRoots)){
        try {
            Copy-FileAtomic $PhoneApkPath (Join-Path $root "BCP_EDGE_CURRENT.apk")
            Write-JsonAtomic $Verified.edge (Join-Path $root "BCP_EDGE_CURRENT.json")
        } catch {}
    }
}

function Verify-ServedEdgeUpdate($Verified) {
    if(-not (Test-Path -LiteralPath $TokenPath -PathType Leaf)){throw "BCP_TOKEN_MISSING_AFTER_INSTALL"}
    $token=(Get-Content -Raw -LiteralPath $TokenPath).Trim()
    $headers=@{Authorization=("Bearer "+$token)}
    $m=Invoke-RestMethod -UseBasicParsing -Uri ("http://127.0.0.1:"+$Port+"/v1/edge/update") -Headers $headers -TimeoutSec 5
    if($m.ok -ne $true){throw "EDGE_UPDATE_ENDPOINT_NOT_OK"}
    if([int]$m.version_code -ne $ExpectedEdgeVersionCode){throw "SERVED_EDGE_VERSION_MISMATCH"}
    if(([string]$m.apk_sha256).ToLowerInvariant() -ne $Verified.apk_sha256){throw "SERVED_EDGE_HASH_MISMATCH"}
    if(([string]$m.signing_cert_sha256).ToLowerInvariant() -ne $ExpectedCertSha256){throw "SERVED_EDGE_CERT_MISMATCH"}
}

function Write-ProductReceipt($Verified,$Health) {
    $receipt=[ordered]@{
        schema="bcp.coordinated_install/1"
        status="PC_PASS_EDGE_STAGED"
        installed_at=[DateTime]::UtcNow.ToString("o")
        pc_version=[string]$Health.version
        edge_version=$ExpectedEdgeVersion
        edge_version_code=$ExpectedEdgeVersionCode
        edge_apk_sha256=$Verified.apk_sha256
        next_physical_gate="ANDROID_OS_INSTALL_CONFIRMATION"
        automatic_phone_delivery="BCP_LOCAL_AUTHENTICATED_EDGE_UPDATE"
    }
    Write-JsonAtomic $receipt (Join-Path $ManagedRoot "receipts\PRODUCT_INSTALL_LATEST.json")
    foreach($root in (Drive-InstallerRoots)){
        try { Write-JsonAtomic $receipt (Join-Path $root "PRODUCT_INSTALL_LATEST.json") } catch {}
    }
}

if($SelfTest){
    $raw=Get-Content -Raw -LiteralPath $PSCommandPath -Encoding UTF8
    foreach($needle in @(
        "0.6.0","1.2.0-evergreen","BCP_EDGE_CURRENT.apk","edge_distribution",
        "PRODUCT_MANIFEST.json","ATOMIC_COPY_HASH_MISMATCH","/v1/edge/update",
        "ANDROID_OS_INSTALL_CONFIRMATION","Drive is a mirror/distribution convenience"
    )){
        if($raw -notmatch [regex]::Escape($needle)){throw ("PRODUCT_INSTALLER_SELFTEST_MISSING_"+$needle)}
    }
    Write-Host "BCP_COORDINATED_PRODUCT_INSTALLER_SELFTEST=PASS"
    exit 0
}

try {
    $verified=Verify-ProductPayload
    if(-not (Test-Path -LiteralPath $PcInstallerPath -PathType Leaf)){throw "PC_INSTALLER_MISSING"}
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $PcInstallerPath
    if($LASTEXITCODE -ne 0){throw ("PC_INSTALL_FAILED rc="+$LASTEXITCODE)}
    $health=Wait-BcpHealth 120
    Stage-EdgeUpdate $verified
    Verify-ServedEdgeUpdate $verified
    Write-ProductReceipt $verified $health
    Write-Host ""
    Write-Host "BCP PRODUCT 0.6.0 + B-EDGE 1.2.0 = PC OK / TELEPHONE PRÊT" -ForegroundColor Green
    Write-Host "Ouvre B-EDGE sur l'ancien téléphone. La mise à jour 1.2.0 doit être proposée automatiquement." -ForegroundColor Green
    Write-Host "Android peut demander une seule confirmation système d'installation." -ForegroundColor Yellow
    exit 0
} catch {
    Write-Host ("BCP PRODUCT INSTALL = ECHEC: "+$_.Exception.Message) -ForegroundColor Red
    exit 1
}
