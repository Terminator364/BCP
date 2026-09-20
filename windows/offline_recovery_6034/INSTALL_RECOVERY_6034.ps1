param(
  [string]$PackagePath = "",
  [string]$InstallRoot = "",
  [string]$PythonPath = "",
  [string]$WorkRoot = "",
  [string]$ExpectedSha256 = "",
  [string]$TargetVersion = "",
  [int]$TargetSequence = 0,
  [switch]$TestMode,
  [switch]$PreflightOnly,
  [int]$FreeMemoryOverrideMB = -1,
  [int]$MinFreeMemoryMB = 160,
  [int]$MinFreeDiskMB = 80
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$PROD_VERSION = "6.0.34"
$PROD_SEQUENCE = 6034
$PROD_PACKAGE = "Tunnel_PC_G6_6.0.34_2003_RECOVERY_DRIVEFS_RESULT_HOTFIX.zip"
$PROD_SHA256 = "53dbc2e38bf7d1759b95195954189e974cb0489215def0c6d85411a285880e26"
$RUNNER_MEMBER = "payload/tools/recovery_update_runner.py"

function Hold([string]$Code, [string]$Detail="") {
  Write-Host ("HOLD " + $Code + $(if($Detail){" :: "+$Detail}else{""}))
  exit 20
}

if (-not $TestMode) {
  $TargetVersion = $PROD_VERSION
  $TargetSequence = $PROD_SEQUENCE
  $ExpectedSha256 = $PROD_SHA256
  if (-not $PackagePath) { $PackagePath = Join-Path $PSScriptRoot $PROD_PACKAGE }
  if (-not $InstallRoot) { $InstallRoot = Join-Path $env:LOCALAPPDATA "Tunnel_PC_G4" }
  if (-not $PythonPath) { $PythonPath = Join-Path $InstallRoot "runtime\python.exe" }
  if (-not $WorkRoot) { $WorkRoot = Join-Path $env:LOCALAPPDATA "ChatGPT_ManagedApps\offline_recovery\6034" }
} else {
  if (-not $TargetVersion -or $TargetSequence -lt 1 -or -not $ExpectedSha256) { Hold "TEST_PARAMETERS_INCOMPLETE" }
  if (-not $PackagePath -or -not $InstallRoot -or -not $PythonPath -or -not $WorkRoot) { Hold "TEST_PATHS_INCOMPLETE" }
}

try { [System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = "BelowNormal" } catch {}

$PackagePath = [IO.Path]::GetFullPath($PackagePath)
$InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
$PythonPath = [IO.Path]::GetFullPath($PythonPath)
$WorkRoot = [IO.Path]::GetFullPath($WorkRoot)
$ExpectedSha256 = $ExpectedSha256.ToLowerInvariant()

if (-not (Test-Path -LiteralPath $PackagePath -PathType Leaf)) { Hold "PACKAGE_MISSING" $PackagePath }
if (-not (Test-Path -LiteralPath $InstallRoot -PathType Container)) { Hold "INSTALL_ROOT_MISSING" $InstallRoot }
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { Hold "PYTHON_RUNTIME_MISSING" $PythonPath }

New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
$LockPath = Join-Path $WorkRoot "install.lock"
$lock = $null
try {
  try {
    $lock = [IO.File]::Open($LockPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  } catch {
    Hold "INSTALL_ALREADY_RUNNING"
  }

  $freeMB = $FreeMemoryOverrideMB
  if ($freeMB -lt 0) {
    try {
      $os = Get-CimInstance Win32_OperatingSystem
      $freeMB = [int]([double]$os.FreePhysicalMemory / 1024.0)
    } catch { $freeMB = 512 }
  }
  if ($freeMB -lt $MinFreeMemoryMB) { Hold "LOW_MEMORY_PREMUTATION" ("free_mb="+$freeMB) }

  try {
    $driveRoot = [IO.Path]::GetPathRoot($WorkRoot)
    $drive = New-Object IO.DriveInfo($driveRoot)
    $freeDiskMB = [int]($drive.AvailableFreeSpace / 1MB)
    if ($freeDiskMB -lt $MinFreeDiskMB) { Hold "LOW_DISK_PREMUTATION" ("free_mb="+$freeDiskMB) }
  } catch {
    if (-not $TestMode) { Hold "DISK_PREFLIGHT_FAILED" $_.Exception.Message }
  }

  $actual = (Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $ExpectedSha256) { Hold "PACKAGE_SHA256_MISMATCH" ("actual="+$actual) }

  $activePath = Join-Path $InstallRoot "state\active_release.json"
  if (Test-Path -LiteralPath $activePath) {
    try {
      $active = Get-Content -Raw -LiteralPath $activePath | ConvertFrom-Json
      $activeSeq = [int]$active.sequence
      if ($activeSeq -gt $TargetSequence) { Hold "TARGET_SUPERSEDED" ("active_sequence="+$activeSeq) }
      if ($activeSeq -eq $TargetSequence -and [string]$active.version -eq $TargetVersion) {
        Write-Host "OFFLINE_RECOVERY_ALREADY_ACTIVE version=$TargetVersion sequence=$TargetSequence"
        exit 0
      }
    } catch {
      if (-not $TestMode) { Hold "ACTIVE_RELEASE_UNREADABLE" $_.Exception.Message }
    }
  }

  $stage = Join-Path $WorkRoot "stage"
  $control = Join-Path $WorkRoot "control"
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $stage,$control
  New-Item -ItemType Directory -Force -Path $stage,(Join-Path $control "00_CONTEXT"),(Join-Path $control "02_UPDATES\AGENT"),(Join-Path $control "RECOVERY") | Out-Null

  $stagedPackage = Join-Path $stage ([IO.Path]::GetFileName($PackagePath))
  Copy-Item -LiteralPath $PackagePath -Destination $stagedPackage -Force
  $stageSha = (Get-FileHash -LiteralPath $stagedPackage -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($stageSha -ne $ExpectedSha256) { Hold "STAGED_PACKAGE_READBACK_MISMATCH" }

  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $zip = [IO.Compression.ZipFile]::OpenRead($stagedPackage)
  try {
    $matches = @($zip.Entries | Where-Object { $_.FullName -eq $RUNNER_MEMBER })
    if ($matches.Count -ne 1) { Hold "RUNNER_MEMBER_COUNT" ("count="+$matches.Count) }
    $entry = $matches[0]
    if ($entry.Length -lt 64 -or $entry.Length -gt 524288) { Hold "RUNNER_SIZE_INVALID" ("bytes="+$entry.Length) }
    $reader = New-Object IO.StreamReader($entry.Open(), [Text.Encoding]::UTF8, $true)
    try { $runnerText = $reader.ReadToEnd() } finally { $reader.Dispose() }
  } finally { $zip.Dispose() }

  if ($runnerText -notmatch "def main\(" -or $runnerText -notmatch "__main__") { Hold "RUNNER_CONTRACT_INVALID" }
  if ($TargetSequence -ge 6034) {
    if ($runnerText -notmatch [regex]::Escape("publish_result(root,result,rec)") -or $runnerText -match [regex]::Escape("atomic(result,rec)")) {
      Hold "RUNNER_DRIVEFS_FAILOPEN_CONTRACT"
    }
  }

  $runnerPath = Join-Path $stage "recovery_update_runner.py"
  [IO.File]::WriteAllText($runnerPath,$runnerText,(New-Object Text.UTF8Encoding($false)))
  & $PythonPath -m py_compile $runnerPath
  if ($LASTEXITCODE -ne 0) { Hold "RUNNER_COMPILE_FAILED" }

  $controlPackage = Join-Path (Join-Path $control "02_UPDATES\AGENT") ([IO.Path]::GetFileName($PackagePath))
  Copy-Item -LiteralPath $stagedPackage -Destination $controlPackage -Force
  if ((Get-FileHash -LiteralPath $controlPackage -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedSha256) { Hold "CONTROL_PACKAGE_READBACK_MISMATCH" }

  $target = [ordered]@{
    schema="g6.recovery_bootstrap_target/1"; status="ACTIVE"; truth="LOCAL_OFFLINE_TARGET_NOT_INSTALL_PROOF";
    version=$TargetVersion; sequence=$TargetSequence; package_file=[IO.Path]::GetFileName($PackagePath);
    package_sha256=$ExpectedSha256; authorization_token="2003"; rollback_version="6.0.32"; rollback_sequence=6032
  }
  $targetPath = Join-Path $control "00_CONTEXT\RECOVERY_BOOTSTRAP_TARGET.json"
  [IO.File]::WriteAllText($targetPath,($target | ConvertTo-Json -Depth 6),(New-Object Text.UTF8Encoding($false)))

  if ($PreflightOnly) {
    Write-Host "OFFLINE_RECOVERY_PREFLIGHT_PASS version=$TargetVersion sequence=$TargetSequence free_memory_mb=$freeMB"
    exit 0
  }

  $stdout = Join-Path $WorkRoot "runner.stdout.log"
  $stderr = Join-Path $WorkRoot "runner.stderr.log"
  Remove-Item -Force -ErrorAction SilentlyContinue $stdout,$stderr
  $args = @($runnerPath,"--install",$InstallRoot,"--control",$control)
  $proc = Start-Process -FilePath $PythonPath -ArgumentList $args -WorkingDirectory $InstallRoot -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
  if (-not $proc.WaitForExit(420000)) {
    try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
    Hold "RUNNER_TIMEOUT_420S"
  }
  if ($proc.ExitCode -ne 0) {
    $tail = ""
    if (Test-Path $stderr) { $tail = (Get-Content -Raw $stderr); if($tail.Length -gt 1200){$tail=$tail.Substring($tail.Length-1200)} }
    Hold "RUNNER_FAILED" ("rc="+$proc.ExitCode+" "+$tail)
  }

  if (-not (Test-Path -LiteralPath $activePath)) { Hold "ACTIVE_RELEASE_MISSING_AFTER_RUN" }
  $final = Get-Content -Raw -LiteralPath $activePath | ConvertFrom-Json
  if ([int]$final.sequence -ne $TargetSequence -or [string]$final.version -ne $TargetVersion) {
    Hold "ACTIVE_RELEASE_READBACK_MISMATCH" ("version="+$final.version+" sequence="+$final.sequence)
  }

  $receipt = [ordered]@{
    schema="bcp.offline_recovery_install/1"; status="INSTALL_ACTIVE_READBACK_PASS";
    version=$TargetVersion; sequence=$TargetSequence; package_sha256=$ExpectedSha256;
    install_root=$InstallRoot; completed_at=(Get-Date).ToUniversalTime().ToString("o");
    internet_required=$false; drivefs_required=$false; field_command_plane_two_cycles_verified=$false
  }
  [IO.File]::WriteAllText((Join-Path $WorkRoot "OFFLINE_INSTALL_RESULT.json"),($receipt | ConvertTo-Json -Depth 6),(New-Object Text.UTF8Encoding($false)))
  Write-Host "OFFLINE_RECOVERY_INSTALL_PASS version=$TargetVersion sequence=$TargetSequence"
  exit 0
}
finally {
  if ($lock) { $lock.Dispose() }
  Remove-Item -Force -ErrorAction SilentlyContinue $LockPath
}
