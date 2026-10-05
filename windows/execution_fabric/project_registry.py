from __future__ import annotations

"""Provider-neutral BCP Project Registry backed by the fenced CriticalStore.

Phase 3 candidate. Project records are durable authority streams, not a second database.
Unknown roots/repositories/Drive objects stay explicit; this module never discovers or
invents a binding on behalf of a project.
"""

import re
from typing import Any

from .critical_store import CriticalStore, RevisionConflict


PROJECT_PREFIX = "project/"
PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")

PROJECT_STATUS = {
    "ACTIVE", "PAUSED", "FROZEN", "ARCHIVED",
    "BINDING_INCOMPLETE", "DEGRADED", "UNKNOWN",
}
PROJECT_PROFILE = {
    "SOFTWARE_ENGINEERING", "KNOWLEDGE_CORPUS", "ANALYTICAL_PIPELINE",
    "EDITORIAL_MEDIA", "CONTROL_PLANE", "DELIVERY_PROVIDER",
    "SPECIALIZED_EXECUTOR", "GENERAL", "ARCHIVE_CLOSED",
}
AUTH_ENGINEERING = {"GITHUB", "DRIVE", "LOCAL", "MIXED", "NONE", "UNRESOLVED"}
AUTH_RUNTIME = {"PC", "B_EDGE", "NEXUS", "DRIVE", "PC_DRIVE", "REMOTE_PROVIDER", "NONE", "UNRESOLVED"}
AUTH_ARTIFACTS = {"DRIVE", "GITHUB_RELEASES", "LOCAL_DRIVE", "BUILDHUB", "MIXED", "NONE", "UNRESOLVED"}
PERMISSION_CLASS = {
    "P0_READ", "P1_SAFE_WRITE", "P2_PROJECT_MUTATION",
    "P3_BOUNDED_SYSTEM_CHANGE", "P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE",
}
RESOURCE_CLASS = {"R0_TINY", "R1_LIGHT", "R2_MEDIUM", "R3_HEAVY", "R4_LOCAL_AI"}
BACKGROUND_POLICY = {"NEVER", "GREEN_ONLY", "GREEN_OR_AMBER_LIGHT", "USER_EXPLICIT"}
PROJECT_WRITE_POLICY = {"DENY", "POLICY", "ALLOW"}
SYSTEM_MODIFY_POLICY = {"DENY", "GATED", "POLICY", "ALLOW"}
UPDATE_MODE = {"PROJECT_DEFINED", "BCP_MANAGED", "EXTERNAL_PROVIDER", "NONE", "UNRESOLVED"}

TOP_LEVEL_KEYS = {
    "schema", "project_id", "display_name", "aliases", "profile", "status",
    "continuation_codes", "authority", "origins", "adapters", "resource_profile",
    "permission_profile", "update_profile", "head_revision", "coordinator_epoch",
    "source_revision", "compatibility", "updated_at",
}



class ProjectRegistryError(RuntimeError):
    pass


class ProjectNotFound(ProjectRegistryError):
    pass


class ProjectAliasAmbiguous(ProjectRegistryError):
    pass


class ProjectRevisionConflict(ProjectRegistryError):
    pass


def _bounded_text(value: Any, field: str, max_len: int) -> str:
    text = str(value or "").strip()
    if not text or len(text) > max_len:
        raise ValueError(f"invalid {field}")
    return text


