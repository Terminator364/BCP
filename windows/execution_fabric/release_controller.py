from __future__ import annotations

"""BCP R3 Phase 5 release/update controller.

This module is a planner and durable promotion authority, not an installer.
Project-specific staging/activation/rollback remains behind typed project-adapter
capabilities. Release candidates, qualification evidence and CURRENT/LKG channel
state all live in the existing fenced CriticalStore.
"""

import copy
import datetime as dt
import re
from typing import Any

from .action_receipt_registry import (
    ActionReceiptRegistry,
    ActionReceiptError,
    ActionReceiptValidationError,
)
from .critical_store import CriticalStore
from .resource_admission import RESOURCE_ORDER, decide as resource_decide


CANDIDATE_PREFIX = "release-candidate/"
QUALIFIED_PREFIX = "release-qualified/"
CHANNEL_PREFIX = "release-channel/"

PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
RELEASE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,199}$")
CAP_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

TRANSPORTS = {
    "GITHUB_RELEASE", "GITHUB_BLOB", "HTTPS_HASH_PINNED",
    "PRIVATE_DRIVE_STABLE_CURRENT", "BUILDHUB", "LOCAL_STAGED", "PROJECT_NATIVE",
}
BUILDERS = {"GITHUB_ACTIONS", "BUILDHUB", "PROJECT_NATIVE", "EXTERNAL_VERIFIED"}
MIGRATIONS = {"NONE", "REVERSIBLE", "MIGRATION_REQUIRED"}
OPERATIONS = {
    "INSPECT", "BUILD", "TEST", "LINT", "INSTALL_TEST", "HEALTHCHECK",
    "RELEASE_VERIFY", "START", "STOP", "UPDATE_STAGE", "UPDATE_ACTIVATE", "ROLLBACK",
}
PERMISSIONS = {
    "P0_READ", "P1_SAFE_WRITE", "P2_PROJECT_MUTATION",
    "P3_BOUNDED_SYSTEM_CHANGE", "P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE",
}
EVIDENCE_KINDS = {
    "EXIT_CODE", "FILE_READBACK", "HASH", "PROCESS_HEALTH", "HTTP_HEALTH",
    "SERVICE_STATE", "GIT_REVISION", "TEST_RESULT", "ARTIFACT_SIGNATURE",
    "PROVIDER_ACK", "DESTINATION_READBACK", "CUSTOM_VALIDATOR",
}


class ReleaseControllerError(RuntimeError):
    pass


class ReleaseCandidateNotFound(ReleaseControllerError):
    pass


class ReleaseQualificationMissing(ReleaseControllerError):
    pass


class ReleasePublicationConflict(ReleaseControllerError):
    pass


class ReleaseValidationError(ReleaseControllerError):
    pass


