from __future__ import annotations

"""BCP/UCMF provider-neutral memory admission on the shared CriticalStore.

Phase 6 candidate.

This module converges the existing B-EDGE EdgeMemory/EdgeMemoryClaim semantics with
the Windows Execution Fabric. It does not create another database or memory authority.

One CriticalStore stream represents one logical memory slot. Every claim (admitted or
rejected) advances that stream's durable history. The payload keeps the current canonical
projection plus the last claim decision. Therefore a rejected claim is auditable without
replacing the canonical value, and an admitted claim updates both atomically.
"""

import copy
import datetime as dt
import hashlib
import json
import re
from typing import Any, Iterable

from .critical_store import CriticalStore


MEMORY_PREFIX = "memory/"
PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
CLAIM_RE = re.compile(r"^mcl-[A-Za-z0-9._-]{8,96}$")
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")

SCOPES = {
    "USER_MEMORY",
    "PROJECT_MEMORY",
    "TECHNICAL_KNOWLEDGE",
    "OPERATING_STATE",
    "HISTORY",
    "POLICY",
}
CATEGORIES = {"NORMATIVE", "DESCRIPTIVE", "DERIVED", "UNTRUSTED_CONTENT"}
EVIDENCE_RANK = {
    "UNTRUSTED_EXTERNAL": 0,
    "UNVERIFIED": 0,
    "MODEL_PROPOSED": 1,
    "CACHE": 2,
    "SOURCE_VERIFIED": 3,
    "MACHINE_READBACK": 4,
    "MACHINE_VERIFIED": 4,
    "VALIDATED": 5,
    "USER_DECLARED": 6,
    "SYSTEM_POLICY": 7,
}
PRIVILEGED_NORMATIVE_EVIDENCE = {"SYSTEM_POLICY", "USER_DECLARED", "VALIDATED"}
SENSITIVITY = {"PUBLIC", "INTERNAL", "PRIVATE", "SECRET_NO_STORE"}

AUTHORITY_CLASS = {
    "SYSTEM_POLICY": "CURRENT_EXPLICIT_USER_OR_SIGNED_POLICY",
    "USER_DECLARED": "CURRENT_EXPLICIT_USER_OR_SIGNED_POLICY",
    "VALIDATED": "VALIDATED_DERIVED_SUMMARY",
    "MACHINE_READBACK": "MACHINE_VERIFIED_CANONICAL",
    "MACHINE_VERIFIED": "MACHINE_VERIFIED_CANONICAL",
    "SOURCE_VERIFIED": "SOURCE_VERIFIED_PROJECT_FACT",
    # CACHE is deliberately downgraded when exported. A cache is not authority merely
    # because it exists locally.
    "CACHE": "MODEL_PROPOSED",
    "MODEL_PROPOSED": "MODEL_PROPOSED",
    "UNTRUSTED_EXTERNAL": "UNTRUSTED_EXTERNAL_CONTENT",
    "UNVERIFIED": "UNTRUSTED_EXTERNAL_CONTENT",
}

CLAIM_KEYS = {
    "schema", "claim_id", "project_id", "scope", "memory_key", "category",
    "payload", "evidence_class", "source", "authority", "provenance",
    "source_revision", "source_hash", "sensitivity", "llm_exportable",
    "pinned", "expires_at", "supersedes_claim_id", "idempotency_key",
    "observed_at",
}
REQUIRED_CLAIM_KEYS = {
    "schema", "claim_id", "project_id", "scope", "memory_key", "category",
    "payload", "evidence_class", "source", "authority", "provenance",
    "llm_exportable", "pinned", "idempotency_key", "observed_at",
}


class MemoryFabricError(RuntimeError):
    pass


class MemorySlotNotFound(MemoryFabricError):
    pass


class MemoryClaimConflict(MemoryFabricError):
    pass


class MemoryAdmissionHold(MemoryFabricError):
    """Claim cannot be safely persisted at all, e.g. SECRET_NO_STORE."""


def _text(value: Any, field: str, max_len: int, *, min_len: int = 1) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be string")
    text = value.strip()
    if len(text) < min_len or len(text) > max_len:
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


def _parse_iso(value: str | None) -> dt.datetime | None:
    if value is None:
        return None
    text = str(value)
    probe = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = dt.datetime.fromisoformat(probe)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def memory_stream(project_id: str, scope: str, memory_key: str) -> str:
    project = _text(project_id, "project_id", 128, min_len=2)
    if not PROJECT_RE.fullmatch(project):
        raise ValueError("invalid project_id")
    sc = _text(scope, "scope", 64).upper()
    if sc not in SCOPES:
        raise ValueError("invalid memory scope")
    key = _text(memory_key, "memory_key", 160)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"{MEMORY_PREFIX}{project}/{sc}/{digest}"