def _validate_binding_list(items: Any, kind: str) -> None:
    if not isinstance(items, list):
        raise ValueError(f"{kind} must be list")
    status_by_kind = {
        "local_roots": {"BOUND", "CANDIDATE", "UNRESOLVED", "NOT_REQUIRED"},
        "repos": {"BOUND", "CANDIDATE", "UNRESOLVED", "NOT_REQUIRED"},
        "drive_refs": {"BOUND", "PARTIAL", "UNRESOLVED", "NOT_REQUIRED"},
    }
    authority_by_kind = {
        "local_roots": {"CANONICAL", "COMPATIBILITY", "RUNTIME", "CANDIDATE", "UNRESOLVED"},
        "repos": {"CANONICAL", "ENGINEERING", "COMPATIBILITY", "CANDIDATE", "UNRESOLVED"},
        "drive_refs": {"CANONICAL", "COMPATIBILITY", "ARTIFACT", "CANDIDATE", "UNRESOLVED"},
    }
    allowed_keys = {
        "local_roots": {"status", "path", "authority"},
        "repos": {"status", "repository", "branch", "path", "authority"},
        "drive_refs": {"status", "id", "title", "role", "authority"},
    }
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"{kind} item must be object")
        if set(item) - allowed_keys[kind]:
            raise ValueError(f"unexpected {kind} field")
        status = str(item.get("status") or "")
        if status not in status_by_kind[kind]:
            raise ValueError(f"invalid {kind} status")
        authority = str(item.get("authority") or "")
        if authority not in authority_by_kind[kind]:
            raise ValueError(f"invalid {kind} authority")
        if kind == "local_roots":
            if "path" not in item:
                raise ValueError("local root path required")
            value = item.get("path")
            if value is not None and (not isinstance(value, str) or len(value) > 1024):
                raise ValueError("invalid local root path")
            if status == "BOUND" and not str(value or "").strip():
                raise ValueError("BOUND local root requires path")
            if status == "UNRESOLVED" and value not in (None, ""):
                raise ValueError("UNRESOLVED local root must not assert path")
        elif kind == "repos":
            if not {"repository", "authority", "status"} <= set(item):
                raise ValueError("repo required fields missing")
            value = item.get("repository")
            if value is not None and (not isinstance(value, str) or len(value) > 300):
                raise ValueError("invalid repository")
            for field, cap in (("branch", 300), ("path", 1024)):
                v = item.get(field)
                if v is not None and (not isinstance(v, str) or len(v) > cap):
                    raise ValueError(f"invalid repo {field}")
            if status == "BOUND" and not str(value or "").strip():
                raise ValueError("BOUND repo requires repository")
            if status == "UNRESOLVED" and value not in (None, ""):
                raise ValueError("UNRESOLVED repo must not assert repository")
        elif kind == "drive_refs":
            if not {"id", "role", "authority", "status"} <= set(item):
                raise ValueError("Drive binding required fields missing")
            value = item.get("id")
            if value is not None and (not isinstance(value, str) or len(value) > 512):
                raise ValueError("invalid Drive id")
            _bounded_text(item.get("role"), "Drive role", 160)
            title = item.get("title")
            if title is not None and (not isinstance(title, str) or len(title) > 300):
                raise ValueError("invalid Drive title")
            if status in {"BOUND", "PARTIAL"} and not str(value or "").strip():
                raise ValueError(f"{status} Drive binding requires id")
            if status == "UNRESOLVED" and value not in (None, ""):
                raise ValueError("UNRESOLVED Drive binding must not assert id")


