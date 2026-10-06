from __future__ import annotations

"""BCP R3 Phase 7 evidence-gated Capability Factory.

The factory is an admission/promotion state machine. It never downloads, shells,
installs, imports or executes candidate code directly. Each executable gate is a
typed capability plan proven by a normalized Action Receipt. Registrations are
immutable CriticalStore records and remain separate from execution authority.
"""

from copy import deepcopy
import datetime as dt
import hashlib
import json
import re
from typing import Any

from .action_receipt_registry import (
    ActionReceiptError,
    ActionReceiptRegistry,
    ActionReceiptValidationError,
)
from .critical_store import CriticalStore
from .resource_admission import RESOURCE_ORDER, decide as resource_decide


CANDIDATE_PREFIX = "capability-factory/"
REGISTRATION_PREFIX = "capability-registration/"
CANDIDATE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,199}$")
PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
CAPABILITY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
SHA_RE = re.compile(r"^[a-fA-F0-9]{64}$")

PERMISSION_ORDER = {
    "P0_READ": 0,
    "P1_SAFE_WRITE": 1,
    "P2_PROJECT_MUTATION": 2,
    "P3_BOUNDED_SYSTEM_CHANGE": 3,
    "P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE": 4,
}
AUTO_PERMISSION_MAX = "P3_BOUNDED_SYSTEM_CHANGE"
EFFECT_PERMISSION = {
    "READ_ONLY": "P0_READ",
    "SAFE_WRITE": "P1_SAFE_WRITE",
    "PROJECT_MUTATION": "P2_PROJECT_MUTATION",
    "BOUNDED_SYSTEM_CHANGE": "P3_BOUNDED_SYSTEM_CHANGE",
    "DESTRUCTIVE_OR_SECURITY_SENSITIVE": "P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE",
}
AUTO_TRUST = {"T0_BUILTIN", "T1_VERIFIED_LOCAL", "T2_VERIFIED_REMOTE"}
FACTORY_PROMOTED_TRUST = {"T1_VERIFIED_LOCAL", "T2_VERIFIED_REMOTE"}
FORBIDDEN_INPUT_KEYS = {
    "command", "argv", "shell", "script", "executable",
    "powershell", "cmd", "commandline", "command_line",
}
TRUST_CLASSES = AUTO_TRUST | {"T3_CANDIDATE", "T4_QUARANTINED"}
LICENSE_STATES = {"APPROVED", "REVIEW_REQUIRED", "DENIED", "UNKNOWN", "NOT_APPLICABLE"}
SCOPE_ORDER = {"REPOSITORY": 0, "SIMULATION": 1, "PROVIDER": 2, "FIELD": 3}
EVIDENCE_KINDS = {
    "EXIT_CODE", "FILE_READBACK", "HASH", "PROCESS_HEALTH", "HTTP_HEALTH",
    "SERVICE_STATE", "GIT_REVISION", "TEST_RESULT", "ARTIFACT_SIGNATURE",
    "PROVIDER_ACK", "DESTINATION_READBACK", "CUSTOM_VALIDATOR",
}

