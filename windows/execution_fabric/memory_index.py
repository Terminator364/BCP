from __future__ import annotations

"""Rebuildable FTS5 index for BCP/UCMF canonical memory.

The FTS table is DERIVED and never an authority source. If FTS5 is unavailable,
corrupt, stale or deleted, the MemoryFabric remains correct and the index can be
reconstructed from canonical memory records.
"""

import hashlib
import json
import re
import sqlite3
from typing import Any, Iterable

from .critical_store import CriticalStore


TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9_.-]{2,}", re.UNICODE)


class MemoryFtsIndex:
    def __init__(self, store: CriticalStore):
        self.store = store
        self.available = self._ensure()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.store.path), timeout=5.0, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA busy_timeout=5000")
        con.execute("PRAGMA mmap_size=0")
        return con

    def _ensure(self) -> bool:
        try:
            with self._connect() as con:
                con.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_fts_meta(
                        project_id TEXT PRIMARY KEY,
                        source_fingerprint TEXT NOT NULL,
                        indexed_count INTEGER NOT NULL,
                        updated_epoch REAL NOT NULL DEFAULT (unixepoch())
                    )
                    """
                )
                con.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                        project_id UNINDEXED,
                        scope UNINDEXED,
                        memory_key,
                        content,
                        claim_id UNINDEXED,
                        slot_hash UNINDEXED,
                        tokenize='unicode61 remove_diacritics 2'
                    )
                    """
                )
            return True
        except sqlite3.DatabaseError:
            return False

    @staticmethod
    def _content(record: dict[str, Any]) -> str:
        payload = json.dumps(
            record.get("payload"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return " ".join(
            [
                str(record.get("memory_key") or ""),
                str(record.get("provenance") or ""),
                str(record.get("source") or ""),
                payload,
            ]
        )

    @staticmethod
    def source_fingerprint(records: Iterable[dict[str, Any]]) -> str:
        parts = sorted(
            str(record.get("slot_content_hash") or record.get("id") or "")
            for record in records
        )
        raw = "\n".join(parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def ensure_project(
        self,
        project_id: str,
        records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.available:
            return {
                "schema": "bcp.memory_index_receipt/1",
                "status": "FTS_UNAVAILABLE",
                "project_id": project_id,
                "indexed": 0,
                "authoritative": False,
            }
        fingerprint = self.source_fingerprint(records)
        try:
            with self._connect() as con:
                row = con.execute(
                    "SELECT source_fingerprint,indexed_count FROM memory_fts_meta WHERE project_id=?",
                    (project_id,),
                ).fetchone()
        except sqlite3.DatabaseError:
            row = None
        if row is not None and str(row["source_fingerprint"]) == fingerprint:
            return {
                "schema": "bcp.memory_index_receipt/1",
                "status": "UNCHANGED",
                "project_id": project_id,
                "indexed": int(row["indexed_count"]),
                "source_fingerprint": fingerprint,
                "authoritative": False,
            }
        receipt = self.rebuild_project(project_id, records)
        if receipt["status"] == "REBUILT":
            with self._connect() as con:
                con.execute(
                    """
                    INSERT INTO memory_fts_meta(project_id,source_fingerprint,indexed_count,updated_epoch)
                    VALUES(?,?,?,unixepoch())
                    ON CONFLICT(project_id) DO UPDATE SET
                      source_fingerprint=excluded.source_fingerprint,
                      indexed_count=excluded.indexed_count,
                      updated_epoch=excluded.updated_epoch
                    """,
                    (project_id, fingerprint, int(receipt["indexed"])),
                )
            receipt["source_fingerprint"] = fingerprint
        return receipt

    def rebuild_project(
        self,
        project_id: str,
        records: Iterable[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.available:
            return {
                "schema": "bcp.memory_index_receipt/1",
                "status": "FTS_UNAVAILABLE",
                "project_id": project_id,
                "indexed": 0,
                "authoritative": False,
            }
        rows = []
        for record in records:
            if not record.get("llm_exportable", False):
                continue
            if record.get("sensitivity") == "SECRET_NO_STORE":
                continue
            rows.append(
                (
                    project_id,
                    str(record.get("scope") or ""),
                    str(record.get("memory_key") or ""),
                    self._content(record),
                    str(record.get("id") or ""),
                    str(record.get("slot_content_hash") or ""),
                )
            )
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                con.execute("DELETE FROM memory_fts WHERE project_id=?", (project_id,))
                con.executemany(
                    """
                    INSERT INTO memory_fts(
                        project_id,scope,memory_key,content,claim_id,slot_hash
                    ) VALUES(?,?,?,?,?,?)
                    """,
                    rows,
                )
                con.execute("COMMIT")
            except Exception:
                con.execute("ROLLBACK")
                raise
        return {
            "schema": "bcp.memory_index_receipt/1",
            "status": "REBUILT",
            "project_id": project_id,
            "indexed": len(rows),
            "authoritative": False,
        }

    @staticmethod
    def _query(text: str) -> str:
        tokens = []
        seen = set()
        for token in TOKEN_RE.findall(str(text or "")):
            folded = token.casefold()
            if folded in seen:
                continue
            seen.add(folded)
            safe = token.replace('"', '""')
            tokens.append(f'"{safe}"')
            if len(tokens) >= 12:
                break
        return " OR ".join(tokens)

    def search(self, project_id: str, query: str, *, limit: int = 24) -> list[dict[str, Any]]:
        if not self.available:
            return []
        expression = self._query(query)
        if not expression:
            return []
        n = max(1, min(int(limit), 100))
        try:
            with self._connect() as con:
                rows = con.execute(
                    """
                    SELECT project_id,scope,memory_key,claim_id,slot_hash,bm25(memory_fts) AS rank
                    FROM memory_fts
                    WHERE memory_fts MATCH ? AND project_id=?
                    ORDER BY rank ASC
                    LIMIT ?
                    """,
                    (expression, project_id, n),
                ).fetchall()
        except sqlite3.DatabaseError:
            return []
        return [dict(row) for row in rows]

    def clear_project(self, project_id: str) -> None:
        if not self.available:
            return
        with self._connect() as con:
            con.execute("DELETE FROM memory_fts WHERE project_id=?", (project_id,))
            con.execute("DELETE FROM memory_fts_meta WHERE project_id=?", (project_id,))


__all__ = ["MemoryFtsIndex"]
