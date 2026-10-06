from __future__ import annotations

"""BCP Phase 6 provider-neutral Transport/Cockpit fabric.

This module does not send Telegram messages, upload Drive files, call Nexus, or
inspect hidden model state. It compiles human-facing projections from durable
evidence, plans a typed transport route from capability observations, persists
that route in the shared CriticalStore, and accepts delivery success only from
a real normalized Action Receipt.
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


TRANSPORT_PREFIX = "transport/"
TRANSPORT_IDEMPOTENCY_PREFIX = "transport-idempotency/"
PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
DELIVERY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,199}$")
PROJECTION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,199}$")
SHA_RE = re.compile(r"^[a-f0-9]{64}$")

TRANSPORTS = {
    "LOCAL_NATIVE", "TELEGRAM", "DRIVE", "NEXUS",
    "B_EDGE", "REMOTE_PROVIDER",
}
CAPABILITY_TRANSPORTS = TRANSPORTS | {
    "GITHUB", "BUILDHUB", "DESKTOP_COMMANDER", "NONE",
}
SURFACES = {"TELEGRAM", "CHATGPT", "DRIVE", "LOCAL_UI"}
PAYLOAD_KINDS = {"STATUS", "DETAILS", "ALERT", "APPROVAL", "REPORT", "CHECKPOINT"}
TARGET_SCOPES = {"REPOSITORY", "SIMULATION", "PROVIDER", "FIELD"}
SCOPE_ORDER = {"REPOSITORY": 0, "SIMULATION": 1, "PROVIDER": 2, "FIELD": 3}
EVIDENCE_ORDER = {
    "UNKNOWN": -1,
    "SELF_REPORTED": 0,
    "REPOSITORY_STATIC": 0,
    "SIMULATION": 1,
    "PROVIDER_PROBE": 2,
    "FIELD_READBACK": 3,
}
EVIDENCE_KINDS = {
    "EXIT_CODE", "FILE_READBACK", "HASH", "PROCESS_HEALTH", "HTTP_HEALTH",
    "SERVICE_STATE", "GIT_REVISION", "TEST_RESULT", "ARTIFACT_SIGNATURE",
    "PROVIDER_ACK", "DESTINATION_READBACK", "CUSTOM_VALIDATOR",
}
COMPLETED_STEP_STATES = {
    "VERIFIED", "DONE", "COMMITTED", "CHECKPOINTED", "SUCCESS", "COMPLETED",
}
HUMAN_STATE_MAP = {
    "DONE": "DONE",
    "COMPLETED": "DONE",
    "CANCELLED": "DONE",
    "WAITING_USER": "NEEDS_YOU",
    "HUMAN_APPROVAL_REQUIRED": "NEEDS_YOU",
    "NEEDS_USER": "NEEDS_YOU",
    "BLOCKED": "BLOCKED",
    "HOLD": "BLOCKED",
    "FAILED_SAFE": "BLOCKED",
    "DEGRADED": "DEGRADED",
    "OFFLINE": "DEGRADED",
}
CONNECTIVITY_STATE = {
    "AVAILABLE": "OK",
    "DEGRADED": "DEGRADED",
    "TEMP_UNAVAILABLE": "OFFLINE",
    "AUTH_REQUIRED": "WAITING_AUTH",
    "RESOURCE_HOLD": "OFFLINE",
    "UNSUPPORTED": "OFFLINE",
    "STALE": "STALE",
    "UNKNOWN": "UNKNOWN",
}


class CockpitProjectionError(ValueError):
    pass


class TransportError(RuntimeError):
    pass


class DeliveryNotFound(TransportError):
    pass


class DeliveryCollision(TransportError):
    pass


class DeliveryTransitionError(TransportError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _iso(value: Any, field: str, *, optional: bool = False) -> tuple[str | None, dt.datetime | None]:
    if value is None and optional:
        return None, None
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
    return text, parsed.astimezone(dt.timezone.utc)


def _text(value: Any, field: str, max_len: int, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be string")
    text = value.strip()
    if not text or len(text) > max_len:
        raise ValueError(f"invalid {field}")
    return text


def _human_state(canonical_state: str) -> str:
    state = canonical_state.upper()
    if state in HUMAN_STATE_MAP:
        return HUMAN_STATE_MAP[state]
    if state.startswith("WAITING_") or state in {
        "QUEUED", "RETRY_SCHEDULED", "PROVIDER_PENDING_UNKNOWN",
        "NO_NEW_EXTERNAL_EVIDENCE", "NETWORK_OFFLINE_QUEUEING",
    }:
        return "WAITING"
    if state in {
        "ACCEPTED", "NORMALIZED", "PLANNED", "STARTED", "DISPATCHED",
        "RESULT_RECEIVED", "VALIDATING", "COMMITTED", "CHECKPOINTED", "RUNNING",
    }:
        return "WORKING"
    return "UNKNOWN"


def _normalize_connectivity(
    observations: list[dict[str, Any]],
    *,
    generated_at: dt.datetime,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for obs in observations:
        if not isinstance(obs, dict) or obs.get("schema") != "bcp.capability_observation/1":
            raise CockpitProjectionError("invalid capability observation")
        transport = str(obs.get("transport") or "")
        if transport not in CAPABILITY_TRANSPORTS:
            raise CockpitProjectionError("invalid observation transport")
        provider_id = _text(obs.get("provider_id"), "provider_id", 160)
        node_id = _text(obs.get("node_id"), "node_id", 160)
        observed_at, _ = _iso(obs.get("observed_at"), "observed_at")
        expires_at, expires_dt = _iso(obs.get("expires_at"), "expires_at", optional=True)
        del expires_at
        explicit_fresh = obs.get("fresh")
        fresh = explicit_fresh is True
        if expires_dt is not None and expires_dt < generated_at:
            fresh = False
        state = CONNECTIVITY_STATE.get(str(obs.get("state") or ""), "UNKNOWN")
        if not fresh and state not in {"WAITING_AUTH", "OFFLINE"}:
            state = "STALE"
        evidence_class = str(obs.get("evidence_class") or "UNKNOWN")
        if evidence_class not in EVIDENCE_ORDER:
            evidence_class = "UNKNOWN"
        out.append(
            {
                "transport": transport,
                "provider_id": provider_id,
                "node_id": node_id,
                "state": state,
                "evidence_class": evidence_class,
                "observed_at": observed_at,
                "fresh": fresh,
            }
        )
    out.sort(key=lambda x: (x["transport"], x["provider_id"], x["node_id"]))
    return out


def validate_projection(projection: Any) -> dict[str, Any]:
    allowed = {
        "schema", "projection_id", "project_id", "mission_id", "canonical_state",
        "human_state", "activity", "finite_progress", "current_step",
        "last_completed_step", "next_step", "human_action", "last_proof",
        "connectivity", "technical_refs", "source_revision", "generated_at",
        "field_certified",
    }
    required = allowed
    if not isinstance(projection, dict) or set(projection) != required:
        raise CockpitProjectionError("invalid cockpit projection fields")
    if projection.get("schema") != "bcp.cockpit_projection/1":
        raise CockpitProjectionError("unsupported cockpit projection")
    pid = _text(projection.get("projection_id"), "projection_id", 200)
    if not PROJECTION_RE.fullmatch(pid):
        raise CockpitProjectionError("invalid projection_id")
    project = _text(projection.get("project_id"), "project_id", 128)
    if not PROJECT_RE.fullmatch(project):
        raise CockpitProjectionError("invalid project_id")
    _text(projection.get("mission_id"), "mission_id", 128, optional=True)
    _text(projection.get("canonical_state"), "canonical_state", 128)
    if projection.get("human_state") not in {
        "WORKING", "WAITING", "BLOCKED", "NEEDS_YOU", "DONE", "DEGRADED", "UNKNOWN"
    }:
        raise CockpitProjectionError("invalid human_state")
    if projection.get("activity") not in {
        "RECENT_EVIDENCE", "WAITING_EXTERNAL", "NO_NEW_EXTERNAL_EVIDENCE",
        "BLOCKED", "DONE", "UNKNOWN",
    }:
        raise CockpitProjectionError("invalid activity")

    progress = projection.get("finite_progress")
    if progress is not None:
        if not isinstance(progress, dict) or set(progress) != {
            "completed", "total", "percent", "plan_revision"
        }:
            raise CockpitProjectionError("invalid finite_progress")
        completed = progress.get("completed")
        total = progress.get("total")
        percent = progress.get("percent")
        if type(completed) is not int or type(total) is not int or type(percent) is not int:
            raise CockpitProjectionError("progress counters must be integers")
        if total < 1 or completed < 0 or completed > total:
            raise CockpitProjectionError("invalid finite progress counters")
        expected = (completed * 100) // total
        if percent != expected:
            raise CockpitProjectionError("progress percent is not machine-derived")
        _text(progress.get("plan_revision"), "plan_revision", 160)

    for field in ("current_step", "last_completed_step", "next_step"):
        _text(projection.get(field), field, 500, optional=True)

    action = projection.get("human_action")
    if not isinstance(action, dict) or set(action) != {"state", "instruction"}:
        raise CockpitProjectionError("invalid human_action")
    if action.get("state") not in {"NONE", "REQUIRED", "OPTIONAL"}:
        raise CockpitProjectionError("invalid human_action state")
    instruction = _text(action.get("instruction"), "human_action instruction", 1000, optional=True)
    if action["state"] == "REQUIRED" and not instruction:
        raise CockpitProjectionError("required human action needs instruction")

    proof = projection.get("last_proof")
    if proof is not None:
        if not isinstance(proof, dict) or set(proof) != {
            "sequence", "state", "summary", "source_node", "observed_at", "evidence_refs"
        }:
            raise CockpitProjectionError("invalid last_proof")
        if type(proof.get("sequence")) is not int or proof["sequence"] < 0:
            raise CockpitProjectionError("invalid proof sequence")
        _text(proof.get("state"), "proof state", 128)
        _text(proof.get("summary"), "proof summary", 1000)
        _text(proof.get("source_node"), "proof source_node", 160)
        _iso(proof.get("observed_at"), "proof observed_at")
        refs = proof.get("evidence_refs")
        if not isinstance(refs, list) or len(refs) != len(set(refs)):
            raise CockpitProjectionError("invalid evidence_refs")
        for ref in refs:
            _text(ref, "evidence_ref", 512)

    connectivity = projection.get("connectivity")
    if not isinstance(connectivity, list) or len(connectivity) > 32:
        raise CockpitProjectionError("invalid connectivity")
    for item in connectivity:
        if not isinstance(item, dict) or set(item) != {
            "transport", "provider_id", "node_id", "state",
            "evidence_class", "observed_at", "fresh",
        }:
            raise CockpitProjectionError("invalid connectivity item")
        if item["transport"] not in CAPABILITY_TRANSPORTS:
            raise CockpitProjectionError("invalid connectivity transport")
        if item["state"] not in {"OK", "DEGRADED", "OFFLINE", "WAITING_AUTH", "STALE", "UNKNOWN"}:
            raise CockpitProjectionError("invalid connectivity state")
        if item["evidence_class"] not in EVIDENCE_ORDER:
            raise CockpitProjectionError("invalid connectivity evidence class")
        if type(item["fresh"]) is not bool:
            raise CockpitProjectionError("invalid connectivity freshness")
        _text(item["provider_id"], "connectivity provider_id", 160)
        _text(item["node_id"], "connectivity node_id", 160)
        _iso(item["observed_at"], "connectivity observed_at")

    refs = projection.get("technical_refs")
    if not isinstance(refs, list) or len(refs) > 64 or len(refs) != len(set(refs)):
        raise CockpitProjectionError("invalid technical_refs")
    for ref in refs:
        _text(ref, "technical_ref", 512)
    _text(projection.get("source_revision"), "source_revision", 256)
    _iso(projection.get("generated_at"), "generated_at")
    if projection.get("field_certified") is not False:
        raise CockpitProjectionError("cockpit projection cannot field-certify authority")
    return deepcopy(projection)


def build_cockpit_projection(
    snapshot: dict[str, Any],
    capability_observations: list[dict[str, Any]],
    *,
    generated_at: str,
    stale_after_seconds: int = 60,
) -> dict[str, Any]:
    allowed = {
        "project_id", "mission_id", "canonical_state", "source_revision",
        "plan_finite", "plan_revision", "plan", "current_step",
        "last_completed_step", "next_step", "human_action", "events",
        "technical_refs",
    }
    if not isinstance(snapshot, dict) or set(snapshot) - allowed:
        raise CockpitProjectionError("invalid cockpit source snapshot fields")
    project = _text(snapshot.get("project_id"), "project_id", 128)
    if not PROJECT_RE.fullmatch(project):
        raise CockpitProjectionError("invalid project_id")
    mission_id = _text(snapshot.get("mission_id"), "mission_id", 128, optional=True)
    canonical_state = _text(snapshot.get("canonical_state"), "canonical_state", 128)
    source_revision = _text(snapshot.get("source_revision"), "source_revision", 256)
    generated_text, generated_dt = _iso(generated_at, "generated_at")
    assert generated_dt is not None
    stale_after = int(stale_after_seconds)
    if stale_after < 1 or stale_after > 86400:
        raise CockpitProjectionError("invalid stale_after_seconds")

    plan_finite = snapshot.get("plan_finite") is True
    plan_revision = snapshot.get("plan_revision")
    plan = snapshot.get("plan") or []
    if not isinstance(plan, list):
        raise CockpitProjectionError("plan must be list")
    finite_progress = None
    if plan_finite:
        revision = _text(plan_revision, "plan_revision", 160)
        if not plan:
            raise CockpitProjectionError("finite plan cannot be empty")
        seen: set[str] = set()
        completed = 0
        for step in plan:
            if not isinstance(step, dict) or set(step) - {"step_id", "label", "state", "verified"}:
                raise CockpitProjectionError("invalid plan step")
            sid = _text(step.get("step_id"), "step_id", 128)
            if sid in seen:
                raise CockpitProjectionError("duplicate plan step_id")
            seen.add(sid)
            _text(step.get("label"), "step label", 500)
            state = _text(step.get("state"), "step state", 64)
            if "verified" in step and type(step.get("verified")) is not bool:
                raise CockpitProjectionError("invalid step verified flag")
            if step.get("verified") is True:
                completed += 1
        total = len(plan)
        finite_progress = {
            "completed": completed,
            "total": total,
            "percent": (completed * 100) // total,
            "plan_revision": revision,
        }

    human_action = snapshot.get("human_action")
    if not isinstance(human_action, dict) or set(human_action) != {"state", "instruction"}:
        raise CockpitProjectionError("human_action must be explicit")
    human_action = {
        "state": str(human_action.get("state") or "").upper(),
        "instruction": human_action.get("instruction"),
    }

    events = snapshot.get("events") or []
    if not isinstance(events, list):
        raise CockpitProjectionError("events must be list")
    durable_events: list[tuple[int, dt.datetime, dict[str, Any]]] = []
    for event in events:
        if not isinstance(event, dict) or set(event) - {
            "sequence", "state", "summary", "source_node",
            "observed_at", "evidence_refs", "durable",
        }:
            raise CockpitProjectionError("invalid event")
        seq = event.get("sequence")
        if type(seq) is not int or seq < 0:
            raise CockpitProjectionError("invalid event sequence")
        state = _text(event.get("state"), "event state", 128)
        summary = _text(event.get("summary"), "event summary", 1000)
        source_node = _text(event.get("source_node"), "event source_node", 160)
        observed_text, observed_dt = _iso(event.get("observed_at"), "event observed_at")
        assert observed_dt is not None
        refs = event.get("evidence_refs") or []
        if not isinstance(refs, list) or len(refs) != len(set(refs)):
            raise CockpitProjectionError("invalid event evidence_refs")
        for ref in refs:
            _text(ref, "event evidence_ref", 512)
        if type(event.get("durable")) is not bool:
            raise CockpitProjectionError("event durable flag required")
        if event["durable"]:
            durable_events.append(
                (
                    seq,
                    observed_dt,
                    {
                        "sequence": seq,
                        "state": state,
                        "summary": summary,
                        "source_node": source_node,
                        "observed_at": observed_text,
                        "evidence_refs": list(refs),
                    },
                )
            )

    last_proof = None
    if durable_events:
        durable_events.sort(key=lambda item: (item[0], item[1]))
        last_proof = durable_events[-1][2]

    human_state = _human_state(canonical_state)
    if human_state == "DONE" and (
        last_proof is None or not (last_proof.get("evidence_refs") or [])
    ):
        human_state = "UNKNOWN"
        activity = "UNKNOWN"
    elif human_state in {"BLOCKED", "NEEDS_YOU"}:
        activity = "BLOCKED"
    elif human_state == "DONE":
        activity = "DONE"
    elif last_proof is None:
        activity = "UNKNOWN"
    else:
        _, proof_dt = _iso(last_proof["observed_at"], "proof observed_at")
        assert proof_dt is not None
        age = max(0.0, (generated_dt - proof_dt).total_seconds())
        if age > stale_after:
            activity = "NO_NEW_EXTERNAL_EVIDENCE"
        elif human_state == "WAITING":
            activity = "WAITING_EXTERNAL"
        else:
            activity = "RECENT_EVIDENCE"

    connectivity = _normalize_connectivity(
        capability_observations,
        generated_at=generated_dt,
    )
    technical_refs = snapshot.get("technical_refs") or []
    if not isinstance(technical_refs, list):
        raise CockpitProjectionError("technical_refs must be list")

    identity = {
        "project_id": project,
        "mission_id": mission_id,
        "source_revision": source_revision,
        "canonical_state": canonical_state,
        "plan_revision": plan_revision if plan_finite else None,
        "current_step": snapshot.get("current_step"),
        "last_completed_step": snapshot.get("last_completed_step"),
        "next_step": snapshot.get("next_step"),
        "last_proof_sequence": None if last_proof is None else last_proof["sequence"],
    }
    projection = {
        "schema": "bcp.cockpit_projection/1",
        "projection_id": "proj-" + _sha256(identity)[:32],
        "project_id": project,
        "mission_id": mission_id,
        "canonical_state": canonical_state,
        "human_state": human_state,
        "activity": activity,
        "finite_progress": finite_progress,
        "current_step": snapshot.get("current_step"),
        "last_completed_step": snapshot.get("last_completed_step"),
        "next_step": snapshot.get("next_step"),
        "human_action": human_action,
        "last_proof": last_proof,
        "connectivity": connectivity,
        "technical_refs": list(technical_refs),
        "source_revision": source_revision,
        "generated_at": generated_text,
        "field_certified": False,
    }
    return validate_projection(projection)


def _observation_fresh(obs: dict[str, Any], now: dt.datetime) -> bool:
    if obs.get("fresh") is not True:
        return False
    _, expiry = _iso(obs.get("expires_at"), "expires_at", optional=True)
    return expiry is None or expiry >= now


def _obs_surfaces(details: dict[str, Any]) -> set[str]:
    value = details.get("surfaces")
    if value is None:
        single = details.get("surface")
        value = [] if single is None else [single]
    if not isinstance(value, list):
        return set()
    return {str(x).upper() for x in value if str(x).upper() in SURFACES}


def _scope_ok(evidence_class: str, target_scope: str) -> bool:
    return EVIDENCE_ORDER.get(evidence_class, -1) >= SCOPE_ORDER[target_scope]


def _route_from_observation(
    obs: dict[str, Any],
    *,
    state: str,
    store_forward: bool,
    reason: str,
) -> dict[str, Any]:
    details = obs.get("details") or {}
    contract = details.get("evidence_contract") or []
    if not isinstance(contract, list) or len(contract) != len(set(contract)):
        raise TransportError("invalid transport evidence contract")
    if not contract or not set(contract) <= EVIDENCE_KINDS:
        raise TransportError("transport route requires canonical evidence contract")
    return {
        "state": state,
        "selected_transport": obs["transport"],
        "provider_id": obs["provider_id"],
        "capability_id": obs["capability_id"],
        "store_forward": store_forward,
        "reason": reason,
        "evidence_class": obs["evidence_class"],
        "evidence_contract": list(contract),
    }


def select_transport_route(
    *,
    surface: str,
    preferred_transports: list[str],
    observations: list[dict[str, Any]],
    target_scope: str,
    policy: dict[str, bool],
    now: str,
) -> dict[str, Any]:
    surf = str(surface).upper()
    if surf not in SURFACES:
        raise TransportError("invalid surface")
    if target_scope not in TARGET_SCOPES:
        raise TransportError("invalid target_scope")
    if not isinstance(preferred_transports, list) or not preferred_transports:
        raise TransportError("preferred transports required")
    if len(preferred_transports) != len(set(preferred_transports)):
        raise TransportError("duplicate preferred transport")
    preferred = [str(x).upper() for x in preferred_transports]
    if not set(preferred) <= TRANSPORTS:
        raise TransportError("invalid preferred transport")
    if not isinstance(policy, dict) or set(policy) != {
        "low_data", "allow_degraded", "allow_store_forward"
    } or not all(type(policy[k]) is bool for k in policy):
        raise TransportError("invalid transport policy")
    _, now_dt = _iso(now, "now")
    assert now_dt is not None

    normalized: list[dict[str, Any]] = []
    relevant_auth = False
    relevant_network = False
    for obs in observations:
        if not isinstance(obs, dict) or obs.get("schema") != "bcp.capability_observation/1":
            raise TransportError("invalid capability observation")
        transport = str(obs.get("transport") or "").upper()
        if transport not in CAPABILITY_TRANSPORTS:
            raise TransportError("invalid observation transport")
        details = obs.get("details")
        if not isinstance(details, dict):
            raise TransportError("transport observation details required")
        direction = str(details.get("direction") or "").upper()
        mode = str(details.get("delivery_mode") or "").upper()
        surfaces = _obs_surfaces(details)
        store_targets = details.get("store_forward_surfaces") or []
        if not isinstance(store_targets, list):
            raise TransportError("invalid store_forward_surfaces")
        store_targets = {str(x).upper() for x in store_targets}
        low_data_ok = details.get("low_data_supported") is True
        live_relevant = surf in surfaces and direction in {"EGRESS", "BIDIRECTIONAL"} and mode in {"LIVE", "BOTH"}
        store_relevant = (
            transport == "DRIVE"
            and direction in {"EGRESS", "BIDIRECTIONAL"}
            and mode in {"STORE_FORWARD", "BOTH"}
            and (surf in store_targets or "*" in store_targets)
        )
        if not live_relevant and not store_relevant:
            continue

        state = str(obs.get("state") or "").upper()
        if state == "AUTH_REQUIRED":
            relevant_auth = True
        elif state in {"TEMP_UNAVAILABLE", "RESOURCE_HOLD", "STALE", "UNKNOWN"}:
            relevant_network = True

        evidence_class = str(obs.get("evidence_class") or "UNKNOWN")
        fresh = _observation_fresh(obs, now_dt)
        if not fresh or not _scope_ok(evidence_class, target_scope):
            relevant_network = True
            continue
        if policy["low_data"] and not low_data_ok:
            continue
        normalized.append(
            {
                **obs,
                "transport": transport,
                "state": state,
                "evidence_class": evidence_class,
                "_live_relevant": live_relevant,
                "_store_relevant": store_relevant,
            }
        )

    for transport in preferred:
        candidates = [
            obs for obs in normalized
            if obs["transport"] == transport
            and obs["_live_relevant"]
            and obs["state"] == "AVAILABLE"
        ]
        if candidates:
            candidates.sort(
                key=lambda x: (
                    EVIDENCE_ORDER.get(x["evidence_class"], -1),
                    str(x.get("observed_at") or ""),
                ),
                reverse=True,
            )
            return _route_from_observation(
                candidates[0],
                state="LIVE_READY",
                store_forward=False,
                reason="PREFERRED_LIVE_ROUTE_AVAILABLE",
            )

    if policy["allow_degraded"]:
        for transport in preferred:
            candidates = [
                obs for obs in normalized
                if obs["transport"] == transport
                and obs["_live_relevant"]
                and obs["state"] == "DEGRADED"
            ]
            if candidates:
                candidates.sort(
                    key=lambda x: (
                        EVIDENCE_ORDER.get(x["evidence_class"], -1),
                        str(x.get("observed_at") or ""),
                    ),
                    reverse=True,
                )
                return _route_from_observation(
                    candidates[0],
                    state="DEGRADED_READY",
                    store_forward=False,
                    reason="DEGRADED_LIVE_ROUTE_ALLOWED",
                )

    if policy["allow_store_forward"]:
        candidates = [
            obs for obs in normalized
            if obs["transport"] == "DRIVE"
            and obs["_store_relevant"]
            and obs["state"] in {"AVAILABLE", "DEGRADED"}
        ]
        if candidates:
            candidates.sort(
                key=lambda x: (
                    x["state"] == "AVAILABLE",
                    EVIDENCE_ORDER.get(x["evidence_class"], -1),
                    str(x.get("observed_at") or ""),
                ),
                reverse=True,
            )
            return _route_from_observation(
                candidates[0],
                state="STORE_FORWARD_READY",
                store_forward=True,
                reason="LIVE_ROUTE_UNAVAILABLE_DRIVE_STORE_FORWARD",
            )

    if relevant_auth:
        return {
            "state": "WAITING_AUTH",
            "selected_transport": None,
            "provider_id": None,
            "capability_id": None,
            "store_forward": False,
            "reason": "TRANSPORT_AUTH_REQUIRED",
            "evidence_class": None,
            "evidence_contract": [],
        }
    if relevant_network:
        return {
            "state": "WAITING_NETWORK",
            "selected_transport": None,
            "provider_id": None,
            "capability_id": None,
            "store_forward": False,
            "reason": "NO_FRESH_QUALIFIED_TRANSPORT",
            "evidence_class": None,
            "evidence_contract": [],
        }
    return {
        "state": "NO_ROUTE",
        "selected_transport": None,
        "provider_id": None,
        "capability_id": None,
        "store_forward": False,
        "reason": "NO_DECLARED_TRANSPORT_ROUTE",
        "evidence_class": None,
        "evidence_contract": [],
    }


def _delivery_stream(project_id: str, delivery_id: str) -> str:
    project = _text(project_id, "project_id", 128)
    delivery = _text(delivery_id, "delivery_id", 200)
    if not PROJECT_RE.fullmatch(project) or not DELIVERY_RE.fullmatch(delivery):
        raise TransportError("invalid delivery stream identity")
    return f"{TRANSPORT_PREFIX}{project}/{delivery}"


def _idempotency_stream(project_id: str, idempotency_key: str) -> str:
    project = _text(project_id, "project_id", 128)
    key = _text(idempotency_key, "idempotency_key", 240)
    if not PROJECT_RE.fullmatch(project):
        raise TransportError("invalid idempotency project")
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"{TRANSPORT_IDEMPOTENCY_PREFIX}{project}/{digest}"


def _expired(delivery: dict[str, Any], *, now: str | None = None) -> bool:
    expires = delivery.get("expires_at")
    if expires is None:
        return False
    _, expires_dt = _iso(expires, "expires_at")
    if now is None:
        now_dt = dt.datetime.now(dt.timezone.utc)
    else:
        _, now_dt = _iso(now, "now")
    assert expires_dt is not None and now_dt is not None
    return now_dt > expires_dt


def validate_delivery(delivery: Any) -> dict[str, Any]:
    required = {
        "schema", "delivery_id", "project_id", "mission_id", "surface",
        "payload_kind", "projection", "content_sha256", "preferred_transports",
        "target_scope", "policy", "route", "status", "receipt_ref",
        "idempotency_key", "created_at", "expires_at", "field_certified",
    }
    if not isinstance(delivery, dict) or set(delivery) != required:
        raise TransportError("invalid delivery fields")
    if delivery.get("schema") != "bcp.transport_delivery/1":
        raise TransportError("unsupported delivery schema")
    delivery_id = _text(delivery.get("delivery_id"), "delivery_id", 200)
    if not DELIVERY_RE.fullmatch(delivery_id):
        raise TransportError("invalid delivery_id")
    project = _text(delivery.get("project_id"), "project_id", 128)
    if not PROJECT_RE.fullmatch(project):
        raise TransportError("invalid project_id")
    _text(delivery.get("mission_id"), "mission_id", 128, optional=True)
    if delivery.get("surface") not in SURFACES:
        raise TransportError("invalid surface")
    if delivery.get("payload_kind") not in PAYLOAD_KINDS:
        raise TransportError("invalid payload_kind")
    projection = validate_projection(delivery.get("projection"))
    if projection["project_id"] != project or projection["mission_id"] != delivery.get("mission_id"):
        raise TransportError("delivery/projection identity mismatch")
    content_hash = str(delivery.get("content_sha256") or "")
    if not SHA_RE.fullmatch(content_hash) or content_hash != _sha256(projection):
        raise TransportError("invalid delivery content hash")
    preferred = delivery.get("preferred_transports")
    if not isinstance(preferred, list) or not preferred or len(preferred) != len(set(preferred)):
        raise TransportError("invalid preferred transports")
    if not set(preferred) <= TRANSPORTS:
        raise TransportError("invalid preferred transport")
    if delivery.get("target_scope") not in TARGET_SCOPES:
        raise TransportError("invalid target_scope")
    policy = delivery.get("policy")
    if not isinstance(policy, dict) or set(policy) != {
        "low_data", "allow_degraded", "allow_store_forward"
    } or not all(type(policy[k]) is bool for k in policy):
        raise TransportError("invalid delivery policy")
    route = delivery.get("route")
    if not isinstance(route, dict) or set(route) != {
        "state", "selected_transport", "provider_id", "capability_id",
        "store_forward", "reason", "evidence_class", "evidence_contract",
    }:
        raise TransportError("invalid delivery route")
    if route["state"] not in {
        "LIVE_READY", "DEGRADED_READY", "STORE_FORWARD_READY", "WAITING_AUTH",
        "WAITING_NETWORK", "NO_ROUTE", "ACKNOWLEDGED", "FAILED_SAFE",
    }:
        raise TransportError("invalid route state")
    selected = route.get("selected_transport")
    if selected is not None and selected not in TRANSPORTS:
        raise TransportError("invalid selected transport")
    _text(route.get("provider_id"), "route provider_id", 160, optional=True)
    _text(route.get("capability_id"), "route capability_id", 160, optional=True)
    if type(route.get("store_forward")) is not bool:
        raise TransportError("invalid store_forward")
    _text(route.get("reason"), "route reason", 500)
    evidence_class = route.get("evidence_class")
    if evidence_class is not None and evidence_class not in EVIDENCE_ORDER:
        raise TransportError("invalid route evidence class")
    contract = route.get("evidence_contract")
    if not isinstance(contract, list) or len(contract) != len(set(contract)) or not set(contract) <= EVIDENCE_KINDS:
        raise TransportError("invalid route evidence contract")
    ready = route["state"] in {"LIVE_READY", "DEGRADED_READY", "STORE_FORWARD_READY", "ACKNOWLEDGED"}
    if ready and (selected is None or route.get("provider_id") is None or route.get("capability_id") is None or not contract):
        raise TransportError("ready route requires typed provider capability and evidence contract")
    expected_status = {
        "LIVE_READY": "DISPATCH_READY",
        "DEGRADED_READY": "DISPATCH_READY",
        "STORE_FORWARD_READY": "DISPATCH_READY",
        "WAITING_AUTH": "WAITING_AUTH",
        "WAITING_NETWORK": "WAITING_NETWORK",
        "NO_ROUTE": "WAITING_NETWORK",
        "ACKNOWLEDGED": "ACKNOWLEDGED",
        "FAILED_SAFE": "FAILED_SAFE",
    }[route["state"]]
    if delivery.get("status") != expected_status:
        raise TransportError("delivery status does not match route state")
    receipt_ref = _text(delivery.get("receipt_ref"), "receipt_ref", 200, optional=True)
    if delivery["status"] == "ACKNOWLEDGED" and not receipt_ref:
        raise TransportError("acknowledged delivery requires receipt")
    _text(delivery.get("idempotency_key"), "idempotency_key", 240)
    _, created_dt = _iso(delivery.get("created_at"), "created_at")
    _, expires_dt = _iso(delivery.get("expires_at"), "expires_at", optional=True)
    if expires_dt is not None and created_dt is not None and expires_dt <= created_dt:
        raise TransportError("delivery expiry must be after creation")
    if delivery.get("field_certified") is not False:
        raise TransportError("transport delivery is not canonical field authority")
    return deepcopy(delivery)


class TransportController:
    def __init__(self, store: CriticalStore):
        self.store = store
        self.receipts = ActionReceiptRegistry(store)

    def get(self, project_id: str, delivery_id: str) -> dict[str, Any]:
        state = self.store.get_state(_delivery_stream(project_id, delivery_id))
        if state is None:
            raise DeliveryNotFound(delivery_id)
        return {
            "delivery": state["payload"],
            "revision": state["revision"],
            "content_hash": state["content_hash"],
            "fencing_token": state["fencing_token"],
            "committed_epoch": state["committed_epoch"],
        }

    def list(self, project_id: str | None = None, *, limit: int = 512) -> list[dict[str, Any]]:
        prefix = TRANSPORT_PREFIX
        if project_id is not None:
            project = _text(project_id, "project_id", 128)
            if not PROJECT_RE.fullmatch(project):
                raise TransportError("invalid project_id")
            prefix += project + "/"
        states = self.store.list_states(prefix, limit=limit)
        return [
            {
                "delivery": item["payload"],
                "revision": item["revision"],
                "content_hash": item["content_hash"],
                "fencing_token": item["fencing_token"],
                "committed_epoch": item["committed_epoch"],
            }
            for item in states
        ]

    def latest_projection(self, project_id: str) -> dict[str, Any] | None:
        items = self.list(project_id, limit=2048)
        if not items:
            return None
        latest = max(items, key=lambda item: item["committed_epoch"])
        return deepcopy(latest["delivery"]["projection"])

    def prepare(
        self,
        *,
        delivery_id: str,
        surface: str,
        payload_kind: str,
        projection: dict[str, Any],
        preferred_transports: list[str],
        target_scope: str,
        policy: dict[str, bool],
        observations: list[dict[str, Any]],
        idempotency_key: str,
        created_at: str,
        expires_at: str | None,
        owner_id: str,
    ) -> dict[str, Any]:
        projection = validate_projection(projection)
        route = select_transport_route(
            surface=surface,
            preferred_transports=preferred_transports,
            observations=observations,
            target_scope=target_scope,
            policy=policy,
            now=created_at,
        )
        status = {
            "LIVE_READY": "DISPATCH_READY",
            "DEGRADED_READY": "DISPATCH_READY",
            "STORE_FORWARD_READY": "DISPATCH_READY",
            "WAITING_AUTH": "WAITING_AUTH",
            "WAITING_NETWORK": "WAITING_NETWORK",
            "NO_ROUTE": "WAITING_NETWORK",
        }[route["state"]]
        payload = {
            "schema": "bcp.transport_delivery/1",
            "delivery_id": delivery_id,
            "project_id": projection["project_id"],
            "mission_id": projection["mission_id"],
            "surface": str(surface).upper(),
            "payload_kind": str(payload_kind).upper(),
            "projection": projection,
            "content_sha256": _sha256(projection),
            "preferred_transports": [str(x).upper() for x in preferred_transports],
            "target_scope": target_scope,
            "policy": deepcopy(policy),
            "route": route,
            "status": status,
            "receipt_ref": None,
            "idempotency_key": idempotency_key,
            "created_at": created_at,
            "expires_at": expires_at,
            "field_certified": False,
        }
        clean = validate_delivery(payload)
        sid = _delivery_stream(clean["project_id"], delivery_id)
        idem_sid = _idempotency_stream(clean["project_id"], clean["idempotency_key"])
        idem_payload = {
            "schema": "bcp.transport_idempotency/1",
            "project_id": clean["project_id"],
            "delivery_id": delivery_id,
            "idempotency_key": clean["idempotency_key"],
            "content_sha256": clean["content_sha256"],
        }
        idem_current = self.store.get_state(idem_sid)
        if idem_current is None:
            idem_fence = self.store.acquire_writer_fence(idem_sid, owner_id)
            try:
                self.store.commit_transition(
                    stream_id=idem_sid,
                    expected_revision=0,
                    new_revision=1,
                    fencing_token=idem_fence,
                    payload=idem_payload,
                    destination="BCP_TRANSPORT_IDEMPOTENCY",
                )
            except Exception:
                idem_current = self.store.get_state(idem_sid)
                if idem_current is None:
                    raise
        if idem_current is None:
            idem_current = self.store.get_state(idem_sid)
        if idem_current is not None and idem_current["payload"] != idem_payload:
            raise DeliveryCollision("idempotency_key already bound to another delivery/content")

        current = self.store.get_state(sid)
        if current is not None:
            if current["payload"] == clean:
                return self.get(clean["project_id"], delivery_id)
            raise DeliveryCollision(f"delivery_id already committed with different content: {delivery_id}")
        fence = self.store.acquire_writer_fence(sid, owner_id)
        self.store.commit_transition(
            stream_id=sid,
            expected_revision=0,
            new_revision=1,
            fencing_token=fence,
            payload=clean,
            destination="BCP_TRANSPORT_STATE",
        )
        return self.get(clean["project_id"], delivery_id)

    def dispatch_plan(
        self,
        project_id: str,
        delivery_id: str,
        *,
        now: str | None = None,
    ) -> dict[str, Any]:
        item = self.get(project_id, delivery_id)
        delivery = item["delivery"]
        if _expired(delivery, now=now):
            raise DeliveryTransitionError("delivery expired before dispatch")
        if delivery["status"] != "DISPATCH_READY":
            raise DeliveryTransitionError("delivery is not dispatch-ready")
        route = delivery["route"]
        return {
            "schema": "bcp.transport_dispatch_plan/1",
            "delivery_id": delivery_id,
            "project_id": delivery["project_id"],
            "mission_id": delivery["mission_id"],
            "surface": delivery["surface"],
            "payload_kind": delivery["payload_kind"],
            "transport": route["selected_transport"],
            "provider_id": route["provider_id"],
            "capability_id": route["capability_id"],
            "input": {
                "delivery_id": delivery_id,
                "idempotency_key": delivery["idempotency_key"],
                "content_sha256": delivery["content_sha256"],
                "projection": deepcopy(delivery["projection"]),
                "store_forward": route["store_forward"],
            },
            "evidence_contract": list(route["evidence_contract"]),
            "field_certified": False,
        }

    def acknowledge(
        self,
        project_id: str,
        delivery_id: str,
        receipt_id: str,
        *,
        owner_id: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        item = self.get(project_id, delivery_id)
        delivery = deepcopy(item["delivery"])
        if _expired(delivery, now=now):
            raise DeliveryTransitionError("delivery expired before acknowledgement")
        if delivery["status"] == "ACKNOWLEDGED":
            if delivery["receipt_ref"] == receipt_id:
                return item
            raise DeliveryTransitionError("delivery already acknowledged by another receipt")
        if delivery["status"] != "DISPATCH_READY":
            raise DeliveryTransitionError("delivery is not awaiting dispatch receipt")

        try:
            receipt_state = self.receipts.require_success(
                receipt_id,
                project_scopes=[project_id],
                field=delivery["target_scope"] == "FIELD",
            )
        except (ActionReceiptError, ActionReceiptValidationError) as exc:
            raise DeliveryTransitionError("delivery receipt validation failed: " + str(exc)) from exc
        receipt = receipt_state["payload"]
        route = delivery["route"]
        if receipt["idempotency_key"] != delivery["idempotency_key"]:
            raise DeliveryTransitionError("receipt idempotency key does not match delivery")
        if delivery.get("expires_at") is not None:
            receipt_time = receipt.get("committed_at") or receipt.get("created_at")
            _, receipt_dt = _iso(receipt_time, "receipt committed_at")
            _, expires_dt = _iso(delivery["expires_at"], "expires_at")
            assert receipt_dt is not None and expires_dt is not None
            if receipt_dt > expires_dt:
                raise DeliveryTransitionError("receipt was committed after delivery expiry")
        if receipt["provider_id"] != route["provider_id"]:
            raise DeliveryTransitionError("receipt provider does not match selected transport route")
        if receipt["capability_id"] != route["capability_id"]:
            raise DeliveryTransitionError("receipt capability does not match selected transport route")
        pass_kinds = {
            evidence["kind"]
            for evidence in receipt.get("evidence") or []
            if evidence.get("status") == "PASS"
        }
        missing = set(route["evidence_contract"]) - pass_kinds
        if missing:
            raise DeliveryTransitionError(
                "delivery receipt evidence contract incomplete: " + ",".join(sorted(missing))
            )

        delivery["route"]["state"] = "ACKNOWLEDGED"
        delivery["route"]["reason"] = "PROVIDER_DELIVERY_RECEIPT_VERIFIED"
        delivery["status"] = "ACKNOWLEDGED"
        delivery["receipt_ref"] = receipt_id
        clean = validate_delivery(delivery)

        sid = _delivery_stream(project_id, delivery_id)
        fence = self.store.acquire_writer_fence(sid, owner_id)
        self.store.commit_transition(
            stream_id=sid,
            expected_revision=int(item["revision"]),
            new_revision=int(item["revision"]) + 1,
            fencing_token=fence,
            payload=clean,
            destination="BCP_TRANSPORT_STATE",
        )
        return self.get(project_id, delivery_id)


__all__ = [
    "CockpitProjectionError",
    "TransportError",
    "DeliveryNotFound",
    "DeliveryCollision",
    "DeliveryTransitionError",
    "build_cockpit_projection",
    "validate_projection",
    "select_transport_route",
    "validate_delivery",
    "TransportController",
]