def validate_project_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("project record must be object")
    if set(record) - TOP_LEVEL_KEYS:
        raise ValueError("unexpected project record field")
    if record.get("schema") != "bcp.project_record/1":
        raise ValueError("unsupported project record schema")

    project_id = _bounded_text(record.get("project_id"), "project_id", 128)
    if not PROJECT_ID_RE.fullmatch(project_id):
        raise ValueError("invalid project_id")
    _bounded_text(record.get("display_name"), "display_name", 160)
    if str(record.get("profile") or "") not in PROJECT_PROFILE:
        raise ValueError("invalid project profile")

    if str(record.get("status") or "") not in PROJECT_STATUS:
        raise ValueError("invalid project status")

    authority = record.get("authority")
    if not isinstance(authority, dict):
        raise ValueError("authority required")
    if set(authority) != {"engineering", "runtime", "artifacts", "conversation"}:
        raise ValueError("invalid authority fields")
    if authority.get("engineering") not in AUTH_ENGINEERING:
        raise ValueError("invalid engineering authority")
    if authority.get("runtime") not in AUTH_RUNTIME:
        raise ValueError("invalid runtime authority")
    if authority.get("artifacts") not in AUTH_ARTIFACTS:
        raise ValueError("invalid artifacts authority")
    if authority.get("conversation") != "NON_AUTHORITATIVE":
        raise ValueError("conversation cannot be project authority")

    origins = record.get("origins")
    if not isinstance(origins, dict):
        raise ValueError("origins required")
    if set(origins) != {"local_roots", "repos", "drive_refs"}:
        raise ValueError("invalid origins fields")
    for kind in ("local_roots", "repos", "drive_refs"):
        if kind not in origins:
            raise ValueError(f"origins.{kind} required")
        _validate_binding_list(origins[kind], kind)

    resources = record.get("resource_profile")
    if not isinstance(resources, dict) or set(resources) != {
        "resource_class", "heavy_work", "offline_capable", "background_policy"
    }:
        raise ValueError("invalid resource_profile")
    if resources.get("resource_class") not in RESOURCE_CLASS:
        raise ValueError("invalid resource class")
    if type(resources.get("heavy_work")) is not bool or type(resources.get("offline_capable")) is not bool:
        raise ValueError("invalid resource booleans")
    if resources.get("background_policy") not in BACKGROUND_POLICY:
        raise ValueError("invalid background policy")

    permissions = record.get("permission_profile")
    if not isinstance(permissions, dict):
        raise ValueError("invalid permission_profile")
    if set(permissions) - {
        "max_permission_class", "read_allowed", "project_write_policy", "system_modify_policy"
    } or not {"max_permission_class", "read_allowed"} <= set(permissions):
        raise ValueError("invalid permission_profile fields")
    if permissions.get("max_permission_class") not in PERMISSION_CLASS:
        raise ValueError("invalid permission class")
    if type(permissions.get("read_allowed")) is not bool:
        raise ValueError("invalid read_allowed")
    if permissions.get("project_write_policy") is not None and permissions.get("project_write_policy") not in PROJECT_WRITE_POLICY:
        raise ValueError("invalid project_write_policy")
    if permissions.get("system_modify_policy") is not None and permissions.get("system_modify_policy") not in SYSTEM_MODIFY_POLICY:
        raise ValueError("invalid system_modify_policy")
    if permissions.get("read_allowed") is not True:
        raise ValueError("project registry requires explicit read_allowed=true")

    for list_field, cap in (("continuation_codes", 160), ("adapters", 500)):
        values = record.get(list_field) or []
        if not isinstance(values, list):
            raise ValueError(f"{list_field} must be list")
        if len(values) != len(set(values)):
            raise ValueError(f"duplicate {list_field}")
        for value in values:
            _bounded_text(value, list_field, cap)

    aliases = record.get("aliases") or []
    if not isinstance(aliases, list):
        raise ValueError("aliases must be list")
    seen: set[str] = set()
    for alias in aliases:
        a = _bounded_text(alias, "alias", 160)
        key = a.casefold()
        if key in seen:
            raise ValueError("duplicate alias")
        seen.add(key)

    update = record.get("update_profile")
    if update is not None:
        if not isinstance(update, dict) or set(update) - {"mode", "rollback_required", "channel"}:
            raise ValueError("invalid update_profile")
        if update.get("mode") is not None and update.get("mode") not in UPDATE_MODE:
            raise ValueError("invalid update mode")
        if "rollback_required" in update and type(update.get("rollback_required")) is not bool:
            raise ValueError("invalid rollback_required")
        channel = update.get("channel")
        if channel is not None and (not isinstance(channel, str) or len(channel) > 160):
            raise ValueError("invalid update channel")

    for int_field in ("head_revision", "coordinator_epoch"):
        value = record.get(int_field)
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError(f"invalid {int_field}")

    source_revision = record.get("source_revision")
    if source_revision is not None and (not isinstance(source_revision, str) or len(source_revision) > 256):
        raise ValueError("invalid source_revision")

    compatibility = record.get("compatibility")
    if compatibility is not None:
        if not isinstance(compatibility, dict) or set(compatibility) - {"legacy_authority_present", "migration_rule"}:
            raise ValueError("invalid compatibility")
        if "legacy_authority_present" in compatibility and type(compatibility.get("legacy_authority_present")) is not bool:
            raise ValueError("invalid legacy_authority_present")
        rule = compatibility.get("migration_rule")
        if rule is not None and (not isinstance(rule, str) or len(rule) > 2000):
            raise ValueError("invalid migration_rule")

    updated_at = _bounded_text(record.get("updated_at"), "updated_at", 80)
    if "T" not in updated_at:
        raise ValueError("updated_at must be ISO-like datetime")

    # Return a shallow copy so callers cannot mutate the stored object by reference.
    return dict(record)


