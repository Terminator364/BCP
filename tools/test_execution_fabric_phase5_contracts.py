from __future__ import annotations

import json
import pathlib
import sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
WINDOWS=ROOT/"windows"
sys.path.insert(0,str(WINDOWS))

from execution_fabric.release_controller import validate_transaction

load=lambda p: json.loads(p.read_text(encoding="utf-8"))

release_schema=load(ROOT/"schemas"/"bcp_release_transaction_v1.schema.json")
adapter_schema=load(ROOT/"schemas"/"bcp_project_adapter_v1.schema.json")
receipt_schema=load(ROOT/"schemas"/"bcp_action_receipt_v1.schema.json")
cap_schema=load(ROOT/"schemas"/"bcp_capability_manifest_v1.schema.json")
current_schema=load(ROOT/"schemas"/"bcp_current_release.schema.json")
current=load(ROOT/"release"/"current.json")
med=load(ROOT/"docs"/"examples"/"execution-fabric"/"med-rebuild.release-transaction-hold.example.json")

assert release_schema["properties"]["schema"]["const"]=="bcp.release_transaction/1"
adapter_ops=set(adapter_schema["properties"]["bindings"]["items"]["properties"]["operation"]["enum"])
required_ops=set(release_schema["properties"]["operations"]["required"])
assert required_ops=={"RELEASE_VERIFY","UPDATE_STAGE","UPDATE_ACTIVATE","HEALTHCHECK","ROLLBACK"}
assert required_ops <= adapter_ops

cap_evidence=set(cap_schema["properties"]["evidence_contract"]["items"]["enum"])
receipt_evidence=set(receipt_schema["properties"]["evidence"]["items"]["properties"]["kind"]["enum"])
release_evidence=set(release_schema["$defs"]["operation_binding"]["properties"]["evidence_contract"]["items"]["enum"])
assert cap_evidence==receipt_evidence==release_evidence

policy=release_schema["properties"]["policy"]["properties"]
assert policy["exact_readback_required"]["const"] is True
assert policy["healthcheck_required"]["const"] is True
assert "P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE" not in policy["max_permission_class"]["enum"]
assert "P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE" in release_schema["$defs"]["operation_binding"]["properties"]["permission_class"]["oneOf"][1]["enum"]

validate_transaction(med)
assert med["state"]=="WAITING_CAPABILITY"
assert med["operations"]["UPDATE_STAGE"]["state"]=="UNSUPPORTED"
assert med["operations"]["UPDATE_STAGE"]["capability_id"] is None
assert med["operations"]["UPDATE_ACTIVATE"]["state"]=="WAITING_BINDING"
assert med["operations"]["ROLLBACK"]["state"]=="WAITING_BINDING"
assert med["candidate"]["source_revision"]=="EXAMPLE_ONLY_NOT_FIELD_AUTHORITY"

assert current_schema["properties"]["update_policy"]["properties"]["hash_verification_required"]["const"] is True
assert current_schema["properties"]["update_policy"]["properties"]["rollback_required"]["const"] is True
assert current["update_policy"]["hash_verification_required"] is True
assert current["update_policy"]["rollback_required"] is True
assert current["update_policy"]["scheduled_chatgpt_automation"] is False

anti=(ROOT/"docs"/"RELEASE_LINE_RECONCILIATION_AND_ANTI_DOWNGRADE.md").read_text(encoding="utf-8")
assert "candidate.versionCode >= current_drive.versionCode" in anti
assert "RELEASE_LINE_RECONCILIATION_REQUIRED" in anti

src=(ROOT/"windows"/"execution_fabric"/"release_controller.py").read_text(encoding="utf-8")
for required in [
    "SUPERSEDED_NO_ROLLBACK",
    "record_candidate_readback",
    "ROLLBACK_READBACK_PENDING",
    "latest_committed",
    "receipt evidence contract incomplete",
    "requires field-certified receipt",
]:
    assert required in src, required

for forbidden in [
    "subprocess.", "os.system", "powershell.exe", "cmd.exe",
    "Invoke-WebRequest", "requests.", "urllib.", "shutil.", "zipfile."
]:
    assert forbidden not in src, forbidden

server=(ROOT/"windows"/"bcp_server_v2.py").read_text(encoding="utf-8")
assert 'if path == "/v2/releases":' in server
post=server.split("def do_POST(self):",1)[1]
for forbidden_route in [
    "/v2/releases","/v2/update","/v2/activate","/v2/rollback","/v2/release/commit"
]:
    assert forbidden_route not in post, forbidden_route

print("BCP_R3_PHASE5_RELEASE_CONTRACT_GUARD=PASS")
print("med_rebuild=WAITING_CAPABILITY")
print("field_certified=false")
