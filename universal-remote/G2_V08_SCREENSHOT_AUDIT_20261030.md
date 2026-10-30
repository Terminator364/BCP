# BCP Universal Remote — Android screenshot audit and v0.8.0 corrective release

Date: 2026-10-30
Branch: feat/universal-remote-transport-20261030
Commit: d922e224b163f36b68320d8c8973f81827a81393
CI: https://github.com/Terminator364/BCP/actions/runs/41090970245 (success)
Package: com.blessing.rescuebridge
Version code: 10
Version name: 0.8.0-g2-status-update

## Screenshot evidence (Samsung)
- v0.7.0 installed in-place; home screen had "Configuration requise" / "Adresse du PC absente" (legacy USB check)
- Missions UI still imports manual JSON; Files still bounded to test workspace
- Settings has 8-digit first-pairing field
- Screenshot shows 4G+ cellular with Tailscale icon; updater intentionally uses unmetered networking only

## Changes in v0.8
- Home screen uses Android Keystore secure pairing state, not legacy host field; no IP entry necessary for G2
- Exact pairing launcher name in UI: "BCP - Appairer mon telephone" on Windows Desktop
- Missions and Files descriptions explicitly identified as old USB pilot, not full admin or ChatGPT-native control
- Same Android applicationId and locally retained release signing identity; user data intended to survive update

## Verified checks
- Android release APK compile and metadata: CI success
- Signed local APK: 58,103 bytes; SHA256 ECBE85FB63E2BFC7EA683CDCE0FA94E09AD60BEF30513186C3DCE978850B029C
- Signature verified as same signing identity as R3.3
- Stable update manifest: versionCode=10, package preserved; served on Tailscale private HTTPS TLS 1.3
- End-to-end Tailscale HTTPS version/size/SHA tests all passed
- HMAC-signed Windows status RPC: PASS
- Pairing route exists through HTTPS Serve and rejects malformed pairing payload: PASS
- One-time pairing security was tested on PC: wrong PIN denied, single-use accepted, replay denied, five-attempt cap; PIN/key not logged
- No physical Android install or self-updater end-to-end success observed for v0.8
- No full Windows admin or ChatGPT-native execution yet; preserve this distinction.

## Immediate next field step
On MBMPC, user opens desktop shortcut "BCP - Appairer mon telephone"; app Settings > enter 8-digit code (do not reveal in chat). Phone Tailscale stays connected. Return to Home > Connecter mon PC. If successful, report authenticated status; if not, report error screen. For v0.8 update, use unmetered Wi-Fi; Android might require one-time permission for installing app updates.

## Delivery
v0.7 already installed by user; do not resend v0.5 or v0.7 as a separate manual APK. v0.8 distributed from BCP stable update feed, not via Telegram by default.
