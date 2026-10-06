from __future__ import annotations

"""Durable Desired State Registry on the shared BCP CriticalStore.

Phase 4 candidate. Desired spec generations and observed status are separated logically
while remaining one durable authority stream. No scheduler or second database is created.
"""

import copy
import datetime as dt
import re
from typing import Any

from .critical_store import CriticalStore


DESIRED_PREFIX = "desired/"
PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
RESOURCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,159}$")
KIND_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{2,127}$")
PHASES = {
    "UNKNOWN","IN_SYNC","DRIFTED","RECONCILING","WAITING_RESOURCE",
    "WAITING_CAPABILITY","AUTH_REQUIRED","DEGRADED","FAILED_SAFE",
}
RECONCILE_MODES = {"OBSERVE_ONLY","AUTO_SAFE","AUTO_PROJECT","AUTO_BOUNDED_SYSTEM"}
PERMISSIONS = {
    "P0_READ","P1_SAFE_WRITE","P2_PROJECT_MUTATION","P3_BOUNDED_SYSTEM_CHANGE",
}
RESOURCES = {"R0_TINY","R1_LIGHT","R2_MEDIUM","R3_HEAVY","R4_LOCAL_AI"}
OWNERS = {"USER","CHATGPT","BCP_POLICY","PROJECT_ADAPTER"}
CONDITION_STATUS = {"TRUE","FALSE","UNKNOWN"}
TOP_LEVEL_KEYS = {"schema","api_version","kind","metadata","spec","status"}


class DesiredStateError(RuntimeError):
    pass


class DesiredStateNotFound(DesiredStateError):
    pass


class DesiredGenerationConflict(DesiredStateError):
    pass