def validate_claim(claim: Any) -> dict[str, Any]:
    if not isinstance(claim, dict):
        raise ValueError("memory claim must be object")
    if set(claim) - CLAIM_KEYS or not REQUIRED_CLAIM_KEYS <= set(claim):
        raise ValueError("invalid memory claim fields")
    if claim.get("schema") != "bcp.memory_claim/1":
        raise ValueError("unsupported memory claim schema")

    claim_id = _text(claim.get("claim_id"), "claim_id", 100)
    if not CLAIM_RE.fullmatch(claim_id):
        raise ValueError("invalid claim_id")
    project = _text(claim.get("project_id"), "project_id", 128, min_len=2)
    if not PROJECT_RE.fullmatch(project):
        raise ValueError("invalid project_id")

    scope = _text(claim.get("scope"), "scope", 64).upper()
    if scope not in SCOPES:
        raise ValueError("invalid scope")
    _text(claim.get("memory_key"), "memory_key", 160)

    category = _text(claim.get("category"), "category", 64).upper()
    if category not in CATEGORIES:
        raise ValueError("invalid category")
    evidence = _text(claim.get("evidence_class"), "evidence_class", 64).upper()
    if evidence not in EVIDENCE_RANK:
        raise ValueError("invalid evidence_class")

    if scope in {"USER_MEMORY", "POLICY"} and evidence not in PRIVILEGED_NORMATIVE_EVIDENCE:
        raise ValueError("USER_MEMORY/POLICY requires user/validated/system evidence")
    if category == "NORMATIVE" and evidence not in PRIVILEGED_NORMATIVE_EVIDENCE:
        raise ValueError("NORMATIVE memory requires privileged evidence")

    _text(claim.get("source"), "source", 160)
    _text(claim.get("authority"), "authority", 96)
    _text(claim.get("provenance"), "provenance", 1024)

    revision = claim.get("source_revision")
    if revision is not None and (not isinstance(revision, str) or len(revision) > 256):
        raise ValueError("invalid source_revision")
    source_hash = claim.get("source_hash")
    if source_hash is not None and (
        not isinstance(source_hash, str) or not HEX64.fullmatch(source_hash)
    ):
        raise ValueError("invalid source_hash")

    sensitivity = str(claim.get("sensitivity") or "INTERNAL").upper()
    if sensitivity not in SENSITIVITY:
        raise ValueError("invalid sensitivity")
    if type(claim.get("llm_exportable")) is not bool:
        raise ValueError("llm_exportable must be boolean")
    if type(claim.get("pinned")) is not bool:
        raise ValueError("pinned must be boolean")
    if sensitivity == "SECRET_NO_STORE":
        if claim["llm_exportable"]:
            raise ValueError("SECRET_NO_STORE cannot be LLM exportable")
        # Do not return a normalized payload that a caller may then persist.
        raise MemoryAdmissionHold("SECRET_NO_STORE payload must not enter normal memory")

    _iso(claim.get("expires_at"), "expires_at", optional=True)
    supersedes = claim.get("supersedes_claim_id")
    if supersedes is not None:
        if not isinstance(supersedes, str) or not CLAIM_RE.fullmatch(supersedes):
            raise ValueError("invalid supersedes_claim_id")
    _text(claim.get("idempotency_key"), "idempotency_key", 192, min_len=8)
    _iso(claim.get("observed_at"), "observed_at")

    clean = copy.deepcopy(claim)
    clean["scope"] = scope
    clean["category"] = category
    clean["evidence_class"] = evidence
    clean["sensitivity"] = sensitivity
    clean["source_hash"] = source_hash.lower() if source_hash else None
    clean["source_revision"] = revision
    clean["expires_at"] = claim.get("expires_at")
    clean["supersedes_claim_id"] = supersedes
    return clean


def evidence_rank(evidence_class: str | None) -> int:
    return EVIDENCE_RANK.get(str(evidence_class or "UNVERIFIED").upper(), 0)


def can_replace_memory(
    scope: str,
    old_evidence: str | None,
    old_pinned: bool,
    new_evidence: str,
) -> bool:
    """Exact semantic port of EdgePolicy.canReplaceMemory."""
    sc = str(scope or "").upper()
    new = str(new_evidence or "UNVERIFIED").upper()
    if sc in {"USER_MEMORY", "POLICY"} and new not in PRIVILEGED_NORMATIVE_EVIDENCE:
        return False
    if not old_evidence:
        return True
    old_rank = evidence_rank(old_evidence)
    new_rank = evidence_rank(new)
    if old_pinned and new_rank < old_rank:
        return False
    return new_rank >= old_rank


