from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

APP_ROOT = Path(os.environ.get(
    "BCP_APP_ROOT",
    str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ChatGPT_ManagedApps" / "bcp"),
))
STATE_DIR = APP_ROOT / "state"
TELEMETRY_DIR = APP_ROOT / "telemetry"
DB_PATH = STATE_DIR / "bcp.sqlite3"
TOKEN_PATH = STATE_DIR / "telegram_bot_token.txt"
CONFIG_PATH = STATE_DIR / "telegram_observability.json"
OFFSET_PATH = STATE_DIR / "telegram_update_offset.json"
PRESENCE_PATH = STATE_DIR / "telegram_presence_state.json"
SYSTEM_PRESENCE_PATH = STATE_DIR / "telegram_system_presence_state.json"
NEXUS_TOKEN_PATH = STATE_DIR / "nexus_device_token.txt"
NEXUS_CURSOR_PATH = STATE_DIR / "nexus_command_cursor.json"
MISSION_EVENT_LOG_PATH = STATE_DIR / "MISSION_EVENT_LOG.jsonl"
LOG_PATH = APP_ROOT / "logs" / "telegram-observability.jsonl"
HEALTH_PATH = STATE_DIR / "telegram_worker_health.json"
MISSION_WATCHDOG_STATE_PATH = STATE_DIR / "mission_watchdog.json"
MISSION_RESUME_REQUEST_PATH = STATE_DIR / "mission_resume_request.json"
MISSION_RESUME_REQUEST_LOG = STATE_DIR / "MISSION_RESUME_REQUESTS.jsonl"
WATCHDOG_NOTIFY_STATE_PATH = STATE_DIR / "telegram_watchdog_notify_state.json"
USER_SEEN_STATE_PATH = STATE_DIR / "telegram_user_seen.json"
NOTIFICATION_POLICY_PATH = STATE_DIR / "telegram_notification_policy.json"
ATTENTION_NOTIFY_STATE_PATH = STATE_DIR / "telegram_attention_notify_state.json"
ATTENTION_ACK_STATE_PATH = STATE_DIR / "telegram_attention_ack.json"
ATTENTION_PENDING_STATE_PATH = STATE_DIR / "telegram_attention_pending.json"
NOTIFICATION_BUDGET_STATE_PATH = STATE_DIR / "telegram_notification_budget.json"

CHAT_STATES = {
    "OBSERVED_CHAT_ACTION",
    "CHAT_WAITING",
    "CHAT_PLATFORM_HOLD_REPORTED",
    "UNKNOWN_INTERNAL_CHAT_STATE",
}
MISSION_STATES = {
    "ACCEPTED", "NORMALIZED", "PLANNED", "QUEUED", "STARTED", "DISPATCHED",
    "WAITING_PROVIDER", "RESULT_RECEIVED", "VALIDATING", "COMMITTED",
    "CHECKPOINTED", "RETRY_SCHEDULED", "BLOCKED", "HOLD", "DONE", "CANCELLED",
}
HOLD_STATES = {
    "WAITING_PROVIDER", "RETRY_SCHEDULED", "BLOCKED", "HOLD",
    "FREE_MODEL_CAPACITY_HOLD", "PROVIDER_PENDING_UNKNOWN", "PROVIDER_TIMEOUT",
    "PLATFORM_VERIFICATION_HOLD", "NETWORK_OFFLINE_QUEUEING",
    "SPEC_CONFLICT_HOLD", "HUMAN_APPROVAL_REQUIRED", "WAITING_FOR_PC",
}
PUSH_STATES = {
    "BLOCKED", "HOLD", "DONE", "CANCELLED",
}
READ_ONLY_COMMANDS = {
    "/start", "/help", "/status", "/details", "/project", "/job", "/last", "/ci", "/holds",
    "/tail", "/where", "/missions", "/objective", "/why", "/since", "/risks", "/ack", "/report", "/reporttech",
}
TOKEN_RE = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{20,}\b")
SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:authorization\s*:\s*)?bearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]\s*['\"]?[^\s,'\"]{8,}"),
)


def redact_text(value: Any) -> str:
    text = str("" if value is None else value)
    text = TOKEN_RE.sub("[REDACTED_TOKEN]", text)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED_SECRET]", text)
    return text


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def clean(value: Any, limit: int = 240) -> str:
    s = redact_text(value)
    return s.replace("\r", " ").replace("\n", " ").strip()[:limit]


def last_jsonl(path: Path, limit: int = 20) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    out: list[dict] = []
    for line in lines[-max(1, min(limit, 200)):]:
        try:
            x = json.loads(line)
            if isinstance(x, dict):
                out.append(x)
        except Exception:
            pass
    return out


def age_seconds(path: Path) -> int | None:
    try:
        return max(0, int(time.time() - path.stat().st_mtime))
    except Exception:
        return None


def event_key(event: dict) -> str:
    raw = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def append_log(event: str, **fields: Any) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOG_PATH.exists() and LOG_PATH.stat().st_size > 2_000_000:
        try:
            os.replace(LOG_PATH, LOG_PATH.with_suffix(".jsonl.1"))
        except Exception:
            pass
    rec = {"ts": utc_now(), "event": clean(event, 80)}
    for key, value in fields.items():
        if "token" in key.lower() or "secret" in key.lower():
            continue
        rec[key] = clean(value, 300) if isinstance(value, str) else value
    with LOG_PATH.open("a", encoding="utf-8") as h:
        h.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")


def write_worker_health(mode: str, state: str, **fields: Any) -> None:
    rec = {
        "schema": "bcp.telegram_worker_health/1",
        "pid": os.getpid(),
        "mode": clean(mode, 40),
        "state": clean(state, 80),
        "updated_at": utc_now(),
    }
    for key, value in fields.items():
        if "token" in key.lower() or "secret" in key.lower():
            continue
        rec[key] = clean(value, 300) if isinstance(value, str) else value
    try:
        atomic_json(HEALTH_PATH, rec)
    except Exception:
        pass


def _pdf_escape(text: str) -> str:
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return text


