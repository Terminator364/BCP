from __future__ import annotations

import argparse
import datetime as dt
import hashlib
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
    "/tail", "/where", "/missions", "/report", "/reporttech",
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
        mission_state = str(
            mission.get("status") or ev.get("state") or "NOT_OBSERVED"
        ).upper()

        if ctx:
            action = clean(ctx.get("current"), 180)
            next_action = self._human_action(ctx.get("next"))
            last_completed = clean(ctx.get("last"), 180)
            progress = str(ctx.get("progress") or ("Étape: " + mission_state.replace("_", " ").lower()))
            age = self._event_age_seconds({
                "updated_at": mission.get("last_progress_at") or mission.get("updated_at")
            })
            evidence_time = clean(
                mission.get("last_progress_at") or mission.get("updated_at") or "non observée", 64
            )
            step_key = [int(ctx.get("verified") or 0), int(ctx.get("total") or 0)] if int(ctx.get("total") or 0) > 0 else None
        else:
            action = clean(
                ev.get("action_summary") or ev.get("step_summary") or ev.get("step_id") or
                "Aucune micro-action durable récente.",
                180,
            )
            next_action = self._human_action(
                ev.get("next_safe_action") or "Relire l’état sauvegardé avant de reprendre."
            )
            age = self._event_age_seconds(ev)
            evidence_time = self._event_timestamp(ev) or "non observée"
            last_completed = self._last_completed_action(events, ev)
            progress = "Étape: " + mission_state.replace("_", " ").lower()
            step_key = None
            try:
                idx = int(ev.get("step_index"))
                total = int(ev.get("step_total"))
                if 0 <= idx <= total and total > 0:
                    pct = int(round(idx * 100 / total))
                    progress = self._bar(idx, total) + " " + str(pct) + "% — étape " + str(idx) + "/" + str(total)
                    step_key = [idx, total]
            except Exception:
                pass

        if age is None:
            age = self.local.mission_activity_age()
        age_label = self._age_label(age)
        if isinstance(age, int) and age < 120:
            activity_band = "RECENT"
        elif isinstance(age, int) and age < 600:
            activity_band = "QUIET"
        elif isinstance(age, int):
            activity_band = "STALE"
        else:
            activity_band = "UNKNOWN"
        if mission_state in HOLD_STATES or clean(mission.get("hold_reason"), 120):
            activity_band = "HOLD"

        hb = runtime.get("_age_seconds")
        heartbeat_ok = isinstance(hb, int) and hb <= 180
        edge_age = edge.get("_age_seconds")
        edge_ok = bool(edge.get("paired")) and isinstance(edge_age, int) and edge_age <= 300
        drive_ok = str(drive.get("status") or "").upper() == "OBSERVED"
        runs = gh.get("runs") or []
        run = runs[0] if runs else {}
        ci_state = clean(run.get("conclusion") or run.get("status"), 30).lower()
        nexus = str(runtime.get("nexus_bootstrap_state") or "NOT_OBSERVED").upper()
        nexus_text = {
            "COMMITTED": "✅ relais Nexus actif",
            "NEXUS_DEPLOYED_LOCAL_WORKER_RUNNING": "✅ relais Nexus actif",
            "EXITED_NO_RECEIPT": "🟡 relais Nexus à reprendre",
            "WRANGLER_RUNTIME_REQUIRED": "🟡 préparation du relais Nexus",
            "LAUNCHED": "🟡 démarrage du relais Nexus en cours",
        }.get(nexus, "⚪ relais Nexus non observé")

        human_gate = self._human_gate(ev, next_action)
        rendered_at = utc_now()
        stable = {
            "pc_active": heartbeat_ok,
            "edge_paired": edge_ok,
            "drive_visible": drive_ok,
            "nexus_state": nexus,
            "ci_state": ci_state,
            "mission_state": mission_state,
            "mission_action": action,
            "mission_next": next_action,
            "mission_step": step_key,
            "activity_band": activity_band,
            "human_gate": human_gate,
            "evidence_time": evidence_time,
        }
        digest = hashlib.sha256(
            json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        if activity_band == "HOLD":
            activity = "🟠 La mission attend un élément identifié."
        elif activity_band == "RECENT":
            activity = "🟢 Une preuve récente confirme que ça avance."
        elif activity_band == "QUIET":
            activity = "🟡 Pas de nouvelle preuve depuis " + age_label + "."
        elif activity_band == "STALE":
            activity = "🟠 Pas de nouvelle preuve depuis " + age_label + ". La liaison doit être revérifiée."
        else:
            activity = "⚪ Progression récente non observée."

        lines = [
            "🤖 BCP Cockpit — " + self.project_id,
            activity,
            "",
            "🎯 Micro-action actuelle: " + action,
            "📊 Progression: " + progress,
            "✅ Dernière micro-action terminée: " + last_completed,
            "➡️ Prochaine micro-action: " + next_action,
            "👤 Action pour vous: " + human_gate,
            "",
            "🕒 Dernière preuve: " + evidence_time + " · âge " + age_label,
            "",
            ("✅ PC/BCP" if heartbeat_ok else "⚠️ PC/BCP — preuve récente absente"),
            ("✅ Ancien téléphone" if edge_ok else ("🟡 Ancien téléphone appairé, preuve récente absente" if edge.get("paired") else "⚠️ Ancien téléphone non observé")),
            ("✅ Drive" if drive_ok else "⚠️ Drive non observé"),
            "🌐 " + nexus_text,
            "🧪 " + self._human_ci(gh),
            "",
            "📋 Micro-actions: bouton ci-dessous · 🔧 technique: Détails",
        ]
        return {"fingerprint": digest, "text": "\n".join(lines), "snapshot": stable}

    def status(self) -> str:
        return self.presence_snapshot()["text"]

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
        return "\n".join([
            "BCP — Rapport de suivi humain",
            "Généré: " + utc_now(),
            "",
            self.status(),
            "",
            self.plan_view(),
            "",
            self.tail(),
            "",
            "LECTURE",
            "- La barre vient uniquement d’un plan fini enregistré.",
            "- Une micro-action = une action concrète et vérifiable (ouvrir/lire un fichier, modifier un fichier, lancer un test, vérifier un commit, publier un reçu).",
            "- L’absence de nouvelle preuve n’est pas présentée comme une réflexion ChatGPT.",
        ])

    def report_technical(self) -> str:
        ctx = self._mission_context()
        mission = (ctx or {}).get("mission") or {}
        mission_meta = [
            "MISSION COURANTE",
            "mission_id: " + clean(mission.get("mission_id") or "NOT_OBSERVED", 120),
            "status: " + clean(mission.get("status") or "NOT_OBSERVED", 80),
            "worker_component: " + clean(mission.get("worker_component") or "NOT_OBSERVED", 120),
            "last_progress_at: " + clean(mission.get("last_progress_at") or "NOT_OBSERVED", 80),
            "receipt_evidence: " + clean(mission.get("receipt_evidence") or "NOT_OBSERVED", 220),
            "hold_reason: " + clean(mission.get("hold_reason") or "NONE", 180),
        ]
        return "\n".join([
            "BCP — Rapport technique détaillé",
            "Généré: " + utc_now(),
            "",
            self.details(),
            "",
            *mission_meta,
            "",
            self.plan_view(),
            "",
            "JOURNAL DES MICRO-ACTIONS",
            self.tail(),
            "",
            "MISSIONS",
            self.missions(),
            "",
            "CONTRAT DE VÉRITÉ",
            "- progression: seulement plan fini persisté et étapes vérifiées;",
            "- preuves: SQLite/BCP, GitHub, Drive, B-EDGE, Nexus ou autre reçu externe;",
            "- aucun accès à la chaîne de pensée privée de ChatGPT;",
            "- un silence UI n’est jamais converti en progrès inventé.",
        ])

    def report_pdf(self, technical: bool = False) -> bytes:
        body = self.report_technical() if technical else self.report_summary()
        title = "BCP Rapport technique detaille" if technical else "BCP Rapport de suivi humain"
        return text_pdf_bytes(title, body)

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
        events = self.local.mission_events(160)
        if code:
            events = [x for x in events if str(x.get("job_code") or x.get("job_id") or "") == code]
        if not events:
            return "Aucune progression durable observée pour cette mission."
        return self.progress_event(events[-1])

    def tail(self, code: str = "") -> str:
        ctx = self._mission_context()
        if ctx:
            mission = ctx.get("mission") or {}
            mission_id = str(mission.get("mission_id") or "")
            rows = self.local.mission_event_tail(mission_id, 10) if mission_id else []
            if rows:
                lines = ["📋 Journal des micro-actions vérifiables"]
                label_by_id = ctx.get("label_by_id") or {}
                for pos, row in enumerate(rows, 1):
                    step_id = clean(row.get("step_id"), 80)
                    label = clean(label_by_id.get(step_id) or row.get("summary") or step_id or "Micro-action", 170)
                    state = str(row.get("status") or row.get("event_type") or "EVENT").upper()
                    icon = "✅" if state in {"DONE", "COMMITTED", "CHECKPOINTED", "SUCCESS", "COMPLETED", "VERIFIED"} else ("🔴" if state in HOLD_STATES or "FAIL" in state else "•")
                    when = clean(row.get("created_at"), 40)
                    lines.append(str(pos) + ". " + icon + " " + label + ((" · " + when) if when else ""))
                return "\n".join(lines)

        events = self.local.mission_events(160)
        if code:
            events = [x for x in events if str(x.get("job_code") or x.get("job_id") or "") == code]
        if not events:
            return "📋 Journal des micro-actions\nAucun événement durable observé."
        lines = ["📋 Journal des micro-actions vérifiables"]
        for pos, ev in enumerate(events[-10:], 1):
            state = clean(ev.get("state") or "EVENT", 30)
            step = clean(ev.get("action_summary") or ev.get("step_summary") or ev.get("step_id") or "Micro-action", 140)
            lines.append(str(pos) + ". " + state + " — " + step)
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

    def help(self) -> str:
        return (
            "BCP Cockpit — lecture simple\n"
            "/status — mission actuelle\n/missions — missions récentes\n/details — vue technique\n"
            "/report — PDF de suivi\n/reporttech — PDF technique\n"
            "/project <id>\n/job <code>\n/tail [code]\n/where [code]\n/last\n/ci\n/holds\n\n"
            "Les boutons du cockpit donnent accès aux vues utiles sans retaper les commandes. "
            "Les pourcentages portent seulement sur des plans finis et vérifiables. "
            "Aucun état interne ou chaîne de pensée ChatGPT n’est lu."
        )

    def dispatch(self, text: str) -> str:
        raw = (text or "").strip()
        if not raw:
            return self.help()
        first, *rest = raw.split(maxsplit=1)
        cmd = first.split("@", 1)[0].lower()
        arg = rest[0].strip() if rest else ""
        if cmd not in READ_ONLY_COMMANDS:
            return "Lecture seule: /status /missions /details /report /reporttech /project <id> /job <code> /tail [code] /where [code] /last /ci /holds"
        if cmd in {"/start", "/help"}:
            return self.help()
        if cmd == "/status":
            return self.status()
        if cmd == "/missions":
            return self.missions()
        if cmd == "/details":
            return self.details()
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
        return {
            "inline_keyboard": [
                [
                    {"text": "🔄 Actualiser", "callback_data": "bcp:status"},
                    {"text": "📍 Étape", "callback_data": "bcp:where"},
                ],
                [
                    {"text": "📋 Micro-actions", "callback_data": "bcp:tail"},
                    {"text": "🗂 Missions", "callback_data": "bcp:missions"},
                ],
                [
                    {"text": "🧾 Détails", "callback_data": "bcp:details"},
                    {"text": "📄 PDF suivi", "callback_data": "bcp:pdf:summary"},
                ],
                [
                    {"text": "📚 PDF technique", "callback_data": "bcp:pdf:technical"},
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

    def send(self, text: str, with_keyboard: bool = True) -> int | None:
        payload = {
            "chat_id": self.chat_id,
            "text": redact_text(text)[:3900],
            "disable_web_page_preview": True,
        }
        if with_keyboard:
            payload["reply_markup"] = self.keyboard()
        obj = self.api("sendMessage", payload, 20)
        result = obj.get("result") or {}
        try:
            return int(result.get("message_id"))
        except Exception:
            return None

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
            "bcp:status": ("/status", "Actualisation"),
            "bcp:where": ("/where", "Position"),
            "bcp:tail": ("/tail", "Micro-actions"),
            "bcp:missions": ("/missions", "Missions"),
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
            self.answer_callback(callback_id, "Préparation du PDF…")
            self.send_document("BCP_SUIVI.pdf", self.service.report_pdf(False), "BCP — rapport de suivi")
            return
        if data == "bcp:pdf:technical":
            self.answer_callback(callback_id, "Préparation du PDF technique…")
            self.send_document("BCP_DETAILS_TECHNIQUES.pdf", self.service.report_pdf(True), "BCP — rapport technique")
            return
        command, label = self._callback_action(data)
        if not command:
            self.answer_callback(callback_id, "Action inconnue")
            return
        self.answer_callback(callback_id, label)
        response = self.service.dispatch(command)
        message_id = msg.get("message_id")
        if message_id and command in {"/status", "/where", "/tail", "/missions", "/details"}:
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
            skipped = max(0, len(relevant) - self.max_events_per_push)
            selected = relevant[-self.max_events_per_push:]
            blocks = []
            if skipped:
                blocks.append("ℹ️ " + str(skipped) + " micro-actions précédentes regroupées.")
            blocks.extend(self.service.progress_event(e) for e in selected)
            self.send("\n\n".join(blocks))
        atomic_json(PRESENCE_PATH, {
            "schema": "bcp.telegram_presence/1",
            "mission_event_key": newest_key,
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
        if message_id:
            try:
                updated = self.edit(int(message_id), str(snap["text"]))
            except Exception:
                updated = False
        if not updated:
            message_id = self.send(str(snap["text"]))
        atomic_json(path, {
            "schema": "bcp.telegram_system_presence/2",
            "fingerprint": snap["fingerprint"],
            "updated_at": utc_now(),
            "transport": "DIRECT_TELEGRAM",
            "message_id": message_id,
        })

    def run(self) -> int:
        offset = int((read_json(OFFSET_PATH, {}) or {}).get("next_offset") or 0)
        backoff = [2, 5, 15, 30, 60]
        failures = 0
        append_log("WORKER_STARTED")
        while True:
            try:
                obj = self.api("getUpdates", {
                    "offset": offset, "timeout": 20, "allowed_updates": ["message", "callback_query"]
                }, 35)
                failures = 0
                for upd in obj.get("result") or []:
                    uid = int(upd.get("update_id") or 0)
                    offset = max(offset, uid + 1)
                    callback = upd.get("callback_query")
                    if isinstance(callback, dict):
                        append_log("CALLBACK_UPDATE", update_id=uid, callback_data=clean(callback.get("data"), 80))
                        self.handle_callback(callback)
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
                    atomic_json(OFFSET_PATH, {
                        "schema": "bcp.telegram_offset/1", "next_offset": offset, "updated_at": utc_now()
                    })
                if not (obj.get("result") or []):
                    atomic_json(OFFSET_PATH, {
                        "schema": "bcp.telegram_offset/1", "next_offset": offset, "updated_at": utc_now()
                    })
                self._push_presence()
                self._push_system_presence()
            except KeyboardInterrupt:
                append_log("WORKER_STOPPED")
                return 0
            except (URLError, TimeoutError, OSError, RuntimeError) as e:
                delay = backoff[min(failures, len(backoff) - 1)]
                failures += 1
                append_log("RETRY", error_class=type(e).__name__, retry_seconds=delay)
                time.sleep(delay)
            except Exception as e:
                append_log("HOLD", error_class=type(e).__name__, detail=clean(e, 140))
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

    def push(self, text: str, idem_seed: str) -> None:
        safe_text = redact_text(text)[:3900]
        idem = hashlib.sha256(("push:" + idem_seed).encode("utf-8")).hexdigest()
        self.api("/v1/device/push", method="POST", payload={
            "kind": "MISSION_PROGRESS",
            "text": safe_text,
            "idempotency_key": idem,
        }, timeout=25)

    def live_card(self, text: str, card_key: str = "mission-status") -> None:
        safe_text = redact_text(text)[:3900]
        self.api("/v1/device/live-card", method="POST", payload={
            "card_key": clean(card_key, 96),
            "text": safe_text,
        }, timeout=25)

    def publish_reports(self) -> None:
        summary = redact_text(self.service.report_summary())[:18000]
        technical = redact_text(self.service.report_technical())[:26000]
        self.api("/v1/device/report", method="POST", payload={
            "summary": summary,
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

    def _push_system_presence(self) -> None:
        if not self.auto_push:
            return
        snap = self.service.presence_snapshot()
        path = self.service.local.state / SYSTEM_PRESENCE_PATH.name
        prior = read_json(path, {}) or {}
        if str(prior.get("fingerprint") or "") == str(snap["fingerprint"]):
            return
        self.publish_reports()
        self.live_card(str(snap["text"]), "mission:" + self.service.project_id)
        atomic_json(path, {
            "schema": "bcp.telegram_system_presence/2",
            "fingerprint": snap["fingerprint"],
            "updated_at": utc_now(),
            "transport": "NEXUS",
            "card_key": "mission:" + self.service.project_id,
        })

    def run(self) -> int:
        cursor = int((read_json(NEXUS_CURSOR_PATH, {}) or {}).get("last_command_id") or 0)
        backoff = [2, 5, 15, 30, 60]
        failures = 0
        append_log("NEXUS_WORKER_STARTED", device_id=self.device_id)
        while True:
            try:
                obj = self.api(
                    "/v1/device/commands?after=" + str(cursor) + "&limit=8",
                    timeout=20,
                )
                commands = obj.get("commands") or []
                failures = 0
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
                    cursor = command_id
                    atomic_json(NEXUS_CURSOR_PATH, {
                        "schema": "bcp.nexus_cursor/1",
                        "last_command_id": cursor,
                        "updated_at": utc_now(),
                    })
                    append_log("NEXUS_COMMAND_REPLIED", command_id=command_id)
                self._push_presence()
                self._push_system_presence()
                if not commands:
                    time.sleep(self.poll_seconds)
            except KeyboardInterrupt:
                append_log("NEXUS_WORKER_STOPPED")
                return 0
            except (URLError, TimeoutError, OSError, RuntimeError) as e:
                delay = backoff[min(failures, len(backoff) - 1)]
                failures += 1
                append_log("NEXUS_RETRY", error_class=type(e).__name__, retry_seconds=delay)
                time.sleep(delay)
            except Exception as e:
                append_log("NEXUS_HOLD", error_class=type(e).__name__, detail=clean(e, 140))
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
        assert "🤖 BCP Cockpit" in status
        assert "🎯 Micro-action actuelle: Lancer le test Windows Bootstrap" in status
        assert "📊 Progression: █████░░░░░ 50% — 2/4 micro-actions vérifiées" in status
        assert "✅ Dernière micro-action terminée: Vérifier le commit de la PR" in status
        assert "➡️ Prochaine micro-action: Lire le journal du test Windows" in status
        assert "Ancien téléphone" in status
        assert "💰 Coût: $0.00" not in status
        assert "👤 Action pour vous: AUCUNE" in status
        assert "🕒 Dernière preuve:" in status
        assert "🧪 ✅ tests réussis" in status
        assert "1. ✅ Lire le cahier des charges courant" in svc.plan_view()
        assert "3. ▶️ Lancer le test Windows Bootstrap" in svc.plan_view()
        presence = svc.presence_snapshot()
        assert len(presence["fingerprint"]) == 64
        assert "🤖 BCP Cockpit" in presence["text"]
        assert "Ancien téléphone" in presence["text"]
        details = svc.details()
        assert "État global: EN_COURS" in details
        assert "GitHub CI: Windows=SUCCESS [work/test]" in details
        assert "B-EDGE: PAIRED / PHONE_HEARTBEAT" in details
        assert "48273195" in svc.job("48273195")
        assert "Vérifier le commit de la PR" in svc.tail()
        assert "Lancer le test Windows Bootstrap" in svc.tail()
        assert "étape enregistrée" in svc.where("48273195")
        assert "WAITING_FOR_PC" in svc.holds()
        assert "Missions récentes" in svc.missions()
        assert "Lecture seule" in svc.dispatch("/run")
        assert svc.dispatch("/report") == "REPORT_PDF_SUMMARY"
        assert svc.dispatch("/reporttech") == "REPORT_PDF_TECHNICAL"
        summary_pdf = svc.report_pdf(False)
        technical_pdf = svc.report_pdf(True)
        assert summary_pdf.startswith(b"%PDF-1.4")
        assert technical_pdf.startswith(b"%PDF-1.4")
        assert summary_pdf.rstrip().endswith(b"%%EOF")
        assert technical_pdf.rstrip().endswith(b"%%EOF")
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
            "bcp:status", "bcp:where", "bcp:tail", "bcp:missions", "bcp:details",
            "bcp:pdf:summary", "bcp:pdf:technical",
        } <= callback_values
        assert "chaîne de pensée" in svc.help()
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
