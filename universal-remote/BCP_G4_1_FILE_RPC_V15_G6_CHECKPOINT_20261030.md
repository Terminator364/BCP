# BCP — checkpoint G4 file RPC + Android v1.5 source + G6, 2026-10-30

Recovery code: `BCP|UNIVERSAL|SYNC|MASTER`
Repository: `Terminator364/BCP`, branch `feat/universal-remote-transport-20261030`
Canonical index: `universal-remote/BCP_UNIVERSAL_SYNC_MASTER.json`

## PRODUCTION: verified live
- MBMPC Windows, G2 HTTPS authenticated service on LAN and Tailscale preserved, signed TLS 1.3 RPC and G2 pairing probe PASS.
- G4 individual-device registry + signed owner inventory + `/v1/g4/owner/files` **deployed**.
- First deployment of signed owner file route had 102/102 preflight tests, 16/16 G4 production negative tests, 12/12 owner-file negative tests, and rollback backup `backups/G4_1_INDIVIDUAL_20261030_225411`.
- Follow-up G4 recovery change additionally deployed with 105/105 preflight, 16/16 G4 production negative and 12/12 file negative over live TLS; rollback backup `backups/G4_1_INDIVIDUAL_20261030_230328`.
- The transfer status now returns a SHA-256 receipt for committed transfers, allowing Android to detect a commit whose final response was lost.
- **No real owner profile activated**, `pending-devices` had **0 pending requests** at last check; therefore the live file write endpoint correctly denies legacy shared-G2-key-only clients.
- Samsung actual authenticated phone report: `2026-10-30T21:49:26.526731+00:00`, `version_code=18`, `network=wifi`, `app_visible=true`, `update_state=current`. **v1.4.0 installed on actual phone**, not just published.
- Desktop shortcut `BCP - Profil proprietaire.lnk` exists on MBMPC.

## Completed lab evidence on real MBMPC (ephemeral test files)
- Owner file positive synthetic TLS end-to-end: 30/30 PASS, including two independent device identities, resumed streamed bytes, full SHA, revoked A denied, B still allowed and recovery of completed receipt.
- Owner transaction unit lab: 16/16 PASS; G4 owner RPC lab: 13/13 PASS.
- G4 durable queue real process lifecycle + resource guard: 26/26 PASS. Synthetic safe Python programs only; output, cancellation, dependencies, crash-recover, low-RAM deferral and resumption.
- G6 resource governor: 24/24 PASS, native Windows sample 3738 MiB usable RAM, 437 MiB free at sample; no settings modified or processes killed.
- Earlier G6 network policy deterministic: 19/19 PASS; **does NOT demonstrate physical USB or Bluetooth fallback**.
- Earlier G5 idempotency ledger: 21/21 PASS, still local-only.

## ANDROID v1.5 next candidate: NOT published
- New `BCPG4FileUploader.java` and `BCPG4FileTransferActivity.java` in source, access via BCP Files tab.
- URI-based source selection from Android SAF, user-selected Windows destination, per-device HMAC, 64KiB streamed chunks, SHA-256 whole-file and per-chunk, resumable persisted upload state, server-authoritative offset reconciliation, committed receipt verification.
- New candidate `versionCode=19`, `versionName=1.5.0-g4-file-upload-candidate`.
- Direct Java17 Android API compile GitHub Actions run `41135627880`: **SUCCESS**.
- Full Gradle APK workflow runs for candidate **FAILED BEFORE JAVA COMPILE** because GitHub runners could not retrieve upstream Kotlin Gradle dependency `org.jetbrains.kotlin:kotlin-stdlib-jdk8:1.9.20` despite the artifact existing in Maven Central. One rerun failed the same way. **No signed v1.5 APK**; leave signed v1.4 stable manifest unchanged.
- Do not claim real on-device v1.5 upload tested.

## G5 plan
- `universal-remote/G5_CHATGPT_NATIVE_MCP_ARCHITECTURE_20261030.md` created.
- Prefer private Secure MCP Tunnel, not public Tailscale Funnel. Native full MCP write tools have plan/workspace restrictions. ChatGPT-native BCP plugin **not installed**; currently connected Remote Desktop Commander is a working fallback.
- Use a separate ChatGPT cryptographic client identity, local owner consent, OAuth/scopes when needed, idempotency ledger. Never piggyback on Android shared pairing secrets.

## G3 USB/Bluetooth
- ADB not on PATH, though legacy BCP archives may contain it elsewhere.
- Windows PnP Bluetooth inventory query was abnormally slow on the 4GB PC; result inconclusive, not a successful physical Bluetooth test. Do not repeatedly run unbounded PnP queries. A process-session termination was attempted but not fully confirmed. Future probes must have strict timeouts, low CPU and avoid logging device serials.
- No physical USB/Bluetooth transport authenticated end to end in this tranche.

## Next human gate (ONE local approval)
1. On the **actual Samsung v1.4 app**: Fichiers → Identité propriétaire G4 → **Demander mon code unique**.
2. On MBMPC: double-click **BCP - Profil proprietaire** shortcut, select this Samsung's pending request, type the phone's six-digit code, and approve locally.
3. Back on Samsung: **Tester mon accès propriétaire**. Capture a real phone-signed inventory response before claiming owner-wide control is working.
4. This approval does not bypass Windows ACL/UAC and does not give another device the same identity.

## Engineering continuity
After a lane blocks, advance other safe independent lanes, then retry the blocked lane. Never rebase/restart project or claim that staged code was deployed. Record each verified change in the canonical master. No work continues by itself once the current tool turn ends unless a separately authorized automation is created.
