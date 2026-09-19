from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

APP_ROOT = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ChatGPT_ManagedApps" / "bcp"
STATE_DIR = APP_ROOT / "state"
TELEMETRY_DIR = APP_ROOT / "telemetry"
DB_PATH = STATE_DIR / "bcp.sqlite3"
TOKEN_PATH = STATE_DIR / "bcp_token.txt"
PAIR_PATH = STATE_DIR / "paired_edge.json"
SERVER_VERSION = "0.4.4"
SERVER_FILE = Path(__file__).resolve()
UPDATE_MANIFEST_URL = "https://raw.githubusercontent.com/Terminator364/BCP/main/release/server.json"
AUTO_UPDATE_INTERVAL_SECONDS = 6 * 60 * 60
EXTERNAL_HEARTBEAT_INTERVAL_SECONDS = 45
DB_LOCK = threading.RLock()
UPDATE_LOCK = threading.RLock()


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


def chatgpt_control_folder():
    override = os.environ.get("BCP_CONTROL_FOLDER", "").strip()
    if override:
        p = Path(override)
        return p if p.exists() else None
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    cfg = read_json(local / "Tunnel_PC_G4" / "state" / "config.json", {}) or {}
    raw = str(cfg.get("control_folder") or "").strip()
    if not raw:
        return None
    p = Path(raw)
    return p if p.exists() else None


def mirror_telemetry_status(event_type: str, extra: dict | None = None) -> bool:
    """Mirror a sanitized BCP status into ChatGPT-PC's Drive control plane.

    Never writes bearer tokens, raw request bodies, or arbitrary telemetry detail.
    This is the machine-readable path ChatGPT can read without screenshots.
    """
    control = chatgpt_control_folder()
    if control is None:
        return False
    root = control / "03_TELEMETRY" / "BCP"
    root.mkdir(parents=True, exist_ok=True)
    pair = read_json(PAIR_PATH, {}) or {}
    rec = {
        "schema": "bcp.telemetry.bridge/1",
        "event_type": str(event_type)[:80],
        "server_version": SERVER_VERSION,
        "pc_name": os.environ.get("COMPUTERNAME", "BCP-PC"),
        "updated_at": utc_now(),
        "paired": bool(pair),
        "device_name": str(pair.get("device_name") or "")[:120],
        "edge_version": str(pair.get("edge_version") or "")[:40],
        "project": str(pair.get("project") or "")[:128],
    }
    allowed = {
        "accepted", "last_event_type", "last_event_ts", "status", "revision",
        "target_version", "update_result", "auto_update",
        "chatgpt_pc_version", "chatgpt_pc_sequence", "recovery_state"
    }
    if isinstance(extra, dict):
        for k in allowed:
            if k in extra:
                v = extra[k]
                rec[k] = v if isinstance(v, (bool, int, float)) or v is None else str(v)[:160]
    atomic_json(root / "BCP_LATEST.json", rec)
    with (root / "BCP_EVENTS.jsonl").open("a", encoding="utf-8") as f:
        f.write(canonical_json(rec) + "\n")
    return True



def lifecycle_registration_status() -> dict:
    if os.name != "nt":
        return {"supported": False, "registered": False, "reason": "non_windows"}
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        value_name = "BlessingControlPlane"
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        launcher = pythonw if pythonw.is_file() else Path(sys.executable)
        command = f'"{launcher}" "{SERVER_FILE}" --bind 0.0.0.0 --port 8765'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            try:
                current, _ = winreg.QueryValueEx(key, value_name)
            except FileNotFoundError:
                current = ""
        return {
            "supported": True,
            "registered": str(current) == command,
            "value_name": value_name,
            "launcher": str(launcher),
        }
    except Exception as e:
        return {"supported": True, "registered": False, "error": str(e)[:240]}