def _text(value: Any, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise ReleaseValidationError(f"{field} must be string")
    text = value.strip()
    if len(text) < minimum or len(text) > maximum:
        raise ReleaseValidationError(f"invalid {field}")
    return text


def _optional_text(value: Any, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > maximum:
        raise ReleaseValidationError(f"invalid {field}")
    return value


def _iso(value: Any, field: str) -> str:
    text = _text(value, field, 1, 96)
    probe = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = dt.datetime.fromisoformat(probe)
    except ValueError as exc:
        raise ReleaseValidationError(f"invalid {field}") from exc
    if parsed.tzinfo is None:
        raise ReleaseValidationError(f"{field} must include timezone")
    return text


def candidate_stream(project_id: str, release_id: str) -> str:
    project = _text(project_id, "project_id", 2, 128)
    release = _text(release_id, "release_id", 8, 200)
    if not PROJECT_RE.fullmatch(project) or not RELEASE_RE.fullmatch(release):
        raise ReleaseValidationError("invalid release stream id")
    return f"{CANDIDATE_PREFIX}{project}/{release}"


def qualified_stream(project_id: str, release_id: str) -> str:
    candidate_stream(project_id, release_id)
    return f"{QUALIFIED_PREFIX}{project_id}/{release_id}"


def channel_stream(project_id: str) -> str:
    project = _text(project_id, "project_id", 2, 128)
    if not PROJECT_RE.fullmatch(project):
        raise ReleaseValidationError("invalid project_id")
    return CHANNEL_PREFIX + project


def validate_release_candidate(candidate: Any) -> dict[str, Any]:
    allowed = {
        "schema", "release_id", "project_id", "sequence", "version",
        "source", "artifact", "provenance", "qualification_policy",
        "activation_policy", "notes", "created_at",
    }
    required = allowed - {"notes"}
    if not isinstance(candidate, dict) or set(candidate) - allowed or not required <= set(candidate):
        raise ReleaseValidationError("invalid release candidate fields")
    if candidate.get("schema") != "bcp.release_candidate/1":
        raise ReleaseValidationError("unsupported release candidate schema")

    release_id = _text(candidate.get("release_id"), "release_id", 8, 200)
    project_id = _text(candidate.get("project_id"), "project_id", 2, 128)
    if not RELEASE_RE.fullmatch(release_id) or not PROJECT_RE.fullmatch(project_id):
        raise ReleaseValidationError("invalid project/release id")
    sequence = candidate.get("sequence")
    if type(sequence) is not int or sequence < 1:
        raise ReleaseValidationError("sequence must be positive integer")
    _text(candidate.get("version"), "version", 1, 160)

    source = candidate.get("source")
    if not isinstance(source, dict) or set(source) - {"repository", "revision", "path"}:
        raise ReleaseValidationError("invalid source")
    if not {"repository", "revision"} <= set(source):
        raise ReleaseValidationError("source required fields missing")
    _text(source.get("repository"), "repository", 1, 300)
    _text(source.get("revision"), "revision", 7, 256)
    _optional_text(source.get("path"), "source path", 1024)

    artifact = candidate.get("artifact")
    if not isinstance(artifact, dict) or set(artifact) - {"transport", "locator", "sha256", "size_bytes"}:
        raise ReleaseValidationError("invalid artifact")
    if not {"transport", "locator", "sha256"} <= set(artifact):
        raise ReleaseValidationError("artifact required fields missing")
    if artifact.get("transport") not in TRANSPORTS:
        raise ReleaseValidationError("invalid artifact transport")
    _text(artifact.get("locator"), "artifact locator", 1, 2048)
    sha = str(artifact.get("sha256") or "")
    if not HEX64.fullmatch(sha):
        raise ReleaseValidationError("invalid artifact sha256")
    if artifact.get("size_bytes") is not None and (
        type(artifact.get("size_bytes")) is not int or artifact["size_bytes"] < 0
    ):
        raise ReleaseValidationError("invalid artifact size")

    provenance = candidate.get("provenance")
    allowed_provenance = {
        "builder_class", "build_recipe_ref", "dependency_lock_ref", "signer", "signature_ref",
    }
    if (
        not isinstance(provenance, dict)
        or set(provenance) - allowed_provenance
        or not {"builder_class", "build_recipe_ref"} <= set(provenance)
    ):
        raise ReleaseValidationError("invalid provenance")
    if provenance.get("builder_class") not in BUILDERS:
        raise ReleaseValidationError("invalid builder_class")
    _text(provenance.get("build_recipe_ref"), "build_recipe_ref", 1, 512)
    _optional_text(provenance.get("dependency_lock_ref"), "dependency_lock_ref", 512)
    _optional_text(provenance.get("signer"), "signer", 256)
    _optional_text(provenance.get("signature_ref"), "signature_ref", 1024)

    qualification = candidate.get("qualification_policy")
    if not isinstance(qualification, dict) or set(qualification) != {
        "required_capabilities", "field_evidence_required",
    }:
        raise ReleaseValidationError("invalid qualification_policy")
    caps = qualification.get("required_capabilities")
    if not isinstance(caps, list) or not caps or len(caps) != len(set(caps)):
        raise ReleaseValidationError("required_capabilities must be unique/non-empty")
    for cap in caps:
        if not isinstance(cap, str) or not CAP_RE.fullmatch(cap):
            raise ReleaseValidationError("invalid qualification capability")
    if type(qualification.get("field_evidence_required")) is not bool:
        raise ReleaseValidationError("field_evidence_required must be boolean")

    activation = candidate.get("activation_policy")
    if not isinstance(activation, dict) or set(activation) != {
        "rollback_required", "field_activation_required", "migration",
    }:
        raise ReleaseValidationError("invalid activation_policy")
    if type(activation.get("rollback_required")) is not bool:
        raise ReleaseValidationError("rollback_required must be boolean")
    if type(activation.get("field_activation_required")) is not bool:
        raise ReleaseValidationError("field_activation_required must be boolean")
    migration = activation.get("migration")
    if not isinstance(migration, dict) or set(migration) - {
        "class", "rollback_compatible", "migration_ref",
    }:
        raise ReleaseValidationError("invalid migration")
    if not {"class", "rollback_compatible"} <= set(migration):
        raise ReleaseValidationError("migration required fields missing")
    if migration.get("class") not in MIGRATIONS:
        raise ReleaseValidationError("invalid migration class")
    if type(migration.get("rollback_compatible")) is not bool:
        raise ReleaseValidationError("rollback_compatible must be boolean")
    _optional_text(migration.get("migration_ref"), "migration_ref", 512)

    notes = candidate.get("notes") or []
    if not isinstance(notes, list) or not all(isinstance(x, str) and len(x) <= 1000 for x in notes):
        raise ReleaseValidationError("invalid notes")
    _iso(candidate.get("created_at"), "created_at")
    return copy.deepcopy(candidate)


def _receipt_has_artifact_hash(receipt: dict[str, Any], expected_sha: str) -> bool:
    if receipt.get("output_hash") == expected_sha:
        return True
    for evidence in receipt.get("evidence") or []:
        if evidence.get("status") == "PASS" and evidence.get("sha256") == expected_sha:
            return True
    return False


def _binding(adapter: dict[str, Any], project_id: str, operation: str) -> dict[str, Any] | None:
    if not isinstance(adapter, dict) or adapter.get("schema") != "bcp.project_adapter/1":
        raise ReleaseValidationError("invalid project adapter")
    if adapter.get("project_id") != project_id:
        raise ReleaseValidationError("adapter project mismatch")
    if operation not in OPERATIONS:
        raise ReleaseValidationError("invalid operation")
    matches = [
        x for x in (adapter.get("bindings") or [])
        if isinstance(x, dict) and x.get("operation") == operation
    ]
    if len(matches) > 1:
        raise ReleaseValidationError(f"ambiguous adapter operation: {operation}")
    if not matches:
        return None
    item = matches[0]
    if item.get("state") != "BOUND":
        return None
    cap = item.get("capability_id")
    if not isinstance(cap, str) or not CAP_RE.fullmatch(cap):
        raise ReleaseValidationError("invalid adapter capability")
    if item.get("permission_class") not in PERMISSIONS:
        raise ReleaseValidationError("invalid adapter permission")
    if item.get("resource_class") not in RESOURCE_ORDER:
        raise ReleaseValidationError("invalid adapter resource")
    evidence = item.get("evidence_contract")
    if not isinstance(evidence, list) or not evidence or not set(evidence) <= EVIDENCE_KINDS:
        raise ReleaseValidationError("invalid adapter evidence contract")
    return copy.deepcopy(item)


class ReleaseController:
    def __init__(self, store: CriticalStore):
        self.store = store
        self.receipts = ActionReceiptRegistry(store)

    def _candidate_state(self, project_id: str, release_id: str) -> dict[str, Any]:
        state = self.store.get_state(candidate_stream(project_id, release_id))
        if state is None:
            raise ReleaseCandidateNotFound(f"{project_id}/{release_id}")
        return state

    def _qualification_state(self, project_id: str, release_id: str) -> dict[str, Any]:
        state = self.store.get_state(qualified_stream(project_id, release_id))
        if state is None:
            raise ReleaseQualificationMissing(f"{project_id}/{release_id}")
        return state

    def channel(self, project_id: str) -> dict[str, Any] | None:
        return self.store.get_state(channel_stream(project_id))

    def register_candidate(self, candidate: dict[str, Any], *, owner_id: str) -> dict[str, Any]:
        clean = validate_release_candidate(candidate)
        project_id = clean["project_id"]
        release_id = clean["release_id"]
        sid = candidate_stream(project_id, release_id)
        current = self.store.get_state(sid)
        if current is not None:
            if current["payload"] == clean:
                return current
            raise ReleasePublicationConflict("release_id already committed with different content")

        for state in self.store.list_states(f"{CANDIDATE_PREFIX}{project_id}/", limit=4096):
            other = state["payload"]
            if int(other.get("sequence") or 0) != clean["sequence"]:
                continue
            if other.get("release_id") == release_id and other == clean:
                return state
            raise ReleasePublicationConflict(
                f"publication fencing conflict at sequence {clean['sequence']}"
            )

        fence = self.store.acquire_writer_fence(sid, owner_id)
        self.store.commit_transition(
            stream_id=sid,
            expected_revision=0,
            new_revision=1,
            fencing_token=fence,
            payload=clean,
            destination="BCP_RELEASE_CANDIDATE",
        )
        return self._candidate_state(project_id, release_id)

    def qualify(
        self,
        project_id: str,
        release_id: str,
        *,
        successful_receipt_refs: list[str],
        regression_refs: list[str],
        qualified_at: str,
        owner_id: str,
        field_receipt_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        candidate_state = self._candidate_state(project_id, release_id)
        candidate = candidate_state["payload"]
        success_refs = list(dict.fromkeys(successful_receipt_refs))
        regressions = list(dict.fromkeys(regression_refs))
        field_refs = list(dict.fromkeys(field_receipt_refs or []))
        if not success_refs or not regressions:
            raise ReleaseValidationError("qualification requires receipts and regressions")
        if not all(isinstance(x, str) and x for x in regressions):
            raise ReleaseValidationError("invalid regression reference")
        _iso(qualified_at, "qualified_at")

        try:
            success_states = [
                self.receipts.require_success(ref, project_scopes=[project_id], field=False)
                for ref in success_refs
            ]
            proved_caps = {x["payload"]["capability_id"] for x in success_states}
            required_caps = set(candidate["qualification_policy"]["required_capabilities"])
            if not required_caps <= proved_caps:
                missing = sorted(required_caps - proved_caps)
                raise ReleaseValidationError(
                    "qualification receipts do not cover required capabilities: " + ",".join(missing)
                )
            artifact_sha = candidate["artifact"]["sha256"]
            if not any(_receipt_has_artifact_hash(x["payload"], artifact_sha) for x in success_states):
                raise ReleaseValidationError("qualification receipts do not prove artifact sha256")

            if candidate["qualification_policy"]["field_evidence_required"]:
                field_states = [
                    self.receipts.require_success(ref, project_scopes=[project_id], field=True)
                    for ref in field_refs
                ]
                field_caps = {x["payload"]["capability_id"] for x in field_states}
                if not required_caps <= field_caps:
                    missing = sorted(required_caps - field_caps)
                    raise ReleaseValidationError(
                        "field qualification does not cover required capabilities: " + ",".join(missing)
                    )
        except (ActionReceiptError, ActionReceiptValidationError) as exc:
            raise ReleaseValidationError("qualification receipt validation failed: " + str(exc)) from exc

        payload = {
            "schema": "bcp.release_qualification/1",
            "project_id": project_id,
            "release_id": release_id,
            "sequence": candidate["sequence"],
            "candidate_content_hash": candidate_state["content_hash"],
            "artifact_sha256": candidate["artifact"]["sha256"],
            "successful_receipt_refs": success_refs,
            "regression_refs": regressions,
            "field_receipt_refs": field_refs,
            "field_evidence_satisfied": bool(
                candidate["qualification_policy"]["field_evidence_required"] and field_refs
            ),
            "qualified_at": qualified_at,
            "field_certified": False,
        }
        sid = qualified_stream(project_id, release_id)
        existing = self.store.get_state(sid)
        if existing is not None:
            if existing["payload"] == payload:
                return existing
            raise ReleasePublicationConflict("qualification already committed with different proof")

        fence = self.store.acquire_writer_fence(sid, owner_id)
        self.store.commit_transition(
            stream_id=sid,
            expected_revision=0,
            new_revision=1,
            fencing_token=fence,
            payload=payload,
            destination="BCP_RELEASE_QUALIFICATION",
        )
        return self._qualification_state(project_id, release_id)

    def _release_ref(self, candidate_state: dict[str, Any], qualification_state: dict[str, Any]) -> dict[str, Any]:
        candidate = candidate_state["payload"]
        return {
            "release_id": candidate["release_id"],
            "sequence": candidate["sequence"],
            "version": candidate["version"],
            "artifact_sha256": candidate["artifact"]["sha256"],
            "candidate_content_hash": candidate_state["content_hash"],
            "qualification_content_hash": qualification_state["content_hash"],
            "source_revision": candidate["source"]["revision"],
        }

    def plan_activation(
        self,
        project_id: str,
        release_id: str,
        adapter: dict[str, Any],
        *,
        resource_mode: str,
    ) -> dict[str, Any]:
        candidate_state = self._candidate_state(project_id, release_id)
        qualification_state = self._qualification_state(project_id, release_id)
        candidate = candidate_state["payload"]
        channel = self.channel(project_id)
        current = channel["payload"].get("current") if channel else None

        if current is not None:
            if candidate["sequence"] < int(current["sequence"]):
                return self._hold(candidate, "HOLD_ANTI_DOWNGRADE", current=current)
            if candidate["sequence"] == int(current["sequence"]):
                if (
                    current.get("release_id") == release_id
                    and current.get("artifact_sha256") == candidate["artifact"]["sha256"]
                ):
                    return self._hold(candidate, "NOOP_ALREADY_CURRENT", current=current)
                return self._hold(candidate, "HOLD_PUBLICATION_FENCING_CONFLICT", current=current)

        migration = candidate["activation_policy"]["migration"]
        if migration["class"] == "MIGRATION_REQUIRED" and not migration["rollback_compatible"]:
            return self._hold(candidate, "HOLD_MIGRATION_SAFETY", current=current)

        operations = ["RELEASE_VERIFY", "UPDATE_ACTIVATE", "HEALTHCHECK"]
        bindings: dict[str, dict[str, Any]] = {}
        for operation in operations:
            item = _binding(adapter, project_id, operation)
            if item is None:
                return self._hold(candidate, f"HOLD_BINDING_{operation}", current=current)
            if item["permission_class"] == "P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE":
                return self._hold(candidate, f"HOLD_FRESH_APPROVAL_{operation}", current=current)
            if item["resource_class"] == "R4_LOCAL_AI":
                return self._hold(candidate, f"HOLD_LOCAL_AI_{operation}", current=current)
            admission = resource_decide(item["resource_class"], mode=resource_mode, background=False)
            if not admission.allowed:
                return self._hold(
                    candidate,
                    f"HOLD_RESOURCE_{operation}:{admission.reason}",
                    current=current,
                )
            bindings[operation] = item

        rollback_binding = None
        if candidate["activation_policy"]["rollback_required"]:
            rollback_binding = _binding(adapter, project_id, "ROLLBACK")
            if rollback_binding is None and current is not None:
                return self._hold(candidate, "HOLD_BINDING_ROLLBACK", current=current)

        common = {
            "release_id": release_id,
            "version": candidate["version"],
            "sequence": candidate["sequence"],
            "artifact": copy.deepcopy(candidate["artifact"]),
            "source_revision": candidate["source"]["revision"],
        }
        steps = []
        for idx, operation in enumerate(operations, start=1):
            item = bindings[operation]
            steps.append({
                "step_id": f"{idx:02d}-{operation.lower().replace('_','-')}",
                "operation": operation,
                "capability_id": item["capability_id"],
                "provider_id": item["provider_id"],
                "permission_class": item["permission_class"],
                "resource_class": item["resource_class"],
                "evidence_contract": copy.deepcopy(item["evidence_contract"]),
                "input": copy.deepcopy(common),
            })

        rollback = None
        if rollback_binding is not None and current is not None:
            rollback = {
                "operation": "ROLLBACK",
                "capability_id": rollback_binding["capability_id"],
                "provider_id": rollback_binding["provider_id"],
                "permission_class": rollback_binding["permission_class"],
                "resource_class": rollback_binding["resource_class"],
                "evidence_contract": copy.deepcopy(rollback_binding["evidence_contract"]),
                "input": {
                    "failed_release_id": release_id,
                    "target": copy.deepcopy(current),
                },
            }

        return {
            "schema": "bcp.release_plan/1",
            "decision": "EXECUTE_TYPED_PLAN",
            "project_id": project_id,
            "release_id": release_id,
            "candidate_sequence": candidate["sequence"],
            "current": copy.deepcopy(current),
            "steps": steps,
            "rollback": rollback,
            "field_activation_required": candidate["activation_policy"]["field_activation_required"],
            "field_certified": False,
        }

    def _hold(self, candidate: dict[str, Any], reason: str, *, current: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "schema": "bcp.release_plan/1",
            "decision": reason,
            "project_id": candidate["project_id"],
            "release_id": candidate["release_id"],
            "candidate_sequence": candidate["sequence"],
            "current": copy.deepcopy(current),
            "steps": [],
            "rollback": None,
            "field_certified": False,
        }

    def commit_activation(
        self,
        project_id: str,
        release_id: str,
        adapter: dict[str, Any],
        *,
        activation_receipt_ref: str,
        health_receipt_ref: str,
        promoted_at: str,
        owner_id: str,
    ) -> dict[str, Any]:
        candidate_state = self._candidate_state(project_id, release_id)
        qualification_state = self._qualification_state(project_id, release_id)
        candidate = candidate_state["payload"]
        _iso(promoted_at, "promoted_at")

        activate = _binding(adapter, project_id, "UPDATE_ACTIVATE")
        health = _binding(adapter, project_id, "HEALTHCHECK")
        if activate is None or health is None:
            raise ReleaseValidationError("activation/health binding unavailable")

        require_field = bool(candidate["activation_policy"]["field_activation_required"])
        try:
            activation_state = self.receipts.require_success(
                activation_receipt_ref,
                project_scopes=[project_id],
                field=require_field,
            )
            health_state = self.receipts.require_success(
                health_receipt_ref,
                project_scopes=[project_id],
                field=require_field,
            )
        except (ActionReceiptError, ActionReceiptValidationError) as exc:
            raise ReleaseValidationError("activation receipt validation failed: " + str(exc)) from exc

        if activation_state["payload"]["capability_id"] != activate["capability_id"]:
            raise ReleaseValidationError("activation receipt capability mismatch")
        if health_state["payload"]["capability_id"] != health["capability_id"]:
            raise ReleaseValidationError("health receipt capability mismatch")
        artifact_sha = candidate["artifact"]["sha256"]
        if not (
            _receipt_has_artifact_hash(activation_state["payload"], artifact_sha)
            or _receipt_has_artifact_hash(health_state["payload"], artifact_sha)
        ):
            raise ReleaseValidationError("activation/health receipts do not prove active artifact hash")

        sid = channel_stream(project_id)
        channel = self.store.get_state(sid)
        old_payload = channel["payload"] if channel else None
        current = old_payload.get("current") if old_payload else None

        if current is not None:
            if candidate["sequence"] < int(current["sequence"]):
                raise ReleaseValidationError("anti-downgrade violation at commit")
            if candidate["sequence"] == int(current["sequence"]):
                if (
                    current.get("release_id") == release_id
                    and current.get("artifact_sha256") == artifact_sha
                ):
                    return channel
                raise ReleasePublicationConflict("publication fencing conflict at commit")

        new_current = self._release_ref(candidate_state, qualification_state)
        payload = {
            "schema": "bcp.release_channel/1",
            "project_id": project_id,
            "current": new_current,
            "lkg": copy.deepcopy(current),
            "promoted_at": promoted_at,
            "activation_receipt_ref": activation_receipt_ref,
            "health_receipt_ref": health_receipt_ref,
            "field_certified": bool(require_field),
        }

        revision = int(channel["revision"]) if channel else 0
        fence = self.store.acquire_writer_fence(sid, owner_id)
        self.store.commit_transition(
            stream_id=sid,
            expected_revision=revision,
            new_revision=revision + 1,
            fencing_token=fence,
            payload=payload,
            destination="BCP_RELEASE_CHANNEL",
        )
        return self.store.get_state(sid)


__all__ = [
    "ReleaseController",
    "ReleaseControllerError",
    "ReleaseCandidateNotFound",
    "ReleaseQualificationMissing",
    "ReleasePublicationConflict",
    "ReleaseValidationError",
    "validate_release_candidate",
    "candidate_stream",
    "qualified_stream",
    "channel_stream",
]
