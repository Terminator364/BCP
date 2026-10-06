from __future__ import annotations

"""Durable cross-project typed adapter registry for BCP R3 Phase 8.

Adapters map project operations to typed capability IDs. They do not execute work,
do not contain command strings, and cannot turn unresolved project bindings into
BOUND state. Durable records reuse the Phase 2 CriticalStore.
"""

from copy import deepcopy
import hashlib
import re
from typing import Any

from .critical_store import CriticalStore
from .project_registry import ProjectRegistry, ProjectNotFound


ADAPTER_PREFIX = "project-adapter/"
ADAPTER_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
CAPABILITY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")

OPERATIONS = {
    "INSPECT", "BUILD", "TEST", "LINT", "INSTALL_TEST", "HEALTHCHECK",
    "RELEASE_VERIFY", "START", "STOP", "UPDATE_STAGE", "UPDATE_ACTIVATE", "ROLLBACK",
}
STATES = {"BOUND", "WAITING_BINDING", "TEMP_UNAVAILABLE", "UNSUPPORTED"}
PERMISSIONS = {
    "P0_READ", "P1_SAFE_WRITE", "P2_PROJECT_MUTATION",
    "P3_BOUNDED_SYSTEM_CHANGE", "P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE",
}
RESOURCES = {"R0_TINY", "R1_LIGHT", "R2_MEDIUM", "R3_HEAVY", "R4_LOCAL_AI"}
EVIDENCE = {
    "EXIT_CODE", "FILE_READBACK", "HASH", "PROCESS_HEALTH", "HTTP_HEALTH",
    "SERVICE_STATE", "GIT_REVISION", "TEST_RESULT", "ARTIFACT_SIGNATURE",
    "PROVIDER_ACK", "DESTINATION_READBACK", "CUSTOM_VALIDATOR",
}
FORBIDDEN_INPUT_KEYS = {
    "command", "argv", "shell", "script", "executable", "powershell", "cmd",
    "commandline", "command_line",
}
REPOSITORY_PROVIDERS = {"GITHUB_REPOSITORY", "GITHUB_ACTIONS"}
PC_PROVIDERS = {"BCP_NATIVE_PC", "PC_NATIVE"}


class ProjectAdapterError(RuntimeError):
    pass


class ProjectAdapterNotFound(ProjectAdapterError):
    pass


class ProjectAdapterCollision(ProjectAdapterError):
    pass


class ProjectAdapterAmbiguous(ProjectAdapterError):
    pass


