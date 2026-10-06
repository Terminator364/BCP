param(
    [string]$OutputPath = "",
    [switch]$NoFileWrite
)

$ErrorActionPreference = "Stop"

function UtcNow {
    [DateTime]::UtcNow.ToString("o")
}

function Safe-Text([string]$Value, [int]$Max = 1200) {
    $safe = [string]$Value
    $safe = ($safe -replace '\b\d{6,12}:[A-Za-z0-9_-]{20,}\b', '<REDACTED_TELEGRAM_TOKEN>')
    $safe = ($safe -replace '(?i)(Bearer\s+)[A-Za-z0-9._~+/-]{12,}', '$1<REDACTED>')
    $safe = ($safe -replace '(?i)((?:api[_-]?key|access[_-]?token|auth[_-]?token|secret|password|passwd|pwd)\s*[=:]\s*)[^\s;,&]+', '$1<REDACTED>')
    $safe = ($safe -replace '(?i)([?&](?:token|key|secret|auth|password)=)[^&\s]+', '$1<REDACTED>')
    $safe = ($safe -replace '[\r\n\t]+', ' ')
    if ($safe.Length -gt $Max) { $safe = $safe.Substring(0, $Max) }
    return $safe
}

function Is-ProviderSyncedPath([string]$Path) {
    $p = ([string]$Path).Replace('/','\').ToLowerInvariant()
    return (
        $p -match '\\onedrive\\' -or
        $p -match '\\google drive\\' -or
        $p -match '\\my drive\\' -or
        $p -match '\\dropbox\\' -or
        $p -match '\\icloud drive\\' -or
        $p -match '\\drivefs\\'
    )
}

function Get-RunEntries {
    $out = @()
    try {
        $obj = Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -ErrorAction Stop
        foreach ($p in $obj.PSObject.Properties) {
            if ($p.Name -like "PS*") { continue }
            $out += [ordered]@{
                name = [string]$p.Name
                value = Safe-Text ([string]$p.Value)
            }
        }
    } catch {}
    return @($out)
}

function Get-TaskInventory {
    $out = @()
    try {
        foreach ($task in @(Get-ScheduledTask -ErrorAction Stop)) {
            $actions = @()
            foreach ($a in @($task.Actions)) {
                $actions += [ordered]@{
                    execute = Safe-Text ([string]$a.Execute)
                    arguments = Safe-Text ([string]$a.Arguments)
                    working_directory = Safe-Text ([string]$a.WorkingDirectory)
                }
            }
            $out += [ordered]@{
                name = [string]$task.TaskName
                path = [string]$task.TaskPath
                state = [string]$task.State
                actions = $actions
            }
        }
    } catch {}
    return @($out)
}

function Get-ServiceInventory {
    $out = @()
    try {
        foreach ($svc in @(Get-CimInstance Win32_Service -ErrorAction Stop)) {
            $out += [ordered]@{
                name = [string]$svc.Name
                display_name = [string]$svc.DisplayName
                state = [string]$svc.State
                start_mode = [string]$svc.StartMode
                path_name = Safe-Text ([string]$svc.PathName)
                process_id = [int]$svc.ProcessId
            }
        }
    } catch {}
    return @($out)
}

function Get-ProcessInventory {
    $out = @()
    try {
        foreach ($p in @(Get-CimInstance Win32_Process -ErrorAction Stop)) {
            $out += [ordered]@{
                pid = [int]$p.ProcessId
                parent_pid = [int]$p.ParentProcessId
                name = [string]$p.Name
                executable_path = Safe-Text ([string]$p.ExecutablePath)
                command_line = Safe-Text ([string]$p.CommandLine)
            }
        }
    } catch {}
    return @($out)
}

function Get-ListenerInventory {
    $out = @()
    try {
        foreach ($c in @(Get-NetTCPConnection -State Listen -ErrorAction Stop)) {
            $out += [ordered]@{
                local_address = [string]$c.LocalAddress
                local_port = [int]$c.LocalPort
                owning_process = [int]$c.OwningProcess
            }
        }
    } catch {}
    return @($out)
}

function Get-ResourceSnapshot {
    $result = [ordered]@{
        memory_total_mib = $null
        memory_free_mib = $null
        memory_load_pct = $null
        pagefile_allocated_mib = $null
        pagefile_current_mib = $null
        pagefile_peak_mib = $null
        system_drive_free_mib = $null
    }
    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
        $totalKb = [double]$os.TotalVisibleMemorySize
        $freeKb = [double]$os.FreePhysicalMemory
        if ($totalKb -gt 0) {
            $result.memory_total_mib = [math]::Round($totalKb / 1024, 0)
            $result.memory_free_mib = [math]::Round($freeKb / 1024, 0)
            $result.memory_load_pct = [math]::Round((1 - ($freeKb / $totalKb)) * 100, 1)
        }
    } catch {}
    try {
        $page = @(Get-CimInstance Win32_PageFileUsage -ErrorAction Stop)
        $result.pagefile_allocated_mib = [int](($page | Measure-Object -Property AllocatedBaseSize -Sum).Sum)
        $result.pagefile_current_mib = [int](($page | Measure-Object -Property CurrentUsage -Sum).Sum)
        $result.pagefile_peak_mib = [int](($page | Measure-Object -Property PeakUsage -Sum).Sum)
    } catch {}
    try {
        $drive = Get-CimInstance Win32_LogicalDisk -Filter ("DeviceID='" + $env:SystemDrive + "'") -ErrorAction Stop
        if ($drive) { $result.system_drive_free_mib = [math]::Round(([double]$drive.FreeSpace / 1MB), 0) }
    } catch {}
    return $result
}

