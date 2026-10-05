from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "windows" / "execution_fabric"

SUP = (RUNTIME / "worker_supervisor.py").read_text(encoding="utf-8")
BOOT = (RUNTIME / "worker_bootstrap.py").read_text(encoding="utf-8")
ADMISSION = (RUNTIME / "resource_admission.py").read_text(encoding="utf-8")
SERVER = (ROOT / "windows" / "bcp_server_v2.py").read_text(encoding="utf-8")

# Windows containment must remain start-gated and whole-tree bounded.
for token in [
    "CreateJobObjectW",
    "SetInformationJobObject",
    "AssignProcessToJobObject",
    "TerminateJobObject",
    "JOB_OBJECT_LIMIT_PROCESS_MEMORY",
    "JOB_OBJECT_LIMIT_JOB_MEMORY",
    "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE",
]:
    assert token in SUP, token

assert "proc.communicate(input=plan" in SUP
assert "bootstrap is blocked waiting for stdin" in SUP
assert "MAX_INLINE_INPUT_BYTES = 512 * 1024" in SUP
assert "MAX_PLAN_BYTES = 1 * 1024 * 1024" in BOOT
assert "MAX_INPUT_BYTES = 512 * 1024" in BOOT

# No arbitrary shell execution contract is exposed by the microkernel.
for forbidden in [
    "shell=True",
    '"shell"',
    "/v2/shell",
    "/v2/exec",
    "/v2/command",
    "caller_argv",
]:
    assert forbidden not in SERVER, forbidden

# Supervisor stays an internal primitive; no HTTP endpoint accepts argv.
assert "WorkerSupervisor" not in SERVER
assert "argv" not in SERVER

# Resource admission consumes Resource Governor mode; it does not probe resources itself.
for token in ["GREEN", "AMBER", "RED", "CRITICAL", "WAITING_RESOURCE", "WAITING_POLICY", "R4_LOCAL_AI"]:
    assert token in ADMISSION, token
for forbidden in ["psutil", "Get-CimInstance", "GlobalMemoryStatusEx", "wmic"]:
    assert forbidden not in ADMISSION, forbidden

# Non-Windows CI is simulation-only. Real Windows Job Object behavior remains a field gate.
assert "NON_WINDOWS_TEST_MODE" in SUP
assert "Windows Job Object required by policy" in SUP

print("BCP_R3_PHASE2B_WORKER_BOUNDARY=PASS")
print("arbitrary_shell_endpoint=false")
print("windows_job_object_field_certification=pending")
