# BCP Operations Canonical — Zero-Manual Normal Path

Status: CANONICAL / REQUIRED

BCP normal operation must follow the same operational pattern used across the user's PhoneMouse / P2PCR95 / BuildHub projects:

- install once;
- resident local agent;
- self-update transactionally;
- automatic preflight / repair / recovery;
- built-in heartbeat, receipts, readback and diagnostics;
- no repeated manual ZIP downloads;
- no repeated IP/token/project copy-paste;
- no screenshots required for ordinary diagnosis;
- local-first / offline-first;
- one bounded user approval only when Windows/Android genuinely requires it.

## Hard rule

After the first bootstrap is installed, a new BCP version is NOT a user download task.

The resident agent must:
1. discover the stable release manifest;
2. download the new payload;
3. verify SHA-256;
4. stage it;
5. health-test it;
6. atomically promote it;
7. rollback automatically if health fails;
8. persist a machine-readable receipt.

## PC normal path

The PC agent owns:
- Windows network-profile preflight;
- local firewall rule for the trusted LAN;
- BCP server lifecycle;
- heartbeat;
- self-update;
- crash/unclean-shutdown detection;
- resource-pressure snapshot;
- update receipts;
- local technical telemetry.

## Android normal path

BCP Edge must evolve to:
- discover the PC automatically on the trusted LAN;
- pair with one confirmation or QR/short code;
- provision/rotate credentials automatically;
- remember the paired PC across restarts and app updates;
- reconnect if PC IP changes;
- run staged connectivity probes automatically;
- keep local telemetry when the PC is unreachable and forward it later;
- hide manual IP/token/project fields under Diagnostics/Advanced.

## Manual fallback

Manual files, IP entry, token entry, port entry and project entry are diagnostics-only fallbacks.
They are not an acceptable normal workflow.

## Acceptance gate

`ZERO_MANUAL_NORMAL_PATH=PASS` requires:
- one initial bootstrap/user approval at most;
- no repeated technical downloads;
- no recurring copy-paste;
- automatic telemetry sufficient to locate the failing stage;
- automatic recovery or a precise machine-readable blocker.
