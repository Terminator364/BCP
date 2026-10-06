from __future__ import annotations

"""Deterministic BCP/UCMF Context Compiler.

Phase 6 candidate.

Retrieval ladder implemented here:
- L0: exact durable revision/core cache inputs;
- L1: exact structured memory keys / deterministic lexical scoring;
- L2: bounded SQLite FTS5 derived index;
- L3: explicit supersession/conflict relations carried by memory records;
- L4/L5: NEVER invoked here. The compiler only emits an escalation recommendation.

The compiler is correct with zero models available.
"""

import copy
import datetime as dt
import hashlib
import json
import re
from typing import Any, Iterable

from .memory_fabric import (
    MemoryFabric,
    as_context_item,
    evidence_rank,
)
from .memory_index import MemoryFtsIndex


GLOBAL_PROJECT_ID = "BCP_GLOBAL"
DEFAULT_MAX_BYTES = 32 * 1024
TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9_.-]{2,}", re.UNICODE)

CRITICAL_SCOPES = {"USER_MEMORY", "POLICY"}
PROJECT_CORE_SCOPES = {"PROJECT_MEMORY", "POLICY", "TECHNICAL_KNOWLEDGE"}
TASK_SCOPES = {
    "PROJECT_MEMORY",
    "TECHNICAL_KNOWLEDGE",
    "OPERATING_STATE",
    "HISTORY",
}


class ContextCompilerError(RuntimeError):
    pass


class ContextBudgetExceeded(ContextCompilerError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _tokens(text: str) -> list[str]:
    out = []
    seen = set()
    for token in TOKEN_RE.findall(str(text or "")):
        folded = token.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        out.append(folded)
        if len(out) >= 32:
            break
    return out


def _search_text(record: dict[str, Any]) -> str:
    return " ".join(
        [
            str(record.get("memory_key") or ""),
            str(record.get("provenance") or ""),
            str(record.get("source") or ""),
            _canonical_json(record.get("payload")),
        ]
    ).casefold()


def _exact_score(record: dict[str, Any], query_tokens: list[str]) -> int:
    if not query_tokens:
        return 0
    key = str(record.get("memory_key") or "").casefold()
    text = _search_text(record)
    score = 0
    for token in query_tokens:
        if token == key:
            score += 12
        elif token in key:
            score += 7
        if token in text:
            score += 2
    if record.get("pinned"):
        score += 4
    score += min(4, evidence_rank(record.get("evidence_class")))
    return score


def _revision(records: Iterable[dict[str, Any]]) -> int:
    """Stable equality revision derived from canonical slot hashes.

    It is intentionally not claimed to be a global monotonic sequence. It is a compact
    deterministic revision fingerprint for Context Resolution equality checks.
    """
    parts = sorted(
        str(record.get("slot_content_hash") or record.get("id") or "")
        for record in records
    )
    if not parts:
        return 0
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:15], 16)


def _is_exportable(record: dict[str, Any]) -> bool:
    return (
        bool(record.get("llm_exportable"))
        and record.get("sensitivity") != "SECRET_NO_STORE"
    )


