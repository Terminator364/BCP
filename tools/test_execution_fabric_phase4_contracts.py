from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
S=ROOT/"schemas"
E=ROOT/"docs"/"examples"/"execution-fabric"

load=lambda p: json.loads(p.read_text(encoding="utf-8"))

recipe_schema=load(S/"bcp_repair_recipe_v1.schema.json")
incident_schema=load(S/"bcp_incident_v1.schema.json")
desired_schema=load(S/"bcp_desired_state_resource_v1.schema.json")
cap_schema=load(S/"bcp_capability_manifest_v1.schema.json")
receipt_schema=load(S/"bcp_action_receipt_v1.schema.json")
recipe=load(E/"bcp-startup.repair-recipe.example.json")
desired=load(E/"bcp-microkernel-startup.desired-state.example.json")

assert recipe_schema["properties"]["schema"]["const"]=="bcp.repair_recipe/1"
assert incident_schema["properties"]["schema"]["const"]=="bcp.incident/1"
assert desired_schema["properties"]["schema"]["const"]=="bcp.desired_state_resource/1"

cap_perm=set(cap_schema["properties"]["permission_class"]["enum"])
cap_res=set(cap_schema["properties"]["resource_class"]["enum"])
cap_ev=set(cap_schema["properties"]["evidence_contract"]["items"]["enum"])
recipe_step=recipe_schema["properties"]["steps"]["items"]["properties"]
assert set(recipe_step["permission_class"]["enum"]) <= cap_perm
assert set(recipe_step["resource_class"]["enum"]) == cap_res
assert set(recipe_step["evidence_contract"]["items"]["enum"]) == cap_ev

desired_policy=desired_schema["properties"]["spec"]["properties"]["reconcile_policy"]["properties"]
assert set(desired_policy["max_permission_class"]["enum"]) <= cap_perm
assert set(desired_policy["resource_ceiling"]["enum"]) == cap_res

receipt_ev=set(receipt_schema["properties"]["evidence"]["items"]["properties"]["kind"]["enum"])
assert cap_ev == receipt_ev

# Structural anti-autonomy: auto eligibility requires field validation.
rule=recipe_schema["allOf"][0]
assert rule["then"]["properties"]["status"]["const"]=="FIELD_VALIDATED"
assert recipe["status"]=="REPOSITORY_VALIDATED"
assert recipe["auto_eligible"] is False

serialized=json.dumps(recipe,sort_keys=True).casefold()
for forbidden in ['"command"','"argv"','"shell"',"powershell.exe","cmd.exe"]:
    assert forbidden not in serialized, forbidden

ledger=(ROOT/".project-memory"/"ERROR_LEDGER.jsonl").read_text(encoding="utf-8")
assert "BCP-ARCH-0003" in ledger
assert recipe["ledger_refs"]==["BCP-ARCH-0003"]

assert desired["metadata"]["project_id"]=="BCP_CORE"
assert desired["status"]["phase"]=="UNKNOWN"
assert desired["spec"]["reconcile_policy"]["mode"]=="AUTO_BOUNDED_SYSTEM"

print("BCP_R3_PHASE4_CONTRACT_GUARD=PASS")
print("recipe_auto_eligible=false")
print("field_certified=false")

SERVER=(ROOT/"windows"/"bcp_server_v2.py").read_text(encoding="utf-8")
for route in ["/v2/desired","/v2/recipes","/v2/incidents"]:
    assert f'if path == "{route}":' in SERVER, route
post=SERVER.split("def do_POST(self):",1)[1]
for forbidden in ["/v2/desired","/v2/recipes","/v2/incidents","/v2/reconcile"]:
    assert forbidden not in post, forbidden
print("PHASE4_READONLY_HTTP_BOUNDARY=PASS")
