# BCP Update Bottleneck – Android Screenshot Incident, 30 Oct 2026

## What actually happened
- Samsung screenshot at 17:47 shows v0.7.0 UI and **"Mise à jour vérifiée et prête : autorisation Android d'installation nécessaire."**
- This is **downloaded-but-not-installed** state. It is not a Tailscale fault or slow transmission.
- Android requires app-specific install-from-this-source permission before BCP can use PackageInstaller. On Android 12+ background updates can *sometimes* avoid confirmation if platform conditions hold; no promise of completely silent installation on all phones.
- v0.7.0 foreground updater throttles automatic re-check to 4 hours; periodic JobScheduler is 24 hours (non-exact). Five minutes on Wi-Fi is not a guarantee of auto-install.
- v0.7.0 may store one pending APK in internal `bcp-update-next.apk`; previous releases are not all queued by server. The stable feed advertises exactly one currently signed version at a time.
- After returning from install-source Settings, v0.7.0 requires user to trigger `Installer si Android le demande` again. Auto-resume is not part of installed v0.7.0.

## Corrections already built and actually deployed
- v0.9.0 removed metered-network blocking and migrated JobScheduler to `NETWORK_TYPE_ANY`.
- GitHub commit `c1ab603` created v1.0.0 (`versionCode=12`), adds automatic resume of a previously verified installation when returning from Android permission Settings, rate-limits repeated sessions, and forces fresh update check after app upgrade. CI: https://github.com/Terminator364/BCP/actions/runs/41093668179 (success).
- Signed v1.0.0 on MBMPC with the existing R3.3 release cert: APK 58,103 bytes, SHA-256 `CFA346965128764BF3A99C9B410EDF9D2F535C23D32EF4B6DE805B622CBA2AA5`, same signing certificate.
- Single current stable feed `https://mbmpc.taild48ba2.ts.net/updates/stable.json` points to `versionCode=12`; signed download `https://mbmpc.taild48ba2.ts.net/updates/stable.apk`. TLS1.3/manifest/byte-count/hash nine checks PASS; HMAC Windows G2 status regression PASS.
- ChatGPT Delivery active APK dispatch queue inspected: no BCP APK currently queued there; historic v0.5 archived.

## Required on-device step (current v0.7)
1. Open BCP -> Réglages -> `Installer si Android le demande`, grant Android per-app `Autoriser depuis cette source` for BCP.
2. Return to BCP; if Wi-Fi still available, `Vérifier la mise à jour` (manual check bypasses automatic 4h interval); wait for verified-ready. This fetches current **v1.0.0**, not a sequence.
3. Press `Installer si Android le demande` again on v0.7 and confirm any system installer dialog. **Do not uninstall app or erase data.**
4. If mobile only and v0.7 blocks new downloads: it can still install its pre-downloaded verified pending APK using same permission; once upgraded to v0.9+ it can fetch next stable over mobile, or use official signed stable URL as a one-time exceptional bootstrap.
5. Confirm actual version through app Settings after installation, not by elapsed time.

## Why ChatGPT lacks live Android view
- PC Desktop Commander is connected, but the Android app has no authenticated client-status/telemetry reporting into PC or ChatGPT currently. Tailscale connectivity does not grant inspection of app UI, permissions, package version, or installation state. An explicitly authorized signed status heartbeat and connector would be future work.
- Do not claim on-device silent update success without physical Samsung evidence.