def _context_authority(evidence_class: str) -> str:
    return AUTHORITY_CLASS[evidence_class]


def _is_expired(record: dict[str, Any] | None, now: dt.datetime) -> bool:
    if not record:
        return False
    expires = _parse_iso(record.get("expires_at"))
    return expires is not None and expires <= now


def _canonical_record_hash(record: dict[str, Any]) -> str:
    raw = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _canonical_record(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": claim["claim_id"],
        "project_id": claim["project_id"],
        "memory_key": claim["memory_key"],
        "category": claim["category"],
        "scope": claim["scope"],
        "authority_class": _context_authority(claim["evidence_class"]),
        "evidence_class": claim["evidence_class"],
        "source": claim["source"],
        "authority": claim["authority"],
        "provenance": claim["provenance"],
        "source_revision": claim.get("source_revision"),
        "source_hash": claim.get("source_hash"),
        "sensitivity": claim["sensitivity"],
        "llm_exportable": claim["llm_exportable"],
        "payload": copy.deepcopy(claim["payload"]),
        "pinned": claim["pinned"],
        "updated_at": claim["observed_at"],
        "expires_at": claim.get("expires_at"),
        "supersedes": [claim["supersedes_claim_id"]] if claim.get("supersedes_claim_id") else [],
        "conflicts_with": [],
    }


def _claim_result(
    claim: dict[str, Any],
    *,
    state: str,
    reason: str,
    canonical_updated: bool,
) -> dict[str, Any]:
    return {
        **copy.deepcopy(claim),
        "state": state,
        "reason": reason,
        "canonical_memory_updated": canonical_updated,
    }