function Get-BoundedDirectoryCandidates([string]$Regex) {
    $roots = @(
        (Join-Path $env:LOCALAPPDATA "ChatGPT_ManagedApps"),
        (Join-Path $HOME "Documents"),
        (Join-Path $HOME "Desktop"),
        (Join-Path $HOME "source"),
        (Join-Path $HOME "repos"),
        (Join-Path $HOME "Projects")
    )
    $out = @()
    foreach ($root in $roots) {
        if (-not $root -or -not (Test-Path -LiteralPath $root -PathType Container)) { continue }
        try {
            foreach ($dir in @(Get-ChildItem -LiteralPath $root -Directory -Force -ErrorAction Stop)) {
                if ([string]$dir.Name -notmatch $Regex -and [string]$dir.FullName -notmatch $Regex) { continue }
                $out += [ordered]@{
                    path = [string]$dir.FullName
                    source_root = [string]$root
                    provider_synced = (Is-ProviderSyncedPath ([string]$dir.FullName))
                    observation = "BOUNDED_NAME_MATCH"
                }
            }
        } catch {}
    }
    return @($out)
}

function Match-Inventory([string]$Regex, $Processes, $Listeners, $Tasks, $Services, $RunEntries) {
    $matchedProcesses = @(
        $Processes | Where-Object {
            ([string]$_.name -match $Regex) -or
            ([string]$_.executable_path -match $Regex) -or
            ([string]$_.command_line -match $Regex)
        }
    )
    $pids = @($matchedProcesses | ForEach-Object { [int]$_.pid })
    $matchedListeners = @(
        $Listeners | Where-Object { $pids -contains [int]$_.owning_process }
    )
    $matchedTasks = @(
        $Tasks | Where-Object {
            $blob = ([string]$_.name + " " + [string]$_.path + " " + (($_.actions | ConvertTo-Json -Compress -Depth 5)))
            $blob -match $Regex
        }
    )
    $matchedServices = @(
        $Services | Where-Object {
            (([string]$_.name + " " + [string]$_.display_name + " " + [string]$_.path_name) -match $Regex)
        }
    )
    $matchedRun = @(
        $RunEntries | Where-Object {
            (([string]$_.name + " " + [string]$_.value) -match $Regex)
        }
    )
    return [ordered]@{
        processes = @($matchedProcesses)
        listeners = @($matchedListeners)
        scheduled_tasks = @($matchedTasks)
        services = @($matchedServices)
        run_entries = @($matchedRun)
    }
}

