from __future__ import annotations

"""BCP Execution Fabric resource admission for constrained PCs.

Adapted from ChatGPT-PC G6 resource_governor.py source commit
6bf6e32b36008957dda014542742657af6b9e017.

The policy is calibrated for the user's real ~4 GiB Windows operating envelope.
On this machine, 80-95% physical-RAM load is a normal operating band, not by itself
a failure signal. Admission is headroom-first: available memory, pagefile pressure,
disk reserve, task class and foreground/background priority dominate raw load percent.
It decides whether a typed work unit may start; it never launches arbitrary commands.
Local AI remains disabled in the Phase 2 baseline and is handled as a later cold-burst capability.
"""

from dataclasses import dataclass
import ctypes
import os
from pathlib import Path
import shutil
from typing import Any

from .worker_supervisor import WorkerPolicy

MB = 1024 * 1024
RESOURCE_ORDER = {
    "R0_TINY": 0,
    "R1_LIGHT": 1,
    "R2_MEDIUM": 2,
    "R3_HEAVY": 3,
    "R4_LOCAL_AI": 4,
}

MODE_CAP_MB = {
    "GREEN": (192, 224),
    "AMBER": (96, 112),
    "RED": (64, 72),
    "CRITICAL": (48, 56),
}

CLASS_CAP_MB = {
    "R0_TINY": 48,
    "R1_LIGHT": 96,
    "R2_MEDIUM": 160,
    "R3_HEAVY": 192,
    "R4_LOCAL_AI": 0,
}

# MBMPC calibration: raw Windows memory load is normally high.
NORMAL_RAM_LOAD_MIN = 80
NORMAL_RAM_LOAD_MAX = 95

# Free-memory reserve left outside the bounded worker itself.
HEADROOM_RESERVE_MB = {
    "R0_TINY": 32,
    "R1_LIGHT": 64,
    "R2_MEDIUM": 128,
    "R3_HEAVY": 256,
    "R4_LOCAL_AI": 0,
}


@dataclass(frozen=True)
class AdmissionDecision:
    allowed: bool
    mode: str
    resource_class: str
    reason: str
    process_memory_mib: int
    job_memory_mib: int
    background_allowed: bool
    local_ai_enabled: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "bcp.resource_admission/1",
            "allowed": self.allowed,
            "mode": self.mode,
            "resource_class": self.resource_class,
            "reason": self.reason,
            "process_memory_mib": self.process_memory_mib,
            "job_memory_mib": self.job_memory_mib,
            "background_allowed": self.background_allowed,
            "local_ai_enabled": self.local_ai_enabled,
            "field_certified": False,
        }


