# BCP Universal Remote — G2 Android release (30 Oct 2026)

## Deliverable
- Android package: `com.blessing.rescuebridge`, versionCode **7**, versionName **0.5.0-g2-universal-lan-tailnet**.
- Release APK on MBMPC: `%LOCALAPPDATA%\\BCP-Universal-Remote\\G2-build\\BCP-Universal-G2-v0.5.0-SIGNED.apk`.
- Size **49,911 bytes**. SHA256 `0E6F4D007D2194BBA51E459789A745E59A78A335F8DC95B71139AE0075F1281A`.
- Signature verified using existing *local-only*, DPAPI-protected signing identity. Certificate matches R3.3 and V4 signer. No keystore or passphrase sent to GitHub or chat.
- GitHub Actions CI run 41081560626: Android release compilation, package metadata and artifact upload completed successfully (unsigned artifact from GitHub, signed only on MBMPC).
- Binary tested as ZIP/Dex with manifest/package and matched CI SHA256 before signing.
- Delivery via Tailscale Serve HTTPS private tailnet, fixed download route, signed hash verified **through the TLS 1.3 proxy**; wrong host rejected; no public Funnel.
- BCP G2 Windows agent remains read-only for status/diagnostics; legacy USB Rescue preserved; Tailscale service automatic and G2 Windows startup configured.

## App changes
- Same Android applicationId and signing key for in-place update. No uninstall intended.
- Home primary button attempts **local Wi-Fi** to private PC host and then private **Tailscale** endpoint, both HTTPS/HMAC.
- Existing USB button retained as fallback; no Wi-Fi/4G tethering to Windows.
- If no app pairing key exists, displays that secure appairage initial is necessary; does not send secrets in chat.
- HTTPS client enforces certificate pinning for LAN and public CA for the Tailscale Serve hostname, verifies HMAC response.
- Download is *not* a completed Android physical installation: Samsung APK install, actual TLS request from installed app, and stored pairing key state remain **UNVERIFIED**.

## Outstanding issues
1. Device-level installation and signed update over R3.3/V4 (phone not present over ADB).
2. Wi-Fi LAN inbound firewall from Samsung to Windows G2 port still needs real field verification; no inbound firewall rule was configured during G2. Tailscale fallback confirmed at TCP/HTTPS level, not from APK.
3. Pairing provisioning without manual 64-character key (QR/physical proof) to build.
4. Full Windows admin command/file/GUI agent (G4), ChatGPT bridge (G5), Bluetooth fallback (G3): not yet delivered.
5. Address and TLS identity values in v0.5 are *specific to first MBMPC*: future configurable discovery/binding and cert renewal needed.

## Safety / privacy
Network links are authenticated. A publicly visible source repository is **not** a place for private pairing secrets. All secrets remain on MBMPC.
