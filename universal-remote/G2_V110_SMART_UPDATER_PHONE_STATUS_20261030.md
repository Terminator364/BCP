# BCP Universal Remote — G2 intelligent updates + first phone status (2026-10-30)

## Version shipped
- Android version **1.1.0**, versionCode 14, package `com.blessing.rescuebridge`.
- Git branch: `feat/universal-remote-transport-20261030`, source commit `000d730e85e9008b69946fcfc9e68f2f9890320f`.
- GitHub Actions build: run `41096794598`, completed success, unsigned artifact metadata validated.
- Signed on MBMPC with existing R3.3 release identity. `62199` bytes, SHA256 `138480E111BC7A030B889AF3AFB452A8C4E72F3BED4E271A13A4AFA90A2CB965`.
- Published atomically to `https://mbmpc.taild48ba2.ts.net/updates/stable.json` and `/updates/stable.apk`. Production HTTPS TLS 1.3: version 14, size and SHA256 all PASS.
- Legacy `BCP-USB-Rescue` left untouched. G2 read-only PC pilot preserved.

## Adaptive updater
- Development activity derived **automatically** on MBMPC from source file modification, branch commit, or stable release modification. `/updates/mode.json` sends `development` when the last activity was within four hours; it sends `normal` afterwards.
- **30-second checks are only while Android activity is visible**; Android periodic JobScheduler remains at best-effort 15-minute intervals when app is in background, including Doze delays.
- Normal foreground check is approximately 15 minutes, and immediate checks remain on app version change. 4G/5G and Wi-Fi both supported; no phone-to-PC tethering.
- Server mode is not an indication of ChatGPT reading the user's phone directly; it reads local project activity.

## Minimal phone status telemetry
- Android `BCPPhoneReporter.java` sends versionCode, network category and updater state to `/v1/phone-state` **only after one-time pairing**, using the existing HTTPS and HMAC protocol.
- Server verifies timestamp, HMAC and nonce anti-replay; restricts status fields and writes `state/g2-phone-status.json` without device identifiers, secrets, IP or app files.
- Python staging tests: 8/8 PASS (mode, four-hour bounds, HMAC request and response, restricted fields, replay denial and anonymous denial).
- Java client-to-G2 staging test PASS (signed phone state, signed reply, certificate spoof rejected).
- Fake staging status was restored/removed. As of release check, **no genuine Android status file yet**.
- Actual phone state and installed v1.1 are NOT verified; first pairing still pending.

## Field pairing — next
1. On MBMPC desktop, open `BCP - Appairer mon telephone.cmd`. It shows a one-time 8-digit code valid 10 minutes. Do not paste code in ChatGPT.
2. On Samsung BCP Universal Remote > Réglages > Appairage initial, enter code and choose `Associer définitivement mon téléphone`.
3. Return home and tap `Connecter mon PC (Wi-Fi / Tailscale)`.
4. Inspect the actual `g2-phone-status.json` on Windows; the phone should report only after the updated APK is installed, app is visible, and pairing succeeded.
5. Next work: expand PC capabilities beyond read-only, establish actual ChatGPT native integration, and robust recovery/USB/Bluetooth fallback.

## Boundaries
No continuous silent 30-second background polling was claimed; Android scheduler and foreground-service policies require respecting system protections. No Play Protect bypass or unsafe unknown-source modification. App update may ask for OS confirmation, even if a self-update is requested.
