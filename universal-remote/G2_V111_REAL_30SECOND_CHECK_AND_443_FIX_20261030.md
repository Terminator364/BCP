# BCP Universal Remote G2 — Real Samsung mode-chantiers validation and v1.1.1 443 correction

Date: 2026-10-30. Device: Samsung on same private Tailscale tailnet as MBMPC.

## Real device screenshot and server log — ACCEPTED
The user submitted the real Samsung Settings screen showing `BCP Universal Remote · 1.1.0 · mode chantier intelligent`, `Application à jour · version 14`, last check at 18:28, and a visible 30-second development mode with a 4-hour window.

Windows `state/g2-update-checks.jsonl` later confirmed requests classified as Android: `17:28:14Z`, `17:28:41Z`, `17:29:12Z` to `/updates/stable.json` (local Kinshasa time: 18:28–18:29). Intervals approximately 27 and 30 seconds. G2 30-second foreground development polling is therefore genuinely field validated. It is not a 30-second always-running background polling guarantee.

User previously proved Wi-Fi local G2 connection with HTTPS and HMAC signed status using Samsung: screen `MBMPC connecté`.

## Bug found: G2 phone-status report and Tailscale fallback failed
A critical validation defect in `G2TransportClient.java` blocked every port below 1024, including the standard secure HTTPS port **443**. Android updater GET requests used a separate transport that supported 443; consequently 30-second updater checks worked, but `BCPPhoneReporter.report` over the signed G2 transport did not send a single successful report, and signed Tailscale fallback was broken.

### v1.1.1 targeted correction
- Source branch: `feat/universal-remote-transport-20261030`, source commit `e5a4a6b`.
- Accept 443 in G2TransportClient constructor; retain rejection for other restricted lower ports, retain 8898 for local HTTPS pinned certificate; HMAC and certificates unchanged.
- CI build `41099612698`: success.
- Private signed APK on MBMPC: `%LOCALAPPDATA%\\BCP-Universal-Remote\\G2-v111-build\\BCP-Universal-v1.1.1-SIGNED.apk`.
- VersionCode 15, versionName `1.1.1-tailscale-443-fix`, 62,199 bytes, SHA256 `60793E3FF7D8F058DA3DDF363EB26E98D566158705B6FE847326893E313FD947`, original R3.3 signing identity verified.
- Published to single atomic stable feed `https://mbmpc.taild48ba2.ts.net/updates/stable.json`: versionCode=15.
- Real JVM signed `POST /v1/status` to **HTTPS 443 via Tailscale Serve** passed with HMAC response verified, after JVM-only host mapping for local Windows DNS (no Windows hosts/network change). Port 100 still rejected. Note: field Android status still pending.
- Production tests: TLS 1.3 HTTPS stable manifest and APK length/hash/mode: PASS; HMAC protected status RPC: PASS; pairing route: PASS.

## Remaining proof
The phone has not been observed to install v1.1.1 yet. At 18:36 Windows local, the last **Android-classified** update request was 18:29 local (the phone likely backgrounded/closed). The 18:36 requests were from PC tests, not the Samsung. `state/g2-phone-status.json` remains absent, and must not be described as operational Android reporting until a genuine POST from the Samsung writes it.

## Next smallest field step
User simply opens BCP and leaves it visible with Tailscale connected. In development mode it should request stable v1.1.1 automatically (within ~30 seconds); Android may still request installation confirmation according to its policies. Do not manually tap `Vérifier la mise à jour` for this field test. After install, keep BCP visible long enough for its signed phone-status report; verify report is real and contains only versionCode, network, update_state and timestamp. If report remains absent while v1.1.1 is installed, investigate based on server outcome logs rather than speculate.

## Architecture boundaries
G2 app controls only read-only status/diagnostics, plus user-authorized legacy USB file operations. Full Windows admin commands/GUI and native ChatGPT control (G4/G5) are NOT implemented. Do not expose legacy HTTP on WAN or use Tailscale Funnel. Never log private pairing key or share signed secret in GitHub.