def _dedupe(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    seen = set()
    for record in records:
        identity = (
            str(record.get("project_id") or ""),
            str(record.get("scope") or ""),
            str(record.get("memory_key") or ""),
            str(record.get("id") or ""),
        )
        if identity in seen:
            continue
        seen.add(identity)
        out.append(record)
    return out


def _sort_core(record: dict[str, Any]) -> tuple:
    return (
        0 if record.get("pinned") else 1,
        -evidence_rank(record.get("evidence_class")),
        0 if record.get("category") == "NORMATIVE" else 1,
        str(record.get("memory_key") or ""),
    )


def _semantic_projection(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope": pack["scope"],
        "revisions": pack["revisions"],
        "layers": pack["layers"],
        "tool_policy": pack.get("tool_policy") or {},
        "resource_state": pack.get("resource_state") or {},
        "warnings": pack.get("warnings") or [],
    }


class ContextCompiler:
    def __init__(
        self,
        memory: MemoryFabric,
        *,
        index: MemoryFtsIndex | None = None,
        global_project_id: str = GLOBAL_PROJECT_ID,
    ):
        self.memory = memory
        self.index = index or MemoryFtsIndex(memory.store)
        self.global_project_id = global_project_id

    def _records(self, project_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        global_records = self.memory.canonical(self.global_project_id, limit=512)
        project_records = self.memory.canonical(project_id, limit=1024)
        return global_records, project_records

    @staticmethod
    def _critical(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            [
                record for record in records
                if _is_exportable(record)
                and record.get("scope") in CRITICAL_SCOPES
                and (
                    record.get("pinned")
                    or evidence_rank(record.get("evidence_class")) >= 5
                )
            ],
            key=_sort_core,
        )

    @staticmethod
    def _project_core(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            [
                record for record in records
                if _is_exportable(record)
                and record.get("scope") in PROJECT_CORE_SCOPES
                and (
                    record.get("pinned")
                    or evidence_rank(record.get("evidence_class")) >= 3
                )
            ],
            key=_sort_core,
        )

    def _task_candidates(
        self,
        project_id: str,
        project_records: list[dict[str, Any]],
        query: str,
    ) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
        tokens = _tokens(query)
        exact_ranked = []
        for record in project_records:
            if not _is_exportable(record) or record.get("scope") not in TASK_SCOPES:
                continue
            score = _exact_score(record, tokens)
            if score > 0:
                exact_ranked.append((score, record))
        exact_ranked.sort(key=lambda x: (-x[0], _sort_core(x[1])))

        selected = [record for _, record in exact_ranked[:24]]
        level = "L1_EXACT" if selected else "L0_CORE_ONLY"

        index_receipt = self.index.ensure_project(
            project_id,
            [record for record in project_records if _is_exportable(record)],
        )
        fts_hits = []
        if query and self.index.available:
            fts_hits = self.index.search(project_id, query, limit=24)
            by_claim = {str(record.get("id")): record for record in project_records}
            for hit in fts_hits:
                record = by_claim.get(str(hit.get("claim_id")))
                if record is not None:
                    selected.append(record)
            if fts_hits:
                level = "L2_FTS"

        # L3 is not a graph database. It is a targeted relation expansion only.
        selected = _dedupe(selected)
        related_ids = set()
        for record in selected:
            related_ids.update(str(x) for x in (record.get("supersedes") or []) if x)
            related_ids.update(str(x) for x in (record.get("conflicts_with") or []) if x)
        if related_ids:
            by_id = {str(record.get("id")): record for record in project_records}
            for related in sorted(related_ids):
                record = by_id.get(related)
                if record is not None and _is_exportable(record):
                    selected.append(record)
            selected = _dedupe(selected)
            level = "L3_RELATIONS"

        trace = {
            "retrieval_level": level,
            "exact_matches": len(exact_ranked),
            "fts_available": bool(self.index.available),
            "fts_status": index_receipt.get("status"),
            "fts_hits": len(fts_hits),
            "semantic_vector_called": False,
            "llm_called": False,
        }
        return selected[:32], level, trace

    @staticmethod
    def _evidence_refs(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        refs = []
        seen = set()
        for record in records:
            sha = record.get("source_hash")
            if not sha:
                continue
            key = (record.get("id"), sha)
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                {
                    "id": str(record.get("id")),
                    "kind": str(record.get("evidence_class") or "MEMORY_SOURCE"),
                    "hash": str(sha),
                    "locator": str(record.get("provenance") or "")[:1024] or None,
                }
            )
        return refs

    @staticmethod
    def _pack_size(pack: dict[str, Any]) -> int:
        return len(_canonical_json(pack).encode("utf-8"))

    @staticmethod
    def _trim_noncritical(
        global_core: list[dict[str, Any]],
        project_core: list[dict[str, Any]],
        task_delta: list[dict[str, Any]],
        *,
        scope: dict[str, Any],
        revisions: dict[str, Any],
        resource_state: dict[str, Any],
        trace: dict[str, Any],
        generated_at: str,
        max_bytes: int,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        warnings: list[str] = []

        def build(g, p, t):
            all_records = _dedupe([*g, *p, *t])
            layers = {
                "global_core": [as_context_item(x) for x in g],
                "project_core": [as_context_item(x) for x in p],
                "task_delta": [as_context_item(x) for x in t],
                "evidence_refs": ContextCompiler._evidence_refs(all_records),
            }
            draft = {
                "schema": "bcp.context_pack/1",
                "context_pack_id": "ctx-pending",
                "generated_at": generated_at,
                "scope": scope,
                "revisions": revisions,
                "layers": layers,
                "tool_policy": {
                    "deterministic_first": True,
                    "retrieval_level": trace["retrieval_level"],
                    "llm_required": False,
                    "l4_vector_used": False,
                    "l5_reflective_llm_used": False,
                },
                "resource_state": resource_state,
                "warnings": warnings,
                "hash": "0" * 64,
            }
            return draft

        # Pinned critical policy/user memory is never trimmed to make history fit.
        protected_global = [
            x for x in global_core
            if x.get("pinned") or x.get("scope") in CRITICAL_SCOPES
        ]
        protected_project = [
            x for x in project_core
            if x.get("pinned") and x.get("scope") in CRITICAL_SCOPES
        ]

        if ContextCompiler._pack_size(build(protected_global, protected_project, [])) > max_bytes:
            raise ContextBudgetExceeded("critical policy alone exceeds context budget")

        g = list(global_core)
        p = list(project_core)
        t = list(task_delta)
        while ContextCompiler._pack_size(build(g, p, t)) > max_bytes:
            if t:
                t.pop()
                if "TASK_DELTA_TRUNCATED" not in warnings:
                    warnings.append("TASK_DELTA_TRUNCATED")
                continue
            removable_p = [
                i for i, record in enumerate(p)
                if not record.get("pinned") and record.get("scope") not in CRITICAL_SCOPES
            ]
            if removable_p:
                p.pop(removable_p[-1])
                if "PROJECT_CORE_TRUNCATED" not in warnings:
                    warnings.append("PROJECT_CORE_TRUNCATED")
                continue
            removable_g = [
                i for i, record in enumerate(g)
                if not record.get("pinned") and record.get("scope") not in CRITICAL_SCOPES
            ]
            if removable_g:
                g.pop(removable_g[-1])
                if "GLOBAL_CORE_TRUNCATED" not in warnings:
                    warnings.append("GLOBAL_CORE_TRUNCATED")
                continue
            raise ContextBudgetExceeded("context budget cannot be met without critical truncation")
        return g, p, t, warnings

    def compile(
        self,
        project_id: str,
        *,
        query: str = "",
        task_class: str | None = None,
        conversation_ref: str | None = None,
        coordinator_epoch: int = 0,
        resource_state: dict[str, Any] | None = None,
        generated_at: str | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> dict[str, Any]:
        if max_bytes < 4096 or max_bytes > 256 * 1024:
            raise ValueError("invalid context max_bytes")
        global_records, project_records = self._records(project_id)

        global_core_records = self._critical(global_records)
        project_core_records = self._project_core(project_records)
        task_records, level, trace = self._task_candidates(project_id, project_records, query)

        scope = {
            "project_id": project_id,
            "task_class": task_class,
            "conversation_ref": conversation_ref,
        }
        revisions = {
            "global_revision": _revision(global_records),
            "project_revision": _revision(project_records),
            "operating_revision": _revision(
                [x for x in project_records if x.get("scope") == "OPERATING_STATE"]
            ),
            "coordinator_epoch": max(0, int(coordinator_epoch)),
        }
        generated = generated_at or _now()
        state = copy.deepcopy(resource_state or {})

        g, p, t, warnings = self._trim_noncritical(
            global_core_records,
            project_core_records,
            task_records,
            scope=scope,
            revisions=revisions,
            resource_state=state,
            trace=trace,
            generated_at=generated,
            max_bytes=max_bytes,
        )

        records = _dedupe([*g, *p, *t])
        layers = {
            "global_core": [as_context_item(x) for x in g],
            "project_core": [as_context_item(x) for x in p],
            "task_delta": [as_context_item(x) for x in t],
            "evidence_refs": self._evidence_refs(records),
        }
        semantic = {
            "scope": scope,
            "revisions": revisions,
            "layers": layers,
            "tool_policy": {
                "deterministic_first": True,
                "retrieval_level": level,
                "llm_required": False,
                "l4_vector_used": False,
                "l5_reflective_llm_used": False,
                "escalation_next": (
                    "L4_VECTOR_OR_L5_REFLECTIVE_PROVIDER"
                    if query and not task_records
                    else None
                ),
            },
            "resource_state": state,
            "warnings": warnings,
        }
        pack_hash = _hash(semantic)
        pack = {
            "schema": "bcp.context_pack/1",
            "context_pack_id": "ctx-" + pack_hash[:24],
            "generated_at": generated,
            **semantic,
            "hash": pack_hash,
        }
        if self._pack_size(pack) > max_bytes:
            raise ContextBudgetExceeded("final context pack exceeds budget")
        return pack

    def resolve(
        self,
        project_id: str,
        *,
        acknowledged_hash: str | None = None,
        acknowledged_revisions: dict[str, Any] | None = None,
        query: str = "",
        task_class: str | None = None,
        conversation_ref: str | None = None,
        coordinator_epoch: int = 0,
        resource_state: dict[str, Any] | None = None,
        generated_at: str | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> dict[str, Any]:
        pack = self.compile(
            project_id,
            query=query,
            task_class=task_class,
            conversation_ref=conversation_ref,
            coordinator_epoch=coordinator_epoch,
            resource_state=resource_state,
            generated_at=generated_at,
            max_bytes=max_bytes,
        )
        revisions = pack["revisions"]
        if acknowledged_hash and acknowledged_hash == pack["hash"]:
            return {
                "schema": "bcp.context_resolution/1",
                "status": "UNCHANGED",
                "current_revisions": {
                    "global_revision": revisions["global_revision"],
                    "project_revision": revisions["project_revision"],
                    "coordinator_epoch": revisions["coordinator_epoch"],
                },
                "context_pack": None,
                "delta_ids": [],
                "warnings": [],
                "ttl_ms": 30_000,
            }

        ack = acknowledged_revisions or {}
        changed = []
        for key in ("global_revision", "project_revision", "coordinator_epoch"):
            if key in ack and int(ack[key]) != int(revisions[key]):
                changed.append(key)

        return {
            "schema": "bcp.context_resolution/1",
            "status": "FULL_REFRESH",
            "current_revisions": {
                "global_revision": revisions["global_revision"],
                "project_revision": revisions["project_revision"],
                "coordinator_epoch": revisions["coordinator_epoch"],
            },
            "context_pack": pack,
            "delta_ids": changed,
            "warnings": list(pack.get("warnings") or []),
            "ttl_ms": 30_000,
        }


__all__ = [
    "ContextCompiler",
    "ContextCompilerError",
    "ContextBudgetExceeded",
    "GLOBAL_PROJECT_ID",
    "DEFAULT_MAX_BYTES",
]