def _text(value: Any, field: str, cap: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be string")
    text = value.strip()
    if not text or len(text) > cap:
        raise ValueError(f"invalid {field}")
    return text


def _find_forbidden(value: Any, path: str = "$") -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in FORBIDDEN_INPUT_KEYS:
                return f"{path}.{key}"
            found = _find_forbidden(item, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = _find_forbidden(item, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(value, str):
        folded = value.casefold()
        if "powershell.exe" in folded or "cmd.exe" in folded:
            return path
    return None


def validate_adapter(adapter: Any) -> dict[str, Any]:
    required = {"schema", "adapter_id", "project_id", "version", "bindings", "source_revision"}
    optional = {"notes"}
    if (
        not isinstance(adapter, dict)
        or set(adapter) - required - optional
        or not required <= set(adapter)
    ):
        raise ValueError("invalid project adapter fields")
    if adapter.get("schema") != "bcp.project_adapter/1":
        raise ValueError("unsupported project adapter schema")

    adapter_id = _text(adapter.get("adapter_id"), "adapter_id", 128)
    project_id = _text(adapter.get("project_id"), "project_id", 128)
    _text(adapter.get("version"), "version", 64)
    _text(adapter.get("source_revision"), "source_revision", 256)
    if not ADAPTER_RE.fullmatch(adapter_id) or not PROJECT_RE.fullmatch(project_id):
        raise ValueError("invalid adapter identity")

    bindings = adapter.get("bindings")
    if not isinstance(bindings, list) or not bindings:
        raise ValueError("bindings required")
    seen_operations: set[str] = set()
    allowed_binding = {
        "operation", "capability_id", "provider_id", "state",
        "permission_class", "resource_class", "evidence_contract",
        "input_defaults", "binding_reason",
    }
    required_binding = {
        "operation", "capability_id", "provider_id", "state",
        "permission_class", "resource_class", "evidence_contract",
    }
    for binding in bindings:
        if (
            not isinstance(binding, dict)
            or set(binding) - allowed_binding
            or not required_binding <= set(binding)
        ):
            raise ValueError("invalid adapter binding fields")
        operation = binding.get("operation")
        if operation not in OPERATIONS or operation in seen_operations:
            raise ValueError("duplicate/invalid adapter operation")
        seen_operations.add(operation)

        capability_id = _text(binding.get("capability_id"), "capability_id", 128)
        if not CAPABILITY_RE.fullmatch(capability_id):
            raise ValueError("invalid capability_id")
        _text(binding.get("provider_id"), "provider_id", 128)
        if binding.get("state") not in STATES:
            raise ValueError("invalid binding state")
        if binding.get("permission_class") not in PERMISSIONS:
            raise ValueError("invalid permission_class")
        if binding.get("resource_class") not in RESOURCES:
            raise ValueError("invalid resource_class")
        evidence = binding.get("evidence_contract")
        if (
            not isinstance(evidence, list) or not evidence
            or len(evidence) != len(set(evidence))
            or not set(evidence) <= EVIDENCE
        ):
            raise ValueError("invalid evidence_contract")
        defaults = binding.get("input_defaults", {})
        if not isinstance(defaults, dict):
            raise ValueError("input_defaults must be object")
        forbidden = _find_forbidden(defaults)
        if forbidden:
            raise ValueError(f"executable mechanics forbidden at {forbidden}")
        reason = binding.get("binding_reason")
        if reason is not None and (not isinstance(reason, str) or len(reason) > 1000):
            raise ValueError("invalid binding_reason")

    notes = adapter.get("notes") or []
    if not isinstance(notes, list) or not all(isinstance(x, str) and len(x) <= 1000 for x in notes):
        raise ValueError("invalid adapter notes")
    return deepcopy(adapter)


def _stream_id(project_id: str, adapter_id: str, version: str) -> str:
    project = _text(project_id, "project_id", 128)
    adapter = _text(adapter_id, "adapter_id", 128)
    ver = _text(version, "version", 64)
    if not PROJECT_RE.fullmatch(project) or not ADAPTER_RE.fullmatch(adapter):
        raise ValueError("invalid project adapter identity")
    digest = hashlib.sha256(f"{adapter}\0{ver}".encode("utf-8")).hexdigest()
    return f"{ADAPTER_PREFIX}{project}/{digest}"


def validate_against_project(adapter: dict[str, Any], project_record: dict[str, Any]) -> None:
    clean = validate_adapter(adapter)
    record = project_record
    if record.get("schema") != "bcp.project_record/1":
        raise ValueError("invalid project record")
    if clean["project_id"] != record.get("project_id"):
        raise ValueError("adapter/project mismatch")

    origins = record.get("origins") or {}
    bound_repos = {
        str(item.get("repository"))
        for item in (origins.get("repos") or [])
        if item.get("status") == "BOUND" and item.get("repository")
    }
    bound_roots = [
        item for item in (origins.get("local_roots") or [])
        if item.get("status") == "BOUND" and item.get("path")
    ]

    for binding in clean["bindings"]:
        if binding["state"] != "BOUND":
            continue
        provider = binding["provider_id"]
        defaults = binding.get("input_defaults") or {}
        if provider in REPOSITORY_PROVIDERS:
            repository = defaults.get("repository")
            if not isinstance(repository, str) or repository not in bound_repos:
                raise ValueError(
                    f"BOUND {provider} operation requires observed project repository"
                )
        elif provider in PC_PROVIDERS:
            if not bound_roots:
                raise ValueError(
                    f"BOUND {provider} operation requires observed local project root"
                )


class ProjectAdapterRegistry:
    def __init__(self, store: CriticalStore):
        self.store = store
        self.projects = ProjectRegistry(store)

    def get(self, project_id: str, adapter_id: str, version: str) -> dict[str, Any]:
        sid = _stream_id(project_id, adapter_id, version)
        state = self.store.get_state(sid)
        if state is None:
            raise ProjectAdapterNotFound(f"{project_id}/{adapter_id}/{version}")
        return state

    def list(self, project_id: str | None = None, *, limit: int = 1024) -> list[dict[str, Any]]:
        prefix = ADAPTER_PREFIX
        if project_id is not None:
            project = _text(project_id, "project_id", 128)
            if not PROJECT_RE.fullmatch(project):
                raise ValueError("invalid project_id")
            prefix += project + "/"
        return self.store.list_states(prefix, limit=limit)

    def put(self, adapter: dict[str, Any], *, owner_id: str) -> dict[str, Any]:
        clean = validate_adapter(adapter)
        try:
            project = self.projects.get(clean["project_id"])["record"]
        except ProjectNotFound as exc:
            raise ValueError("project must be registered before adapter") from exc
        validate_against_project(clean, project)

        sid = _stream_id(clean["project_id"], clean["adapter_id"], clean["version"])
        current = self.store.get_state(sid)
        if current is not None:
            if current["payload"] == clean:
                return current
            raise ProjectAdapterCollision(
                "project adapter id/version already registered with different content"
            )
        fence = self.store.acquire_writer_fence(sid, owner_id)
        self.store.commit_transition(
            stream_id=sid,
            expected_revision=0,
            new_revision=1,
            fencing_token=fence,
            payload=clean,
            destination="BCP_PROJECT_ADAPTER_REGISTRY",
        )
        return self.get(clean["project_id"], clean["adapter_id"], clean["version"])

    def resolve(
        self,
        project_id: str,
        operation: str,
        *,
        require_bound: bool = True,
    ) -> dict[str, Any]:
        op = str(operation).upper()
        if op not in OPERATIONS:
            raise ValueError("invalid operation")
        matches: list[dict[str, Any]] = []
        for state in self.list(project_id, limit=4096):
            adapter = state["payload"]
            for binding in adapter["bindings"]:
                if binding["operation"] != op:
                    continue
                if require_bound and binding["state"] != "BOUND":
                    continue
                matches.append({
                    "adapter_id": adapter["adapter_id"],
                    "version": adapter["version"],
                    "project_id": adapter["project_id"],
                    "binding": deepcopy(binding),
                    "source_revision": adapter["source_revision"],
                    "field_certified": False,
                })
        if not matches:
            raise ProjectAdapterNotFound(f"{project_id}/{op}")
        if len(matches) > 1:
            raise ProjectAdapterAmbiguous(f"{project_id}/{op}")
        return matches[0]


__all__ = [
    "ProjectAdapterRegistry",
    "ProjectAdapterError",
    "ProjectAdapterNotFound",
    "ProjectAdapterCollision",
    "ProjectAdapterAmbiguous",
    "validate_adapter",
    "validate_against_project",
]
