# BCP Telemetry Contract V0.1

Status: REQUIRED / PRIVACY-BOUNDED

Telemetry is technical and diagnostic only.

## Never collect by default
- user text/content;
- passwords;
- bearer tokens;
- API keys;
- private document contents;
- clipboard contents;
- screenshots;
- arbitrary file names from user folders.

## Local telemetry streams

`%LOCALAPPDATA%\\BCP\\telemetry\\heartbeat.json`
- timestamp
- agent_version
- server_version
- process_up
- local_health
- lan_health
- update_state
- network_profile
- firewall_rule_state
- memory_pressure_class
- last_event_id

`events.jsonl`
- bounded event ledger:
  - START
  - UPDATE_CHECK
  - UPDATE_STAGED
  - UPDATE_VERIFIED
  - UPDATE_COMMITTED
  - UPDATE_ROLLBACK
  - SERVER_START
  - SERVER_CRASH
  - HEALTH_LOCAL_PASS/FAIL
  - HEALTH_LAN_PASS/FAIL
  - PHONE_DISCOVERED
  - PHONE_PAIRED
  - PHONE_HEARTBEAT
  - RECOVERY

`last_error.json`
- stage
- error_class
- sanitized message
- timestamp
- retry_count
- recovery_action
- resolved

## Receipts

Every consequential operation produces a durable receipt containing:
- operation_id
- version_before
- version_after
- payload_sha256
- readback_sha256
- started_at
- committed_at
- result
- rollback_result if applicable

## Remote mirroring

Remote telemetry must be opt-in/private and sanitized.
Public GitHub must never receive machine secrets or raw local diagnostic data.
Until a private BCP relay exists, telemetry stays local and is exposed to the local control plane only.