def _text(value: Any, field: str, max_len: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be string")
    text = value.strip()
    if not text or len(text) > max_len:
        raise ValueError(f"invalid {field}")
    return text


def _iso(value: Any, field: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    text = _text(value, field, 96)
    probe = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = dt.datetime.fromisoformat(probe)
    except ValueError as exc:
        raise ValueError(f"invalid {field}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return text


def stream_id(project_id: str, resource_id: str) -> str:
    project = _text(project_id, "project_id", 128)
    resource = _text(resource_id, "resource_id", 160)
    if not PROJECT_RE.fullmatch(project) or not RESOURCE_RE.fullmatch(resource):
        raise ValueError("invalid desired state identifier")
    return f"{DESIRED_PREFIX}{project}/{resource}"


def validate_resource(resource: Any) -> dict[str, Any]:
    if not isinstance(resource, dict):
        raise ValueError("desired state resource must be object")
    if set(resource) != TOP_LEVEL_KEYS:
        raise ValueError("invalid desired state top-level fields")
    if resource.get("schema") != "bcp.desired_state_resource/1":
        raise ValueError("unsupported desired state schema")
    if resource.get("api_version") != "bcp/v1":
        raise ValueError("unsupported api_version")
    kind = _text(resource.get("kind"), "kind", 128)
    if not KIND_RE.fullmatch(kind):
        raise ValueError("invalid kind")

    metadata = resource.get("metadata")
    allowed_metadata = {"resource_id","project_id","generation","created_at","updated_at","owner"}
    required_metadata = {"resource_id","project_id","generation","created_at"}
    if not isinstance(metadata, dict) or set(metadata) - allowed_metadata or not required_metadata <= set(metadata):
        raise ValueError("invalid metadata fields")
    resource_id = _text(metadata.get("resource_id"), "resource_id", 160)
    project_id = _text(metadata.get("project_id"), "project_id", 128)
    if not RESOURCE_RE.fullmatch(resource_id) or not PROJECT_RE.fullmatch(project_id):
        raise ValueError("invalid metadata identifiers")
    generation = metadata.get("generation")
    if type(generation) is not int or generation < 1:
        raise ValueError("generation must be integer >=1")
    _iso(metadata.get("created_at"), "created_at")
    _iso(metadata.get("updated_at"), "updated_at", optional=True)
    if metadata.get("owner") is not None and metadata.get("owner") not in OWNERS:
        raise ValueError("invalid desired state owner")

    spec = resource.get("spec")
    allowed_spec = {"desired","reconcile_policy","evidence_contract","dependencies"}
    if not isinstance(spec, dict) or set(spec) - allowed_spec:
        raise ValueError("invalid spec fields")
    if not {"desired","reconcile_policy"} <= set(spec) or not isinstance(spec.get("desired"), dict):
        raise ValueError("spec.desired required")
    policy = spec.get("reconcile_policy")
    allowed_policy = {
        "mode","max_permission_class","resource_ceiling",
        "repair_backoff_seconds","max_attempts_per_incident",
    }
    if not isinstance(policy, dict) or set(policy) - allowed_policy:
        raise ValueError("invalid reconcile_policy fields")
    if not {"mode","max_permission_class"} <= set(policy):
        raise ValueError("reconcile_policy required fields missing")
    if policy.get("mode") not in RECONCILE_MODES:
        raise ValueError("invalid reconcile mode")
    if policy.get("max_permission_class") not in PERMISSIONS:
        raise ValueError("invalid max_permission_class")
    if policy.get("resource_ceiling") is not None and policy.get("resource_ceiling") not in RESOURCES:
        raise ValueError("invalid resource_ceiling")
    if "max_attempts_per_incident" in policy:
        attempts = policy["max_attempts_per_incident"]
        if type(attempts) is not int or not 1 <= attempts <= 20:
            raise ValueError("invalid max_attempts_per_incident")
    if "repair_backoff_seconds" in policy:
        backoff = policy["repair_backoff_seconds"]
        if type(backoff) is not int or not 1 <= backoff <= 86400:
            raise ValueError("invalid repair_backoff_seconds")

    evidence = spec.get("evidence_contract") or []
    if not isinstance(evidence, list) or len(evidence) != len(set(evidence)):
        raise ValueError("invalid evidence_contract")
    for item in evidence:
        _text(item, "evidence_contract item", 128)
    dependencies = spec.get("dependencies") or []
    if not isinstance(dependencies, list) or len(dependencies) != len(set(dependencies)):
        raise ValueError("invalid dependencies")
    for item in dependencies:
        _text(item, "dependency", 160)

    status = resource.get("status")
    allowed_status = {
        "observed_generation","phase","last_observed_at","last_reconciled_at","conditions",
    }
    if not isinstance(status, dict) or set(status) - allowed_status:
        raise ValueError("invalid status fields")
    if not {"observed_generation","phase"} <= set(status):
        raise ValueError("status required fields missing")
    if status.get("phase") not in PHASES:
        raise ValueError("invalid status phase")
    observed = status.get("observed_generation")
    if type(observed) is not int or observed < 0 or observed > generation:
        raise ValueError("observed_generation outside desired generation")
    if status.get("phase") == "IN_SYNC" and observed != generation:
        raise ValueError("IN_SYNC requires current desired generation observation")
    _iso(status.get("last_observed_at"), "last_observed_at", optional=True)
    _iso(status.get("last_reconciled_at"), "last_reconciled_at", optional=True)

    conditions = status.get("conditions") or []
    if not isinstance(conditions, list):
        raise ValueError("conditions must be list")
    allowed_condition = {"type","status","reason","evidence_ref"}
    for condition in conditions:
        if not isinstance(condition, dict) or set(condition) - allowed_condition:
            raise ValueError("invalid condition fields")
        if not {"type","status"} <= set(condition):
            raise ValueError("condition required fields missing")
        _text(condition.get("type"), "condition type", 128)
        if condition.get("status") not in CONDITION_STATUS:
            raise ValueError("invalid condition status")
        if condition.get("reason") is not None:
            _text(condition.get("reason"), "condition reason", 256)
        if condition.get("evidence_ref") is not None:
            _text(condition.get("evidence_ref"), "condition evidence_ref", 512)

    return copy.deepcopy(resource)

def deep_drift(desired: Any, observed: Any, path: str = "$") -> list[dict[str, Any]]:
    """Deterministic subset drift: extra observed fields are tolerated."""
    out: list[dict[str, Any]] = []
    if isinstance(desired, dict):
        if not isinstance(observed, dict):
            return [{"path": path, "reason": "TYPE_MISMATCH", "expected": desired, "observed": observed}]
        for key in sorted(desired):
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            child = f"{path}/{escaped}"
            if key not in observed:
                out.append({"path": child, "reason": "MISSING", "expected": desired[key], "observed": None})
            else:
                out.extend(deep_drift(desired[key], observed[key], child))
    elif isinstance(desired, list):
        if not isinstance(observed, list) or desired != observed:
            out.append({"path": path, "reason": "VALUE_MISMATCH", "expected": desired, "observed": observed})
    elif desired != observed:
        out.append({"path": path, "reason": "VALUE_MISMATCH", "expected": desired, "observed": observed})
    return out


def _spec_projection(resource: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(resource["metadata"])
    # updated_at is metadata about the write, not desired semantics.
    metadata.pop("updated_at", None)
    return {
        "schema": resource["schema"],
        "api_version": resource["api_version"],
        "kind": resource["kind"],
        "metadata": metadata,
        "spec": resource["spec"],
    }


class DesiredStateRegistry:
    def __init__(self, store: CriticalStore):
        self.store = store

    def get(self, project_id: str, resource_id: str) -> dict[str, Any]:
        state = self.store.get_state(stream_id(project_id, resource_id))
        if state is None:
            raise DesiredStateNotFound(f"{project_id}/{resource_id}")
        return {
            "resource": state["payload"],
            "revision": state["revision"],
            "content_hash": state["content_hash"],
            "fencing_token": state["fencing_token"],
            "committed_epoch": state["committed_epoch"],
        }

    def list(self, project_id: str | None = None, *, limit: int = 512) -> list[dict[str, Any]]:
        prefix = DESIRED_PREFIX if project_id is None else f"{DESIRED_PREFIX}{_text(project_id,'project_id',128)}/"
        states = self.store.list_states(prefix, limit=limit)
        return [
            {
                "resource": x["payload"],
                "revision": x["revision"],
                "content_hash": x["content_hash"],
                "fencing_token": x["fencing_token"],
                "committed_epoch": x["committed_epoch"],
            }
            for x in states
        ]

    def drift(self, project_id: str, resource_id: str, observed: dict[str, Any]) -> list[dict[str, Any]]:
        item = self.get(project_id, resource_id)
        if not isinstance(observed, dict):
            raise ValueError("observed must be object")
        return deep_drift(item["resource"]["spec"]["desired"], observed)

    def put_spec(self, resource: dict[str, Any], *, owner_id: str) -> dict[str, Any]:
        incoming = validate_resource(resource)
        meta = incoming["metadata"]
        sid = stream_id(meta["project_id"], meta["resource_id"])
        current = self.store.get_state(sid)
        current_generation = int(current["payload"]["metadata"]["generation"]) if current else 0
        incoming_generation = int(meta["generation"])

        if current is None:
            if incoming_generation != 1:
                raise DesiredGenerationConflict("first desired generation must be 1")
            if int(incoming["status"]["observed_generation"]) != 0 or incoming["status"]["phase"] != "UNKNOWN":
                raise DesiredGenerationConflict("first desired generation must start unobserved/UNKNOWN")
        else:
            if incoming_generation == current_generation:
                if _spec_projection(current["payload"]) != _spec_projection(incoming):
                    raise DesiredGenerationConflict("same generation cannot change desired spec")
                return {
                    "schema": "bcp.desired_state_receipt/1",
                    "status": "UNCHANGED",
                    "project_id": meta["project_id"],
                    "resource_id": meta["resource_id"],
                    "generation": current_generation,
                    "revision": current["revision"],
                    "content_hash": current["content_hash"],
                    "idempotent_replay": True,
                    "field_certified": False,
                }
            if incoming_generation != current_generation + 1:
                raise DesiredGenerationConflict(
                    f"generation must advance exactly by one: current={current_generation} incoming={incoming_generation}"
                )
            if int(incoming["status"]["observed_generation"]) > current_generation:
                raise DesiredGenerationConflict("desired writer cannot self-observe the new generation")

        fence = self.store.acquire_writer_fence(sid, owner_id)
        receipt = self.store.commit_transition(
            stream_id=sid,
            expected_revision=int(current["revision"]) if current else 0,
            new_revision=(int(current["revision"]) if current else 0) + 1,
            fencing_token=fence,
            payload=incoming,
            destination="BCP_DESIRED_STATE",
        )
        return {
            "schema": "bcp.desired_state_receipt/1",
            "status": receipt.status,
            "project_id": meta["project_id"],
            "resource_id": meta["resource_id"],
            "generation": incoming_generation,
            "revision": receipt.revision,
            "fencing_token": receipt.fencing_token,
            "content_hash": receipt.content_hash,
            "outbox_message_id": receipt.outbox_message_id,
            "idempotent_replay": receipt.idempotent_replay,
            "field_certified": False,
        }

    def update_status(
        self,
        project_id: str,
        resource_id: str,
        status: dict[str, Any],
        *,
        expected_generation: int,
        owner_id: str,
        updated_at: str | None = None,
    ) -> dict[str, Any]:
        sid = stream_id(project_id, resource_id)
        current = self.store.get_state(sid)
        if current is None:
            raise DesiredStateNotFound(f"{project_id}/{resource_id}")
        payload = copy.deepcopy(current["payload"])
        generation = int(payload["metadata"]["generation"])
        if int(expected_generation) != generation:
            raise DesiredGenerationConflict(
                f"status update generation mismatch: expected={expected_generation} current={generation}"
            )
        if not isinstance(status, dict):
            raise ValueError("status must be object")
        candidate = copy.deepcopy(payload)
        candidate["status"] = copy.deepcopy(status)
        if updated_at is not None:
            candidate["metadata"]["updated_at"] = _text(updated_at, "updated_at", 80)
        validate_resource(candidate)

        if candidate == payload:
            return {
                "schema": "bcp.desired_state_status_receipt/1",
                "status": "UNCHANGED",
                "project_id": project_id,
                "resource_id": resource_id,
                "generation": generation,
                "revision": current["revision"],
                "field_certified": False,
            }

        fence = self.store.acquire_writer_fence(sid, owner_id)
        receipt = self.store.commit_transition(
            stream_id=sid,
            expected_revision=int(current["revision"]),
            new_revision=int(current["revision"]) + 1,
            fencing_token=fence,
            payload=candidate,
            destination="BCP_DESIRED_STATE",
        )
        return {
            "schema": "bcp.desired_state_status_receipt/1",
            "status": receipt.status,
            "project_id": project_id,
            "resource_id": resource_id,
            "generation": generation,
            "revision": receipt.revision,
            "fencing_token": receipt.fencing_token,
            "content_hash": receipt.content_hash,
            "outbox_message_id": receipt.outbox_message_id,
            "field_certified": False,
        }


__all__ = [
    "DesiredStateRegistry",
    "DesiredStateError",
    "DesiredStateNotFound",
    "DesiredGenerationConflict",
    "validate_resource",
    "deep_drift",
    "stream_id",
]
