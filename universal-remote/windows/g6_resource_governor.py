"""BCP G6 resource-awareness for 4 GB Windows PCs.

Never cancels an existing owner task, alters Windows settings, or imposes an
artificial total time/operation/file-size cap. Only delays NEW background
work during severe low-memory conditions; user control remains available.
"""
from __future__ import annotations
from dataclasses import dataclass
import os
import sys

MIB=1024*1024

@dataclass(frozen=True)
class Resources:
    total_bytes:int
    available_bytes:int
    def __post_init__(self):
        if (type(self.total_bytes)!=int or type(self.available_bytes)!=int or
            self.total_bytes<=0 or not 0<=self.available_bytes<=self.total_bytes):
            raise ValueError("INVALID_RESOURCE_SAMPLE")
    @property
    def free_mib(self):
        return self.available_bytes/MIB
    @property
    def free_percent(self):
        return self.available_bytes*100/self.total_bytes

def windows_memory():
    if os.name!="nt":
        raise OSError("WINDOWS_ONLY")
    import ctypes
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_=[("dwLength",ctypes.c_ulong),
                  ("dwMemoryLoad",ctypes.c_ulong),
                  ("ullTotalPhys",ctypes.c_ulonglong),
                  ("ullAvailPhys",ctypes.c_ulonglong),
                  ("ullTotalPageFile",ctypes.c_ulonglong),
                  ("ullAvailPageFile",ctypes.c_ulonglong),
                  ("ullTotalVirtual",ctypes.c_ulonglong),
                  ("ullAvailVirtual",ctypes.c_ulonglong),
                  ("ullAvailExtendedVirtual",ctypes.c_ulonglong)]
    state=MEMORYSTATUSEX()
    state.dwLength=ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
        raise OSError("WINDOWS_MEMORY_QUERY_FAILED")
    return Resources(state.ullTotalPhys,state.ullAvailPhys)

class ResourceGovernor:
    """Hysteretic admission control for NEW optional jobs, not user capacity."""
    def __init__(self,critical_mib=128,resume_mib=256):
        if not (0<critical_mib<resume_mib):
            raise ValueError("MEMORY_POLICY_INVALID")
        self.critical=critical_mib
        self.resume=resume_mib
        self.pause_heavy=False
    def decide(self,sample:Resources,active_heavy=0):
        if not isinstance(sample,Resources):
            raise ValueError("RESOURCE_SAMPLE_REQUIRED")
        if type(active_heavy)!=int or active_heavy<0:
            raise ValueError("ACTIVE_WORKERS_INVALID")
        if sample.free_mib<=self.critical:
            self.pause_heavy=True
        elif sample.free_mib>=self.resume:
            self.pause_heavy=False
        # Resource cap is concurrent worker count only; not a count of queued
        # operations or total bytes.
        allowed=(not self.pause_heavy and active_heavy<1)
        return {
            "start_optional_heavy_job":allowed,
            "leave_existing_jobs_running":True,
            "queued_jobs_retained":True,
            "user_interactive_control_allowed":True,
            "max_heavy_concurrent":1,
            "max_total_operations":None,
            "max_total_transfer_bytes":None,
            "per_chunk_bytes":65536,
            "memory_free_mib":round(sample.free_mib,1),
            "reason":"RAM_PRESSURE" if self.pause_heavy else
                     "HEAVY_WORKER_BUSY" if active_heavy>=1 else "AVAILABLE"
        }
