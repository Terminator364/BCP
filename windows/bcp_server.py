from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import struct
import subprocess
import sys
import threading
from contextlib import contextmanager
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen

APP_ROOT = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ChatGPT_ManagedApps" / "bcp"
STATE_DIR = APP_ROOT / "state"
TELEMETRY_DIR = APP_ROOT / "telemetry"
DB_PATH = STATE_DIR / "bcp.sqlite3"
TOKEN_PATH = STATE_DIR / "bcp_token.txt"
PAIR_PATH = STATE_DIR / "paired_edge.json"
SERVER_VERSION = "0.7.9"
SERVER_FILE = Path(__file__).resolve()
UPDATE_MANIFEST_URL = "https://raw.githubusercontent.com/Terminator364/BCP/main/release/server.json"
TELEGRAM_COMPANION_MANIFEST_URL = "https://raw.githubusercontent.com/Terminator364/BCP/main/release/telegram_observability.json"
TELEGRAM_COMPANION_PATH = APP_ROOT / "telegram_observability.py"
TELEGRAM_COMPANION_STATE_PATH = STATE_DIR / "telegram_companion_update.json"
TELEGRAM_COMPANION_HEALTH_PATH = STATE_DIR / "telegram_worker_health.json"
TELEGRAM_COMPANION_WATCHDOG_PATH = STATE_DIR / "telegram_companion_watchdog.json"
MISSION_WATCHDOG_STATE_PATH = STATE_DIR / "mission_watchdog.json"
MISSION_RESUME_REQUEST_PATH = STATE_DIR / "mission_resume_request.json"
MISSION_RESUME_REQUEST_LOG = STATE_DIR / "MISSION_RESUME_REQUESTS.jsonl"
CONVERSATION_RECEIPT_INBOX = STATE_DIR / "CONVERSATION_RECEIPTS.jsonl"
CONVERSATION_RECEIPT_CURSOR = STATE_DIR / "conversation_receipt_cursor.json"
CONVERSATION_RECEIPT_ACK = STATE_DIR / "conversation_receipt_ack.json"
CHATGPT_PC_FLOW_BRIDGE_CURSOR = STATE_DIR / "chatgpt_pc_flow_bridge_cursor.json"
CHATGPT_PC_FLOW_BRIDGE_STATUS = STATE_DIR / "chatgpt_pc_flow_bridge_status.json"
CHATGPT_PC_FLOW_BATCH = 24
CONVERSATION_RECEIPT_POLL_SECONDS = 10
NEXUS_BOOTSTRAP_MANIFEST_URL = "https://raw.githubusercontent.com/Terminator364/BCP/main/release/nexus_bootstrap.json"
NEXUS_BOOTSTRAP_ROOT = APP_ROOT / "nexus-bootstrap"
NEXUS_BOOTSTRAP_STATE_PATH = STATE_DIR / "nexus_bootstrap_delivery.json"
NEXUS_BOOTSTRAP_RECEIPT_PATH = STATE_DIR / "nexus_bootstrap_receipt.json"
AUTO_UPDATE_INTERVAL_SECONDS = 30 * 60
UPDATE_NETWORK_BACKOFF_SECONDS = (2 * 60, 5 * 60, 15 * 60, 30 * 60)
NEXUS_HUMAN_GATE_MANIFEST_WATCH_SECONDS = 2 * 60
NEXUS_HUMAN_GATE_MANIFEST_WATCH_MAX_BACKOFF_SECONDS = 15 * 60
EXTERNAL_HEARTBEAT_INTERVAL_SECONDS = 45
MISSION_STALE_SECONDS = 10 * 60
MISSION_WATCHDOG_MAX_AUTO_REQUESTS = 3
MISSION_WATCHDOG_COOLDOWNS = (5 * 60, 15 * 60, 60 * 60)
NEXUS_BOOTSTRAP_RETRY_BASE_SECONDS = 5 * 60
NEXUS_BOOTSTRAP_RETRY_MAX_SECONDS = 30 * 60
NEXUS_BOOTSTRAP_MAX_AUTO_ATTEMPTS = 4
NEXUS_BOOTSTRAP_PROCESS_TIMEOUT_SECONDS = 45 * 60
DB_LOCK = threading.RLock()
UPDATE_LOCK = threading.RLock()
NEXUS_BOOTSTRAP_LOCK = threading.RLock()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def public_identity_fingerprint(token: str) -> str:
    """Stable non-secret PC identity hint for one-time user confirmation."""
    return hashlib.sha256(("BCP-PC-IDENTITY:" + token).encode("utf-8")).hexdigest()[:20]


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
        "error_class", "error_detail", "transport_lane", "retry_seconds",
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


def edge_distribution_roots() -> list[Path]:
    """Return candidate Drive-synced installer folders for B-EDGE releases."""
    roots: list[Path] = []
    override = os.environ.get("BCP_EDGE_DISTRIBUTION_DIR", "").strip()
    if override:
        # An explicit override is authoritative. Do not silently fall back to
        # another Drive root if the override is invalid/tampered; this keeps
        # field behavior deterministic and makes candidate self-tests isolated
        # from whatever real Drive mounts happen to exist on the PC.
        return [Path(override)]
    candidates = [
        Path(r"G:\\Mon Drive\\API_BCP\\00_A_INSTALLER"),
        Path(r"G:\\My Drive\\API_BCP\\00_A_INSTALLER"),
        Path.home() / "My Drive" / "API_BCP" / "00_A_INSTALLER",
        Path.home() / "Mon Drive" / "API_BCP" / "00_A_INSTALLER",
    ]
    for p in candidates:
        try:
            if p.exists() and p.is_dir():
                roots.append(p)
        except Exception:
            pass
    dedup: list[Path] = []
    seen = set()
    for p in roots:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            dedup.append(p)
    return dedup


def edge_update_bundle() -> dict:
    """Read and verify the private Drive-backed B-EDGE CURRENT bundle.

    The APK is never trusted from metadata alone: its SHA-256 is recomputed
    before any manifest is exposed to the paired phone.
    """
    last_error = "edge_update_bundle_not_found"
    for root in edge_distribution_roots():
        manifest_path = root / "BCP_EDGE_CURRENT.json"
        apk_path = root / "BCP_EDGE_CURRENT.apk"
        try:
            if not manifest_path.is_file() or not apk_path.is_file():
                continue
            manifest = read_json(manifest_path, {}) or {}
            required = [
                "package_id", "version_code", "version_name",
                "apk_sha256", "signing_cert_sha256"
            ]
            if any(not manifest.get(k) for k in required):
                raise ValueError("edge_manifest_incomplete")
            expected = str(manifest["apk_sha256"]).lower()
            if len(expected) != 64:
                raise ValueError("edge_manifest_sha256_invalid")
            actual = hashlib.sha256(apk_path.read_bytes()).hexdigest()
            if not hmac.compare_digest(actual, expected):
                raise ValueError("edge_apk_sha256_mismatch")
            size = apk_path.stat().st_size
            if size <= 0 or size > 50 * 1024 * 1024:
                raise ValueError("edge_apk_size_invalid")
            public = {
                "ok": True,
                "channel": str(manifest.get("channel") or "stable")[:40],
                "package_id": str(manifest["package_id"])[:160],
                "version_code": int(manifest["version_code"]),
                "version_name": str(manifest["version_name"])[:80],
                "apk_sha256": actual,
                "signing_cert_sha256": str(manifest["signing_cert_sha256"]).lower()[:64],
                "size_bytes": size,
                "published_at": str(manifest.get("published_at") or "")[:80],
                "transport": "BCP_LOCAL_AUTHENTICATED",
            }
            return {"manifest": public, "apk_path": apk_path, "root": root}
        except Exception as e:
            last_error = str(e)
    raise FileNotFoundError(last_error)


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


def windows_resource_status() -> dict:
    """Dependency-free Windows RAM and power snapshot for the external heartbeat."""
    out = {
        "pc_memory_load_percent": None,
        "pc_available_memory_mb": None,
        "pc_power_source": "UNKNOWN",
        "pc_battery_percent": None,
        "pc_battery_critical": False,
    }
    if os.name != "nt":
        return out
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        mem = MEMORYSTATUSEX()
        mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
            out["pc_memory_load_percent"] = int(mem.dwMemoryLoad)
            out["pc_available_memory_mb"] = int(mem.ullAvailPhys // (1024 * 1024))

        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_ubyte),
                ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte),
                ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", ctypes.c_ulong),
                ("BatteryFullLifeTime", ctypes.c_ulong),
            ]

        power = SYSTEM_POWER_STATUS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power)):
            if int(power.ACLineStatus) == 1:
                out["pc_power_source"] = "AC"
            elif int(power.ACLineStatus) == 0:
                out["pc_power_source"] = "BATTERY"
            pct = int(power.BatteryLifePercent)
            if pct != 255:
                out["pc_battery_percent"] = pct
                out["pc_battery_critical"] = bool(pct <= 10 and int(power.ACLineStatus) != 1)
    except Exception:
        pass
    return out


def telegram_companion_runtime_status() -> dict:
    health = read_json(TELEGRAM_COMPANION_HEALTH_PATH, {}) or {}
    update = read_json(TELEGRAM_COMPANION_STATE_PATH, {}) or {}
    age = None
    try:
        if TELEGRAM_COMPANION_HEALTH_PATH.is_file():
            age = max(0, int(time.time() - TELEGRAM_COMPANION_HEALTH_PATH.stat().st_mtime))
    except Exception:
        age = None
    return {
        "state": str(health.get("state") or "NOT_OBSERVED")[:80],
        "mode": str(health.get("mode") or "")[:40],
        "pid": int(health.get("pid") or 0),
        "age_seconds": age,
        "last_poll_at": str(health.get("last_poll_at") or "")[:80],
        "last_callback_data": str(health.get("callback_data") or "")[:80],
        "last_callback_received_at": str(health.get("callback_received_at") or "")[:80],
        "last_callback_handled_at": str(health.get("callback_handled_at") or "")[:80],
        "error_class": str(health.get("error_class") or "")[:120],
        "error_detail": str(health.get("error_detail") or "")[:240],
        "consecutive_failures": int(health.get("consecutive_failures") or 0),
        "update_state": str(update.get("state") or "NONE")[:80],
        "target_version": str(update.get("target_version") or "")[:80],
        "installed_sha256": str(update.get("installed_sha256") or "")[:64],
    }


def _telegram_companion_watchdog() -> dict:
    """Restart only a truly stale V6+ companion; network failures still update health."""
    status = telegram_companion_runtime_status()
    age = status.get("age_seconds")
    if os.name != "nt" or not _telegram_companion_configured() or not TELEGRAM_COMPANION_PATH.is_file():
        return dict(status, watchdog="NOT_APPLICABLE")
    if age is None:
        return dict(status, watchdog="AWAITING_HEALTH_CAPABLE_COMPANION")
    if age <= 180:
        return dict(status, watchdog="HEALTHY")

    prior = read_json(TELEGRAM_COMPANION_WATCHDOG_PATH, {}) or {}
    last = _parse_utc_timestamp(prior.get("restarted_at"))
    now = dt.datetime.now(dt.timezone.utc)
    if last is not None and (now - last).total_seconds() < 300:
        return dict(status, watchdog="RESTART_COOLDOWN")

    _stop_telegram_companion_windows()
    proc = _launch_telegram_companion()
    atomic_json(TELEGRAM_COMPANION_WATCHDOG_PATH, {
        "schema": "bcp.telegram_companion_watchdog/1",
        "restarted_at": utc_now(),
        "pid": int(proc.pid),
        "reason": "HEALTH_STALE",
        "prior_health_age_seconds": age,
    })
    mirror_telemetry_status("TELEGRAM_COMPANION_WATCHDOG_RESTART", {
        "status": "RECOVERING",
        "prior_health_age_seconds": age,
    })
    return dict(status, watchdog="RESTARTED", restart_pid=int(proc.pid))


def mirror_external_runtime_status(reason: str = "PERIODIC_HEARTBEAT") -> list[str]:
    """Publish sanitized runtime truth to any available synced external folder."""
    update = read_json(STATE_DIR / "server_update.json", {}) or {}
    nexus = read_json(NEXUS_BOOTSTRAP_STATE_PATH, {}) or {}
    chat = chatgpt_pc_status()
    telegram = telegram_companion_runtime_status()
    resources = windows_resource_status()
    mission_watchdog = read_json(MISSION_WATCHDOG_STATE_PATH, {}) or {}
    resume_request = read_json(MISSION_RESUME_REQUEST_PATH, {}) or {}
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
        "nexus_bootstrap_state": str(nexus.get("state") or "NONE")[:80],
        "nexus_bootstrap_bundle_version": str(nexus.get("bundle_version") or "")[:40],
        "nexus_bootstrap_exit_code": nexus.get("exit_code"),
        "nexus_bootstrap_receipt_status": str(nexus.get("receipt_status") or "")[:80],
        "nexus_bootstrap_error_class": str(nexus.get("error_class") or "")[:120],
        "nexus_bootstrap_error_detail": str(nexus.get("error_detail") or "")[:240],
        "nexus_bootstrap_stage": str(nexus.get("stage") or "")[:120],
        "telegram_companion_state": telegram["state"],
        "telegram_companion_mode": telegram["mode"],
        "telegram_companion_pid": telegram["pid"],
        "telegram_companion_health_age_seconds": telegram["age_seconds"],
        "telegram_companion_last_poll_at": telegram["last_poll_at"],
        "telegram_companion_last_callback_data": telegram["last_callback_data"],
        "telegram_companion_last_callback_received_at": telegram["last_callback_received_at"],
        "telegram_companion_last_callback_handled_at": telegram["last_callback_handled_at"],
        "telegram_companion_error_class": telegram["error_class"],
        "telegram_companion_error_detail": telegram["error_detail"],
        "telegram_companion_consecutive_failures": telegram["consecutive_failures"],
        "telegram_companion_update_state": telegram["update_state"],
        "telegram_companion_target_version": telegram["target_version"],
        "chatgpt_pc_active_version": str(chat.get("active_version") or "")[:40],
        "chatgpt_pc_active_sequence": int(chat.get("active_sequence") or 0),
        "chatgpt_pc_heartbeat_version": str(chat.get("heartbeat_version") or "")[:40],
        "chatgpt_pc_heartbeat_age_seconds": chat.get("heartbeat_age_seconds"),
        "chatgpt_pc_command_plane": str(chat.get("command_plane") or "")[:80],
        "chatgpt_pc_command_plane_age_seconds": chat.get("command_plane_age_seconds"),
        "recovery_phase": str(chat.get("recovery_phase") or "")[:80],
        "recovery_result_status": str(chat.get("recovery_result_status") or "")[:80],
        "lifecycle_registration": lifecycle_registration_status(),
        "pc_memory_load_percent": resources.get("pc_memory_load_percent"),
        "pc_available_memory_mb": resources.get("pc_available_memory_mb"),
        "pc_power_source": resources.get("pc_power_source"),
        "pc_battery_percent": resources.get("pc_battery_percent"),
        "pc_battery_critical": bool(resources.get("pc_battery_critical")),
        "mission_watchdog_state": str(mission_watchdog.get("state") or "NOT_OBSERVED")[:80],
        "mission_watchdog_mission_id": str(mission_watchdog.get("mission_id") or "")[:120],
        "mission_watchdog_stale_seconds": int(mission_watchdog.get("stale_seconds") or 0),
        "mission_watchdog_attempt_count": int(mission_watchdog.get("attempt_count") or 0),
        "mission_watchdog_last_action": str(mission_watchdog.get("last_action") or "")[:160],
        "mission_resume_request_state": str(resume_request.get("state") or "")[:80],
        "mission_resume_request_id": str(resume_request.get("request_id") or "")[:120],
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
                _telegram_companion_watchdog()
            except Exception as e:
                try:
                    mirror_telemetry_status("TELEGRAM_COMPANION_WATCHDOG_FAILED", {
                        "status": "DEGRADED",
                        "error_class": type(e).__name__,
                    })
                except Exception:
                    pass
            try:
                consume_mission_resume_request()
                mission_watchdog_tick()
            except Exception as e:
                try:
                    mirror_telemetry_status("MISSION_WATCHDOG_FAILED", {
                        "status": "DEGRADED",
                        "update_result": type(e).__name__,
                    })
                except Exception:
                    pass
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


def _chatgpt_pc_recovery_launcher_content(pythonw: Path, runner: Path) -> str:
    command = f'"{pythonw}" "{runner}"'
    escaped = command.replace('"', '""')
    return (
        'Option Explicit\r\n'
        'Dim sh\r\n'
        'Set sh = CreateObject("WScript.Shell")\r\n'
        f'sh.Run "{escaped}", 0, False\r\n'
    )


