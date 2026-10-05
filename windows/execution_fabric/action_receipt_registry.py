from __future__ import annotations

"""Immutable normalized Action Receipt registry for the BCP Execution Fabric.

Receipts are provider-neutral proof objects defined by bcp.action_receipt/1.
They are stored in the same fenced CriticalStore under hashed receipt streams.
A receipt_id is immutable: identical replay is accepted, conflicting reuse fails closed.
"""

import copy
import datetime as dt
import hashlib
import re
from typing import Any, Iterable

from .critical_store import CriticalStore


RECEIPT_PREFIX = "receipt/"
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")

STATUS = {
    "ACCEPTED", "RUNNING", "SUCCEEDED", "FAILED", "ROLLED_BACK",
    "WAITING_PROVIDER", "WAITING_RESOURCE", "WAITING_USER", "SKIPPED", "UNKNOWN",
}
RESULT = {"PASS", "FAIL", "PARTIAL", "OBSERVED", "DEFERRED", "NOT_APPLICABLE", "UNKNOWN"}
PROOF_SCOPE = {"REPOSITORY", "SIMULATION", "PROVIDER", "FIELD"}
DURABILITY = {
    "OBSERVED_ONLY", "DURABLE_LOCAL", "OUTBOX_COMMITTED", "REPLICATED", "PROVIDER_COMMITTED",
}
EVIDENCE_KIND = {
    "EXIT_CODE", "FILE_READBACK", "HASH", "PROCESS_HEALTH", "HTTP_HEALTH",
    "SERVICE_STATE", "GIT_REVISION", "TEST_RESULT", "ARTIFACT_SIGNATURE",
    "PROVIDER_ACK", "DESTINATION_READBACK", "CUSTOM_VALIDATOR",
}
EVIDENCE_STATUS = {"PASS", "FAIL", "OBSERVED", "NOT_APPLICABLE", "UNKNOWN"}
READBACK_STATUS = {"PASS", "FAIL", "PARTIAL", "NOT_RUN", "UNKNOWN"}
SIDE_EFFECT_STATE = {"PLANNED", "APPLIED", "VERIFIED", "ROLLED_BACK", "FAILED"}

TOP_LEVEL_KEYS = {
    "schema", "receipt_id", "mission_id", "project_id", "action_id", "job_id", "step_id",
    "capability_id", "provider_id", "node_id", "idempotency_key", "status", "result",
    "proof_scope", "field_certified", "durability", "committed_revision", "fencing_token",
    "content_hash", "predecessor_hash", "output_hash", "source_revision",
    "environment_fingerprint", "outbox_message_id", "idempotent_replay", "evidence",
    "readback", "side_effects", "error", "created_at", "committed_at",
}
REQUIRED_KEYS = {
    "schema", "receipt_id", "mission_id", "project_id", "action_id", "capability_id",
    "provider_id", "idempotency_key", "status", "result", "proof_scope",
    "field_certified", "durability", "committed_revision", "created_at", "evidence",
}


class ActionReceiptError(RuntimeError):
    pass


class ActionReceiptNotFound(ActionReceiptError):
    pass


class ActionReceiptCollision(ActionReceiptError):
    pass


class ActionReceiptValidationError(ActionReceiptError):
    pass


