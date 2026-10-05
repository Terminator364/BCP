from __future__ import annotations

"""Evidence-gated Incident/Repair Recipe engine for BCP Phase 4.

This module plans typed capability work. It does not execute shell commands or mutate
Windows/project state directly. Incidents and recipes are durable CriticalStore streams.
"""

import copy
import datetime as dt
import hashlib
import json
import re
from typing import Any

from .critical_store import CriticalStore
from .resource_admission import RESOURCE_ORDER, decide as resource_decide
from .action_receipt_registry import (
    ActionReceiptRegistry,
    ActionReceiptError,
    ActionReceiptValidationError,
)
from .desired_state_registry import validate_resource


INCIDENT_PREFIX = "incident/"
RECIPE_PREFIX = "recipe/"
HEX64 = re.compile(r"^[a-f0-9]{64}$")
PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
RESOURCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,159}$")
CAPABILITY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")

PERMISSION_ORDER = {
    "P0_READ": 0,
    "P1_SAFE_WRITE": 1,
    "P2_PROJECT_MUTATION": 2,
    "P3_BOUNDED_SYSTEM_CHANGE": 3,
}
MODE_PERMISSION_CEILING = {
    "OBSERVE_ONLY": -1,
    "AUTO_SAFE": 1,
    "AUTO_PROJECT": 2,
    "AUTO_BOUNDED_SYSTEM": 3,
}
EVIDENCE_KINDS = {
    "EXIT_CODE","FILE_READBACK","HASH","PROCESS_HEALTH","HTTP_HEALTH",
    "SERVICE_STATE","GIT_REVISION","TEST_RESULT","ARTIFACT_SIGNATURE",
    "PROVIDER_ACK","DESTINATION_READBACK","CUSTOM_VALIDATOR",
}
FORBIDDEN_RECIPE_KEYS = {
    "command","argv","shell","script","executable","powershell","cmd",
}


class RecipeError(RuntimeError):
    pass


class RecipeNotFound(RecipeError):
    pass


class RecipeAmbiguous(RecipeError):
    pass


class RecipeValidationError(RecipeError):
    pass


