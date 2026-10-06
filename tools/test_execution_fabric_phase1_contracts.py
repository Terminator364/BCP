from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
EXAMPLES = ROOT / "docs" / "examples" / "execution-fabric"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def top_level_contract(schema: dict, example: dict) -> None:
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    required = set(schema["required"])
    properties = set(schema["properties"])
    assert required <= properties
    assert required <= set(example)
    assert set(example) <= properties
    const = schema["properties"]["schema"]["const"]
    assert example["schema"] == const


def enum(schema: dict, *path: str) -> set[str]:
    cur = schema
    for key in path:
        cur = cur[key]
    return set(cur["enum"])


project = load(SCHEMAS / "bcp_project_record_v1.schema.json")
receipt = load(SCHEMAS / "bcp_action_receipt_v1.schema.json")
ingress = load(SCHEMAS / "bcp_mission_ingress_v1.schema.json")
observation = load(SCHEMAS / "bcp_capability_observation_v1.schema.json")
mission = load(SCHEMAS / "bcp_mission_envelope_v2.schema.json")
capability = load(SCHEMAS / "bcp_capability_manifest_v1.schema.json")
grant = load(SCHEMAS / "bcp_capability_grant_v1.schema.json")

project_example = load(EXAMPLES / "bcp-core.project-record.example.json")
receipt_example = load(EXAMPLES / "phase1.repository-action-receipt.example.json")
ingress_example = load(EXAMPLES / "phase1.mission-ingress.example.json")
observation_example = load(EXAMPLES / "phase1.capability-observation.example.json")

for s, e in [
    (project, project_example),
    (receipt, receipt_example),
    (ingress, ingress_example),
    (observation, observation_example),
]:
    top_level_contract(s, e)

# Permission classes may only be equal or stricter in mission/project contracts.
cap_permissions = enum(capability, "properties", "permission_class")
mission_permissions = enum(mission, "properties", "approval_policy", "properties", "max_permission_class")
project_permissions = enum(project, "properties", "permission_profile", "properties", "max_permission_class")
grant_permissions = enum(grant, "properties", "max_permission_class")
assert cap_permissions == mission_permissions == project_permissions
assert grant_permissions == cap_permissions - {"P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE"}

# Resource classes must stay identical across the authority-bearing contracts.
cap_resources = enum(capability, "properties", "resource_class")
mission_resources = enum(mission, "properties", "resource_policy", "properties", "max_resource_class")
project_resources = enum(project, "properties", "resource_profile", "properties", "resource_class")
assert cap_resources == mission_resources == project_resources

# Evidence vocabulary used by receipts must cover every capability evidence contract kind.
cap_evidence = enum(capability, "properties", "evidence_contract", "items")
receipt_evidence = enum(receipt, "properties", "evidence", "items", "properties", "kind")
assert cap_evidence == receipt_evidence

# Ingress transport vocabulary must not weaken Mission Envelope source kinds.
mission_sources = enum(mission, "properties", "source", "properties", "kind")
ingress_transports = enum(ingress, "properties", "transport")
assert ingress_transports == mission_sources
assert ingress_example["transport"] == ingress_example["mission"]["source"]["kind"]

# Runtime observations must cover the mutable availability states from manifests.
manifest_availability = enum(capability, "properties", "availability")
observed_states = enum(observation, "properties", "state")
assert manifest_availability <= observed_states

# Project record can preserve ChatGPT-PC/B-EDGE semantics without inventing roots.
assert project_example["origins"]["local_roots"][0]["status"] == "UNRESOLVED"
assert project_example["origins"]["local_roots"][0]["path"] is None
assert project_example["authority"]["conversation"] == "NON_AUTHORITATIVE"
assert {"head_revision", "coordinator_epoch"} <= set(project["properties"])

# Receipt contract preserves durable-store and B-EDGE receipt semantics.
for field in [
    "action_id", "job_id", "project_id", "idempotency_key", "output_hash",
    "committed_revision", "fencing_token", "content_hash", "predecessor_hash",
    "outbox_message_id", "idempotent_replay",
]:
    assert field in receipt["properties"], field

# Anti-false-PASS: repository/simulation proof cannot be field certified.
assert receipt_example["proof_scope"] == "REPOSITORY"
assert receipt_example["field_certified"] is False
field_rule = receipt["allOf"][0]
assert field_rule["then"]["properties"]["proof_scope"]["const"] == "FIELD"

# Examples must state repository proof honestly.
assert receipt_example["status"] == "SUCCEEDED"
assert receipt_example["result"] == "PASS"
assert receipt_example["readback"]["status"] == "PASS"
assert observation_example["evidence_class"] == "REPOSITORY_STATIC"
assert observation_example["details"]["field_certified"] is False

print("BCP_R3_PHASE1_CONTRACT_CONVERGENCE=PASS")
print("schemas=7 examples=4")
print("field_certified=false")
