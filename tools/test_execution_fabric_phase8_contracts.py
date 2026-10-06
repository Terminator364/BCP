from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "windows" / "execution_fabric" / "catalogs" / "phase8_cross_project.json"
SCHEMA = ROOT / "schemas" / "bcp_cross_project_catalog_v1.schema.json"
SERVER = (ROOT / "windows" / "bcp_server_v2.py").read_text(encoding="utf-8")
REGISTRY = (
    ROOT / "windows" / "execution_fabric" / "project_adapter_registry.py"
).read_text(encoding="utf-8")

catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
assert schema["type"] == "object"
assert catalog["schema"] == "bcp.cross_project_catalog/1"
assert len(catalog["projects"]) == 7
assert len(catalog["adapters"]) == 7

projects = {x["project_id"]: x for x in catalog["projects"]}
adapters = {x["project_id"]: x for x in catalog["adapters"]}
assert set(projects) == set(adapters)
assert set(projects) == {
    "TLIB", "EXCELLENTIA", "DELIVERY", "BUILDHUB",
    "PC_COMMAND", "PHONEMOUSE", "P2PCR95",
}

# Conversation never becomes source of authority.
for record in projects.values():
    assert record["authority"]["conversation"] == "NON_AUTHORITATIVE"
    assert record["origins"]["local_roots"][0]["status"] == "UNRESOLVED"
    assert record["origins"]["local_roots"][0]["path"] is None

# TLIB source binding stays unresolved; audit evidence is not silently upgraded to source authority.
tlib = projects["TLIB"]
assert tlib["authority"]["engineering"] == "UNRESOLVED"
assert tlib["origins"]["repos"][0]["status"] == "UNRESOLVED"
assert tlib["origins"]["repos"][0]["repository"] is None

# Only repository-observed operations may be BOUND at repository phase.
for adapter in adapters.values():
    for binding in adapter["bindings"]:
        if binding["state"] != "BOUND":
            continue
        assert binding["provider_id"] == "GITHUB_REPOSITORY"
        assert binding["permission_class"] == "P0_READ"
        assert binding["resource_class"] in {"R0_TINY", "R1_LIGHT"}
        assert binding["operation"] in {"INSPECT", "RELEASE_VERIFY"}

# Excellentia has an exact observed release manifest.
excellentia = adapters["EXCELLENTIA"]
release = next(x for x in excellentia["bindings"] if x["operation"] == "RELEASE_VERIFY")
assert release["state"] == "BOUND"
assert release["input_defaults"]["release_manifest"] == "excellentia-study-cockpit/release/current.json"

# Delivery remains multi-provider for release truth.
delivery_release = next(
    x for x in adapters["DELIVERY"]["bindings"]
    if x["operation"] == "RELEASE_VERIFY"
)
assert delivery_release["state"] == "WAITING_BINDING"
assert delivery_release["provider_id"] == "DELIVERY"

# PC-COMMAND state repo is not mislabeled as engineering authority.
pc_command = projects["PC_COMMAND"]
assert pc_command["authority"]["engineering"] == "UNRESOLVED"
assert pc_command["origins"]["repos"][0]["authority"] == "COMPATIBILITY"

# No automatic cross-project adapter may smuggle high-risk or local-AI authority.
serialized = json.dumps(catalog, sort_keys=True).casefold()
for forbidden in (
    '"command"', '"argv"', '"shell"', '"script"', '"executable"',
    "powershell.exe", "cmd.exe",
):
    assert forbidden not in serialized, forbidden
for adapter in adapters.values():
    for binding in adapter["bindings"]:
        assert binding["permission_class"] != "P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE"
        assert binding["resource_class"] != "R4_LOCAL_AI"

# Registry remains a typed mapping layer, not an executor.
for forbidden in ("subprocess", "os.system", "shell=True"):
    assert forbidden not in REGISTRY, forbidden
for required in (
    "validate_against_project",
    "BOUND {provider} operation requires observed project repository",
    "BOUND {provider} operation requires observed local project root",
    "ProjectAdapterAmbiguous",
):
    assert required in REGISTRY, required

# Microkernel exposure is read-only; raw authority mutation stays absent.
for route in ('"/v2/project-adapters"', '"/v2/project-adapters/resolve"'):
    assert route in SERVER, route
post = SERVER.split("    def do_POST(self):", 1)[1]
for forbidden in (
    'if path == "/v2/project-adapters"',
    'if path == "/v2/project-adapters/resolve"',
    'if path == "/v2/authority/fence"',
    'if path == "/v2/authority/transition"',
    'body.get("command")',
    'body.get("argv")',
):
    assert forbidden not in post, forbidden

print("BCP_R3_PHASE8_CROSS_PROJECT_CONTRACTS=PASS")
print("projects=7 adapters=7")
print("field_certified=false")
