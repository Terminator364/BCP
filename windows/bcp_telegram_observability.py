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
    s = str("" if value is None else value)
    s = TOKEN_RE.sub("[REDACTED_TOKEN]", s)
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
        try:
            cx = sqlite3.connect("file:" + self.db.as_posix() + "?mode=ro", uri=True, timeout=2)
            cx.row_factory = sqlite3.Row
            rows = [dict(x) for x in cx.execute(sql, args).fetchall()]
            cx.close()
            return rows
        except Exception:
            return []

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
        mission_state = str(ev.get("state") or "NOT_OBSERVED").upper()
        action = clean(
            ev.get("action_summary") or ev.get("step_summary") or ev.get("step_id") or
            "Aucune micro-action durable récente.",
            150,
        )
        next_action = self._human_action(
            ev.get("next_safe_action") or "Relire l’état sauvegardé avant de reprendre."
        )
        age = self._event_age_seconds(ev)
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
        if mission_state in HOLD_STATES:
            activity_band = "HOLD"

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
        }.get(nexus, "⚪ relais Nexus non observé")

        evidence_time = self._event_timestamp(ev) or "non observée"
        last_completed = self._last_completed_action(events, ev)
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
            activity = "🟡 Pas de nouvelle preuve depuis " + age_label + ". Je surveille sans conclure à un blocage."
        elif activity_band == "STALE":
            activity = "🟠 Pas de nouvelle preuve depuis " + age_label + ". La liaison doit être revérifiée."
        else:
            activity = "⚪ Progression récente non observée."

        lines = [
            "🤖 BCP — suivi de mission",
            activity,
            "",
            "🎯 Maintenant: " + action,
            "📊 " + progress,
            "✅ Dernière étape terminée: " + last_completed,
            "➡️ Ensuite: " + next_action,
            "👤 Action pour vous: " + human_gate,
            "",
            "🕒 Preuve observée: " + evidence_time,
            "⏱️ Âge de la preuve à l’envoi: " + age_label,
            "📨 Carte générée: " + rendered_at,
            "",
            ("✅ PC/BCP actif" if heartbeat_ok else "⚠️ PC/BCP: preuve récente absente"),
            ("✅ Ancien téléphone actif" if edge_ok else ("🟡 Ancien téléphone appairé, preuve récente absente" if edge.get("paired") else "⚠️ Ancien téléphone non observé")),
            ("✅ Sauvegarde Drive visible" if drive_ok else "⚠️ Sauvegarde Drive non observée"),
            "🌐 " + nexus_text,
            "🧪 " + self._human_ci(gh),
            "",
            "🔧 Détails techniques: /details",
        ]
        return {"fingerprint": digest, "text": "\n".join(lines), "snapshot": stable}

    def status(self) -> str:
        runtime = self.local.runtime()
        edge = self.local.edge()
        gh = self.github.snapshot()
        drive = self.local.drive()
        chat = self.local.chat(self.project_id)
        events = [
            e for e in self.local.mission_events(160)
            if not e.get("project_id") or str(e.get("project_id")) == self.project_id
        ]
        ev = events[-1] if events else {}
        mission_state = str(ev.get("state") or "NOT_OBSERVED").upper()
        action = clean(
            ev.get("action_summary") or ev.get("step_summary") or ev.get("step_id") or
            "Aucune micro-action durable récente.",
            150,
        )
        next_action = self._human_action(
            ev.get("next_safe_action") or "Relire l’état sauvegardé avant de reprendre."
        )
        age = self._event_age_seconds(ev)
        if age is None:
            age = self.local.mission_activity_age()
        age_label = self._age_label(age)

        progress = "Étape: " + mission_state.replace("_", " ").lower()
        try:
            idx = int(ev.get("step_index"))
            total = int(ev.get("step_total"))
            if 0 <= idx <= total and total > 0:
                pct = int(round(idx * 100 / total))
                progress = self._bar(idx, total) + " " + str(pct) + "% — étape " + str(idx) + "/" + str(total)
        except Exception:
            pass

        if mission_state in HOLD_STATES:
            activity = "🟠 En attente d’un élément externe ou d’une reprise."
        elif isinstance(age, int) and age <= 120:
            activity = "🟢 Activité récente."
        elif isinstance(age, int) and age <= 600:
            activity = "🟡 Aucune nouvelle preuve depuis " + age_label + ". Réseau, CI ou service externe peuvent être en attente."
        elif isinstance(age, int):
            activity = "🟠 Aucune nouvelle preuve depuis " + age_label + ". La liaison doit être revérifiée avant de conclure à un blocage."
        else:
            activity = "⚪ Âge de la dernière preuve non observé."

        hb = runtime.get("_age_seconds")
        heartbeat_ok = isinstance(hb, int) and hb <= 180
        edge_age = edge.get("_age_seconds")
        edge_ok = bool(edge.get("paired")) and isinstance(edge_age, int) and edge_age <= 300
        github_ok = bool(gh.get("ok"))
        drive_ok = str(drive.get("status") or "").upper() == "OBSERVED"
        nexus = str(runtime.get("nexus_bootstrap_state") or "NOT_OBSERVED").upper()
        nexus_text = {
            "COMMITTED": "✅ actif",
            "NEXUS_DEPLOYED_LOCAL_WORKER_RUNNING": "✅ actif",
            "EXITED_NO_RECEIPT": "🟡 reprise automatique à réparer",
            "WRANGLER_RUNTIME_REQUIRED": "🟡 préparation en cours",
        }.get(nexus, "⚪ " + clean(nexus, 45).replace("_", " ").lower())

        chat_state = str(chat.get("state") or "UNKNOWN_INTERNAL_CHAT_STATE")
        chat_text = {
            "OBSERVED_CHAT_ACTION": "✅ action externe observée",
            "CHAT_WAITING": "⏳ réponse en attente",
            "CHAT_PLATFORM_HOLD_REPORTED": "🟠 vérification ChatGPT signalée",
            "UNKNOWN_INTERNAL_CHAT_STATE": "⚪ activité interne non visible",
        }.get(chat_state, "⚪ " + clean(chat_state, 60))

        evidence_time = self._event_timestamp(ev) or "non observée"
        last_completed = self._last_completed_action(events, ev)
        human_gate = self._human_gate(ev, next_action)
        rendered_at = utc_now()
        return "\n".join([
            "🤖 BCP Cockpit — " + self.project_id,
            activity,
            "",
            "🎯 Maintenant: " + action,
            "📊 " + progress,
            "✅ Dernière étape terminée: " + last_completed,
            "➡️ Ensuite: " + next_action,
            "👤 Action pour vous: " + human_gate,
            "",
            "🕒 Preuve observée: " + evidence_time,
            "⏱️ Âge de la preuve à l’envoi: " + age_label,
            "📨 Réponse générée: " + rendered_at,
            "",
            ("✅ PC/BCP" if heartbeat_ok else "⚠️ PC/BCP — preuve récente absente"),
            ("✅ Ancien téléphone — actif" if edge_ok else ("🟡 Ancien téléphone — appairé, preuve récente absente" if edge.get("paired") else "⚠️ Ancien téléphone — non observé")),
            ("✅ GitHub" if github_ok else "⚠️ GitHub — non observé"),
            ("✅ Sauvegarde Drive" if drive_ok else "⚠️ Sauvegarde Drive — non observée"),
            "🌐 Relais Nexus: " + nexus_text,
            "ChatGPT: " + chat_text,
            "🧪 " + self._human_ci(gh),
            "",
            "ℹ️ Le cockpit montre les micro-actions et preuves externes; il ne prétend pas lire la réflexion privée de ChatGPT.",
            "🔧 Détails techniques: /details",
        ])

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
            "BCP — Rapport de suivi",
            "Généré: " + utc_now(),
            "",
            self.status(),
        ])

    def report_technical(self) -> str:
        return "\n".join([
            "BCP — Rapport technique",
            "Généré: " + utc_now(),
            "",
            self.details(),
            "",
            "MICRO-ACTIONS",
            self.tail(),
            "",
            "MISSIONS",
            self.missions(),
        ])

    def report_pdf(self, technical: bool = False) -> bytes:
        body = self.report_technical() if technical else self.report_summary()
        title = "BCP Rapport technique" if technical else "BCP Rapport de suivi"
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
        events = self.local.mission_events(160)
        if code:
            events = [x for x in events if str(x.get("job_code") or x.get("job_id") or "") == code]
        if not events:
            return "Aucun événement durable observé."
        lines = ["Dernières micro-actions vérifiables"]
        for ev in events[-8:]:
            state = clean(ev.get("state") or "EVENT", 30)
            step = clean(ev.get("action_summary") or ev.get("step_id") or "", 95)
            lines.append("• " + state + ((" — " + step) if step else ""))
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

    def api(self, method: str, payload: dict, timeout: int) -> dict:
        status, obj = self.http.json(
            self.base + "/" + method, method="POST", payload=payload, timeout=timeout
        )
        if status != 200 or not isinstance(obj, dict) or not obj.get("ok"):
            desc = clean(obj.get("description") if isinstance(obj, dict) else "http_" + str(status), 140)
            raise RuntimeError("telegram_api_error:" + desc)
        return obj

    def send(self, text: str) -> int | None:
        obj = self.api("sendMessage", {
            "chat_id": self.chat_id,
            "text": TOKEN_RE.sub("[REDACTED_TOKEN]", text)[:3900],
            "disable_web_page_preview": True,
        }, 20)
        result = obj.get("result") or {}
        try:
            return int(result.get("message_id"))
        except Exception:
            return None

    def edit(self, message_id: int, text: str) -> bool:
        try:
            self.api("editMessageText", {
                "chat_id": self.chat_id,
                "message_id": int(message_id),
                "text": TOKEN_RE.sub("[REDACTED_TOKEN]", text)[:3900],
                "disable_web_page_preview": True,
            }, 20)
            return True
        except Exception as e:
            append_log("LIVE_CARD_EDIT_FAILED", error_class=type(e).__name__, detail=clean(e, 140))
            return False

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
                    "offset": offset, "timeout": 20, "allowed_updates": ["message"]
                }, 35)
                failures = 0
                for upd in obj.get("result") or []:
                    uid = int(upd.get("update_id") or 0)
                    offset = max(offset, uid + 1)
                    msg = upd.get("message") or {}
                    chat = msg.get("chat") or {}
                    incoming = int(chat.get("id") or 0)
                    authorized = incoming == self.chat_id and str(chat.get("type") or "") == "private"
                    append_log("UPDATE", update_id=uid, authorized=authorized)
                    if authorized:
                        self.send(self.service.dispatch(str(msg.get("text") or "")))
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
        safe_text = TOKEN_RE.sub("[REDACTED_TOKEN]", text)[:3900]
        idem = hashlib.sha256(
            ("reply:" + str(command_id) + ":" + safe_text).encode("utf-8")
        ).hexdigest()
        self.api("/v1/device/reply", method="POST", payload={
            "command_id": int(command_id),
            "text": safe_text,
            "idempotency_key": idem,
        }, timeout=25)

    def push(self, text: str, idem_seed: str) -> None:
        safe_text = TOKEN_RE.sub("[REDACTED_TOKEN]", text)[:3900]
        idem = hashlib.sha256(("push:" + idem_seed).encode("utf-8")).hexdigest()
        self.api("/v1/device/push", method="POST", payload={
            "kind": "MISSION_PROGRESS",
            "text": safe_text,
            "idempotency_key": idem,
        }, timeout=25)

    def live_card(self, text: str, card_key: str = "mission-status") -> None:
        safe_text = TOKEN_RE.sub("[REDACTED_TOKEN]", text)[:3900]
        self.api("/v1/device/live-card", method="POST", payload={
            "card_key": clean(card_key, 96),
            "text": safe_text,
        }, timeout=25)

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
        assert "🎯 Maintenant:" in status
        assert "Ancien téléphone" in status
        assert "ChatGPT: ⏳ réponse en attente" in status
        assert "💰 Coût: $0.00" not in status
        assert "👤 Action pour vous: AUCUNE" in status
        assert "🕒 Preuve observée:" in status
        assert "🧪 ✅ tests réussis" in status
        presence = svc.presence_snapshot()
        assert len(presence["fingerprint"]) == 64
        assert "🤖 BCP — suivi" in presence["text"]
        assert "Ancien téléphone" in presence["text"]
        details = svc.details()
        assert "État global: EN_COURS" in details
        assert "GitHub CI: Windows=SUCCESS [work/test]" in details
        assert "B-EDGE: PAIRED / PHONE_HEARTBEAT" in details
        assert "48273195" in svc.job("48273195")
        assert "CI patch persisted" in svc.tail("48273195")
        assert "étape enregistrée" in svc.where("48273195")
        assert "WAITING_FOR_PC" in svc.holds()
        assert "Missions récentes" in svc.missions()
        assert "Lecture seule" in svc.dispatch("/run")
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
