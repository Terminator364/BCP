from __future__ import annotations
import json
import sys
from pathlib import Path

def fail(msg: str, code: int = 2) -> int:
    print(msg, file=sys.stderr)
    return code

def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != "register":
        return fail("usage: cli.py register <manifest>")
    p = Path(sys.argv[2])
    raw = p.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return fail("manifest_has_utf8_bom", 11)
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        return fail(f"manifest_utf8_json_invalid: {e}", 12)
    for key in ("app_id", "display_name", "install_root"):
        if not data.get(key):
            return fail(f"missing_{key}", 13)
    root = Path(data["install_root"])
    marker = root / "PCA_MANAGED_APP_APPROVED.json"
    try:
        approval = json.loads(marker.read_text(encoding="utf-8"))
    except Exception as e:
        return fail(f"approval_marker_invalid: {e}", 14)
    if approval.get("approved") is not True or approval.get("app_id") != data["app_id"]:
        return fail("approval_marker_contract_failed", 15)
    print(json.dumps({"registered": data["app_id"], "contract": "chatgpt-pc-register/1"}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
