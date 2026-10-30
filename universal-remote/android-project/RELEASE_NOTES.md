# BCP Universal G2 Android prototype
versionCode 7; retains applicationId com.blessing.rescuebridge and the same signing certificate.

Main button: Wi-Fi LAN preferred, private Tailscale fallback, physical USB rescue retained.
Authenticated status/diagnostics only. No automatic mobile data sharing; no ChatGPT-native execution.
G2 requires an existing encrypted app pairing key. Do not expose key in chat.
TLS pin and current MBMPC LAN IP are initial field values; must become dynamic for general release.
Build unsigned in GitHub Actions; sign only on the authorized MBMPC Windows machine.
