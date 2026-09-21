from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "windows" / "bcp_server.py"


def load_server():
    spec = importlib.util.spec_from_file_location("bcp_server_under_test", SERVER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    bcp = load_server()

    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        state = root / "state"
        state.mkdir(parents=True, exist_ok=True)

        bcp.STATE_DIR = state
        bcp.NEXUS_BOOTSTRAP_STATE_PATH = state / "nexus_bootstrap_delivery.json"
        bcp.NEXUS_BOOTSTRAP_RECEIPT_PATH = state / "nexus_bootstrap_receipt.json"

        bcp.atomic_json(
            bcp.NEXUS_BOOTSTRAP_STATE_PATH,
            {
                "schema": "bcp.nexus_bootstrap_delivery/1",
                "state": "HUMAN_AUTH_REQUIRED",
                "bundle_version": "0.2.6",
                "attempt_count": 1,
            },
        )
        bcp.atomic_json(
            bcp.NEXUS_BOOTSTRAP_RECEIPT_PATH,
            {
                "schema": "bcp.nexus_bootstrap_receipt/1",
                "state": "HUMAN_AUTH_REQUIRED",
                "bundle_version": "0.2.6",
                "error": "CLOUDFLARE_DEVICE_AUTH_REQUIRED_OR_EXPIRED",
            },
        )

        calls = []

        def fake_locked(auto_launch=True):
            calls.append(bool(auto_launch))
            return {
                "ok": True,
                "result": "LAUNCHED",
                "bundle_version": "0.2.6",
                "simulated_provider_boundary": True,
            }

        bcp._apply_nexus_bootstrap_delivery_locked = fake_locked

        result = bcp.apply_nexus_bootstrap_delivery(
            auto_launch=True,
            explicit_human_retry=True,
        )

        assert result["result"] == "LAUNCHED", result
        assert result["explicit_human_retry"] is True, result
        assert result["previous_receipt_archived"] is True, result
        assert calls == [True], calls

        state_after = json.loads(bcp.NEXUS_BOOTSTRAP_STATE_PATH.read_text(encoding="utf-8"))
        assert state_after["state"] == "EXPLICIT_RETRY_REQUESTED", state_after
        nonce = str(state_after.get("explicit_retry_nonce") or "")
        assert len(nonce) == 32, state_after
        assert not bcp.NEXUS_BOOTSTRAP_RECEIPT_PATH.exists()

        archive_dir = state / "nexus-auth-archive"
        archived = list(archive_dir.glob("nexus_bootstrap_receipt_*.json"))
        assert len(archived) == 1, archived
        latest = json.loads((archive_dir / "LATEST.json").read_text(encoding="utf-8"))
        assert latest["reason"] == "EXPLICIT_FRESH_DEVICE_FLOW_RETRY", latest

    print("BCP_NEXUS_EXPLICIT_RETRY_RUNTIME_SIMULATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
