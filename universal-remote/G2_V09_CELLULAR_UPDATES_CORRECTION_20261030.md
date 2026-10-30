# BCP Universal Remote v0.9.0 — Cellular updates correction (2026-10-30)

## User decision
The Wi-Fi-only, unmetered-only update policy was an assistant-introduced constraint and was not authorized by the user. User wants automatic security-verified updates on Wi-Fi **and mobile data**, without requiring a Wi-Fi switch. No automatic mobile tethering to Windows.

## Source + build
- Branch: feat/universal-remote-transport-20261030
- Commit: 8c9313155ba1a995a0ae6cbdcb0ef3c914000530
- GitHub Actions CI: https://github.com/Terminator364/BCP/actions/runs/41091931194 — success
- Android package: com.blessing.rescuebridge
- Version: 0.9.0-updates-any-network, versionCode 11
- Signed APK on MBMPC: %LOCALAPPDATA%\\BCP-Universal-Remote\\G2-v09-build\\BCP-Universal-v0.9.0-SIGNED.apk
- Bytes: 58103
- SHA256: 5F2FE787E1608D4A725F73A2513E618280316D1BFFF780BF888B6AD00052DACC
- Private signing identity unchanged (verified same as R3.3).
- Production stable feed `https://mbmpc.taild48ba2.ts.net/updates/stable.json` now advertises code 11.
- APK feed `https://mbmpc.taild48ba2.ts.net/updates/stable.apk` HTTPS TLS1.3, 58103 bytes, hash exact.

## Corrected Android logic
- Deleted early rejection when `isActiveNetworkMetered()` is true.
- Changed Android JobScheduler from `NETWORK_TYPE_UNMETERED` to `NETWORK_TYPE_ANY`.
- Migration: cancels previously scheduled Wi-Fi-only job, then installs new network-any job, preventing an old constraint from persisting.
- App explanation explicitly says updates available over Wi-Fi and mobile data.
- No automatic tethering or change of PC network settings.

## Tests
- CI compile and artifact: PASS.
- Local APK signing and original identity: PASS.
- Production Tailscale HTTPS feed: 9/9 PASS.
- Signed RPC via Serve (TLS1.3, response HMAC): PASS.
- Pairing route negative test via Serve: PASS.
- Installation and unattended update behavior on actual Samsung: NOT YET VERIFIED.

## Bootstrap migration issue
The currently installed 0.7.x app blocks update downloads on metered cellular networks. Updating code on the server cannot magically change this installed client's behavior. One-time transition options:
A) Connect to an unmetered Wi-Fi network once; current updater fetches the stable 0.9.0; after that cellular is allowed for subsequent releases.
B) If user expressly wants immediate mobile-data migration: install the exact signed v0.9.0 once using the private stable APK URL / controlled ChatGPT Delivery. This is a one-time exception to the no-manual-APK policy. No uninstall; preserve pairing data.
We should not claim 0.9.0 already installed.

## Do not regress
Never reintroduce billing-based network restrictions without explicit user authorization. Prioritize trustworthy signing and data integrity; cellular data usage should be transparent but not silently blocked.