def ensure_lifecycle_registration() -> dict:
    """Ensure the same BCP managed app starts again at user logon.

    This is a lifecycle launcher only: it does not create a second control plane
    or a second resident service. Registration is per-user and idempotent.
    """
    if os.name != "nt":
        return {"supported": False, "registered": False, "reason": "non_windows"}
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        value_name = "BlessingControlPlane"
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        launcher = pythonw if pythonw.is_file() else Path(sys.executable)
        command = f'"{launcher}" "{SERVER_FILE}" --bind 0.0.0.0 --port 8765'
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_WRITE
        ) as key:
            current = ""
            try:
                current, _ = winreg.QueryValueEx(key, value_name)
            except FileNotFoundError:
                pass
            if str(current) != command:
                winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, command)
        return {
            "supported": True,
            "registered": True,
            "value_name": value_name,
            "launcher": str(launcher),
        }
    except Exception as e:
        return {"supported": True, "registered": False, "error": str(e)[:240]}


def external_telemetry_roots() -> list[Path]:
    """Return safe external folders where sanitized runtime truth can be mirrored.

    This path is intentionally independent from the ChatGPT-PC interactive
    channel. Missing/unmounted candidates are ignored without blocking BCP.
    """
    roots: list[Path] = []
    override = os.environ.get("BCP_EXTERNAL_TELEMETRY_DIR", "").strip()
    if override:
        roots.append(Path(override))

    candidates = [
        # Canonical API/BCP Drive tree. Keep this first.
        Path(r"G:\\Mon Drive\\API_BCP\\02_TELEMETRY\\BCP"),
        Path(r"G:\\My Drive\\API_BCP\\02_TELEMETRY\\BCP"),
        Path.home() / "My Drive" / "API_BCP" / "02_TELEMETRY" / "BCP",
        Path.home() / "Mon Drive" / "API_BCP" / "02_TELEMETRY" / "BCP",
        # Legacy compatibility while older ChatGPT-PC layouts are still present.
        Path(r"G:\\Mon Drive\\CHATGPT_PC_AGENT\\03_TELEMETRY\\BCP"),
        Path(r"G:\\My Drive\\CHATGPT_PC_AGENT\\03_TELEMETRY\\BCP"),
        Path.home() / "My Drive" / "CHATGPT_PC_AGENT" / "03_TELEMETRY" / "BCP",
        Path.home() / "Mon Drive" / "CHATGPT_PC_AGENT" / "03_TELEMETRY" / "BCP",
    ]
    for p in candidates:
        try:
            parent = p
            while not parent.exists() and parent.parent != parent:
                parent = parent.parent
            if parent.exists():
                roots.append(p)
        except Exception:
            pass

    # Existing control folder remains a valid mirror if it is present, but is
    # not required for the external heartbeat.
    control = chatgpt_control_folder()
    if control is not None:
        roots.append(control / "03_TELEMETRY" / "BCP")

    dedup: list[Path] = []
    seen = set()
    for p in roots:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            dedup.append(p)
    return dedup


def mirror_external_runtime_status(reason: str = "PERIODIC_HEARTBEAT") -> list[str]:
    """Publish sanitized runtime truth to any available synced external folder."""
    update = read_json(STATE_DIR / "server_update.json", {}) or {}
    chat = chatgpt_pc_status()
    rec = {
        "schema": "bcp.external_runtime/1",
        "reason": str(reason)[:80],
        "server_version": SERVER_VERSION,
        "server_pid": os.getpid(),
        "pc_name": os.environ.get("COMPUTERNAME", "BCP-PC"),
        "updated_at": utc_now(),
        "paired": PAIR_PATH.exists(),
        "server_file": str(SERVER_FILE),
        "server_sha256": hashlib.sha256(SERVER_FILE.read_bytes()).hexdigest(),
        "update_state": str(update.get("state") or "NONE")[:80],
        "update_target_version": str(update.get("target_version") or "")[:40],
        "chatgpt_pc_active_version": str(chat.get("active_version") or "")[:40],
        "chatgpt_pc_active_sequence": int(chat.get("active_sequence") or 0),
        "chatgpt_pc_heartbeat_version": str(chat.get("heartbeat_version") or "")[:40],
        "chatgpt_pc_heartbeat_age_seconds": chat.get("heartbeat_age_seconds"),
        "chatgpt_pc_command_plane": str(chat.get("command_plane") or "")[:80],
        "chatgpt_pc_command_plane_age_seconds": chat.get("command_plane_age_seconds"),
        "recovery_phase": str(chat.get("recovery_phase") or "")[:80],
        "recovery_result_status": str(chat.get("recovery_result_status") or "")[:80],
        "lifecycle_registration": lifecycle_registration_status(),
    }
    written: list[str] = []
    for root in external_telemetry_roots():
        try:
            root.mkdir(parents=True, exist_ok=True)
            atomic_json(root / "BCP_RUNTIME_LATEST.json", rec)
            with (root / "BCP_RUNTIME_EVENTS.jsonl").open("a", encoding="utf-8") as h:
                h.write(canonical_json(rec) + "\n")
            written.append(str(root))
        except Exception:
            continue
    return written


