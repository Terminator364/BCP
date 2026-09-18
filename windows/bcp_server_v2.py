from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from urllib.parse import unquote, urlparse

APP_ROOT = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ChatGPT_ManagedApps" / "bcp"
STATE_DIR = APP_ROOT / "state"
TELEMETRY_DIR = APP_ROOT / "telemetry"
DB_PATH = STATE_DIR / "bcp.sqlite3"
TOKEN_PATH = STATE_DIR / "bcp_token.txt"
PAIR_PATH = STATE_DIR / "paired_edge.json"
SERVER_VERSION = "0.3.0"
DB_LOCK = threading.RLock()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def private_or_loopback(addr: str) -> bool:
    try:
        a = ip_address(addr)
        return bool(a.is_private or a.is_loopback or a.is_link_local)
    except Exception:
        return False


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def atomic_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def ensure_state() -> str:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    if not TOKEN_PATH.exists():
        token = secrets.token_urlsafe(32)
        TOKEN_PATH.write_text(token + "\n", encoding="utf-8")
    else:
        token = TOKEN_PATH.read_text(encoding="utf-8").strip()

    with sqlite3.connect(DB_PATH) as cx:
        cx.execute("PRAGMA journal_mode=WAL")
        cx.execute("PRAGMA synchronous=FULL")
        cx.execute(
            """
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL,
                UNIQUE(project_id,idempotency_key),
                UNIQUE(project_id,revision)
            )
            """
        )
        cx.execute(
            """
            CREATE TABLE IF NOT EXISTS heads(
                project_id TEXT PRIMARY KEY,
                revision INTEGER NOT NULL,
                last_event_id INTEGER NOT NULL,
                last_event_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                last_completed_action TEXT NOT NULL,
                next_action TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cx.commit()
    return token


def connect_db():
    cx = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    cx.row_factory = sqlite3.Row
    return cx


def get_head(project_id: str):
    with connect_db() as cx:
        row = cx.execute("SELECT * FROM heads WHERE project_id=?", (project_id,)).fetchone()
        return dict(row) if row else None


def recent_events(project_id: str, limit: int = 10):
    limit = max(1, min(int(limit), 50))
    with connect_db() as cx:
        rows = cx.execute(
            "SELECT * FROM events WHERE project_id=? ORDER BY revision DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
    out = []
    for row in reversed(rows):
        d = dict(row)
        d["payload"] = json.loads(d.pop("payload_json"))
        out.append(d)
    return out


def commit_event(project_id: str, event_type: str, payload: dict, idem: str):
    if not project_id or len(project_id) > 128:
        raise ValueError("invalid_project_id")
    if not idem or len(idem) > 200:
        raise ValueError("invalid_idempotency_key")

    created = utc_now()
    with DB_LOCK:
        cx = connect_db()
        try:
            cx.execute("BEGIN IMMEDIATE")
            old = cx.execute(
                "SELECT * FROM events WHERE project_id=? AND idempotency_key=?",
                (project_id, idem),
            ).fetchone()
            if old:
                cx.execute("COMMIT")
                return {
                    "result": "ALREADY_COMMITTED",
                    "project_id": project_id,
                    "revision": old["revision"],
                    "event_id": old["id"],
                    "event_hash": old["event_hash"],
                    "created_at": old["created_at"],
                }

            head = cx.execute("SELECT * FROM heads WHERE project_id=?", (project_id,)).fetchone()
            revision = (head["revision"] + 1) if head else 1
            prev_hash = head["last_event_hash"] if head else "GENESIS"
            envelope = {
                "project_id": project_id,
                "revision": revision,
                "event_type": event_type,
                "payload": payload,
                "idempotency_key": idem,
                "created_at": created,
                "prev_hash": prev_hash,
            }
            event_hash = sha256_text(canonical_json(envelope))
            cur = cx.execute(
                """
                INSERT INTO events(
                    project_id,revision,event_type,payload_json,
                    idempotency_key,created_at,prev_hash,event_hash
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    project_id,
                    revision,
                    event_type,
                    canonical_json(payload),
                    idem,
                    created,
                    prev_hash,
                    event_hash,
                ),
            )

            status = payload.get("status", head["status"] if head else "ACTIVE")
            done = payload.get(
                "last_completed_action",
                head["last_completed_action"] if head else "",
            )
            nxt = payload.get("next_action", head["next_action"] if head else "")
            cx.execute(
                """
                INSERT INTO heads(
                    project_id,revision,last_event_id,last_event_hash,
                    status,last_completed_action,next_action,updated_at
                ) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(project_id) DO UPDATE SET
                    revision=excluded.revision,
                    last_event_id=excluded.last_event_id,
                    last_event_hash=excluded.last_event_hash,
                    status=excluded.status,
                    last_completed_action=excluded.last_completed_action,
                    next_action=excluded.next_action,
                    updated_at=excluded.updated_at
                """,
                (
                    project_id,
                    revision,
                    cur.lastrowid,
                    event_hash,
                    status,
                    done,
                    nxt,
                    created,
                ),
            )
            cx.execute("COMMIT")
            return {
                "result": "COMMITTED",
                "project_id": project_id,
                "revision": revision,
                "event_id": cur.lastrowid,
                "event_hash": event_hash,
                "created_at": created,
            }
        except Exception:
            try:
                cx.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            cx.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "BCP/0.3"

    def remote_ip(self):
        return self.client_address[0] if self.client_address else ""

    def send_json(self, status, obj):
        raw = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self):
        n = int(self.headers.get("Content-Length", "0") or "0")
        if n <= 0 or n > 256_000:
            raise ValueError("invalid_body_size")
        obj = json.loads(self.rfile.read(n).decode("utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("json_object_required")
        return obj

    def authorized(self):
        auth = self.headers.get("Authorization", "")
        return auth.startswith("Bearer ") and hmac.compare_digest(
            auth[7:].strip(), self.server.bcp_token
        )

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self.send_json(
                200,
                {
                    "ok": True,
                    "service": "BCP PC Node Windows Native",
                    "version": SERVER_VERSION,
                    "pc_name": os.environ.get("COMPUTERNAME", "BCP-PC"),
                    "pairing_open": True,
                    "time": utc_now(),
                },
            )
            return

        if not self.authorized():
            self.send_json(401, {"error": "unauthorized"})
            return

        if path == "/v1/diagnostics":
            self.send_json(
                200,
                {
                    "ok": True,
                    "version": SERVER_VERSION,
                    "paired": PAIR_PATH.exists(),
                    "pair": read_json(PAIR_PATH, {}),
                    "telemetry_file": str(TELEMETRY_DIR / "phone-events.jsonl"),
                },
            )
            return

        parts = [unquote(x) for x in path.split("/") if x]
        if len(parts) == 4 and parts[:2] == ["v1", "projects"]:
            project = parts[2]
            if parts[3] == "head":
                self.send_json(200, {"project_id": project, "head": get_head(project)})
                return
            if parts[3] == "resume":
                self.send_json(
                    200,
                    {
                        "project_id": project,
                        "head": get_head(project),
                        "recent_events": recent_events(project),
                    },
                )
                return

        self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/pair":
            if not private_or_loopback(self.remote_ip()):
                self.send_json(403, {"error": "pairing_requires_private_lan"})
                return
            try:
                body = self.read_json()
                device_name = str(body.get("device_name", ""))[:120]
                existing = read_json(PAIR_PATH, {}) or {}
                if existing and existing.get("device_name") not in ("", device_name):
                    self.send_json(
                        409,
                        {
                            "error": "paired_to_other_device",
                            "pc_name": os.environ.get("COMPUTERNAME", "BCP-PC"),
                        },
                    )
                    return
                pair = {
                    "paired_at": existing.get("paired_at") or utc_now(),
                    "last_paired_at": utc_now(),
                    "remote_ip": self.remote_ip(),
                    "device_name": device_name,
                    "edge_version": str(body.get("edge_version", ""))[:40],
                    "project": str(body.get("project", "buildhub"))[:128],
                }
                atomic_json(PAIR_PATH, pair)
                self.send_json(
                    200,
                    {
                        "paired": True,
                        "token": self.server.bcp_token,
                        "pc_name": os.environ.get("COMPUTERNAME", "BCP-PC"),
                        "version": SERVER_VERSION,
                    },
                )
            except Exception as e:
                self.send_json(400, {"error": "pairing_failed", "detail": str(e)})
            return

        if not self.authorized():
            self.send_json(401, {"error": "unauthorized"})
            return

        if path == "/v1/telemetry":
            try:
                body = self.read_json()
                events = body.get("events", [])
                if not isinstance(events, list):
                    raise ValueError("events_must_be_list")
                out = TELEMETRY_DIR / "phone-events.jsonl"
                with out.open("a", encoding="utf-8") as f:
                    for e in events[:100]:
                        if isinstance(e, dict):
                            rec = {
                                "received_at": utc_now(),
                                "remote_ip": self.remote_ip(),
                                "event": e,
                            }
                            f.write(canonical_json(rec) + "\n")
                self.send_json(200, {"ok": True, "accepted": min(len(events), 100)})
            except Exception as e:
                self.send_json(400, {"error": "telemetry_failed", "detail": str(e)})
            return

        parts = [unquote(x) for x in path.split("/") if x]
        if len(parts) == 4 and parts[:2] == ["v1", "projects"] and parts[3] == "events":
            try:
                body = self.read_json()
                payload = body.get("payload", {})
                if not isinstance(payload, dict):
                    raise ValueError("payload_must_be_object")
                idem = self.headers.get("Idempotency-Key") or body.get("idempotency_key")
                if not idem:
                    raise ValueError("Idempotency-Key required")
                receipt = commit_event(
                    parts[2],
                    str(body.get("type", "checkpoint")),
                    payload,
                    str(idem),
                )
                self.send_json(200, receipt)
            except Exception as e:
                self.send_json(400, {"error": "bad_request", "detail": str(e)})
            return

        self.send_json(404, {"error": "not_found"})

    def log_message(self, fmt, *args):
        log_dir = APP_ROOT / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "http.log").open("a", encoding="utf-8") as f:
            f.write(f"{utc_now()} {self.remote_ip()} {fmt % args}\n")


def selftest():
    import tempfile

    global APP_ROOT, STATE_DIR, TELEMETRY_DIR, DB_PATH, TOKEN_PATH, PAIR_PATH
    with tempfile.TemporaryDirectory() as td:
        APP_ROOT = Path(td)
        STATE_DIR = APP_ROOT / "state"
        TELEMETRY_DIR = APP_ROOT / "telemetry"
        DB_PATH = STATE_DIR / "bcp.sqlite3"
        TOKEN_PATH = STATE_DIR / "bcp_token.txt"
        PAIR_PATH = STATE_DIR / "paired_edge.json"
        token = ensure_state()
        assert token
        r1 = commit_event(
            "buildhub",
            "checkpoint",
            {
                "status": "ACTIVE",
                "last_completed_action": "A",
                "next_action": "B",
            },
            "same-key",
        )
        r2 = commit_event(
            "buildhub",
            "checkpoint",
            {
                "status": "ACTIVE",
                "last_completed_action": "A",
                "next_action": "B",
            },
            "same-key",
        )
        assert r1["result"] == "COMMITTED"
        assert r2["result"] == "ALREADY_COMMITTED"
        assert get_head("buildhub")["revision"] == 1
    print("BCP_SERVER_SELFTEST=PASS")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        selftest()
        return 0

    token = ensure_state()
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.bcp_token = token
    print(f"[BCP] v{SERVER_VERSION} listening on {args.bind}:{args.port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