def _pdf_ascii(text: str) -> str:
    replacements = {
        "—": "-", "–": "-", "→": "->", "←": "<-", "•": "*",
        "✅": "[OK]", "⚠️": "[!]", "⚠": "[!]", "🟢": "[OK]", "🟡": "[~]", "🟠": "[~]",
        "🔴": "[X]", "⚪": "[ ]", "🤖": "BCP", "🎯": "NOW", "📊": "PROGRESS",
        "➡️": "NEXT", "➡": "NEXT", "👤": "YOU", "🕒": "TIME", "⏱️": "AGE",
        "📨": "SENT", "🌐": "NEXUS", "🧪": "TESTS", "🔧": "DETAILS", "ℹ️": "INFO",
        "💾": "CHECKPOINT", "🏁": "DONE", "📌": "MISSION", "🧭": "PLAN",
        "▶️": "START", "📤": "DISPATCH", "📥": "RESULT", "🔎": "VERIFY",
        "🔁": "RETRY", "🛑": "BLOCKED", "⏹️": "STOP",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("cp1252", errors="replace").decode("cp1252")


def text_pdf_bytes(title: str, body: str) -> bytes:
    # Tiny dependency-free PDF for low-data status exports.
    lines: list[str] = []
    for raw in (title + "\n\n" + body).splitlines():
        raw = _pdf_ascii(raw)
        if not raw:
            lines.append("")
            continue
        while len(raw) > 92:
            cut = raw.rfind(" ", 0, 92)
            if cut < 24:
                cut = 92
            lines.append(raw[:cut].rstrip())
            raw = raw[cut:].lstrip()
        lines.append(raw)
    per_page = 46
    pages = [lines[i:i + per_page] for i in range(0, max(1, len(lines)), per_page)] or [[]]

    objects: list[bytes] = []
    # 1 Catalog, 2 Pages, 3 Helvetica font.
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_refs: list[int] = []
    next_obj = 4
    for page_lines in pages:
        page_obj = next_obj
        stream_obj = next_obj + 1
        next_obj += 2
        page_refs.append(page_obj)
        content = ["BT", "/F1 10 Tf", "48 790 Td", "12 TL"]
        for idx, line in enumerate(page_lines):
            if idx:
                content.append("T*")
            content.append("(" + _pdf_escape(line) + ") Tj")
        content.append("ET")
        stream = "\n".join(content).encode("cp1252", errors="replace")
        objects.append(
            ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
             "/Resources << /Font << /F1 3 0 R >> >> /Contents " +
             str(stream_obj) + " 0 R >>").encode("ascii")
        )
        objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
    kids = " ".join(str(x) + " 0 R" for x in page_refs)
    objects[1] = ("<< /Type /Pages /Kids [" + kids + "] /Count " + str(len(page_refs)) + " >>").encode("ascii")

    out = bytearray(b"%PDF-1.4\n%BCP\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(str(i).encode("ascii") + b" 0 obj\n" + obj + b"\nendobj\n")
    xref = len(out)
    out.extend(("xref\n0 " + str(len(objects) + 1) + "\n").encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        ("trailer\n<< /Size " + str(len(objects) + 1) + " /Root 1 0 R >>\n"
         "startxref\n" + str(xref) + "\n%%EOF\n").encode("ascii")
    )
    return bytes(out)


class Http:
    def json(self, url: str, method: str = "GET", payload: dict | None = None,
             headers: dict | None = None, timeout: int = 20) -> tuple[int, Any]:
        body = None
        hdr = {"User-Agent": "BCP-Telegram-Observability/1"}
        if headers:
            hdr.update(headers)
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            hdr["Content-Type"] = "application/json"
        req = Request(url, data=body, headers=hdr, method=method)
        try:
            with urlopen(req, timeout=timeout) as res:
                raw = res.read()
                return int(res.status), json.loads(raw.decode("utf-8")) if raw else {}
        except HTTPError as e:
            raw = e.read()
            try:
                obj = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception:
                obj = {"description": clean(raw.decode("utf-8", errors="replace"))}
            return int(e.code), obj


class GitHubReader:
    def __init__(self, repo: str, http: Http | None = None):
        self.repo = repo
        self.http = http or Http()
        self.cache: dict | None = None
        self.cache_at = 0.0

    def _get(self, suffix: str) -> Any:
        status, obj = self.http.json(
            "https://api.github.com/repos/" + self.repo + suffix,
            headers={"Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"},
        )
        if status != 200:
            raise RuntimeError("github_http_" + str(status))
        return obj

    def snapshot(self, force: bool = False) -> dict:
        if not force and self.cache and time.time() - self.cache_at < 180:
            return dict(self.cache, cache="FRESH_CACHE")
        try:
            runs = self._get("/actions/runs?per_page=8")
            prs = self._get("/pulls?state=open&per_page=10")
            commits = self._get("/commits?per_page=5")
            if not isinstance(runs, dict) or not isinstance(prs, list) or not isinstance(commits, list):
                raise RuntimeError("github_shape_invalid")
            snap = {
                "ok": True,
                "repo": self.repo,
                "runs": list(runs.get("workflow_runs") or []),
                "pulls": prs,
                "commits": commits,
                "observed_at": utc_now(),
                "cache": "LIVE",
            }
            self.cache, self.cache_at = snap, time.time()
            return snap
        except Exception as e:
            if self.cache:
                return dict(self.cache, ok=False, cache="STALE_CACHE", error=clean(e))
            return {"ok": False, "repo": self.repo, "runs": [], "pulls": [],
                    "commits": [], "cache": "NONE", "error": clean(e)}


class LocalTruth:
    def __init__(self, root: Path = APP_ROOT):
        self.root = root
        self.state = root / "state"
        self.telemetry = root / "telemetry"
        self.db = self.state / "bcp.sqlite3"

    def _query(self, sql: str, args: tuple = ()) -> list[dict]:
        if not self.db.is_file():
            return []
        cx = None
        try:
            cx = sqlite3.connect("file:" + self.db.as_posix() + "?mode=ro", uri=True, timeout=2)
            cx.row_factory = sqlite3.Row
            return [dict(x) for x in cx.execute(sql, args).fetchall()]
        except Exception:
            return []
        finally:
            if cx is not None:
                try:
                    cx.close()
                except Exception:
                    pass

    def head(self, project: str) -> dict | None:
        rows = self._query("SELECT * FROM heads WHERE project_id=?", (project,))
        return rows[0] if rows else None

    def events(self, project: str, limit: int = 8) -> list[dict]:
        rows = self._query(
            "SELECT revision,event_type,payload_json,created_at,event_hash "
            "FROM events WHERE project_id=? ORDER BY revision DESC LIMIT ?",
            (project, max(1, min(limit, 30))),
        )
        for row in rows:
            try:
                row["payload"] = json.loads(row.pop("payload_json"))
            except Exception:
                row["payload"] = {}
        return rows

    def jobs(self, project: str, limit: int = 30) -> list[dict]:
        return self._query(
            "SELECT id,project_id,kind,state,created_at,updated_at "
            "FROM jobs WHERE project_id=? ORDER BY id DESC LIMIT ?",
            (project, max(1, min(limit, 50))),
        )

    def runtime(self) -> dict:
        candidates = []
        override = os.environ.get("BCP_EXTERNAL_TELEMETRY_DIR", "").strip()
        if override:
            candidates.append(Path(override) / "BCP_RUNTIME_LATEST.json")
        home = Path.home()
        candidates += [
            Path(r"G:\Mon Drive\API_BCP\02_TELEMETRY\BCP\BCP_RUNTIME_LATEST.json"),
            Path(r"G:\My Drive\API_BCP\02_TELEMETRY\BCP\BCP_RUNTIME_LATEST.json"),
            home / "Mon Drive" / "API_BCP" / "02_TELEMETRY" / "BCP" / "BCP_RUNTIME_LATEST.json",
            home / "My Drive" / "API_BCP" / "02_TELEMETRY" / "BCP" / "BCP_RUNTIME_LATEST.json",
            self.telemetry / "BCP_RUNTIME_LATEST.json",
        ]
        for p in candidates:
            obj = read_json(p, None)
            if isinstance(obj, dict):
                return dict(obj, _age_seconds=age_seconds(p))
        return {"status": "NOT_OBSERVED", "_age_seconds": None}

    def edge(self) -> dict:
        pair = read_json(self.state / "paired_edge.json", {}) or {}
        event_path = self.telemetry / "phone-events.jsonl"
        evs = last_jsonl(event_path, 5)
        last = evs[-1] if evs else {}
        return {
            "paired": bool(pair),
            "edge_version": clean(pair.get("edge_version"), 40),
            "last_event": clean(last.get("event_type") or last.get("type"), 80),
            "_age_seconds": age_seconds(event_path),
        }

    def mission_events(self, limit: int = 80) -> list[dict]:
        path = self.state / MISSION_EVENT_LOG_PATH.name
        return [
            x for x in last_jsonl(path, limit)
            if str(x.get("state") or "").upper() in MISSION_STATES
        ]

    def mission_activity_age(self) -> int | None:
        return age_seconds(self.state / MISSION_EVENT_LOG_PATH.name)

    def mission_snapshot(self, project: str) -> dict | None:
        rows = self._query(
            "SELECT mission_id,project_id,current_step,last_committed_step,next_step,"
            "last_progress_at,worker_component,receipt_evidence,status,hold_reason,"
            "plan_json,created_at,updated_at FROM missions "
            "WHERE project_id=? ORDER BY updated_at DESC LIMIT 1",
            (project,),
        )
        if not rows and project == "API/BCP":
            rows = self._query(
                "SELECT mission_id,project_id,current_step,last_committed_step,next_step,"
                "last_progress_at,worker_component,receipt_evidence,status,hold_reason,"
                "plan_json,created_at,updated_at FROM missions "
                "WHERE project_id IN ('API','BCP') ORDER BY updated_at DESC LIMIT 1"
            )
        if not rows:
            return None
        out = dict(rows[0])
        try:
            plan = json.loads(out.pop("plan_json") or "[]")
            out["plan"] = plan if isinstance(plan, list) else []
        except Exception:
            out["plan"] = []
        return out

    def mission_event_tail(self, mission_id: str, limit: int = 12) -> list[dict]:
        rows = self._query(
            "SELECT seq,event_type,step_id,worker_component,summary,evidence_ref,status,"
            "failure_hold_reason,created_at FROM mission_events "
            "WHERE mission_id=? ORDER BY seq DESC LIMIT ?",
            (mission_id, max(1, min(limit, 30))),
        )
        return list(reversed(rows))

    def buildhub(self) -> dict:
        raw = os.environ.get("BCP_BUILDHUB_RECEIPT", "").strip()
        if raw:
            obj = read_json(Path(raw), None)
            if isinstance(obj, dict):
                return {"status": clean(obj.get("status") or obj.get("state") or "OBSERVED", 80)}
        return {"status": "NOT_OBSERVED"}

    def drive(self) -> dict:
        home = Path.home()
        candidates = [
            Path(r"G:\Mon Drive\API_BCP\02_TELEMETRY\BCP\BCP_RUNTIME_LATEST.json"),
            Path(r"G:\My Drive\API_BCP\02_TELEMETRY\BCP\BCP_RUNTIME_LATEST.json"),
            home / "Mon Drive" / "API_BCP" / "02_TELEMETRY" / "BCP" / "BCP_RUNTIME_LATEST.json",
            home / "My Drive" / "API_BCP" / "02_TELEMETRY" / "BCP" / "BCP_RUNTIME_LATEST.json",
        ]
        existing = [p for p in candidates if p.is_file()]
        if not existing:
            return {"status": "NOT_OBSERVED"}
        p = max(existing, key=lambda x: x.stat().st_mtime)
        return {"status": "OBSERVED", "age_seconds": age_seconds(p)}

    def broker(self) -> dict:
        obj = read_json(self.state / "model_broker_state.json", {}) or {}
        try:
            spend = float(obj.get("spend_usd") or 0.0)
        except Exception:
            spend = 0.0
        return {"state": clean(obj.get("state") or "NOT_OBSERVED", 80), "spend_usd": spend}

    def chat(self, project: str) -> dict:
        obj = read_json(self.state / "chat_observability.json", {}) or {}
        state = str(obj.get("state") or "").upper()
        if state in CHAT_STATES:
            return {"state": state, "evidence": clean(obj.get("evidence"), 120)}
        for ev in self.events(project, 12):
            payload = ev.get("payload") or {}
            state = str(payload.get("chat_state") or "").upper()
            if state in CHAT_STATES:
                return {"state": state, "evidence": "BCP event r" + str(ev.get("revision"))}
            et = str(ev.get("event_type") or "").upper()
            if "CHATGPT" in et or et.startswith("CHAT_"):
                return {"state": "OBSERVED_CHAT_ACTION", "evidence": "BCP event " + et}
        return {"state": "UNKNOWN_INTERNAL_CHAT_STATE",
                "evidence": "no supported external ChatGPT telemetry"}

    def find_job(self, code: str) -> dict | None:
        if not re.fullmatch(r"\d{4,12}", code.strip()):
            return None
        for ev in reversed(self.mission_events(200)):
            if str(ev.get("job_code") or "") == code:
                return ev
        try:
            rows = self._query(
                "SELECT id,project_id,kind,state,created_at,updated_at FROM jobs WHERE id=?",
                (int(code),),
            )
            return rows[0] if rows else None
        except Exception:
            return None


class Service:
    def __init__(self, config: dict, local: LocalTruth | None = None,
                 github: GitHubReader | None = None):
        self.cfg = config
        self.project_id = str(config.get("default_project") or "API/BCP")
        self.local = local or LocalTruth()
        self.github = github or GitHubReader(str(config.get("github_repo") or "Terminator364/BCP"))

    def _head(self, project: str | None = None) -> dict | None:
        pid = project or self.project_id
        return self.local.head(pid) or self.local.head("API") or self.local.head("BCP")

    def _ci(self, gh: dict) -> str:
        runs = gh.get("runs") or []
        if not runs:
            return "NOT_OBSERVED (" + str(gh.get("cache") or "NONE") + ")"
        r = runs[0]
        state = clean(r.get("conclusion") or r.get("status") or "unknown", 30).upper()
        name = clean(r.get("name") or "workflow", 65)
        branch = clean(r.get("head_branch"), 65)
        return name + "=" + state + ((" [" + branch + "]") if branch else "")

    @staticmethod
    def _bar(done: int, total: int, width: int = 10) -> str:
        if total <= 0:
            return "░" * width
        filled = max(0, min(width, round(width * done / total)))
        return ("█" * filled) + ("░" * (width - filled))

    @staticmethod
    def _event_timestamp(ev: dict) -> str:
        return clean(
            ev.get("observed_at") or ev.get("timestamp") or ev.get("updated_at") or
            ev.get("created_at") or ev.get("ts") or "",
            64,
        )

    @staticmethod
    def _event_age_seconds(ev: dict) -> int | None:
        raw = Service._event_timestamp(ev)
        if not raw:
            return None
        try:
            parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return max(0, int((dt.datetime.now(dt.timezone.utc) - parsed.astimezone(dt.timezone.utc)).total_seconds()))
        except Exception:
            return None

    @staticmethod
    def _age_label(seconds: int | None) -> str:
        if not isinstance(seconds, int):
            return "inconnue"
        if seconds < 60:
            return str(seconds) + " s"
        if seconds < 3600:
            return str(seconds // 60) + " min"
        return str(seconds // 3600) + " h " + str((seconds % 3600) // 60) + " min"

    def _mission_context(self) -> dict | None:
        mission = self.local.mission_snapshot(self.project_id)
        if not mission:
            return None
        plan = mission.get("plan") or []
        label_by_id: dict[str, str] = {}
        verified = 0
        for pos, step in enumerate(plan, 1):
            if not isinstance(step, dict):
                continue
            sid = clean(step.get("id") or ("step-" + str(pos)), 80)
            label = clean(step.get("label") or sid, 180)
            if sid:
                label_by_id[sid] = label
            state = str(step.get("state") or "").upper()
            if bool(step.get("verified")) or state in {"VERIFIED", "DONE", "COMMITTED", "CHECKPOINTED", "SUCCESS", "COMPLETED"}:
                verified += 1
        current_id = clean(mission.get("current_step"), 80)
        last_id = clean(mission.get("last_committed_step"), 80)
        next_id = clean(mission.get("next_step"), 80)
        total = len([x for x in plan if isinstance(x, dict)])
        progress = ""
        if total > 0:
            pct = int(round(verified * 100 / total))
            progress = self._bar(verified, total) + " " + str(pct) + "% — " + str(verified) + "/" + str(total) + " micro-actions vérifiées"
        return {
            "mission": mission,
            "plan": plan,
            "current": label_by_id.get(current_id, current_id) or "Aucune micro-action active observée.",
            "last": label_by_id.get(last_id, last_id) or "Aucune micro-action terminée récente observée.",
            "next": label_by_id.get(next_id, next_id) or "Relire l’état sauvegardé avant de reprendre.",
            "progress": progress,
            "verified": verified,
            "total": total,
            "label_by_id": label_by_id,
        }

    def plan_view(self) -> str:
        ctx = self._mission_context()
        if not ctx:
            return "PLAN DE MICRO-ACTIONS\nAucun plan fini et durable observé."
        plan = ctx.get("plan") or []
        lines = ["🧭 Plan de micro-actions"]
        if ctx.get("progress"):
            lines.append("📊 " + str(ctx["progress"]))
        for pos, step in enumerate(plan, 1):
            if not isinstance(step, dict):
                continue
            state = str(step.get("state") or "PENDING").upper()
            verified = bool(step.get("verified")) or state in {"VERIFIED", "DONE", "COMMITTED", "CHECKPOINTED", "SUCCESS", "COMPLETED"}
            icon = "✅" if verified else ("▶️" if clean(step.get("id"), 80) == clean((ctx["mission"] or {}).get("current_step"), 80) else "⬜")
            label = clean(step.get("label") or step.get("id") or ("Étape " + str(pos)), 180)
            lines.append(str(pos) + ". " + icon + " " + label)
        return "\n".join(lines)

    @staticmethod
    def _last_completed_action(events: list[dict], current: dict) -> str:
        completed = {"COMMITTED", "CHECKPOINTED", "DONE"}
        for item in reversed(events):
            if item is current:
                continue
            if str(item.get("state") or "").upper() in completed:
                return clean(
                    item.get("action_summary") or item.get("step_summary") or item.get("step_id") or
                    "Étape terminée.",
                    150,
                )
        return "Aucune étape terminée récente observée."

    @staticmethod
    def _human_gate(ev: dict, next_action: str) -> str:
        raw = ev.get("human_action_required")
        required = raw is True or str(raw or "").strip().lower() in {"1", "true", "yes", "required", "requise"}
        state = str(ev.get("state") or "").upper()
        if state == "HUMAN_APPROVAL_REQUIRED":
            required = True
        instruction = clean(
            ev.get("human_instruction") or ev.get("human_action") or
            (next_action if required else ""),
            180,
        )
        if required:
            return "REQUISE" + ((" — " + instruction) if instruction else "")
        optional = str(raw or "").strip().lower() in {"optional", "optionnelle"}
        if optional:
            return "OPTIONNELLE" + ((" — " + instruction) if instruction else "")
        return "AUCUNE"

    @staticmethod
    def _human_action(value: Any) -> str:
        raw = clean(value, 220)
        if not raw or raw == "NOT_OBSERVED":
            return "Relire l’état sauvegardé puis reprendre à la prochaine étape prouvée."
        low = raw.lower()
        if "read durable evidence" in low or "do not replay committed work" in low:
            return "Relire les preuves sauvegardées puis continuer sans refaire ce qui est déjà terminé."
        if "telegram" in low and ("progress" in low or "presence" in low):
            return "Vérifier que Telegram reçoit automatiquement les changements d’étape."
        if "nexus" in low:
            return "Finaliser le relais Nexus pour que le PC ne dépende plus d’un accès direct à Telegram."
        if "chatgpt-pc" in low or "heartbeat" in low or "cycle_lease" in low:
            return "Réparer la preuve de présence de ChatGPT-PC sans réinstaller BCP."
        if "apk" in low or "signing" in low:
            return "Vérifier l’identité de l’application B-EDGE déjà installée sur l’ancien téléphone."
        if "field" in low and ("edge" in low or "bcp" in low):
            return "Terminer la vérification réelle entre le PC et l’ancien téléphone."
        return raw.replace("_", " ").replace("->", "→")

    def _human_ci(self, gh: dict) -> str:
        runs = gh.get("runs") or []
        if not runs:
            return "⚪ tests non observés"
        r = runs[0]
        state = str(r.get("conclusion") or r.get("status") or "unknown").lower()
        labels = {
            "success": "✅ tests réussis",
            "completed": "✅ tests terminés",
            "in_progress": "🔄 tests en cours",
            "queued": "⏳ tests en attente",
            "requested": "⏳ tests demandés",
            "failure": "🔴 tests à corriger",
            "cancelled": "🟠 tests interrompus",
        }
        name = clean(r.get("name") or "qualification", 60)
        return labels.get(state, "⚪ tests: " + clean(state, 30)) + " — " + name

    @staticmethod
    def _micro_weight(label: str) -> int:
        """Deterministic forecast weight for a high-level step. This is an estimate, never proof."""
        low = clean(label, 220).lower()
        weight = 4
        if any(x in low for x in ("pdf", "fichier", "file", "read", "lire", "ouvrir", "inspect", "vérifier", "verify", "hash", "log")):
            weight += 2
        if any(x in low for x in ("modifier", "patch", "corriger", "fix", "code", "implément", "update", "mise à jour")):
            weight += 4
        if any(x in low for x in ("workflow", "ci", "build", "test", "qualification", "android", "windows")):
            weight += 5
        if any(x in low for x in ("release", "publier", "merge", "déployer", "deploy", "terrain", "field", "readback", "télémétr")):
            weight += 5
        return max(2, min(24, weight))

    def _micro_forecast(self, ctx: dict | None, events: list[dict], gh: dict) -> dict:
        """Estimate fine-grained micro-actions from persisted work. Explicitly approximate."""
        runs = gh.get("runs") or []
        if ctx and (ctx.get("plan") or []):
            plan = [x for x in (ctx.get("plan") or []) if isinstance(x, dict)]
            total = 0
            done = 0
            current_id = clean(((ctx.get("mission") or {}).get("current_step")), 80)
            for pos, step in enumerate(plan, 1):
                label = clean(step.get("label") or step.get("id") or ("Étape " + str(pos)), 180)
                weight = self._micro_weight(label)
                total += weight
                state = str(step.get("state") or "").upper()
                verified = bool(step.get("verified")) or state in {
                    "VERIFIED", "DONE", "COMMITTED", "CHECKPOINTED", "SUCCESS", "COMPLETED"
                }
                if verified:
                    done += weight
                elif clean(step.get("id"), 80) == current_id:
                    done += max(1, weight // 3)
            total = max(total, 12)
        else:
            observed_events = min(40, len(events))
            completed_events = sum(
                1 for e in events
                if str(e.get("state") or "").upper() in {"COMMITTED", "CHECKPOINTED", "DONE", "RESULT_RECEIVED", "VALIDATING"}
            )
            run_count = min(8, len(runs))
            completed_runs = sum(
                1 for r in runs
                if str(r.get("conclusion") or "").lower() == "success"
            )
            # Medium BCP engineering work generally spans dozens of atomic reads,
            # edits, checks, commits and readbacks. Forecast expands as evidence appears.
            total = max(32, min(1000, 32 + observed_events * 2 + run_count * 6))
            done = min(total - 1, completed_events * 2 + completed_runs * 4 + min(observed_events, 12))
        pct = max(0, min(100, int(round(done * 100 / max(1, total)))))
        return {
            "done": int(done),
            "total": int(total),
            "pct": pct,
            "bar": self._bar(done, total, 12),
            "approximate": True,
        }

    @staticmethod
    def _forecast_micro_labels(action: str) -> list[str]:
        low = clean(action, 220).lower()
        labels = [
            "Lire les preuves et fichiers utiles",
            "Identifier le prochain changement atomique",
        ]
        if any(x in low for x in ("pdf", "fichier", "file", "doc", "rapport")):
            labels += ["Ouvrir/lire le document ciblé", "Vérifier les données extraites"]
        if any(x in low for x in ("workflow", "ci", "test", "build", "qualification")):
            labels += ["Vérifier le workflow ciblé", "Lancer le test", "Lire le résultat et les logs"]
        if any(x in low for x in ("corrig", "patch", "modifier", "update", "mise à jour", "code")):
            labels += ["Appliquer la modification ciblée", "Vérifier syntaxe et cohérence"]
        if any(x in low for x in ("release", "merge", "publ", "déploi", "deploy")):
            labels += ["Aligner versions et hashes", "Vérifier les contrats de release", "Intégrer après PASS"]
        labels += ["Sauvegarder un checkpoint durable", "Effectuer le readback de confirmation"]
        out = []
        for item in labels:
            if item not in out:
                out.append(item)
        return out[:10]

    @staticmethod
    def _human_ci_explanation(gh: dict) -> str:
        runs = gh.get("runs") or []
        if not runs:
            return "Aucun test GitHub récent disponible."
        r = runs[0]
        name = str(r.get("name") or "tests")
        state = str(r.get("conclusion") or r.get("status") or "unknown").lower()
        state_text = {
            "success": "terminés avec succès",
            "in_progress": "en cours",
            "queued": "en attente de démarrage",
            "failure": "en échec — correction nécessaire",
            "cancelled": "interrompus",
        }.get(state, "état " + clean(state, 30))
        low = name.lower()
        if "coordinated product" in low:
            purpose = "vérifie que PC, B-EDGE, versions et contrats restent compatibles ensemble"
        elif "field ecosystem" in low:
            purpose = "reproduit les contraintes réelles Windows/RAM/réseau et le runtime Nexus avant le terrain"
        elif "telegram" in low:
            purpose = "vérifie le cockpit Telegram, ses boutons et ses garde-fous"
        elif "nexus" in low:
            purpose = "vérifie le relais Nexus utilisé quand le PC ne joint pas directement Telegram"
        elif "current release" in low:
            purpose = "vérifie que la version publiée est cohérente, signée par ses hashes et auto-mise-à-jour"
        else:
            purpose = "vérifie automatiquement la prochaine version avant déploiement"
        return "Tests " + state_text + " : " + purpose + "."

    @staticmethod
    def _nexus_progress(state: str) -> tuple[int, str]:
        s = str(state or "").upper()
        table = {
            "NONE": (5, "Relais Internet pas encore préparé"),
            "NOT_OBSERVED": (5, "Relais Internet pas encore observé"),
            "WRANGLER_RUNTIME_REQUIRED": (70, "Préparation du moteur Nexus sur le PC"),
            "RUNTIME_PROBE_FAILED": (70, "Préparation Nexus à corriger"),
            "LAUNCHED": (82, "Démarrage et vérification du relais Nexus"),
            "HUMAN_AUTH_REQUIRED": (90, "Autorisation fournisseur requise"),
            "COMMITTED": (100, "Relais Nexus opérationnel"),
            "NEXUS_DEPLOYED_LOCAL_WORKER_RUNNING": (100, "Relais Nexus opérationnel"),
        }
        return table.get(s, (50, "Préparation du relais Nexus"))

    def _ecosystem_health(self, heartbeat_ok: bool, edge_ok: bool, edge_paired: bool,
                          drive_ok: bool, ci_state: str, nexus_state: str) -> tuple[int, str]:
        score = 0
        score += 28 if heartbeat_ok else 0
        score += 18 if edge_ok else (10 if edge_paired else 0)
        score += 14 if drive_ok else 0
        score += 20 if ci_state == "success" else (10 if ci_state in {"in_progress", "queued"} else 0)
        score += 20 if nexus_state in {"COMMITTED", "NEXUS_DEPLOYED_LOCAL_WORKER_RUNNING"} else (
            12 if nexus_state in {"LAUNCHED", "HUMAN_AUTH_REQUIRED", "WRANGLER_RUNTIME_REQUIRED"} else 4
        )
        score = max(0, min(100, score))
        return score, self._bar(score, 100, 12)

    def presence_snapshot(self) -> dict:
        runtime = self.local.runtime()
        edge = self.local.edge()
        gh = self.github.snapshot()
        drive = self.local.drive()
        events = [
            e for e in self.local.mission_events(160)
            if not e.get("project_id") or str(e.get("project_id")) == self.project_id
        ]
        ev = events[-1] if events else {}
        ctx = self._mission_context()
        mission = (ctx or {}).get("mission") or {}
        mission_state = str(mission.get("status") or ev.get("state") or "UNKNOWN").upper()

        if ctx:
            plan_for_objective = ctx.get("plan") or []
            objective = clean(
                mission.get("objective") or mission.get("title") or
                ((plan_for_objective[0].get("label") if isinstance(plan_for_objective[0], dict) else "") if plan_for_objective else "") or
                "Faire avancer la mission API/BCP",
                180,
            )
            action = clean(ctx.get("current") or "Analyse de la prochaine action vérifiable.", 180)
            next_action = self._human_action(ctx.get("next"))
            last_completed = clean(ctx.get("last") or "Point de reprise durable conservé.", 180)
            age = self._event_age_seconds({"updated_at": mission.get("last_progress_at") or mission.get("updated_at")})
            evidence_time = clean(mission.get("last_progress_at") or mission.get("updated_at") or "", 64)
        else:
            objective = clean(
                ev.get("mission_objective") or ev.get("objective") or
                ev.get("job_title") or "Faire avancer la mission API/BCP en cours.",
                180,
            )
            action = clean(
                ev.get("action_summary") or ev.get("step_summary") or ev.get("step_id") or
                "Reconstitution automatique de l’activité à partir des preuves disponibles.",
                180,
            )
            next_action = self._human_action(ev.get("next_safe_action") or "")
            last_completed = self._last_completed_action(events, ev)
            age = self._event_age_seconds(ev)
            evidence_time = self._event_timestamp(ev)

        if age is None:
            age = self.local.mission_activity_age()
        age_label = self._age_label(age)

        forecast = self._micro_forecast(ctx, events, gh)
        hb = runtime.get("_age_seconds")
        heartbeat_ok = isinstance(hb, int) and hb <= 180
        edge_age = edge.get("_age_seconds")
        edge_ok = bool(edge.get("paired")) and isinstance(edge_age, int) and edge_age <= 300
        edge_paired = bool(edge.get("paired"))
        drive_ok = str(drive.get("status") or "").upper() == "OBSERVED"
        runs = gh.get("runs") or []
        run = runs[0] if runs else {}
        ci_state = clean(run.get("conclusion") or run.get("status"), 30).lower()
        nexus = str(runtime.get("nexus_bootstrap_state") or "NOT_OBSERVED").upper()
        nexus_pct, nexus_stage = self._nexus_progress(nexus)
        health_pct, health_bar = self._ecosystem_health(
            heartbeat_ok, edge_ok, edge_paired, drive_ok, ci_state, nexus
        )

        hold_reason = clean(mission.get("hold_reason") or ev.get("failure_hold_reason"), 120)
        if mission_state in HOLD_STATES or hold_reason:
            activity = "🟠 En attente : " + (hold_reason.replace("_", " ").lower() if hold_reason else "un blocage identifié doit être levé.")
        elif isinstance(age, int) and age < 120:
            activity = "🟢 Travail actif — nouvelle preuve reçue il y a " + age_label + "."
        elif isinstance(age, int) and age < 900:
            activity = "🔵 Travail en cours / attente normale — dernière preuve il y a " + age_label + "."
        elif isinstance(age, int):
            activity = "🟡 Travail sans nouvelle preuve depuis " + age_label + " — le suivi automatique continue."
        else:
            activity = "🔵 Suivi automatique actif — synchronisation des preuves en cours."

        battery_pct = runtime.get("pc_battery_percent")
        battery_critical = bool(runtime.get("pc_battery_critical"))
        power_source = str(runtime.get("pc_power_source") or "UNKNOWN").upper()
        mem_pct = runtime.get("pc_memory_load_percent")
        pc_suffix = []
        if power_source == "AC":
            pc_suffix.append("secteur")
        elif power_source == "BATTERY":
            pc_suffix.append("batterie")
        if isinstance(battery_pct, int):
            pc_suffix.append(str(battery_pct) + "%")
        if isinstance(mem_pct, int):
            pc_suffix.append("RAM " + str(mem_pct) + "%")
        suffix = (" · " + " · ".join(pc_suffix)) if pc_suffix else ""
        if battery_critical:
            pc_text = "🔴 PC : allumé mais batterie critique" + suffix
        elif heartbeat_ok:
            pc_text = "🟢 PC : allumé · BCP en vie" + suffix
        elif isinstance(hb, int) and hb <= 600:
            pc_text = "🟡 PC : probablement allumé · télémétrie retardée" + suffix
        else:
            pc_text = "🔴 PC : non joignable récemment" + suffix

        if edge_ok:
            edge_text = "🟢 Ancien téléphone : serveur B-EDGE actif"
        elif edge_paired:
            edge_text = "🔵 Ancien téléphone : serveur appairé · veille normale"
        else:
            edge_text = "🔴 Ancien téléphone : serveur non appairé"

        human_gate = self._human_gate(ev, next_action)
        forecast_confidence, forecast_confidence_reason = self._forecast_confidence(ctx, events, gh)
        telegram_state = str(runtime.get("telegram_companion_state") or "").upper()
        attention_reasons = []
        if human_gate != "AUCUNE":
            attention_reasons.append("Une intervention humaine est explicitement requise par la mission.")
        if nexus == "HUMAN_AUTH_REQUIRED":
            attention_reasons.append("Nexus est prêt mais attend l’autorisation Cloudflare dans le navigateur du PC.")
        if battery_critical:
            attention_reasons.append("La batterie du PC est critique.")
        if not heartbeat_ok and isinstance(hb, int) and hb > 600:
            attention_reasons.append("Le PC/BCP n’a pas fourni de heartbeat récent.")
        if mission_state in HOLD_STATES or hold_reason:
            attention_reasons.append("La mission est en attente sur un blocage identifié.")
        if isinstance(age, int) and age >= 900:
            attention_reasons.append("Aucune nouvelle preuve de progression depuis " + age_label + ".")
        if telegram_state in {"DEGRADED_RETRY", "HOLD"} and nexus not in {"COMMITTED", "NEXUS_DEPLOYED_LOCAL_WORKER_RUNNING"}:
            attention_reasons.append("Le canal Telegram direct est dégradé et le relais Nexus n’est pas encore totalement opérationnel.")

        if battery_critical or (not heartbeat_ok and isinstance(hb, int) and hb > 600):
            attention_level = "CRITICAL"
        elif human_gate != "AUCUNE" or nexus == "HUMAN_AUTH_REQUIRED":
            attention_level = "ACTION"
        elif mission_state in HOLD_STATES or hold_reason or (isinstance(age, int) and age >= 900):
            attention_level = "WATCH"
        elif isinstance(age, int) and age < 900 and mission_state not in {"DONE", "CANCELLED"}:
            attention_level = "ACTIVE"
        else:
            attention_level = "NORMAL"

        chat_state = self.local.chat(self.project_id).get("state")
        ci_active = ci_state in {"in_progress", "queued", "requested"}
        if chat_state == "CHAT_PLATFORM_HOLD_REPORTED":
            execution_text = "🟠 Exécution : interruption plateforme signalée · reprise depuis le dernier checkpoint"
        elif ci_active:
            execution_text = "🔄 Exécution : travail distant encore actif (tests/qualification)"
        elif isinstance(age, int) and age >= 900:
            execution_text = "⏸️ Exécution : pause apparente · aucune nouvelle micro-action confirmée depuis " + age_label
        elif isinstance(age, int) and age < 120:
            execution_text = "▶️ Exécution : activité récente confirmée"
        else:
            execution_text = "🔵 Exécution : suivi actif · prochaine preuve attendue"
        rendered_at = utc_now()
        refresh_seconds = 60 if mission_state not in {"DONE", "CANCELLED"} else 300
        refresh_bucket = int(time.time() // refresh_seconds)
        stable = {
            "pc_active": heartbeat_ok,
            "edge_paired": edge_paired,
            "edge_active": edge_ok,
            "drive_visible": drive_ok,
            "nexus_state": nexus,
            "ci_state": ci_state,
            "mission_state": mission_state,
            "mission_action": action,
            "mission_next": next_action,
            "forecast": [forecast["done"], forecast["total"], forecast["pct"]],
            "health_pct": health_pct,
            "human_gate": human_gate,
            "attention_level": attention_level,
            "attention_reasons": attention_reasons,
            "forecast_confidence": forecast_confidence,
            "forecast_confidence_reason": forecast_confidence_reason,
            "evidence_age_label": age_label,
            "evidence_time": evidence_time,
            "objective": objective,
            "activity": activity,
            "execution_text": execution_text,
            "last_completed": last_completed,
            "pc_text": pc_text,
            "edge_text": edge_text,
            "drive_text": ("🟢 Drive : synchronisation visible" if drive_ok else "🟡 Drive : synchronisation non confirmée"),
            "nexus_pct": nexus_pct,
            "nexus_stage": nexus_stage,
            "ci_text": self._human_ci_explanation(gh),
            "refresh_seconds": refresh_seconds,
            "refresh_bucket": refresh_bucket,
        }
        digest = hashlib.sha256(
            json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        headline = self._attention_label(attention_level)
        headline_detail = {
            "CRITICAL": "Le système nécessite une vérification prioritaire.",
            "ACTION": "Une étape précise attend votre intervention; le reste est conservé.",
            "WATCH": "Le système reste suivi mais un signal mérite attention.",
            "ACTIVE": "Des preuves récentes indiquent que le travail avance.",
            "NORMAL": "Aucun signal prioritaire détecté.",
        }.get(attention_level, "Suivi automatique actif.")

        lines = [
            "🛰️ BCP · " + headline,
            headline_detail,
            activity,
            "",
            "🎯 " + objective,
            "📈 Progression ≈ " + forecast["bar"] + " " + str(forecast["pct"]) + "% · ≈" + str(forecast["done"]) + "/" + str(forecast["total"]) + " micro-actions",
            "🎚️ Confiance : " + forecast_confidence.lower() + " · " + forecast_confidence_reason,
            "🧭 Maintenant : " + action,
            execution_text,
        ]
        if last_completed and "Aucune étape" not in last_completed:
            lines.append("✅ Dernière action confirmée : " + last_completed)
        if next_action:
            lines.append("➡️ Ensuite : " + next_action)
        if human_gate != "AUCUNE":
            lines.append("👤 Votre intervention : " + human_gate)

        lines += [
            "",
            "🌡️ État général : " + health_bar + " " + str(health_pct) + "%",
            pc_text,
            edge_text,
            ("🟢 Drive : synchronisation visible" if drive_ok else "🟡 Drive : synchronisation non confirmée"),
            "🌐 Nexus : " + self._bar(nexus_pct, 100, 10) + " ≈" + str(nexus_pct) + "% · " + nexus_stage,
            "🧪 " + self._human_ci_explanation(gh),
            "",
            "🔄 Actualisation automatique : " + str(refresh_seconds) + " s quand la liaison est disponible · reprise automatique après coupure",
            ("🕒 Dernière preuve : " + (evidence_time or "horodatage en cours de synchronisation") + " · " + age_label if age is not None else "🕒 Dernière preuve : synchronisation en cours"),
            "",
            "Boutons : situation · depuis ma visite · pourquoi · étape · activité · rapports",
        ]
        return {
            "fingerprint": digest,
            "text": "\n".join(lines),
            "snapshot": stable,
            "rendered_at": rendered_at,
            "refresh_seconds": refresh_seconds,
        }

    def status(self) -> str:
        return self.presence_snapshot()["text"]

    def rich_status_html(self) -> str:
        """Telegram Bot API 10.3 rich cockpit. Plain V9 remains the fallback."""
        snap = self.presence_snapshot()
        s = snap.get("snapshot") or {}

        def esc(value: Any, limit: int = 500) -> str:
            return html.escape(clean(value, limit), quote=True)

        level = str(s.get("attention_level") or "NORMAL")
        title = self._attention_label(level)
        style = "danger" if level in {"CRITICAL", "ACTION"} else ("primary" if level == "WATCH" else "success")
        forecast = s.get("forecast") or [0, 1, 0]
        try:
            done, total, pct = int(forecast[0]), int(forecast[1]), int(forecast[2])
        except Exception:
            done, total, pct = 0, 1, 0

        reasons = list(s.get("attention_reasons") or [])
        why = "".join("<li>" + esc(x, 260) + "</li>" for x in reasons[:6])
        if not why:
            why = "<li>Aucun signal prioritaire détecté.</li>"

        human_gate = clean(s.get("human_gate") or "AUCUNE", 220)
        action_row = ""
        if human_gate != "AUCUNE":
            action_row = "<tr><th>Vous</th><td>" + esc(human_gate, 220) + "</td></tr>"

        last_completed = clean(s.get("last_completed") or "", 220)
        last_html = ("<p>✅ <b>Dernière preuve confirmée</b><br/>" + esc(last_completed, 220) + "</p>") if last_completed else ""

        return (
            "<h2>🛰️ BCP · " + esc(title, 80) + "</h2>"
            "<p><b>" + esc(s.get("activity") or "Suivi actif", 240) + "</b></p>"
            "<table bordered striped compact>"
            "<tr><th>Objectif</th><td>" + esc(s.get("objective") or self.project_id, 300) + "</td></tr>"
            "<tr><th>Progression</th><td>≈" + str(pct) + "% · ≈" + str(done) + "/" + str(total) + " micro-actions</td></tr>"
            "<tr><th>Confiance</th><td>" + esc(str(s.get("forecast_confidence") or "FAIBLE").lower(), 60) + "</td></tr>"
            "<tr><th>Preuve</th><td>" + esc(s.get("evidence_age_label") or "inconnue", 80) + "</td></tr>"
            + action_row +
            "</table>"
            "<p>🧭 <b>Maintenant</b><br/>" + esc(s.get("mission_action") or "", 260) + "</p>"
            + last_html +
            ("<p>➡️ <b>Ensuite</b><br/>" + esc(s.get("mission_next"), 260) + "</p>" if s.get("mission_next") else "") +
            "<details><summary>❓ Pourquoi cet état ?</summary><ul>" + why + "</ul></details>"
            "<details><summary>🌐 Appareils, réseau et preuves</summary>"
            "<table compact>"
            "<tr><th>PC</th><td>" + esc(s.get("pc_text") or "", 220) + "</td></tr>"
            "<tr><th>B-EDGE</th><td>" + esc(s.get("edge_text") or "", 220) + "</td></tr>"
            "<tr><th>Drive</th><td>" + esc(s.get("drive_text") or "", 220) + "</td></tr>"
            "<tr><th>Nexus</th><td>≈" + str(int(s.get("nexus_pct") or 0)) + "% · " + esc(s.get("nexus_stage") or "", 180) + "</td></tr>"
            "<tr><th>Tests</th><td>" + esc(s.get("ci_text") or "", 220) + "</td></tr>"
            "</table></details>"
            "<tg-button-row align=\"center\">"
            "<tg-button type=\"callback_data\" style=\"" + style + "\" data=\"bcp:status\">Situation</tg-button>"
            "<tg-button type=\"callback_data\" style=\"primary\" data=\"bcp:since\">Depuis ma visite</tg-button>"
            "</tg-button-row>"
            "<tg-button-row align=\"center\">"
            "<tg-button type=\"callback_data\" style=\"primary\" data=\"bcp:why\">Pourquoi ?</tg-button>"
            "<tg-button type=\"callback_data\" style=\"primary\" data=\"bcp:risks\">Radar</tg-button>"
            "</tg-button-row>"
            "<tg-button-row align=\"center\">"
            "<tg-button type=\"callback_data\" style=\"primary\" data=\"bcp:where\">Étape</tg-button>"
            "<tg-button type=\"callback_data\" style=\"primary\" data=\"bcp:tail\">Activité</tg-button>"
            "<tg-button type=\"callback_data\" style=\"success\" data=\"bcp:continue\">Continuer</tg-button>"
            "</tg-button-row>"
            + ("<tg-button-row align=\"center\"><tg-button type=\"callback_data\" style=\"primary\" data=\"bcp:ack\">✅ J’ai vu</tg-button></tg-button-row>" if level in {"CRITICAL","ACTION","WATCH"} else "") +
            "<footer>Fallback V9 texte actif si Rich Messages n’est pas disponible.</footer>"
        )

    def details(self) -> str:
        head = self._head()
        runtime = self.local.runtime()
        edge = self.local.edge()
        gh = self.github.snapshot()
        buildhub = self.local.buildhub()
        drive = self.local.drive()
        broker = self.local.broker()
        chat = self.local.chat(self.project_id)
        global_state = clean(
            (head or {}).get("status") or runtime.get("recovery_phase") or runtime.get("status") or "UNKNOWN",
            80,
        )
        checkpoint = clean((head or {}).get("last_completed_action") or "NOT_OBSERVED", 180)
        writer = clean(self.cfg.get("writer_branch") or "NOT_OBSERVED", 100)
        hb = runtime.get("_age_seconds")
        heartbeat = str(hb) + "s" if isinstance(hb, int) else "NOT_OBSERVED"
        edge_state = "PAIRED" if edge.get("paired") else "NOT_OBSERVED"
        if edge.get("last_event"):
            edge_state += " / " + str(edge["last_event"])
        next_action = clean(
            (head or {}).get("next_action") or "read durable evidence; do not replay committed work",
            190,
        )
        spend = float(broker.get("spend_usd") or 0.0)
        return "\n".join([
            self.project_id + " — État global: " + global_state,
            "Dernier checkpoint: " + checkpoint,
            "Git writer: " + writer,
            "GitHub CI: " + self._ci(gh),
            "B-EDGE: " + edge_state,
            "BuildHub: " + clean(buildhub.get("status"), 80),
            "Drive receipt: " + clean(drive.get("status"), 80),
            "BCP heartbeat: " + heartbeat,
            "ChatGPT: " + chat["state"],
            "Prochaine action sûre: " + next_action,
            "Spend: $" + format(spend, ".2f"),
        ])

    def report_summary(self) -> str:
        snap = self.presence_snapshot()
        return "\n".join([
            "BCP — RAPPORT 1/4 — SITUATION HUMAINE COMPLÈTE",
            "Généré: " + utc_now(),
            "",
            snap["text"],
            "",
            "OBJECTIF ET TRAJECTOIRE",
            self.plan_view(),
            "",
            "ACTIVITÉ RÉCENTE",
            self.tail(),
            "",
            "MISSIONS",
            self.missions(),
            "",
            "COMMENT LIRE LES POURCENTAGES",
            "- Le compteur de micro-actions marqué ≈ est une prévision dynamique, pas un nombre promis.",
            "- Une micro-action est atomique: lire/ouvrir un fichier, vérifier un workflow, lire un log, modifier un fichier, calculer un hash, lancer un test, créer un commit, faire un readback, etc.",
            "- L'estimation se recalcule quand la mission se précise; elle peut donc augmenter ou diminuer.",
            "- Les actions confirmées restent distinguées des actions seulement prévues.",
        ])

    def report_devices(self) -> str:
        runtime = self.local.runtime()
        edge = self.local.edge()
        drive = self.local.drive()
        gh = self.github.snapshot()
        keys = [
            "server_version", "server_pid", "pc_name", "updated_at", "paired",
            "update_state", "update_target_version", "nexus_bootstrap_state",
            "nexus_bootstrap_bundle_version", "nexus_bootstrap_exit_code",
            "nexus_bootstrap_receipt_status", "nexus_bootstrap_error_class",
            "nexus_bootstrap_error_detail", "nexus_bootstrap_stage",
            "telegram_companion_state", "telegram_companion_mode",
            "telegram_companion_pid", "telegram_companion_health_age_seconds",
            "telegram_companion_last_poll_at", "telegram_companion_last_callback_data",
            "telegram_companion_last_callback_received_at",
            "telegram_companion_last_callback_handled_at",
            "telegram_companion_error_class", "telegram_companion_error_detail",
            "chatgpt_pc_active_version", "chatgpt_pc_heartbeat_age_seconds",
            "chatgpt_pc_command_plane", "chatgpt_pc_command_plane_age_seconds",
            "recovery_phase", "recovery_result_status",
        ]
        lines = [
            "BCP — RAPPORT 2/4 — APPAREILS, RÉSEAU ET TRANSPORTS",
            "Généré: " + utc_now(),
            "",
            "VUE HUMAINE",
            self.status(),
            "",
            "TÉLÉMÉTRIE PC / BCP",
        ]
        for key in keys:
            if key in runtime:
                lines.append(key + ": " + clean(runtime.get(key), 260))
        lines += [
            "",
            "B-EDGE / ANCIEN TÉLÉPHONE",
            "paired: " + str(bool(edge.get("paired"))),
            "edge_version: " + clean(edge.get("edge_version") or "", 80),
            "last_event: " + clean(edge.get("last_event") or "", 120),
            "event_age_seconds: " + str(edge.get("_age_seconds")),
            "",
            "DRIVE",
            "status: " + clean(drive.get("status") or "", 80),
            "age_seconds: " + str(drive.get("age_seconds")),
            "",
            "GITHUB / QUALIFICATION",
            self.ci(),
            "",
            "INTERPRÉTATION",
            "- Direct PC→Telegram est opportuniste; une coupure TCP/443 ne doit pas arrêter BCP.",
            "- Nexus est le relais distant robuste quand le chemin direct est indisponible.",
            "- Le mode hors-ligne conserve l'état local; la synchronisation reprend quand une liaison revient.",
            "- Un poller Telegram unique est obligatoire pour éviter HTTP 409 getUpdates.",
        ]
        return "\n".join(lines)

    def report_mission(self) -> str:
        ctx = self._mission_context()
        mission = (ctx or {}).get("mission") or {}
        events = [
            e for e in self.local.mission_events(160)
            if not e.get("project_id") or str(e.get("project_id")) == self.project_id
        ]
        forecast = self._micro_forecast(ctx, events, self.github.snapshot())
        return "\n".join([
            "BCP — RAPPORT 3/4 — OBJECTIF, ÉTAPES ET MICRO-ACTIONS",
            "Généré: " + utc_now(),
            "",
            "MISSION COURANTE",
            "mission_id: " + clean(mission.get("mission_id") or "synthèse depuis preuves externes", 120),
            "status: " + clean(mission.get("status") or "suivi actif", 80),
            "current_step: " + clean(mission.get("current_step") or "", 160),
            "last_committed_step: " + clean(mission.get("last_committed_step") or "", 160),
            "next_step: " + clean(mission.get("next_step") or "", 160),
            "last_progress_at: " + clean(mission.get("last_progress_at") or "", 80),
            "",
            "PRÉVISION DYNAMIQUE DE MICRO-ACTIONS",
            forecast["bar"] + " ≈" + str(forecast["pct"]) + "% · ≈" + str(forecast["done"]) + "/" + str(forecast["total"]),
            "Le total est volontairement estimatif et peut être recalculé quand de nouvelles sous-actions apparaissent.",
            "",
            self.plan_view(),
            "",
            "JOURNAL FIN",
            self.tail(),
            "",
            "BLOCAGES / ATTENTES",
            self.holds(),
            "",
            "MISSIONS RÉCENTES",
            self.missions(),
        ])

    def report_technical(self) -> str:
        ctx = self._mission_context()
        mission = (ctx or {}).get("mission") or {}
        head = self._head() or {}
        gh = self.github.snapshot()
        return "\n".join([
            "BCP — RAPPORT 4/4 — DOSSIER TECHNIQUE ET AUDIT",
            "Généré: " + utc_now(),
            "",
            "ÉTAT TECHNIQUE",
            self.details(),
            "",
            "HEAD / CHECKPOINT",
            "revision: " + str(head.get("revision") or ""),
            "status: " + clean(head.get("status") or "", 120),
            "last_completed_action: " + clean(head.get("last_completed_action") or "", 500),
            "next_action: " + clean(head.get("next_action") or "", 500),
            "",
            "MISSION",
            "mission_id: " + clean(mission.get("mission_id") or "", 120),
            "worker_component: " + clean(mission.get("worker_component") or "", 120),
            "receipt_evidence: " + clean(mission.get("receipt_evidence") or "", 500),
            "hold_reason: " + clean(mission.get("hold_reason") or "", 240),
            "",
            "CI / WORKFLOWS",
            self.ci(),
            "",
            "PLAN ET JOURNAL",
            self.plan_view(),
            self.tail(),
            "",
            "CONTRAT DE VÉRITÉ",
            "- micro-actions confirmées = preuves externes/durables;",
            "- total ≈ = estimation de planification, explicitement non exacte;",
            "- état des appareils = heartbeat/télémétrie, jamais supposition silencieuse;",
            "- pas d'accès à la chaîne de pensée privée de ChatGPT;",
            "- absence de preuve ≠ travail inventé;",
            "- mutations: writer fence, idempotence, hash/readback avant COMMITTED.",
            "",
            "SNAPSHOT GITHUB",
            clean(json.dumps(gh, ensure_ascii=False, sort_keys=True), 5000),
        ])

    def report_pdf(self, kind: Any = "summary") -> bytes:
        if kind is True:
            kind = "technical"
        elif kind is False:
            kind = "summary"
        key = str(kind or "summary").lower()
        if key == "devices":
            body, title = self.report_devices(), "BCP Appareils Reseau et Transports"
        elif key == "mission":
            body, title = self.report_mission(), "BCP Objectif Etapes et Micro-actions"
        elif key == "technical":
            body, title = self.report_technical(), "BCP Dossier technique et audit"
        else:
            body, title = self.report_summary(), "BCP Situation humaine complete"
        return text_pdf_bytes(title, body)

    def objective(self) -> str:
        ctx = self._mission_context()
        events = [
            e for e in self.local.mission_events(160)
            if not e.get("project_id") or str(e.get("project_id")) == self.project_id
        ]
        forecast = self._micro_forecast(ctx, events, self.github.snapshot())
        mission = (ctx or {}).get("mission") or {}
        objective = clean(
            mission.get("objective") or mission.get("title") or
            (events[-1].get("mission_objective") if events else "") or
            "Faire avancer l’objectif API/BCP courant jusqu’au prochain état durable vérifié.",
            260,
        )
        current = clean((ctx or {}).get("current") or (events[-1].get("action_summary") if events else "") or "Synchroniser l’état courant.", 220)
        next_action = self._human_action((ctx or {}).get("next") or (events[-1].get("next_safe_action") if events else ""))
        lines = [
            "🎯 OBJECTIF ACTUEL",
            objective,
            "",
            "📈 Avancement estimé : " + forecast["bar"] + " ≈" + str(forecast["pct"]) + "% · ≈" + str(forecast["done"]) + "/" + str(forecast["total"]) + " micro-actions",
            "🧭 Maintenant : " + current,
        ]
        if next_action:
            lines.append("➡️ Ensuite : " + next_action)
        lines += ["", self.plan_view()]
        return "\n".join(lines)

    def missions(self) -> str:
        events = self.local.mission_events(200)
        if not events:
            return "MISSIONS ACTIVES\nAucune mission durable récente observée."
        latest: dict[str, dict] = {}
        for ev in events:
            project = clean(ev.get("project_id") or ev.get("project") or self.project_id, 80)
            key = clean(ev.get("mission_id") or ev.get("job_code") or ev.get("job_id") or project, 80)
            latest[project + "::" + key] = ev
        rows = list(latest.values())[-8:]
        lines = ["🗂️ Missions récentes"]
        for ev in reversed(rows):
            project = clean(ev.get("project_id") or ev.get("project") or self.project_id, 55)
            state = str(ev.get("state") or "NOT_OBSERVED").upper().replace("_", " ")
            action = clean(ev.get("action_summary") or ev.get("step_summary") or ev.get("step_id") or "état observé", 95)
            progress = state.lower()
            try:
                idx = int(ev.get("step_index"))
                total = int(ev.get("step_total"))
                if 0 <= idx <= total and total > 0:
                    progress = self._bar(idx, total) + " " + str(int(round(idx * 100 / total))) + "% " + str(idx) + "/" + str(total)
            except Exception:
                pass
            age = self._age_label(self._event_age_seconds(ev))
            lines.append("• " + project + " — " + progress + "\n  " + action + " · preuve " + age)
        return "\n".join(lines)

    def project(self, project: str) -> str:
        project = clean(project, 128)
        if not project:
            return "Usage: /project <id>"
        head = self.local.head(project)
        events = self.local.events(project, 5)
        if not head and not events:
            return "PROJECT " + project + "\nÉtat durable: NOT_OBSERVED"
        lines = ["PROJECT " + project]
        if head:
            lines += [
                "Revision: " + str(head.get("revision")),
                "État: " + clean(head.get("status"), 80),
                "Dernière action: " + clean(head.get("last_completed_action"), 180),
                "Prochaine action: " + clean(head.get("next_action"), 180),
            ]
        for ev in reversed(events):
            lines.append("- r" + str(ev.get("revision")) + " " + clean(ev.get("event_type"), 70))
        return "\n".join(lines)

    def job(self, code: str) -> str:
        rec = self.local.find_job(code)
        if not rec:
            return (
                "MISSION " + clean(code, 20) + "\nÉtat: NOT_OBSERVED\n"
                "Le code est un locator, jamais une clé d’authentification."
            )
        return "\n".join([
            "MISSION " + clean(code, 20),
            "Project: " + clean(rec.get("project_id") or rec.get("project"), 80),
            "State: " + clean(rec.get("state") or "OBSERVED", 80),
            "Step: " + clean(rec.get("step_id") or rec.get("kind"), 80),
            "Last event: " + clean(
                rec.get("timestamp") or rec.get("updated_at") or rec.get("created_at"), 80
            ),
            "Next safe action: " + clean(
                rec.get("next_safe_action") or "read durable mission journal", 160
            ),
            "Spend: $0.00",
        ])

    def last(self) -> str:
        events = self.local.mission_events(8) or self.local.events(self.project_id, 8)
        if not events:
            return "LAST EVENTS\nAucun événement durable observé."
        lines = ["LAST EVENTS"]
        for ev in events[-8:]:
            state = ev.get("state") or ev.get("event_type") or "EVENT"
            ts = ev.get("timestamp") or ev.get("created_at") or ev.get("ts") or ""
            summary = ev.get("action_summary") or ev.get("step_id") or ""
            lines.append("- " + clean(ts, 35) + " " + clean(state, 45) + " " + clean(summary, 90))
        return "\n".join(lines)

    def ci(self) -> str:
        gh = self.github.snapshot()
        runs = gh.get("runs") or []
        if not runs:
            return "GITHUB CI\nNOT_OBSERVED (" + str(gh.get("cache") or "NONE") + ")"
        lines = ["GITHUB CI — " + clean(gh.get("repo"), 80) + " — " + str(gh.get("cache") or "")]
        for r in runs[:6]:
            state = clean(r.get("conclusion") or r.get("status") or "unknown", 30).upper()
            lines.append(
                "- " + clean(r.get("name") or "workflow", 60) + ": " + state +
                " [" + clean(r.get("head_branch"), 60) + "] #" + str(r.get("run_number") or "?")
            )
        return "\n".join(lines)

    def progress_event(self, ev: dict) -> str:
        state = str(ev.get("state") or "EVENT").upper()
        action = clean(
            ev.get("action_summary") or ev.get("step_summary") or ev.get("step_id") or
            "Étape enregistrée.",
            145,
        )
        next_action = self._human_action(ev.get("next_safe_action") or "")
        labels = {
            "ACCEPTED": ("📌", "mission reçue"),
            "NORMALIZED": ("🧭", "mission préparée"),
            "PLANNED": ("🧭", "plan prêt"),
            "QUEUED": ("⏳", "en attente de démarrage"),
            "STARTED": ("▶️", "travail démarré"),
            "DISPATCHED": ("📤", "action lancée"),
            "WAITING_PROVIDER": ("⏳", "attente d’un service externe"),
            "RESULT_RECEIVED": ("📥", "résultat reçu"),
            "VALIDATING": ("🔎", "vérification en cours"),
            "COMMITTED": ("✅", "étape enregistrée"),
            "CHECKPOINTED": ("💾", "point de reprise sauvegardé"),
            "RETRY_SCHEDULED": ("🔁", "nouvel essai prévu"),
            "BLOCKED": ("🛑", "blocage confirmé"),
            "HOLD": ("🟠", "en attente"),
            "DONE": ("🏁", "terminé"),
            "CANCELLED": ("⏹️", "arrêté"),
        }
        icon, label = labels.get(state, ("•", state.replace("_", " ").lower()))
        lines = [icon + " " + label]
        try:
            idx = int(ev.get("step_index"))
            total = int(ev.get("step_total"))
            if 0 <= idx <= total and total > 0:
                pct = int(round(idx * 100 / total))
                lines.append(self._bar(idx, total) + " " + str(pct) + "% — étape " + str(idx) + "/" + str(total))
        except Exception:
            pass
        lines.append("🔧 " + action)
        if next_action:
            lines.append("➡️ " + next_action)
        return "\n".join(lines)

    def where(self, code: str = "") -> str:
        ctx = self._mission_context()
        events = self.local.mission_events(160)
        if code:
            events = [x for x in events if str(x.get("job_code") or x.get("job_id") or "") == code]
        ev = events[-1] if events else {}
        forecast = self._micro_forecast(ctx, events, self.github.snapshot())
        current = clean(
            (ctx or {}).get("current") or ev.get("action_summary") or ev.get("step_summary") or
            ev.get("step_id") or "Synchronisation de l’étape courante.",
            220,
        )
        next_action = self._human_action((ctx or {}).get("next") or ev.get("next_safe_action") or "")
        state = str(((ctx or {}).get("mission") or {}).get("status") or ev.get("state") or "EN_COURS").upper()
        human_state = {
            "DONE": "terminée",
            "COMMITTED": "étape enregistrée",
            "VALIDATING": "vérification en cours",
            "STARTED": "travail en cours",
            "DISPATCHED": "action lancée",
            "HOLD": "en attente",
            "BLOCKED": "bloquée",
        }.get(state, state.replace("_", " ").lower())
        lines = [
            "🔵 OÙ EN EST-ON ?",
            "État : " + human_state,
            "Progression estimée : " + forecast["bar"] + " ≈" + str(forecast["pct"]) + "% · ≈" + str(forecast["done"]) + "/" + str(forecast["total"]),
            "Étape actuelle : " + current,
        ]
        if next_action:
            lines.append("Étape suivante : " + next_action)
        lines.append("ℹ️ Le total ≈ est recalculé si de nouvelles micro-actions deviennent nécessaires.")
        return "\n".join(lines)

    def tail(self, code: str = "") -> str:
        ctx = self._mission_context()
        events = self.local.mission_events(160)
        if code:
            events = [x for x in events if str(x.get("job_code") or x.get("job_id") or "") == code]
        forecast = self._micro_forecast(ctx, events, self.github.snapshot())
        lines = [
            "⚙️ ACTIVITÉ FINE",
            "Compteur prévisionnel : " + forecast["bar"] + " ≈" + str(forecast["pct"]) + "% · ≈" + str(forecast["done"]) + "/" + str(forecast["total"]),
            "",
            "Micro-actions confirmées récemment :",
        ]
        durable_rows = []
        if ctx:
            mission = ctx.get("mission") or {}
            mission_id = str(mission.get("mission_id") or "")
            durable_rows = self.local.mission_event_tail(mission_id, 8) if mission_id else []
        if durable_rows:
            label_by_id = ctx.get("label_by_id") or {}
            for pos, row in enumerate(durable_rows, 1):
                step_id = clean(row.get("step_id"), 80)
                label = clean(label_by_id.get(step_id) or row.get("summary") or step_id or "Micro-action", 170)
                state = str(row.get("status") or row.get("event_type") or "EVENT").upper()
                icon = "✅" if state in {"DONE", "COMMITTED", "CHECKPOINTED", "SUCCESS", "COMPLETED", "VERIFIED"} else ("🟠" if state in HOLD_STATES or "FAIL" in state else "•")
                lines.append(str(pos) + ". " + icon + " " + label)
        elif events:
            for pos, ev in enumerate(events[-8:], 1):
                state = str(ev.get("state") or "EVENT").upper()
                icon = "✅" if state in {"DONE", "COMMITTED", "CHECKPOINTED"} else "•"
                step = clean(ev.get("action_summary") or ev.get("step_summary") or ev.get("step_id") or "Micro-action", 160)
                lines.append(str(pos) + ". " + icon + " " + step)
        else:
            lines.append("• Aucun reçu fin récent; la prévision ci-dessous reste disponible.")

        current = clean((ctx or {}).get("current") or (events[-1].get("action_summary") if events else "") or "Continuer la mission courante", 220)
        predicted = self._forecast_micro_labels(current)
        base = int(forecast["done"])
        lines += ["", "Prochaines micro-actions prévues (≈) :"]
        for offset, label in enumerate(predicted[:6], 1):
            number = base + offset
            if number > forecast["total"]:
                break
            lines.append("≈" + str(number) + "/" + str(forecast["total"]) + " ⬜ " + label)
        lines.append("ℹ️ Prévision ≠ preuve : les numéros peuvent être recalculés si le travail révèle de nouvelles sous-actions.")
        return "\n".join(lines)

    def holds(self) -> str:
        found = []
        for ev in self.local.mission_events(80):
            state = str(ev.get("state") or "").upper()
            if state in HOLD_STATES:
                found.append(state + ": " + clean(
                    ev.get("action_summary") or ev.get("error_class") or ev.get("next_safe_action"), 120
                ))
        for job in self.local.jobs(self.project_id):
            state = str(job.get("state") or "").upper()
            if state in HOLD_STATES:
                found.append("JOB " + str(job.get("id")) + " " + state + ": " + clean(job.get("kind"), 80))
        if self.local.chat(self.project_id)["state"] == "CHAT_PLATFORM_HOLD_REPORTED":
            found.append("CHAT_PLATFORM_HOLD_REPORTED")
        if not found:
            return "HOLDS\nAucun HOLD/BLOCKED durable observé."
        return "HOLDS\n" + "\n".join("- " + x for x in found[:12])

    def request_continue(self, source: str = "TELEGRAM_BUTTON") -> str:
        mission = self.local.mission_snapshot(self.project_id)
        if not mission:
            return "ℹ️ Aucune mission durable active à reprendre."
        if str(mission.get("status") or "").upper() in {"DONE", "CANCELLED"}:
            return "✅ La dernière mission durable est déjà terminée."
        mission_id = str(mission.get("mission_id") or "")
        anchor = clean(mission.get("last_progress_at") or mission.get("updated_at") or utc_now(), 80)
        step = clean(mission.get("next_step") or mission.get("current_step") or "RESUME", 100)
        request_id = hashlib.sha256(
            ("mission-resume:" + mission_id + ":" + anchor + ":" + step).encode("utf-8")
        ).hexdigest()[:32]
        rec = {
            "schema": "bcp.mission_resume_request/1",
            "request_id": request_id,
            "mission_id": mission_id,
            "project_id": self.project_id,
            "source": clean(source, 40),
            "state": "QUEUED",
            "step_id": step,
            "created_at": utc_now(),
            "zero_paid_spend_usd": 0.0,
        }
        old = read_json(MISSION_RESUME_REQUEST_PATH, {}) or {}
        if old.get("request_id") == request_id and old.get("state") in {"QUEUED", "ACKNOWLEDGED"}:
            return "▶️ Reprise déjà demandée. Le watchdog attend la prochaine preuve sans dupliquer l’action."
        atomic_json(MISSION_RESUME_REQUEST_PATH, rec)
        MISSION_RESUME_REQUEST_LOG.parent.mkdir(parents=True, exist_ok=True)
        with MISSION_RESUME_REQUEST_LOG.open("a", encoding="utf-8") as h:
            h.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        return "▶️ Continuer demandé. La reprise est enregistrée durablement et sera consommée par BCP dès que le moteur/transport qualifié est disponible."

    @staticmethod
    def _forecast_confidence(ctx: dict | None, events: list[dict], gh: dict) -> tuple[str, str]:
        plan = (ctx or {}).get("plan") or []
        evidence = len(events) + len(gh.get("runs") or [])
        if len(plan) >= 4 and evidence >= 6:
            return "ÉLEVÉE", "plan durable + preuves multiples"
        if plan or evidence >= 4:
            return "MOYENNE", "décomposition partielle, recalcul possible"
        return "FAIBLE", "peu de preuves structurées; estimation très révisable"

    @staticmethod
    def _attention_label(level: str) -> str:
        return {
            "CRITICAL": "🔴 CRITIQUE",
            "ACTION": "🟣 ACTION REQUISE",
            "WATCH": "🟠 À SURVEILLER",
            "ACTIVE": "🟢 EN COURS",
            "NORMAL": "🔵 STABLE",
        }.get(level, "🔵 SUIVI")

    def why(self) -> str:
        snap = self.presence_snapshot()
        s = snap.get("snapshot") or {}
        reasons = list(s.get("attention_reasons") or [])
        lines = [
            "❓ POURQUOI CET ÉTAT ?",
            self._attention_label(str(s.get("attention_level") or "NORMAL")),
        ]
        if reasons:
            lines += [""] + ["• " + clean(x, 220) for x in reasons[:8]]
        else:
            lines += ["", "• Aucun signal prioritaire; le système attend la prochaine preuve durable."]
        lines += [
            "",
            "Preuve fraîche : " + clean(s.get("evidence_age_label") or "inconnue", 80),
            "Confiance progression : " + clean(s.get("forecast_confidence") or "FAIBLE", 40),
            "ℹ️ La progression ≈ est une prévision; les actions confirmées restent séparées.",
        ]
        return "\n".join(lines)

    def mark_user_seen(self, source: str) -> None:
        atomic_json(USER_SEEN_STATE_PATH, {
            "schema": "bcp.telegram_user_seen/1",
            "seen_at": utc_now(),
            "source": clean(source, 40),
        })

    def since_last_seen(self) -> str:
        state = read_json(USER_SEEN_STATE_PATH, {}) or {}
        since = str(state.get("seen_at") or "")
        events = [
            e for e in self.local.mission_events(240)
            if not e.get("project_id") or str(e.get("project_id")) == self.project_id
        ]
        if since:
            recent = [e for e in events if self._event_timestamp(e) > since]
        else:
            recent = events[-12:]
        lines = ["🕘 DEPUIS VOTRE DERNIÈRE VISITE"]
        if since:
            lines.append("Depuis : " + clean(since, 40))
        if not recent:
            lines += ["", "Aucune nouvelle micro-action durable observée."]
        else:
            grouped = recent[-12:]
            lines += ["", str(len(recent)) + " nouvelle(s) preuve(s) durable(s)."]
            for ev in grouped:
                state_name = str(ev.get("state") or ev.get("status") or "EVENT").upper()
                icon = "✅" if state_name in {"DONE","COMMITTED","CHECKPOINTED","SUCCESS","COMPLETED","VERIFIED"} else ("🟠" if state_name in HOLD_STATES else "•")
                label = clean(ev.get("action_summary") or ev.get("summary") or ev.get("step_summary") or ev.get("step_id") or state_name, 170)
                lines.append(icon + " " + label)
            if len(recent) > len(grouped):
                lines.append("… +" + str(len(recent) - len(grouped)) + " événements regroupés")
        snap = self.presence_snapshot().get("snapshot") or {}
        lines += [
            "",
            "Maintenant : " + self._attention_label(str(snap.get("attention_level") or "NORMAL")),
            "Prochaine étape : " + clean(snap.get("mission_next") or "en cours de détermination", 180),
        ]
        return "\n".join(lines)

    def risk_radar(self) -> str:
        runtime = self.local.runtime()
        edge = self.local.edge()
        gh = self.github.snapshot()
        ctx = self._mission_context()
        mission = (ctx or {}).get("mission") or {}
        risks = []

        nexus = str(runtime.get("nexus_bootstrap_state") or "").upper()
        telegram_state = str(runtime.get("telegram_companion_state") or "").upper()
        if nexus == "HUMAN_AUTH_REQUIRED":
            risks.append(("ÉLEVÉ", "Relais distant", "Nexus est prêt mais non autorisé; si le Wi-Fi PC bloque Telegram, le cockpit distant reste vulnérable."))
        elif nexus not in {"COMMITTED", "NEXUS_DEPLOYED_LOCAL_WORKER_RUNNING"}:
            risks.append(("MOYEN", "Relais distant", "Nexus n’est pas encore totalement qualifié sur le terrain."))

        mem = runtime.get("pc_memory_load_percent")
        if isinstance(mem, int) and mem >= 90:
            risks.append(("ÉLEVÉ", "Mémoire PC", "RAM à " + str(mem) + "%; les tâches lourdes doivent rester sérialisées/déportées."))
        elif isinstance(mem, int) and mem >= 80:
            risks.append(("MOYEN", "Mémoire PC", "RAM à " + str(mem) + "%; marge locale réduite."))

        battery = runtime.get("pc_battery_percent")
        source = str(runtime.get("pc_power_source") or "").upper()
        if source == "BATTERY" and isinstance(battery, int) and battery <= 25:
            risks.append(("ÉLEVÉ", "Énergie", "PC sur batterie à " + str(battery) + "%; risque de coupure avant checkpoint."))
        elif source == "BATTERY":
            risks.append(("FAIBLE", "Énergie", "PC sur batterie; prévoir une reprise durable avant travaux longs."))

        if not edge.get("paired"):
            risks.append(("ÉLEVÉ", "Sentinelle B-EDGE", "Le téléphone secondaire n’est pas appairé; pas de seconde sentinelle disponible."))
        elif not (isinstance(edge.get("_age_seconds"), int) and edge.get("_age_seconds") <= 900):
            risks.append(("MOYEN", "Sentinelle B-EDGE", "B-EDGE est appairé mais sa preuve récente est limitée."))

        runs = gh.get("runs") or []
        if runs:
            st = str(runs[0].get("conclusion") or runs[0].get("status") or "").lower()
            if st == "failure":
                risks.append(("ÉLEVÉ", "Qualification", "Le dernier workflow GitHub observé est en échec."))
            elif st in {"queued", "in_progress"}:
                risks.append(("FAIBLE", "Qualification", "Une qualification GitHub est encore en cours."))

        age = None
        if mission:
            age = self._event_age_seconds({"updated_at": mission.get("last_progress_at") or mission.get("updated_at")})
        if isinstance(age, int) and age >= 900:
            risks.append(("MOYEN", "Continuité mission", "Aucune preuve nouvelle depuis " + self._age_label(age) + "; le watchdog doit rester attentif."))

        if telegram_state in {"DEGRADED_RETRY", "HOLD"} and nexus not in {"COMMITTED", "NEXUS_DEPLOYED_LOCAL_WORKER_RUNNING"}:
            risks.append(("ÉLEVÉ", "Visibilité distante", "Telegram direct est dégradé avant bascule Nexus complète."))

        order = {"ÉLEVÉ": 0, "MOYEN": 1, "FAIBLE": 2}
        risks.sort(key=lambda x: order.get(x[0], 9))
        lines = [
            "🔭 RADAR — risques proches",
            "Prévision ≠ incident : cette vue anticipe les fragilités à partir des preuves observables.",
            "",
        ]
        if not risks:
            lines.append("🟢 Aucun risque proche significatif détecté.")
        else:
            for level, area, text_value in risks[:8]:
                icon = "🔴" if level == "ÉLEVÉ" else ("🟠" if level == "MOYEN" else "🟡")
                lines.append(icon + " " + level + " · " + area + "\n   " + text_value)
        return "\n".join(lines)

    def _attention_key(self, snapshot: dict | None = None) -> tuple[str, str, str]:
        snap = snapshot or (self.presence_snapshot().get("snapshot") or {})
        level = str(snap.get("attention_level") or "NORMAL")
        reasons = list(snap.get("attention_reasons") or [])
        root = clean(reasons[0] if reasons else level, 180)
        key = hashlib.sha256((level + "\n" + root).encode("utf-8")).hexdigest()
        return key, level, root

    def acknowledge_attention(self) -> str:
        snap = self.presence_snapshot().get("snapshot") or {}
        key, level, root = self._attention_key(snap)
        atomic_json(ATTENTION_ACK_STATE_PATH, {
            "schema": "bcp.telegram_attention_ack/1",
            "key": key,
            "level": level,
            "root": root,
            "acknowledged_at": utc_now(),
        })
        return (
            "✅ Pris en compte.\n"
            + self._attention_label(level)
            + ("\n" + root if root else "")
            + "\nJe n’interromprai plus pour ce même signal inchangé; une aggravation ou un nouveau motif reste prioritaire."
        )

    def attention_is_acknowledged(self, key: str) -> bool:
        state = read_json(ATTENTION_ACK_STATE_PATH, {}) or {}
        return bool(key) and str(state.get("key") or "") == str(key)

    def recovery_transition_stable(self, key: str, level: str) -> bool:
        """Damp recovery flapping: require two observations or 60 seconds."""
        now = int(time.time())
        state = read_json(ATTENTION_PENDING_STATE_PATH, {}) or {}
        if str(state.get("key") or "") != key or str(state.get("level") or "") != level:
            atomic_json(ATTENTION_PENDING_STATE_PATH, {
                "schema": "bcp.telegram_attention_pending/1",
                "key": key,
                "level": level,
                "first_seen_epoch": now,
                "count": 1,
                "updated_at": utc_now(),
            })
            return False
        count = int(state.get("count") or 0) + 1
        first = int(state.get("first_seen_epoch") or now)
        atomic_json(ATTENTION_PENDING_STATE_PATH, {
            "schema": "bcp.telegram_attention_pending/1",
            "key": key,
            "level": level,
            "first_seen_epoch": first,
            "count": count,
            "updated_at": utc_now(),
        })
        return count >= 2 or (now - first) >= 60

    def consume_notification_budget(self, category: str, critical: bool = False) -> bool:
        """Bound routine interruption volume; critical/human-action alerts bypass."""
        if critical:
            return True
        now = int(time.time())
        window = 30 * 60
        limit = 3
        state = read_json(NOTIFICATION_BUDGET_STATE_PATH, {}) or {}
        stamps = []
        for value in state.get("sent_epochs") or []:
            try:
                value = int(value)
            except Exception:
                continue
            if now - value < window:
                stamps.append(value)
        if len(stamps) >= limit:
            atomic_json(NOTIFICATION_BUDGET_STATE_PATH, {
                "schema": "bcp.telegram_notification_budget/1",
                "sent_epochs": stamps,
                "window_seconds": window,
                "limit": limit,
                "suppressed_category": clean(category, 80),
                "updated_at": utc_now(),
            })
            return False
        stamps.append(now)
        atomic_json(NOTIFICATION_BUDGET_STATE_PATH, {
            "schema": "bcp.telegram_notification_budget/1",
            "sent_epochs": stamps,
            "window_seconds": window,
            "limit": limit,
            "last_category": clean(category, 80),
            "updated_at": utc_now(),
        })
        return True

    def quiet_mode(self, minutes: int) -> str:
        if minutes <= 0:
            atomic_json(NOTIFICATION_POLICY_PATH, {
                "schema": "bcp.telegram_notification_policy/1",
                "quiet_until_epoch": 0,
                "updated_at": utc_now(),
            })
            return "🔔 Mode normal rétabli. Les alertes pertinentes peuvent de nouveau être envoyées."
        minutes = max(15, min(480, int(minutes)))
        until = int(time.time()) + minutes * 60
        atomic_json(NOTIFICATION_POLICY_PATH, {
            "schema": "bcp.telegram_notification_policy/1",
            "quiet_until_epoch": until,
            "quiet_minutes": minutes,
            "updated_at": utc_now(),
            "critical_bypass": True,
        })
        return "🔕 Mode discret activé pour " + str(minutes) + " min. Les alertes critiques et actions humaines requises restent autorisées."

    def notifications_allowed(self, critical: bool = False) -> bool:
        if critical:
            return True
        state = read_json(NOTIFICATION_POLICY_PATH, {}) or {}
        try:
            return int(state.get("quiet_until_epoch") or 0) <= int(time.time())
        except Exception:
            return True

    def watchdog_notice(self) -> tuple[str, str] | None:
        wd = read_json(MISSION_WATCHDOG_STATE_PATH, {}) or {}
        state = str(wd.get("state") or "").upper()
        if state not in {"RESUME_REQUESTED", "ESCALATED", "HUMAN_GATE"}:
            return None
        mission_id = clean(wd.get("mission_id") or "", 100)
        attempt = int(wd.get("attempt_count") or 0)
        stale = int(wd.get("stale_seconds") or 0)
        key = hashlib.sha256(
            (state + ":" + mission_id + ":" + str(attempt) + ":" + str(wd.get("anchor_key") or "")).encode("utf-8")
        ).hexdigest()
        if state == "RESUME_REQUESTED":
            text = (
                "🔄 BCP a détecté une interruption de progression.\n"
                "Mission: " + (mission_id or "courante") + "\n"
                "Aucune nouvelle preuve depuis ≈" + str(max(1, stale // 60)) + " min.\n"
                "Reprise automatique demandée (" + str(attempt) + "/3).\n"
                "Vous n’avez rien à faire; le prochain reçu mettra la carte à jour."
            )
        elif state == "HUMAN_GATE":
            text = (
                "👤 BCP a atteint une étape qui nécessite réellement votre intervention.\n"
                "Mission: " + (mission_id or "courante") + "\n"
                "Le système conserve l’état et n’effectue pas de retries aveugles."
            )
        else:
            text = (
                "⚠️ BCP a tenté les reprises automatiques prévues sans nouvelle preuve.\n"
                "Mission: " + (mission_id or "courante") + "\n"
                "L’état est conservé. Utilisez ▶️ Continuer quand vous voulez relancer une demande de reprise."
            )
        return key, text

    def help(self) -> str:
        return (
            "Automate de suivi BCP — lecture simple\n"
            "/continue — demander une reprise durable\n/status — situation actuelle\n/since — changements depuis votre dernière visite\n/why — expliquer l’état affiché\n/risks — radar des risques proches\n/ack — confirmer que vous avez vu le signal courant\n/quiet 120 — mode discret 2h\n/objective — objectif courant\n/missions — historique des missions\n/details — vue technique\n"
            "/report — rapport 1/4 suivi humain\n/reporttech — rapport 4/4 audit technique\n"
            "/project <id>\n/job <code>\n/tail [code]\n/where [code]\n/last\n/ci\n/holds\n\n"
            "Les boutons donnent une lecture humaine de la situation et quatre rapports PDF complémentaires. "
            "Le compteur marqué ≈ est une estimation dynamique de micro-actions atomiques; les actions confirmées restent fondées sur des preuves durables. "
            "Aucun état interne ni chaîne de pensée ChatGPT n’est lu."
        )

    def dispatch(self, text: str) -> str:
        raw = (text or "").strip()
        if not raw:
            return self.help()
        first, *rest = raw.split(maxsplit=1)
        cmd = first.split("@", 1)[0].lower()
        arg = rest[0].strip() if rest else ""
        if cmd == "/continue":
            return self.request_continue("TELEGRAM_COMMAND")
        if cmd == "/ack":
            return self.acknowledge_attention()
        if cmd == "/quiet":
            try:
                minutes = 0 if arg.lower() in {"off","normal","0"} else int(arg or "120")
            except Exception:
                return "Usage: /quiet 120 · /quiet off"
            return self.quiet_mode(minutes)
        if cmd not in READ_ONLY_COMMANDS:
            return "Commandes: /continue /status /since /why /risks /ack /quiet 120 /objective /missions /details /report /reporttech /project <id> /job <code> /tail [code] /where [code] /last /ci /holds"
        if cmd in {"/start", "/help"}:
            return self.help()
        if cmd == "/status":
            return self.status()
        if cmd == "/missions":
            return self.missions()
        if cmd == "/objective":
            return self.objective()
        if cmd == "/details":
            return self.details()
        if cmd == "/why":
            return self.why()
        if cmd == "/since":
            return self.since_last_seen()
        if cmd == "/risks":
            return self.risk_radar()
        if cmd == "/project":
            return self.project(arg)
        if cmd == "/job":
            return self.job(arg)
        if cmd == "/tail":
            return self.tail(arg)
        if cmd == "/where":
            return self.where(arg)
        if cmd == "/last":
            return self.last()
        if cmd == "/ci":
            return self.ci()
        if cmd == "/report":
            return "REPORT_PDF_SUMMARY"
        if cmd == "/reporttech":
            return "REPORT_PDF_TECHNICAL"
        return self.holds()


class Telegram:
    def __init__(self, token: str, chat_id: int, service: Service, http: Http | None = None):
        self.token = token
        self.chat_id = int(chat_id)
        self.service = service
        self.http = http or Http()
        self.base = "https://api.telegram.org/bot" + token
        presence = service.cfg.get("presence") or {}
        self.auto_push = bool(presence.get("auto_push", True))
        try:
            self.max_events_per_push = max(1, min(12, int(presence.get("max_events_per_push", 6))))
        except Exception:
            self.max_events_per_push = 6

    @staticmethod
    def keyboard() -> dict:
        # Keep the chat surface compact: orientation first, deep reports last.
        return {
            "inline_keyboard": [
                [
                    {"text": "🟢 Situation", "callback_data": "bcp:status"},
                    {"text": "🕘 Depuis ma visite", "callback_data": "bcp:since"},
                ],
                [
                    {"text": "❓ Pourquoi ?", "callback_data": "bcp:why"},
                    {"text": "🔭 Radar", "callback_data": "bcp:risks"},
                ],
                [
                    {"text": "📍 Étape actuelle", "callback_data": "bcp:where"},
                    {"text": "⚙️ Activité fine", "callback_data": "bcp:tail"},
                ],
                [
                    {"text": "🎯 Objectif", "callback_data": "bcp:missions"},
                    {"text": "▶️ Continuer", "callback_data": "bcp:continue"},
                ],
                [
                    {"text": "✅ J’ai vu", "callback_data": "bcp:ack"},
                    {"text": "🔕 Discret 2h", "callback_data": "bcp:quiet:120"},
                    {"text": "🔔 Normal", "callback_data": "bcp:quiet:off"},
                ],
                [
                    {"text": "🧰 Technique", "callback_data": "bcp:details"},
                ],
                [
                    {"text": "📄 Suivi", "callback_data": "bcp:pdf:summary"},
                    {"text": "🖥️ Appareils", "callback_data": "bcp:pdf:devices"},
                ],
                [
                    {"text": "🧭 Mission", "callback_data": "bcp:pdf:mission"},
                    {"text": "📚 Audit", "callback_data": "bcp:pdf:technical"},
                ],
            ]
        }

    def api(self, method: str, payload: dict, timeout: int) -> dict:
        status, obj = self.http.json(
            self.base + "/" + method, method="POST", payload=payload, timeout=timeout
        )
        if status != 200 or not isinstance(obj, dict) or not obj.get("ok"):
            desc = clean(obj.get("description") if isinstance(obj, dict) else "http_" + str(status), 140)
            raise RuntimeError("telegram_api_error:" + desc)
        return obj

    def send(self, text: str, with_keyboard: bool = True, silent: bool = False) -> int | None:
        payload = {
            "chat_id": self.chat_id,
            "text": redact_text(text)[:3900],
            "disable_web_page_preview": True,
            "disable_notification": bool(silent),
        }
        if with_keyboard:
            payload["reply_markup"] = self.keyboard()
        obj = self.api("sendMessage", payload, 20)
        result = obj.get("result") or {}
        try:
            return int(result.get("message_id"))
        except Exception:
            return None

    def send_rich(self, rich_html: str, fallback_text: str) -> int | None:
        """Prefer Bot API 10.3 Rich Messages; V9 plain text is mandatory fallback."""
        try:
            obj = self.api("sendRichMessage", {
                "chat_id": self.chat_id,
                "rich_message": {
                    "html": redact_text(rich_html)[:30000],
                    "skip_entity_detection": True,
                },
            }, 20)
            result = obj.get("result") or {}
            append_log("RICH_MESSAGE_SENT", mode="BOT_API_10_3")
            try:
                return int(result.get("message_id"))
            except Exception:
                return None
        except Exception as e:
            append_log("RICH_MESSAGE_SEND_FALLBACK",
                       error_class=type(e).__name__, detail=clean(e, 140))
            return self.send(fallback_text, with_keyboard=True)

    def edit_rich(self, message_id: int, rich_html: str, fallback_text: str) -> bool:
        try:
            self.api("editMessageText", {
                "chat_id": self.chat_id,
                "message_id": int(message_id),
                "rich_message": {
                    "html": redact_text(rich_html)[:30000],
                    "skip_entity_detection": True,
                },
            }, 20)
            append_log("RICH_MESSAGE_EDITED", mode="BOT_API_10_3")
            return True
        except Exception as e:
            append_log("RICH_MESSAGE_EDIT_FALLBACK",
                       error_class=type(e).__name__, detail=clean(e, 140))
            return self.edit(message_id, fallback_text, with_keyboard=True)

    def edit(self, message_id: int, text: str, with_keyboard: bool = True) -> bool:
        try:
            payload = {
                "chat_id": self.chat_id,
                "message_id": int(message_id),
                "text": redact_text(text)[:3900],
                "disable_web_page_preview": True,
            }
            if with_keyboard:
                payload["reply_markup"] = self.keyboard()
            self.api("editMessageText", payload, 20)
            return True
        except Exception as e:
            append_log("LIVE_CARD_EDIT_FAILED", error_class=type(e).__name__, detail=clean(e, 140))
            return False

    def answer_callback(self, callback_id: str, text: str = "") -> None:
        try:
            payload = {"callback_query_id": str(callback_id)}
            if text:
                payload["text"] = clean(text, 160)
            self.api("answerCallbackQuery", payload, 10)
        except Exception as e:
            append_log("CALLBACK_ACK_FAILED", error_class=type(e).__name__, detail=clean(e, 120))

    def send_document(self, filename: str, data: bytes, caption: str) -> None:
        if len(data) > 750_000:
            raise RuntimeError("telegram_document_too_large_for_cockpit")
        boundary = "----BCP" + hashlib.sha256(filename.encode("utf-8")).hexdigest()[:20]
        chunks: list[bytes] = []
        def field(name: str, value: str) -> None:
            chunks.extend([
                ("--" + boundary + "\r\n").encode("ascii"),
                ('Content-Disposition: form-data; name="' + name + '"\r\n\r\n').encode("ascii"),
                value.encode("utf-8"),
                b"\r\n",
            ])
        field("chat_id", str(self.chat_id))
        field("caption", clean(caption, 900))
        chunks.extend([
            ("--" + boundary + "\r\n").encode("ascii"),
            ('Content-Disposition: form-data; name="document"; filename="' + filename.replace('"', "") + '"\r\n').encode("ascii"),
            b"Content-Type: application/pdf\r\n\r\n",
            data,
            b"\r\n",
            ("--" + boundary + "--\r\n").encode("ascii"),
        ])
        req = Request(
            self.base + "/sendDocument",
            data=b"".join(chunks),
            headers={"Content-Type": "multipart/form-data; boundary=" + boundary,
                     "User-Agent": "BCP-Telegram-Observability/1"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=30) as res:
                obj = json.loads(res.read().decode("utf-8"))
        except Exception as e:
            raise RuntimeError("telegram_send_document_failed:" + type(e).__name__) from e
        if not isinstance(obj, dict) or not obj.get("ok"):
            raise RuntimeError("telegram_send_document_failed")

    def _callback_action(self, data: str) -> tuple[str, str]:
        mapping = {
            "bcp:continue": ("/continue", "Reprise demandée"),
            "bcp:status": ("/status", "Situation actualisée"),
            "bcp:since": ("/since", "Résumé depuis votre visite"),
            "bcp:why": ("/why", "Explication"),
            "bcp:risks": ("/risks", "Radar des risques"),
            "bcp:ack": ("/ack", "Signal pris en compte"),
            "bcp:where": ("/where", "Étape actuelle"),
            "bcp:tail": ("/tail", "Activité fine"),
            "bcp:missions": ("/objective", "Objectif"),
            "bcp:quiet:120": ("/quiet 120", "Mode discret 2h"),
            "bcp:quiet:off": ("/quiet off", "Mode normal"),
            "bcp:details": ("/details", "Détails"),
        }
        return mapping.get(data, ("", ""))

    def handle_callback(self, callback: dict) -> None:
        callback_id = str(callback.get("id") or "")
        data = str(callback.get("data") or "")
        msg = callback.get("message") or {}
        chat = msg.get("chat") or {}
        incoming = int(chat.get("id") or 0)
        authorized = incoming == self.chat_id and str(chat.get("type") or "") == "private"
        if not authorized:
            self.answer_callback(callback_id, "Non autorisé")
            return
        if data == "bcp:pdf:summary":
            self.answer_callback(callback_id, "Rapport 1/4 en préparation…")
            self.send_document("BCP_1_SITUATION.pdf", self.service.report_pdf("summary"), "BCP — situation humaine complète")
            return
        if data == "bcp:pdf:devices":
            self.answer_callback(callback_id, "Rapport 2/4 en préparation…")
            self.send_document("BCP_2_APPAREILS_RESEAU.pdf", self.service.report_pdf("devices"), "BCP — appareils, réseau et transports")
            return
        if data == "bcp:pdf:mission":
            self.answer_callback(callback_id, "Rapport 3/4 en préparation…")
            self.send_document("BCP_3_MISSION_MICRO_ACTIONS.pdf", self.service.report_pdf("mission"), "BCP — objectif, étapes et micro-actions")
            return
        if data == "bcp:pdf:technical":
            self.answer_callback(callback_id, "Rapport 4/4 en préparation…")
            self.send_document("BCP_4_AUDIT_TECHNIQUE.pdf", self.service.report_pdf("technical"), "BCP — dossier technique et audit")
            return
        command, label = self._callback_action(data)
        if not command:
            self.answer_callback(callback_id, "Action inconnue")
            return
        self.answer_callback(callback_id, label)
        response = self.service.dispatch(command)
        self.service.mark_user_seen("TELEGRAM_CALLBACK:" + data)
        message_id = msg.get("message_id")
        if command == "/status":
            rich_html = self.service.rich_status_html()
            if message_id:
                if not self.edit_rich(int(message_id), rich_html, response):
                    self.send(response)
            else:
                self.send_rich(rich_html, response)
        elif message_id and command in {"/since", "/why", "/risks", "/where", "/tail", "/missions", "/objective", "/details", "/quiet 120", "/quiet off"}:
            if not self.edit(int(message_id), response):
                self.send(response)
        else:
            self.send(response)

    def _push_presence(self) -> None:
        if not self.auto_push:
            return
        events = [
            e for e in self.service.local.mission_events(200)
            if not e.get("project_id") or str(e.get("project_id")) == self.service.project_id
        ]
        if not events:
            return
        state = read_json(PRESENCE_PATH, {}) or {}
        last_key = str(state.get("mission_event_key") or "")
        keys = [event_key(e) for e in events]
        newest_key = keys[-1]

        # First observation primes the cursor without replaying an old backlog.
        if not last_key:
            atomic_json(PRESENCE_PATH, {
                "schema": "bcp.telegram_presence/1",
                "mission_event_key": newest_key,
                "updated_at": utc_now(),
            })
            return

        if last_key not in keys:
            # History window moved or journal was compacted. Never guess/replay.
            atomic_json(PRESENCE_PATH, {
                "schema": "bcp.telegram_presence/1",
                "mission_event_key": newest_key,
                "updated_at": utc_now(),
                "resync": "CURSOR_PRIMED_NO_REPLAY",
            })
            return

        idx = keys.index(last_key)
        pending = events[idx + 1:]
        relevant = [
            e for e in pending
            if str(e.get("state") or "").upper() in PUSH_STATES
            or e.get("human_action_required") is True
        ]
        if relevant:
            if not self.service.notifications_allowed(False):
                urgent = [e for e in relevant if e.get("human_action_required") is True
                          or str(e.get("state") or "").upper() in {"BLOCKED", "HOLD"}]
                relevant = urgent
            skipped = max(0, len(relevant) - self.max_events_per_push)
            selected = relevant[-self.max_events_per_push:]
            blocks = []
            if skipped:
                blocks.append("ℹ️ " + str(skipped) + " micro-actions précédentes regroupées.")
            blocks.extend(self.service.progress_event(e) for e in selected)
            if blocks:
                self.send("\n\n".join(blocks))
        atomic_json(PRESENCE_PATH, {
            "schema": "bcp.telegram_presence/1",
            "mission_event_key": newest_key,
            "updated_at": utc_now(),
        })

    def _push_watchdog_notice(self) -> None:
        if not self.auto_push:
            return
        notice = self.service.watchdog_notice()
        if not notice:
            return
        key, text = notice
        wd_state = str((read_json(MISSION_WATCHDOG_STATE_PATH, {}) or {}).get("state") or "").upper()
        if not self.service.notifications_allowed(wd_state in {"HUMAN_GATE", "ESCALATED"}):
            return
        prior = read_json(WATCHDOG_NOTIFY_STATE_PATH, {}) or {}
        if str(prior.get("key") or "") == key:
            return
        self.send(text, silent=(wd_state == "RESUME_REQUESTED"))
        atomic_json(WATCHDOG_NOTIFY_STATE_PATH, {
            "schema": "bcp.telegram_watchdog_notice/1",
            "key": key,
            "updated_at": utc_now(),
            "transport": "DIRECT_TELEGRAM",
        })

    def _push_attention_transition(self) -> None:
        snap = self.service.presence_snapshot()
        state = snap.get("snapshot") or {}
        level = str(state.get("attention_level") or "NORMAL")
        reasons = list(state.get("attention_reasons") or [])
        root = clean(reasons[0] if reasons else level, 180)
        key = hashlib.sha256((level + "\n" + root).encode("utf-8")).hexdigest()
        prior = read_json(ATTENTION_NOTIFY_STATE_PATH, {}) or {}
        prior_level = str(prior.get("level") or "")
        prior_key = str(prior.get("key") or "")
        if prior_key == key:
            return

        text = ""
        critical = level in {"CRITICAL", "ACTION"}
        if level in {"CRITICAL", "ACTION"}:
            text = self.service._attention_label(level) + "\n" + (root or "Une action humaine est requise.")
        elif prior_level in {"CRITICAL", "ACTION"} and level in {"ACTIVE", "NORMAL"}:
            text = "✅ SITUATION RÉTABLIE\nLe signal qui nécessitait votre attention n’est plus actif."

        # WATCH remains visible in the live card/Radar but is deliberately not
        # pushed as a page-like alert while automation can still handle it.
        if text and self.service.notifications_allowed(critical):
            self.send(text, silent=(level in {"ACTIVE", "NORMAL"}))
        atomic_json(ATTENTION_NOTIFY_STATE_PATH, {
            "schema": "bcp.telegram_attention_notice/1",
            "key": key,
            "level": level,
            "root": root,
            "updated_at": utc_now(),
        })

    def _push_system_presence(self) -> None:
        if not self.auto_push:
            return
        snap = self.service.presence_snapshot()
        path = self.service.local.state / SYSTEM_PRESENCE_PATH.name
        prior = read_json(path, {}) or {}
        if str(prior.get("fingerprint") or "") == str(snap["fingerprint"]):
            return
        message_id = prior.get("message_id")
        updated = False
        rich_html = self.service.rich_status_html()
        if message_id:
            try:
                updated = self.edit_rich(int(message_id), rich_html, str(snap["text"]))
            except Exception:
                updated = False
        if not updated:
            message_id = self.send_rich(rich_html, str(snap["text"]))
        atomic_json(path, {
            "schema": "bcp.telegram_system_presence/3",
            "fingerprint": snap["fingerprint"],
            "updated_at": utc_now(),
            "transport": "DIRECT_TELEGRAM",
            "render_mode": "RICH_V10_WITH_V9_FALLBACK",
            "message_id": message_id,
        })

    def run(self) -> int:
        offset = int((read_json(OFFSET_PATH, {}) or {}).get("next_offset") or 0)
        backoff = [2, 5, 15, 30, 60]
        failures = 0
        append_log("WORKER_STARTED")
        write_worker_health("DIRECT_TELEGRAM", "RUNNING", consecutive_failures=0, next_offset=offset)
        while True:
            try:
                obj = self.api("getUpdates", {
                    "offset": offset, "timeout": 20, "allowed_updates": ["message", "callback_query"]
                }, 35)
                failures = 0
                updates = obj.get("result") or []
                write_worker_health(
                    "DIRECT_TELEGRAM", "ACTIVE",
                    consecutive_failures=0,
                    next_offset=offset,
                    updates_received=len(updates),
                    last_poll_at=utc_now(),
                )
                for upd in updates:
                    uid = int(upd.get("update_id") or 0)
                    offset = max(offset, uid + 1)
                    callback = upd.get("callback_query")
                    if isinstance(callback, dict):
                        callback_data = clean(callback.get("data"), 80)
                        append_log("CALLBACK_UPDATE", update_id=uid, callback_data=callback_data)
                        write_worker_health(
                            "DIRECT_TELEGRAM", "CALLBACK_RECEIVED",
                            consecutive_failures=0,
                            update_id=uid,
                            callback_data=callback_data,
                            callback_received_at=utc_now(),
                        )
                        self.handle_callback(callback)
                        write_worker_health(
                            "DIRECT_TELEGRAM", "ACTIVE",
                            consecutive_failures=0,
                            update_id=uid,
                            callback_data=callback_data,
                            callback_handled_at=utc_now(),
                        )
                    else:
                        msg = upd.get("message") or {}
                        chat = msg.get("chat") or {}
                        incoming = int(chat.get("id") or 0)
                        authorized = incoming == self.chat_id and str(chat.get("type") or "") == "private"
                        append_log("UPDATE", update_id=uid, authorized=authorized)
                        if authorized:
                            raw = str(msg.get("text") or "")
                            result = self.service.dispatch(raw)
                            if result == "REPORT_PDF_SUMMARY":
                                self.send_document("BCP_SUIVI.pdf", self.service.report_pdf(False), "BCP — rapport de suivi")
                            elif result == "REPORT_PDF_TECHNICAL":
                                self.send_document("BCP_DETAILS_TECHNIQUES.pdf", self.service.report_pdf(True), "BCP — rapport technique")
                            else:
                                self.send(result)
                            self.service.mark_user_seen("TELEGRAM_COMMAND")
                    atomic_json(OFFSET_PATH, {
                        "schema": "bcp.telegram_offset/1", "next_offset": offset, "updated_at": utc_now()
                    })
                if not (obj.get("result") or []):
                    atomic_json(OFFSET_PATH, {
                        "schema": "bcp.telegram_offset/1", "next_offset": offset, "updated_at": utc_now()
                    })
                self._push_presence()
                self._push_watchdog_notice()
                self._push_attention_transition()
                self._push_system_presence()
            except KeyboardInterrupt:
                append_log("WORKER_STOPPED")
                write_worker_health("DIRECT_TELEGRAM", "STOPPED", consecutive_failures=failures)
                return 0
            except (URLError, TimeoutError, OSError, RuntimeError) as e:
                delay = backoff[min(failures, len(backoff) - 1)]
                failures += 1
                detail = clean(e, 180)
                append_log("RETRY", error_class=type(e).__name__, retry_seconds=delay)
                write_worker_health(
                    "DIRECT_TELEGRAM", "DEGRADED_RETRY",
                    consecutive_failures=failures,
                    error_class=type(e).__name__,
                    error_detail=detail,
                    retry_seconds=delay,
                )
                time.sleep(delay)
            except Exception as e:
                detail = clean(e, 180)
                append_log("HOLD", error_class=type(e).__name__, detail=detail)
                write_worker_health(
                    "DIRECT_TELEGRAM", "HOLD",
                    consecutive_failures=failures,
                    error_class=type(e).__name__,
                    error_detail=detail,
                    retry_seconds=60,
                )
                time.sleep(60)


class Nexus:
    def __init__(self, base_url: str, device_id: str, token: str,
                 service: Service, http: Http | None = None):
        self.base_url = base_url.rstrip("/")
        self.device_id = device_id
        self.token = token
        self.service = service
        self.http = http or Http()
        transport = service.cfg.get("transport") or {}
        try:
            self.poll_seconds = max(5, min(120, int(transport.get("poll_seconds", 15))))
        except Exception:
            self.poll_seconds = 15
        presence = service.cfg.get("presence") or {}
        self.auto_push = bool(presence.get("auto_push", True))
        try:
            self.max_events_per_push = max(1, min(12, int(presence.get("max_events_per_push", 6))))
        except Exception:
            self.max_events_per_push = 6

    def _headers(self) -> dict:
        return {
            "Authorization": "Bearer " + self.token,
            "X-BCP-Device-ID": self.device_id,
        }

    def api(self, path: str, method: str = "GET", payload: dict | None = None,
            timeout: int = 20) -> dict:
        status, obj = self.http.json(
            self.base_url + path, method=method, payload=payload,
            headers=self._headers(), timeout=timeout,
        )
        if status != 200 or not isinstance(obj, dict) or obj.get("ok") is False:
            detail = clean(obj.get("error") if isinstance(obj, dict) else "http_" + str(status), 140)
            raise RuntimeError("nexus_api_error:" + detail)
        return obj

    def reply(self, command_id: int, text: str) -> None:
        safe_text = redact_text(text)[:3900]
        idem = hashlib.sha256(
            ("reply:" + str(command_id) + ":" + safe_text).encode("utf-8")
        ).hexdigest()
        self.api("/v1/device/reply", method="POST", payload={
            "command_id": int(command_id),
            "text": safe_text,
            "idempotency_key": idem,
        }, timeout=25)

    def push(self, text: str, idem_seed: str, silent: bool = False) -> None:
        safe_text = redact_text(text)[:3900]
        idem = hashlib.sha256(("push:" + idem_seed).encode("utf-8")).hexdigest()
        self.api("/v1/device/push", method="POST", payload={
            "kind": "MISSION_PROGRESS",
            "text": safe_text,
            "idempotency_key": idem,
            "silent": bool(silent),
        }, timeout=25)

    def live_card(self, text: str, card_key: str = "mission-status",
                  rich_html: str = "") -> None:
        safe_text = redact_text(text)[:3900]
        payload = {
            "card_key": clean(card_key, 96),
            "text": safe_text,
        }
        if rich_html:
            payload["rich_html"] = redact_text(rich_html)[:30000]
        self.api("/v1/device/live-card", method="POST", payload=payload, timeout=25)

    def publish_reports(self) -> None:
        summary = redact_text(self.service.report_summary())[:18000]
        devices = redact_text(self.service.report_devices())[:22000]
        mission = redact_text(self.service.report_mission())[:24000]
        technical = redact_text(self.service.report_technical())[:26000]
        self.api("/v1/device/report", method="POST", payload={
            "summary": summary,
            "devices": devices,
            "mission": mission,
            "technical": technical,
        }, timeout=30)

    def _push_presence(self) -> None:
        if not self.auto_push:
            return
        events = [
            e for e in self.service.local.mission_events(200)
            if not e.get("project_id") or str(e.get("project_id")) == self.service.project_id
        ]
        if not events:
            return
        state = read_json(PRESENCE_PATH, {}) or {}
        last_key = str(state.get("mission_event_key") or "")
        keys = [event_key(e) for e in events]
        newest_key = keys[-1]

        if not last_key:
            atomic_json(PRESENCE_PATH, {
                "schema": "bcp.telegram_presence/1",
                "mission_event_key": newest_key,
                "updated_at": utc_now(),
                "transport": "NEXUS",
            })
            return

        if last_key not in keys:
            atomic_json(PRESENCE_PATH, {
                "schema": "bcp.telegram_presence/1",
                "mission_event_key": newest_key,
                "updated_at": utc_now(),
                "transport": "NEXUS",
                "resync": "CURSOR_PRIMED_NO_REPLAY",
            })
            return

        idx = keys.index(last_key)
        pending = events[idx + 1:]
        relevant = [
            e for e in pending
            if str(e.get("state") or "").upper() in PUSH_STATES
            or e.get("human_action_required") is True
        ]
        if relevant:
            skipped = max(0, len(relevant) - self.max_events_per_push)
            selected = relevant[-self.max_events_per_push:]
            blocks = []
            if skipped:
                blocks.append("ℹ️ " + str(skipped) + " micro-actions précédentes regroupées.")
            blocks.extend(self.service.progress_event(e) for e in selected)
            self.push("\n\n".join(blocks), newest_key)

        atomic_json(PRESENCE_PATH, {
            "schema": "bcp.telegram_presence/1",
            "mission_event_key": newest_key,
            "updated_at": utc_now(),
            "transport": "NEXUS",
        })

    def _push_watchdog_notice(self) -> None:
        if not self.auto_push:
            return
        notice = self.service.watchdog_notice()
        if not notice:
            return
        key, text = notice
        wd_state = str((read_json(MISSION_WATCHDOG_STATE_PATH, {}) or {}).get("state") or "").upper()
        if not self.service.notifications_allowed(wd_state in {"HUMAN_GATE", "ESCALATED"}):
            return
        prior = read_json(WATCHDOG_NOTIFY_STATE_PATH, {}) or {}
        if str(prior.get("key") or "") == key:
            return
        self.push(text, "watchdog:" + key, silent=(wd_state == "RESUME_REQUESTED"))
        atomic_json(WATCHDOG_NOTIFY_STATE_PATH, {
            "schema": "bcp.telegram_watchdog_notice/1",
            "key": key,
            "updated_at": utc_now(),
            "transport": "NEXUS",
        })

    def _push_attention_transition(self) -> None:
        snap = self.service.presence_snapshot()
        state = snap.get("snapshot") or {}
        level = str(state.get("attention_level") or "NORMAL")
        reasons = list(state.get("attention_reasons") or [])
        root = clean(reasons[0] if reasons else level, 180)
        key = hashlib.sha256((level + "\n" + root).encode("utf-8")).hexdigest()
        prior = read_json(ATTENTION_NOTIFY_STATE_PATH, {}) or {}
        prior_level = str(prior.get("level") or "")
        prior_key = str(prior.get("key") or "")
        if prior_key == key:
            return

        text = ""
        critical = level in {"CRITICAL", "ACTION"}
        if level in {"CRITICAL", "ACTION"}:
            text = self.service._attention_label(level) + "\n" + (root or "Une action humaine est requise.")
        elif prior_level in {"CRITICAL", "ACTION"} and level in {"ACTIVE", "NORMAL"}:
            text = "✅ SITUATION RÉTABLIE\nLe signal qui nécessitait votre attention n’est plus actif."

        if text and self.service.notifications_allowed(critical):
            self.push(text, "attention:" + key, silent=(level in {"ACTIVE", "NORMAL"}))
        atomic_json(ATTENTION_NOTIFY_STATE_PATH, {
            "schema": "bcp.telegram_attention_notice/1",
            "key": key,
            "level": level,
            "root": root,
            "updated_at": utc_now(),
            "transport": "NEXUS",
        })

    def _push_system_presence(self) -> None:
        if not self.auto_push:
            return
        snap = self.service.presence_snapshot()
        path = self.service.local.state / SYSTEM_PRESENCE_PATH.name
        prior = read_json(path, {}) or {}
        if str(prior.get("fingerprint") or "") == str(snap["fingerprint"]):
            return
        self.publish_reports()
        self.live_card(
            str(snap["text"]),
            "mission:" + self.service.project_id,
            rich_html=self.service.rich_status_html(),
        )
        atomic_json(path, {
            "schema": "bcp.telegram_system_presence/3",
            "fingerprint": snap["fingerprint"],
            "updated_at": utc_now(),
            "transport": "NEXUS",
            "render_mode": "RICH_V10_WITH_V9_FALLBACK",
            "card_key": "mission:" + self.service.project_id,
        })

    def run(self) -> int:
        cursor = int((read_json(NEXUS_CURSOR_PATH, {}) or {}).get("last_command_id") or 0)
        backoff = [2, 5, 15, 30, 60]
        failures = 0
        append_log("NEXUS_WORKER_STARTED", device_id=self.device_id)
        write_worker_health("NEXUS", "RUNNING", consecutive_failures=0, last_command_id=cursor)
        while True:
            try:
                obj = self.api(
                    "/v1/device/commands?after=" + str(cursor) + "&limit=8",
                    timeout=20,
                )
                commands = obj.get("commands") or []
                failures = 0
                write_worker_health(
                    "NEXUS", "ACTIVE",
                    consecutive_failures=0,
                    last_command_id=cursor,
                    commands_received=len(commands),
                    last_poll_at=utc_now(),
                )
                for command in commands:
                    command_id = int(command.get("id") or 0)
                    if command_id <= cursor:
                        continue
                    response = self.service.dispatch(str(command.get("text") or ""))
                    if response == "REPORT_PDF_SUMMARY":
                        self.publish_reports()
                        response = "📄 Rapport de suivi actualisé. Utilisez le bouton « PDF suivi »."
                    elif response == "REPORT_PDF_TECHNICAL":
                        self.publish_reports()
                        response = "📚 Rapport technique actualisé. Utilisez le bouton « PDF technique »."
                    self.reply(command_id, response)
                    self.service.mark_user_seen("NEXUS_COMMAND")
                    cursor = command_id
                    atomic_json(NEXUS_CURSOR_PATH, {
                        "schema": "bcp.nexus_cursor/1",
                        "last_command_id": cursor,
                        "updated_at": utc_now(),
                    })
                    append_log("NEXUS_COMMAND_REPLIED", command_id=command_id)
                self._push_presence()
                self._push_watchdog_notice()
                self._push_attention_transition()
                self._push_system_presence()
                if not commands:
                    time.sleep(self.poll_seconds)
            except KeyboardInterrupt:
                append_log("NEXUS_WORKER_STOPPED")
                write_worker_health("NEXUS", "STOPPED", consecutive_failures=failures, last_command_id=cursor)
                return 0
            except (URLError, TimeoutError, OSError, RuntimeError) as e:
                delay = backoff[min(failures, len(backoff) - 1)]
                failures += 1
                detail = clean(e, 180)
                append_log("NEXUS_RETRY", error_class=type(e).__name__, retry_seconds=delay)
                write_worker_health(
                    "NEXUS", "DEGRADED_RETRY",
                    consecutive_failures=failures,
                    last_command_id=cursor,
                    error_class=type(e).__name__,
                    error_detail=detail,
                    retry_seconds=delay,
                )
                time.sleep(delay)
            except Exception as e:
                detail = clean(e, 180)
                append_log("NEXUS_HOLD", error_class=type(e).__name__, detail=detail)
                write_worker_health(
                    "NEXUS", "HOLD",
                    consecutive_failures=failures,
                    last_command_id=cursor,
                    error_class=type(e).__name__,
                    error_detail=detail,
                    retry_seconds=60,
                )
                time.sleep(60)


class SingleInstance:
    def __init__(self):
        self.handle = None

    def acquire(self) -> bool:
        if os.name == "nt":
            try:
                import ctypes
                self.handle = ctypes.windll.kernel32.CreateMutexW(
                    None, False, r"Local\BCP_Telegram_Observability_MVP"
                )
                return bool(self.handle) and ctypes.windll.kernel32.GetLastError() != 183
            except Exception:
                return True
        try:
            import fcntl
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            self.handle = (STATE_DIR / "telegram-observability.lock").open("a+")
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except Exception:
            return False


def load_config() -> tuple[str, dict]:
    cfg = read_json(CONFIG_PATH, {}) or {}
    transport = cfg.get("transport") or {}
    mode = str(transport.get("mode") or "DIRECT_TELEGRAM").upper()

    if mode == "NEXUS":
        base_url = str(transport.get("nexus_url") or "").strip()
        device_id = str(transport.get("device_id") or "").strip()
        device_token = NEXUS_TOKEN_PATH.read_text(encoding="utf-8").strip() if NEXUS_TOKEN_PATH.is_file() else ""
        if not base_url.startswith("https://"):
            raise RuntimeError("NEXUS_HTTPS_URL_NOT_CONFIGURED")
        if not device_id:
            raise RuntimeError("NEXUS_DEVICE_ID_NOT_CONFIGURED")
        if len(device_token) < 24:
            raise RuntimeError("NEXUS_DEVICE_TOKEN_NOT_CONFIGURED")
        return "", cfg

    if mode != "DIRECT_TELEGRAM":
        raise RuntimeError("TRANSPORT_MODE_UNSUPPORTED:" + mode)

    token = TOKEN_PATH.read_text(encoding="utf-8").strip() if TOKEN_PATH.is_file() else ""
    if not token:
        raise RuntimeError("TELEGRAM_TOKEN_NOT_CONFIGURED")
    if not TOKEN_RE.fullmatch(token):
        raise RuntimeError("TELEGRAM_TOKEN_FORMAT_INVALID")
    if not isinstance(cfg.get("allowed_chat_id"), int) or int(cfg["allowed_chat_id"]) == 0:
        raise RuntimeError("TELEGRAM_ALLOWED_CHAT_ID_NOT_CONFIGURED")
    return token, cfg


def selftest() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "bcp"
        (root / "state").mkdir(parents=True)
        (root / "telemetry").mkdir(parents=True)
        db = root / "state" / "bcp.sqlite3"
        cx = sqlite3.connect(db)
        cx.executescript("""
        CREATE TABLE heads(project_id TEXT PRIMARY KEY,revision INTEGER,last_event_id INTEGER,last_event_hash TEXT,status TEXT,last_completed_action TEXT,next_action TEXT,updated_at TEXT);
        CREATE TABLE events(id INTEGER PRIMARY KEY,project_id TEXT,revision INTEGER,event_type TEXT,payload_json TEXT,idempotency_key TEXT,created_at TEXT,prev_hash TEXT,event_hash TEXT);
        CREATE TABLE jobs(id INTEGER PRIMARY KEY,project_id TEXT,kind TEXT,payload_json TEXT,state TEXT,requires_pc INTEGER,idempotency_key TEXT,created_at TEXT,updated_at TEXT);
        CREATE TABLE missions(
            mission_id TEXT PRIMARY KEY,project_id TEXT,current_step TEXT,last_committed_step TEXT,
            next_step TEXT,last_progress_at TEXT,worker_component TEXT,receipt_evidence TEXT,
            status TEXT,hold_reason TEXT,plan_json TEXT,created_at TEXT,updated_at TEXT
        );
        CREATE TABLE mission_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,mission_id TEXT,seq INTEGER,event_type TEXT,
            step_id TEXT,worker_component TEXT,summary TEXT,evidence_ref TEXT,status TEXT,
            failure_hold_reason TEXT,created_at TEXT
        );
        """)
        cx.execute("INSERT INTO heads VALUES(?,?,?,?,?,?,?,?)", (
            "API/BCP", 7, 7, "abc", "EN_COURS", "CI patch persisted",
            "validate -> checkpoint", utc_now()
        ))
        cx.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?)", (
            7, "API/BCP", 7, "CHECKPOINT", json.dumps({"chat_state": "CHAT_WAITING"}),
            "idem7", utc_now(), "prev", "abc"
        ))
        cx.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)", (
            42, "API/BCP", "android-build", "{}", "WAITING_FOR_PC", 1, "j42", utc_now(), utc_now()
        ))
        now = utc_now()
        cx.execute("INSERT INTO missions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            "mission-test", "API/BCP", "run-test", "check-commit", "read-log",
            now, "GITHUB_CI", "run:9", "STARTED", "", "[{\"id\":\"read-spec\",\"label\":\"Lire le cahier des charges courant\",\"state\":\"DONE\",\"verified\":true},{\"id\":\"check-commit\",\"label\":\"Vérifier le commit de la PR\",\"state\":\"DONE\",\"verified\":true},{\"id\":\"run-test\",\"label\":\"Lancer le test Windows Bootstrap\",\"state\":\"RUNNING\",\"verified\":false},{\"id\":\"read-log\",\"label\":\"Lire le journal du test Windows\",\"state\":\"PENDING\",\"verified\":false}]",
            now, now
        ))
        cx.execute("INSERT INTO mission_events(mission_id,seq,event_type,step_id,worker_component,summary,evidence_ref,status,failure_hold_reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (
            "mission-test", 1, "STEP_COMMITTED", "read-spec", "LOCAL",
            "Lire le cahier des charges courant", "spec:R11", "COMMITTED", "", now
        ))
        cx.execute("INSERT INTO mission_events(mission_id,seq,event_type,step_id,worker_component,summary,evidence_ref,status,failure_hold_reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (
            "mission-test", 2, "STEP_COMMITTED", "check-commit", "GITHUB",
            "Vérifier le commit de la PR", "commit:test", "COMMITTED", "", now
        ))
        cx.execute("INSERT INTO mission_events(mission_id,seq,event_type,step_id,worker_component,summary,evidence_ref,status,failure_hold_reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (
            "mission-test", 3, "STEP_STARTED", "run-test", "GITHUB_CI",
            "Lancer le test Windows Bootstrap", "run:9", "STARTED", "", now
        ))
        cx.commit()
        cx.close()
        atomic_json(root / "state" / "paired_edge.json", {"edge_version": "2.0"})
        (root / "telemetry" / "phone-events.jsonl").write_text(
            json.dumps({"event_type": "PHONE_HEARTBEAT", "ts": utc_now()}) + "\n",
            encoding="utf-8",
        )
        (root / "state" / "MISSION_EVENT_LOG.jsonl").write_text(
            json.dumps({
                "state": "COMMITTED", "job_code": "48273195", "project_id": "API/BCP",
                "step_id": "07", "timestamp": utc_now(),
                "action_summary": "CI patch persisted",
                "next_safe_action": "validate -> checkpoint",
            }) + "\n", encoding="utf-8"
        )

        class FakeGitHub:
            def snapshot(self, force=False):
                return {
                    "ok": True, "repo": "Terminator364/BCP", "cache": "TEST",
                    "runs": [{"name": "Windows", "conclusion": "success",
                              "head_branch": "work/test", "run_number": 9}],
                    "pulls": [], "commits": [],
                }

        svc = Service(
            {"default_project": "API/BCP", "github_repo": "Terminator364/BCP",
             "writer_branch": "work/test"},
            local=LocalTruth(root), github=FakeGitHub()
        )
        status = svc.status()
        assert "🛰️ BCP ·" in status
        assert "🧭 Maintenant : Lancer le test Windows Bootstrap" in status
        assert "📈 Progression ≈" in status and "micro-actions" in status
        assert "✅ Dernière action confirmée : Vérifier le commit de la PR" in status
        assert "➡️ Ensuite : Lire le journal du test Windows" in status
        assert "Ancien téléphone" in status
        assert "💰 Coût: $0.00" not in status
        assert "Votre intervention" not in status
        assert "🕒 Dernière preuve :" in status
        assert "🧪 Tests terminés avec succès" in status
        assert "1. ✅ Lire le cahier des charges courant" in svc.plan_view()
        assert "3. ▶️ Lancer le test Windows Bootstrap" in svc.plan_view()
        presence = svc.presence_snapshot()
        assert len(presence["fingerprint"]) == 64
        assert "🛰️ BCP ·" in presence["text"]
        assert "Ancien téléphone" in presence["text"]
        details = svc.details()
        assert "État global: EN_COURS" in details
        assert "GitHub CI: Windows=SUCCESS [work/test]" in details
        assert "B-EDGE: PAIRED / PHONE_HEARTBEAT" in details
        assert "48273195" in svc.job("48273195")
        assert "Vérifier le commit de la PR" in svc.tail()
        assert "Lancer le test Windows Bootstrap" in svc.tail()
        assert "OÙ EN EST-ON" in svc.where("48273195") and "≈" in svc.where("48273195")
        assert "WAITING_FOR_PC" in svc.holds()
        assert "Missions récentes" in svc.missions() and "OBJECTIF ACTUEL" in svc.objective()
        assert "Commandes:" in svc.dispatch("/run")
        assert svc.dispatch("/report") == "REPORT_PDF_SUMMARY"
        assert svc.dispatch("/reporttech") == "REPORT_PDF_TECHNICAL"
        summary_pdf = svc.report_pdf("summary")
        devices_pdf = svc.report_pdf("devices")
        mission_pdf = svc.report_pdf("mission")
        technical_pdf = svc.report_pdf("technical")
        for pdf in (summary_pdf, devices_pdf, mission_pdf, technical_pdf):
            assert pdf.startswith(b"%PDF-1.4")
            assert pdf.rstrip().endswith(b"%%EOF")
        assert "sk-" not in redact_text("key=sk-abcdefghijklmnopqrstuv")
        assert "ghp_" not in redact_text("ghp_123456789012345678901234567890")
        assert "Bearer abcdefghijklmnop" not in redact_text("Authorization: Bearer abcdefghijklmnop")
        keyboard = Telegram.keyboard()
        callback_values = {
            button.get("callback_data")
            for row in keyboard.get("inline_keyboard", [])
            for button in row
        }
        assert {
            "bcp:status", "bcp:since", "bcp:why", "bcp:risks", "bcp:ack", "bcp:where", "bcp:tail", "bcp:missions",
            "bcp:quiet:120", "bcp:quiet:off", "bcp:details",
            "bcp:pdf:summary", "bcp:pdf:devices", "bcp:pdf:mission", "bcp:pdf:technical",
        } <= callback_values
        assert "chaîne de pensée" in svc.help() and "estimation dynamique" in svc.help()
        assert "POURQUOI CET ÉTAT" in svc.why()
        assert "DEPUIS VOTRE DERNIÈRE VISITE" in svc.since_last_seen()
        assert "RADAR" in svc.risk_radar()
        assert "Pris en compte" in svc.acknowledge_attention()
        rich = svc.rich_status_html()
        assert "<table bordered striped compact>" in rich
        assert 'style="success"' in rich or 'style="primary"' in rich or 'style="danger"' in rich
        assert 'type="callback_data"' in rich
        assert "Fallback V9" in rich
        assert CHAT_STATES == {
            "OBSERVED_CHAT_ACTION", "CHAT_WAITING",
            "CHAT_PLATFORM_HOLD_REPORTED", "UNKNOWN_INTERNAL_CHAT_STATE",
        }
        assert MISSION_STATES >= {
            "ACCEPTED", "NORMALIZED", "PLANNED", "QUEUED", "STARTED", "DISPATCHED",
            "WAITING_PROVIDER", "RESULT_RECEIVED", "VALIDATING", "COMMITTED",
            "CHECKPOINTED", "RETRY_SCHEDULED", "BLOCKED", "HOLD", "DONE", "CANCELLED",
        }
        # Nexus transport is opt-in; direct Telegram remains the default.
        assert str((svc.cfg.get("transport") or {}).get("mode") or "DIRECT_TELEGRAM") == "DIRECT_TELEGRAM"
        assert Nexus.__name__ == "Nexus"
        assert HEALTH_PATH.name == "telegram_worker_health.json"
        assert MISSION_WATCHDOG_STATE_PATH.name == "mission_watchdog.json"
        assert "bcp:continue" in json.dumps(Telegram.keyboard(), ensure_ascii=False)
        assert Telegram._callback_action.__name__ == "_callback_action"
    print("BCP_TELEGRAM_OBSERVABILITY_SELFTEST=PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="BCP Telegram read-only observability cockpit")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--once-status", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    token, cfg = load_config()
    svc = Service(cfg)
    if args.once_status:
        print(svc.status())
        return 0
    lock = SingleInstance()
    if not lock.acquire():
        print("BCP_TELEGRAM_OBSERVABILITY_ALREADY_RUNNING", file=sys.stderr)
        return 0

    transport = cfg.get("transport") or {}
    mode = str(transport.get("mode") or "DIRECT_TELEGRAM").upper()
    if mode == "NEXUS":
        device_token = NEXUS_TOKEN_PATH.read_text(encoding="utf-8").strip()
        return Nexus(
            str(transport["nexus_url"]),
            str(transport["device_id"]),
            device_token,
            svc,
        ).run()
    return Telegram(token, int(cfg["allowed_chat_id"]), svc).run()


if __name__ == "__main__":
    raise SystemExit(main())