def start_external_heartbeat_worker() -> None:
    def worker():
        while True:
            try:
                mirror_external_runtime_status("PERIODIC_HEARTBEAT")
            except Exception:
                pass
            time.sleep(EXTERNAL_HEARTBEAT_INTERVAL_SECONDS)

    threading.Thread(target=worker, daemon=True, name="bcp-external-heartbeat").start()


def _file_age_seconds(path: Path) -> float | None:
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except Exception:
        return None


def chatgpt_pc_status() -> dict:
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    root = local / "Tunnel_PC_G4"
    active = read_json(root / "state" / "active_release.json", {}) or {}
    heartbeat = read_json(root / "state" / "heartbeat.json", {}) or {}
    command = read_json(root / "state" / "command_plane_health.json", {}) or {}
    control = chatgpt_control_folder()
    tick_path = (control / "RECOVERY" / "RECOVERY_PLANE_TICK.json") if control else None
    result_path = (control / "RECOVERY" / "RECOVERY_BOOTSTRAP_RESULT.json") if control else None
    tick = read_json(tick_path, {}) if tick_path else {}
    result = read_json(result_path, {}) if result_path else {}
    out = {
        "ok": bool(root.exists()),
        "install_root": str(root),
        "control_folder_present": bool(control),
        "active_version": str(active.get("version") or ""),
        "active_sequence": int(active.get("sequence") or 0),
        "heartbeat_version": str(heartbeat.get("agent_version") or ""),
        "heartbeat_age_seconds": _file_age_seconds(root / "state" / "heartbeat.json"),
        "command_plane_age_seconds": _file_age_seconds(root / "state" / "command_plane_health.json"),
        "command_plane": str(command.get("command_plane") or ""),
        "recovery_tick_age_seconds": _file_age_seconds(tick_path) if tick_path else None,
        "recovery_phase": str((tick or {}).get("phase") or ""),
        "recovery_result_status": str((result or {}).get("status") or ""),
        "recovery_result_version": str((result or {}).get("version") or ""),
        "recovery_result_sequence": int((result or {}).get("sequence") or 0),
    }
    return out


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def request_chatgpt_pc_recovery() -> dict:
    if os.name != "nt":
        raise RuntimeError("chatgpt_pc_recovery_requires_windows")
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    root = local / "Tunnel_PC_G4"
    py = root / "runtime" / "python.exe"
    control = chatgpt_control_folder()
    if not py.is_file():
        raise FileNotFoundError("chatgpt_pc_runtime_missing")
    if control is None:
        raise FileNotFoundError("chatgpt_pc_control_folder_missing")

    target_path = control / "00_CONTEXT" / "RECOVERY_BOOTSTRAP_TARGET.json"
    target = read_json(target_path, {}) or {}
    if target.get("status") != "ACTIVE":
        raise RuntimeError("recovery_target_not_active")
    target_version = str(target.get("version") or "")
    target_sequence = int(target.get("sequence") or 0)
    package_file = str(target.get("package_file") or "")
    package_sha = str(target.get("package_sha256") or "").lower()
    if not target_version or target_sequence < 1 or not package_file or Path(package_file).name != package_file:
        raise ValueError("recovery_target_invalid")
    package = control / "02_UPDATES" / "AGENT" / package_file
    if not package.is_file():
        raise FileNotFoundError("recovery_package_not_synced")
    actual = hashlib.sha256(package.read_bytes()).hexdigest()
    if len(package_sha) != 64 or not hmac.compare_digest(actual, package_sha):
        raise ValueError("recovery_package_sha256_mismatch")

    active = read_json(root / "state" / "active_release.json", {}) or {}
    release_root = Path(str(active.get("release_root") or ""))
    candidates = [
        control / "RECOVERY" / "recovery_update_runner_hotfix_6026.py",
        root / "recovery_update_runner.py",
        release_root / "tools" / "recovery_update_runner.py",
    ]
    runner = next((p for p in candidates if p.is_file()), None)
    if runner is None:
        raise FileNotFoundError("recovery_update_runner_missing")

    state_path = STATE_DIR / "chatgpt_pc_recovery_request.json"
    prior = read_json(state_path, {}) or {}
    prior_pid = int(prior.get("pid") or 0)
    prior_age = _file_age_seconds(state_path)
    if prior.get("status") == "STARTED" and prior_age is not None and prior_age < 90 and _process_alive(prior_pid):
        return {
            "ok": True, "result": "ALREADY_RUNNING", "pid": prior_pid,
            "target_version": target_version, "target_sequence": target_sequence
        }

    log_path = APP_ROOT / "logs" / "chatgpt-pc-recovery.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("ab", buffering=0)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(
        [str(py), str(runner), "--install", str(root), "--control", str(control)],
        cwd=str(root),
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=log,
        shell=False,
        creationflags=flags,
        close_fds=True,
    )
    rec = {
        "schema": "bcp.chatgpt_pc_recovery/1",
        "status": "STARTED",
        "pid": int(proc.pid),
        "started_at": utc_now(),
        "runner": str(runner),
        "target_version": target_version,
        "target_sequence": target_sequence,
        "package_sha256": actual,
    }
    atomic_json(state_path, rec)
    mirror_telemetry_status("CHATGPT_PC_RECOVERY_STARTED", {
        "status": "RECOVERY_STARTED",
        "chatgpt_pc_version": str(active.get("version") or ""),
        "chatgpt_pc_sequence": int(active.get("sequence") or 0),
        "recovery_state": "STARTED",
        "target_version": target_version,
    })
    return {"ok": True, "result": "STARTED", **rec}


