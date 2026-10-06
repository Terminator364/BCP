from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"
sys.path.insert(0, str(WINDOWS))

from execution_fabric.desired_state_registry import validate_resource  # noqa: E402
from execution_fabric.incident_recipe import validate_recipe  # noqa: E402

SCHEMAS = ROOT / "schemas"
EXAMPLES = ROOT / "docs" / "examples" / "execution-fabric"

schema_paths = [
    SCHEMAS / "bcp_action_receipt_v1.schema.json",
    SCHEMAS / "bcp_desired_state_resource_v1.schema.json",
    SCHEMAS / "bcp_incident_v1.schema.json",
    SCHEMAS / "bcp_repair_recipe_v1.schema.json",
    SCHEMAS / "bcp_reconcile_plan_v1.schema.json",
]
for path in schema_paths:
    obj = json.loads(path.read_text(encoding="utf-8"))
    assert obj["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert obj["type"] == "object"

desired = json.loads((EXAMPLES / "bcp-runtime.desired-state.example.json").read_text(encoding="utf-8"))
recipe = json.loads((EXAMPLES / "bcp-runtime.restart-recipe-candidate.example.json").read_text(encoding="utf-8"))

validate_resource(desired)
validate_recipe(recipe)

assert recipe["status"] == "CANDIDATE"
assert recipe["validation"]["field_evidence_required"] is True
assert recipe["validation"]["successful_receipt_refs"] == []
assert recipe["validation"]["regression_refs"] == []
assert recipe["validation"]["field_evidence_refs"] == []

serialized = json.dumps(recipe, sort_keys=True).casefold()
for forbidden in ['"command"', '"argv"', '"shell"', "powershell.exe", "cmd.exe"]:
    assert forbidden not in serialized, forbidden

server = (ROOT / "windows" / "bcp_server_v2.py").read_text(encoding="utf-8")
for route in ('"/v2/desired"', '"/v2/recipes"', '"/v2/incidents"'):
    assert route in server, route

post = server.split("    def do_POST(self):", 1)[1]
for route in ('if path == "/v2/desired"', 'if path == "/v2/recipes"', 'if path == "/v2/incidents"'):
    assert route not in post, route

for forbidden in (
    'body.get("recipe")',
    'body.get("desired")',
    'body.get("command")',
    'body.get("argv")',
    'if path == "/v2/authority/fence"',
    'if path == "/v2/authority/transition"',
):
    assert forbidden not in post, forbidden

planner = (ROOT / "windows" / "execution_fabric" / "incident_recipe.py").read_text(encoding="utf-8")
for required in (
    "NO_VALIDATED_RECIPE",
    "MULTIPLE_VALIDATED_RECIPES_FOR_SIGNATURE",
    "MAX_ATTEMPTS_REACHED",
    "REPAIR_BACKOFF_ACTIVE",
    "RECIPE_PERMISSION_EXCEEDS_RECONCILE_POLICY",
    "RECIPE_RESOURCE_EXCEEDS_DESIRED_CEILING",
    "VALIDATED_RECIPE_MATCH",
):
    assert required in planner, required

for required in (
    "P3 recipe requires field_evidence_required=true",
    "capability_states object required",
    "WAITING_CAPABILITY",
    "CAPABILITY_",
    "observation.observed object required",
):
    assert required in planner, required

# A provider-supplied boolean may never be a trust input for reconciliation.
assert '"matches_desired"' not in planner

assert "subprocess" not in planner
assert "os.system" not in planner
assert "shell=True" not in planner

print("BCP_R3_PHASE4_STATIC_GUARD=PASS")
print("recipe_candidate_executable=false")
print("field_certified=false")


ACTION_RECEIPTS = (
    ROOT / "windows" / "execution_fabric" / "action_receipt_registry.py"
).read_text(encoding="utf-8")

for required in (
    "class ActionReceiptRegistry",
    "def require_success",
    "field_certified",
    'receipt.get("proof_scope") == "FIELD"',
    "receipt is not successful",
    "receipt contains FAIL evidence",
):
    assert required in ACTION_RECEIPTS, required

# Recipe promotion must resolve real receipts, not trust arbitrary string labels.
for required in (
    "ActionReceiptRegistry",
    "self.receipts.require_success",
    "successful receipts do not cover required capabilities",
    "field receipts do not cover required capabilities",
    "non-candidate recipe cannot be overwritten",
):
    assert required in planner, required

# Phase 3/4 network surface is read-only for domain state and contains no raw authority mutation.
for forbidden_route in (
    'if path == "/v2/authority/fence"',
    'if path == "/v2/authority/transition"',
):
    assert forbidden_route not in server, forbidden_route

print("BCP_R3_PHASE4_RECEIPT_CHAIN_GUARD=PASS")
