from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "windows" / "bcp_server.py"
RELAY = ROOT / "android-b-edge" / "src" / "main" / "java" / "com" / "blessing" / "bcpedge" / "EdgeRelayService.java"
API = ROOT / "android-b-edge" / "src" / "main" / "java" / "com" / "blessing" / "bcpedge" / "EdgeNodeApi.java"
CONNECTIVITY = ROOT / "android-b-edge" / "src" / "main" / "java" / "com" / "blessing" / "bcpedge" / "EdgeConnectivity.java"
BOOT = ROOT / "android-b-edge" / "src" / "main" / "java" / "com" / "blessing" / "bcpedge" / "EdgeBootReceiver.java"
MANIFEST = ROOT / "android-b-edge" / "src" / "main" / "AndroidManifest.xml"
POLICY = ROOT / ".project-memory" / "PHONE_PRIMARY_EDGE_SERVER_POLICY.json"
DOC = ROOT / "docs" / "PHONE_PRIMARY_EDGE_SERVER_R67.md"


def load_server():
    spec = importlib.util.spec_from_file_location("bcp_server_phone_node_test", SERVER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def ck(name: str, ok: bool):
    if not ok:
        raise AssertionError(name)
    print(f"{name}=PASS")


def main() -> int:
    relay = RELAY.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    connectivity = CONNECTIVITY.read_text(encoding="utf-8")
    boot = BOOT.read_text(encoding="utf-8")
    manifest = MANIFEST.read_text(encoding="utf-8")
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    doc = DOC.read_text(encoding="utf-8")

    ck("phone-role", "PHONE_PRIMARY_EDGE_SERVER" in relay and "PHONE_PRIMARY_EDGE_SERVER" in api)
    ck("local-api", all(x in api for x in [
        '"/health"', '"/v1/edge/status"', '"/v1/edge/capabilities"',
        '"/v1/edge/jobs"', '"/v1/edge/reconcile"', '"/v1/edge/sentinel"'
    ]))
    ck("auth-boundary", "isValidBearerAuthorization" in api and "UNAUTHORIZED" in api)
    ck("bounded-body", "MAX_BODY_BYTES = 64 * 1024" in api and "Payload Too Large" in relay)
    ck("durable-queue", "orchestrator.queueJob" in api and "ROOM_SQLITE_WAL" in api)
    ck("adaptive-capabilities", all(x in connectivity for x in [
        "FEATURE_WIFI_DIRECT", "FEATURE_BLUETOOTH_LE", "FEATURE_USB_HOST",
        "isDeviceOwnerApp", "isActiveNetworkMetered"
    ]))
    ck("boot-recovery", "RECEIVE_BOOT_COMPLETED" in manifest and ".EdgeBootReceiver" in manifest)
    ck("sticky-node", "START_STICKY" in relay)
    ck("no-general-proxy", '"api.telegram.org"' in (ROOT / "android-b-edge" / "src" / "main" / "java" / "com" / "blessing" / "bcpedge" / "EdgeRelayPolicy.java").read_text(encoding="utf-8"))
    ck("policy-role", policy["role"] == "PHONE_PRIMARY_EDGE_SERVER")
    ck("no-sim-assumption", policy["resource_intent"]["no_sim_required"] is True)
    ck("pc-specialist-not-center", policy["resource_intent"]["pc_role"] == "WINDOWS_SPECIALIST_AND_BURST_COMPUTE_NODE")
    ck("transport-ladder", [x["id"] for x in policy["transport_ladder"]][:4] == [
        "PRIVATE_LAN_OR_HOTSPOT", "USB_ADB_PORT_FORWARD", "WIFI_DIRECT", "BLUETOOTH_BLE_CONTROL"
    ])
    ck("usb-ci-plan", "adb forward" in doc)

    bcp = load_server()
    ck("server-version", bcp.SERVER_VERSION == "0.7.16")
    ck("server-phone-probe", hasattr(bcp, "edge_node_api_status"))

    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        bcp.EDGE_RELAY_STATE_PATH = root / "edge_relay.json"
        now = 2_000_000
        old_time = bcp.time.time
        bcp.time.time = lambda: now
        try:
            out = bcp.register_edge_relay("192.168.50.12", {
                "port": 8876,
                "capability": "HTTPS_CONNECT_TELEGRAM",
                "node_role": "PHONE_PRIMARY_EDGE_SERVER",
                "api_version": 1,
                "api_base": "/v1/edge",
                "capabilities": ["LOCAL_AUTHENTICATED_API", "DURABLE_ROOM_QUEUE"],
                "connectivity": {
                    "transports": ["WIFI"],
                    "internet": True,
                    "validated": True,
                    "metered": False,
                    "wifi_direct_supported": True,
                    "bluetooth_le_supported": True,
                    "usb_host_supported": True,
                    "device_owner": False,
                },
                "pending_jobs": 3,
                "ttl_seconds": 300,
                "edge_version": "2.2.0-rc1-phone-server",
            })
        finally:
            bcp.time.time = old_time

        ck("registration-active", out["active"] is True)
        ck("registration-role", out["node_role"] == "PHONE_PRIMARY_EDGE_SERVER")
        ck("registration-api", out["api_version"] == 1 and out["api_base"] == "/v1/edge")
        ck("registration-capabilities", "DURABLE_ROOM_QUEUE" in out["capabilities"])
        ck("registration-connectivity", out["connectivity"]["wifi_direct_supported"] is True)
        ck("registration-pending-jobs", out["pending_jobs"] == 3)

    print("BCP_PHONE_PRIMARY_EDGE_SERVER_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
