from __future__ import annotations

import importlib.util
import pathlib
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "windows" / "bcp_server.py"
TELEGRAM = ROOT / "windows" / "bcp_telegram_observability.py"
RELAY = ROOT / "android-b-edge" / "src" / "main" / "java" / "com" / "blessing" / "bcpedge" / "EdgeRelayService.java"
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
    policy = POLICY.read_text(encoding="utf-8")
    manifest = MANIFEST.read_text(encoding="utf-8")

    assert '"api.telegram.org".equalsIgnoreCase' in policy
    assert "port != 443" in policy
    assert "MessageDigest.isEqual" in policy
    assert "MAX_CONNECTIONS = 4" in policy
    assert '"proxy-authorization"' in relay
    assert "CredentialStore(this).getToken()" in relay
    assert "FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING" in relay
    assert 'android:foregroundServiceType="remoteMessaging"' in manifest
    assert "FOREGROUND_SERVICE_REMOTE_MESSAGING" in manifest

    assert "http.client.HTTPSConnection" in telegram
    assert 'conn.set_tunnel(' in telegram
    assert '"Proxy-Authorization": "Bearer " + pair_token' in telegram
    assert 'BCP_PAIR_TOKEN_PATH = STATE_DIR / "bcp_token.txt"' in telegram
    assert 'parsed.hostname != "api.telegram.org"' in telegram
    assert 'EDGE_RELAY_FALLBACK_FAILED' in telegram
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
            result = bcp.register_edge_relay(
                "192.168.44.23",
                {
                    "port": 8876,
                    "capability": "HTTPS_CONNECT_TELEGRAM",
                    "ttl_seconds": 300,
                    "edge_version": "test-edge",
                },
            )
            assert result["ok"] is True
            assert result["active"] is True
            assert result["relay_host"] == "192.168.44.23"
            assert result["relay_port"] == 8876
            assert result["expires_in_seconds"] == 300

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