GATE_SEQUENCE = [
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
GATE_STAGE = {
    "reuse_search": "REUSE_SEARCH",
    "source_trust": "SOURCE_TRUST_CHECK",
    "license_policy": "LICENSE_POLICY_CHECK",
    "build_adapter": "BUILD_ADAPTER",
    "static_validate": "STATIC_VALIDATE",
    "sandbox_test": "SANDBOX_TEST",
    "resource_test": "RESOURCE_TEST",
    "rollback_test": "ROLLBACK_TEST",
    "security_test": "SECURITY_TEST",
    "canary": "CANARY",
}
GATE_CAPABILITY = {
    "reuse_search": "factory.reuse.search",
    "source_trust": "factory.source.verify",
    "license_policy": "factory.license.verify",
    "build_adapter": "factory.adapter.build",
    "static_validate": "factory.static.validate",
    "sandbox_test": "factory.sandbox.test",
    "resource_test": "factory.resource.test",
    "rollback_test": "factory.rollback.test",
    "security_test": "factory.security.test",
    "canary": "factory.canary.run",
}
GATE_PERMISSION = {
    "reuse_search": "P0_READ",
    "source_trust": "P0_READ",
    "license_policy": "P0_READ",
    "build_adapter": "P2_PROJECT_MUTATION",
    "static_validate": "P0_READ",
    "sandbox_test": "P1_SAFE_WRITE",
    "resource_test": "P1_SAFE_WRITE",
    "rollback_test": "P1_SAFE_WRITE",
    "security_test": "P1_SAFE_WRITE",
}
GATE_RESOURCE = {
    "reuse_search": "R0_TINY",
    "source_trust": "R0_TINY",
    "license_policy": "R0_TINY",
    "build_adapter": "R2_MEDIUM",
    "static_validate": "R1_LIGHT",
    "sandbox_test": "R2_MEDIUM",
    "resource_test": "R2_MEDIUM",
    "rollback_test": "R2_MEDIUM",
    "security_test": "R2_MEDIUM",
}
GATE_EVIDENCE = {
    "reuse_search": {"CUSTOM_VALIDATOR"},
    "source_trust": {"HASH"},
    "license_policy": {"CUSTOM_VALIDATOR"},
    "build_adapter": {"ARTIFACT_SIGNATURE"},
    "static_validate": {"TEST_RESULT"},
    "sandbox_test": {"TEST_RESULT"},
    "resource_test": {"TEST_RESULT"},
    "rollback_test": {"TEST_RESULT"},
    "security_test": {"TEST_RESULT"},
}
GATE_MIN_SCOPE = {
    "reuse_search": "REPOSITORY",
    "source_trust": "REPOSITORY",
    "license_policy": "REPOSITORY",
    "build_adapter": "SIMULATION",
    "static_validate": "SIMULATION",
    "sandbox_test": "SIMULATION",
    "resource_test": "SIMULATION",
    "rollback_test": "SIMULATION",
    "security_test": "SIMULATION",
}


class CapabilityFactoryError(RuntimeError):
    pass


class CandidateNotFound(CapabilityFactoryError):
    pass


class CandidateCollision(CapabilityFactoryError):
    pass


class CandidateTransitionError(CapabilityFactoryError):
    pass


class RegistrationNotFound(CapabilityFactoryError):
    pass


class RegistrationCollision(CapabilityFactoryError):
    pass


def _iso(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid {field}")
    text = value.strip()
    probe = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = dt.datetime.fromisoformat(probe)
    except ValueError as exc:
        raise ValueError(f"invalid {field}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return text


def _text(value: Any, field: str, cap: int, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be string")
    text = value.strip()
    if not text or len(text) > cap:
        raise ValueError(f"invalid {field}")
    return text


def _hash_obj(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _find_forbidden_input(value: Any, path: str = "$") -> str | None:
    if isinstance(value, dict):
        props = value.get("properties")
        if isinstance(props, dict):
            for key in props:
                if str(key).casefold() in FORBIDDEN_INPUT_KEYS:
                    return f"{path}.properties.{key}"
        for key, item in value.items():
            found = _find_forbidden_input(item, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = _find_forbidden_input(item, f"{path}[{index}]")
            if found:
                return found
    return None


def _candidate_stream(project_id: str, candidate_id: str) -> str:
    project = _text(project_id, "project_id", 128)
    candidate = _text(candidate_id, "candidate_id", 200)
    if not PROJECT_RE.fullmatch(project) or not CANDIDATE_RE.fullmatch(candidate):
        raise ValueError("invalid factory candidate identity")
    return f"{CANDIDATE_PREFIX}{project}/{candidate}"


def _registration_stream(capability_id: str, provider_id: str, version: str) -> str:
    cap = _text(capability_id, "capability_id", 128)
    provider = _text(provider_id, "provider_id", 128)
    ver = _text(version, "version", 64)
    if not CAPABILITY_RE.fullmatch(cap):
        raise ValueError("invalid capability_id")
    digest = hashlib.sha256(f"{cap}\0{provider}\0{ver}".encode("utf-8")).hexdigest()
    return REGISTRATION_PREFIX + digest


def validate_manifest(manifest: Any) -> dict[str, Any]:
    required = {
        "schema", "capability_id", "provider_id", "version", "effect_class",
        "permission_class", "resource_class", "input_schema", "evidence_contract",
    }
    optional = {
        "description", "project_scopes", "availability", "requires_network",
        "requires_pc", "requires_bedge", "requires_admin", "preemptible",
        "timeout_seconds", "output_schema", "preconditions", "rollback", "executor",
    }
    if not isinstance(manifest, dict) or set(manifest) - required - optional or not required <= set(manifest):
        raise ValueError("invalid capability manifest fields")
    if manifest.get("schema") != "bcp.capability_manifest/1":
        raise ValueError("unsupported capability manifest")
    cap = _text(manifest.get("capability_id"), "capability_id", 128)
    if not CAPABILITY_RE.fullmatch(cap):
        raise ValueError("invalid capability_id")
    _text(manifest.get("provider_id"), "provider_id", 128)
    _text(manifest.get("version"), "version", 64)
    if manifest.get("effect_class") not in {
        "READ_ONLY", "SAFE_WRITE", "PROJECT_MUTATION", "BOUNDED_SYSTEM_CHANGE",
        "DESTRUCTIVE_OR_SECURITY_SENSITIVE",
    }:
        raise ValueError("invalid effect_class")
    if manifest.get("permission_class") not in PERMISSION_ORDER:
        raise ValueError("invalid permission_class")
    if EFFECT_PERMISSION[manifest["effect_class"]] != manifest["permission_class"]:
        raise ValueError("effect_class/permission_class semantic mismatch")
    if manifest.get("resource_class") not in RESOURCE_ORDER:
        raise ValueError("invalid resource_class")
    if not isinstance(manifest.get("input_schema"), dict):
        raise ValueError("input_schema must be object")
    forbidden_input = _find_forbidden_input(manifest["input_schema"])
    if forbidden_input:
        raise ValueError(f"free-form execution input forbidden at {forbidden_input}")
    if "output_schema" in manifest and not isinstance(manifest.get("output_schema"), dict):
        raise ValueError("output_schema must be object")
    evidence = manifest.get("evidence_contract")
    if (
        not isinstance(evidence, list) or not evidence
        or len(evidence) != len(set(evidence))
        or not set(evidence) <= EVIDENCE_KINDS
    ):
        raise ValueError("invalid evidence_contract")
    scopes = manifest.get("project_scopes") or []
    if not isinstance(scopes, list) or len(scopes) != len(set(scopes)):
        raise ValueError("invalid project_scopes")
    for scope in scopes:
        _text(scope, "project_scope", 128)
    for field in ("requires_network", "requires_pc", "requires_bedge", "requires_admin", "preemptible"):
        if field in manifest and type(manifest.get(field)) is not bool:
            raise ValueError(f"invalid {field}")
    if manifest.get("requires_admin") is True and PERMISSION_ORDER[manifest["permission_class"]] < PERMISSION_ORDER["P3_BOUNDED_SYSTEM_CHANGE"]:
        raise ValueError("admin requirement requires P3 classification")
    timeout = manifest.get("timeout_seconds")
    if timeout is not None and (type(timeout) is not int or timeout < 1 or timeout > 86400):
        raise ValueError("invalid timeout_seconds")
    rollback = manifest.get("rollback")
    if manifest["permission_class"] in {"P2_PROJECT_MUTATION", "P3_BOUNDED_SYSTEM_CHANGE"}:
        if not isinstance(rollback, dict) or rollback.get("required") is not True:
            raise ValueError("P2/P3 capability requires explicit rollback")
    if rollback is not None:
        if not isinstance(rollback, dict) or set(rollback) - {"required", "strategy"}:
            raise ValueError("invalid rollback")
        if "required" in rollback and type(rollback.get("required")) is not bool:
            raise ValueError("invalid rollback.required")
        if rollback.get("strategy") is not None:
            _text(rollback.get("strategy"), "rollback.strategy", 240)
    executor = manifest.get("executor")
    if executor is not None:
        if not isinstance(executor, dict) or set(executor) - {
            "kind", "entrypoint", "pinned_version", "sha256"
        } or "kind" not in executor:
            raise ValueError("invalid executor")
        if executor["kind"] not in {
            "INTERNAL", "POWERSHELL", "WIN32", "GIT", "PYTHON", "NODE",
            "BUILDHUB", "DELIVERY", "MODEL", "REMOTE_PROVIDER",
        }:
            raise ValueError("invalid executor kind")
        if executor["kind"] == "MODEL" and manifest["permission_class"] != "P0_READ":
            raise ValueError("MODEL executor cannot hold consequential mutation authority")
        if executor["kind"] in {"POWERSHELL", "WIN32", "PYTHON", "NODE"}:
            if not executor.get("pinned_version") or not executor.get("sha256"):
                raise ValueError("local executable capability requires pinned version and sha256")
        if executor.get("entrypoint") is not None:
            _text(executor.get("entrypoint"), "executor.entrypoint", 500)
        if executor.get("pinned_version") is not None:
            _text(executor.get("pinned_version"), "executor.pinned_version", 128)
        sha = executor.get("sha256")
        if sha is not None and (not isinstance(sha, str) or not SHA_RE.fullmatch(sha)):
            raise ValueError("invalid executor sha256")
    return deepcopy(manifest)


def _validate_source(source: Any) -> dict[str, Any]:
    required = {"kind", "locator", "revision", "artifact_sha256", "publisher"}
    if not isinstance(source, dict) or set(source) != required:
        raise ValueError("invalid source fields")
    if source["kind"] not in {
        "BUILTIN", "LOCAL_REPO", "REMOTE_REPO", "PACKAGE",
        "EXISTING_CAPABILITY", "GENERATED_ADAPTER",
    }:
        raise ValueError("invalid source kind")
    _text(source.get("locator"), "source locator", 1000, optional=True)
    _text(source.get("revision"), "source revision", 256, optional=True)
    _text(source.get("publisher"), "source publisher", 256, optional=True)
    sha = source.get("artifact_sha256")
    if sha is not None and (not isinstance(sha, str) or not SHA_RE.fullmatch(sha)):
        raise ValueError("invalid source artifact_sha256")
    out = deepcopy(source)
    if sha is not None:
        out["artifact_sha256"] = sha.lower()
    return out


def _validate_license(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"status", "identifier", "evidence_refs"}:
        raise ValueError("invalid license fields")
    if value["status"] not in LICENSE_STATES:
        raise ValueError("invalid license status")
    _text(value.get("identifier"), "license identifier", 160, optional=True)
    refs = value.get("evidence_refs")
    if not isinstance(refs, list) or len(refs) != len(set(refs)):
        raise ValueError("invalid license evidence_refs")
    for ref in refs:
        _text(ref, "license evidence_ref", 512)
    return deepcopy(value)


def _validate_policy(policy: Any) -> dict[str, Any]:
    required = {
        "max_permission_class", "max_resource_class", "allowed_trust_classes",
        "require_sandbox", "require_rollback", "require_security_test",
        "require_canary", "target_scope",
    }
    if not isinstance(policy, dict) or set(policy) != required:
        raise ValueError("invalid factory policy fields")
    if policy["max_permission_class"] not in PERMISSION_ORDER or policy["max_permission_class"] == "P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE":
        raise ValueError("invalid automatic permission ceiling")
    if policy["max_resource_class"] not in RESOURCE_ORDER or policy["max_resource_class"] == "R4_LOCAL_AI":
        raise ValueError("invalid automatic resource ceiling")
    trusts = policy["allowed_trust_classes"]
    if not isinstance(trusts, list) or not trusts or len(trusts) != len(set(trusts)) or not set(trusts) <= AUTO_TRUST:
        raise ValueError("invalid allowed trust classes")
    for field in ("require_sandbox", "require_rollback", "require_security_test", "require_canary"):
        if type(policy[field]) is not bool:
            raise ValueError(f"invalid {field}")
    if policy["target_scope"] not in SCOPE_ORDER:
        raise ValueError("invalid target_scope")
    return deepcopy(policy)


def validate_candidate(candidate: Any) -> dict[str, Any]:
    required = {
        "schema", "candidate_id", "project_id", "original_mission_id",
        "requested_capability_id", "stage", "status", "trust_class",
        "source", "license", "proposed_manifest", "policy", "gate_receipts",
        "created_at", "updated_at", "field_certified",
    }
    optional = {"registration_ref", "failure"}
    if not isinstance(candidate, dict) or set(candidate) - required - optional or not required <= set(candidate):
        raise ValueError("invalid capability factory candidate fields")
    if candidate.get("schema") != "bcp.capability_factory_candidate/1":
        raise ValueError("unsupported capability factory candidate")
    cid = _text(candidate.get("candidate_id"), "candidate_id", 200)
    project = _text(candidate.get("project_id"), "project_id", 128)
    requested = _text(candidate.get("requested_capability_id"), "requested_capability_id", 128)
    if not CANDIDATE_RE.fullmatch(cid) or not PROJECT_RE.fullmatch(project) or not CAPABILITY_RE.fullmatch(requested):
        raise ValueError("invalid candidate identity")
    _text(candidate.get("original_mission_id"), "original_mission_id", 128, optional=True)
    trust_class = candidate.get("trust_class")
    if trust_class not in TRUST_CLASSES or trust_class == "T0_BUILTIN":
        raise ValueError("invalid factory trust_class")
    if candidate.get("stage") == "REGISTERED":
        if trust_class not in FACTORY_PROMOTED_TRUST or not candidate.get("registration_ref"):
            raise ValueError("registered candidate requires promoted T1/T2 trust")
    elif trust_class not in {"T3_CANDIDATE", "T4_QUARANTINED"}:
        raise ValueError("candidate cannot self-claim verified trust before registration")
    source = _validate_source(candidate["source"])
    license_info = _validate_license(candidate["license"])
    manifest = validate_manifest(candidate["proposed_manifest"])
    policy = _validate_policy(candidate["policy"])
    if manifest["capability_id"] != requested:
        raise ValueError("proposed manifest does not match requested capability")
    scopes = set(manifest.get("project_scopes") or [])
    if scopes and project not in scopes and "*" not in scopes:
        raise ValueError("proposed manifest outside project scope")
    gates = candidate["gate_receipts"]
    if not isinstance(gates, dict) or set(gates) - set(GATE_SEQUENCE):
        raise ValueError("invalid gate_receipts")
    for value in gates.values():
        if value is not None:
            _text(value, "gate receipt", 200)
    if candidate["stage"] not in {
        "GAP_DETECTED", "DEFINE_CONTRACT", *GATE_STAGE.values(), "REGISTER",
        "REGISTERED", "WAITING_APPROVAL", "WAITING_RESOURCE",
        "WAITING_CAPABILITY", "QUARANTINED", "FAILED_SAFE", "SUPERSEDED",
    }:
        raise ValueError("invalid candidate stage")
    if candidate["status"] not in {"ACTIVE", "HOLD", "FAILED_SAFE", "REGISTERED", "SUPERSEDED"}:
        raise ValueError("invalid candidate status")
    hold_stages = {"WAITING_APPROVAL", "WAITING_RESOURCE", "WAITING_CAPABILITY", "QUARANTINED"}
    if candidate["stage"] in hold_stages and candidate["status"] != "HOLD":
        raise ValueError("hold stage requires HOLD status")
    if candidate["stage"] == "REGISTERED" and candidate["status"] != "REGISTERED":
        raise ValueError("REGISTERED stage requires REGISTERED status")
    if candidate["status"] == "REGISTERED" and candidate.get("registration_ref") is None:
        raise ValueError("registered candidate requires registration_ref")
    if candidate["stage"] == "FAILED_SAFE" and candidate["status"] != "FAILED_SAFE":
        raise ValueError("FAILED_SAFE stage/status mismatch")
    if candidate["stage"] == "SUPERSEDED" and candidate["status"] != "SUPERSEDED":
        raise ValueError("SUPERSEDED stage/status mismatch")
    _iso(candidate["created_at"], "created_at")
    _iso(candidate["updated_at"], "updated_at")
    if candidate.get("field_certified") is not False:
        raise ValueError("factory candidate cannot field-certify authority")
    registration_ref = candidate.get("registration_ref")
    if registration_ref is not None:
        _text(registration_ref, "registration_ref", 200)
    failure = candidate.get("failure")
    if failure is not None:
        if not isinstance(failure, dict) or set(failure) - {"code", "detail"}:
            raise ValueError("invalid candidate failure")
        _text(failure.get("code"), "failure code", 160)
        _text(failure.get("detail"), "failure detail", 2000, optional=True)
    out = deepcopy(candidate)
    out["source"] = source
    out["license"] = license_info
    out["proposed_manifest"] = manifest
    out["policy"] = policy
    return out


def _gate_idempotency(candidate_id: str, gate: str) -> str:
    candidate = _text(candidate_id, "candidate_id", 200)
    if gate not in GATE_SEQUENCE:
        raise ValueError("invalid factory gate")
    return f"factory:{candidate}:{gate}"


def _registration_id(candidate: dict[str, Any]) -> str:
    m = candidate["proposed_manifest"]
    digest = _hash_obj({
        "candidate_id": candidate["candidate_id"],
        "capability_id": m["capability_id"],
        "provider_id": m["provider_id"],
        "version": m["version"],
    })
    return "capreg-" + digest[:32]


def validate_registration(registration: Any) -> dict[str, Any]:
    required = {
        "schema", "registration_id", "candidate_id", "project_id",
        "capability_id", "provider_id", "version", "trust_class",
        "manifest", "source", "license", "gate_receipts", "registered_at", "field_certified",
    }
    optional = {"source_revision"}
    if not isinstance(registration, dict) or set(registration) - required - optional or not required <= set(registration):
        raise ValueError("invalid capability registration fields")
    if registration.get("schema") != "bcp.capability_registration/1":
        raise ValueError("unsupported capability registration")
    _text(registration["registration_id"], "registration_id", 200)
    trust_class = registration["trust_class"]
    candidate_id = registration.get("candidate_id")
    if trust_class == "T0_BUILTIN":
        if candidate_id is not None:
            raise ValueError("T0 builtin registration must not invent candidate_id")
    else:
        _text(candidate_id, "candidate_id", 200)
    project = _text(registration["project_id"], "project_id", 128)
    if not PROJECT_RE.fullmatch(project):
        raise ValueError("invalid registration project")
    manifest = validate_manifest(registration["manifest"])
    source = _validate_source(registration["source"])
    license_info = _validate_license(registration["license"])
    for field in ("capability_id", "provider_id", "version"):
        if registration[field] != manifest[field]:
            raise ValueError(f"registration {field} does not match manifest")
    if trust_class not in AUTO_TRUST:
        raise ValueError("registration requires verified trust class")
    if trust_class == "T0_BUILTIN":
        if source["kind"] != "BUILTIN":
            raise ValueError("T0 registration requires BUILTIN provenance")
    elif license_info["status"] not in {"APPROVED", "NOT_APPLICABLE"}:
        raise ValueError("verified capability registration requires approved license")
    refs = registration["gate_receipts"]
    if not isinstance(refs, list) or len(refs) != len(set(refs)):
        raise ValueError("invalid registration gate receipts")
    if trust_class != "T0_BUILTIN" and not refs:
        raise ValueError("verified registration gate receipts required")
    for ref in refs:
        _text(ref, "registration gate receipt", 200)
    _text(registration.get("source_revision"), "source_revision", 256, optional=True)
    _iso(registration["registered_at"], "registered_at")
    field_certified = registration.get("field_certified")
    if type(field_certified) is not bool:
        raise ValueError("field_certified must be boolean")
    if trust_class == "T1_VERIFIED_LOCAL" and field_certified is not True:
        raise ValueError("T1 verified-local registration requires field proof")
    if trust_class == "T0_BUILTIN" and field_certified is not False:
        raise ValueError("T0 builtin registration is qualified code, not field execution proof")
    out = deepcopy(registration)
    out["manifest"] = manifest
    out["source"] = source
    out["license"] = license_info
    return out


def _gate_required(candidate: dict[str, Any], gate: str) -> bool:
    policy = candidate["policy"]
    if gate == "build_adapter":
        return candidate["source"]["kind"] == "GENERATED_ADAPTER"
    if gate == "sandbox_test":
        return policy["require_sandbox"]
    if gate == "rollback_test":
        return policy["require_rollback"]
    if gate == "security_test":
        return policy["require_security_test"]
    if gate == "canary":
        return policy["require_canary"]
    return True


def _next_gate_after(candidate: dict[str, Any], gate: str | None) -> str | None:
    start = 0 if gate is None else GATE_SEQUENCE.index(gate) + 1
    for name in GATE_SEQUENCE[start:]:
        if _gate_required(candidate, name):
            return name
    return None


def _gate_requirements(candidate: dict[str, Any], gate: str) -> tuple[str, str, set[str], str]:
    if gate == "canary":
        manifest = candidate["proposed_manifest"]
        return (
            manifest["permission_class"],
            manifest["resource_class"],
            set(manifest["evidence_contract"]),
            candidate["policy"]["target_scope"],
        )
    return (
        GATE_PERMISSION[gate],
        GATE_RESOURCE[gate],
        set(GATE_EVIDENCE[gate]),
        GATE_MIN_SCOPE[gate],
    )


class CapabilityRegistry:
    def __init__(self, store: CriticalStore):
        self.store = store

    def get(self, capability_id: str, provider_id: str, version: str) -> dict[str, Any]:
        sid = _registration_stream(capability_id, provider_id, version)
        state = self.store.get_state(sid)
        if state is None:
            raise RegistrationNotFound(f"{capability_id}/{provider_id}/{version}")
        return state

    def list(self, *, limit: int = 1024) -> list[dict[str, Any]]:
        return self.store.list_states(REGISTRATION_PREFIX, limit=limit)

    def search(
        self,
        capability_id: str,
        *,
        project_id: str,
        minimum_trust: str = "T2_VERIFIED_REMOTE",
    ) -> list[dict[str, Any]]:
        cap = _text(capability_id, "capability_id", 128)
        project = _text(project_id, "project_id", 128)
        if not CAPABILITY_RE.fullmatch(cap) or not PROJECT_RE.fullmatch(project):
            raise ValueError("invalid capability search")
        trust_rank = {
            "T2_VERIFIED_REMOTE": 1,
            "T1_VERIFIED_LOCAL": 2,
            "T0_BUILTIN": 3,
        }
        if minimum_trust not in trust_rank:
            raise ValueError("invalid minimum_trust")
        out = []
        for state in self.list(limit=4096):
            reg = state["payload"]
            if reg["capability_id"] != cap:
                continue
            if trust_rank[reg["trust_class"]] < trust_rank[minimum_trust]:
                continue
            scopes = set(reg["manifest"].get("project_scopes") or [])
            if scopes and "*" not in scopes and project not in scopes:
                continue
            out.append(state)
        out.sort(
            key=lambda x: (
                -trust_rank[x["payload"]["trust_class"]],
                x["payload"]["provider_id"],
                x["payload"]["version"],
            )
        )
        return out

    def put(self, registration: dict[str, Any], *, owner_id: str) -> dict[str, Any]:
        clean = validate_registration(registration)
        sid = _registration_stream(
            clean["capability_id"], clean["provider_id"], clean["version"]
        )
        current = self.store.get_state(sid)
        if current is not None:
            if current["payload"] == clean:
                return current
            raise RegistrationCollision(
                "capability/provider/version already registered with different content"
            )
        fence = self.store.acquire_writer_fence(sid, owner_id)
        self.store.commit_transition(
            stream_id=sid,
            expected_revision=0,
            new_revision=1,
            fencing_token=fence,
            payload=clean,
            destination="BCP_CAPABILITY_REGISTRY",
        )
        return self.get(clean["capability_id"], clean["provider_id"], clean["version"])


class CapabilityFactory:
    def __init__(self, store: CriticalStore):
        self.store = store
        self.receipts = ActionReceiptRegistry(store)
        self.registry = CapabilityRegistry(store)

    def get(self, project_id: str, candidate_id: str) -> dict[str, Any]:
        state = self.store.get_state(_candidate_stream(project_id, candidate_id))
        if state is None:
            raise CandidateNotFound(candidate_id)
        return state

    def list(self, project_id: str | None = None, *, limit: int = 512) -> list[dict[str, Any]]:
        prefix = CANDIDATE_PREFIX
        if project_id is not None:
            project = _text(project_id, "project_id", 128)
            if not PROJECT_RE.fullmatch(project):
                raise ValueError("invalid project_id")
            prefix += project + "/"
        return self.store.list_states(prefix, limit=limit)

    def find_reusable(
        self,
        project_id: str,
        capability_id: str,
    ) -> list[dict[str, Any]]:
        return self.registry.search(
            capability_id,
            project_id=project_id,
            minimum_trust="T2_VERIFIED_REMOTE",
        )

    def _put(self, candidate: dict[str, Any], *, owner_id: str) -> dict[str, Any]:
        clean = validate_candidate(candidate)
        sid = _candidate_stream(clean["project_id"], clean["candidate_id"])
        current = self.store.get_state(sid)
        rev = int(current["revision"]) if current else 0
        if current is not None and current["payload"] == clean:
            return current
        fence = self.store.acquire_writer_fence(sid, owner_id)
        self.store.commit_transition(
            stream_id=sid,
            expected_revision=rev,
            new_revision=rev + 1,
            fencing_token=fence,
            payload=clean,
            destination="BCP_CAPABILITY_FACTORY",
        )
        return self.get(clean["project_id"], clean["candidate_id"])

    def create(
        self,
        *,
        candidate_id: str,
        project_id: str,
        original_mission_id: str | None,
        requested_capability_id: str,
        trust_class: str,
        source: dict[str, Any],
        license_info: dict[str, Any],
        proposed_manifest: dict[str, Any],
        policy: dict[str, Any],
        owner_id: str,
        now: str,
    ) -> dict[str, Any]:
        manifest = validate_manifest(proposed_manifest)
        policy = _validate_policy(policy)
        source = _validate_source(source)
        license_info = _validate_license(license_info)
        stage = "REUSE_SEARCH"
        status = "ACTIVE"
        failure = None

        if manifest["capability_id"] != requested_capability_id:
            raise ValueError("requested capability and manifest mismatch")
        if trust_class not in {"T3_CANDIDATE", "T4_QUARANTINED"}:
            raise ValueError("new factory candidate must start T3 or T4")
        if manifest["permission_class"] == "P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE":
            raise ValueError("P4 capability factory qualification requires a separate human-approved lane")
        if manifest["resource_class"] == "R4_LOCAL_AI":
            raise ValueError("R4 local AI qualification is deferred to Phase 10")
        if isinstance(manifest.get("executor"), dict) and manifest["executor"].get("kind") == "MODEL":
            raise ValueError("MODEL executor qualification is deferred to Phase 10")
        if not policy["require_sandbox"] or not policy["require_security_test"] or not policy["require_canary"]:
            raise ValueError("automatic factory requires sandbox, security test and canary")
        if isinstance(manifest.get("rollback"), dict) and manifest["rollback"].get("required") is True and not policy["require_rollback"]:
            raise ValueError("factory policy cannot disable required rollback test")
        if trust_class == "T4_QUARANTINED":
            stage, status = "QUARANTINED", "HOLD"
            failure = {"code": "SOURCE_QUARANTINED", "detail": "source trust class is T4"}
        elif license_info["status"] == "DENIED":
            stage, status = "QUARANTINED", "HOLD"
            failure = {"code": "LICENSE_DENIED", "detail": "license policy denied source"}
        elif PERMISSION_ORDER[manifest["permission_class"]] > PERMISSION_ORDER[policy["max_permission_class"]]:
            stage, status = "WAITING_APPROVAL", "HOLD"
            failure = {"code": "PERMISSION_CEILING", "detail": manifest["permission_class"]}
        elif RESOURCE_ORDER[manifest["resource_class"]] > RESOURCE_ORDER[policy["max_resource_class"]]:
            stage, status = "WAITING_RESOURCE", "HOLD"
            failure = {"code": "RESOURCE_CEILING", "detail": manifest["resource_class"]}

        candidate = {
            "schema": "bcp.capability_factory_candidate/1",
            "candidate_id": candidate_id,
            "project_id": project_id,
            "original_mission_id": original_mission_id,
            "requested_capability_id": requested_capability_id,
            "stage": stage,
            "status": status,
            "trust_class": trust_class,
            "source": source,
            "license": license_info,
            "proposed_manifest": manifest,
            "policy": policy,
            "gate_receipts": {},
            "registration_ref": None,
            "failure": failure,
            "created_at": _iso(now, "now"),
            "updated_at": _iso(now, "now"),
            "field_certified": False,
        }
        existing = self.store.get_state(_candidate_stream(project_id, candidate_id))
        if existing is not None:
            if existing["payload"] == validate_candidate(candidate):
                return existing
            raise CandidateCollision("candidate_id already committed with different content")
        return self._put(candidate, owner_id=owner_id)

    def plan_next(
        self,
        project_id: str,
        candidate_id: str,
        *,
        resource_mode: str,
    ) -> dict[str, Any]:
        state = self.get(project_id, candidate_id)
        candidate = state["payload"]
        if candidate["status"] != "ACTIVE":
            return {
                "schema": "bcp.capability_factory_plan/1",
                "candidate_id": candidate_id,
                "project_id": project_id,
                "decision": candidate["stage"],
                "gate": None,
                "capability_id": None,
                "permission_class": None,
                "resource_class": None,
                "target_scope": None,
                "input": {},
                "evidence_contract": [],
                "field_certified": False,
            }
        current_gate = next(
            (name for name, stage in GATE_STAGE.items() if stage == candidate["stage"]),
            None,
        )
        if candidate["stage"] == "REUSE_SEARCH":
            current_gate = "reuse_search"
        if current_gate is None:
            if candidate["stage"] == "REGISTER":
                return {
                    "schema": "bcp.capability_factory_plan/1",
                    "candidate_id": candidate_id,
                    "project_id": project_id,
                    "decision": "REGISTER_READY",
                    "gate": None,
                    "capability_id": None,
                    "permission_class": None,
                    "resource_class": None,
                    "target_scope": None,
                    "input": {},
                    "evidence_contract": [],
                    "field_certified": False,
                }
            raise CandidateTransitionError(f"candidate stage is not executable: {candidate['stage']}")

        permission, resource, evidence, scope = _gate_requirements(candidate, current_gate)
        if PERMISSION_ORDER[permission] > PERMISSION_ORDER[candidate["policy"]["max_permission_class"]]:
            return {
                "schema": "bcp.capability_factory_plan/1",
                "candidate_id": candidate_id,
                "project_id": project_id,
                "decision": "WAITING_APPROVAL",
                "gate": current_gate,
                "capability_id": GATE_CAPABILITY[current_gate],
                "permission_class": permission,
                "resource_class": resource,
                "target_scope": scope,
                "input": {},
                "evidence_contract": sorted(evidence),
                "field_certified": False,
            }
        if RESOURCE_ORDER[resource] > RESOURCE_ORDER[candidate["policy"]["max_resource_class"]]:
            decision = "WAITING_RESOURCE"
        else:
            admission = resource_decide(
                resource, mode=resource_mode, background=False, essential=False
            )
            decision = "EXECUTE_TYPED_GATE" if admission.allowed else "WAITING_RESOURCE"
        return {
            "schema": "bcp.capability_factory_plan/1",
            "candidate_id": candidate_id,
            "project_id": project_id,
            "decision": decision,
            "gate": current_gate,
            "capability_id": GATE_CAPABILITY[current_gate],
            "permission_class": permission,
            "resource_class": resource,
            "target_scope": scope,
            "input": {
                "candidate_id": candidate_id,
                "idempotency_key": _gate_idempotency(candidate_id, current_gate),
                "requested_capability_id": candidate["requested_capability_id"],
                "source": deepcopy(candidate["source"]),
                "trust_class": candidate["trust_class"],
                "license": deepcopy(candidate["license"]),
                "proposed_manifest": deepcopy(candidate["proposed_manifest"]),
            },
            "evidence_contract": sorted(evidence),
            "field_certified": False,
        }

    def record_gate(
        self,
        project_id: str,
        candidate_id: str,
        *,
        gate: str,
        receipt_id: str,
        owner_id: str,
        now: str,
        trust_class: str | None = None,
        license_status: str | None = None,
        license_identifier: str | None = None,
    ) -> dict[str, Any]:
        if gate not in GATE_SEQUENCE:
            raise CandidateTransitionError("unknown factory gate")
        state = self.get(project_id, candidate_id)
        candidate = deepcopy(state["payload"])
        if candidate["status"] != "ACTIVE":
            raise CandidateTransitionError("candidate is not active")
        if candidate["stage"] != GATE_STAGE[gate]:
            raise CandidateTransitionError(
                f"gate/stage mismatch: gate={gate} stage={candidate['stage']}"
            )

        permission, resource, required_evidence, min_scope = _gate_requirements(candidate, gate)
        del permission, resource
        field = gate == "canary" and min_scope == "FIELD"
        try:
            receipt_state = self.receipts.require_success(
                receipt_id, project_scopes=[project_id], field=field
            )
        except (ActionReceiptError, ActionReceiptValidationError) as exc:
            raise CandidateTransitionError("factory gate receipt invalid: " + str(exc)) from exc
        receipt = receipt_state["payload"]
        if receipt["idempotency_key"] != _gate_idempotency(candidate_id, gate):
            raise CandidateTransitionError("receipt idempotency key does not match candidate gate")
        if receipt["capability_id"] != GATE_CAPABILITY[gate]:
            raise CandidateTransitionError("receipt capability does not match factory gate")
        if SCOPE_ORDER[receipt["proof_scope"]] < SCOPE_ORDER[min_scope]:
            raise CandidateTransitionError("receipt proof scope below gate requirement")
        source_revision = candidate["source"].get("revision")
        receipt_revision = receipt.get("source_revision")
        if source_revision is not None and receipt_revision is not None and receipt_revision != source_revision:
            raise CandidateTransitionError("receipt source revision does not match candidate")
        pass_kinds = {
            item["kind"] for item in receipt.get("evidence") or []
            if item.get("status") == "PASS"
        }
        missing = required_evidence - pass_kinds
        if missing:
            raise CandidateTransitionError(
                "factory gate evidence incomplete: " + ",".join(sorted(missing))
            )

        candidate["gate_receipts"][gate] = receipt_id
        candidate["updated_at"] = _iso(now, "now")
        candidate["failure"] = None

        if gate == "source_trust":
            if trust_class not in {"T3_CANDIDATE", "T4_QUARANTINED"}:
                raise CandidateTransitionError("source trust gate may keep T3 or quarantine T4 only")
            candidate["trust_class"] = trust_class
            if trust_class == "T4_QUARANTINED":
                candidate["stage"] = "QUARANTINED"
                candidate["status"] = "HOLD"
                candidate["failure"] = {"code": "SOURCE_QUARANTINED", "detail": None}
                return self._put(candidate, owner_id=owner_id)
        if gate == "license_policy":
            if license_status is None or license_status not in LICENSE_STATES:
                raise CandidateTransitionError("license gate requires resulting license status")
            candidate["license"]["status"] = license_status
            candidate["license"]["identifier"] = license_identifier
            refs = list(candidate["license"].get("evidence_refs") or [])
            if receipt_id not in refs:
                refs.append(receipt_id)
            candidate["license"]["evidence_refs"] = refs
            if license_status == "DENIED":
                candidate["stage"] = "QUARANTINED"
                candidate["status"] = "HOLD"
                candidate["failure"] = {"code": "LICENSE_DENIED", "detail": license_identifier}
                return self._put(candidate, owner_id=owner_id)
            if license_status not in {"APPROVED", "NOT_APPLICABLE"}:
                candidate["stage"] = "WAITING_APPROVAL"
                candidate["status"] = "HOLD"
                candidate["failure"] = {"code": "LICENSE_REVIEW_REQUIRED", "detail": license_status}
                return self._put(candidate, owner_id=owner_id)

        if gate == "build_adapter" and candidate["source"].get("artifact_sha256") is None:
            artifact_hash = receipt.get("output_hash")
            if artifact_hash is None:
                for item in receipt.get("evidence") or []:
                    if item.get("status") == "PASS" and item.get("sha256"):
                        artifact_hash = item["sha256"]
                        break
            if artifact_hash is not None and SHA_RE.fullmatch(str(artifact_hash)):
                candidate["source"]["artifact_sha256"] = str(artifact_hash).lower()
            if candidate["source"].get("revision") is None and receipt.get("source_revision"):
                candidate["source"]["revision"] = receipt["source_revision"]

        next_gate = _next_gate_after(candidate, gate)
        candidate["stage"] = "REGISTER" if next_gate is None else GATE_STAGE[next_gate]
        return self._put(candidate, owner_id=owner_id)

    def register(
        self,
        project_id: str,
        candidate_id: str,
        *,
        owner_id: str,
        now: str,
    ) -> dict[str, Any]:
        state = self.get(project_id, candidate_id)
        candidate = deepcopy(state["payload"])
        if candidate["status"] != "ACTIVE" or candidate["stage"] != "REGISTER":
            raise CandidateTransitionError("candidate is not registration-ready")
        manifest = candidate["proposed_manifest"]
        if candidate["trust_class"] != "T3_CANDIDATE":
            raise CandidateTransitionError("registration requires a T3 candidate that completed all gates")
        if candidate["license"]["status"] not in {"APPROVED", "NOT_APPLICABLE"}:
            raise CandidateTransitionError("candidate license is not registration-qualified")
        if PERMISSION_ORDER[manifest["permission_class"]] > PERMISSION_ORDER[AUTO_PERMISSION_MAX]:
            raise CandidateTransitionError("P4 capability requires fresh human approval outside auto factory")
        if PERMISSION_ORDER[manifest["permission_class"]] > PERMISSION_ORDER[candidate["policy"]["max_permission_class"]]:
            raise CandidateTransitionError("manifest permission exceeds factory policy")
        if RESOURCE_ORDER[manifest["resource_class"]] > RESOURCE_ORDER[candidate["policy"]["max_resource_class"]]:
            raise CandidateTransitionError("manifest resource exceeds factory policy")

        required_gates = [
            gate for gate in GATE_SEQUENCE if _gate_required(candidate, gate)
        ]
        missing = [
            gate for gate in required_gates
            if not candidate["gate_receipts"].get(gate)
        ]
        if missing:
            raise CandidateTransitionError(
                "registration missing gates: " + ",".join(missing)
            )

        canary_ref = candidate["gate_receipts"].get("canary")
        if not canary_ref:
            raise CandidateTransitionError("registration requires canary receipt")
        canary = self.receipts.get(canary_ref)["payload"]
        if canary["proof_scope"] == "FIELD" and canary.get("field_certified") is True:
            target_trust = "T1_VERIFIED_LOCAL"
            field_certified = True
        elif canary["proof_scope"] in {"PROVIDER", "FIELD"}:
            target_trust = "T2_VERIFIED_REMOTE"
            field_certified = bool(canary.get("field_certified"))
        else:
            raise CandidateTransitionError("repository/simulation canary cannot promote unattended capability")
        if target_trust not in candidate["policy"]["allowed_trust_classes"]:
            raise CandidateTransitionError("canary-derived trust class is not allowed by policy")

        registration = {
            "schema": "bcp.capability_registration/1",
            "registration_id": _registration_id(candidate),
            "candidate_id": candidate_id,
            "project_id": project_id,
            "capability_id": manifest["capability_id"],
            "provider_id": manifest["provider_id"],
            "version": manifest["version"],
            "trust_class": target_trust,
            "manifest": deepcopy(manifest),
            "source": deepcopy(candidate["source"]),
            "license": deepcopy(candidate["license"]),
            "gate_receipts": [
                candidate["gate_receipts"][gate] for gate in required_gates
            ],
            "source_revision": candidate["source"].get("revision"),
            "registered_at": _iso(now, "now"),
            "field_certified": field_certified,
        }
        registered = self.registry.put(registration, owner_id=owner_id)
        candidate["stage"] = "REGISTERED"
        candidate["status"] = "REGISTERED"
        candidate["trust_class"] = target_trust
        candidate["registration_ref"] = registration["registration_id"]
        candidate["updated_at"] = _iso(now, "now")
        self._put(candidate, owner_id=owner_id)
        return registered


__all__ = [
    "CapabilityFactory",
    "CapabilityRegistry",
    "CapabilityFactoryError",
    "CandidateNotFound",
    "CandidateCollision",
    "CandidateTransitionError",
    "RegistrationNotFound",
    "RegistrationCollision",
    "validate_manifest",
    "validate_candidate",
    "validate_registration",
]
