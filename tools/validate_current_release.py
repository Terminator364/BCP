from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "release" / "current.json"
SERVER = ROOT / "release" / "server.json"
ANDROID = ROOT / "release" / "android.json"
SERVER_SOURCE = ROOT / "windows" / "bcp_server.py"
SPEC = ROOT / "docs" / "CANONICAL_PRODUCT_REQUIREMENTS.md"


def fail(message: str) -> None:
    raise SystemExit("BCP_CURRENT_RELEASE_INVALID: " + message)


def load(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        fail(path.as_posix() + " not object")
    return obj


def is_sha(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value or ""))


def main() -> int:
    cur = load(CURRENT)
    srv = load(SERVER)
    edge = load(ANDROID)
    source = SERVER_SOURCE.read_bytes()
    spec = SPEC.read_text(encoding="utf-8")

    if cur.get("schema") != "bcp.current_release/1":
        fail("schema")
    if cur.get("channel") != "CURRENT":
        fail("channel")
    if cur.get("zero_usd") is not True:
        fail("zero_usd")
    policy = cur.get("update_policy") or {}
    required_policy = {
        "unchanged_version_zero_download": True,
        "metered_large_download_default": False,
        "hash_verification_required": True,
        "rollback_required": True,
        "scheduled_chatgpt_automation": False,
    }
    for key, expected in required_policy.items():
        if policy.get(key) is not expected:
            fail("policy." + key)

    m = re.search(r"^Revision:\s*(\S+)", spec, re.M)
    if not m or m.group(1) != cur.get("requirements_revision"):
        fail("requirements_revision_not_current")

    components = cur.get("components") or {}
    pc = components.get("windows_bcp") or {}
    android = components.get("android_b_edge") or {}
    nexus = components.get("nexus") or {}

    actual_server_sha = hashlib.sha256(source).hexdigest()
    if pc.get("version") != str(srv.get("version")):
        fail("server_version_drift")
    if pc.get("artifact", {}).get("url") != str(srv.get("url")):
        fail("server_url_drift")
    if pc.get("artifact", {}).get("sha256") != str(srv.get("sha256")):
        fail("server_manifest_sha_drift")
    if actual_server_sha != str(srv.get("sha256")):
        fail("server_source_sha_drift")
    if pc.get("distribution_ready") is not True or pc.get("auto_update_eligible") is not True:
        fail("server_distribution_contract")

    if android.get("version") != str(edge.get("version_name")):
        fail("android_version_drift")
    if str(edge.get("minimum_server_version")) != str(srv.get("version")):
        fail("component_compatibility_drift")

    edge_url = str(edge.get("apk_url") or "")
    edge_sha = str(edge.get("apk_sha256") or "")
    edge_ready = bool(edge_url and is_sha(edge_sha))
    if bool(android.get("distribution_ready")) != edge_ready:
        fail("android_distribution_truth_mismatch")
    if bool(android.get("auto_update_eligible")) != edge_ready:
        fail("android_auto_update_truth_mismatch")

    nexus_ready = bool(nexus.get("artifact", {}).get("url") and is_sha(nexus.get("artifact", {}).get("sha256") or ""))
    if bool(nexus.get("distribution_ready")) != nexus_ready:
        fail("nexus_distribution_truth_mismatch")

    all_ready = bool(pc.get("distribution_ready") and android.get("distribution_ready") and nexus.get("distribution_ready"))
    overall = str(cur.get("overall_state") or "")
    if all_ready and overall == "CI_QUALIFIED_DISTRIBUTION_INCOMPLETE":
        fail("overall_state_underclaims_ready")
    if not all_ready and overall != "CI_QUALIFIED_DISTRIBUTION_INCOMPLETE":
        fail("overall_state_overclaims_ready")

    print(json.dumps({
        "schema": cur["schema"],
        "overall_state": overall,
        "server": {"version": pc["version"], "distribution_ready": pc["distribution_ready"]},
        "android": {"version": android["version"], "distribution_ready": android["distribution_ready"]},
        "nexus": {"version": nexus["version"], "distribution_ready": nexus["distribution_ready"]},
        "zero_usd": True,
    }, sort_keys=True))
    print("BCP_CURRENT_RELEASE_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
