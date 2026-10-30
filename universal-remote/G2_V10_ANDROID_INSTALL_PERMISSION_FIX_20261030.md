# BCP Universal Remote — Android install-permission gate, screenshot at 17:47 (2026-10-30)

## New screenshot, decisive interpretation
The Samsung app footer displays **0.7.0**. The update card says:
"Mise à jour vérifiée et prête : autorisation Android d'installation nécessaire."
This proves the installed updater has a verified APK cached and `PackageManager.canRequestPackageInstalls()` returned false. This is **not a network outage or slow Wi-Fi**. The user must grant the system's "Allow from this source" permission to this APK installer once. Android may still require final installation confirmation according to its security policy.

## Status of pending versions
Windows build directories retain old releases v0.6–v0.9 but production `updates/stable.json` holds only **one** stable release, replaced atomically. The ChatGPT Delivery queue does **not** contain two BCP APKs; the old v0.5 was moved to Archives. A cached APK within the Android app may still be an earlier build; its version cannot be determined from the screenshot without device inspection.

## Concrete source issue fixed for subsequent updates
Original v0.7 onResume called only `checkForeground`, not `resumePending`. After Android granted the package install source permission, a second press of "Installer si Android le demande" was required. Additionally `checkForeground` had a 4-hour throttle stored across app upgrades, delaying the next release check.

## v1.0.0 release proof
- Source commit `c1ab603f873c2f16bad4415664df41234cf87c33` on branch `feat/universal-remote-transport-20261030`
- CI run `41093668179`: PASS
- Android `com.blessing.rescuebridge`, versionCode 12, `1.0.0-update-resume`
- Windows-signed APK: `%LOCALAPPDATA%\\BCP-Universal-Remote\\G2-v10-build\\BCP-Universal-v1.0.0-SIGNED.apk`, 58103 bytes
- Signed SHA256 `CFA346965128764BF3A99C9B410EDF9D2F535C23D32EF4B6DE805B622CBA2AA5`, existing R3.3 identity matches.
- Production private update feed `https://mbmpc.taild48ba2.ts.net/updates/stable.json`: versionCode 12 ONLY.
- Tests: HTTPS TLS1.3 feed/size/version/hash 9/9 PASS, HMAC signed RPC PASS, pairing route negative test PASS.
- Physical Samsung update from v0.7 to v1.0 NOT YET VERIFIED.

## Changes
1. On foreground resume, enqueue the verified pending install attempt once permission is granted; avoid repeated PackageInstaller sessions for 90 seconds.
2. After update or first launch, check the current version even if prior four-hour throttle has not expired.
3. Clear stale pending entries if installer already succeeded.
4. Preserve all-network (Wi-Fi and cellular) policy; no tethering to Windows.

## One-time field transition for v0.7 (user action)
1. From BCP Settings > update card: tap "Installer si Android le demande".
2. When Android opens per-source unknown apps settings, grant permission specifically to BCP Universal Remote (not system-wide); return to app.
3. As stable advanced while the old APK was cached, tap "Vérifier la mise à jour" ONCE to pull v1.0 directly; with permission now granted, v0.7 check() should request install automatically.
4. Accept Android's system installer dialog if shown; if absent, press "Installer si Android le demande" and capture status.
5. Confirm app footer shows **1.0.0** (not v0.7) and G2 pairing UI preserved.

Do not claim Android unattended install proven until actual phone evidence. Do not uninstall or clear app data.
