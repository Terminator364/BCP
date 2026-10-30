# BCP G2 — Samsung pairing verified, v1.1 upgrade bootstrap (30 Oct 2026)

## Field proof at approximately 18:23 Kinshasa / Windows local time
- User Samsung screenshot: `MBMPC connecté`, `Canal Wi-Fi local · HTTPS et HMAC vérifiés · mode G2 lecture/diagnostic`. This is real, not a simulated pairing.
- Screenshot Settings still reads `BCP Universal Remote · 1.0.0` and `Application à jour · version 12` (Android versionCode 12). This status reflects the last client check, not a fresh server fetch.
- MBMPC Tailscale online: 100.109.148.51; Samsung online: 100.119.168.75. Windows G2 listeners active on 127.0.0.1, Wi-Fi 192.168.168.106 and Tailscale 100.109.148.51.
- Production `updates/stable.json` only has one stable release: **v1.1.0 (versionCode 14)**, 62,199 bytes, SHA256 `138480e111bc7a030b889af3afb452a8c4e72f3bed4e271a13a4afa90a2cb965`.
- `state/g2-update-checks.jsonl` had only two requests after release deployment: `GET /updates/stable.json` and `GET /updates/stable.apk`, both classified as non-Android test clients at 2026-10-30T17:17:53Z. **No Android update request after release observed as of Windows 18:25+01**.
- `state/g2-phone-status.json` absent: v1.0.0 cannot report this; the new authenticated heartbeat exists only in v1.1.

## Cause
v1.0.0 checks on activity resume and via Android JobScheduler, but does not run the new every-30-second visible-app development poll. The phone remains on stale cached updater status. Server-side publishing cannot force a version not yet installed to request an update. Android does not guarantee 15-minute or 24-hour periodic jobs at an exact time.

## Minimal one-time migration
User must launch the current app Settings -> `Vérifier la mise à jour` **once** while connected to Tailscale (Wi-Fi or 4G). Server now offers direct v1.1.0 without intermediate 1.0.1. The update client verifies signed APK and attempts install; Android may present system package-installer or Play Protect confirmation. Keep old app installed and app data.
Afterwards, Settings footer must show v1.1.0, and if app is foregrounded during the four-hour local development window, update polls every 30s, otherwise foreground 15-minute fallback and OS-scheduled background checks. This functionality must still be field-verified, not asserted.

## Next validation
With v1.1 installed and paired, check `state/g2-phone-status.json` for authenticated first real phone report. Do not treat simulated PC-side Java and Python tests as phone evidence. Continue G3/G4/G5 only after verified G2 full field roundtrip.
