from __future__ import annotations

import importlib.util
import pathlib
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "windows" / "bcp_server.py"
TELEGRAM = ROOT / "windows" / "bcp_telegram_observability.py"
RELAY = ROOT / "android-b-edge" / "src" / "main" / "java" / "com" / "blessing" / "bcpedge" / "EdgeRelayService.java"
TLS_IDENTITY = ROOT / "android-b-edge" / "src" / "main" / "java" / "com" / "blessing" / "bcpedge" / "EdgeTlsIdentity.java"
POLICY = ROOT / "android-b-edge" / "src" / "main" / "java" / "com" / "blessing" / "bcpedge" / "EdgeRelayPolicy.java"
MANIFEST = ROOT / "android-b-edge" / "src" / "main" / "AndroidManifest.xml"


def load_server():
    spec = importlib.util.spec_from_file_location("bcp_server_relay_test", SERVER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    telegram = TELEGRAM.read_text(encoding="utf-8")
    relay = RELAY.read_text(encoding="utf-8")
    tls_identity = TLS_IDENTITY.read_text(encoding="utf-8")
    policy = POLICY.read_text(encoding="utf-8")
    manifest = MANIFEST.read_text(encoding="utf-8")

    assert '"api.telegram.org".equalsIgnoreCase' in policy
    assert "port != 443" in policy
    assert "MessageDigest.isEqual" in policy
    assert "HmacSHA256" in policy
    assert "BCP-HMAC-SHA256" in policy
    assert "API_TLS_PORT = 8877" in policy
    assert "MAX_CONNECTIONS = 4" in policy
    assert '"proxy-authorization"' in relay
    assert "AUTH_REPLAY_REJECT" in relay
    assert "EdgeTlsIdentity.createServerSocket" in relay
    assert "TLS_API_LISTENING" in relay
    assert '"AndroidKeyStore"' in tls_identity
    assert "SSLServerSocket" in tls_identity
    assert '"TLSv1.3"' in tls_identity and '"TLSv1.2"' in tls_identity
    assert "CredentialStore(this).getToken()" in relay
    assert "FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING" in relay
    assert "FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE" in relay
    assert "DEDICATED_EDGE_API_SERVER" in relay
    assert '"/v1/node/status"' in policy
    assert '"/v1/node/sync"' in policy
    assert '"/v1/node/jobs"' in policy
    assert '"/v1/node/shell"' not in policy
    assert "EdgePresenceAdvertiser" in relay
    assert 'android:foregroundServiceType="remoteMessaging|connectedDevice"' in manifest
    assert "FOREGROUND_SERVICE_CONNECTED_DEVICE" in manifest
    assert "RECEIVE_BOOT_COMPLETED" in manifest
    assert "NEARBY_WIFI_DEVICES" in manifest
    assert "BLUETOOTH_SCAN" in manifest
    assert "ACCESS_COARSE_LOCATION" in manifest
    assert "ACCESS_FINE_LOCATION" in manifest
    assert "POST_NOTIFICATIONS" in manifest
    assert "FOREGROUND_SERVICE_REMOTE_MESSAGING" in manifest

    assert "http.client.HTTPSConnection" in telegram
    assert 'conn.set_tunnel(' in telegram
    assert "BCP-HMAC-SHA256" in telegram
    assert "_relay_proxy_authorization" in telegram
    assert "hmac.new(" in telegram
    assert "edge_api_json" in telegram
    assert "edge_tls_pin_mismatch" in telegram
    assert "getpeercert(binary_form=True)" in telegram
    assert 'BCP_PAIR_TOKEN_PATH = STATE_DIR / "bcp_token.txt"' in telegram
    assert 'parsed.hostname != "api.telegram.org"' in telegram
    assert 'EDGE_RELAY_FALLBACK_FAILED' in telegram
    assert 'TRANSPORT_ROUTE_PATH = STATE_DIR / "telegram_transport_route.json"' in telegram
    assert 'record_transport_route("DIRECT_TELEGRAM", "PROVIDER_REACHABLE")' in telegram
    assert '"B_EDGE_RELAY",' in telegram and '"PROVIDER_REACHABLE"' in telegram
    assert '"NO_WORKING_OUTBOUND_ROUTE",' in telegram
    # The Telegram bot token must not be used as proxy authentication.
    proxy_section = telegram[telegram.index("def _json_via_edge"):telegram.index("def json(", telegram.index("def _json_via_edge"))]
    assert "self.token" not in proxy_section
    assert "telegram_bot_token" not in proxy_section

    bcp = load_server()
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        bcp.EDGE_RELAY_STATE_PATH = root / "edge_relay.json"
        now = 2_000_000
        original_time = bcp.time.time
        try:
            bcp.time.time = lambda: float(now)
            secure_fp = "a" * 64
            result = bcp.register_edge_relay(
                "192.168.44.23",
                {
                    "port": 8876,
                    "capability": "HTTPS_CONNECT_TELEGRAM",
                    "ttl_seconds": 300,
                    "edge_version": "2.2.0-full-node",
                    "api_scheme": "https",
                    "api_port": 8877,
                    "api_tls_sha256": secure_fp,
                    "relay_auth": "BCP_HMAC_SHA256",
                    "relay_long_lived_bearer_on_lan": False,
                },
            )
            assert result["ok"] is True
            assert result["active"] is True
            assert result["relay_host"] == "192.168.44.23"
            assert result["relay_port"] == 8876
            assert result["expires_in_seconds"] == 300
            assert result["secure_api_ready"] is True
            assert result["api_port"] == 8877
            assert result["api_tls_sha256"] == secure_fp
            assert result["relay_auth"] == "BCP_HMAC_SHA256"
            assert result["long_lived_bearer_on_relay_lan"] is False

            try:
                bcp.register_edge_relay(
                    "192.168.44.23",
                    {
                        "port": 8876,
                        "capability": "HTTPS_CONNECT_TELEGRAM",
                        "api_scheme": "https",
                        "api_port": 8877,
                        "api_tls_sha256": "bad",
                        "relay_auth": "BCP_HMAC_SHA256",
                    },
                )
                raise AssertionError("invalid TLS fingerprint unexpectedly accepted")
            except ValueError as exc:
                assert "fingerprint_invalid" in str(exc)

            try:
                bcp.register_edge_relay(
                    "8.8.8.8",
                    {"port": 8876, "capability": "HTTPS_CONNECT_TELEGRAM", "ttl_seconds": 300},
                )
                raise AssertionError("public relay registration unexpectedly accepted")
            except ValueError as exc:
                assert "private_lan" in str(exc)

            try:
                bcp.register_edge_relay(
                    "192.168.44.23",
                    {"port": 8888, "capability": "HTTPS_CONNECT_TELEGRAM", "ttl_seconds": 300},
                )
                raise AssertionError("wrong port unexpectedly accepted")
            except ValueError as exc:
                assert "port_not_allowed" in str(exc)

            bcp.time.time = lambda: float(now + 301)
            expired = bcp.edge_relay_status()
            assert expired["active"] is False
            assert expired["relay_host"] == ""
        finally:
            bcp.time.time = original_time

    print("BCP_BEDGE_RELAY_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