def _write_utf16_recovery_vbs(path: Path, content: str) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".bcp-repair.tmp")
    tmp.write_bytes(content.encode("utf-16"))
    os.replace(tmp, path)
    raw = path.read_bytes()
    if not raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise RuntimeError("recovery_vbs_utf16_bom_missing")
    if raw.decode("utf-16") != content:
        raise RuntimeError("recovery_vbs_readback_mismatch")
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def repair_chatgpt_pc_recovery_launcher() -> dict:
    if os.name != "nt":
        raise RuntimeError("chatgpt_pc_recovery_requires_windows")
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    root = local / "Tunnel_PC_G4"
    pythonw = root / "runtime" / "pythonw.exe"
    runner = root / "recovery_plane_runner.py"
    if not pythonw.is_file():
        raise FileNotFoundError("chatgpt_pc_pythonw_missing")
    if not runner.is_file():
        raise FileNotFoundError("chatgpt_pc_recovery_plane_runner_missing")
    appdata = os.environ.get("APPDATA", "").strip()
    if not appdata:
        raise RuntimeError("appdata_missing")
    startup = (
        Path(appdata)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / "ChatGPTPC_RecoveryPlane.vbs"
    )
    content = _chatgpt_pc_recovery_launcher_content(pythonw, runner)
    proof = _write_utf16_recovery_vbs(startup, content)
    wscript = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "wscript.exe"
    if not wscript.is_file():
        raise FileNotFoundError("wscript_missing")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(
        [str(wscript), str(startup)],
        cwd=str(root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
        creationflags=flags,
        close_fds=True,
    )
    rec = {
        "schema": "bcp.chatgpt_pc_recovery_launcher_bridge/1",
        "status": "STARTED",
        "pid": int(proc.pid),
        "started_at": utc_now(),
        "startup_path": str(startup),
        "startup_sha256": proof["sha256"],
        "encoding": "UTF-16",
        "runner": str(runner),
        "pythonw": str(pythonw),
        "privilege_expansion": False,
        "network_policy_broadened": False,
    }
    atomic_json(STATE_DIR / "chatgpt_pc_recovery_launcher_bridge.json", rec)
    mirror_telemetry_status("CHATGPT_PC_RECOVERY_LAUNCHER_BRIDGE_STARTED", {
        "status": "RECOVERY_STARTED",
        "recovery_state": "LAUNCHER_BRIDGE_STARTED",
    })
    return {"ok": True, "result": "RECOVERY_LAUNCHER_REPAIRED_AND_STARTED", **rec}


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
        bridge = repair_chatgpt_pc_recovery_launcher()
        return {
            **bridge,
            "recovery_state": "CONTROL_FOLDER_UNAVAILABLE_BRIDGE_STARTED",
            "target_version": "",
            "target_sequence": 0,
        }

    target_path = control / "00_CONTEXT" / "RECOVERY_BOOTSTRAP_TARGET.json"
    target = read_json(target_path, {}) or {}
    if target.get("status") != "ACTIVE":
        bridge = repair_chatgpt_pc_recovery_launcher()
        return {
            **bridge,
            "recovery_state": "LOCAL_TARGET_NOT_ACTIVE_BRIDGE_STARTED",
            "target_version": str(target.get("version") or ""),
            "target_sequence": int(target.get("sequence") or 0),
            "local_target_status": str(target.get("status") or "MISSING"),
        }
    target_version = str(target.get("version") or "")
    target_sequence = int(target.get("sequence") or 0)
    package_file = str(target.get("package_file") or "")
    package_sha = str(target.get("package_sha256") or "").lower()
    if not target_version or target_sequence < 1 or not package_file or Path(package_file).name != package_file:
        raise ValueError("recovery_target_invalid")
    package = control / "02_UPDATES" / "AGENT" / package_file
    if not package.is_file():
        bridge = repair_chatgpt_pc_recovery_launcher()
        return {
            **bridge,
            "recovery_state": "PACKAGE_SYNC_PENDING_BRIDGE_STARTED",
            "target_version": target_version,
            "target_sequence": target_sequence,
            "local_target_status": "ACTIVE",
        }
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


def _telegram_companion_configured() -> bool:
    return (STATE_DIR / "telegram_observability.json").is_file()


def telegram_companion_update_status(check_remote: bool = True) -> dict:
    installed_sha = ""
    if TELEGRAM_COMPANION_PATH.is_file():
        try:
            installed_sha = hashlib.sha256(TELEGRAM_COMPANION_PATH.read_bytes()).hexdigest()
        except Exception:
            installed_sha = ""
    local = read_json(TELEGRAM_COMPANION_STATE_PATH, {}) or {}
    out = {
        "ok": True,
        "configured": _telegram_companion_configured(),
        "installed": TELEGRAM_COMPANION_PATH.is_file(),
        "installed_sha256": installed_sha,
        "last_state": str(local.get("state") or "NONE"),
        "last_checked_at": local.get("checked_at"),
        "last_update_at": local.get("updated_at"),
    }
    if not check_remote:
        return out
    manifest = _fetch_json(TELEGRAM_COMPANION_MANIFEST_URL)
    if manifest.get("schema") != "bcp.telegram_companion_release/1":
        raise ValueError("telegram_companion_manifest_schema")
    target = str(manifest.get("version") or "")
    url = str(manifest.get("url") or "")
    sha = str(manifest.get("sha256") or "").lower()
    minimum_server = str(manifest.get("minimum_server_version") or "")
    if not target or not url or len(sha) != 64:
        raise ValueError("telegram_companion_manifest_incomplete")
    if minimum_server and _version_tuple(SERVER_VERSION) < _version_tuple(minimum_server):
        raise ValueError("telegram_companion_server_too_old")
    available = bool(out["configured"] and installed_sha.lower() != sha)
    out.update({
        "target_version": target,
        "target_sha256": sha,
        "url": url,
        "available": available,
        "checked_at": utc_now(),
    })
    atomic_json(TELEGRAM_COMPANION_STATE_PATH, {
        "schema": "bcp.telegram_companion_update/1",
        "state": "UPDATE_AVAILABLE" if available else ("UP_TO_DATE" if out["configured"] else "NOT_CONFIGURED"),
        "target_version": target,
        "installed_sha256": installed_sha,
        "target_sha256": sha,
        "checked_at": out["checked_at"],
        "updated_at": local.get("updated_at"),
    })
    return out


def _telegram_companion_selftest(path: Path) -> dict:
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
    if p.returncode != 0 or "BCP_TELEGRAM_OBSERVABILITY_SELFTEST=PASS" not in tail:
        raise RuntimeError("telegram_companion_selftest_failed:" + tail[-1200:])
    return {"returncode": int(p.returncode), "pass": True}


def _ensure_telegram_companion_startup() -> dict:
    if os.name != "nt":
        return {"supported": False, "registered": False, "reason": "non_windows"}
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        value_name = "BlessingControlPlaneTelegram"
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        launcher = pythonw if pythonw.is_file() else Path(sys.executable)
        command = f'"{launcher}" "{TELEGRAM_COMPANION_PATH}"'
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
        return {"supported": True, "registered": True, "value_name": value_name}
    except Exception as e:
        return {"supported": True, "registered": False, "error": str(e)[:240]}


def _stop_telegram_companion_windows() -> None:
    if os.name != "nt":
        return
    script = (
        "$ErrorActionPreference='SilentlyContinue'; "
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -match '(?i)python' -and "
        "$_.CommandLine -match 'telegram_observability\\.py' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=20,
        creationflags=flags,
        check=False,
    )
    time.sleep(0.8)


def _launch_telegram_companion() -> subprocess.Popen:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    launcher = pythonw if os.name == "nt" and pythonw.is_file() else Path(sys.executable)
    flags = 0
    if os.name == "nt":
        for name in ("CREATE_NO_WINDOW", "DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP"):
            flags |= int(getattr(subprocess, name, 0))
    return subprocess.Popen(
        [str(launcher), str(TELEGRAM_COMPANION_PATH)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        close_fds=True,
    )


def apply_telegram_companion_update() -> dict:
    st = telegram_companion_update_status(check_remote=True)
    if not st.get("configured"):
        return {"ok": True, "result": "NOT_CONFIGURED", "restart_required": False}
    if not st.get("available"):
        return {
            "ok": True, "result": "NO_UPDATE", "target_version": st.get("target_version"),
            "restart_required": False,
        }

    payload = _fetch_bytes(str(st["url"]), 2_000_000)
    actual = hashlib.sha256(payload).hexdigest()
    expected = str(st["target_sha256"]).lower()
    if not hmac.compare_digest(actual.lower(), expected):
        raise ValueError("telegram_companion_sha256_mismatch")

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    candidate = STATE_DIR / "telegram_observability.candidate.py"
    candidate.write_bytes(payload)
    proof = _telegram_companion_selftest(candidate)

    backup = STATE_DIR / "telegram_observability.backup.py"
    had_previous = TELEGRAM_COMPANION_PATH.is_file()
    if had_previous:
        shutil.copy2(TELEGRAM_COMPANION_PATH, backup)
    TELEGRAM_COMPANION_PATH.parent.mkdir(parents=True, exist_ok=True)
    os.replace(candidate, TELEGRAM_COMPANION_PATH)

    registration = _ensure_telegram_companion_startup()
    if os.name == "nt":
        _stop_telegram_companion_windows()
        proc = _launch_telegram_companion()
        time.sleep(2.0)
        if proc.poll() is not None:
            if had_previous and backup.is_file():
                shutil.copy2(backup, TELEGRAM_COMPANION_PATH)
                _ensure_telegram_companion_startup()
                rollback = _launch_telegram_companion()
                atomic_json(TELEGRAM_COMPANION_STATE_PATH, {
                    "schema": "bcp.telegram_companion_update/1",
                    "state": "ROLLED_BACK",
                    "target_version": st.get("target_version"),
                    "target_sha256": expected,
                    "rollback_pid": int(rollback.pid),
                    "updated_at": utc_now(),
                })
            raise RuntimeError("telegram_companion_restart_failed")
        pid = int(proc.pid)
    else:
        pid = 0

    rec = {
        "schema": "bcp.telegram_companion_update/1",
        "state": "COMMITTED",
        "target_version": st.get("target_version"),
        "installed_sha256": actual,
        "target_sha256": expected,
        "selftest": proof,
        "startup": registration,
        "pid": pid,
        "checked_at": st.get("checked_at"),
        "updated_at": utc_now(),
    }
    atomic_json(TELEGRAM_COMPANION_STATE_PATH, rec)
    return {
        "ok": True,
        "result": "COMMITTED",
        "target_version": st.get("target_version"),
        "sha256": actual,
        "pid": pid,
        "restart_required": False,
    }


def _nexus_bootstrap_success() -> bool:
    receipt = read_json(NEXUS_BOOTSTRAP_RECEIPT_PATH, {}) or {}
    return str(receipt.get("status") or "") == "NEXUS_DEPLOYED_LOCAL_WORKER_RUNNING"


def _nexus_safe_relpath(value: str) -> str:
    raw = str(value or "").replace("\\", "/").strip("/")
    if not raw or raw.startswith("/") or ".." in raw.split("/"):
        raise ValueError("nexus_bootstrap_path_invalid")
    allowed = (
        "windows/BOOTSTRAP_BCP_NEXUS.ps1",
        "windows/CONFIGURE_BCP_NEXUS.ps1",
        "nexus/cloudflare-worker/src/worker.mjs",
        "nexus/cloudflare-worker/migrations/0001_init.sql",
    )
    if raw not in allowed:
        raise ValueError("nexus_bootstrap_path_not_allowlisted")
    return raw


def nexus_bootstrap_delivery_status(check_remote: bool = True) -> dict:
    local = read_json(NEXUS_BOOTSTRAP_STATE_PATH, {}) or {}
    out = {
        "ok": True,
        "configured": _nexus_bootstrap_success(),
        "state": str(local.get("state") or "NONE"),
        "bundle_version": str(local.get("bundle_version") or ""),
        "pid": int(local.get("pid") or 0),
        "manifest_url": NEXUS_BOOTSTRAP_MANIFEST_URL,
    }
    if not check_remote:
        return out
    manifest = _fetch_json(NEXUS_BOOTSTRAP_MANIFEST_URL)
    if manifest.get("schema") != "bcp.nexus_bootstrap_release/1":
        raise ValueError("nexus_bootstrap_manifest_schema")
    version = str(manifest.get("version") or "")
    minimum_server = str(manifest.get("minimum_server_version") or "")
    files = manifest.get("files")
    if not version or not isinstance(files, list) or not files:
        raise ValueError("nexus_bootstrap_manifest_incomplete")
    if minimum_server and _version_tuple(SERVER_VERSION) < _version_tuple(minimum_server):
        raise ValueError("nexus_bootstrap_server_too_old")
    missing = 0
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("nexus_bootstrap_file_invalid")
        rel = _nexus_safe_relpath(item.get("path"))
        expected = str(item.get("sha256") or "").lower()
        url = str(item.get("url") or "")
        if len(expected) != 64 or not url.startswith("https://raw.githubusercontent.com/Terminator364/BCP/"):
            raise ValueError("nexus_bootstrap_file_contract_invalid")
        target = NEXUS_BOOTSTRAP_ROOT / Path(rel)
        actual = ""
        if target.is_file():
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if not hmac.compare_digest(actual.lower(), expected):
            missing += 1
    out.update({
        "target_version": version,
        "available": bool(missing),
        "files_needing_update": int(missing),
        "zero_usd": bool(manifest.get("zero_usd", True)),
    })
    return out


def _parse_utc_timestamp(value: str):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = dt.datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except Exception:
        return None


def _nexus_retry_delay_seconds(bundle_version: str, attempt_count: int) -> int:
    attempt = max(1, int(attempt_count or 1))
    base = min(
        NEXUS_BOOTSTRAP_RETRY_MAX_SECONDS,
        NEXUS_BOOTSTRAP_RETRY_BASE_SECONDS * (2 ** max(0, attempt - 1)),
    )
    # Stable 0-20% jitter prevents synchronized retry bursts without introducing
    # non-deterministic state or an extra dependency.
    seed = hashlib.sha256((str(bundle_version) + ":" + str(attempt)).encode("utf-8")).digest()
    jitter = int(base * 0.20 * (int.from_bytes(seed[:2], "big") / 65535.0))
    return int(min(NEXUS_BOOTSTRAP_RETRY_MAX_SECONDS, base + jitter))


def _nexus_retry_policy(bundle_version: str, prior: dict, now=None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    prior = prior or {}
    prior_version = str(prior.get("bundle_version") or "")
    prior_state = str(prior.get("state") or "")
    try:
        attempts = max(0, int(prior.get("attempt_count") or 0))
    except Exception:
        attempts = 0

    if prior_version != bundle_version:
        return {"action": "LAUNCH", "next_attempt_count": 1, "reason": "NEW_BUNDLE"}

    if prior_state == "HUMAN_AUTH_REQUIRED":
        return {
            "action": "HUMAN_GATE",
            "attempt_count": attempts,
            "reason": "CLOUDFLARE_BROWSER_AUTHORIZATION_REQUIRED",
        }
    if prior_state == "COMMITTED":
        return {"action": "ALREADY_CONFIGURED", "attempt_count": attempts}

    retry_states = {"WRANGLER_RUNTIME_REQUIRED", "EXITED_NO_RECEIPT", "LAUNCHED"}
    if prior_state in retry_states:
        # Older field state did not persist attempt_count; count it as one prior attempt.
        attempts = max(1, attempts)
        if attempts >= NEXUS_BOOTSTRAP_MAX_AUTO_ATTEMPTS:
            return {
                "action": "EXHAUSTED",
                "attempt_count": attempts,
                "reason": "MAX_AUTO_ATTEMPTS_REACHED",
            }
        due = _parse_utc_timestamp(prior.get("next_retry_at"))
        if due is None:
            anchor = _parse_utc_timestamp(prior.get("updated_at")) or _parse_utc_timestamp(prior.get("launched_at"))
            if anchor is not None:
                due = anchor + dt.timedelta(seconds=_nexus_retry_delay_seconds(bundle_version, attempts))
        if due is not None and now < due:
            return {
                "action": "COOLDOWN",
                "attempt_count": attempts,
                "next_attempt_count": attempts + 1,
                "next_retry_at": due.replace(microsecond=0).isoformat(),
                "retry_after_seconds": max(1, int((due - now).total_seconds())),
            }
        return {
            "action": "LAUNCH",
            "next_attempt_count": attempts + 1,
            "reason": "BOUNDED_RETRY_DUE",
        }

    return {
        "action": "LAUNCH",
        "next_attempt_count": max(1, attempts + 1),
        "reason": "STAGED_OR_UNSEEN",
    }


def _terminate_nexus_process_tree(pid: int) -> bool:
    pid = int(pid or 0)
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
            result = subprocess.run(
                ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                creationflags=flags,
            )
            return result.returncode == 0 or not _process_alive(pid)
        os.kill(pid, 15)
        return True
    except Exception:
        return not _process_alive(pid)


def _schedule_nexus_bootstrap_retry(delay_seconds: int, bundle_version: str) -> None:
    delay = max(1, int(delay_seconds))

    def retry():
        current = read_json(NEXUS_BOOTSTRAP_STATE_PATH, {}) or {}
        if str(current.get("bundle_version") or "") != bundle_version:
            return
        if str(current.get("state") or "") not in ("WRANGLER_RUNTIME_REQUIRED", "EXITED_NO_RECEIPT"):
            return
        if bool(current.get("auto_retry_exhausted")):
            return
        try:
            apply_nexus_bootstrap_delivery(auto_launch=True)
        except Exception as exc:
            try:
                mirror_telemetry_status("NEXUS_BOOTSTRAP_RETRY_DISPATCH_FAILED", {
                    "status": "DEGRADED",
                    "bundle_version": bundle_version,
                    "error_class": type(exc).__name__,
                })
            except Exception:
                pass

    timer = threading.Timer(delay, retry)
    timer.daemon = True
    timer.name = "BCP-Nexus-Retry"
    timer.start()


def _monitor_nexus_bootstrap(
    proc: subprocess.Popen,
    bundle_version: str,
    attempt_count: int,
    files_staged: int = 0,
) -> None:
    def worker():
        timed_out = False
        try:
            code = int(proc.wait(timeout=NEXUS_BOOTSTRAP_PROCESS_TIMEOUT_SECONDS))
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_nexus_process_tree(int(proc.pid))
            try:
                code = int(proc.wait(timeout=10))
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
                code = 124
        except Exception:
            code = -1
        receipt = read_json(NEXUS_BOOTSTRAP_RECEIPT_PATH, {}) or {}
        receipt_status = str(receipt.get("status") or "")
        error_class = str(receipt.get("error_class") or "")[:240]
        error_detail = str(receipt.get("error_detail") or "")[:240]
        failure_stage = str(receipt.get("stage") or "")[:120]
        if timed_out and not error_class:
            error_class = "BOOTSTRAP_PROCESS_TIMEOUT"
        success = receipt_status == "NEXUS_DEPLOYED_LOCAL_WORKER_RUNNING"
        human_gate = receipt_status == "HUMAN_AUTH_REQUIRED"
        if success:
            state = "COMMITTED"
        elif human_gate:
            state = "HUMAN_AUTH_REQUIRED"
        elif code == 3:
            state = "WRANGLER_RUNTIME_REQUIRED"
        else:
            state = "EXITED_NO_RECEIPT"

        retryable = (not success) and (not human_gate)
        exhausted = bool(retryable and attempt_count >= NEXUS_BOOTSTRAP_MAX_AUTO_ATTEMPTS)
        delay = _nexus_retry_delay_seconds(bundle_version, attempt_count) if retryable and not exhausted else 0
        next_retry_at = ""
        if delay:
            next_retry_at = (
                dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=delay)
            ).replace(microsecond=0).isoformat()

        atomic_json(NEXUS_BOOTSTRAP_STATE_PATH, {
            "schema": "bcp.nexus_bootstrap_delivery/1",
            "state": state,
            "bundle_version": bundle_version,
            "pid": int(proc.pid),
            "exit_code": code,
            "timed_out": bool(timed_out),
            "process_timeout_seconds": NEXUS_BOOTSTRAP_PROCESS_TIMEOUT_SECONDS,
            "attempt_count": int(attempt_count),
            "max_auto_attempts": NEXUS_BOOTSTRAP_MAX_AUTO_ATTEMPTS,
            "retryable": bool(retryable),
            "auto_retry_exhausted": bool(exhausted),
            "next_retry_at": next_retry_at,
            "files_staged": int(files_staged),
            "updated_at": utc_now(),
            "receipt_present": bool(receipt),
            "receipt_status": receipt_status,
            "error_class": error_class,
            "error_detail": error_detail,
            "stage": failure_stage,
            "spend_usd": 0.0,
        })
        try:
            if success:
                mirror_telemetry_status("NEXUS_BOOTSTRAP_COMMITTED", {
                    "status": "COMMITTED",
                    "bundle_version": bundle_version,
                    "attempt_count": attempt_count,
                })
            elif human_gate:
                mirror_telemetry_status("NEXUS_BOOTSTRAP_HUMAN_AUTH_REQUIRED", {
                    "status": "HUMAN_AUTH_REQUIRED",
                    "bundle_version": bundle_version,
                    "attempt_count": attempt_count,
                })
            elif exhausted:
                mirror_telemetry_status("NEXUS_BOOTSTRAP_AUTO_RETRY_EXHAUSTED", {
                    "status": "DEGRADED",
                    "bundle_version": bundle_version,
                    "attempt_count": attempt_count,
                })
            else:
                mirror_telemetry_status("NEXUS_BOOTSTRAP_RETRY_SCHEDULED", {
                    "status": "WAITING_RETRY",
                    "bundle_version": bundle_version,
                    "attempt_count": attempt_count,
                    "next_retry_at": next_retry_at,
                })
            mirror_external_runtime_status("NEXUS_BOOTSTRAP_PROCESS_EXITED")
        except Exception:
            pass

        if delay:
            _schedule_nexus_bootstrap_retry(delay, bundle_version)

    threading.Thread(target=worker, daemon=True, name="bcp-nexus-bootstrap-monitor").start()


def _launch_nexus_bootstrap_once(
    bundle_version: str,
    prior_snapshot: dict | None = None,
    files_staged: int = 0,
) -> dict:
    if _nexus_bootstrap_success():
        return {"ok": True, "result": "ALREADY_CONFIGURED", "bundle_version": bundle_version}
    if os.name != "nt":
        return {"ok": True, "result": "STAGED_NON_WINDOWS", "bundle_version": bundle_version}

    prior = dict(prior_snapshot if prior_snapshot is not None else (read_json(NEXUS_BOOTSTRAP_STATE_PATH, {}) or {}))
    prior_pid = int(prior.get("pid") or 0)
    prior_version = str(prior.get("bundle_version") or "")
    prior_state = str(prior.get("state") or "")
    if prior_version == bundle_version and prior_state == "LAUNCHED" and _process_alive(prior_pid):
        launched_at = _parse_utc_timestamp(prior.get("launched_at"))
        now = dt.datetime.now(dt.timezone.utc)
        age_seconds = int((now - launched_at).total_seconds()) if launched_at is not None else None
        if age_seconds is None or age_seconds < NEXUS_BOOTSTRAP_PROCESS_TIMEOUT_SECONDS:
            return {
                "ok": True,
                "result": "ALREADY_RUNNING",
                "bundle_version": bundle_version,
                "pid": prior_pid,
                "age_seconds": age_seconds,
                "watchdog_timeout_seconds": NEXUS_BOOTSTRAP_PROCESS_TIMEOUT_SECONDS,
            }
        _terminate_nexus_process_tree(prior_pid)
        prior = dict(prior)
        prior.update({
            "state": "EXITED_NO_RECEIPT",
            "exit_code": 124,
            "timed_out": True,
            "retryable": True,
            "error_class": "ORPHAN_LAUNCHED_PROCESS_TIMEOUT",
            "updated_at": utc_now(),
            "next_retry_at": "",
        })
        atomic_json(NEXUS_BOOTSTRAP_STATE_PATH, prior)

    decision = _nexus_retry_policy(bundle_version, prior)
    action = str(decision.get("action") or "")
    if action == "HUMAN_GATE":
        return {
            "ok": True,
            "result": "HUMAN_AUTH_REQUIRED",
            "bundle_version": bundle_version,
            "attempt_count": int(decision.get("attempt_count") or 0),
        }
    if action == "EXHAUSTED":
        preserved = dict(prior)
        preserved.update({
            "schema": "bcp.nexus_bootstrap_delivery/1",
            "auto_retry_exhausted": True,
            "max_auto_attempts": NEXUS_BOOTSTRAP_MAX_AUTO_ATTEMPTS,
            "last_policy_check_at": utc_now(),
            "files_staged": int(files_staged),
            "spend_usd": 0.0,
        })
        atomic_json(NEXUS_BOOTSTRAP_STATE_PATH, preserved)
        return {
            "ok": True,
            "result": "AUTO_RETRY_EXHAUSTED",
            "bundle_version": bundle_version,
            "attempt_count": int(decision.get("attempt_count") or 0),
        }
    if action == "COOLDOWN":
        preserved = dict(prior)
        preserved.update({
            "schema": "bcp.nexus_bootstrap_delivery/1",
            "last_policy_check_at": utc_now(),
            "files_staged": int(files_staged),
            "spend_usd": 0.0,
        })
        atomic_json(NEXUS_BOOTSTRAP_STATE_PATH, preserved)
        retry_after = max(1, int(decision.get("retry_after_seconds") or 1))
        _schedule_nexus_bootstrap_retry(retry_after, bundle_version)
        return {
            "ok": True,
            "result": "RETRY_COOLDOWN",
            "bundle_version": bundle_version,
            "next_retry_at": decision.get("next_retry_at"),
            "retry_after_seconds": retry_after,
        }
    if action == "ALREADY_CONFIGURED":
        return {"ok": True, "result": "ALREADY_CONFIGURED", "bundle_version": bundle_version}

    bootstrap = NEXUS_BOOTSTRAP_ROOT / "windows" / "BOOTSTRAP_BCP_NEXUS.ps1"
    if not bootstrap.is_file():
        raise FileNotFoundError("nexus_bootstrap_script_missing")
    attempt_count = max(1, int(decision.get("next_attempt_count") or 1))
    flags = int(getattr(subprocess, "CREATE_NEW_CONSOLE", 0)) | int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    proc = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(bootstrap)],
        cwd=str(NEXUS_BOOTSTRAP_ROOT),
        creationflags=flags,
        close_fds=True,
    )
    atomic_json(NEXUS_BOOTSTRAP_STATE_PATH, {
        "schema": "bcp.nexus_bootstrap_delivery/1",
        "state": "LAUNCHED",
        "bundle_version": bundle_version,
        "pid": int(proc.pid),
        "attempt_count": attempt_count,
        "max_auto_attempts": NEXUS_BOOTSTRAP_MAX_AUTO_ATTEMPTS,
        "launched_at": utc_now(),
        "files_staged": int(files_staged),
        "launch_reason": str(decision.get("reason") or ""),
        "human_gate": "CLOUDFLARE_BROWSER_AUTHORIZATION_IF_REQUIRED",
        "spend_usd": 0.0,
    })
    _monitor_nexus_bootstrap(proc, bundle_version, attempt_count, files_staged)
    return {
        "ok": True,
        "result": "LAUNCHED",
        "bundle_version": bundle_version,
        "pid": int(proc.pid),
        "attempt_count": attempt_count,
    }


