# BCP Edge — Automatic Diagnostics / Telemetry Requirement

Status: REQUIRED NEXT ANDROID ITERATION

BCP Edge must diagnose connection failures without asking the user to reason about them.

Staged probe sequence:
1. Android network available?
2. Wi-Fi/LAN transport active?
3. paired PC discovered?
4. TCP port reachable?
5. HTTP /health reachable?
6. authentication accepted?
7. project HEAD reachable?
8. checkpoint commit accepted?
9. receipt/readback confirmed?

Each stage emits a local technical event.
If the PC is unreachable, events remain queued locally and are forwarded after reconnection.

User-facing result should be concise:
- CONNECTED
- PC_NOT_FOUND
- LAN_ISOLATION_SUSPECTED
- WINDOWS_FIREWALL_BLOCK_SUSPECTED
- AUTH_FAILED
- SERVER_UNHEALTHY
- PROJECT_STATE_ERROR

The app must not display long tokens in normal UI.