def stream_id(project_id: str) -> str:
    pid = _bounded_text(project_id, "project_id", 128)
    if not PROJECT_ID_RE.fullmatch(pid):
        raise ValueError("invalid project_id")
    return PROJECT_PREFIX + pid


class ProjectRegistry:
    def __init__(self, store: CriticalStore):
        self.store = store

    def get(self, project_id: str) -> dict[str, Any]:
        state = self.store.get_state(stream_id(project_id))
        if state is None:
            raise ProjectNotFound(project_id)
        return {
            "record": state["payload"],
            "revision": state["revision"],
            "content_hash": state["content_hash"],
            "fencing_token": state["fencing_token"],
            "committed_epoch": state["committed_epoch"],
        }

    def list(self, *, limit: int = 512) -> list[dict[str, Any]]:
        states = self.store.list_states(PROJECT_PREFIX, limit=limit)
        return [
            {
                "record": state["payload"],
                "revision": state["revision"],
                "content_hash": state["content_hash"],
                "fencing_token": state["fencing_token"],
                "committed_epoch": state["committed_epoch"],
            }
            for state in states
        ]

    def resolve(self, identifier: str) -> dict[str, Any]:
        needle = _bounded_text(identifier, "project identifier", 160).casefold()
        matches: list[dict[str, Any]] = []
        for item in self.list(limit=2048):
            record = item["record"]
            if str(record.get("project_id") or "").casefold() == needle:
                return item
            aliases = [str(x).casefold() for x in (record.get("aliases") or [])]
            if needle in aliases:
                matches.append(item)
        if not matches:
            raise ProjectNotFound(identifier)
        if len(matches) > 1:
            raise ProjectAliasAmbiguous(identifier)
        return matches[0]

    def put(
        self,
        record: dict[str, Any],
        *,
        owner_id: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        clean = validate_project_record(record)
        sid = stream_id(clean["project_id"])
        current = self.store.get_state(sid)
        current_revision = int(current["revision"]) if current else 0

        if expected_revision is not None and int(expected_revision) != current_revision:
            raise ProjectRevisionConflict(
                f"expected revision {expected_revision}, current {current_revision}"
            )

        if current is not None and current["payload"] == clean:
            return {
                "schema": "bcp.project_registry_receipt/1",
                "status": "UNCHANGED",
                "project_id": clean["project_id"],
                "revision": current_revision,
                "fencing_token": current["fencing_token"],
                "content_hash": current["content_hash"],
                "outbox_message_id": None,
                "idempotent_replay": True,
                "field_certified": False,
            }

        fence = self.store.acquire_writer_fence(sid, owner_id)
        try:
            receipt = self.store.commit_transition(
                stream_id=sid,
                expected_revision=current_revision,
                new_revision=current_revision + 1,
                fencing_token=fence,
                payload=clean,
                destination="BCP_PROJECT_REGISTRY",
            )
        except RevisionConflict as exc:
            raise ProjectRevisionConflict(str(exc)) from exc

        return {
            "schema": "bcp.project_registry_receipt/1",
            "status": receipt.status,
            "project_id": clean["project_id"],
            "revision": receipt.revision,
            "fencing_token": receipt.fencing_token,
            "content_hash": receipt.content_hash,
            "predecessor_hash": receipt.predecessor_hash,
            "outbox_message_id": receipt.outbox_message_id,
            "idempotent_replay": receipt.idempotent_replay,
            "field_certified": False,
        }


__all__ = [
    "ProjectRegistry",
    "ProjectRegistryError",
    "ProjectNotFound",
    "ProjectAliasAmbiguous",
    "ProjectRevisionConflict",
    "validate_project_record",
    "stream_id",
]