class IncidentNotFound(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def strict_iso(value: Any, field: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
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


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def causal_signature(project_id: str, resource_id: str, symptoms: dict[str, Any]) -> str:
    project = str(project_id).strip()
    resource = str(resource_id).strip()
    if not PROJECT_ID_RE.fullmatch(project) or not RESOURCE_ID_RE.fullmatch(resource):
        raise ValueError("invalid incident project/resource id")
    if not isinstance(symptoms, dict) or not symptoms:
        raise ValueError("non-empty symptoms object required")
    raw = canonical_json({
        "project_id": project,
        "resource_id": resource,
        "symptoms": symptoms,
    }).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def incident_stream(project_id: str, resource_id: str, signature: str) -> str:
    project = str(project_id).strip()
    resource = str(resource_id).strip()
    if not PROJECT_ID_RE.fullmatch(project) or not RESOURCE_ID_RE.fullmatch(resource):
        raise ValueError("invalid incident project/resource id")
    sig = str(signature).lower()
    if not HEX64.fullmatch(sig):
        raise ValueError("invalid incident signature")
    return f"{INCIDENT_PREFIX}{project}/{resource}/{sig}"


def recipe_stream(recipe_id: str) -> str:
    rid = str(recipe_id).strip()
    if not rid or len(rid) > 200:
        raise ValueError("invalid recipe_id")
    return RECIPE_PREFIX + rid


def _find_forbidden(value: Any, path: str = "$") -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            k = str(key).casefold()
            if k in FORBIDDEN_RECIPE_KEYS:
                return f"{path}.{key}"
            found = _find_forbidden(item, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            found = _find_forbidden(item, f"{path}[{idx}]")
            if found:
                return found
    elif isinstance(value, str):
        text = value.casefold()
        if "powershell.exe" in text or "cmd.exe" in text:
            return path
    return None


def validate_recipe(recipe: Any) -> dict[str, Any]:
    allowed_top = {
        "schema","recipe_id","signature","status","project_scopes",
        "max_permission_class","max_resource_class","steps","validation",
        "created_at","updated_at","promoted_at","notes",
    }
    required_top = {
        "schema","recipe_id","signature","status","project_scopes",
        "max_permission_class","max_resource_class","steps","validation",
        "created_at","updated_at",
    }
    if not isinstance(recipe, dict) or set(recipe) - allowed_top or not required_top <= set(recipe):
        raise RecipeValidationError("invalid repair recipe fields")
    if recipe.get("schema") != "bcp.repair_recipe/1":
        raise RecipeValidationError("unsupported repair recipe")
    recipe_id = recipe.get("recipe_id")
    if not isinstance(recipe_id, str) or not (8 <= len(recipe_id.strip()) <= 200):
        raise RecipeValidationError("invalid recipe_id")
    signature = str(recipe.get("signature") or "").lower()
    if not HEX64.fullmatch(signature):
        raise RecipeValidationError("invalid signature")
    status = recipe.get("status")
    if status not in {"CANDIDATE","VALIDATED","SUSPENDED","RETIRED"}:
        raise RecipeValidationError("invalid recipe status")

    scopes = recipe.get("project_scopes")
    if not isinstance(scopes, list) or not scopes or len(scopes) != len(set(scopes)):
        raise RecipeValidationError("project_scopes required/unique")
    for scope in scopes:
        if not isinstance(scope, str) or not scope or len(scope) > 128:
            raise RecipeValidationError("invalid project scope")

    if recipe.get("max_permission_class") not in PERMISSION_ORDER:
        raise RecipeValidationError("invalid max_permission_class")
    max_resource = recipe.get("max_resource_class")
    if max_resource not in RESOURCE_ORDER or max_resource == "R4_LOCAL_AI":
        raise RecipeValidationError("invalid max_resource_class")

    steps = recipe.get("steps")
    if not isinstance(steps, list) or not (1 <= len(steps) <= 32):
        raise RecipeValidationError("steps required")
    allowed_step = {
        "step_id","capability_id","permission_class","resource_class",
        "input_template","evidence_contract","optional",
    }
    seen: set[str] = set()
    for step in steps:
        if not isinstance(step, dict) or set(step) - allowed_step:
            raise RecipeValidationError("invalid step fields")
        if not {
            "step_id","capability_id","permission_class","resource_class",
            "input_template","evidence_contract",
        } <= set(step):
            raise RecipeValidationError("step required fields missing")
        sid = step.get("step_id")
        if not isinstance(sid, str) or not sid or len(sid) > 128 or sid in seen:
            raise RecipeValidationError("duplicate/invalid step_id")
        seen.add(sid)
        cap = step.get("capability_id")
        if not isinstance(cap, str) or not CAPABILITY_RE.fullmatch(cap):
            raise RecipeValidationError("invalid capability_id")
        perm = step.get("permission_class")
        resource = step.get("resource_class")
        if perm not in PERMISSION_ORDER:
            raise RecipeValidationError("invalid step permission")
        if resource not in RESOURCE_ORDER or resource == "R4_LOCAL_AI":
            raise RecipeValidationError("invalid step resource")
        if PERMISSION_ORDER[perm] > PERMISSION_ORDER[recipe["max_permission_class"]]:
            raise RecipeValidationError("step permission exceeds recipe ceiling")
        if RESOURCE_ORDER[resource] > RESOURCE_ORDER[max_resource]:
            raise RecipeValidationError("step resource exceeds recipe ceiling")
        evidence = step.get("evidence_contract")
        if (
            not isinstance(evidence, list) or not evidence
            or len(evidence) != len(set(evidence))
            or not set(evidence) <= EVIDENCE_KINDS
        ):
            raise RecipeValidationError("invalid step evidence contract")
        if not isinstance(step.get("input_template"), dict):
            raise RecipeValidationError("input_template must be object")
        if "optional" in step and type(step.get("optional")) is not bool:
            raise RecipeValidationError("optional must be boolean")

    forbidden = _find_forbidden(recipe)
    if forbidden:
        raise RecipeValidationError(f"recipe contains executable mechanics at {forbidden}")

    validation = recipe.get("validation")
    allowed_validation = {
        "successful_receipt_refs","regression_refs",
        "field_evidence_required","field_evidence_refs",
    }
    required_validation = {
        "successful_receipt_refs","regression_refs","field_evidence_required",
    }
    if (
        not isinstance(validation, dict)
        or set(validation) - allowed_validation
        or not required_validation <= set(validation)
    ):
        raise RecipeValidationError("invalid validation fields")
    if type(validation.get("field_evidence_required")) is not bool:
        raise RecipeValidationError("field_evidence_required must be boolean")
    receipts = validation.get("successful_receipt_refs")
    regressions = validation.get("regression_refs")
    field_refs = validation.get("field_evidence_refs") or []
    for name, refs in (
        ("successful_receipt_refs", receipts),
        ("regression_refs", regressions),
        ("field_evidence_refs", field_refs),
    ):
        if not isinstance(refs, list) or len(refs) != len(set(refs)):
            raise RecipeValidationError(f"invalid {name}")
        if not all(isinstance(x, str) and 0 < len(x) <= 512 for x in refs):
            raise RecipeValidationError(f"invalid {name} reference")

    try:
        strict_iso(recipe.get("created_at"), "created_at")
        strict_iso(recipe.get("updated_at"), "updated_at")
        strict_iso(recipe.get("promoted_at"), "promoted_at", optional=True)
    except ValueError as exc:
        raise RecipeValidationError(str(exc)) from exc

    notes = recipe.get("notes") or []
    if not isinstance(notes, list) or not all(isinstance(x, str) and len(x) <= 1000 for x in notes):
        raise RecipeValidationError("invalid notes")

    if status == "VALIDATED":
        if not receipts or not regressions:
            raise RecipeValidationError("validated recipe needs successful receipt and regression")
        if recipe.get("promoted_at") is None:
            raise RecipeValidationError("validated recipe requires promoted_at")
        if validation["field_evidence_required"] and not field_refs:
            raise RecipeValidationError("validated recipe requires field evidence")

    return copy.deepcopy(recipe)


class IncidentRegistry:
    def __init__(self, store: CriticalStore):
        self.store = store

    def observe(
        self,
        *,
        project_id: str,
        resource_id: str,
        symptoms: dict[str, Any],
        environment_fingerprint: str,
        desired_generation: int,
        observed_at: str,
        owner_id: str,
    ) -> dict[str, Any]:
        signature = causal_signature(project_id, resource_id, symptoms)
        sid = incident_stream(project_id, resource_id, signature)
        current = self.store.get_state(sid)
        now = strict_iso(observed_at, "observed_at")
        if not isinstance(environment_fingerprint, str) or not environment_fingerprint.strip() or len(environment_fingerprint) > 512:
            raise ValueError("invalid environment_fingerprint")
        if type(desired_generation) is not int or desired_generation < 1:
            raise ValueError("invalid desired_generation")
        if current is None:
            payload = {
                "schema": "bcp.incident/1",
                "incident_id": "inc-" + signature[:24],
                "project_id": str(project_id),
                "resource_id": str(resource_id),
                "signature": signature,
                "status": "OPEN",
                "attempts": 0,
                "first_observed_at": now,
                "last_observed_at": now,
                "next_retry_at": None,
                "observation": copy.deepcopy(symptoms),
                "environment_fingerprint": str(environment_fingerprint)[:512],
                "matched_recipe_id": None,
                "desired_generation": int(desired_generation),
                "receipt_refs": [],
                "last_error": None,
                "field_certified": False,
            }
            expected_revision = 0
        else:
            payload = copy.deepcopy(current["payload"])
            previous_generation = int(payload.get("desired_generation") or 0)
            payload["last_observed_at"] = now
            payload["observation"] = copy.deepcopy(symptoms)
            payload["environment_fingerprint"] = environment_fingerprint.strip()
            payload["desired_generation"] = desired_generation
            if previous_generation != desired_generation:
                payload["status"] = "OPEN"
                payload["attempts"] = 0
                payload["first_observed_at"] = now
                payload["next_retry_at"] = None
                payload["matched_recipe_id"] = None
                payload["receipt_refs"] = []
                payload["last_error"] = None
            elif payload.get("status") == "RESOLVED":
                payload["status"] = "OPEN"
                payload["next_retry_at"] = None
                payload["matched_recipe_id"] = None
            expected_revision = int(current["revision"])
            if payload == current["payload"]:
                return current

        fence = self.store.acquire_writer_fence(sid, owner_id)
        self.store.commit_transition(
            stream_id=sid,
            expected_revision=expected_revision,
            new_revision=expected_revision + 1,
            fencing_token=fence,
            payload=payload,
            destination="BCP_INCIDENT_LEDGER",
        )
        return self.store.get_state(sid)

    def get(self, project_id: str, resource_id: str, signature: str) -> dict[str, Any]:
        state = self.store.get_state(incident_stream(project_id, resource_id, signature))
        if state is None:
            raise IncidentNotFound(signature)
        return state

    def set_state(
        self,
        project_id: str,
        resource_id: str,
        signature: str,
        *,
        status: str,
        owner_id: str,
        matched_recipe_id: str | None = None,
        increment_attempt: bool = False,
        next_retry_at: str | None = None,
        receipt_ref: str | None = None,
        last_error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if status not in {
            "OPEN","MATCHED","RECONCILING","WAITING_BACKOFF","WAITING_RESOURCE",
            "WAITING_CAPABILITY","NEEDS_REASONING","RESOLVED","FAILED_SAFE",
        }:
            raise ValueError("invalid incident status")
        sid = incident_stream(project_id, resource_id, signature)
        current = self.store.get_state(sid)
        if current is None:
            raise IncidentNotFound(signature)
        payload = copy.deepcopy(current["payload"])
        payload["status"] = status
        payload["matched_recipe_id"] = matched_recipe_id
        payload["next_retry_at"] = next_retry_at
        if increment_attempt:
            payload["attempts"] = int(payload.get("attempts", 0)) + 1
        if receipt_ref:
            refs = list(payload.get("receipt_refs") or [])
            if receipt_ref not in refs:
                refs.append(receipt_ref)
            payload["receipt_refs"] = refs
        payload["last_error"] = copy.deepcopy(last_error)

        fence = self.store.acquire_writer_fence(sid, owner_id)
        self.store.commit_transition(
            stream_id=sid,
            expected_revision=int(current["revision"]),
            new_revision=int(current["revision"]) + 1,
            fencing_token=fence,
            payload=payload,
            destination="BCP_INCIDENT_LEDGER",
        )
        return self.store.get_state(sid)

    def mark_attempt_failed(
        self,
        project_id: str,
        resource_id: str,
        signature: str,
        *,
        owner_id: str,
        now: str,
        backoff_seconds: int,
        max_attempts: int,
        error: dict[str, Any],
        receipt_ref: str | None = None,
    ) -> dict[str, Any]:
        current = self.get(project_id, resource_id, signature)
        attempts = int(current["payload"].get("attempts", 0))
        if attempts >= int(max_attempts):
            return self.set_state(
                project_id, resource_id, signature,
                status="FAILED_SAFE", owner_id=owner_id,
                matched_recipe_id=current["payload"].get("matched_recipe_id"),
                receipt_ref=receipt_ref, last_error=error,
            )
        parsed = parse_iso(now)
        if parsed is None:
            raise ValueError("invalid now")
        retry = parsed + dt.timedelta(seconds=int(backoff_seconds))
        return self.set_state(
            project_id, resource_id, signature,
            status="WAITING_BACKOFF", owner_id=owner_id,
            matched_recipe_id=current["payload"].get("matched_recipe_id"),
            next_retry_at=retry.replace(microsecond=0).isoformat(),
            receipt_ref=receipt_ref, last_error=error,
        )


class RecipeRegistry:
    def __init__(self, store: CriticalStore):
        self.store = store
        self.receipts = ActionReceiptRegistry(store)

    def get(self, recipe_id: str) -> dict[str, Any]:
        state = self.store.get_state(recipe_stream(recipe_id))
        if state is None:
            raise RecipeNotFound(recipe_id)
        return state

    def list(self, *, limit: int = 512) -> list[dict[str, Any]]:
        return self.store.list_states(RECIPE_PREFIX, limit=limit)

    def register_candidate(self, recipe: dict[str, Any], *, owner_id: str) -> dict[str, Any]:
        clean = validate_recipe(recipe)
        if clean["status"] != "CANDIDATE":
            raise RecipeValidationError("new recipes must enter as CANDIDATE")
        sid = recipe_stream(clean["recipe_id"])
        current = self.store.get_state(sid)
        if current is not None:
            if current["payload"] == clean:
                return current
            if current["payload"].get("status") != "CANDIDATE":
                raise RecipeValidationError("non-candidate recipe cannot be overwritten")
        fence = self.store.acquire_writer_fence(sid, owner_id)
        rev = int(current["revision"]) if current else 0
        self.store.commit_transition(
            stream_id=sid,
            expected_revision=rev,
            new_revision=rev + 1,
            fencing_token=fence,
            payload=clean,
            destination="BCP_RECIPE_LEDGER",
        )
        return self.store.get_state(sid)

    def promote(
        self,
        recipe_id: str,
        *,
        owner_id: str,
        successful_receipt_refs: list[str],
        regression_refs: list[str],
        promoted_at: str,
        field_evidence_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        current = self.get(recipe_id)
        recipe = copy.deepcopy(current["payload"])
        if recipe.get("status") not in {"CANDIDATE","SUSPENDED"}:
            raise RecipeValidationError("only candidate/suspended recipe may be promoted")
        success_refs = list(dict.fromkeys(successful_receipt_refs))
        regression_refs = list(dict.fromkeys(regression_refs))
        field_refs = list(dict.fromkeys(field_evidence_refs or []))
        required_caps = {
            step["capability_id"] for step in recipe["steps"] if not bool(step.get("optional", False))
        }
        try:
            success_states = [
                self.receipts.require_success(
                    ref,
                    project_scopes=recipe["project_scopes"],
                    field=False,
                )
                for ref in success_refs
            ]
            proved_caps = {state["payload"]["capability_id"] for state in success_states}
            if not required_caps <= proved_caps:
                missing = sorted(required_caps - proved_caps)
                raise RecipeValidationError("successful receipts do not cover required capabilities: " + ",".join(missing))
            if recipe["validation"].get("field_evidence_required"):
                field_states = [
                    self.receipts.require_success(
                        ref,
                        project_scopes=recipe["project_scopes"],
                        field=True,
                    )
                    for ref in field_refs
                ]
                field_caps = {state["payload"]["capability_id"] for state in field_states}
                if not required_caps <= field_caps:
                    missing = sorted(required_caps - field_caps)
                    raise RecipeValidationError("field receipts do not cover required capabilities: " + ",".join(missing))
        except (ActionReceiptError, ActionReceiptValidationError) as exc:
            raise RecipeValidationError("receipt validation failed: " + str(exc)) from exc

        validation = recipe.setdefault("validation", {})
        validation["successful_receipt_refs"] = success_refs
        validation["regression_refs"] = regression_refs
        validation["field_evidence_refs"] = field_refs
        recipe["status"] = "VALIDATED"
        recipe["promoted_at"] = str(promoted_at)
        recipe["updated_at"] = str(promoted_at)
        clean = validate_recipe(recipe)

        sid = recipe_stream(recipe_id)
        fence = self.store.acquire_writer_fence(sid, owner_id)
        self.store.commit_transition(
            stream_id=sid,
            expected_revision=int(current["revision"]),
            new_revision=int(current["revision"]) + 1,
            fencing_token=fence,
            payload=clean,
            destination="BCP_RECIPE_LEDGER",
        )
        return self.store.get_state(sid)

    def match_validated(self, signature: str, project_id: str) -> dict[str, Any] | None:
        sig = str(signature).lower()
        matches = []
        for state in self.list(limit=2048):
            recipe = state["payload"]
            if recipe.get("status") != "VALIDATED" or recipe.get("signature") != sig:
                continue
            scopes = set(recipe.get("project_scopes") or [])
            if project_id in scopes or "*" in scopes:
                matches.append(state)
        if len(matches) > 1:
            raise RecipeAmbiguous(signature)
        return matches[0] if matches else None


class ReconcilePlanner:
    def __init__(self, incidents: IncidentRegistry, recipes: RecipeRegistry):
        self.incidents = incidents
        self.recipes = recipes

    def plan(
        self,
        desired_resource: dict[str, Any],
        observation: dict[str, Any],
        *,
        environment_fingerprint: str,
        resource_mode: str,
        observed_at: str,
        owner_id: str,
    ) -> dict[str, Any]:
        desired_resource = validate_resource(desired_resource)
        if not isinstance(observation, dict) or set(observation) - {"matches_desired","symptoms","evidence_refs"}:
            raise ValueError("invalid observation fields")
        if type(observation.get("matches_desired")) is not bool:
            raise ValueError("observation.matches_desired boolean required")
        strict_iso(observed_at, "observed_at")
        if not isinstance(environment_fingerprint, str) or not environment_fingerprint.strip() or len(environment_fingerprint) > 512:
            raise ValueError("invalid environment_fingerprint")
        meta = desired_resource["metadata"]
        project_id = str(meta["project_id"])
        resource_id = str(meta["resource_id"])
        generation = int(meta["generation"])

        base = {
            "schema": "bcp.reconcile_plan/1",
            "resource_id": resource_id,
            "project_id": project_id,
            "desired_generation": generation,
            "incident_id": None,
            "recipe_id": None,
            "steps": [],
            "field_certified": False,
        }

        if observation["matches_desired"] is True:
            return {**base, "decision": "IN_SYNC", "reason": "OBSERVATION_MATCHES_DESIRED"}

        symptoms = observation.get("symptoms")
        if not isinstance(symptoms, dict) or not symptoms:
            return {**base, "decision": "NEEDS_REASONING", "reason": "DRIFT_WITHOUT_CAUSAL_SYMPTOMS"}

        incident = self.incidents.observe(
            project_id=project_id,
            resource_id=resource_id,
            symptoms=symptoms,
            environment_fingerprint=environment_fingerprint,
            desired_generation=generation,
            observed_at=observed_at,
            owner_id=owner_id,
        )
        incident_payload = incident["payload"]
        signature = incident_payload["signature"]
        base["incident_id"] = incident_payload["incident_id"]

        policy = desired_resource["spec"]["reconcile_policy"]
        mode = str(policy["mode"])
        if mode == "OBSERVE_ONLY":
            return {**base, "decision": "OBSERVE_ONLY_DRIFT", "reason": "RECONCILE_POLICY_OBSERVE_ONLY"}

        max_attempts = int(policy.get("max_attempts_per_incident", 3))
        attempts = int(incident_payload.get("attempts", 0))
        if attempts >= max_attempts:
            return {**base, "decision": "FAILED_SAFE", "reason": "MAX_ATTEMPTS_REACHED"}

        retry_at = parse_iso(incident_payload.get("next_retry_at"))
        now = parse_iso(observed_at)
        if retry_at is not None and now is not None and now < retry_at:
            return {**base, "decision": "WAITING_BACKOFF", "reason": "REPAIR_BACKOFF_ACTIVE"}

        try:
            matched = self.recipes.match_validated(signature, project_id)
        except RecipeAmbiguous:
            return {**base, "decision": "FAILED_SAFE", "reason": "MULTIPLE_VALIDATED_RECIPES_FOR_SIGNATURE"}
        if matched is None:
            return {**base, "decision": "NEEDS_REASONING", "reason": "NO_VALIDATED_RECIPE"}

        recipe = matched["payload"]
        base["recipe_id"] = recipe["recipe_id"]

        policy_permission = PERMISSION_ORDER[str(policy["max_permission_class"])]
        mode_ceiling = MODE_PERMISSION_CEILING[mode]
        effective_permission = min(policy_permission, mode_ceiling)
        if PERMISSION_ORDER[recipe["max_permission_class"]] > effective_permission:
            return {**base, "decision": "POLICY_BLOCKED", "reason": "RECIPE_PERMISSION_EXCEEDS_RECONCILE_POLICY"}

        ceiling = str(policy.get("resource_ceiling") or "R3_HEAVY")
        if RESOURCE_ORDER[recipe["max_resource_class"]] > RESOURCE_ORDER[ceiling]:
            return {**base, "decision": "POLICY_BLOCKED", "reason": "RECIPE_RESOURCE_EXCEEDS_DESIRED_CEILING"}

        steps = []
        for step in recipe["steps"]:
            admission = resource_decide(
                step["resource_class"],
                mode=resource_mode,
                background=False,
                essential=False,
                local_ai_enabled=False,
            )
            if not admission.allowed:
                return {**base, "decision": "WAITING_RESOURCE", "reason": admission.reason}
            steps.append({
                "step_id": step["step_id"],
                "capability_id": step["capability_id"],
                "permission_class": step["permission_class"],
                "resource_class": step["resource_class"],
                "input": copy.deepcopy(step["input_template"]),
                "evidence_contract": list(step["evidence_contract"]),
                "optional": bool(step.get("optional", False)),
            })

        return {
            **base,
            "decision": "EXECUTE_TYPED_PLAN",
            "reason": "VALIDATED_RECIPE_MATCH",
            "steps": steps,
        }


__all__ = [
    "IncidentRegistry",
    "RecipeRegistry",
    "ReconcilePlanner",
    "RecipeError",
    "RecipeNotFound",
    "RecipeAmbiguous",
    "RecipeValidationError",
    "IncidentNotFound",
    "causal_signature",
    "validate_recipe",
]