class MemoryFabric:
    def __init__(self, store: CriticalStore):
        self.store = store

    def slot(self, project_id: str, scope: str, memory_key: str) -> dict[str, Any]:
        state = self.store.get_state(memory_stream(project_id, scope, memory_key))
        if state is None:
            raise MemorySlotNotFound(f"{project_id}/{scope}/{memory_key}")
        return state

    def _history_claims(self, stream_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for event in self.store.history(stream_id):
            payload = event.get("payload") or {}
            claim = payload.get("last_claim")
            if isinstance(claim, dict):
                out.append(claim)
        return out

    def admit(self, claim: dict[str, Any], *, owner_id: str) -> dict[str, Any]:
        clean = validate_claim(claim)
        sid = memory_stream(clean["project_id"], clean["scope"], clean["memory_key"])
        current = self.store.get_state(sid)

        # Exact idempotency is durable even if a later claim already became current.
        for prior in reversed(self._history_claims(sid)) if current is not None else []:
            if prior.get("idempotency_key") == clean["idempotency_key"]:
                same_identity = (
                    prior.get("claim_id") == clean["claim_id"]
                    and prior.get("project_id") == clean["project_id"]
                    and prior.get("scope") == clean["scope"]
                    and prior.get("memory_key") == clean["memory_key"]
                )
                if not same_identity:
                    raise MemoryClaimConflict("idempotency key reused for another claim identity")
                return {
                    "schema": "bcp.memory_claim_receipt/1",
                    "result": "ALREADY_RECORDED",
                    "claim": copy.deepcopy(prior),
                    "slot_revision": current["revision"],
                    "field_certified": False,
                }

        now = _parse_iso(clean["observed_at"]) or _now_utc()
        old_canonical = copy.deepcopy((current or {}).get("payload", {}).get("canonical"))
        if _is_expired(old_canonical, now):
            old_canonical = None

        prior_claim_ids = {
            str(item.get("claim_id"))
            for item in self._history_claims(sid)
            if item.get("claim_id")
        } if current is not None else set()
        explicit_supersedes = clean.get("supersedes_claim_id")
        if explicit_supersedes and explicit_supersedes not in prior_claim_ids:
            raise MemoryClaimConflict("invalid_supersedes_claim_id")

        current_claim_id = old_canonical.get("id") if old_canonical else None
        if not explicit_supersedes and current_claim_id:
            clean["supersedes_claim_id"] = str(current_claim_id)

        old_evidence = old_canonical.get("evidence_class") if old_canonical else None
        old_pinned = bool(old_canonical.get("pinned")) if old_canonical else False
        admitted = can_replace_memory(
            clean["scope"], old_evidence, old_pinned, clean["evidence_class"]
        )

        if admitted:
            canonical = _canonical_record(clean)
            decision = _claim_result(
                clean,
                state="ADMITTED",
                reason="PRECEDENCE_ACCEPTED",
                canonical_updated=True,
            )
        else:
            canonical = old_canonical
            decision = _claim_result(
                clean,
                state="REJECTED",
                reason="PRECEDENCE_REJECTED",
                canonical_updated=False,
            )

        previous_count = int((current or {}).get("payload", {}).get("claim_count") or 0)
        payload = {
            "schema": "bcp.memory_slot/1",
            "project_id": clean["project_id"],
            "scope": clean["scope"],
            "memory_key": clean["memory_key"],
            "canonical": canonical,
            "last_claim": decision,
            "claim_count": previous_count + 1,
            "updated_at": clean["observed_at"],
            "field_certified": False,
        }

        current_revision = int(current["revision"]) if current else 0
        fence = self.store.acquire_writer_fence(sid, owner_id)
        receipt = self.store.commit_transition(
            stream_id=sid,
            expected_revision=current_revision,
            new_revision=current_revision + 1,
            fencing_token=fence,
            payload=payload,
            destination="BCP_MEMORY_FABRIC",
        )
        return {
            "schema": "bcp.memory_claim_receipt/1",
            "result": "ADMITTED" if admitted else "REJECTED",
            "claim": decision,
            "canonical": copy.deepcopy(canonical),
            "slot_revision": receipt.revision,
            "fencing_token": receipt.fencing_token,
            "content_hash": receipt.content_hash,
            "outbox_message_id": receipt.outbox_message_id,
            "field_certified": False,
        }

    def canonical(
        self,
        project_id: str,
        *,
        scopes: Iterable[str] | None = None,
        now: dt.datetime | None = None,
        limit: int = 512,
    ) -> list[dict[str, Any]]:
        project = _text(project_id, "project_id", 128, min_len=2)
        if not PROJECT_RE.fullmatch(project):
            raise ValueError("invalid project_id")
        wanted = {str(x).upper() for x in (scopes or SCOPES)}
        if not wanted <= SCOPES:
            raise ValueError("invalid memory scope filter")
        instant = now or _now_utc()
        states = self.store.list_states(f"{MEMORY_PREFIX}{project}/", limit=limit)
        out: list[dict[str, Any]] = []
        for state in states:
            payload = state["payload"]
            if payload.get("scope") not in wanted:
                continue
            record = payload.get("canonical")
            if not isinstance(record, dict) or _is_expired(record, instant):
                continue
            item = copy.deepcopy(record)
            item["slot_revision"] = int(state["revision"])
            # Context/index equality follows canonical content, not the latest rejected
            # claim stored in the slot envelope.
            item["slot_content_hash"] = _canonical_record_hash(record)
            item["slot_state_hash"] = state["content_hash"]
            out.append(item)
        out.sort(
            key=lambda x: (
                0 if x.get("pinned") else 1,
                -evidence_rank(x.get("evidence_class")),
                str(x.get("memory_key") or ""),
            )
        )
        return out

    def claim_ledger(self, project_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        project = _text(project_id, "project_id", 128, min_len=2)
        rows: list[dict[str, Any]] = []
        for state in self.store.list_states(f"{MEMORY_PREFIX}{project}/", limit=512):
            for claim in self._history_claims(state["stream_id"]):
                rows.append(copy.deepcopy(claim))
        rows.sort(key=lambda x: str(x.get("observed_at") or ""), reverse=True)
        return rows[: max(1, min(int(limit), 2000))]


def as_context_item(record: dict[str, Any]) -> dict[str, Any]:
    """Project a canonical memory record into the existing bcp.context_pack/1 item."""
    return {
        "id": record["id"],
        "category": record["category"],
        "scope": record["scope"],
        "authority_class": record["authority_class"],
        "provenance": record["provenance"],
        "sensitivity": record.get("sensitivity"),
        "llm_exportable": bool(record["llm_exportable"]),
        "payload": copy.deepcopy(record["payload"]),
        "updated_at": record["updated_at"],
        "expires_at": record.get("expires_at"),
        "supersedes": list(record.get("supersedes") or []),
        "conflicts_with": list(record.get("conflicts_with") or []),
    }


__all__ = [
    "MemoryFabric",
    "MemoryFabricError",
    "MemorySlotNotFound",
    "MemoryClaimConflict",
    "MemoryAdmissionHold",
    "SCOPES",
    "CATEGORIES",
    "EVIDENCE_RANK",
    "evidence_rank",
    "can_replace_memory",
    "validate_claim",
    "memory_stream",
    "as_context_item",
]