def _version_tuple(value: str):
    base = str(value or "").split("-", 1)[0].strip()
    out = []
    for part in base.split("."):
        try:
            out.append(int(part))
        except Exception:
            out.append(0)
    while len(out) < 3:
        out.append(0)
    return tuple(out[:4])


def _fetch_bytes(url: str, max_bytes: int = 2_000_000) -> bytes:
    prefix = "https://raw.githubusercontent.com/Terminator364/BCP/"
    if not str(url).startswith(prefix):
        raise ValueError("update_url_not_allowlisted")
    req = Request(str(url), headers={"User-Agent": "BCP-Updater/" + SERVER_VERSION})
    with urlopen(req, timeout=12) as r:
        data = r.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("update_payload_too_large")
    return data


def _fetch_json(url: str) -> dict:
    data = json.loads(_fetch_bytes(url, 512_000).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("update_manifest_not_object")
    return data


def _write_update_state(obj: dict) -> None:
    atomic_json(STATE_DIR / "server_update.json", obj)


def server_update_status(check_remote: bool = True) -> dict:
    local = read_json(STATE_DIR / "server_update.json", {}) or {}
    out = {
        "ok": True,
        "current_version": SERVER_VERSION,
        "auto_update": True,
        "manifest_url": UPDATE_MANIFEST_URL,
        "last_state": local.get("state", "NONE"),
        "last_checked_at": local.get("checked_at"),
        "last_update_at": local.get("updated_at"),
    }
    if not check_remote:
        return out
    manifest = _fetch_json(UPDATE_MANIFEST_URL)
    target = str(manifest.get("version") or "")
    url = str(manifest.get("url") or "")
    sha = str(manifest.get("sha256") or "").lower()
    if not target or not url or len(sha) != 64:
        raise ValueError("update_manifest_incomplete")
    out.update({
        "target_version": target,
        "available": _version_tuple(target) > _version_tuple(SERVER_VERSION),
        "channel": str(manifest.get("channel") or "stable"),
        "sha256": sha,
        "url": url,
        "checked_at": utc_now(),
    })
    _write_update_state({
        "schema": "bcp.server_update/1",
        "state": "UPDATE_AVAILABLE" if out["available"] else "UP_TO_DATE",
        "current_version": SERVER_VERSION,
        "target_version": target,
        "checked_at": out["checked_at"],
        "updated_at": local.get("updated_at"),
    })
    return out


def _candidate_selftest(path: Path) -> dict:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    p = subprocess.run(
        [sys.executable, str(path), "--selftest"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        timeout=45,
        creationflags=flags,
    )
    tail = (p.stdout or "")[-4000:]
    if p.returncode != 0 or "BCP_SERVER_SELFTEST=PASS" not in tail:
        raise RuntimeError("candidate_selftest_failed:" + tail[-1200:])
    return {"returncode": p.returncode, "pass": True}


def apply_server_update() -> dict:
    with UPDATE_LOCK:
        st = server_update_status(check_remote=True)
        if not st.get("available"):
            return {
                "ok": True,
                "result": "NO_UPDATE",
                "current_version": SERVER_VERSION,
                "target_version": st.get("target_version", SERVER_VERSION),
                "restart_required": False,
            }

        target = str(st["target_version"])
        payload = _fetch_bytes(str(st["url"]), 2_000_000)
        actual = hashlib.sha256(payload).hexdigest()
        if not hmac.compare_digest(actual.lower(), str(st["sha256"]).lower()):
            raise ValueError("update_sha256_mismatch")

        STATE_DIR.mkdir(parents=True, exist_ok=True)
        candidate = STATE_DIR / ("server-" + target + ".candidate.py")
        candidate.write_bytes(payload)
        proof = _candidate_selftest(candidate)

        backup = STATE_DIR / ("server-" + SERVER_VERSION + ".backup.py")
        shutil.copy2(SERVER_FILE, backup)
        os.replace(candidate, SERVER_FILE)

        rec = {
            "schema": "bcp.server_update/1",
            "state": "APPLIED_RESTART_PENDING",
            "current_version": SERVER_VERSION,
            "target_version": target,
            "sha256": actual,
            "checked_at": st.get("checked_at"),
            "updated_at": utc_now(),
            "selftest": proof,
            "backup": str(backup),
        }
        _write_update_state(rec)
        mirror_telemetry_status("SERVER_UPDATE_APPLIED", {
            "status": "RESTART_PENDING",
            "target_version": target,
            "update_result": "APPLIED_RESTART_PENDING",
            "auto_update": True,
        })
        return {
            "ok": True,
            "result": "APPLIED_RESTART_PENDING",
            "current_version": SERVER_VERSION,
            "target_version": target,
            "restart_required": True,
            "_backup": str(backup),
        }


def _restart_helper_source() -> str:
    return r"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
from urllib.request import urlopen

old_pid = int(sys.argv[1])
server_file = Path(sys.argv[2])
backup = Path(sys.argv[3])
bind = sys.argv[4]
port = int(sys.argv[5])
expected = sys.argv[6]
state_file = Path(sys.argv[7])
log_file = Path(sys.argv[8])

def write_state(state, **extra):
    d = {"schema":"bcp.server_update/1","state":state,"target_version":expected,"updated_at":time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    d.update(extra)
    tmp = state_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, state_file)

def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False

deadline = time.time() + 8
while alive(old_pid) and time.time() < deadline:
    time.sleep(0.2)

flags = 0
for name in ("CREATE_NO_WINDOW","DETACHED_PROCESS","CREATE_NEW_PROCESS_GROUP"):
    flags |= int(getattr(subprocess, name, 0))

log_file.parent.mkdir(parents=True, exist_ok=True)
log = open(log_file, "ab", buffering=0)
p = subprocess.Popen([sys.executable, str(server_file), "--bind", bind, "--port", str(port)], stdout=log, stderr=log, creationflags=flags)

ok = False
for _ in range(40):
    time.sleep(0.4)
    try:
        with urlopen("http://127.0.0.1:%d/health" % port, timeout=1.5) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("ok") is True and str(data.get("version")) == expected:
            ok = True
            break
    except Exception:
        pass

if ok:
    write_state("COMMITTED", health=True, pid=p.pid)
    raise SystemExit(0)

try:
    p.terminate()
except Exception:
    pass
time.sleep(0.8)
if backup.is_file():
    shutil.copy2(backup, server_file)
rollback = subprocess.Popen([sys.executable, str(server_file), "--bind", bind, "--port", str(port)], stdout=log, stderr=log, creationflags=flags)
write_state("ROLLED_BACK", health=False, rollback_pid=rollback.pid)
"""


def schedule_server_restart(http_server, bind: str, port: int, result: dict) -> None:
    backup = str(result.get("_backup") or "")
    target = str(result.get("target_version") or "")
    if not backup or not target:
        raise ValueError("restart_metadata_missing")
    helper = STATE_DIR / "server_restart_helper.py"
    helper.write_text(_restart_helper_source(), encoding="utf-8")
    log_file = APP_ROOT / "logs" / "server-update-restart.log"
    flags = 0
    for name in ("CREATE_NO_WINDOW", "DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP"):
        flags |= int(getattr(subprocess, name, 0))
    subprocess.Popen(
        [
            sys.executable, str(helper), str(os.getpid()), str(SERVER_FILE), backup,
            bind, str(port), target, str(STATE_DIR / "server_update.json"), str(log_file)
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    threading.Timer(0.8, http_server.shutdown).start()


def start_auto_update_worker(http_server, bind: str, port: int) -> None:
    def worker():
        # Give pairing/telemetry priority immediately after startup.
        time.sleep(20)
        while True:
            try:
                st = server_update_status(check_remote=True)
                mirror_telemetry_status("SERVER_UPDATE_CHECK", {
                    "status": "AVAILABLE" if st.get("available") else "UP_TO_DATE",
                    "target_version": st.get("target_version"),
                    "auto_update": True,
                })
                if st.get("available"):
                    result = apply_server_update()
                    if result.get("restart_required"):
                        schedule_server_restart(http_server, bind, port, result)
                        return
            except Exception as e:
                _write_update_state({
                    "schema": "bcp.server_update/1",
                    "state": "CHECK_FAILED",
                    "current_version": SERVER_VERSION,
                    "checked_at": utc_now(),
                    "error": str(e)[:500],
                })
                mirror_telemetry_status("SERVER_UPDATE_CHECK_FAILED", {
                    "status": "DEGRADED",
                    "update_result": type(e).__name__,
                    "auto_update": True,
                })
            time.sleep(AUTO_UPDATE_INTERVAL_SECONDS)

    threading.Thread(target=worker, name="BCP-AutoUpdate", daemon=True).start()


def ensure_state() -> str:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    if not TOKEN_PATH.exists():
        token = secrets.token_urlsafe(32)
        TOKEN_PATH.write_text(token + "\n", encoding="utf-8")
    else:
        token = TOKEN_PATH.read_text(encoding="utf-8").strip()

    cx = sqlite3.connect(DB_PATH)
    try:
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
    finally:
        cx.close()
    return token


def connect_db():
    cx = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    cx.row_factory = sqlite3.Row
    return cx


def get_head(project_id: str):
    cx = connect_db()
    try:
        row = cx.execute("SELECT * FROM heads WHERE project_id=?", (project_id,)).fetchone()
        return dict(row) if row else None
    finally:
        cx.close()


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
    server_version = "BCP/" + SERVER_VERSION

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

        if path == "/v1/system/chatgpt-pc":
            try:
                self.send_json(200, chatgpt_pc_status())
            except Exception as e:
                self.send_json(500, {"ok": False, "error": "chatgpt_pc_status_failed", "detail": str(e)[:500]})
            return

        if path == "/v1/system/update":
            try:
                self.send_json(200, server_update_status(check_remote=True))
            except Exception as e:
                self.send_json(503, {"ok": False, "error": "update_check_failed", "detail": str(e)[:500], "current_version": SERVER_VERSION})
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
                    "telemetry_bridge_control_folder": str(chatgpt_control_folder() or ""),
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
                mirror_telemetry_status("PAIRING_PASS", {"status": "CONNECTED"})
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

        if path == "/v1/system/chatgpt-pc/recover":
            try:
                body = self.read_json()
                if body.get("confirm") is not True:
                    raise ValueError("explicit_confirm_required")
                self.send_json(202, request_chatgpt_pc_recovery())
            except Exception as e:
                self.send_json(500, {"ok": False, "error": "chatgpt_pc_recovery_failed", "detail": str(e)[:500]})
            return

        if path == "/v1/system/update/apply":
            try:
                result = apply_server_update()
                public = {k: v for k, v in result.items() if not str(k).startswith("_")}
                self.send_json(200, public)
                if result.get("restart_required"):
                    schedule_server_restart(self.server, str(self.server.server_address[0]), int(self.server.server_address[1]), result)
            except Exception as e:
                self.send_json(500, {"ok": False, "error": "update_apply_failed", "detail": str(e)[:500], "current_version": SERVER_VERSION})
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
                last = events[-1] if events and isinstance(events[-1], dict) else {}
                mirror_telemetry_status("TELEMETRY_RECEIVED", {
                    "accepted": min(len(events), 100),
                    "last_event_type": last.get("type"),
                    "last_event_ts": last.get("ts"),
                    "status": "CONNECTED",
                })
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
        assert _version_tuple("0.4.4") > _version_tuple("0.4.3")
        assert _version_tuple("0.4.4") == (0, 4, 4)
        source = SERVER_FILE.read_text(encoding="utf-8")
        assert "API_BCP" in source and "02_TELEMETRY" in source
        assert "/v1/system/chatgpt-pc/recover" in source
        assert "recovery_package_sha256_mismatch" in source
        assert "shell=False" in source
        control = Path(td) / "control"
        control.mkdir(parents=True, exist_ok=True)
        previous = os.environ.get("BCP_CONTROL_FOLDER")
        os.environ["BCP_CONTROL_FOLDER"] = str(control)
        try:
            assert mirror_telemetry_status("SELFTEST", {"accepted": 1, "last_event_type": "PHONE_HEARTBEAT", "status": "CONNECTED"})
            bridge = control / "03_TELEMETRY" / "BCP" / "BCP_LATEST.json"
            assert bridge.is_file()
            raw = bridge.read_text(encoding="utf-8")
            assert "token" not in raw.lower()
            data = json.loads(raw)
            assert data["schema"] == "bcp.telemetry.bridge/1"
            assert data["last_event_type"] == "PHONE_HEARTBEAT"
            external = Path(td) / "external"
            old_external = os.environ.get("BCP_EXTERNAL_TELEMETRY_DIR")
            os.environ["BCP_EXTERNAL_TELEMETRY_DIR"] = str(external)
            try:
                written = mirror_external_runtime_status("SELFTEST")
                assert str(external) in written
                runtime = json.loads((external / "BCP_RUNTIME_LATEST.json").read_text(encoding="utf-8"))
                assert runtime["schema"] == "bcp.external_runtime/1"
                assert runtime["server_version"] == SERVER_VERSION
                assert "token" not in json.dumps(runtime).lower()
            finally:
                if old_external is None:
                    os.environ.pop("BCP_EXTERNAL_TELEMETRY_DIR", None)
                else:
                    os.environ["BCP_EXTERNAL_TELEMETRY_DIR"] = old_external
        finally:
            if previous is None:
                os.environ.pop("BCP_CONTROL_FOLDER", None)
            else:
                os.environ["BCP_CONTROL_FOLDER"] = previous
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
    lifecycle = ensure_lifecycle_registration()
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.bcp_token = token
    mirror_external_runtime_status("SERVER_START")
    if not lifecycle.get("registered", False):
        mirror_telemetry_status("LIFECYCLE_REGISTRATION_DEGRADED", {"status": "DEGRADED"})
    start_external_heartbeat_worker()
    start_auto_update_worker(server, args.bind, args.port)
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
