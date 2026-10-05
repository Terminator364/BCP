from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
EXAMPLES = ROOT / "docs" / "examples" / "execution-fabric"

schema = json.loads((SCHEMAS / "bcp_project_adapter_v1.schema.json").read_text(encoding="utf-8"))
adapter = json.loads((EXAMPLES / "med-rebuild.project-adapter.example.json").read_text(encoding="utf-8"))
project = json.loads((EXAMPLES / "med-rebuild.project-record.example.json").read_text(encoding="utf-8"))
capability = json.loads((SCHEMAS / "bcp_capability_manifest_v1.schema.json").read_text(encoding="utf-8"))

assert schema["properties"]["schema"]["const"] == "bcp.project_adapter/1"
assert adapter["schema"] == "bcp.project_adapter/1"
assert adapter["project_id"] == project["project_id"] == "MED_REBUILD"

allowed_binding_keys = set(
    schema["properties"]["bindings"]["items"]["properties"]
)
for binding in adapter["bindings"]:
    assert set(binding) <= allowed_binding_keys

# Adapter is capability-based; executable mechanics do not belong here.
serialized = json.dumps(adapter, sort_keys=True).casefold()
for forbidden in ['"command"', '"argv"', '"shell"', "powershell.exe", "cmd.exe"]:
    assert forbidden not in serialized, forbidden

# Evidence/permission/resource vocabularies cannot exceed the canonical capability manifest.
cap_evidence = set(capability["properties"]["evidence_contract"]["items"]["enum"])
cap_permissions = set(capability["properties"]["permission_class"]["enum"])
cap_resources = set(capability["properties"]["resource_class"]["enum"])
for binding in adapter["bindings"]:
    assert set(binding["evidence_contract"]) <= cap_evidence
    assert binding["permission_class"] in cap_permissions
    assert binding["resource_class"] in cap_resources

# Only repository verification is currently bound. PC operations await real field binding.
bound = [b for b in adapter["bindings"] if b["state"] == "BOUND"]
assert [b["operation"] for b in bound] == ["RELEASE_VERIFY"]
for binding in adapter["bindings"]:
    if binding["provider_id"] == "BCP_NATIVE_PC":
        assert binding["state"] == "WAITING_BINDING"

# Root/path anti-invention is explicit in the project record.
local = project["origins"]["local_roots"]
assert len(local) == 1
assert local[0]["status"] == "UNRESOLVED"
assert local[0]["path"] is None

# Known engineering binding is explicit and narrow.
repo = project["origins"]["repos"][0]
assert repo["status"] == "BOUND"
assert repo["repository"] == "Terminator364/ChatGPT-PC"
assert repo["path"] == "med-rebuild-study-hub/v1.5-prototype"

print("BCP_R3_PHASE3_PROJECT_ADAPTER_STATIC_GUARD=PASS")
print("bound_operations=RELEASE_VERIFY")
print("pc_operations=WAITING_BINDING")
print("field_certified=false")