def _memory() -> tuple[int, int, int, int, int]:
    """Return physical total/available/load plus pagefile total/available bytes."""
    if os.name == "nt":
        class M(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        m = M()
        m.dwLength = ctypes.sizeof(M)
        ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        if ok:
            return (
                int(m.ullTotalPhys),
                int(m.ullAvailPhys),
                int(m.dwMemoryLoad),
                int(m.ullTotalPageFile),
                int(m.ullAvailPageFile),
            )
        return 0, 0, 0, 0, 0

    try:
        d: dict[str, int] = {}
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                key, value = line.split(":", 1)
                d[key] = int(value.strip().split()[0]) * 1024
        total = int(d["MemTotal"])
        avail = int(d.get("MemAvailable", d.get("MemFree", 0)))
        load = round(100 * (1 - (avail / total))) if total else 0
        swap_total = int(d.get("SwapTotal", 0))
        swap_free = int(d.get("SwapFree", 0))
        # Windows "pagefile" includes commit headroom beyond physical RAM. Linux swap
        # is not identical, but this is adequate for deterministic CI/simulation.
        page_total = total + swap_total
        page_avail = avail + swap_free
        return total, avail, load, page_total, page_avail
    except Exception:
        return 0, 0, 0, 0, 0


def classify_mode(
    total: int,
    available: int,
    load_pct: int,
    disk_free: int,
    pagefile_available: int | None = None,
) -> str:
    """Classify machine pressure using real headroom, not RAM-load percent alone.

    80-95% physical-RAM load remains GREEN when physical/pagefile/disk headroom
    is healthy. This matches MBMPC's observed normal operating envelope.
    """
    page_avail = None if pagefile_available is None else int(pagefile_available)

    if (
        disk_free < 512 * MB
        or (total and available < 64 * MB)
        or load_pct >= 99
        or (page_avail is not None and page_avail < 128 * MB)
    ):
        return "CRITICAL"

    if (
        disk_free < 1024 * MB
        or (total and available < 96 * MB)
        or load_pct >= 98
        or (page_avail is not None and page_avail < 256 * MB)
    ):
        return "RED"

    if (
        (total and available < 160 * MB)
        or load_pct >= 96
        or (page_avail is not None and page_avail < 512 * MB)
    ):
        return "AMBER"

    return "GREEN"


def snapshot(path: str | Path | None = None) -> dict[str, Any]:
    total, available, load_pct, page_total, page_available = _memory()
    disk = shutil.disk_usage(path or os.getcwd())
    mode = classify_mode(
        total,
        available,
        load_pct,
        int(disk.free),
        pagefile_available=page_available if page_total else None,
    )
    normal_band = NORMAL_RAM_LOAD_MIN <= load_pct <= NORMAL_RAM_LOAD_MAX
    return {
        "schema": "bcp.resource_snapshot/1",
        "mode": mode,
        "memory_total": total,
        "memory_available": available,
        "memory_load_pct": load_pct,
        "normal_operating_band": normal_band,
        "normal_operating_band_pct": [NORMAL_RAM_LOAD_MIN, NORMAL_RAM_LOAD_MAX],
        "pagefile_total": page_total,
        "pagefile_available": page_available,
        "disk_free": int(disk.free),
        "pressure_basis": "HEADROOM_FIRST",
        "policy": {
            "GREEN": "normal operation; 80-95% RAM is acceptable when headroom is healthy",
            "AMBER": "headroom tightening; foreground tiny/light work, defer medium/heavy/background",
            "RED": "low real headroom; tiny essential/foreground work only",
            "CRITICAL": "continuity/receipt/health work only",
        }[mode],
        "field_certified": False,
    }


def decide(
    resource_class: str,
    *,
    mode: str | None = None,
    background: bool = False,
    essential: bool = False,
    local_ai_enabled: bool = False,
    available_bytes: int | None = None,
) -> AdmissionDecision:
    rc = str(resource_class).upper()
    if rc not in RESOURCE_ORDER:
        raise ValueError(f"unknown resource_class: {resource_class}")
    live = None
    if mode is None:
        live = snapshot()
        m = str(live["mode"]).upper()
        if available_bytes is None:
            available_bytes = int(live.get("memory_available") or 0)
    else:
        m = str(mode).upper()
    if m not in MODE_CAP_MB:
        raise ValueError(f"unknown resource mode: {m}")

    mode_process, mode_job = MODE_CAP_MB[m]
    class_cap = CLASS_CAP_MB[rc]
    process_cap = min(mode_process, class_cap) if class_cap else 0
    job_cap = min(mode_job, max(process_cap, class_cap + 16)) if class_cap else 0

    if rc == "R4_LOCAL_AI":
        return AdmissionDecision(
            False, m, rc, "LOCAL_AI_DISABLED_PHASE2",
            0, 0, False, local_ai_enabled=False,
        )

    max_by_mode = {
        "GREEN": RESOURCE_ORDER["R3_HEAVY"],
        "AMBER": RESOURCE_ORDER["R1_LIGHT"],
        "RED": RESOURCE_ORDER["R0_TINY"],
        "CRITICAL": RESOURCE_ORDER["R0_TINY"] if essential else -1,
    }[m]

    if available_bytes is not None and available_bytes > 0 and class_cap:
        required_headroom = (process_cap + HEADROOM_RESERVE_MB[rc]) * MB
        if int(available_bytes) < required_headroom:
            return AdmissionDecision(
                False, m, rc, "RESOURCE_HOLD_HEADROOM",
                process_cap, job_cap, False, local_ai_enabled=False,
            )

    if RESOURCE_ORDER[rc] > max_by_mode:
        return AdmissionDecision(
            False, m, rc, f"RESOURCE_HOLD_{m}",
            process_cap, job_cap, False, local_ai_enabled=False,
        )

    background_allowed = (
        m == "GREEN"
        and rc in {"R0_TINY", "R1_LIGHT", "R2_MEDIUM"}
    )
    if background and not background_allowed:
        return AdmissionDecision(
            False, m, rc, f"BACKGROUND_HOLD_{m}",
            process_cap, job_cap, False, local_ai_enabled=False,
        )

    return AdmissionDecision(
        True, m, rc, "ADMITTED",
        process_cap, job_cap, background_allowed, local_ai_enabled=False,
    )


def worker_policy(
    name: str,
    resource_class: str,
    timeout_seconds: float,
    *,
    mode: str | None = None,
    background: bool = False,
    essential: bool = False,
) -> tuple[AdmissionDecision, WorkerPolicy | None]:
    decision = decide(
        resource_class,
        mode=mode,
        background=background,
        essential=essential,
        local_ai_enabled=False,
    )
    if not decision.allowed:
        return decision, None
    return decision, WorkerPolicy(
        name=str(name),
        timeout_seconds=float(timeout_seconds),
        process_memory_mib=max(16, int(decision.process_memory_mib)),
        job_memory_mib=max(16, int(decision.job_memory_mib)),
        require_windows_job_object=True,
        background_priority=bool(background),
    )


__all__ = [
    "AdmissionDecision",
    "RESOURCE_ORDER",
    "NORMAL_RAM_LOAD_MIN",
    "NORMAL_RAM_LOAD_MAX",
    "HEADROOM_RESERVE_MB",
    "classify_mode",
    "snapshot",
    "decide",
    "worker_policy",
]
