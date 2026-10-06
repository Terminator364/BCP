from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"
sys.path.insert(0, str(WINDOWS))

from execution_fabric.capability_factory import (  # noqa: E402
    GATE_SEQUENCE,
    GATE_STAGE,
    AUTO_TRUST,
    FACTORY_PROMOTED_TRUST,
    validate_manifest,
)

SCHEMAS = ROOT / "schemas"


def load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


candidate = load("bcp_capability_factory_candidate_v1.schema.json")
plan = load("bcp_capability_factory_plan_v1.schema.json")
registration = load("bcp_capability_registration_v1.schema.json")
manifest_schema = load("bcp_capability_manifest_v1.schema.json")
receipt_schema = load("bcp_action_receipt_v1.schema.json")

for schema in (candidate, plan, registration):
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False

# Canonical pipeline must remain exactly the R3 factory gate sequence.
expected_gates = [
    "reuse_search",
    "source_trust",
    "license_policy",
    "build_adapter",
    "static_validate",
    "sandbox_test",
    "resource_test",
    "rollback_test",
    "security_test",
    "canary",
]
assert GATE_SEQUENCE == expected_gates
assert set(GATE_STAGE) == set(expected_gates)
plan_gates = {
    x for x in plan["properties"]["gate"]["enum"] if x is not None
}
assert plan_gates == set(expected_gates)

# Automatic Factory plans never carry P4 or R4.
plan_permissions = {
    x for x in plan["properties"]["permission_class"]["enum"] if x is not None
}
plan_resources = {
    x for x in plan["properties"]["resource_class"]["enum"] if x is not None
}
assert plan_permissions == {
    "P0_READ", "P1_SAFE_WRITE", "P2_PROJECT_MUTATION",
    "P3_BOUNDED_SYSTEM_CHANGE",
}
assert plan_resources == {"R0_TINY", "R1_LIGHT", "R2_MEDIUM", "R3_HEAVY"}

# Candidate policy may auto-promote only verified trust classes.
allowed_trust = set(
    candidate["properties"]["policy"]["properties"]["allowed_trust_classes"]["items"]["enum"]
)
assert allowed_trust == {"T0_BUILTIN", "T1_VERIFIED_LOCAL", "T2_VERIFIED_REMOTE"}
assert AUTO_TRUST == allowed_trust
assert FACTORY_PROMOTED_TRUST == {"T1_VERIFIED_LOCAL", "T2_VERIFIED_REMOTE"}
assert "T3_CANDIDATE" not in allowed_trust
assert "T4_QUARANTINED" not in allowed_trust

# The candidate itself cannot claim field certification.
assert candidate["properties"]["field_certified"]["const"] is False
assert plan["properties"]["field_certified"]["const"] is False

# A locally verified registration must be backed by field proof.
t1_rules = [
    rule for rule in registration.get("allOf", [])
    if rule.get("if", {}).get("properties", {}).get("trust_class", {}).get("const")
    == "T1_VERIFIED_LOCAL"
]
assert len(t1_rules) == 1
assert (
    t1_rules[0]["then"]["properties"]["field_certified"]["const"] is True
)

# Registration embeds the canonical manifest and carries immutable source/license evidence.
required_registration = set(registration["required"])
assert {"manifest", "source", "license", "gate_receipts"} <= required_registration
assert registration["properties"]["manifest"]["$ref"].endswith(
    "bcp_capability_manifest_v1.schema.json"
)

# Existing canonical contracts remain the vocabulary source.
manifest_permissions = set(manifest_schema["properties"]["permission_class"]["enum"])
receipt_scopes = set(receipt_schema["properties"]["proof_scope"]["enum"])
assert "P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE" in manifest_permissions
assert receipt_scopes == {"REPOSITORY", "SIMULATION", "PROVIDER", "FIELD"}

factory = (
    ROOT / "windows" / "execution_fabric" / "capability_factory.py"
).read_text(encoding="utf-8")
server = (ROOT / "windows" / "bcp_server_v2.py").read_text(encoding="utf-8")

# Candidate manifests cannot smuggle free-form command/argv/shell inputs.
for token in (
    "FORBIDDEN_INPUT_KEYS",
    "_find_forbidden_input",
    "free-form execution input forbidden",
    "MODEL executor qualification is deferred to Phase 10",
    "R4 local AI qualification is deferred to Phase 10",
    "P4 capability factory qualification requires a separate human-approved lane",
    "local executable capability requires pinned version and sha256",
    "P2/P3 capability requires explicit rollback",
):
    assert token in factory, token

# Every gate must be receipt-bound to candidate+gate and source revision.
for token in (
    "ActionReceiptRegistry",
    "_gate_idempotency",
    "receipt idempotency key does not match candidate gate",
    "receipt source revision does not match candidate",
    "factory gate evidence incomplete",
    "repository/simulation canary cannot promote unattended capability",
):
    assert token in factory, token

# Factory is an orchestrator only: no direct code/provider execution.
for forbidden in (
    "subprocess.",
    "os.system",
    "shell=True",
    "requests.",
    "urllib.request",
    "safe_extract(",
):
    assert forbidden not in factory, forbidden

# Microkernel exposes inspection only.
for route in (
    'if path == "/v2/capability-factory"',
    'if path == "/v2/capabilities"',
):
    assert route in server, route
post = server.split("    def do_POST(self):", 1)[1]
for forbidden in (
    'if path == "/v2/capability-factory"',
    'if path == "/v2/capabilities"',
    'body.get("candidate")',
    'body.get("registration")',
    'body.get("manifest")',
    'body.get("gate")',
    'body.get("command")',
    'body.get("argv")',
):
    assert forbidden not in post, forbidden

print("BCP_R3_PHASE7_CONTRACT_GUARD=PASS")
print("factory_direct_execution=false")
print("factory_http_mutation=false")
print("candidate_field_certified=false")
