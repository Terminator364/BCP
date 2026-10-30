# BCP Universal Remote — G2 field validation completed (30 October 2026)

## Confirmed on the actual Samsung, not a simulated client

At 18:38 local Kinshasa time, the user supplied a screenshot of **BCP Universal Remote 1.1.1, versionCode 15**, showing "Application à jour", last check 30/10 18:38 and automatic 30-second development mode.

A subsequent remote read of the actual Windows file `%LOCALAPPDATA%\\BCP-Universal-Remote\\state\\g2-phone-status.json` at 18:39:37 local returned the following field report, timestamped 18:38:51 local:

```json
{"utc":"2026-10-30T17:38:51.986967+00:00","version_code":15,"network":"wifi","update_state":"current","app_visible":true}
```

The server writes this file **only after verifying HMAC signature and anti-replay nonce** for POST `/v1/phone-state`. The report contains no device identifiers, message content, pairing key, or precise location. The screenshot and the record agree about the installed version.

### Actual update requests (sanitized request log)
The G2 server logged Android user-agent class requests to `/updates/stable.json` and `/updates/stable.apk` at 18:38:37–18:38:38 local, followed by status checks at 18:38:49 and 18:38:51. Earlier 18:28–18:29 requests established approximately 30-second foreground polling.

### Field gates
- G1: Tailscale pair and direct LAN reachability — PASS.
- G2A: Samsung app HTTPS + HMAC authenticated Wi-Fi status — PASS.
- G2B: Signed application updates (v1.0 to v1.1 to v1.1.1) — PASS on device; whether Android always installs without a system confirmation is **NOT proven**.
- G2C: Android foreground ~30-second development update polling — PASS on device.
- G2D: HMAC-authenticated Android-to-Windows heartbeat — **PASS**.
- G2E: Signed remote Tailscale 443 from Samsung specifically — NOT independently field-verified; Java client to Serve and actual phone heartbeat pass, but heartbeat path is through HTTPS Serve; screenshot of primary status was LAN.
- G3: robust USB/Bluetooth fallbacks — incomplete.
- G4: full authorized Windows control beyond diagnostic pilot — incomplete.
- G5: native ChatGPT plugin/connector access to this agent — incomplete.

## Next engineering phase
Preserve G2 as a stable release baseline; do not force a needless APK reinstall for backend-only changes. Develop G4 in an isolated feature area with per-action permissions, Windows session authorization/UAC and audit/rollback safeguards. ChatGPT-to-PC linkage should be implemented through an explicitly connected action-capable plugin/connector (or authorized existing Desktop Commander); a standalone Android APK does not grant ChatGPT cloud direct control.

### Project policy
Do not restore metered-network update bans. Keep a single signed stable APK and a single update manifest. Use mode-chantiers for visible-app 30-second checks only, normal 15-minute nominal checks otherwise. Never state that phone telemetry exists before the authenticated file actually appears on Windows.