$projects = [ordered]@{
    BCP = "(?i)(BlessingControlPlane|ChatGPT_ManagedApps\\bcp|bcp_server|bcp_server_v2)"
    TLIB = "(?i)(TLIB|total[-_ ]?library)"
    EXCELLENTIA = "(?i)(excellentia)"
    DELIVERY = "(?i)(chatgpt[-_ ]?delivery|chatgpt_?delivery|ChatGPT_ManagedApps\\\\ChatGPT[-_ ]?Delivery)"
    BUILDHUB = "(?i)(buildhub)"
    PC_COMMAND = "(?i)(pc[-_ ]?command)"
    PHONEMOUSE = "(?i)(phonemouse)"
    P2PCR95 = "(?i)(p2pcr95|pc[-_ ]?remote)"
}

$processes = Get-ProcessInventory
$listeners = Get-ListenerInventory
$tasks = Get-TaskInventory
$services = Get-ServiceInventory
$runEntries = Get-RunEntries

$projectResults = [ordered]@{}
foreach ($entry in $projects.GetEnumerator()) {
    $id = [string]$entry.Key
    $regex = [string]$entry.Value
    $runtime = Match-Inventory $regex $processes $listeners $tasks $services $runEntries
    $roots = Get-BoundedDirectoryCandidates $regex
    $projectResults[$id] = [ordered]@{
        local_root_candidates = @($roots)
        runtime_observations = $runtime
        candidate_counts = [ordered]@{
            roots = @($roots).Count
            processes = @($runtime.processes).Count
            listeners = @($runtime.listeners).Count
            scheduled_tasks = @($runtime.scheduled_tasks).Count
            services = @($runtime.services).Count
            run_entries = @($runtime.run_entries).Count
        }
        binding_decision = "READBACK_REQUIRED"
        field_certified = $false
    }
}

$bcpHealth = [ordered]@{ reachable=$false; version=$null; pc_name=$null; error=$null }
try {
    $h = Invoke-RestMethod -UseBasicParsing -Method Get -Uri "http://127.0.0.1:8765/health" -TimeoutSec 3
    $bcpHealth.reachable = ($h.ok -eq $true)
    $bcpHealth.version = Safe-Text ([string]$h.version) 120
    $bcpHealth.pc_name = Safe-Text ([string]$h.pc_name) 120
} catch {
    $bcpHealth.error = Safe-Text ([string]$_.Exception.Message) 240
}

$receipt = [ordered]@{
    schema = "bcp.cross_project_field_binding_probe/1"
    observed_at = UtcNow
    computer_name = [string]$env:COMPUTERNAME
    user_name = [string]$env:USERNAME
    os = [ordered]@{
        platform = "WINDOWS"
        version = [Environment]::OSVersion.Version.ToString()
    }
    safety = [ordered]@{
        read_only_system_probe = $true
        process_mutation = $false
        scheduled_task_mutation = $false
        service_mutation = $false
        registry_mutation = $false
        network_mutation = $false
        evidence_file_write_only = (-not $NoFileWrite)
        command_line_redaction = $true
        field_certified = $false
    }
    resources = Get-ResourceSnapshot
    bcp_health = $bcpHealth
    projects = $projectResults
    decision_policy = [ordered]@{
        local_root_candidate_is_not_binding = $true
        process_match_is_not_install_proof = $true
        listener_match_is_not_project_authority = $true
        provider_synced_root_is_not_hot_state_authority = $true
        repository_bindings_remain_from_phase8_catalog = $true
        final_binding_requires_bcp_readback = $true
    }
}

if (-not $OutputPath) {
    $OutputPath = Join-Path $env:LOCALAPPDATA "ChatGPT_ManagedApps\bcp\evidence\BCP_R3_CROSS_PROJECT_BINDING_LATEST.json"
}

$json = $receipt | ConvertTo-Json -Depth 14
if (-not $NoFileWrite) {
    $dir = Split-Path -Parent $OutputPath
    if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    [IO.File]::WriteAllText($OutputPath, $json, (New-Object Text.UTF8Encoding($false)))
}

Write-Output $json
