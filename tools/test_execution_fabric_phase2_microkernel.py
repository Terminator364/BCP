from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "windows" / "bcp_server_v2.py").read_text(encoding="utf-8")
STORE = (ROOT / "windows" / "execution_fabric" / "critical_store.py").read_text(encoding="utf-8")
POLICY = (ROOT / "windows" / "execution_fabric" / "local_path_policy.py").read_text(encoding="utf-8")

# The selected microkernel must stay small and provider-neutral.
assert 'SERVER_VERSION = "0.4.0-r3-phase2"' in SERVER
for forbidden in [
    "TELEGRAM_COMPANION_MANIFEST_URL",
    "NEXUS_BOOTSTRAP_MANIFEST_URL",
    "AUTO_UPDATE_INTERVAL_SECONDS",
    "MISSION_WATCHDOG_COOLDOWNS",
]:
    assert forbidden not in SERVER, forbidden

# Phase 2 durable-authority endpoints.
for route in [
    "/v2/authority/state",
    "/v2/authority/history",
    "/v2/outbox/due",
    "/v2/authority/fence",
    "/v2/authority/transition",
    "/v2/resources",
]:
    assert route in SERVER, route

# Core invariants reused from vNext.
for token in [
    "writer_fence",
    "authority_state",
    "authority_history",
    "outbox",
    "BEGIN IMMEDIATE",
    "PRAGMA synchronous=FULL",
    "PRAGMA mmap_size=0",
    "idempotent_replay",
    "claim_due_outbox",
    "OutboxClaimConflict",
]:
    assert token in STORE, token

# Hot authority DB must fail closed on provider/network roots.
for token in ["drivefs", "onedrive", "dropbox", "icloud drive", "NonLocalStatePath"]:
    assert token in POLICY.casefold() if token != "NonLocalStatePath" else token in POLICY

# The microkernel selftest must exercise fence + durable commit + replay + outbox.
for token in [
    'acquire_writer_fence("bcp/core"',
    'destination="BCP_RUNTIME"',
    "replay.idempotent_replay is True",
    "due_outbox",
    "integrity_check",
]:
    assert token in SERVER, token

# No field PASS from repository code.
assert '"field_certified": False' in SERVER
assert '"proof_scope": "FIELD" if os.name == "nt" else "SIMULATION"' in SERVER

print("BCP_R3_PHASE2_MICROKERNEL_STATIC_GUARD=PASS")
print("candidate=bcp_server_v2.py")
print("field_certified=false")

# Tranche B: constrained resource admission + bounded worker containment.
RESOURCE_ADMISSION = (ROOT / "windows" / "execution_fabric" / "resource_admission.py").read_text(encoding="utf-8")
WORKER = (ROOT / "windows" / "execution_fabric" / "worker_supervisor.py").read_text(encoding="utf-8")
BOOTSTRAP = (ROOT / "windows" / "execution_fabric" / "worker_bootstrap.py").read_text(encoding="utf-8")

for token in ["R4_LOCAL_AI", "LOCAL_AI_DISABLED_PHASE2", "RESOURCE_HOLD_", "BACKGROUND_HOLD_", "worker_policy"]:
    assert token in RESOURCE_ADMISSION, token

for token in ["CreateJobObjectW", "AssignProcessToJobObject", "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE", "MAX_INLINE_INPUT_BYTES", "WorkerTimeout"]:
    assert token in WORKER, token

assert "MAX_PLAN_BYTES" in BOOTSTRAP
assert "MAX_INPUT_BYTES" in BOOTSTRAP

# No free-form remote execution surface in the microkernel.
assert '"/v2/execute"' not in SERVER
assert 'body.get("argv")' not in SERVER
assert 'body.get("command")' not in SERVER

print("BCP_R3_PHASE2_WORKER_BOUNDARY=PASS")

# Startup consolidation candidate: one lightweight per-user trigger only.
assert "BlessingControlPlane" in SERVER
assert r"CurrentVersion\Run" in SERVER
assert "ensure_lifecycle_registration" in SERVER
for forbidden in ["schtasks", "bcp_supervisor.ps1", "BCP Resident Agent", "Tunnel_PC_G4"]:
    assert forbidden not in SERVER, forbidden
print("BCP_R3_PHASE2_STARTUP_BOUNDARY=PASS")
