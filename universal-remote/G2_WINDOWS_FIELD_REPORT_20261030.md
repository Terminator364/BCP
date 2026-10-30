# BCP Universal Remote — G2 field report (2026-10-30)

Status: **G2-WINDOWS-TRANSPORT-PILOT = PASS**; **G2-ANDROID-APP = PENDING FIELD INTEGRATION**.

## Real Windows executions
- G1 Tailscale tailnet connectivity between MBMPC and Samsung previously proved via Tailscale ping.
- Private Windows G2 server `g2_tls_bridge.py` bound to loopback, current Wi-Fi LAN IP and Tailscale PC IP; private key/certificate generated on PC and never committed.
- Server reuses BCP USB Rescue authenticated HMAC-SHA256, timestamp/nonce, replay protection, audit ledger. **Read-only status/diagnostics/audit only** in this pilot.
- Python G2 smoke test: 9/9 checks passed: TLS + signed status on the three Windows endpoints, denial of anonymous request and write.
- Java client `G2TransportClient.java`: JVM field test passed (authentic signed status, wrong certificate rejected, disallowed endpoint rejected). Does not require Android to compile, but APK integration still needed.
- Tailscale Serve enabled as **private HTTPS reverse proxy** to this service, not public Funnel.
- Real signed HTTPS POST traversing Serve: **HTTP 200, TLS 1.3, response HMAC valid, MBMPC status returned**. This test originated on the PC; a smartphone-origin request is not yet proved.
- Auto-start `BCP Universal G2.vbs` registered in Windows Startup; `g2_autostart.ps1` correctly identifies the existing service without duplication.
- The old R3.3 APK and original USB Rescue service have not been modified.

## Important remaining blockers
1. Integrate `G2TransportClient.java` into a signed Android APK with existing signing identity. Device native-app update not yet installed.
2. Initial phone pairing not yet established for the new transport; secret keys must not be copied through chat.
3. Test HTTPS request initiated by Samsung over LAN; confirm LAN first, then Tailscale failover, plus Windows firewall narrowly scoped if needed.
4. Implement full authorized Windows admin/GUI capabilities only after secure application transport field validation.
5. ChatGPT native tool-to-Android/Windows bridging requires a separately supported integration and remains unimplemented. No false claims of total remote control.

## Files on MBMPC
`%LOCALAPPDATA%\BCP-Universal-Remote\g2_tls_bridge.py`
`%LOCALAPPDATA%\BCP-Universal-Remote\g2_autostart.ps1`
`%LOCALAPPDATA%\BCP-Universal-Remote\g2_test.py`
`%LOCALAPPDATA%\BCP-Universal-Remote\g2_serve_test.py`
`%LOCALAPPDATA%\BCP-Universal-Remote\android\com\blessing\rescuebridge\G2TransportClient.java`
`%LOCALAPPDATA%\BCP-Universal-Remote\state\g2-test-report.json`

Security: no SMS, email or third-party server required for LAN transport. Do not expose G2 server or its unpaired successor to public internet. Tailscale Serve only, never Funnel.

## Rectification de l'erreur du navigateur Android (16 h 02)
- Capture Samsung : `{"ok":false,"reason":"NOT_FOUND"}`; cela prouve que le serveur a répondu, mais ne prouve pas le canal HMAC depuis l'APK.
- GET `/` n'était pas servi, à la différence de `/health`.
- Correctif dans `g2_tls_bridge.py` uniquement : GET `/` et GET `/health/` redirigés en interne vers GET `/health` ; POST et secrets inchangés.
- Port 8899 : les trois URL retournent 200. Après redémarrage du port 8898 : suite TLS/HMAC 9/9 PASS, POST signé via Tailscale Serve PASS (TLS 1.3, HTTP 200, HMAC réponse valide).
- Test navigateur Samsung après correction : encore à confirmer par une nouvelle capture ou ouverture.
