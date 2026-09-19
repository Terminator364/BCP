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
READ_ONLY_COMMANDS = {
    "/start", "/help", "/status", "/details", "/project", "/job", "/last", "/ci", "/holds",
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
        evs = last_jsonl(self.telemetry / "phone-events.jsonl", 5)
        last = evs[-1] if evs else {}
        return {
            "paired": bool(pair),
            "edge_version": clean(pair.get("edge_version"), 40),
            "last_event": clean(last.get("event_type") or last.get("type"), 80),
        }

    def mission_events(self, limit: int = 80) -> list[dict]:
        return [
            x for x in last_jsonl(self.state / "MISSION_EVENT_LOG.jsonl", limit)
            if str(x.get("state") or "").upper() in MISSION_STATES
        ]

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

    def status(self) -> str:
        head = self._head()
        runtime = self.local.runtime()
        edge = self.local.edge()
        gh = self.github.snapshot()
        drive = self.local.drive()
        chat = self.local.chat(self.project_id)

        hb = runtime.get("_age_seconds")
        heartbeat_ok = isinstance(hb, int) and hb <= 180
        edge_ok = bool(edge.get("paired"))
        github_ok = bool(gh.get("ok"))
        drive_ok = str(drive.get("status") or "").upper() == "OBSERVED"
        checks = [heartbeat_ok, edge_ok, github_ok, drive_ok]
        done = sum(1 for x in checks if x)
        total = len(checks)
        percent = int(round(done * 100 / total)) if total else 0

        global_state = str(
            (head or {}).get("status") or runtime.get("recovery_phase") or runtime.get("status") or "UNKNOWN"
        ).upper()
        if "HEALTH" in global_state or "UP_TO_DATE" in global_state:
            state_label = "🟢 Système actif"
        elif "HOLD" in global_state or "BLOCK" in global_state or "FAIL" in global_state:
            state_label = "🔴 Attention requise"
        else:
            state_label = "🟡 Actif / état partiellement observé"

        chat_state = str(chat.get("state") or "UNKNOWN_INTERNAL_CHAT_STATE")
        chat_labels = {
            "OBSERVED_CHAT_ACTION": "✅ action externe observée",
            "CHAT_WAITING": "⏳ réponse en attente",
            "CHAT_PLATFORM_HOLD_REPORTED": "🟠 vérification ChatGPT signalée",
            "UNKNOWN_INTERNAL_CHAT_STATE": "⚪ état interne non visible",
        }
        next_action = clean(
            (head or {}).get("next_action") or "continuer depuis le dernier checkpoint durable",
            170,
        )
        latest_ci = self._ci(gh)
        return "\n".join([
            "🤖 BCP Cockpit",
            state_label,
            "",
            "Progression vérifiable des liaisons",
            self._bar(done, total) + "  " + str(percent) + "% (" + str(done) + "/" + str(total) + ")",
            "",
            ("✅" if heartbeat_ok else "⚠️") + " PC/BCP",
            ("✅" if edge_ok else "⚠️") + " Téléphone B-EDGE",
            ("✅" if github_ok else "⚠️") + " GitHub",
            ("✅" if drive_ok else "⚠️") + " Sauvegarde Drive",
            "",
            "ChatGPT: " + chat_labels.get(chat_state, "⚪ " + clean(chat_state, 60)),
            "Tests: " + clean(latest_ci, 110),
            "",
            "➡️ Prochaine étape: " + next_action,
            "💰 Coût: $0.00",
            "",
            "Détails techniques: /details",
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
            "/status — vue simple\n/details — vue technique\n"
            "/project <id>\n/job <code>\n/last\n/ci\n/holds\n\n"
            "Les pourcentages portent seulement sur des étapes ou liaisons vérifiables. "
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
            return "Lecture seule: /status /details /project <id> /job <code> /last /ci /holds"
        if cmd in {"/start", "/help"}:
            return self.help()
        if cmd == "/status":
            return self.status()
        if cmd == "/details":
            return self.details()
        if cmd == "/project":
            return self.project(arg)
        if cmd == "/job":
            return self.job(arg)
        if cmd == "/last":
            return self.last()
        if cmd == "/ci":
            return self.ci()
        return self.holds()


class Telegram:
    def __init__(self, token: str, chat_id: int, service: Service, http: Http | None = None):
        self.token = token
        self.chat_id = int(chat_id)
        self.service = service
        self.http = http or Http()
        self.base = "https://api.telegram.org/bot" + token

    def api(self, method: str, payload: dict, timeout: int) -> dict:
        status, obj = self.http.json(
            self.base + "/" + method, method="POST", payload=payload, timeout=timeout
        )
        if status != 200 or not isinstance(obj, dict) or not obj.get("ok"):
            desc = clean(obj.get("description") if isinstance(obj, dict) else "http_" + str(status), 140)
            raise RuntimeError("telegram_api_error:" + desc)
        return obj

    def send(self, text: str) -> None:
        self.api("sendMessage", {
            "chat_id": self.chat_id,
            "text": TOKEN_RE.sub("[REDACTED_TOKEN]", text)[:3900],
            "disable_web_page_preview": True,
        }, 20)

    def run(self) -> int:
        offset = int((read_json(OFFSET_PATH, {}) or {}).get("next_offset") or 0)
        backoff = [2, 5, 15, 30, 60]
        failures = 0
        append_log("WORKER_STARTED")
        while True:
            try:
                obj = self.api("getUpdates", {
                    "offset": offset, "timeout": 50, "allowed_updates": ["message"]
                }, 65)
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
    token = TOKEN_PATH.read_text(encoding="utf-8").strip() if TOKEN_PATH.is_file() else ""
    cfg = read_json(CONFIG_PATH, {}) or {}
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
        assert "Progression vérifiable des liaisons" in status
        assert "Téléphone B-EDGE" in status
        assert "ChatGPT: ⏳ réponse en attente" in status
        assert "💰 Coût: $0.00" in status
        details = svc.details()
        assert "État global: EN_COURS" in details
        assert "GitHub CI: Windows=SUCCESS [work/test]" in details
        assert "B-EDGE: PAIRED / PHONE_HEARTBEAT" in details
        assert "48273195" in svc.job("48273195")
        assert "WAITING_FOR_PC" in svc.holds()
        assert "MVP read-only" in svc.dispatch("/run")
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
    return Telegram(token, int(cfg["allowed_chat_id"]), svc).run()


if __name__ == "__main__":
    raise SystemExit(main())