def _apply_nexus_bootstrap_delivery_locked(auto_launch: bool = True) -> dict:
    # Read the previous delivery state BEFORE staging. This is important:
    # overwriting it with STAGED used to erase retry history and could cause
    # repeated launch attempts after transient failures.
    prior = read_json(NEXUS_BOOTSTRAP_STATE_PATH, {}) or {}
    manifest = _fetch_json(NEXUS_BOOTSTRAP_MANIFEST_URL)
    if manifest.get("schema") != "bcp.nexus_bootstrap_release/1":
        raise ValueError("nexus_bootstrap_manifest_schema")
    version = str(manifest.get("version") or "")
    minimum_server = str(manifest.get("minimum_server_version") or "")
    files = manifest.get("files")
    if not version or not isinstance(files, list) or not files:
        raise ValueError("nexus_bootstrap_manifest_incomplete")
    if minimum_server and _version_tuple(SERVER_VERSION) < _version_tuple(minimum_server):
        raise ValueError("nexus_bootstrap_server_too_old")

    staged = 0
    for item in files:
        rel = _nexus_safe_relpath(item.get("path"))
        expected = str(item.get("sha256") or "").lower()
        url = str(item.get("url") or "")
        limit = int(item.get("max_bytes") or 500_000)
        if len(expected) != 64 or limit < 1 or limit > 2_000_000:
            raise ValueError("nexus_bootstrap_file_contract_invalid")
        target = NEXUS_BOOTSTRAP_ROOT / Path(rel)
        if target.is_file():
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if hmac.compare_digest(actual.lower(), expected):
                continue
        payload = _fetch_bytes(url, limit)
        actual = hashlib.sha256(payload).hexdigest()
        if not hmac.compare_digest(actual.lower(), expected):
            raise ValueError("nexus_bootstrap_sha256_mismatch:" + rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        candidate = target.with_name(target.name + ".candidate")
        candidate.write_bytes(payload)
        os.replace(candidate, target)
        staged += 1

    if auto_launch and bool(manifest.get("auto_launch_once", True)):
        return _launch_nexus_bootstrap_once(version, prior_snapshot=prior, files_staged=staged)

    atomic_json(NEXUS_BOOTSTRAP_STATE_PATH, {
        "schema": "bcp.nexus_bootstrap_delivery/1",
        "state": "STAGED",
        "bundle_version": version,
        "files_staged": staged,
        "attempt_count": int(prior.get("attempt_count") or 0) if str(prior.get("bundle_version") or "") == version else 0,
        "updated_at": utc_now(),
        "spend_usd": 0.0,
    })
    return {"ok": True, "result": "STAGED", "bundle_version": version, "files_staged": staged}


def apply_nexus_bootstrap_delivery(auto_launch: bool = True) -> dict:
    with NEXUS_BOOTSTRAP_LOCK:
        return _apply_nexus_bootstrap_delivery_locked(auto_launch=auto_launch)


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


def start_nexus_human_gate_manifest_watcher() -> None:
    """Fast low-data manifest watch only while a Cloudflare human gate is open."""
    def worker():
        failures = 0
        while True:
            delay = AUTO_UPDATE_INTERVAL_SECONDS
            try:
                current = read_json(NEXUS_BOOTSTRAP_STATE_PATH, {}) or {}
                state = str(current.get("state") or "")
                current_version = str(current.get("bundle_version") or "")
                if state == "HUMAN_AUTH_REQUIRED":
                    delay = NEXUS_HUMAN_GATE_MANIFEST_WATCH_SECONDS
                    manifest = _fetch_json(NEXUS_BOOTSTRAP_MANIFEST_URL)
                    target_version = str(manifest.get("version") or "")
                    failures = 0
                    if target_version and target_version != current_version:
                        mirror_telemetry_status("NEXUS_HUMAN_GATE_NEW_BUNDLE_DETECTED", {
                            "status": "UPDATE_AVAILABLE",
                            "target_version": target_version,
                            "update_result": "HUMAN_GATE_FAST_PATH",
                            "auto_update": True,
                        })
                        apply_nexus_bootstrap_delivery(auto_launch=True)
            except Exception:
                failures = min(failures + 1, 4)
                delay = min(
                    NEXUS_HUMAN_GATE_MANIFEST_WATCH_SECONDS * (2 ** failures),
                    NEXUS_HUMAN_GATE_MANIFEST_WATCH_MAX_BACKOFF_SECONDS,
                )
            time.sleep(max(30, int(delay)))

    threading.Thread(
        target=worker,
        name="BCP-Nexus-HumanGate-ManifestWatch",
        daemon=True,
    ).start()


def _transport_error_detail(exc: Exception) -> tuple[str, str]:
    name = type(exc).__name__
    detail = str(exc).replace("\\r", " ").replace("\\n", " ")[:240]
    lowered = detail.lower()
    if "10060" in lowered or "timed out" in lowered or "timeout" in lowered:
        return "OUTBOUND_TIMEOUT", detail
    if "11001" in lowered or "name or service not known" in lowered or "getaddrinfo" in lowered:
        return "DNS_RESOLUTION_FAILED", detail
    if "certificate" in lowered or "ssl" in lowered or "tls" in lowered:
        return "TLS_FAILURE", detail
    if "connection refused" in lowered or "10061" in lowered:
        return "CONNECTION_REFUSED", detail
    return name, detail


def start_auto_update_worker(http_server, bind: str, port: int) -> None:
    def worker():
        # Give pairing/telemetry priority immediately after startup.
        time.sleep(20)
        failures = 0
        while True:
            server_ok = False
            try:
                st = server_update_status(check_remote=True)
                server_ok = True
                failures = 0
                mirror_telemetry_status("SERVER_UPDATE_CHECK", {
                    "status": "AVAILABLE" if st.get("available") else "UP_TO_DATE",
                    "target_version": st.get("target_version"),
                    "auto_update": True,
                    "transport_lane": "SERVER",
                })
                if st.get("available"):
                    result = apply_server_update()
                    if result.get("restart_required"):
                        schedule_server_restart(http_server, bind, port, result)
                        return
            except Exception as e:
                failures = min(failures + 1, len(UPDATE_NETWORK_BACKOFF_SECONDS))
                error_class, error_detail = _transport_error_detail(e)
                retry_seconds = UPDATE_NETWORK_BACKOFF_SECONDS[failures - 1]
                _write_update_state({
                    "schema": "bcp.server_update/1",
                    "state": "CHECK_FAILED",
                    "current_version": SERVER_VERSION,
                    "checked_at": utc_now(),
                    "error_class": error_class,
                    "error": error_detail,
                    "retry_seconds": retry_seconds,
                })
                mirror_telemetry_status("SERVER_UPDATE_CHECK_FAILED", {
                    "status": "DEGRADED",
                    "update_result": type(e).__name__,
                    "error_class": error_class,
                    "error_detail": error_detail,
                    "transport_lane": "SERVER",
                    "retry_seconds": retry_seconds,
                    "auto_update": True,
                })

            # Companion lanes are independent. A raw GitHub failure must not
            # suppress Telegram/Nexus reconciliation for the whole cycle.
            try:
                apply_telegram_companion_update()
            except Exception as companion_error:
                error_class, error_detail = _transport_error_detail(companion_error)
                mirror_telemetry_status("TELEGRAM_COMPANION_UPDATE_FAILED", {
                    "status": "DEGRADED",
                    "update_result": type(companion_error).__name__,
                    "error_class": error_class,
                    "error_detail": error_detail,
                    "transport_lane": "TELEGRAM_COMPANION",
                    "auto_update": True,
                })
            try:
                apply_nexus_bootstrap_delivery(auto_launch=True)
            except Exception as nexus_error:
                error_class, error_detail = _transport_error_detail(nexus_error)
                atomic_json(NEXUS_BOOTSTRAP_STATE_PATH, {
                    "schema": "bcp.nexus_bootstrap_delivery/1",
                    "state": "STAGE_FAILED",
                    "bundle_version": "",
                    "updated_at": utc_now(),
                    "error_class": error_class,
                    "error": error_detail,
                    "spend_usd": 0.0,
                })
                mirror_telemetry_status("NEXUS_BOOTSTRAP_UPDATE_FAILED", {
                    "status": "DEGRADED",
                    "update_result": type(nexus_error).__name__,
                    "error_class": error_class,
                    "error_detail": error_detail,
                    "transport_lane": "NEXUS",
                    "auto_update": True,
                })

            delay = AUTO_UPDATE_INTERVAL_SECONDS if server_ok else UPDATE_NETWORK_BACKOFF_SECONDS[min(max(failures, 1), len(UPDATE_NETWORK_BACKOFF_SECONDS)) - 1]
            time.sleep(delay)

    threading.Thread(target=worker, name="BCP-AutoUpdate", daemon=True).start()


def _ensure_sqlite_column(cx, table: str, column: str, ddl: str) -> None:
    cols = {str(r[1]) for r in cx.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        cx.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _dns_name(name: str) -> bytes:
    labels = [x for x in str(name).strip(".").split(".") if x]
    out = bytearray()
    for label in labels:
        b = label.encode("utf-8")[:63]
        out.append(len(b))
        out.extend(b)
    out.append(0)
    return bytes(out)


def _mdns_rr(name: str, rtype: int, rclass: int, ttl: int, rdata: bytes) -> bytes:
    return _dns_name(name) + struct.pack("!HHIH", rtype, rclass, ttl, len(rdata)) + rdata


def _lan_ipv4() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("192.0.2.1", 9))
            ip = str(s.getsockname()[0])
            if ip and not ip.startswith("127."):
                return ip
        finally:
            s.close()
    except Exception:
        pass
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return ""


def mdns_announcement_packet(port: int = 8765) -> bytes:
    pc = (os.environ.get("COMPUTERNAME") or socket.gethostname() or "BCP-PC").replace(".", "-")[:40]
    service = "_bcp._tcp.local"
    instance = f"BCP-{pc}.{service}"
    host = f"{pc}.local"
    ip = _lan_ipv4()
    if not ip:
        raise RuntimeError("no_lan_ipv4_for_mdns")
    token = TOKEN_PATH.read_text(encoding="utf-8").strip() if TOKEN_PATH.is_file() else ensure_state()
    txt_parts = [
        f"ver={SERVER_VERSION}".encode("utf-8"),
        b"proto=1",
        ("fp=" + public_identity_fingerprint(token)).encode("utf-8"),
    ]
    txt = b"".join(bytes([min(len(x), 255)]) + x[:255] for x in txt_parts)
    records = [
        _mdns_rr(service, 12, 1, 120, _dns_name(instance)),
        _mdns_rr(instance, 33, 0x8001, 120, struct.pack("!HHH", 0, 0, int(port)) + _dns_name(host)),
        _mdns_rr(instance, 16, 0x8001, 120, txt),
        _mdns_rr(host, 1, 0x8001, 120, socket.inet_aton(ip)),
    ]
    return struct.pack("!HHHHHH", 0, 0x8400, 0, len(records), 0, 0) + b"".join(records)


def start_mdns_advertiser(port: int = 8765) -> None:
    def worker():
        group = ("224.0.0.251", 5353)
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            tx.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
        except Exception:
            pass
        rx = None
        try:
            rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            rx.bind(("", 5353))
            try:
                rx.setsockopt(
                    socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                    socket.inet_aton("224.0.0.251") + socket.inet_aton("0.0.0.0"),
                )
            except Exception:
                pass
            rx.settimeout(1.0)
        except Exception:
            if rx is not None:
                try:
                    rx.close()
                except Exception:
                    pass
            rx = None

        last_announce = 0.0
        burst = 3
        while True:
            try:
                packet = mdns_announcement_packet(port)
                now = time.monotonic()
                if burst > 0 or (now - last_announce) >= 30.0:
                    tx.sendto(packet, group)
                    last_announce = now
                    burst = max(0, burst - 1)
                if rx is not None:
                    try:
                        data, _ = rx.recvfrom(4096)
                        if b"_bcp" in data.lower():
                            tx.sendto(packet, group)
                    except socket.timeout:
                        pass
                else:
                    time.sleep(1.0 if burst > 0 else 5.0)
            except Exception:
                time.sleep(3.0)

    threading.Thread(target=worker, name="BCP-mDNS", daemon=True).start()


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
        cx.execute(
            """CREATE TABLE IF NOT EXISTS memory_records(
                project_id TEXT NOT NULL,
                layer TEXT NOT NULL,
                key TEXT NOT NULL,
                value_json TEXT NOT NULL,
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(project_id,layer,key)
            )"""
        )
        cx.execute(
            """CREATE TABLE IF NOT EXISTS jobs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                state TEXT NOT NULL,
                requires_pc INTEGER NOT NULL,
                idempotency_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                action_id TEXT NOT NULL DEFAULT '',
                priority INTEGER NOT NULL DEFAULT 50,
                resource_class TEXT NOT NULL DEFAULT 'PC_R3',
                expected_revision INTEGER,
                input_hash TEXT NOT NULL DEFAULT '',
                coordinator_epoch INTEGER NOT NULL DEFAULT 0,
                evidence_contract TEXT NOT NULL DEFAULT '',
                attempt_count INTEGER NOT NULL DEFAULT 0,
                lease_until TEXT,
                UNIQUE(project_id,idempotency_key)
            )"""
        )
        cx.execute(
            """CREATE TABLE IF NOT EXISTS job_dependencies(
                job_id INTEGER NOT NULL,
                depends_on_job_id INTEGER NOT NULL,
                PRIMARY KEY(job_id, depends_on_job_id)
            )"""
        )
        cx.execute(
            """CREATE TABLE IF NOT EXISTS missions(
                mission_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                request_text TEXT NOT NULL,
                request_digest TEXT NOT NULL,
                spec_revision TEXT NOT NULL,
                context_revision TEXT NOT NULL,
                execution_profile TEXT NOT NULL,
                allowed_capabilities_json TEXT NOT NULL,
                provider_policy_json TEXT NOT NULL,
                approval_gates_json TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                current_step TEXT NOT NULL,
                last_committed_step TEXT NOT NULL,
                next_step TEXT NOT NULL,
                last_progress_at TEXT NOT NULL,
                worker_component TEXT NOT NULL,
                receipt_evidence TEXT NOT NULL,
                status TEXT NOT NULL,
                hold_reason TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id,idempotency_key)
            )"""
        )
        cx.execute(
            """CREATE TABLE IF NOT EXISTS mission_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                step_id TEXT NOT NULL,
                worker_component TEXT NOT NULL,
                summary TEXT NOT NULL,
                evidence_ref TEXT NOT NULL,
                status TEXT NOT NULL,
                failure_hold_reason TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL,
                UNIQUE(mission_id,seq),
                UNIQUE(mission_id,idempotency_key)
            )"""
        )
        cx.execute("CREATE INDEX IF NOT EXISTS idx_mission_events_mid_seq ON mission_events(mission_id,seq)")
        cx.execute(
            """CREATE TABLE IF NOT EXISTS conversation_threads(
                conversation_id TEXT PRIMARY KEY,
                alias TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                last_sequence INTEGER NOT NULL DEFAULT 0,
                last_activity_at TEXT NOT NULL,
                last_delivery_state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        cx.execute(
            """CREATE TABLE IF NOT EXISTS conversation_messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                message_key TEXT NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                mirrored_at TEXT NOT NULL,
                delivery_state TEXT NOT NULL,
                evidence_class TEXT NOT NULL,
                linked_mission_id TEXT NOT NULL DEFAULT '',
                content_hash TEXT NOT NULL,
                seen_at TEXT NOT NULL DEFAULT '',
                producer_sequence INTEGER NOT NULL DEFAULT 0,
                producer_session_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE(conversation_id,sequence),
                UNIQUE(conversation_id,message_key)
            )"""
        )
        cx.execute("CREATE INDEX IF NOT EXISTS idx_conversation_threads_activity ON conversation_threads(last_activity_at DESC)")
        cx.execute("CREATE INDEX IF NOT EXISTS idx_conversation_messages_thread_seq ON conversation_messages(conversation_id,sequence DESC)")
        for col, ddl in (
            ("producer_sequence", "producer_sequence INTEGER NOT NULL DEFAULT 0"),
            ("producer_session_id", "producer_session_id TEXT NOT NULL DEFAULT ''")
        ):
            _ensure_sqlite_column(cx, "conversation_messages", col, ddl)
        cx.execute("CREATE INDEX IF NOT EXISTS idx_conversation_messages_producer_seq ON conversation_messages(conversation_id,producer_session_id,producer_sequence)")
        cx.execute(
            """CREATE TABLE IF NOT EXISTS conversation_producers(
                conversation_id TEXT NOT NULL,
                producer_session_id TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                sequence_floor INTEGER NOT NULL DEFAULT 1,
                announced_sequence INTEGER NOT NULL DEFAULT 0,
                last_heartbeat_at TEXT NOT NULL DEFAULT '',
                last_receipt_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY(conversation_id,producer_session_id)
            )"""
        )
        cx.execute("CREATE INDEX IF NOT EXISTS idx_conversation_producers_updated ON conversation_producers(updated_at DESC)")
        cx.execute("CREATE INDEX IF NOT EXISTS idx_missions_project_updated ON missions(project_id,updated_at)")
        for col, ddl in (
            ("evidence_class", "evidence_class TEXT NOT NULL DEFAULT 'UNCLASSIFIED'"),
            ("source_id", "source_id TEXT NOT NULL DEFAULT ''"),
            ("pinned", "pinned INTEGER NOT NULL DEFAULT 0"),
            ("expires_at", "expires_at TEXT"),
            ("supersedes_key", "supersedes_key TEXT NOT NULL DEFAULT ''")
        ):
            _ensure_sqlite_column(cx, "memory_records", col, ddl)
        for col, ddl in (
            ("action_id", "action_id TEXT NOT NULL DEFAULT ''"),
            ("priority", "priority INTEGER NOT NULL DEFAULT 50"),
            ("resource_class", "resource_class TEXT NOT NULL DEFAULT 'PC_R3'"),
            ("expected_revision", "expected_revision INTEGER"),
            ("input_hash", "input_hash TEXT NOT NULL DEFAULT ''"),
            ("coordinator_epoch", "coordinator_epoch INTEGER NOT NULL DEFAULT 0"),
            ("evidence_contract", "evidence_contract TEXT NOT NULL DEFAULT ''"),
            ("attempt_count", "attempt_count INTEGER NOT NULL DEFAULT 0"),
            ("lease_until", "lease_until TEXT")
        ):
            _ensure_sqlite_column(cx, "jobs", col, ddl)
        cx.execute("CREATE INDEX IF NOT EXISTS idx_memory_project_layer_pin ON memory_records(project_id,layer,pinned,updated_at)")
        cx.execute("CREATE INDEX IF NOT EXISTS idx_jobs_project_state_priority ON jobs(project_id,state,priority,created_at)")
        cx.commit()
    finally:
        cx.close()
    return token


def connect_db():
    cx = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    cx.row_factory = sqlite3.Row
    return cx


@contextmanager
def db_connection():
    """Transactional sqlite context that also closes the Windows file handle."""
    cx = connect_db()
    try:
        with cx:
            yield cx
    finally:
        cx.close()


MEMORY_LAYERS = ("USER_MEMORY", "PROJECT_MEMORY", "TECHNICAL_KNOWLEDGE", "OPERATING_STATE", "HISTORY", "POLICY")


def system_resources() -> dict:
    total = available = 0
    try:
        if os.name == "nt":
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                total, available = int(st.ullTotalPhys), int(st.ullAvailPhys)
        elif hasattr(os, "sysconf"):
            page = int(os.sysconf("SC_PAGE_SIZE"))
            total = page * int(os.sysconf("SC_PHYS_PAGES"))
            available = page * int(os.sysconf("SC_AVPHYS_PAGES"))
    except Exception:
        pass
    used_pct = round((1.0 - (available / total)) * 100.0, 1) if total > 0 else None
    return {"total_bytes": total, "available_bytes": available, "used_pct": used_pct}


_PC_MODE_STATE = "PC_AVAILABLE"
_PC_MODE_CHANGED_AT = 0.0


def pc_operating_mode() -> str:
    global _PC_MODE_STATE, _PC_MODE_CHANGED_AT
    r = system_resources()
    used = r.get("used_pct")
    available = int(r.get("available_bytes") or 0)
    enter_pressure = (
        (isinstance(used, (int, float)) and used >= 88.0)
        or (available > 0 and available < 384 * 1024 * 1024)
    )
    exit_pressure = (
        (not isinstance(used, (int, float)) or used <= 78.0)
        and (available == 0 or available >= 640 * 1024 * 1024)
    )
    now = time.monotonic()
    if _PC_MODE_STATE != "PC_MEMORY_PRESSURE" and enter_pressure:
        _PC_MODE_STATE = "PC_MEMORY_PRESSURE"
        _PC_MODE_CHANGED_AT = now
    elif _PC_MODE_STATE == "PC_MEMORY_PRESSURE" and exit_pressure and (now - _PC_MODE_CHANGED_AT) >= 30.0:
        _PC_MODE_STATE = "PC_AVAILABLE"
        _PC_MODE_CHANGED_AT = now
    return _PC_MODE_STATE


_MEMORY_EVIDENCE_RANK = {
    "UNTRUSTED_EXTERNAL": 0,
    "MODEL_DERIVED": 1,
    "UNCLASSIFIED": 1,
    "LOCAL_DETERMINISTIC": 2,
    "MACHINE_READBACK": 3,
    "VALIDATED": 4,
    "USER_DECLARED": 5,
    "SYSTEM_POLICY": 6,
}


def memory_put(
    project_id: str,
    layer: str,
    key: str,
    value,
    source: str = "BCP",
    evidence_class: str = "UNCLASSIFIED",
    source_id: str = "",
    pinned: bool = False,
    expires_at: str | None = None,
    supersedes_key: str = "",
) -> dict:
    layer = str(layer or "").upper()
    if layer not in MEMORY_LAYERS:
        raise ValueError("invalid_memory_layer")
    key = str(key or "").strip()
    if not key or len(key) > 180:
        raise ValueError("invalid_memory_key")
    evidence_class = str(evidence_class or "UNCLASSIFIED").upper()
    if evidence_class not in _MEMORY_EVIDENCE_RANK:
        raise ValueError("invalid_evidence_class")
    if layer in ("USER_MEMORY", "POLICY") and evidence_class not in ("USER_DECLARED", "VALIDATED", "SYSTEM_POLICY"):
        raise ValueError("memory_admission_rejected_protected_layer")
    raw = canonical_json(value)
    if len(raw.encode("utf-8")) > 64000:
        raise ValueError("memory_value_too_large")
    now = utc_now()
    with DB_LOCK:
        with db_connection() as cx:
            old = cx.execute(
                """SELECT evidence_class,pinned FROM memory_records
                   WHERE project_id=? AND layer=? AND key=?""",
                (project_id, layer, key),
            ).fetchone()
            if old and int(old["pinned"] or 0) == 1:
                old_rank = _MEMORY_EVIDENCE_RANK.get(str(old["evidence_class"]), 0)
                if _MEMORY_EVIDENCE_RANK[evidence_class] < old_rank:
                    raise ValueError("memory_admission_rejected_pinned_precedence")
            cx.execute(
                """INSERT INTO memory_records(
                       project_id,layer,key,value_json,source,updated_at,
                       evidence_class,source_id,pinned,expires_at,supersedes_key
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(project_id,layer,key) DO UPDATE SET
                       value_json=excluded.value_json,
                       source=excluded.source,
                       updated_at=excluded.updated_at,
                       evidence_class=excluded.evidence_class,
                       source_id=excluded.source_id,
                       pinned=excluded.pinned,
                       expires_at=excluded.expires_at,
                       supersedes_key=excluded.supersedes_key""",
                (
                    project_id, layer, key, raw, str(source)[:80], now,
                    evidence_class, str(source_id)[:180], 1 if pinned else 0,
                    expires_at, str(supersedes_key)[:180],
                ),
            )
    return {
        "result": "MEMORY_COMMITTED",
        "project_id": project_id,
        "layer": layer,
        "key": key,
        "evidence_class": evidence_class,
        "pinned": bool(pinned),
        "updated_at": now,
    }


def memory_list(project_id: str, limit_per_layer: int = 24) -> dict:
    limit_per_layer = max(1, min(int(limit_per_layer), 50))
    out = {k: [] for k in MEMORY_LAYERS}
    now = utc_now()
    with db_connection() as cx:
        for layer in MEMORY_LAYERS:
            rows = cx.execute(
                """SELECT key,value_json,source,updated_at,evidence_class,source_id,
                          pinned,expires_at,supersedes_key
                   FROM memory_records
                   WHERE project_id=? AND layer=?
                     AND (expires_at IS NULL OR expires_at='' OR expires_at>?)
                   ORDER BY pinned DESC, updated_at DESC LIMIT ?""",
                (project_id, layer, now, limit_per_layer),
            ).fetchall()
            for row in rows:
                out[layer].append({
                    "key": row["key"],
                    "value": json.loads(row["value_json"]),
                    "source": row["source"],
                    "source_id": row["source_id"],
                    "evidence_class": row["evidence_class"],
                    "pinned": bool(row["pinned"]),
                    "expires_at": row["expires_at"],
                    "supersedes_key": row["supersedes_key"],
                    "updated_at": row["updated_at"],
                })
    return out


def _context_relevance(entry: dict, task_terms: set[str]) -> int:
    score = 100 if entry.get("pinned") else 0
    score += 10 * _MEMORY_EVIDENCE_RANK.get(str(entry.get("evidence_class", "")), 0)
    if not task_terms:
        return score
    hay = (str(entry.get("key", "")) + " " + canonical_json(entry.get("value"))).lower()
    score += 20 * sum(1 for term in task_terms if term in hay)
    return score


def build_context_pack(project_id: str, task: str = "", byte_budget: int = 24000) -> dict:
    budget = max(4096, min(int(byte_budget), 48000))
    task_terms = {x for x in str(task).lower().replace("/", " ").replace("_", " ").split() if len(x) >= 3}
    project_memory = memory_list(project_id, 36)
    global_memory = memory_list("__global__", 24)
    selected = {k: [] for k in MEMORY_LAYERS}
    used = 0
    for layer in MEMORY_LAYERS:
        candidates = list(project_memory.get(layer, []))
        if layer in ("USER_MEMORY", "POLICY", "TECHNICAL_KNOWLEDGE"):
            candidates += list(global_memory.get(layer, []))
        candidates.sort(key=lambda e: (_context_relevance(e, task_terms), str(e.get("updated_at", ""))), reverse=True)
        for entry in candidates:
            encoded = canonical_json(entry).encode("utf-8")
            if used + len(encoded) > budget:
                continue
            selected[layer].append(entry)
            used += len(encoded)
    head = get_head(project_id)
    pack = {
        "schema": "bcp.context_pack/2",
        "project_id": project_id,
        "task": str(task)[:1000],
        "generated_at": utc_now(),
        "head": head,
        "recent_events": recent_events(project_id, 8),
        "memory": selected,
        "operating_mode": pc_operating_mode(),
        "resources": system_resources(),
        "budget": {"bytes": budget, "used_bytes": used},
        "policy": {
            "default_paid_spend_usd": 0.0,
            "llm_required_for_known_transitions": False,
            "chat_history_is_canonical": False,
            "external_content_can_self_promote": False,
        },
    }
    pack["revision_vector"] = {
        "project_revision": int(head["revision"]) if head else 0,
        "context_hash": sha256_text(canonical_json(pack)),
    }
    return pack


def enqueue_job(
    project_id: str,
    kind: str,
    payload: dict,
    idem: str,
    requires_pc: bool = True,
    priority: int = 50,
    resource_class: str = "",
    action_id: str = "",
    expected_revision: int | None = None,
    input_hash: str = "",
    coordinator_epoch: int = 0,
    evidence_contract: str = "",
    dependencies: list[int] | None = None,
) -> dict:
    if not idem or len(idem) > 200:
        raise ValueError("invalid_idempotency_key")
    if not isinstance(payload, dict):
        raise ValueError("payload_must_be_object")
    priority = max(0, min(int(priority), 100))
    resource_class = str(resource_class or ("PC_R3" if requires_pc else "EDGE_R1")).upper()
    if resource_class not in ("EDGE_R0", "EDGE_R1", "EDGE_R2", "PC_R3", "REMOTE_AI"):
        raise ValueError("invalid_resource_class")
    action_id = str(action_id or ("action-" + secrets.token_hex(12)))[:120]
    input_hash = str(input_hash or sha256_text(canonical_json(payload)))[:128]
    evidence_contract = str(evidence_contract or "EFFECT_RECEIPT_REQUIRED")[:240]
    dependencies = [int(x) for x in (dependencies or []) if int(x) > 0][:64]
    mode = pc_operating_mode()
    state = "WAITING_FOR_PC" if requires_pc and mode == "PC_MEMORY_PRESSURE" else "READY"
    if dependencies:
        state = "BLOCKED"
    now = utc_now()
    with DB_LOCK:
        with db_connection() as cx:
            cx.execute("BEGIN IMMEDIATE")
            old = cx.execute(
                "SELECT * FROM jobs WHERE project_id=? AND idempotency_key=?",
                (project_id, idem),
            ).fetchone()
            if old:
                cx.execute("COMMIT")
                return {"result": "ALREADY_QUEUED", **dict(old)}
            if expected_revision is not None:
                head = cx.execute("SELECT revision FROM heads WHERE project_id=?", (project_id,)).fetchone()
                actual = int(head["revision"]) if head else 0
                if int(expected_revision) != actual:
                    cx.execute("ROLLBACK")
                    raise ValueError(f"stale_job_revision:expected={int(expected_revision)}:actual={actual}")
            cur = cx.execute(
                """INSERT INTO jobs(
                       project_id,kind,payload_json,state,requires_pc,idempotency_key,created_at,updated_at,
                       action_id,priority,resource_class,expected_revision,input_hash,coordinator_epoch,evidence_contract
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    project_id, str(kind)[:80], canonical_json(payload), state, 1 if requires_pc else 0,
                    idem, now, now, action_id, priority, resource_class, expected_revision,
                    input_hash, int(coordinator_epoch), evidence_contract,
                ),
            )
            job_id = int(cur.lastrowid)
            for dep in dependencies:
                cx.execute(
                    "INSERT OR IGNORE INTO job_dependencies(job_id,depends_on_job_id) VALUES(?,?)",
                    (job_id, dep),
                )
            cx.execute("COMMIT")
    return {
        "result": "QUEUED",
        "job_id": job_id,
        "action_id": action_id,
        "project_id": project_id,
        "state": state,
        "priority": priority,
        "resource_class": resource_class,
        "input_hash": input_hash,
        "coordinator_epoch": int(coordinator_epoch),
        "operating_mode": mode,
    }


def jobs_snapshot(project_id: str, limit: int = 50) -> list[dict]:
    limit = max(1, min(int(limit), 100))
    with db_connection() as cx:
        rows = cx.execute(
            "SELECT * FROM jobs WHERE project_id=? ORDER BY id DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["payload"] = json.loads(d.pop("payload_json"))
        out.append(d)
    return out


MISSION_EVENT_TYPES = {
    "ACCEPTED", "NORMALIZED", "CONTEXT_RESOLVED", "PLANNED", "QUEUED",
    "STARTED", "DISPATCHED", "WAITING", "PROVIDER_WAIT", "RESULT_RECEIVED",
    "VALIDATING", "COMMITTED", "CHECKPOINTED", "RETRY_SCHEDULED", "BLOCKED",
    "HOLD", "PLATFORM_HOLD", "NETWORK_WAIT", "STALLED", "DONE", "CANCELLED",
}
MISSION_TERMINAL_STATES = {"DONE", "CANCELLED"}
MISSION_STEP_DONE_STATES = {"COMMITTED", "CHECKPOINTED", "DONE"}
WORKER_PRIORITY = {"LOCAL": 0, "B-EDGE": 1, "BEDGE": 1, "PC": 2, "REMOTE_AI": 3}


def _json_list(value, name: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(name + "_must_be_list")
    return value


def _json_dict(value, name: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(name + "_must_be_object")
    return value


def _mission_public(row) -> dict | None:
    if not row:
        return None
    d = dict(row)
    d["allowed_capabilities"] = json.loads(d.pop("allowed_capabilities_json"))
    d["provider_policy"] = json.loads(d.pop("provider_policy_json"))
    d["approval_gates"] = json.loads(d.pop("approval_gates_json"))
    d["plan"] = json.loads(d.pop("plan_json"))
    d.pop("request_text", None)
    return d


def _mission_event_public(row) -> dict:
    d = dict(row)
    d["payload"] = json.loads(d.pop("payload_json"))
    return d


def _mission_progress(plan: list[dict]) -> dict | None:
    if not plan:
        return None
    total = len(plan)
    verified = sum(1 for step in plan if bool(step.get("verified")))
    return {
        "verified_steps": verified,
        "total_steps": total,
        "percent": int((verified * 100) / total),
        "basis": "finite_externally_verifiable_plan_steps_only",
    }


def _normalize_plan(steps) -> list[dict]:
    raw = _json_list(steps, "steps")
    if not raw or len(raw) > 128:
        raise ValueError("steps_count_out_of_range")
    normalized = []
    seen = set()
    for pos, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError("step_must_be_object")
        step_id = str(item.get("id") or ("step-%02d" % pos))[:80]
        if not step_id or step_id in seen:
            raise ValueError("duplicate_or_empty_step_id")
        seen.add(step_id)
        deps = [str(x)[:80] for x in _json_list(item.get("dependencies", []), "dependencies")]
        worker = str(item.get("worker_class", "LOCAL")).upper()
        if worker not in WORKER_PRIORITY:
            raise ValueError("invalid_worker_class")
        normalized.append({
            "id": step_id,
            "label": str(item.get("label", step_id))[:240],
            "dependencies": deps,
            "worker_class": worker,
            "state": str(item.get("state", "PENDING")).upper(),
            "verified": bool(item.get("verified", False)),
        })
    known = {s["id"] for s in normalized}
    for step in normalized:
        if any(dep not in known for dep in step["dependencies"]):
            raise ValueError("unknown_step_dependency")
        if step["id"] in step["dependencies"]:
            raise ValueError("self_dependency")
    return normalized


def _next_runnable_from_plan(plan: list[dict]) -> dict | None:
    done = {
        step["id"] for step in plan
        if bool(step.get("verified")) or str(step.get("state", "")).upper() in MISSION_STEP_DONE_STATES
    }
    candidates = []
    for pos, step in enumerate(plan):
        if bool(step.get("verified")) or str(step.get("state", "")).upper() in MISSION_STEP_DONE_STATES:
            continue
        if all(dep in done for dep in step.get("dependencies", [])):
            candidates.append((WORKER_PRIORITY.get(str(step.get("worker_class", "REMOTE_AI")).upper(), 99), pos, step))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    return dict(candidates[0][2])


def mission_get(mission_id: str, include_request: bool = False) -> dict | None:
    with db_connection() as cx:
        row = cx.execute("SELECT * FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
    if not row:
        return None
    out = _mission_public(row)
    if include_request:
        out["request_text"] = row["request_text"]
    out["progress"] = _mission_progress(out["plan"])
    return out


CONVERSATION_SOURCE_KINDS = {"CHATGPT_UI", "OPENAI_API", "BCP_AGENT", "CHATGPT_PC"}
CONVERSATION_ROLES = {"USER", "ASSISTANT", "SYSTEM", "TOOL"}
CONVERSATION_DELIVERY_STATES = {
    "GENERATED", "MIRRORED_BCP", "TELEGRAM_SENT", "USER_SEEN",
    "CHATGPT_UI_DELIVERY_UNKNOWN", "DELIVERY_GAP_DETECTED"
}

_CONVERSATION_SECRET_PATTERNS = (
    re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"),
)

def _conversation_safe_text(value) -> str:
    text = str(value or "").replace("\x00", " ").strip()[:12000]
    for pattern in _CONVERSATION_SECRET_PATTERNS:
        text = pattern.sub("[REDACTED_SECRET]", text)
    return text

def conversation_append_message(conversation_id: str, *, alias: str, source_kind: str,
                                source_ref: str, message_key: str, role: str, text: str,
                                delivery_state: str, evidence_class: str = "EXTERNAL_RECEIPT",
                                generated_at: str = "", linked_mission_id: str = "",
                                producer_sequence: int = 0, producer_session_id: str = "") -> dict:
    cid = str(conversation_id or "").strip()[:64]
    if not cid or not re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", cid):
        raise ValueError("invalid_conversation_id")
    alias = str(alias or cid).strip()[:120]
    source_kind = str(source_kind or "BCP_AGENT").upper()
    role = str(role or "").upper()
    state = str(delivery_state or "MIRRORED_BCP").upper()
    message_key = str(message_key or "").strip()[:160]
    if source_kind not in CONVERSATION_SOURCE_KINDS:
        raise ValueError("invalid_conversation_source")
    if role not in CONVERSATION_ROLES:
        raise ValueError("invalid_conversation_role")
    if state not in CONVERSATION_DELIVERY_STATES:
        raise ValueError("invalid_delivery_state")
    if not message_key:
        raise ValueError("message_key_required")
    safe_text = _conversation_safe_text(text)
    if not safe_text:
        raise ValueError("message_text_required")
    now = utc_now()
    generated = str(generated_at or now)[:64]
    digest = sha256_text(safe_text)
    try:
        producer_sequence = max(0, int(producer_sequence or 0))
    except Exception:
        producer_sequence = 0
    producer_session_id = str(producer_session_id or "")[:120]
    with db_connection() as cx:
        existing = cx.execute(
            "SELECT * FROM conversation_messages WHERE conversation_id=? AND message_key=?",
            (cid, message_key),
        ).fetchone()
        if existing:
            return {"result": "ALREADY_RECORDED", "conversation_id": cid,
                    "sequence": int(existing["sequence"]), "content_hash": existing["content_hash"]}
        thread = cx.execute("SELECT * FROM conversation_threads WHERE conversation_id=?", (cid,)).fetchone()
        seq = int(thread["last_sequence"] if thread else 0) + 1
        cx.execute(
            """INSERT INTO conversation_messages(
                conversation_id,sequence,message_key,role,text,generated_at,mirrored_at,
                delivery_state,evidence_class,linked_mission_id,content_hash,seen_at,
                producer_sequence,producer_session_id,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cid, seq, message_key, role, safe_text, generated, now, state,
             str(evidence_class or "EXTERNAL_RECEIPT")[:80],
             str(linked_mission_id or "")[:80], digest, "",
             producer_sequence, producer_session_id, now),
        )
        if thread:
            cx.execute(
                """UPDATE conversation_threads SET alias=?,source_kind=?,source_ref=?,
                   last_sequence=?,last_activity_at=?,last_delivery_state=?,updated_at=?
                   WHERE conversation_id=?""",
                (alias, source_kind, str(source_ref or "")[:240], seq, now, state, now, cid),
            )
        else:
            cx.execute(
                """INSERT INTO conversation_threads(
                    conversation_id,alias,source_kind,source_ref,last_sequence,last_activity_at,
                    last_delivery_state,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (cid, alias, source_kind, str(source_ref or "")[:240], seq, now, state, now, now),
            )
    return {"result": "RECORDED", "conversation_id": cid, "sequence": seq,
            "content_hash": digest, "delivery_state": state}

def conversation_register_producer(conversation_id: str, producer_session_id: str,
                                   announced_sequence: int, source_kind: str = "BCP_AGENT",
                                   source_ref: str = "", sequence_floor: int = 1,
                                   heartbeat_at: str = "") -> dict:
    cid = str(conversation_id or "").strip()[:64]
    sid = str(producer_session_id or "").strip()[:120]
    if not cid or not re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", cid):
        raise ValueError("invalid_conversation_id")
    if not sid:
        raise ValueError("producer_session_id_required")
    source_kind = str(source_kind or "BCP_AGENT").upper()
    if source_kind not in CONVERSATION_SOURCE_KINDS:
        raise ValueError("invalid_conversation_source")
    try:
        announced = max(0, int(announced_sequence or 0))
        floor = max(1, int(sequence_floor or 1))
    except Exception:
        raise ValueError("invalid_producer_sequence")
    if announced and floor > announced:
        floor = announced
    now = utc_now()
    hb = str(heartbeat_at or now)[:64]
    with db_connection() as cx:
        old = cx.execute(
            "SELECT announced_sequence,sequence_floor FROM conversation_producers "
            "WHERE conversation_id=? AND producer_session_id=?",
            (cid, sid),
        ).fetchone()
        announced = max(announced, int(old["announced_sequence"]) if old else 0)
        floor = min(floor, int(old["sequence_floor"]) if old else floor)
        cx.execute(
            """INSERT INTO conversation_producers(
                   conversation_id,producer_session_id,source_kind,source_ref,sequence_floor,
                   announced_sequence,last_heartbeat_at,last_receipt_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(conversation_id,producer_session_id) DO UPDATE SET
                   source_kind=excluded.source_kind,
                   source_ref=excluded.source_ref,
                   sequence_floor=MIN(conversation_producers.sequence_floor,excluded.sequence_floor),
                   announced_sequence=MAX(conversation_producers.announced_sequence,excluded.announced_sequence),
                   last_heartbeat_at=excluded.last_heartbeat_at,
                   updated_at=excluded.updated_at""",
            (cid, sid, source_kind, str(source_ref or "")[:240], floor,
             announced, hb, "", now),
        )
    return {
        "ok": True, "conversation_id": cid, "producer_session_id": sid,
        "announced_sequence": announced, "sequence_floor": floor, "heartbeat_at": hb,
    }

def conversation_touch_producer_receipt(conversation_id: str, producer_session_id: str,
                                        producer_sequence: int, source_kind: str,
                                        source_ref: str = "") -> None:
    if not producer_session_id or int(producer_sequence or 0) <= 0:
        return
    cid = str(conversation_id)[:64]
    sid = str(producer_session_id)[:120]
    seq = int(producer_sequence)
    now = utc_now()
    conversation_register_producer(cid, sid, seq, source_kind, source_ref, seq, now)
    with db_connection() as cx:
        cx.execute(
            "UPDATE conversation_producers SET last_receipt_at=?,updated_at=? "
            "WHERE conversation_id=? AND producer_session_id=?",
            (now, now, cid, sid),
        )

def conversation_producer_sync(conversation_id: str = "") -> list[dict]:
    params = []
    where = ""
    if conversation_id:
        where = "WHERE conversation_id=?"
        params.append(str(conversation_id)[:64])
    with db_connection() as cx:
        producers = cx.execute(
            """SELECT conversation_id,producer_session_id,source_kind,source_ref,sequence_floor,
                      announced_sequence,last_heartbeat_at,last_receipt_at,updated_at
               FROM conversation_producers """ + where + " ORDER BY updated_at DESC",
            tuple(params),
        ).fetchall()
        messages = cx.execute(
            """SELECT conversation_id,producer_session_id,producer_sequence
               FROM conversation_messages
               WHERE producer_sequence>0 AND producer_session_id<>'' """
               + ("AND conversation_id=? " if conversation_id else "")
               + "ORDER BY conversation_id,producer_session_id,producer_sequence",
            tuple(params),
        ).fetchall()
    received = {}
    for row in messages:
        key = (row["conversation_id"], row["producer_session_id"])
        received.setdefault(key, set()).add(int(row["producer_sequence"]))
    out = []
    for row in producers:
        item = dict(row)
        key = (item["conversation_id"], item["producer_session_id"])
        seqs = received.get(key, set())
        floor = max(1, int(item.get("sequence_floor") or 1))
        announced = max(0, int(item.get("announced_sequence") or 0))
        cursor = floor
        while cursor in seqs and cursor <= announced:
            cursor += 1
        contiguous = min(announced, cursor - 1) if announced else (cursor - 1)
        missing = []
        if announced >= floor:
            start = None
            for n in range(floor, announced + 1):
                if n not in seqs and start is None:
                    start = n
                elif n in seqs and start is not None:
                    missing.append((start, n - 1))
                    start = None
            if start is not None:
                missing.append((start, announced))
        item.update({
            "highest_received_sequence": max(seqs) if seqs else 0,
            "contiguous_received_sequence": contiguous,
            "missing_count": sum(b - a + 1 for a, b in missing),
            "missing_ranges": [{"from": a, "to": b} for a, b in missing[:20]],
            "sync_state": "COMPLETE" if not missing else "INCOMPLETE",
        })
        out.append(item)
    return out

def write_conversation_receipt_ack() -> dict:
    producers = conversation_producer_sync("")
    payload = {
        "schema": "bcp.conversation_receipt_ack/1",
        "updated_at": utc_now(),
        "producer_count": len(producers),
        "producers": producers,
    }
    atomic_json(CONVERSATION_RECEIPT_ACK, payload)
    return payload

def conversation_sequence_gaps(conversation_id: str = "", limit: int = 20) -> list[dict]:
    limit = max(1, min(int(limit), 100))
    out = []
    sync = conversation_producer_sync(conversation_id)
    if sync:
        for item in sync:
            for r in item.get("missing_ranges", []):
                out.append({
                    "conversation_id": item["conversation_id"],
                    "producer_session_id": item["producer_session_id"],
                    "missing_from": int(r["from"]),
                    "missing_to": int(r["to"]),
                    "missing_count": int(r["to"]) - int(r["from"]) + 1,
                    "announced_sequence": int(item.get("announced_sequence") or 0),
                    "state": "SEQUENCE_GAP",
                })
                if len(out) >= limit:
                    return out
        return out

    # Compatibility fallback for R25-era receipts that predate producer watermarks.
    params = []
    where = "WHERE producer_sequence>0 AND producer_session_id<>''"
    if conversation_id:
        where += " AND conversation_id=?"
        params.append(str(conversation_id)[:64])
    with db_connection() as cx:
        rows = cx.execute(
            f"""SELECT conversation_id,producer_session_id,producer_sequence
                FROM conversation_messages {where}
                ORDER BY conversation_id,producer_session_id,producer_sequence""",
            tuple(params),
        ).fetchall()
    groups = {}
    for row in rows:
        key = (row["conversation_id"], row["producer_session_id"])
        groups.setdefault(key, []).append(int(row["producer_sequence"]))
    for (cid, sid), seqs in groups.items():
        unique = sorted(set(x for x in seqs if x > 0))
        if len(unique) < 2:
            continue
        prev = unique[0]
        for cur in unique[1:]:
            if cur > prev + 1:
                out.append({
                    "conversation_id": cid, "producer_session_id": sid,
                    "missing_from": prev + 1, "missing_to": cur - 1,
                    "missing_count": cur - prev - 1, "state": "SEQUENCE_GAP",
                })
                if len(out) >= limit:
                    return out
            prev = cur
    return out

def conversation_ingest_receipt(receipt: dict) -> dict:
    if not isinstance(receipt, dict):
        raise ValueError("receipt_must_be_object")
    schema = str(receipt.get("schema") or "")
    if schema == "bcp.conversation_producer_heartbeat/1":
        registered = conversation_register_producer(
            receipt.get("conversation_id"),
            receipt.get("producer_session_id"),
            receipt.get("announced_sequence") or 0,
            receipt.get("source_kind") or "BCP_AGENT",
            receipt.get("source_ref") or "",
            receipt.get("sequence_floor") or 1,
            receipt.get("heartbeat_at") or "",
        )
        registered["sequence_gaps"] = conversation_sequence_gaps(str(receipt.get("conversation_id") or ""), 20)
        return registered
    if schema not in {"bcp.conversation_receipt/1", "bcp.conversation_receipt/2"}:
        raise ValueError("unsupported_receipt_schema")
    result = conversation_append_message(
        receipt.get("conversation_id"),
        alias=receipt.get("alias") or receipt.get("conversation_id"),
        source_kind=receipt.get("source_kind") or "BCP_AGENT",
        source_ref=receipt.get("source_ref") or "",
        message_key=receipt.get("message_key") or "",
        role=receipt.get("role") or "",
        text=receipt.get("text") or "",
        delivery_state=receipt.get("delivery_state") or "MIRRORED_BCP",
        evidence_class=receipt.get("evidence_class") or "PRODUCER_RECEIPT",
        generated_at=receipt.get("generated_at") or "",
        linked_mission_id=receipt.get("linked_mission_id") or "",
        producer_sequence=receipt.get("producer_sequence") or 0,
        producer_session_id=receipt.get("producer_session_id") or "",
    )
    conversation_touch_producer_receipt(
        receipt.get("conversation_id"),
        receipt.get("producer_session_id") or "",
        int(receipt.get("producer_sequence") or 0),
        receipt.get("source_kind") or "BCP_AGENT",
        receipt.get("source_ref") or "",
    )
    result["sequence_gaps"] = conversation_sequence_gaps(str(receipt.get("conversation_id") or ""), 20)
    return result

def process_conversation_receipt_inbox(max_lines: int = 64) -> dict:
    """Consume local append-only receipts incrementally; no cloud transcript dependency."""
    path = CONVERSATION_RECEIPT_INBOX
    if not path.is_file():
        return {"processed": 0, "accepted": 0, "rejected": 0, "offset": 0}
    state = read_json(CONVERSATION_RECEIPT_CURSOR, {}) or {}
    try:
        offset = max(0, int(state.get("offset") or 0))
        size = path.stat().st_size
        if offset > size:
            offset = 0
    except Exception:
        offset = 0
    processed = accepted = rejected = 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        fh.seek(offset)
        while processed < max(1, min(int(max_lines), 256)):
            raw = fh.readline(32769)
            if not raw:
                break
            processed += 1
            if len(raw) > 32768 and not raw.endswith("\n"):
                rejected += 1
                continue
            try:
                obj = json.loads(raw)
                conversation_ingest_receipt(obj)
                accepted += 1
            except Exception:
                rejected += 1
        offset = fh.tell()
    atomic_json(CONVERSATION_RECEIPT_CURSOR, {
        "schema": "bcp.conversation_receipt_cursor/1",
        "offset": offset,
        "processed": processed,
        "accepted": accepted,
        "rejected": rejected,
        "updated_at": utc_now(),
    })
    write_conversation_receipt_ack()
    return {"processed": processed, "accepted": accepted, "rejected": rejected, "offset": offset}

def chatgpt_pc_flow_db_path() -> Path:
    override = os.environ.get("BCP_CHATGPT_PC_FLOW_DB", "").strip()
    if override:
        return Path(override)
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    return local / "Tunnel_PC_G4" / "state" / "flow_ledger.sqlite3"

def _chatgpt_pc_conversation_id(session_id: str, mission_id: str) -> str:
    material = (str(session_id or "") + "\n" + str(mission_id or "")).strip() or "default"
    return "cgp-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]

def sync_chatgpt_pc_flow_ledger(max_events: int = CHATGPT_PC_FLOW_BATCH) -> dict:
    """Read ChatGPT-PC's local append-only flow ledger without mutating it."""
    source = chatgpt_pc_flow_db_path()
    state = read_json(CHATGPT_PC_FLOW_BRIDGE_CURSOR, {}) or {}
    last_source_seq = max(0, int(state.get("last_source_seq") or 0))
    counters = state.get("conversation_counters") if isinstance(state.get("conversation_counters"), dict) else {}
    if not source.is_file():
        status = {
            "schema": "bcp.chatgpt_pc_flow_bridge/1", "status": "NOT_OBSERVED",
            "source": str(source), "last_source_seq": last_source_seq,
            "updated_at": utc_now(), "imported": 0, "backlog": None,
        }
        atomic_json(CHATGPT_PC_FLOW_BRIDGE_STATUS, status)
        return status

    rows = []
    backlog = 0
    source_high_seq = last_source_seq
    try:
        uri = "file:" + str(source.resolve()).replace("\\", "/") + "?mode=ro"
        cx = sqlite3.connect(uri, uri=True, timeout=1)
        cx.row_factory = sqlite3.Row
        try:
            high = cx.execute(
                """SELECT COALESCE(MAX(seq),0) FROM flow_events
                   WHERE kind IN ('conversation_message_exact','assistant_visible_message_exact')
                     AND role IN ('user','assistant')"""
            ).fetchone()
            source_high_seq = int(high[0] or 0)
            rows = cx.execute(
                """SELECT seq,event_id,at,session_id,mission_id,kind,role,exact_utf8,
                          source,evidence_ref,text_sha256,chain_sha256
                   FROM flow_events
                   WHERE seq>? AND kind IN ('conversation_message_exact','assistant_visible_message_exact')
                     AND role IN ('user','assistant')
                   ORDER BY seq LIMIT ?""",
                (last_source_seq, max(1, min(int(max_events), 64))),
            ).fetchall()
            pending = cx.execute(
                """SELECT COUNT(*) FROM flow_events
                   WHERE seq>? AND kind IN ('conversation_message_exact','assistant_visible_message_exact')
                     AND role IN ('user','assistant')""",
                (last_source_seq,),
            ).fetchone()
            backlog = int(pending[0] or 0)
        finally:
            cx.close()
    except Exception as ex:
        status = {
            "schema": "bcp.chatgpt_pc_flow_bridge/1", "status": "SOURCE_READ_DEFERRED",
            "source": str(source), "last_source_seq": last_source_seq,
            "updated_at": utc_now(), "imported": 0, "backlog": None,
            "error_class": type(ex).__name__,
        }
        atomic_json(CHATGPT_PC_FLOW_BRIDGE_STATUS, status)
        return status

    imported = duplicates = rejected = 0
    for row in rows:
        seq = int(row["seq"])
        try:
            raw = row["exact_utf8"]
            if raw is None:
                raise ValueError("missing_exact_text")
            raw_bytes = bytes(raw) if isinstance(raw, (bytes, bytearray, memoryview)) else str(raw).encode("utf-8")
            text = raw_bytes.decode("utf-8", "strict")
            declared = str(row["text_sha256"] or "").lower()
            actual = hashlib.sha256(raw_bytes).hexdigest()
            if declared and declared != actual:
                raise ValueError("source_text_sha256_mismatch")

            session_id = str(row["session_id"] or "")
            mission_id = str(row["mission_id"] or "")
            cid = _chatgpt_pc_conversation_id(session_id, mission_id)
            producer_session = "chatgptpc-" + hashlib.sha256(
                (session_id or mission_id or "default").encode("utf-8")
            ).hexdigest()[:20]
            producer_seq = int(counters.get(cid) or 0) + 1
            alias = ("ChatGPT-PC · " + (mission_id or session_id or "conversation"))[:120]
            role = str(row["role"] or "").upper()
            delivery = "CHATGPT_UI_DELIVERY_UNKNOWN" if role == "ASSISTANT" else "MIRRORED_BCP"
            receipt = conversation_append_message(
                cid,
                alias=alias,
                source_kind="CHATGPT_PC",
                source_ref="flow_ledger.sqlite3#seq=" + str(seq),
                message_key="chatgptpc-flow:" + str(row["event_id"] or seq),
                role=role,
                text=text,
                delivery_state=delivery,
                evidence_class="CHATGPT_PC_FLOW_LEDGER",
                generated_at=str(row["at"] or ""),
                linked_mission_id=mission_id,
                producer_sequence=producer_seq,
                producer_session_id=producer_session,
            )
            if receipt.get("result") == "ALREADY_RECORDED":
                duplicates += 1
            else:
                imported += 1
                counters[cid] = producer_seq
                conversation_touch_producer_receipt(
                    cid, producer_session, producer_seq, "CHATGPT_PC",
                    "flow_ledger.sqlite3#seq=" + str(seq),
                )
            last_source_seq = max(last_source_seq, seq)
        except Exception:
            rejected += 1
            # Fail closed on the bad source row: do not advance beyond it.
            break

    atomic_json(CHATGPT_PC_FLOW_BRIDGE_CURSOR, {
        "schema": "bcp.chatgpt_pc_flow_cursor/1",
        "last_source_seq": last_source_seq,
        "source_high_seq": source_high_seq,
        "conversation_counters": counters,
        "updated_at": utc_now(),
    })
    write_conversation_receipt_ack()
    remaining = max(0, backlog - len(rows))
    status = {
        "schema": "bcp.chatgpt_pc_flow_bridge/1",
        "status": "CAUGHT_UP" if remaining == 0 and rejected == 0 else ("SOURCE_ROW_HOLD" if rejected else "CATCHING_UP"),
        "source": str(source),
        "last_source_seq": last_source_seq,
        "source_high_seq": source_high_seq,
        "imported": imported,
        "duplicates": duplicates,
        "rejected": rejected,
        "backlog": remaining,
        "updated_at": utc_now(),
        "read_only": True,
    }
    atomic_json(CHATGPT_PC_FLOW_BRIDGE_STATUS, status)
    return status

def start_conversation_receipt_worker() -> None:
    def worker():
        while True:
            try:
                process_conversation_receipt_inbox(64)
            except Exception:
                pass
            try:
                sync_chatgpt_pc_flow_ledger(CHATGPT_PC_FLOW_BATCH)
            except Exception:
                pass
            time.sleep(CONVERSATION_RECEIPT_POLL_SECONDS)
    threading.Thread(target=worker, name="BCP-conversation-receipts", daemon=True).start()


def _iso_age_seconds(value: str) -> int | None:
    try:
        parsed = dt.datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return max(0, int((dt.datetime.now(dt.timezone.utc) - parsed.astimezone(dt.timezone.utc)).total_seconds()))
    except Exception:
        return None

def conversation_delivery_gaps(threshold_seconds: int = 5 * 60, limit: int = 20) -> list[dict]:
    """Derive unanswered delivery risk without inventing hidden ChatGPT/UI state."""
    threshold_seconds = max(60, min(int(threshold_seconds), 24 * 60 * 60))
    limit = max(1, min(int(limit), 50))
    with db_connection() as cx:
        rows = cx.execute(
            """SELECT m.conversation_id,m.sequence,m.role,m.text,m.generated_at,m.mirrored_at,
                      m.delivery_state,m.evidence_class,m.linked_mission_id,m.content_hash,m.seen_at,
                      t.alias,t.source_kind,t.last_activity_at
               FROM conversation_messages m
               JOIN conversation_threads t ON t.conversation_id=m.conversation_id
               WHERE m.role='ASSISTANT'
                 AND m.delivery_state IN ('GENERATED','MIRRORED_BCP','CHATGPT_UI_DELIVERY_UNKNOWN','DELIVERY_GAP_DETECTED')
                 AND COALESCE(m.seen_at,'')=''
               ORDER BY m.mirrored_at ASC LIMIT ?""",
            (max(limit * 4, 20),),
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        age = _iso_age_seconds(item.get("mirrored_at") or item.get("generated_at"))
        if age is None or age < threshold_seconds:
            continue
        item["age_seconds"] = age
        item["derived_state"] = "DELIVERY_GAP_DETECTED"
        item["reason"] = "assistant_message_without_positive_downstream_seen_evidence"
        item["text"] = _conversation_safe_text(item.get("text"))[:700]
        out.append(item)
        if len(out) >= limit:
            break
    return out

def conversation_list(limit: int = 8) -> list[dict]:
    limit = max(1, min(int(limit), 20))
    with db_connection() as cx:
        rows = cx.execute(
            """SELECT conversation_id,alias,source_kind,source_ref,last_sequence,last_activity_at,
                      last_delivery_state,created_at,updated_at
               FROM conversation_threads ORDER BY last_activity_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]

def conversation_messages(conversation_id: str, limit: int = 8) -> list[dict]:
    limit = max(1, min(int(limit), 20))
    with db_connection() as cx:
        rows = cx.execute(
            """SELECT conversation_id,sequence,message_key,role,text,generated_at,mirrored_at,
                      delivery_state,evidence_class,linked_mission_id,content_hash,seen_at,
                      producer_sequence,producer_session_id
               FROM conversation_messages WHERE conversation_id=?
               ORDER BY sequence DESC LIMIT ?""",
            (str(conversation_id)[:64], limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]

def _elapsed_seconds_between(start_value: str, end_value: str) -> int | None:
    try:
        start = dt.datetime.fromisoformat(str(start_value or "").replace("Z", "+00:00"))
        end = dt.datetime.fromisoformat(str(end_value or "").replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=dt.timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=dt.timezone.utc)
        return max(0, int((end.astimezone(dt.timezone.utc) - start.astimezone(dt.timezone.utc)).total_seconds()))
    except Exception:
        return None

def conversation_latency_summary(conversation_id: str) -> dict:
    cid = str(conversation_id or "")[:64]
    messages = conversation_messages(cid, 20)
    assistant = None
    user = None
    for msg in reversed(messages):
        if assistant is None and str(msg.get("role") or "").upper() == "ASSISTANT":
            assistant = msg
            continue
        if assistant is not None and str(msg.get("role") or "").upper() == "USER":
            user = msg
            break
    out = {
        "schema": "bcp.conversation_latency/1",
        "conversation_id": cid,
        "producer_response_seconds": None,
        "producer_to_bcp_mirror_seconds": None,
        "bcp_mirror_to_seen_seconds": None,
        "user_to_seen_seconds": None,
        "seen_evidence": False,
        "truth_boundary": "MEASURED_FROM_DURABLE_RECEIPT_TIMESTAMPS_ONLY",
    }
    if not assistant:
        return out
    if user:
        out["producer_response_seconds"] = _elapsed_seconds_between(
            user.get("generated_at"), assistant.get("generated_at")
        )
    out["producer_to_bcp_mirror_seconds"] = _elapsed_seconds_between(
        assistant.get("generated_at"), assistant.get("mirrored_at")
    )
    if assistant.get("seen_at"):
        out["seen_evidence"] = True
        out["bcp_mirror_to_seen_seconds"] = _elapsed_seconds_between(
            assistant.get("mirrored_at"), assistant.get("seen_at")
        )
        if user:
            out["user_to_seen_seconds"] = _elapsed_seconds_between(
                user.get("generated_at"), assistant.get("seen_at")
            )
    out["assistant_sequence"] = int(assistant.get("sequence") or 0)
    out["assistant_delivery_state"] = str(assistant.get("delivery_state") or "")
    return out

def conversation_mark_seen(conversation_id: str, sequence: int = 0) -> dict:
    cid = str(conversation_id or "")[:64]
    now = utc_now()
    with db_connection() as cx:
        if sequence > 0:
            cur = cx.execute(
                """UPDATE conversation_messages SET seen_at=?,delivery_state='USER_SEEN'
                   WHERE conversation_id=? AND sequence=?""",
                (now, cid, int(sequence)),
            )
        else:
            cur = cx.execute(
                """UPDATE conversation_messages SET seen_at=?,delivery_state='USER_SEEN'
                   WHERE conversation_id=? AND sequence=(
                     SELECT MAX(sequence) FROM conversation_messages WHERE conversation_id=?
                   )""",
                (now, cid, cid),
            )
        latest = cx.execute(
            "SELECT delivery_state FROM conversation_messages WHERE conversation_id=? ORDER BY sequence DESC LIMIT 1",
            (cid,),
        ).fetchone()
        if latest:
            cx.execute(
                "UPDATE conversation_threads SET last_delivery_state=?,updated_at=? WHERE conversation_id=?",
                (latest["delivery_state"], now, cid),
            )
    return {"ok": True, "conversation_id": cid, "updated": int(cur.rowcount or 0), "seen_at": now}


def mission_tail(mission_id: str, limit: int = 12) -> list[dict]:
    limit = max(1, min(int(limit), 50))
    with db_connection() as cx:
        rows = cx.execute(
            "SELECT * FROM mission_events WHERE mission_id=? ORDER BY seq DESC LIMIT ?",
            (mission_id, limit),
        ).fetchall()
    return [_mission_event_public(x) for x in reversed(rows)]


def accept_mission(
    project_id: str,
    request_text: str,
    idempotency_key: str,
    spec_revision: str = "",
    context_revision: str = "",
    execution_profile: str = "NORMAL",
    allowed_capabilities=None,
    provider_policy=None,
    approval_gates=None,
) -> dict:
    project_id = str(project_id or "").strip()[:128]
    request_text = str(request_text or "").strip()
    idempotency_key = str(idempotency_key or "").strip()[:200]
    if not project_id:
        raise ValueError("project_id_required")
    if not request_text or len(request_text) > 50000:
        raise ValueError("request_text_invalid")
    if not idempotency_key:
        raise ValueError("idempotency_key_required")
    profile = str(execution_profile or "NORMAL").upper()
    if profile not in ("FAST", "NORMAL", "DEEP", "AUDIT"):
        raise ValueError("invalid_execution_profile")
    capabilities = [str(x)[:100] for x in _json_list(allowed_capabilities or [], "allowed_capabilities")]
    policy = _json_dict(provider_policy or {}, "provider_policy")
    if float(policy.get("default_paid_spend_usd", 0.0) or 0.0) != 0.0:
        raise ValueError("paid_spend_policy_must_be_zero")
    policy = {
        "default_paid_spend_usd": 0.0,
        "local_first": True,
        "field_qualified_free_only": True,
        **policy,
    }
    if float(policy.get("default_paid_spend_usd", 0.0) or 0.0) != 0.0:
        raise ValueError("paid_spend_policy_must_be_zero")
    gates = [str(x)[:160] for x in _json_list(approval_gates or [], "approval_gates")]
    created = utc_now()
    digest = sha256_text(request_text)
    with DB_LOCK:
        cx = connect_db()
        try:
            cx.execute("BEGIN IMMEDIATE")
            old = cx.execute(
                "SELECT * FROM missions WHERE project_id=? AND idempotency_key=?",
                (project_id, idempotency_key),
            ).fetchone()
            if old:
                cx.execute("COMMIT")
                return {"result": "ALREADY_ACCEPTED", "mission": _mission_public(old)}
            mission_id = "M-" + secrets.token_hex(8)
            cx.execute(
                """INSERT INTO missions(
                    mission_id,project_id,request_text,request_digest,spec_revision,context_revision,
                    execution_profile,allowed_capabilities_json,provider_policy_json,approval_gates_json,
                    idempotency_key,current_step,last_committed_step,next_step,last_progress_at,
                    worker_component,receipt_evidence,status,hold_reason,plan_json,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    mission_id, project_id, request_text, digest, str(spec_revision)[:120],
                    str(context_revision)[:120], profile, canonical_json(capabilities),
                    canonical_json(policy), canonical_json(gates), idempotency_key,
                    "MISSION_ACCEPTED", "", "RESOLVE_CONTEXT", created, "BCP",
                    "", "ACCEPTED", "", "[]", created, created,
                ),
            )
            envelope = {
                "mission_id": mission_id,
                "seq": 1,
                "event_type": "ACCEPTED",
                "step_id": "MISSION_ACCEPTED",
                "worker_component": "BCP",
                "summary": "Mission persisted before significant work.",
                "evidence_ref": "",
                "status": "ACCEPTED",
                "failure_hold_reason": "",
                "payload": {
                    "request_digest": digest,
                    "next_step": "RESOLVE_CONTEXT",
                    "zero_paid_spend_usd": 0.0,
                },
                "idempotency_key": "accept:" + idempotency_key,
                "created_at": created,
                "prev_hash": "GENESIS",
            }
            event_hash = sha256_text(canonical_json(envelope))
            cx.execute(
                """INSERT INTO mission_events(
                    mission_id,seq,event_type,step_id,worker_component,summary,evidence_ref,status,
                    failure_hold_reason,payload_json,idempotency_key,created_at,prev_hash,event_hash
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    mission_id, 1, "ACCEPTED", "MISSION_ACCEPTED", "BCP",
                    "Mission persisted before significant work.", "", "ACCEPTED", "",
                    canonical_json(envelope["payload"]), "accept:" + idempotency_key,
                    created, "GENESIS", event_hash,
                ),
            )
            cx.execute("COMMIT")
        except Exception:
            try:
                cx.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            cx.close()
    return {"result": "MISSION_ACCEPTED", "mission": mission_get(mission_id)}


def append_mission_event(
    mission_id: str,
    event_type: str,
    idempotency_key: str,
    *,
    step_id: str = "",
    worker_component: str = "",
    summary: str = "",
    evidence_ref: str = "",
    status: str = "",
    failure_hold_reason: str = "",
    payload=None,
) -> dict:
    event_type = str(event_type or "").upper()
    if event_type not in MISSION_EVENT_TYPES:
        raise ValueError("invalid_mission_event_type")
    idempotency_key = str(idempotency_key or "").strip()[:200]
    if not idempotency_key:
        raise ValueError("idempotency_key_required")
    extra = _json_dict(payload or {}, "payload")
    now = utc_now()
    with DB_LOCK:
        cx = connect_db()
        try:
            cx.execute("BEGIN IMMEDIATE")
            mission = cx.execute("SELECT * FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
            if not mission:
                cx.execute("ROLLBACK")
                raise ValueError("mission_not_found")
            old = cx.execute(
                "SELECT * FROM mission_events WHERE mission_id=? AND idempotency_key=?",
                (mission_id, idempotency_key),
            ).fetchone()
            if old:
                cx.execute("COMMIT")
                return {"result": "ALREADY_RECORDED", "event": _mission_event_public(old), "mission": mission_get(mission_id)}
            last = cx.execute(
                "SELECT * FROM mission_events WHERE mission_id=? ORDER BY seq DESC LIMIT 1",
                (mission_id,),
            ).fetchone()
            seq = int(last["seq"]) + 1 if last else 1
            prev_hash = last["event_hash"] if last else "GENESIS"
            plan = json.loads(mission["plan_json"])
            sid = str(step_id or extra.get("step_id") or mission["current_step"])[:100]
            step_state = str(extra.get("step_state", "")).upper()
            if sid and step_state:
                for item in plan:
                    if item.get("id") == sid:
                        item["state"] = step_state
                        if "verified" in extra:
                            item["verified"] = bool(extra.get("verified"))
                        break
            if "plan" in extra:
                plan = _normalize_plan(extra["plan"])
            current_step = str(extra.get("current_step") or sid or mission["current_step"])[:160]
            last_committed = str(mission["last_committed_step"])
            if event_type == "COMMITTED":
                last_committed = sid or current_step
            next_step = str(extra.get("next_step", mission["next_step"]))[:160]
            if plan and not next_step:
                nxt = _next_runnable_from_plan(plan)
                next_step = nxt["id"] if nxt else ""
            worker = str(worker_component or extra.get("worker_component") or mission["worker_component"])[:120]
            evidence = str(evidence_ref or extra.get("evidence_ref") or "")[:500]
            new_status = str(status or extra.get("status") or event_type)[:80]
            hold = str(failure_hold_reason or extra.get("failure_hold_reason") or "")[:500]
            event_payload = dict(extra)
            event_payload.pop("plan", None)
            envelope = {
                "mission_id": mission_id,
                "seq": seq,
                "event_type": event_type,
                "step_id": sid,
                "worker_component": worker,
                "summary": str(summary)[:500],
                "evidence_ref": evidence,
                "status": new_status,
                "failure_hold_reason": hold,
                "payload": event_payload,
                "idempotency_key": idempotency_key,
                "created_at": now,
                "prev_hash": prev_hash,
            }
            event_hash = sha256_text(canonical_json(envelope))
            cur = cx.execute(
                """INSERT INTO mission_events(
                    mission_id,seq,event_type,step_id,worker_component,summary,evidence_ref,status,
                    failure_hold_reason,payload_json,idempotency_key,created_at,prev_hash,event_hash
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    mission_id, seq, event_type, sid, worker, str(summary)[:500], evidence,
                    new_status, hold, canonical_json(event_payload), idempotency_key,
                    now, prev_hash, event_hash,
                ),
            )
            cx.execute(
                """UPDATE missions SET current_step=?,last_committed_step=?,next_step=?,
                   last_progress_at=?,worker_component=?,receipt_evidence=?,status=?,hold_reason=?,
                   plan_json=?,updated_at=? WHERE mission_id=?""",
                (
                    current_step, last_committed, next_step, now, worker, evidence, new_status,
                    hold, canonical_json(plan), now, mission_id,
                ),
            )
            cx.execute("COMMIT")
            return {
                "result": "RECORDED",
                "event_id": int(cur.lastrowid),
                "seq": seq,
                "event_hash": event_hash,
                "mission": mission_get(mission_id),
            }
        except Exception:
            try:
                cx.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            cx.close()


def set_mission_plan(mission_id: str, steps, idempotency_key: str) -> dict:
    plan = _normalize_plan(steps)
    first = _next_runnable_from_plan(plan)
    return append_mission_event(
        mission_id,
        "PLANNED",
        idempotency_key,
        step_id="PLAN",
        worker_component="BCP",
        summary="Bounded dependency plan persisted.",
        status="PLANNED",
        payload={
            "plan": plan,
            "current_step": "PLAN",
            "next_step": first["id"] if first else "",
        },
    )


def mission_next_action(mission_id: str) -> dict:
    mission = mission_get(mission_id)
    if not mission:
        raise ValueError("mission_not_found")
    if mission["status"] in MISSION_TERMINAL_STATES:
        return {"mission_id": mission_id, "terminal": True, "next_action": None}
    step = _next_runnable_from_plan(mission["plan"])
    if step:
        return {
            "mission_id": mission_id,
            "terminal": False,
            "next_action": step,
            "selection_policy": "dependencies_then_local_first",
        }
    return {
        "mission_id": mission_id,
        "terminal": False,
        "next_action": {"id": mission.get("next_step") or "", "worker_class": "UNSPECIFIED"},
        "selection_policy": "durable_next_step_fallback",
    }


def mission_where(mission_id: str) -> dict:
    mission = mission_get(mission_id)
    if not mission:
        raise ValueError("mission_not_found")
    events = mission_tail(mission_id, 1)
    state = mission["status"]
    try:
        last = dt.datetime.fromisoformat(mission["last_progress_at"].replace("Z", "+00:00"))
        elapsed = max(0, int((dt.datetime.now(dt.timezone.utc) - last).total_seconds()))
    except Exception:
        elapsed = None
    observable = state
    if state not in MISSION_TERMINAL_STATES and state not in (
        "WAITING", "PROVIDER_WAIT", "PLATFORM_HOLD", "NETWORK_WAIT", "STALLED", "HOLD", "BLOCKED"
    ) and elapsed is not None and elapsed >= 60:
        observable = "NO_NEW_EXTERNAL_EVIDENCE"
    return {
        "mission_id": mission_id,
        "project_id": mission["project_id"],
        "status": state,
        "observable_state": observable,
        "current_step": mission["current_step"],
        "last_committed_step": mission["last_committed_step"],
        "next_step": mission["next_step"],
        "last_progress_at": mission["last_progress_at"],
        "worker_component": mission["worker_component"],
        "receipt_evidence": mission["receipt_evidence"],
        "hold_reason": mission["hold_reason"],
        "progress": mission["progress"],
        "last_event": events[-1] if events else None,
        "elapsed_since_proof_seconds": elapsed,
    }


def _parse_utc(value: str) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def _mission_watchdog_anchor(mission_id: str) -> tuple[str, int]:
    """Return last non-watchdog durable event time/seq so retries do not create fake progress."""
    with db_connection() as cx:
        row = cx.execute(
            "SELECT seq,created_at,event_hash FROM mission_events "
            "WHERE mission_id=? AND NOT (event_type='RETRY_SCHEDULED' AND summary LIKE 'Watchdog:%') "
            "ORDER BY seq DESC LIMIT 1",
            (mission_id,),
        ).fetchone()
    if not row:
        mission = mission_get(mission_id)
        return (str((mission or {}).get("last_progress_at") or ""), 0)
    return (str(row["created_at"] or ""), int(row["seq"] or 0))


def _latest_nonterminal_missions(limit: int = 8) -> list[dict]:
    with db_connection() as cx:
        rows = cx.execute(
            "SELECT mission_id FROM missions WHERE status NOT IN ('DONE','CANCELLED') "
            "ORDER BY updated_at DESC LIMIT ?",
            (max(1, min(int(limit), 32)),),
        ).fetchall()
    out = []
    for row in rows:
        item = mission_get(str(row["mission_id"]))
        if item:
            out.append(item)
    return out


def request_mission_resume(mission_id: str, source: str = "WATCHDOG") -> dict:
    mission = mission_get(mission_id)
    if not mission:
        raise ValueError("mission_not_found")
    if mission.get("status") in MISSION_TERMINAL_STATES:
        return {"result": "TERMINAL", "mission_id": mission_id}

    hold = str(mission.get("hold_reason") or "").upper()
    status = str(mission.get("status") or "").upper()
    human_gate = status in {"PLATFORM_HOLD"} or any(
        token in hold for token in ("USER_", "HUMAN_", "APPROVAL", "AUTHORIZATION", "LOGIN_REQUIRED")
    )
    if human_gate:
        return {"result": "HUMAN_GATE", "mission_id": mission_id, "hold_reason": hold[:240]}

    anchor_at, anchor_seq = _mission_watchdog_anchor(mission_id)
    next_info = mission_next_action(mission_id)
    next_action = next_info.get("next_action") or {}
    step_id = str(next_action.get("id") or mission.get("next_step") or "RESUME")[:100]
    worker = str(next_action.get("worker_class") or "UNSPECIFIED").upper()[:40]
    request_id = sha256_text(
        "mission-resume:" + mission_id + ":" + anchor_at + ":" + step_id
    )[:32]

    req = {
        "schema": "bcp.mission_resume_request/1",
        "request_id": request_id,
        "mission_id": mission_id,
        "project_id": str(mission.get("project_id") or "")[:128],
        "source": str(source or "WATCHDOG")[:40],
        "state": "QUEUED",
        "step_id": step_id,
        "worker_class": worker,
        "anchor_at": anchor_at,
        "anchor_seq": anchor_seq,
        "created_at": utc_now(),
        "zero_paid_spend_usd": 0.0,
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    old = read_json(MISSION_RESUME_REQUEST_PATH, {}) or {}
    if old.get("request_id") == request_id and old.get("state") in {"QUEUED", "ACKNOWLEDGED"}:
        return {"result": "ALREADY_QUEUED", **old}
    atomic_json(MISSION_RESUME_REQUEST_PATH, req)
    with MISSION_RESUME_REQUEST_LOG.open("a", encoding="utf-8") as h:
        h.write(canonical_json(req) + "\n")
    append_mission_event(
        mission_id,
        "RETRY_SCHEDULED",
        "watchdog:" + request_id,
        step_id=step_id,
        worker_component="BCP_WATCHDOG",
        summary="Watchdog: durable resume request queued after stalled observable progress.",
        status="RETRY_SCHEDULED",
        payload={
            "resume_request_id": request_id,
            "source": str(source or "WATCHDOG")[:40],
            "worker_class": worker,
            "anchor_at": anchor_at,
            "anchor_seq": anchor_seq,
            "next_step": step_id,
        },
    )
    mirror_telemetry_status("MISSION_RESUME_QUEUED", {
        "status": "RETRY_SCHEDULED",
        "revision": anchor_seq,
    })
    return {"result": "QUEUED", **req}


def consume_mission_resume_request() -> dict:
    """Acknowledge durable request locally. Execution is delegated to qualified workers/model broker."""
    req = read_json(MISSION_RESUME_REQUEST_PATH, {}) or {}
    if not req or req.get("state") != "QUEUED":
        return {"result": "NONE"}
    mission_id = str(req.get("mission_id") or "")
    mission = mission_get(mission_id)
    if not mission:
        req["state"] = "ORPHANED"
        req["acknowledged_at"] = utc_now()
        atomic_json(MISSION_RESUME_REQUEST_PATH, req)
        return {"result": "ORPHANED"}
    req["state"] = "ACKNOWLEDGED"
    req["acknowledged_at"] = utc_now()
    req["next_action"] = mission_next_action(mission_id).get("next_action")
    atomic_json(MISSION_RESUME_REQUEST_PATH, req)
    # Mirror to the Drive/control plane. A qualified orchestrator can consume the
    # request without the user having to copy/paste context.
    control = chatgpt_control_folder()
    if control is not None:
        root = control / "03_TELEMETRY" / "BCP"
        try:
            root.mkdir(parents=True, exist_ok=True)
            atomic_json(root / "MISSION_RESUME_REQUEST.json", req)
        except Exception:
            pass
    return {"result": "ACKNOWLEDGED", **req}


def mission_watchdog_tick() -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    state = read_json(MISSION_WATCHDOG_STATE_PATH, {}) or {}
    selected = None
    for mission in _latest_nonterminal_missions():
        anchor_at, anchor_seq = _mission_watchdog_anchor(str(mission["mission_id"]))
        anchor = _parse_utc(anchor_at)
        if anchor is None:
            continue
        stale = max(0, int((now - anchor).total_seconds()))
        if selected is None or stale > selected["stale_seconds"]:
            selected = {
                "mission": mission, "anchor_at": anchor_at,
                "anchor_seq": anchor_seq, "stale_seconds": stale,
            }
    if selected is None:
        rec = {"schema": "bcp.mission_watchdog/1", "state": "IDLE", "updated_at": utc_now()}
        atomic_json(MISSION_WATCHDOG_STATE_PATH, rec)
        return rec

    mission = selected["mission"]
    mission_id = str(mission["mission_id"])
    stale = int(selected["stale_seconds"])
    status = str(mission.get("status") or "").upper()
    hold = str(mission.get("hold_reason") or "")
    anchor_key = sha256_text(mission_id + ":" + selected["anchor_at"])[:24]
    previous_anchor = str(state.get("anchor_key") or "")
    attempts = int(state.get("attempt_count") or 0) if previous_anchor == anchor_key else 0
    last_requested = _parse_utc(state.get("last_requested_at")) if previous_anchor == anchor_key else None
    cooldown = MISSION_WATCHDOG_COOLDOWNS[min(attempts, len(MISSION_WATCHDOG_COOLDOWNS) - 1)]
    human_gate = status == "PLATFORM_HOLD" or any(
        token in hold.upper() for token in ("USER_", "HUMAN_", "APPROVAL", "AUTHORIZATION", "LOGIN_REQUIRED")
    )

    rec = {
        "schema": "bcp.mission_watchdog/1",
        "state": "HEALTHY" if stale < MISSION_STALE_SECONDS else ("HUMAN_GATE" if human_gate else "STALLED"),
        "mission_id": mission_id,
        "project_id": str(mission.get("project_id") or ""),
        "mission_status": status,
        "current_step": str(mission.get("current_step") or ""),
        "next_step": str(mission.get("next_step") or ""),
        "last_proof_at": selected["anchor_at"],
        "stale_seconds": stale,
        "anchor_key": anchor_key,
        "attempt_count": attempts,
        "last_action": "OBSERVE",
        "updated_at": utc_now(),
    }

    if stale >= MISSION_STALE_SECONDS and not human_gate and attempts < MISSION_WATCHDOG_MAX_AUTO_REQUESTS:
        allowed = last_requested is None or (now - last_requested).total_seconds() >= cooldown
        if allowed:
            result = request_mission_resume(mission_id, source="AUTO_WATCHDOG")
            if result.get("result") in {"QUEUED", "ALREADY_QUEUED"}:
                attempts += 1
                rec["state"] = "RESUME_REQUESTED"
                rec["attempt_count"] = attempts
                rec["last_requested_at"] = utc_now()
                rec["last_action"] = "QUEUE_RESUME_REQUEST"
                rec["resume_request_id"] = str(result.get("request_id") or "")
    elif attempts >= MISSION_WATCHDOG_MAX_AUTO_REQUESTS and stale >= MISSION_STALE_SECONDS:
        rec["state"] = "ESCALATED"
        rec["last_action"] = "NOTIFY_USER_NO_MORE_AUTO_RETRIES"

    atomic_json(MISSION_WATCHDOG_STATE_PATH, rec)
    return rec


def provider_call_allowed(expected_cost_usd: float, provider_state: str) -> tuple[bool, str]:
    if float(expected_cost_usd or 0.0) > 0.0:
        return False, "COST_HOLD"
    if str(provider_state or "").upper() != "ACTIVE_FREE_PROVIDER":
        return False, "FREE_MODEL_CAPACITY_HOLD"
    return True, "ALLOW"


def get_head(project_id: str):
    cx = connect_db()
    try:
        row = cx.execute("SELECT * FROM heads WHERE project_id=?", (project_id,)).fetchone()
        return dict(row) if row else None
    finally:
        cx.close()


def recent_events(project_id: str, limit: int = 10):
    limit = max(1, min(int(limit), 50))
    with db_connection() as cx:
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


def commit_event(project_id: str, event_type: str, payload: dict, idem: str, expected_revision: int | None = None):
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
            actual_revision = int(head["revision"]) if head else 0
            if expected_revision is not None and int(expected_revision) != actual_revision:
                cx.execute("ROLLBACK")
                raise ValueError(f"stale_revision:expected={int(expected_revision)}:actual={actual_revision}")
            revision = actual_revision + 1
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

    def send_file(self, status, path: Path, content_type: str):
        size = path.stat().st_size
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        with path.open("rb") as src:
            while True:
                chunk = src.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)

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
                    "identity_fingerprint": public_identity_fingerprint(self.server.bcp_token),
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

        if path == "/v1/system/nexus":
            try:
                self.send_json(200, nexus_bootstrap_delivery_status(check_remote=True))
            except Exception as e:
                self.send_json(503, {"ok": False, "error": "nexus_bootstrap_status_failed", "detail": str(e)[:500]})
            return

        if path == "/v1/edge/update":
            try:
                bundle = edge_update_bundle()
                self.send_json(200, bundle["manifest"])
            except Exception as e:
                self.send_json(404, {"ok": False, "error": "edge_update_unavailable", "detail": str(e)[:240]})
            return

        if path == "/v1/edge/update/apk":
            try:
                bundle = edge_update_bundle()
                self.send_file(200, bundle["apk_path"], "application/vnd.android.package-archive")
            except Exception as e:
                self.send_json(404, {"ok": False, "error": "edge_update_unavailable", "detail": str(e)[:240]})
            return

        if path == "/v1/orchestrator/status":
            self.send_json(200, {
                "ok": True,
                "schema": "bcp.orchestrator_status/1",
                "server_version": SERVER_VERSION,
                "operating_mode": pc_operating_mode(),
                "resources": system_resources(),
                "memory_layers": list(MEMORY_LAYERS),
                "default_paid_spend_usd": 0.0,
            })
            return

        if path == "/v1/diagnostics":
            self.send_json(
                200,
                {
                    "ok": True,
                    "version": SERVER_VERSION,
                    "server_pid": os.getpid(),
                    "server_file": str(SERVER_FILE),
                    "server_sha256": hashlib.sha256(SERVER_FILE.read_bytes()).hexdigest(),
                    "lifecycle_registration": lifecycle_registration_status(),
                    "paired": PAIR_PATH.exists(),
                    "pair": read_json(PAIR_PATH, {}),
                    "telemetry_file": str(TELEMETRY_DIR / "phone-events.jsonl"),
                    "telemetry_bridge_control_folder": str(chatgpt_control_folder() or ""),
                },
            )
            return

        parts = [unquote(x) for x in path.split("/") if x]
        if parts == ["v1", "conversations", "gaps"]:
            query = parse_qs(urlparse(self.path).query)
            try:
                threshold = int((query.get("threshold_seconds") or ["300"])[0])
                limit = int((query.get("limit") or ["20"])[0])
            except Exception:
                threshold, limit = 300, 20
            gaps = conversation_delivery_gaps(threshold, limit)
            self.send_json(200, {
                "ok": True,
                "schema": "bcp.conversation_delivery_gaps/1",
                "threshold_seconds": max(60, min(threshold, 86400)),
                "gap_count": len(gaps),
                "gaps": gaps,
                "truth_boundary": "DERIVED_FROM_BCP_RECEIPTS_NOT_CHATGPT_INTERNAL_STATE",
            })
            return
        if parts == ["v1", "conversations", "producers"]:
            query = parse_qs(urlparse(self.path).query)
            cid = str((query.get("conversation_id") or [""])[0])[:64]
            producers = conversation_producer_sync(cid)
            self.send_json(200, {
                "ok": True,
                "schema": "bcp.conversation_producer_sync/1",
                "producer_count": len(producers),
                "producers": producers,
            })
            return
        if parts == ["v1", "conversations", "sequence-gaps"]:
            query = parse_qs(urlparse(self.path).query)
            cid = str((query.get("conversation_id") or [""])[0])[:64]
            self.send_json(200, {
                "ok": True,
                "schema": "bcp.conversation_sequence_gaps/1",
                "gaps": conversation_sequence_gaps(cid, 50),
            })
            return
        if parts == ["v1", "conversations"]:
            query = parse_qs(urlparse(self.path).query)
            try:
                limit = int((query.get("limit") or ["8"])[0])
            except Exception:
                limit = 8
            self.send_json(200, {"ok": True, "conversations": conversation_list(limit)})
            return
        if len(parts) == 4 and parts[:2] == ["v1", "conversations"] and parts[3] == "producer-heartbeat":
            try:
                body = self.read_json()
                receipt = conversation_register_producer(
                    parts[2],
                    body.get("producer_session_id"),
                    body.get("announced_sequence") or 0,
                    body.get("source_kind") or "BCP_AGENT",
                    body.get("source_ref") or "",
                    body.get("sequence_floor") or 1,
                    body.get("heartbeat_at") or "",
                )
                receipt["sequence_gaps"] = conversation_sequence_gaps(parts[2], 20)
                write_conversation_receipt_ack()
                self.send_json(200, receipt)
            except Exception as e:
                self.send_json(400, {"error": "conversation_producer_heartbeat_failed", "detail": str(e)[:240]})
            return
        if len(parts) == 4 and parts[:2] == ["v1", "conversations"] and parts[3] == "latency":
            self.send_json(200, {
                "ok": True,
                "latency": conversation_latency_summary(parts[2]),
            })
            return
        if len(parts) == 4 and parts[:2] == ["v1", "conversations"] and parts[3] == "messages":
            query = parse_qs(urlparse(self.path).query)
            try:
                limit = int((query.get("limit") or ["8"])[0])
            except Exception:
                limit = 8
            self.send_json(200, {"ok": True, "conversation_id": parts[2],
                                "messages": conversation_messages(parts[2], limit)})
            return
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
            if parts[3] == "context":
                query = parse_qs(urlparse(self.path).query)
                task = str((query.get("task") or [""])[0])[:1000]
                known_hash = str((query.get("known_hash") or [""])[0])[:128]
                try:
                    budget = int((query.get("byte_budget") or ["24000"])[0])
                except Exception:
                    budget = 24000
                pack = build_context_pack(project, task=task, byte_budget=budget)
                current_hash = str(pack.get("revision_vector", {}).get("context_hash", ""))
                if known_hash and hmac.compare_digest(known_hash, current_hash):
                    self.send_json(200, {
                        "schema": "bcp.context_pack_result/1",
                        "status": "UNCHANGED",
                        "project_id": project,
                        "context_hash": current_hash,
                        "head": pack.get("head"),
                    })
                else:
                    pack["status"] = "FULL_REFRESH"
                    self.send_json(200, pack)
                return
            if parts[3] == "jobs":
                self.send_json(200, {"project_id": project, "jobs": jobs_snapshot(project)})
                return
        if len(parts) == 4 and parts[:2] == ["v1", "missions"]:
            mission_id = parts[2]
            try:
                if parts[3] == "status":
                    mission = mission_get(mission_id)
                    if not mission:
                        self.send_json(404, {"error": "mission_not_found"})
                    else:
                        self.send_json(200, {"ok": True, "mission": mission})
                    return
                if parts[3] == "tail":
                    self.send_json(200, {"ok": True, "mission_id": mission_id, "events": mission_tail(mission_id)})
                    return
                if parts[3] == "where":
                    self.send_json(200, {"ok": True, **mission_where(mission_id)})
                    return
                if parts[3] == "next":
                    self.send_json(200, {"ok": True, **mission_next_action(mission_id)})
                    return
            except ValueError as e:
                self.send_json(404, {"error": str(e)})
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
                expected_identity = public_identity_fingerprint(self.server.bcp_token)
                supplied_identity = str(body.get("identity_fingerprint", ""))[:80]
                if supplied_identity != expected_identity:
                    self.send_json(409, {
                        "error": "pc_identity_confirmation_mismatch",
                        "pc_name": os.environ.get("COMPUTERNAME", "BCP-PC"),
                        "identity_fingerprint": expected_identity,
                    })
                    return
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
                        "identity_fingerprint": expected_identity,
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

        if path == "/v1/system/nexus/apply":
            try:
                self.send_json(200, apply_nexus_bootstrap_delivery(auto_launch=True))
            except Exception as e:
                self.send_json(500, {"ok": False, "error": "nexus_bootstrap_apply_failed", "detail": str(e)[:500]})
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
        if len(parts) == 4 and parts[:2] == ["v1", "conversations"] and parts[3] == "messages":
            try:
                body = self.read_json()
                idem = self.headers.get("Idempotency-Key") or body.get("message_key")
                receipt = conversation_append_message(
                    parts[2],
                    alias=body.get("alias") or parts[2],
                    source_kind=body.get("source_kind") or "BCP_AGENT",
                    source_ref=body.get("source_ref") or "",
                    message_key=str(idem or ""),
                    role=body.get("role"),
                    text=body.get("text"),
                    delivery_state=body.get("delivery_state") or "MIRRORED_BCP",
                    evidence_class=body.get("evidence_class") or "EXTERNAL_RECEIPT",
                    generated_at=body.get("generated_at") or "",
                    linked_mission_id=body.get("linked_mission_id") or "",
                    producer_sequence=body.get("producer_sequence") or 0,
                    producer_session_id=body.get("producer_session_id") or "",
                )
                conversation_touch_producer_receipt(
                    parts[2], body.get("producer_session_id") or "",
                    int(body.get("producer_sequence") or 0),
                    body.get("source_kind") or "BCP_AGENT",
                    body.get("source_ref") or "",
                )
                receipt["sequence_gaps"] = conversation_sequence_gaps(parts[2], 20)
                write_conversation_receipt_ack()
                self.send_json(200, receipt)
            except Exception as e:
                self.send_json(400, {"error": "conversation_message_failed", "detail": str(e)[:240]})
            return
        if len(parts) == 4 and parts[:2] == ["v1", "conversations"] and parts[3] == "seen":
            try:
                body = self.read_json()
                self.send_json(200, conversation_mark_seen(parts[2], int(body.get("sequence") or 0)))
            except Exception as e:
                self.send_json(400, {"error": "conversation_seen_failed", "detail": str(e)[:240]})
            return
        if parts == ["v1", "missions"]:
            try:
                body = self.read_json()
                idem = self.headers.get("Idempotency-Key") or body.get("idempotency_key")
                receipt = accept_mission(
                    body.get("project_id"),
                    body.get("request_text"),
                    str(idem or ""),
                    spec_revision=body.get("spec_revision", ""),
                    context_revision=body.get("context_revision", ""),
                    execution_profile=body.get("execution_profile", "NORMAL"),
                    allowed_capabilities=body.get("allowed_capabilities", []),
                    provider_policy=body.get("provider_policy", {}),
                    approval_gates=body.get("approval_gates", []),
                )
                self.send_json(200, receipt)
            except Exception as e:
                self.send_json(400, {"error": "mission_accept_failed", "detail": str(e)[:500]})
            return

        if len(parts) == 4 and parts[:2] == ["v1", "missions"]:
            mission_id = parts[2]
            try:
                body = self.read_json()
                idem = self.headers.get("Idempotency-Key") or body.get("idempotency_key")
                if parts[3] == "plan":
                    self.send_json(200, set_mission_plan(mission_id, body.get("steps"), str(idem or "")))
                    return
                if parts[3] == "events":
                    self.send_json(200, append_mission_event(
                        mission_id,
                        body.get("event_type"),
                        str(idem or ""),
                        step_id=body.get("step_id", ""),
                        worker_component=body.get("worker_component", ""),
                        summary=body.get("summary", ""),
                        evidence_ref=body.get("evidence_ref", ""),
                        status=body.get("status", ""),
                        failure_hold_reason=body.get("failure_hold_reason", ""),
                        payload=body.get("payload", {}),
                    ))
                    return
            except ValueError as e:
                detail = str(e)
                code = 404 if detail == "mission_not_found" else 400
                self.send_json(code, {"error": detail})
                return
            except Exception as e:
                self.send_json(400, {"error": "mission_update_failed", "detail": str(e)[:500]})
                return

        if len(parts) == 4 and parts[:2] == ["v1", "projects"] and parts[3] == "memory":
            try:
                body = self.read_json()
                receipt = memory_put(
                    parts[2], body.get("layer"), body.get("key"),
                    body.get("value"), body.get("source", "B-EDGE"),
                    evidence_class=body.get("evidence_class", "UNCLASSIFIED"),
                    source_id=body.get("source_id", ""),
                    pinned=bool(body.get("pinned", False)),
                    expires_at=body.get("expires_at"),
                    supersedes_key=body.get("supersedes_key", ""),
                )
                self.send_json(200, {"ok": True, **receipt})
            except Exception as e:
                self.send_json(400, {"error": "memory_write_failed", "detail": str(e)[:500]})
            return

        if len(parts) == 4 and parts[:2] == ["v1", "projects"] and parts[3] == "jobs":
            try:
                body = self.read_json()
                idem = self.headers.get("Idempotency-Key") or body.get("idempotency_key")
                receipt = enqueue_job(
                    parts[2], body.get("kind", "generic"), body.get("payload", {}),
                    str(idem or ""), bool(body.get("requires_pc", True)),
                    priority=body.get("priority", 50),
                    resource_class=body.get("resource_class", ""),
                    action_id=body.get("action_id", ""),
                    expected_revision=body.get("expected_revision"),
                    input_hash=body.get("input_hash", ""),
                    coordinator_epoch=body.get("coordinator_epoch", 0),
                    evidence_contract=body.get("evidence_contract", ""),
                    dependencies=body.get("dependency_job_ids", []),
                )
                self.send_json(200, receipt)
            except ValueError as e:
                detail = str(e)
                if detail.startswith("stale_job_revision:"):
                    self.send_json(409, {"error": "stale_job_revision", "detail": detail, "project_id": parts[2], "head": get_head(parts[2])})
                else:
                    self.send_json(400, {"error": "job_queue_failed", "detail": detail[:500]})
            except Exception as e:
                self.send_json(400, {"error": "job_queue_failed", "detail": str(e)[:500]})
            return

        if len(parts) == 4 and parts[:2] == ["v1", "projects"] and parts[3] == "events":
            try:
                body = self.read_json()
                payload = body.get("payload", {})
                if not isinstance(payload, dict):
                    raise ValueError("payload_must_be_object")
                idem = self.headers.get("Idempotency-Key") or body.get("idempotency_key")
                if not idem:
                    raise ValueError("Idempotency-Key required")
                expected_raw = self.headers.get("X-BCP-Expected-Revision")
                if expected_raw in (None, ""):
                    expected_raw = body.get("expected_revision")
                expected_revision = None if expected_raw in (None, "") else int(expected_raw)
                receipt = commit_event(
                    parts[2],
                    str(body.get("type", "checkpoint")),
                    payload,
                    str(idem),
                    expected_revision=expected_revision,
                )
                receipt["revision_precondition"] = expected_revision
                self.send_json(200, receipt)
            except ValueError as e:
                detail = str(e)
                if detail.startswith("stale_revision:"):
                    self.send_json(409, {
                        "error": "stale_revision",
                        "detail": detail,
                        "project_id": parts[2],
                        "head": get_head(parts[2]),
                    })
                else:
                    self.send_json(400, {"error": "bad_request", "detail": detail})
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

    global APP_ROOT, STATE_DIR, TELEMETRY_DIR, DB_PATH, TOKEN_PATH, PAIR_PATH, MISSION_WATCHDOG_STATE_PATH, MISSION_RESUME_REQUEST_PATH, MISSION_RESUME_REQUEST_LOG, CONVERSATION_RECEIPT_INBOX, CONVERSATION_RECEIPT_CURSOR, CONVERSATION_RECEIPT_ACK, CHATGPT_PC_FLOW_BRIDGE_CURSOR, CHATGPT_PC_FLOW_BRIDGE_STATUS
    with tempfile.TemporaryDirectory() as td:
        APP_ROOT = Path(td)
        STATE_DIR = APP_ROOT / "state"
        TELEMETRY_DIR = APP_ROOT / "telemetry"
        DB_PATH = STATE_DIR / "bcp.sqlite3"
        TOKEN_PATH = STATE_DIR / "bcp_token.txt"
        PAIR_PATH = STATE_DIR / "paired_edge.json"
        MISSION_WATCHDOG_STATE_PATH = STATE_DIR / "mission_watchdog.json"
        MISSION_RESUME_REQUEST_PATH = STATE_DIR / "mission_resume_request.json"
        MISSION_RESUME_REQUEST_LOG = STATE_DIR / "MISSION_RESUME_REQUESTS.jsonl"
        CONVERSATION_RECEIPT_INBOX = STATE_DIR / "CONVERSATION_RECEIPTS.jsonl"
        CONVERSATION_RECEIPT_CURSOR = STATE_DIR / "conversation_receipt_cursor.json"
        CONVERSATION_RECEIPT_ACK = STATE_DIR / "conversation_receipt_ack.json"
        CHATGPT_PC_FLOW_BRIDGE_CURSOR = STATE_DIR / "chatgpt_pc_flow_bridge_cursor.json"
        CHATGPT_PC_FLOW_BRIDGE_STATUS = STATE_DIR / "chatgpt_pc_flow_bridge_status.json"
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
            expected_revision=0,
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
            expected_revision=0,
        )
        assert r1["result"] == "COMMITTED"
        assert r2["result"] == "ALREADY_COMMITTED"
        assert get_head("buildhub")["revision"] == 1
        stale_rejected = False
        try:
            commit_event(
                "buildhub",
                "checkpoint",
                {
                    "status": "ACTIVE",
                    "last_completed_action": "STALE",
                    "next_action": "MUST_REJECT",
                },
                "stale-key",
                expected_revision=0,
            )
        except ValueError as e:
            stale_rejected = str(e).startswith("stale_revision:")
        assert stale_rejected
        assert get_head("buildhub")["revision"] == 1
        assert _version_tuple("0.4.8") > _version_tuple("0.4.7")
        assert _version_tuple("0.4.8") == (0, 4, 8)
        source = SERVER_FILE.read_text(encoding="utf-8")
        assert '"server_pid": os.getpid()' in source
        assert '"server_sha256": hashlib.sha256' in source
        assert "/v1/edge/update" in source
        assert "BCP_EDGE_CURRENT.apk" in source
        assert "edge_apk_sha256_mismatch" in source
        assert "identity_fingerprint" in source
        assert "pc_identity_confirmation_mismatch" in source
        assert "API_BCP" in source and "02_TELEMETRY" in source
        assert "/v1/system/chatgpt-pc/recover" in source
        assert "recovery_package_sha256_mismatch" in source
        assert "RECOVERY_LAUNCHER_REPAIRED_AND_STARTED" in source
        assert "LOCAL_TARGET_NOT_ACTIVE_BRIDGE_STARTED" in source
        sample_vbs = _chatgpt_pc_recovery_launcher_content(
            Path(r"C:\\Users\\Lenovo\\AppData\\Local\\Tunnel_PC_G4\\runtime\\pythonw.exe"),
            Path(r"C:\\Users\\Lenovo\\AppData\\Local\\Tunnel_PC_G4\\recovery_plane_runner.py"),
        )
        assert sample_vbs.startswith("Option Explicit\r\n")
        assert 'CreateObject("WScript.Shell")' in sample_vbs
        assert "recovery_plane_runner.py" in sample_vbs
        probe_vbs = APP_ROOT / "ChatGPTPC_RecoveryPlane.vbs"
        probe = _write_utf16_recovery_vbs(probe_vbs, sample_vbs)
        assert probe_vbs.read_bytes().startswith((b"\xff\xfe", b"\xfe\xff"))
        assert probe["bytes"] > 16 and len(probe["sha256"]) == 64
        assert "shell=False" in source
        assert "/v1/orchestrator/status" in source
        assert 'parts[3] == "context"' in source
        assert 'parts[3] == "memory"' in source
        assert 'parts[3] == "jobs"' in source
        with db_connection() as cx:
            mem_cols = {r[1] for r in cx.execute("PRAGMA table_info(memory_records)").fetchall()}
            job_cols = {r[1] for r in cx.execute("PRAGMA table_info(jobs)").fetchall()}
            assert {"evidence_class","source_id","pinned","expires_at","supersedes_key"} <= mem_cols
            assert {"action_id","priority","resource_class","expected_revision","input_hash","coordinator_epoch","evidence_contract"} <= job_cols

        memory_put(
            "buildhub", "PROJECT_MEMORY", "goal", {"value": "final product"}, "selftest",
            evidence_class="VALIDATED", source_id="selftest:goal", pinned=True
        )
        protected_rejected = False
        try:
            memory_put("__global__", "POLICY", "unsafe", {"x": 1}, "web",
                       evidence_class="UNTRUSTED_EXTERNAL")
        except ValueError as e:
            protected_rejected = "memory_admission_rejected" in str(e)
        assert protected_rejected

        pack = build_context_pack("buildhub", task="final product orchestration", byte_budget=12000)
        assert pack["schema"] == "bcp.context_pack/2"
        assert pack["memory"]["PROJECT_MEMORY"][0]["key"] == "goal"
        assert pack["budget"]["used_bytes"] <= pack["budget"]["bytes"]
        assert len(pack["revision_vector"]["context_hash"]) == 64

        q1 = enqueue_job(
            "buildhub", "test", {"x": 1}, "job-idem", requires_pc=False,
            priority=80, resource_class="EDGE_R1", action_id="selftest-action",
            expected_revision=1, coordinator_epoch=1, evidence_contract="SELFTEST_RECEIPT"
        )
        q2 = enqueue_job("buildhub", "test", {"x": 1}, "job-idem", requires_pc=False)
        assert q1["result"] == "QUEUED"
        assert q1["priority"] == 80 and q1["resource_class"] == "EDGE_R1"
        assert q2["result"] == "ALREADY_QUEUED"
        blocked = enqueue_job(
            "buildhub", "dependent", {"x": 2}, "job-dep", requires_pc=False,
            dependencies=[q1["job_id"]]
        )
        assert blocked["state"] == "BLOCKED"
        stale_job_rejected = False
        try:
            enqueue_job("buildhub", "stale", {}, "job-stale", expected_revision=0)
        except ValueError as e:
            stale_job_rejected = str(e).startswith("stale_job_revision:")
        assert stale_job_rejected
        assert pc_operating_mode() in ("PC_AVAILABLE", "PC_MEMORY_PRESSURE")
        assert "_bcp._tcp.local" in source
        assert "start_mdns_advertiser" in source

        m1 = accept_mission(
            "api-bcp",
            "Qualify durable mission recovery",
            "mission-selftest-accept",
            spec_revision="SELFTEST-R1",
            context_revision="CTX-1",
            execution_profile="DEEP",
            allowed_capabilities=["LOCAL", "PC", "REMOTE_AI"],
            provider_policy={"default_paid_spend_usd": 0.0},
        )
        m2 = accept_mission(
            "api-bcp",
            "Qualify durable mission recovery",
            "mission-selftest-accept",
            spec_revision="SELFTEST-R1",
        )
        assert m1["result"] == "MISSION_ACCEPTED"
        assert m2["result"] == "ALREADY_ACCEPTED"
        mission_id = m1["mission"]["mission_id"]
        assert m2["mission"]["mission_id"] == mission_id
        planned = set_mission_plan(
            mission_id,
            [
                {"id": "context", "label": "Resolve canonical context", "worker_class": "LOCAL"},
                {"id": "validate", "label": "Deterministic validation", "dependencies": ["context"], "worker_class": "LOCAL"},
                {"id": "semantic", "label": "Semantic worker only if needed", "dependencies": ["validate"], "worker_class": "REMOTE_AI"},
            ],
            "mission-selftest-plan",
        )
        assert planned["result"] == "RECORDED"
        assert mission_next_action(mission_id)["next_action"]["id"] == "context"
        c1 = append_mission_event(
            mission_id,
            "COMMITTED",
            "mission-selftest-context-commit",
            step_id="context",
            worker_component="LOCAL",
            summary="Context resolved deterministically.",
            evidence_ref="selftest:context",
            payload={"step_state": "COMMITTED", "verified": True, "next_step": "validate"},
        )
        c2 = append_mission_event(
            mission_id,
            "COMMITTED",
            "mission-selftest-context-commit",
            step_id="context",
            worker_component="LOCAL",
            summary="Duplicate must deduplicate.",
            evidence_ref="selftest:context",
            payload={"step_state": "COMMITTED", "verified": True, "next_step": "validate"},
        )
        assert c1["result"] == "RECORDED"
        assert c2["result"] == "ALREADY_RECORDED"
        assert mission_next_action(mission_id)["next_action"]["id"] == "validate"
        where = mission_where(mission_id)
        assert where["progress"]["verified_steps"] == 1
        assert where["progress"]["total_steps"] == 3
        hold = append_mission_event(
            mission_id,
            "PLATFORM_HOLD",
            "mission-selftest-platform-hold",
            step_id="validate",
            worker_component="CHATGPT",
            summary="External platform interruption; checkpoint remains resumable.",
            status="PLATFORM_HOLD",
            failure_hold_reason="PLATFORM_VERIFICATION_HOLD",
            payload={"next_step": "validate"},
        )
        assert hold["mission"]["next_step"] == "validate"
        assert mission_next_action(mission_id)["next_action"]["id"] == "validate"
        assert request_mission_resume(mission_id, "SELFTEST").get("result") == "HUMAN_GATE"
        resumed = append_mission_event(
            mission_id,
            "STARTED",
            "mission-selftest-resume-started",
            step_id="validate",
            worker_component="LOCAL",
            summary="Resume path is again machine-runnable.",
            status="STARTED",
            failure_hold_reason="",
            payload={"next_step": "validate"},
        )
        assert resumed["result"] == "RECORDED"
        # Force only the non-watchdog evidence anchor stale. The watchdog retry
        # event itself must never be allowed to masquerade as real task progress.
        old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=20)).replace(microsecond=0).isoformat()
        with db_connection() as cx:
            cx.execute(
                "UPDATE mission_events SET created_at=? WHERE mission_id=? AND idempotency_key=?",
                (old, mission_id, "mission-selftest-resume-started"),
            )
            cx.execute(
                "UPDATE missions SET last_progress_at=?,updated_at=? WHERE mission_id=?",
                (old, old, mission_id),
            )
        wd1 = mission_watchdog_tick()
        assert wd1["state"] == "RESUME_REQUESTED"
        assert wd1["attempt_count"] == 1
        req1 = read_json(MISSION_RESUME_REQUEST_PATH, {}) or {}
        assert req1.get("state") == "QUEUED"
        assert req1.get("mission_id") == mission_id
        ack = consume_mission_resume_request()
        assert ack["result"] == "ACKNOWLEDGED"
        # Same anchor + cooldown => no duplicate automatic retry.
        wd2 = mission_watchdog_tick()
        assert wd2["attempt_count"] == 1
        assert len(mission_tail(mission_id, 50)) >= 5
        assert provider_call_allowed(0.0, "ACTIVE_FREE_PROVIDER") == (True, "ALLOW")
        assert provider_call_allowed(0.01, "ACTIVE_FREE_PROVIDER") == (False, "COST_HOLD")
        assert provider_call_allowed(0.0, "FIELD_UNVERIFIED") == (False, "FREE_MODEL_CAPACITY_HOLD")
        source = SERVER_FILE.read_text(encoding="utf-8")
        assert "/v1/missions" in source
        assert 'parts[3] == "where"' in source
        assert 'parts[3] == "tail"' in source
        assert "NO_NEW_EXTERNAL_EVIDENCE" in source
        assert "conversation_threads" in source
        assert "conversation_messages" in source
        assert "/v1/conversations" in source
        assert "conversation_delivery_gaps" in source
        assert "sync_chatgpt_pc_flow_ledger" in source
        assert "conversation_latency_summary" in source
        assert "MEASURED_FROM_DURABLE_RECEIPT_TIMESTAMPS_ONLY" in source
        assert "mode=ro" in source
        assert "CHATGPT_PC_FLOW_LEDGER" in source
        assert "DERIVED_FROM_BCP_RECEIPTS_NOT_CHATGPT_INTERNAL_STATE" in source
        mirrored = conversation_append_message(
            "chat-main", alias="Conversation principale", source_kind="CHATGPT_UI",
            source_ref="local-test", message_key="turn-1", role="ASSISTANT",
            text="Réponse produite et miroir durable.", delivery_state="CHATGPT_UI_DELIVERY_UNKNOWN",
        )
        assert mirrored["result"] == "RECORDED"
        assert conversation_list(3)[0]["conversation_id"] == "chat-main"
        assert conversation_messages("chat-main", 3)[0]["delivery_state"] == "CHATGPT_UI_DELIVERY_UNKNOWN"
        # Fresh message must not be called a gap; aging it beyond the threshold must.
        assert conversation_delivery_gaps(300, 10) == []

        # R25 local producer bridge: accept out-of-order receipts, expose a gap,
        # then resolve it when the missing sequence arrives later.
        receipts = [
            {"schema":"bcp.conversation_receipt/2","conversation_id":"bridge-x","alias":"Bridge X",
             "source_kind":"CHATGPT_PC","source_ref":"selftest","message_key":"p1","role":"USER",
             "text":"Question","producer_session_id":"session-a","producer_sequence":1},
            {"schema":"bcp.conversation_receipt/2","conversation_id":"bridge-x","alias":"Bridge X",
             "source_kind":"CHATGPT_PC","source_ref":"selftest","message_key":"p3","role":"ASSISTANT",
             "text":"Réponse après trou","delivery_state":"CHATGPT_UI_DELIVERY_UNKNOWN",
             "producer_session_id":"session-a","producer_sequence":3},
        ]
        CONVERSATION_RECEIPT_INBOX.write_text(
            "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in receipts), encoding="utf-8"
        )
        receipt_pass = process_conversation_receipt_inbox()
        assert receipt_pass["accepted"] == 2 and receipt_pass["rejected"] == 0
        seq_gaps = conversation_sequence_gaps("bridge-x", 10)
        assert len(seq_gaps) == 1 and seq_gaps[0]["missing_from"] == 2 and seq_gaps[0]["missing_to"] == 2
        with CONVERSATION_RECEIPT_INBOX.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(
                {"schema":"bcp.conversation_receipt/2","conversation_id":"bridge-x","alias":"Bridge X",
                 "source_kind":"CHATGPT_PC","source_ref":"selftest","message_key":"p2","role":"ASSISTANT",
                 "text":"Réponse arrivée en retard","delivery_state":"MIRRORED_BCP",
                 "producer_session_id":"session-a","producer_sequence":2},
                ensure_ascii=False
            ) + "\n")
        receipt_late = process_conversation_receipt_inbox()
        assert receipt_late["accepted"] == 1
        assert conversation_sequence_gaps("bridge-x", 10) == []
        hb = conversation_register_producer("bridge-x", "session-a", 4, "CHATGPT_PC", "selftest", 1)
        assert hb["announced_sequence"] == 4
        tail_gap = conversation_sequence_gaps("bridge-x", 10)
        assert len(tail_gap) == 1 and tail_gap[0]["missing_from"] == 4 and tail_gap[0]["missing_to"] == 4
        conversation_ingest_receipt({
            "schema":"bcp.conversation_receipt/2","conversation_id":"bridge-x","alias":"Bridge X",
            "source_kind":"CHATGPT_PC","source_ref":"selftest","message_key":"p4","role":"ASSISTANT",
            "text":"Dernier reçu","delivery_state":"MIRRORED_BCP",
            "producer_session_id":"session-a","producer_sequence":4
        })
        assert conversation_sequence_gaps("bridge-x", 10) == []
        ack = write_conversation_receipt_ack()
        assert ack["producer_count"] >= 1
        assert any(x["sync_state"] == "COMPLETE" for x in ack["producers"])

        # R27: import exact ChatGPT-PC visible turns from a read-only source ledger.
        source_root = Path(td) / "chatgpt-pc-source"
        source_root.mkdir(parents=True, exist_ok=True)
        source_db = source_root / "flow_ledger.sqlite3"
        scx = sqlite3.connect(source_db)
        scx.executescript("""
        CREATE TABLE flow_events(
            seq INTEGER PRIMARY KEY,event_id TEXT,at TEXT,session_id TEXT,mission_id TEXT,
            kind TEXT,role TEXT,exact_utf8 BLOB,source TEXT,evidence_ref TEXT,
            text_sha256 TEXT,chain_sha256 TEXT
        );
        CREATE INDEX idx_flow_kind_seq ON flow_events(kind,seq DESC);
        """)
        u = "Question exacte depuis ChatGPT-PC."
        atext = "Réponse exacte produite; affichage mobile non confirmé."
        scx.execute("INSERT INTO flow_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
            101,"evt-u",utc_now(),"chat-session-1","M-R27","conversation_message_exact","user",
            sqlite3.Binary(u.encode("utf-8")),"runtime","selftest",hashlib.sha256(u.encode()).hexdigest(),"chain-u"
        ))
        scx.execute("INSERT INTO flow_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
            102,"evt-a",utc_now(),"chat-session-1","M-R27","assistant_visible_message_exact","assistant",
            sqlite3.Binary(atext.encode("utf-8")),"runtime","selftest",hashlib.sha256(atext.encode()).hexdigest(),"chain-a"
        ))
        scx.commit(); scx.close()
        old_flow_override = os.environ.get("BCP_CHATGPT_PC_FLOW_DB")
        os.environ["BCP_CHATGPT_PC_FLOW_DB"] = str(source_db)
        try:
            bridge = sync_chatgpt_pc_flow_ledger(24)
            assert bridge["status"] == "CAUGHT_UP"
            assert bridge["imported"] == 2 and bridge["read_only"] is True
            expected_cid = _chatgpt_pc_conversation_id("chat-session-1", "M-R27")
            threads = {x["conversation_id"]: x for x in conversation_list(20)}
            assert expected_cid in threads and threads[expected_cid]["source_kind"] == "CHATGPT_PC"
            bridged = conversation_messages(expected_cid, 8)
            assert [x["role"] for x in bridged][-2:] == ["USER","ASSISTANT"]
            assert bridged[-1]["delivery_state"] == "CHATGPT_UI_DELIVERY_UNKNOWN"
            again = sync_chatgpt_pc_flow_ledger(24)
            assert again["imported"] == 0
        finally:
            if old_flow_override is None:
                os.environ.pop("BCP_CHATGPT_PC_FLOW_DB", None)
            else:
                os.environ["BCP_CHATGPT_PC_FLOW_DB"] = old_flow_override
        with db_connection() as cx:
            old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=8)).replace(microsecond=0).isoformat()
            cx.execute("UPDATE conversation_messages SET mirrored_at=?,generated_at=? WHERE conversation_id='chat-main'", (old, old))
        gaps = conversation_delivery_gaps(300, 10)
        assert len(gaps) == 1 and gaps[0]["derived_state"] == "DELIVERY_GAP_DETECTED"
        seen = conversation_mark_seen("chat-main")
        assert seen["updated"] == 1
        assert conversation_delivery_gaps(300, 10) == []
        assert "TELEGRAM_COMPANION_MANIFEST_URL" in source
        assert "telegram_companion_update_status" in source
        assert "apply_telegram_companion_update" in source
        assert "telegram_companion_sha256_mismatch" in source
        assert "telegram_companion_selftest_failed" in source
        assert "BlessingControlPlaneTelegram" in source
        assert "telegram_companion_runtime_status" in source
        assert "TELEGRAM_COMPANION_HEALTH_PATH" in source
        assert "_telegram_companion_watchdog" in source
        assert "windows_resource_status" in source
        assert "pc_battery_critical" in source
        assert "pc_memory_load_percent" in source
        assert "mission_watchdog_tick" in source
        assert "request_mission_resume" in source
        assert "MISSION_RESUME_REQUESTS.jsonl" in source
        assert "NEXUS_HUMAN_GATE_MANIFEST_WATCH_SECONDS = 2 * 60" in source
        assert "NEXUS_HUMAN_GATE_MANIFEST_WATCH_MAX_BACKOFF_SECONDS = 15 * 60" in source
        assert "start_nexus_human_gate_manifest_watcher" in source
        assert "HUMAN_GATE_FAST_PATH" in source
        assert "target_version != current_version" in source
        assert "NEXUS_BOOTSTRAP_MAX_AUTO_ATTEMPTS" in source
        assert "NEXUS_BOOTSTRAP_RETRY_BASE_SECONDS" in source
        assert "NEXUS_BOOTSTRAP_RETRY_MAX_SECONDS" in source
        assert "NEXUS_BOOTSTRAP_PROCESS_TIMEOUT_SECONDS" in source
        assert "NEXUS_BOOTSTRAP_LOCK" in source
        assert "_terminate_nexus_process_tree" in source
        assert "proc.wait(timeout=NEXUS_BOOTSTRAP_PROCESS_TIMEOUT_SECONDS)" in source
        fixed_now = dt.datetime(2026, 9, 20, 0, 0, tzinfo=dt.timezone.utc)
        fresh_retry = _nexus_retry_policy("0.1.5", {}, now=fixed_now)
        assert fresh_retry["action"] == "LAUNCH" and fresh_retry["next_attempt_count"] == 1
        human_retry = _nexus_retry_policy(
            "0.1.5",
            {"bundle_version": "0.1.5", "state": "HUMAN_AUTH_REQUIRED", "attempt_count": 1},
            now=fixed_now,
        )
        assert human_retry["action"] == "HUMAN_GATE"
        cooldown_retry = _nexus_retry_policy(
            "0.1.5",
            {
                "bundle_version": "0.1.5",
                "state": "WRANGLER_RUNTIME_REQUIRED",
                "attempt_count": 1,
                "next_retry_at": (fixed_now + dt.timedelta(seconds=120)).isoformat(),
            },
            now=fixed_now,
        )
        assert cooldown_retry["action"] == "COOLDOWN"
        due_retry = _nexus_retry_policy(
            "0.1.5",
            {
                "bundle_version": "0.1.5",
                "state": "EXITED_NO_RECEIPT",
                "attempt_count": 1,
                "next_retry_at": (fixed_now - dt.timedelta(seconds=1)).isoformat(),
            },
            now=fixed_now,
        )
        assert due_retry["action"] == "LAUNCH" and due_retry["next_attempt_count"] == 2
        exhausted_retry = _nexus_retry_policy(
            "0.1.5",
            {
                "bundle_version": "0.1.5",
                "state": "EXITED_NO_RECEIPT",
                "attempt_count": NEXUS_BOOTSTRAP_MAX_AUTO_ATTEMPTS,
            },
            now=fixed_now,
        )
        assert exhausted_retry["action"] == "EXHAUSTED"

        edge_dist = Path(td) / "edge-dist"
        edge_dist.mkdir(parents=True, exist_ok=True)
        edge_apk = edge_dist / "BCP_EDGE_CURRENT.apk"
        edge_apk.write_bytes(b"selftest-edge-apk-payload")
        edge_sha = hashlib.sha256(edge_apk.read_bytes()).hexdigest()
        atomic_json(edge_dist / "BCP_EDGE_CURRENT.json", {
            "channel": "stable",
            "package_id": "com.blessing.bcpedge.evergreen",
            "version_code": 100,
            "version_name": "1.0.0-evergreen",
            "apk_sha256": edge_sha,
            "signing_cert_sha256": "0baad4749918f1b2430bbbf3f5ddbdb1de4908b017910d67aef2cb987ddeb617",
            "published_at": utc_now(),
        })
        old_edge_dist = os.environ.get("BCP_EDGE_DISTRIBUTION_DIR")
        os.environ["BCP_EDGE_DISTRIBUTION_DIR"] = str(edge_dist)
        try:
            assert edge_distribution_roots() == [edge_dist]
            bundle = edge_update_bundle()
            assert bundle["manifest"]["version_code"] == 100
            assert bundle["manifest"]["apk_sha256"] == edge_sha
            assert bundle["apk_path"] == edge_apk
            edge_apk.write_bytes(b"tampered")
            tamper_rejected = False
            try:
                edge_update_bundle()
            except FileNotFoundError as e:
                tamper_rejected = "edge_apk_sha256_mismatch" in str(e)
            assert tamper_rejected
        finally:
            if old_edge_dist is None:
                os.environ.pop("BCP_EDGE_DISTRIBUTION_DIR", None)
            else:
                os.environ["BCP_EDGE_DISTRIBUTION_DIR"] = old_edge_dist

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
    start_conversation_receipt_worker()
    start_mdns_advertiser(args.port)
    start_nexus_human_gate_manifest_watcher()
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
