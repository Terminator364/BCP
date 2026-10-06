from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "windows" / "BCP_R3_CROSS_PROJECT_FIELD_BINDING_PROBE.ps1").read_text(
    encoding="utf-8"
)
SCHEMA = json.loads(
    (ROOT / "schemas" / "bcp_cross_project_field_binding_probe_v1.schema.json").read_text(
        encoding="utf-8"
    )
)

assert SCHEMA["$schema"] == "https://json-schema.org/draft/2020-12/schema"
assert SCHEMA["properties"]["safety"]["properties"]["field_certified"]["const"] is False

# No system/runtime mutation is allowed in this evidence package.
for forbidden in (
    "Stop-Process",
    "Start-Process",
    "Set-ItemProperty",
    "New-ItemProperty",
    "Remove-ItemProperty",
    "Remove-Item ",
    "Move-Item",
    "Copy-Item",
    "Disable-ScheduledTask",
    "Enable-ScheduledTask",
    "Register-ScheduledTask",
    "Unregister-ScheduledTask",
    "Set-ScheduledTask",
    "Start-ScheduledTask",
    "Stop-ScheduledTask",
    "Set-Service",
    "Start-Service",
    "Stop-Service",
    "Restart-Service",
    "Restart-Computer",
    "shutdown.exe",
    "taskkill",
    "sc.exe ",
    "reg.exe ",
):
    assert forbidden not in SCRIPT, forbidden

# The only filesystem write is the optional evidence JSON output.
assert "[IO.File]::WriteAllText($OutputPath" in SCRIPT
assert "[switch]$NoFileWrite" in SCRIPT
assert "evidence_file_write_only" in SCRIPT

# Inventory is bounded; it must not recursively crawl user disks.
assert "Get-ChildItem" in SCRIPT
assert "-Recurse" not in SCRIPT
assert "Get-CimInstance Win32_Process" in SCRIPT
assert "Get-NetTCPConnection -State Listen" in SCRIPT
assert "Get-ScheduledTask" in SCRIPT
assert "Get-CimInstance Win32_Service" in SCRIPT

# Secret-bearing process/task strings are redacted before output.
for token in (
    "REDACTED_TELEGRAM_TOKEN",
    "Bearer",
    "api[_-]?key",
    "access[_-]?token",
    "password",
):
    assert token in SCRIPT, token

# Network use is localhost health GET only, not a remote discovery scan.
assert 'http://127.0.0.1:8765/health' in SCRIPT
assert "Invoke-WebRequest" not in SCRIPT
assert "Test-NetConnection" not in SCRIPT

# Exact Phase 8 project scope.
for project_id in (
    "BCP",
    "TLIB",
    "EXCELLENTIA",
    "DELIVERY",
    "BUILDHUB",
    "PC_COMMAND",
    "PHONEMOUSE",
    "P2PCR95",
):
    assert project_id in SCRIPT

# Candidate observations are never promoted by the probe itself.
for required in (
    'binding_decision = "READBACK_REQUIRED"',
    "local_root_candidate_is_not_binding",
    "process_match_is_not_install_proof",
    "listener_match_is_not_project_authority",
    "final_binding_requires_bcp_readback",
    "field_certified = $false",
):
    assert required in SCRIPT, required

print("BCP_R3_FIELD_BINDING_PACKAGE_STATIC_GUARD=PASS")
print("system_mutation=false")
print("field_certified=false")
