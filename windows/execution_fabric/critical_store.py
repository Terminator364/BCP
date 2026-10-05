from __future__ import annotations

"""Experimental A0 critical store + transactional local outbox.

DESIGN-ONLY: not imported by canonical G6.0.22 runtime.

A0 invariants:
- SQLite is local-only; DB/WAL never lives in DriveFS/network/provider-sync roots.
- writer fencing is independent from the last published state;
- a writer must hold the current per-stream monotonic fence token;
- state transition + replication outbox message commit in one FULL-sync transaction;
- outbox delivery uses atomic owner/lease claims so two replicators cannot concurrently own
  the same message;
- `DURABLE_LOCAL` is returned only after COMMIT succeeds.
"""

from dataclasses import dataclass
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

try:
    from .local_path_policy import assert_local_state_root
except ImportError:  # direct-file test compatibility
    from local_path_policy import assert_local_state_root


SCHEMA_VERSION = 3


class CriticalStoreError(RuntimeError):
    pass


class RevisionConflict(CriticalStoreError):
    pass


class FencingConflict(CriticalStoreError):
    pass


class OutboxClaimConflict(CriticalStoreError):
    pass


@dataclass(frozen=True)
class DurableReceipt:
    status: str
    stream_id: str
    revision: int
    fencing_token: int
    content_hash: str
    predecessor_hash: str
    outbox_message_id: str
    idempotent_replay: bool = False


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _valid_stream(stream_id: str) -> str:
    stream = str(stream_id).strip()
    if not stream or len(stream) > 160:
        raise ValueError("invalid stream_id")
    return stream


def _valid_owner(owner_id: str) -> str:
    owner = str(owner_id).strip()
    if not owner or len(owner) > 200:
        raise ValueError("invalid owner_id")
    return owner