def _text(value: Any, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise ActionReceiptValidationError(f"{field} must be string")
    text = value.strip()
    if len(text) < minimum or len(text) > maximum:
        raise ActionReceiptValidationError(f"invalid {field}")
    return text


def _optional_text(value: Any, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > maximum:
        raise ActionReceiptValidationError(f"invalid {field}")
    return value


def _iso(value: Any, field: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    text = _text(value, field, 1, 96)
    probe = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = dt.datetime.fromisoformat(probe)
    except ValueError as exc:
        raise ActionReceiptValidationError(f"invalid {field}") from exc
    if parsed.tzinfo is None:
        raise ActionReceiptValidationError(f"{field} must include timezone")
    return text


def _hash(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise ActionReceiptValidationError(f"invalid {field}")
    return value.lower()


def receipt_stream(receipt_id: str) -> str:
    rid = _text(receipt_id, "receipt_id", 8, 200)
    return RECEIPT_PREFIX + hashlib.sha256(rid.encode("utf-8")).hexdigest()


def validate_action_receipt(receipt: Any) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise ActionReceiptValidationError("receipt must be object")
    if set(receipt) - TOP_LEVEL_KEYS:
        raise ActionReceiptValidationError("unexpected receipt field")
    if not REQUIRED_KEYS <= set(receipt):
        raise ActionReceiptValidationError("missing required receipt field")
    if receipt.get("schema") != "bcp.action_receipt/1":
        raise ActionReceiptValidationError("unsupported receipt schema")

    _text(receipt.get("receipt_id"), "receipt_id", 8, 200)
    _text(receipt.get("mission_id"), "mission_id", 1, 128)
    _text(receipt.get("project_id"), "project_id", 1, 128)
    _text(receipt.get("action_id"), "action_id", 1, 160)
    _text(receipt.get("capability_id"), "capability_id", 3, 160)
    _text(receipt.get("provider_id"), "provider_id", 1, 160)
    _text(receipt.get("idempotency_key"), "idempotency_key", 8, 240)

    for field, cap in (
        ("job_id", 160), ("step_id", 160), ("node_id", 160),
        ("source_revision", 256), ("environment_fingerprint", 512),
        ("outbox_message_id", 200),
    ):
        _optional_text(receipt.get(field), field, cap)

    if receipt.get("status") not in STATUS:
        raise ActionReceiptValidationError("invalid status")
    if receipt.get("result") not in RESULT:
        raise ActionReceiptValidationError("invalid result")
    if receipt.get("proof_scope") not in PROOF_SCOPE:
        raise ActionReceiptValidationError("invalid proof_scope")
    if type(receipt.get("field_certified")) is not bool:
        raise ActionReceiptValidationError("field_certified must be boolean")
    if receipt.get("durability") not in DURABILITY:
        raise ActionReceiptValidationError("invalid durability")
    if type(receipt.get("committed_revision")) is not int or int(receipt["committed_revision"]) < 0:
        raise ActionReceiptValidationError("invalid committed_revision")
    if receipt.get("fencing_token") is not None and (
        type(receipt.get("fencing_token")) is not int or int(receipt["fencing_token"]) < 1
    ):
        raise ActionReceiptValidationError("invalid fencing_token")
    if "idempotent_replay" in receipt and type(receipt.get("idempotent_replay")) is not bool:
        raise ActionReceiptValidationError("idempotent_replay must be boolean")

    for field in ("content_hash", "predecessor_hash", "output_hash"):
        _hash(receipt.get(field), field)

    if receipt["field_certified"] and receipt["proof_scope"] != "FIELD":
        raise ActionReceiptValidationError("field certification requires FIELD proof scope")
    if receipt["status"] == "SUCCEEDED" and receipt["result"] != "PASS":
        raise ActionReceiptValidationError("SUCCEEDED receipt must be PASS")

    evidence = receipt.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ActionReceiptValidationError("receipt evidence required")
    seen_evidence: set[str] = set()
    allowed_evidence = {"evidence_id", "kind", "status", "value", "sha256", "source", "observed_at"}
    for item in evidence:
        if not isinstance(item, dict) or set(item) - allowed_evidence:
            raise ActionReceiptValidationError("invalid evidence object")
        if not {"evidence_id", "kind", "status", "observed_at"} <= set(item):
            raise ActionReceiptValidationError("evidence required fields missing")
        eid = _text(item.get("evidence_id"), "evidence_id", 1, 200)
        if eid in seen_evidence:
            raise ActionReceiptValidationError("duplicate evidence_id")
        seen_evidence.add(eid)
        if item.get("kind") not in EVIDENCE_KIND:
            raise ActionReceiptValidationError("invalid evidence kind")
        if item.get("status") not in EVIDENCE_STATUS:
            raise ActionReceiptValidationError("invalid evidence status")
        _hash(item.get("sha256"), "evidence sha256")
        _optional_text(item.get("source"), "evidence source", 500)
        _iso(item.get("observed_at"), "evidence observed_at")

    readback = receipt.get("readback")
    if readback is not None:
        if not isinstance(readback, dict) or set(readback) - {"status", "summary", "observed_revision"}:
            raise ActionReceiptValidationError("invalid readback")
        if readback.get("status") is not None and readback.get("status") not in READBACK_STATUS:
            raise ActionReceiptValidationError("invalid readback status")
        _optional_text(readback.get("summary"), "readback summary", 2000)
        _optional_text(readback.get("observed_revision"), "readback observed_revision", 256)

    side_effects = receipt.get("side_effects")
    if side_effects is not None:
        if not isinstance(side_effects, list):
            raise ActionReceiptValidationError("side_effects must be list")
        for item in side_effects:
            if not isinstance(item, dict) or set(item) - {"effect_id", "state", "journal_ref"}:
                raise ActionReceiptValidationError("invalid side effect")
            if not {"effect_id", "state"} <= set(item):
                raise ActionReceiptValidationError("side effect required fields missing")
            _text(item.get("effect_id"), "effect_id", 1, 200)
            if item.get("state") not in SIDE_EFFECT_STATE:
                raise ActionReceiptValidationError("invalid side effect state")
            _optional_text(item.get("journal_ref"), "journal_ref", 500)

    error = receipt.get("error")
    if error is not None:
        if not isinstance(error, dict) or set(error) - {"class", "code", "detail", "retryable"}:
            raise ActionReceiptValidationError("invalid error")
        if "class" in error:
            _text(error.get("class"), "error class", 1, 160)
        _optional_text(error.get("code"), "error code", 160)
        _optional_text(error.get("detail"), "error detail", 2000)
        if "retryable" in error and type(error.get("retryable")) is not bool:
            raise ActionReceiptValidationError("error retryable must be boolean")

    _iso(receipt.get("created_at"), "created_at")
    _iso(receipt.get("committed_at"), "committed_at", optional=True)
    return copy.deepcopy(receipt)


class ActionReceiptRegistry:
    def __init__(self, store: CriticalStore):
        self.store = store

    def get(self, receipt_id: str) -> dict[str, Any]:
        state = self.store.get_state(receipt_stream(receipt_id))
        if state is None:
            raise ActionReceiptNotFound(receipt_id)
        if state["payload"].get("receipt_id") != receipt_id:
            raise ActionReceiptCollision("receipt hash collision")
        return state

    def list(self, *, limit: int = 512) -> list[dict[str, Any]]:
        return self.store.list_states(RECEIPT_PREFIX, limit=limit)

    def put(self, receipt: dict[str, Any], *, owner_id: str) -> dict[str, Any]:
        clean = validate_action_receipt(receipt)
        sid = receipt_stream(clean["receipt_id"])
        current = self.store.get_state(sid)
        if current is not None:
            if current["payload"] == clean:
                return current
            raise ActionReceiptCollision(f"receipt_id already committed with different content: {clean['receipt_id']}")

        fence = self.store.acquire_writer_fence(sid, owner_id)
        self.store.commit_transition(
            stream_id=sid,
            expected_revision=0,
            new_revision=1,
            fencing_token=fence,
            payload=clean,
            destination="BCP_ACTION_RECEIPT",
        )
        return self.get(clean["receipt_id"])

    def require_success(
        self,
        receipt_id: str,
        *,
        project_scopes: Iterable[str] | None = None,
        field: bool = False,
    ) -> dict[str, Any]:
        state = self.get(receipt_id)
        receipt = state["payload"]
        if receipt["status"] != "SUCCEEDED" or receipt["result"] != "PASS":
            raise ActionReceiptValidationError(f"receipt is not successful: {receipt_id}")
        if receipt["durability"] == "OBSERVED_ONLY":
            raise ActionReceiptValidationError(f"receipt is not durable: {receipt_id}")
        evidence = receipt.get("evidence") or []
        if not any(item.get("status") == "PASS" for item in evidence):
            raise ActionReceiptValidationError(f"receipt has no PASS evidence: {receipt_id}")
        if any(item.get("status") == "FAIL" for item in evidence):
            raise ActionReceiptValidationError(f"receipt contains FAIL evidence: {receipt_id}")
        readback = receipt.get("readback")
        if isinstance(readback, dict) and readback.get("status") not in (None, "PASS"):
            raise ActionReceiptValidationError(f"receipt readback is not PASS: {receipt_id}")

        scopes = set(project_scopes or [])
        if scopes and "*" not in scopes and receipt["project_id"] not in scopes:
            raise ActionReceiptValidationError(f"receipt project outside recipe scope: {receipt_id}")

        if field and not (
            receipt.get("field_certified") is True and receipt.get("proof_scope") == "FIELD"
        ):
            raise ActionReceiptValidationError(f"receipt is not field certified: {receipt_id}")
        return state


__all__ = [
    "ActionReceiptRegistry",
    "ActionReceiptError",
    "ActionReceiptNotFound",
    "ActionReceiptCollision",
    "ActionReceiptValidationError",
    "validate_action_receipt",
    "receipt_stream",
]