class CriticalStore:
    def __init__(self, path: str | Path):
        assert_local_state_root(path)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=5.0, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=FULL")
        con.execute("PRAGMA temp_store=FILE")
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=5000")
        con.execute("PRAGMA mmap_size=0")
        con.execute("PRAGMA cache_size=-2048")
        return con

    def _init_schema(self) -> None:
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS writer_fence(
                    stream_id TEXT PRIMARY KEY,
                    fencing_token INTEGER NOT NULL CHECK(fencing_token > 0),
                    owner_id TEXT NOT NULL,
                    acquired_epoch REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS authority_state(
                    stream_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL CHECK(revision >= 0),
                    fencing_token INTEGER NOT NULL CHECK(fencing_token > 0),
                    content_hash TEXT NOT NULL,
                    predecessor_hash TEXT NOT NULL,
                    payload_json BLOB NOT NULL,
                    committed_epoch REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS authority_history(
                    stream_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    fencing_token INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    predecessor_hash TEXT NOT NULL,
                    payload_json BLOB NOT NULL,
                    committed_epoch REAL NOT NULL,
                    PRIMARY KEY(stream_id, revision),
                    UNIQUE(stream_id, content_hash)
                );

                CREATE TABLE IF NOT EXISTS outbox(
                    message_id TEXT PRIMARY KEY,
                    stream_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    destination TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    envelope_json BLOB NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('PENDING','INFLIGHT','DELIVERED','DEADLETTER')),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt_epoch REAL NOT NULL,
                    created_epoch REAL NOT NULL,
                    delivered_epoch REAL,
                    last_error TEXT,
                    claim_owner TEXT,
                    claim_until_epoch REAL,
                    UNIQUE(stream_id, revision, destination)
                );

                CREATE INDEX IF NOT EXISTS outbox_due_idx
                    ON outbox(state, next_attempt_epoch, created_epoch);
                CREATE INDEX IF NOT EXISTS outbox_claim_idx
                    ON outbox(state, claim_until_epoch, next_attempt_epoch);
                """
            )
            columns = {str(r[1]) for r in con.execute("PRAGMA table_info(outbox)").fetchall()}
            if "claim_owner" not in columns:
                con.execute("ALTER TABLE outbox ADD COLUMN claim_owner TEXT")
            if "claim_until_epoch" not in columns:
                con.execute("ALTER TABLE outbox ADD COLUMN claim_until_epoch REAL")
            con.execute(
                "CREATE INDEX IF NOT EXISTS outbox_claim_idx ON outbox(state,claim_until_epoch,next_attempt_epoch)"
            )
            con.execute(
                "INSERT INTO meta(key,value) VALUES('schema_version',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )

    def pragmas(self) -> dict[str, Any]:
        with self._connect() as con:
            return {
                "journal_mode": con.execute("PRAGMA journal_mode").fetchone()[0],
                "synchronous": con.execute("PRAGMA synchronous").fetchone()[0],
                "mmap_size": con.execute("PRAGMA mmap_size").fetchone()[0],
                "cache_size": con.execute("PRAGMA cache_size").fetchone()[0],
            }

    def acquire_writer_fence(
        self, stream_id: str, owner_id: str, *, now_epoch: float | None = None
    ) -> int:
        stream = _valid_stream(stream_id)
        owner = _valid_owner(owner_id)
        now = float(time.time() if now_epoch is None else now_epoch)
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT fencing_token FROM writer_fence WHERE stream_id=?", (stream,)
            ).fetchone()
            token = (int(row["fencing_token"]) if row is not None else 0) + 1
            con.execute(
                "INSERT INTO writer_fence(stream_id,fencing_token,owner_id,acquired_epoch) VALUES(?,?,?,?) "
                "ON CONFLICT(stream_id) DO UPDATE SET fencing_token=excluded.fencing_token,owner_id=excluded.owner_id,acquired_epoch=excluded.acquired_epoch",
                (stream, token, owner, now),
            )
            con.execute("COMMIT")
            return token
        except Exception:
            try:
                con.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            con.close()

    def current_writer_fence(self, stream_id: str) -> dict[str, Any] | None:
        stream = _valid_stream(stream_id)
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM writer_fence WHERE stream_id=?", (stream,)
            ).fetchone()
        if row is None:
            return None
        return {
            "stream_id": row["stream_id"],
            "fencing_token": int(row["fencing_token"]),
            "owner_id": row["owner_id"],
            "acquired_epoch": float(row["acquired_epoch"]),
        }

    def get_state(self, stream_id: str) -> dict[str, Any] | None:
        stream = _valid_stream(stream_id)
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM authority_state WHERE stream_id=?", (stream,)
            ).fetchone()
        if row is None:
            return None
        return {
            "stream_id": row["stream_id"],
            "revision": int(row["revision"]),
            "fencing_token": int(row["fencing_token"]),
            "content_hash": row["content_hash"],
            "predecessor_hash": row["predecessor_hash"],
            "payload": json.loads(bytes(row["payload_json"]).decode("utf-8")),
            "committed_epoch": float(row["committed_epoch"]),
        }

    def commit_transition(
        self,
        *,
        stream_id: str,
        expected_revision: int,
        new_revision: int,
        fencing_token: int,
        payload: Any,
        destination: str = "DRIVE_RUNTIME",
        now_epoch: float | None = None,
    ) -> DurableReceipt:
        stream = _valid_stream(stream_id)
        dest = str(destination).strip()
        if not dest or len(dest) > 160:
            raise ValueError("invalid destination")
        expected = int(expected_revision)
        new = int(new_revision)
        fence = int(fencing_token)
        if new != expected + 1:
            raise RevisionConflict("new_revision must equal expected_revision + 1")
        if expected < 0 or fence <= 0:
            raise ValueError("invalid revision/fencing token")

        payload_bytes = _canonical_bytes(payload)
        content_hash = _sha256(payload_bytes)
        now = float(time.time() if now_epoch is None else now_epoch)

        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            lease = con.execute(
                "SELECT fencing_token FROM writer_fence WHERE stream_id=?", (stream,)
            ).fetchone()
            if lease is None:
                raise FencingConflict("no writer fence acquired for stream")
            current_lease_token = int(lease["fencing_token"])
            if fence != current_lease_token:
                raise FencingConflict(
                    f"writer token {fence} is not current token {current_lease_token}"
                )

            current = con.execute(
                "SELECT * FROM authority_state WHERE stream_id=?", (stream,)
            ).fetchone()
            if current is None:
                current_revision = 0
                predecessor_hash = "0" * 64
            else:
                current_revision = int(current["revision"])
                predecessor_hash = str(current["content_hash"])

            if current is not None and current_revision == new and str(current["content_hash"]) == content_hash:
                row = con.execute(
                    "SELECT message_id FROM outbox WHERE stream_id=? AND revision=? AND destination=?",
                    (stream, new, dest),
                ).fetchone()
                if row is None:
                    raise CriticalStoreError("state/outbox atomicity invariant broken")
                con.execute("COMMIT")
                return DurableReceipt(
                    status="DURABLE_LOCAL",
                    stream_id=stream,
                    revision=new,
                    fencing_token=fence,
                    content_hash=content_hash,
                    predecessor_hash=str(current["predecessor_hash"]),
                    outbox_message_id=str(row["message_id"]),
                    idempotent_replay=True,
                )

            if current_revision != expected:
                raise RevisionConflict(
                    f"expected revision {expected}, current revision {current_revision}"
                )

            envelope = {
                "schema": "chatgpt-pc.a0-replication-envelope/2",
                "stream_id": stream,
                "revision": new,
                "fencing_token": fence,
                "content_hash": content_hash,
                "predecessor_hash": predecessor_hash,
                "payload": payload,
            }
            envelope_bytes = _canonical_bytes(envelope)
            envelope_hash = _sha256(envelope_bytes)
            message_id = _sha256(
                (f"{stream}\n{new}\n{dest}\n{envelope_hash}").encode("utf-8")
            )

            con.execute(
                "INSERT INTO authority_history(stream_id,revision,fencing_token,content_hash,predecessor_hash,payload_json,committed_epoch) VALUES(?,?,?,?,?,?,?)",
                (stream, new, fence, content_hash, predecessor_hash, payload_bytes, now),
            )
            con.execute(
                "INSERT INTO authority_state(stream_id,revision,fencing_token,content_hash,predecessor_hash,payload_json,committed_epoch) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(stream_id) DO UPDATE SET revision=excluded.revision,fencing_token=excluded.fencing_token,content_hash=excluded.content_hash,predecessor_hash=excluded.predecessor_hash,payload_json=excluded.payload_json,committed_epoch=excluded.committed_epoch",
                (stream, new, fence, content_hash, predecessor_hash, payload_bytes, now),
            )
            con.execute(
                "INSERT INTO outbox(message_id,stream_id,revision,destination,payload_hash,envelope_json,state,attempts,next_attempt_epoch,created_epoch,claim_owner,claim_until_epoch) "
                "VALUES(?,?,?,?,?,?,'PENDING',0,?,?,NULL,NULL)",
                (message_id, stream, new, dest, envelope_hash, envelope_bytes, now, now),
            )
            con.execute("COMMIT")
            return DurableReceipt(
                status="DURABLE_LOCAL",
                stream_id=stream,
                revision=new,
                fencing_token=fence,
                content_hash=content_hash,
                predecessor_hash=predecessor_hash,
                outbox_message_id=message_id,
            )
        except Exception:
            try:
                con.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            con.close()

    @staticmethod
    def _row_to_outbox(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "message_id": row["message_id"],
            "stream_id": row["stream_id"],
            "revision": int(row["revision"]),
            "destination": row["destination"],
            "payload_hash": row["payload_hash"],
            "envelope": json.loads(bytes(row["envelope_json"]).decode("utf-8")),
            "state": row["state"],
            "attempts": int(row["attempts"]),
            "next_attempt_epoch": float(row["next_attempt_epoch"]),
            "claim_owner": row["claim_owner"],
            "claim_until_epoch": None if row["claim_until_epoch"] is None else float(row["claim_until_epoch"]),
        }

    def due_outbox(self, *, now_epoch: float | None = None, limit: int = 32) -> list[dict[str, Any]]:
        """Read-only diagnostic of currently unclaimed due messages.

        Delivery workers must use claim_due_outbox(), never this method, before publishing.
        """
        now = float(time.time() if now_epoch is None else now_epoch)
        n = max(1, min(int(limit), 256))
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM outbox WHERE state='PENDING' AND next_attempt_epoch<=? ORDER BY created_epoch,message_id LIMIT ?",
                (now, n),
            ).fetchall()
        return [self._row_to_outbox(row) for row in rows]

    def claim_due_outbox(
        self,
        owner_id: str,
        *,
        now_epoch: float | None = None,
        lease_seconds: float = 30.0,
        limit: int = 16,
    ) -> list[dict[str, Any]]:
        owner = _valid_owner(owner_id)
        now = float(time.time() if now_epoch is None else now_epoch)
        lease = float(lease_seconds)
        if lease <= 0 or lease > 900:
            raise ValueError("lease_seconds must be >0 and <=900")
        n = max(1, min(int(limit), 128))
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                "UPDATE outbox SET state='PENDING',claim_owner=NULL,claim_until_epoch=NULL "
                "WHERE state='INFLIGHT' AND claim_until_epoch IS NOT NULL AND claim_until_epoch<=?",
                (now,),
            )
            rows = con.execute(
                "SELECT message_id FROM outbox WHERE state='PENDING' AND next_attempt_epoch<=? ORDER BY created_epoch,message_id LIMIT ?",
                (now, n),
            ).fetchall()
            ids = [str(r["message_id"]) for r in rows]
            until = now + lease
            for mid in ids:
                cur = con.execute(
                    "UPDATE outbox SET state='INFLIGHT',claim_owner=?,claim_until_epoch=? WHERE message_id=? AND state='PENDING'",
                    (owner, until, mid),
                )
                if cur.rowcount != 1:
                    raise OutboxClaimConflict(f"claim race:{mid}")
            claimed: list[sqlite3.Row] = []
            for mid in ids:
                row = con.execute("SELECT * FROM outbox WHERE message_id=?", (mid,)).fetchone()
                assert row is not None
                claimed.append(row)
            con.execute("COMMIT")
            return [self._row_to_outbox(row) for row in claimed]
        except Exception:
            try:
                con.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            con.close()

    def renew_outbox_claim(
        self,
        message_id: str,
        owner_id: str,
        *,
        now_epoch: float | None = None,
        lease_seconds: float = 30.0,
    ) -> None:
        owner = _valid_owner(owner_id)
        now = float(time.time() if now_epoch is None else now_epoch)
        lease = float(lease_seconds)
        if lease <= 0 or lease > 900:
            raise ValueError("lease_seconds must be >0 and <=900")
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT state,claim_owner,claim_until_epoch FROM outbox WHERE message_id=?", (str(message_id),)).fetchone()
            if row is None:
                raise KeyError(message_id)
            if row["state"] != "INFLIGHT" or row["claim_owner"] != owner:
                raise OutboxClaimConflict("claim not owned")
            if row["claim_until_epoch"] is None or float(row["claim_until_epoch"]) < now:
                raise OutboxClaimConflict("claim expired")
            con.execute(
                "UPDATE outbox SET claim_until_epoch=? WHERE message_id=?",
                (now + lease, str(message_id)),
            )
            con.execute("COMMIT")

    def mark_claim_failed(
        self,
        message_id: str,
        owner_id: str,
        error: str,
        *,
        now_epoch: float | None = None,
        max_backoff_seconds: float = 900.0,
    ) -> None:
        owner = _valid_owner(owner_id)
        now = float(time.time() if now_epoch is None else now_epoch)
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT attempts,state,claim_owner,claim_until_epoch FROM outbox WHERE message_id=?",
                (str(message_id),),
            ).fetchone()
            if row is None:
                raise KeyError(message_id)
            if row["state"] == "DELIVERED":
                con.execute("COMMIT")
                return
            if row["state"] != "INFLIGHT" or row["claim_owner"] != owner:
                raise OutboxClaimConflict("claim not owned")
            if row["claim_until_epoch"] is None or float(row["claim_until_epoch"]) < now:
                raise OutboxClaimConflict("claim expired")
            attempts = int(row["attempts"]) + 1
            delay = min(float(max_backoff_seconds), float(2 ** min(attempts, 10)))
            con.execute(
                "UPDATE outbox SET state='PENDING',attempts=?,next_attempt_epoch=?,last_error=?,claim_owner=NULL,claim_until_epoch=NULL WHERE message_id=?",
                (attempts, now + delay, str(error)[:2000], str(message_id)),
            )
            con.execute("COMMIT")
        except Exception:
            try:
                con.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            con.close()

    def mark_claim_delivered(
        self,
        message_id: str,
        owner_id: str,
        *,
        delivered_epoch: float | None = None,
    ) -> None:
        owner = _valid_owner(owner_id)
        now = float(time.time() if delivered_epoch is None else delivered_epoch)
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT state,claim_owner,claim_until_epoch FROM outbox WHERE message_id=?",
                (str(message_id),),
            ).fetchone()
            if row is None:
                raise KeyError(message_id)
            if row["state"] == "DELIVERED":
                con.execute("COMMIT")
                return
            if row["state"] != "INFLIGHT" or row["claim_owner"] != owner:
                raise OutboxClaimConflict("claim not owned")
            if row["claim_until_epoch"] is None or float(row["claim_until_epoch"]) < now:
                raise OutboxClaimConflict("claim expired")
            con.execute(
                "UPDATE outbox SET state='DELIVERED',delivered_epoch=?,last_error=NULL,claim_owner=NULL,claim_until_epoch=NULL WHERE message_id=?",
                (now, str(message_id)),
            )
            con.execute("COMMIT")
        except Exception:
            try:
                con.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            con.close()

    def mark_attempt_failed(
        self,
        message_id: str,
        error: str,
        *,
        now_epoch: float | None = None,
        max_backoff_seconds: float = 900.0,
    ) -> None:
        """Legacy unclaimed failure path; refuses to bypass an active claim."""
        now = float(time.time() if now_epoch is None else now_epoch)
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT attempts,state FROM outbox WHERE message_id=?", (str(message_id),)
            ).fetchone()
            if row is None:
                raise KeyError(message_id)
            if row["state"] == "DELIVERED":
                con.execute("COMMIT")
                return
            if row["state"] == "INFLIGHT":
                raise OutboxClaimConflict("active claim requires mark_claim_failed")
            attempts = int(row["attempts"]) + 1
            delay = min(float(max_backoff_seconds), float(2 ** min(attempts, 10)))
            con.execute(
                "UPDATE outbox SET state='PENDING',attempts=?,next_attempt_epoch=?,last_error=?,claim_owner=NULL,claim_until_epoch=NULL WHERE message_id=?",
                (attempts, now + delay, str(error)[:2000], str(message_id)),
            )
            con.execute("COMMIT")

    def mark_delivered(self, message_id: str, *, delivered_epoch: float | None = None) -> None:
        """Legacy unclaimed delivery path; refuses to bypass an active claim."""
        now = float(time.time() if delivered_epoch is None else delivered_epoch)
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT state FROM outbox WHERE message_id=?", (str(message_id),)).fetchone()
            if row is None:
                raise KeyError(message_id)
            if row["state"] == "INFLIGHT":
                raise OutboxClaimConflict("active claim requires mark_claim_delivered")
            if row["state"] == "DELIVERED":
                con.execute("COMMIT")
                return
            con.execute(
                "UPDATE outbox SET state='DELIVERED',delivered_epoch=?,last_error=NULL,claim_owner=NULL,claim_until_epoch=NULL WHERE message_id=?",
                (now, str(message_id)),
            )
            con.execute("COMMIT")

    def integrity_check(self) -> str:
        with self._connect() as con:
            return str(con.execute("PRAGMA quick_check").fetchone()[0])

    def history(self, stream_id: str) -> list[dict[str, Any]]:
        stream = _valid_stream(stream_id)
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM authority_history WHERE stream_id=? ORDER BY revision",
                (stream,),
            ).fetchall()
        return [
            {
                "revision": int(r["revision"]),
                "fencing_token": int(r["fencing_token"]),
                "content_hash": r["content_hash"],
                "predecessor_hash": r["predecessor_hash"],
            }
            for r in rows
        ]


__all__ = [
    "CriticalStore",
    "CriticalStoreError",
    "DurableReceipt",
    "RevisionConflict",
    "FencingConflict",
    "OutboxClaimConflict",
]
