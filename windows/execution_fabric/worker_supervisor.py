from __future__ import annotations

"""Experimental vNext worker supervisor.

DESIGN-ONLY: this module is not imported by the canonical G6.0.22 runtime.

The supervisor never launches arbitrary project work directly. It launches the controlled
`worker_bootstrap.py`, attaches that bootstrap to a Windows Job Object first, and only
then sends the real work plan over stdin. The bootstrap cannot create the real child
before the plan arrives, closing the assign-after-spawn escape window for project work.

Large worker inputs must be passed by bounded spool/artifact references, not giant pipes.
"""

import base64
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Mapping, Sequence


MAX_INLINE_INPUT_BYTES = 512 * 1024
BOOTSTRAP_OVERHEAD_SECONDS = 5.0
BOOTSTRAP_TIMEOUT_EXIT = 124
BOOTSTRAP_ERROR_EXIT = 125


class WorkerSupervisorError(RuntimeError):
    pass


class WorkerIsolationError(WorkerSupervisorError):
    pass


class WorkerTimeout(WorkerSupervisorError):
    pass


class WorkerBootstrapError(WorkerSupervisorError):
    pass


@dataclass(frozen=True)
class WorkerPolicy:
    name: str
    timeout_seconds: float
    process_memory_mib: int
    job_memory_mib: int
    max_stdout_bytes: int = 1_048_576
    max_stderr_bytes: int = 1_048_576
    require_windows_job_object: bool = True
    background_priority: bool = True

    def validate(self) -> None:
        if not self.name or len(self.name) > 96:
            raise ValueError("invalid worker name")
        if not (0.1 <= float(self.timeout_seconds) <= 86_400):
            raise ValueError("invalid timeout")
        if not (16 <= int(self.process_memory_mib) <= 4096):
            raise ValueError("invalid per-process memory cap")
        if not (int(self.process_memory_mib) <= int(self.job_memory_mib) <= 8192):
            raise ValueError("invalid job memory cap")
        if not (4096 <= int(self.max_stdout_bytes) <= 16 * 1024 * 1024):
            raise ValueError("invalid stdout cap")
        if not (4096 <= int(self.max_stderr_bytes) <= 16 * 1024 * 1024):
            raise ValueError("invalid stderr cap")


@dataclass(frozen=True)
class WorkerResult:
    name: str
    pid: int
    returncode: int
    duration_ms: float
    stdout: bytes
    stderr: bytes
    isolation: str
    timed_out: bool = False


class _WindowsJob:
    """Small ctypes wrapper around a Windows Job Object."""

    def __init__(self, policy: WorkerPolicy):
        if os.name != "nt":
            raise OSError("Windows Job Objects are only available on Windows")
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._wintypes = wintypes
        self._k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._handle = None
        self._closed = False
        self._policy = policy
        self._setup_types()
        self._create_and_limit()

    def _setup_types(self) -> None:
        ctypes = self._ctypes
        wintypes = self._wintypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        self._EXT = JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        self._k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self._k32.CreateJobObjectW.restype = wintypes.HANDLE
        self._k32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
        ]
        self._k32.SetInformationJobObject.restype = wintypes.BOOL
        self._k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self._k32.AssignProcessToJobObject.restype = wintypes.BOOL
        self._k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self._k32.TerminateJobObject.restype = wintypes.BOOL
        self._k32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._k32.CloseHandle.restype = wintypes.BOOL

    def _create_and_limit(self) -> None:
        ctypes = self._ctypes
        h = self._k32.CreateJobObjectW(None, None)
        if not h:
            raise WorkerIsolationError(f"CreateJobObjectW failed: {ctypes.get_last_error()}")
        self._handle = h

        JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
        JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
        JobObjectExtendedLimitInformation = 9

        info = self._EXT()
        info.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_PROCESS_MEMORY
            | JOB_OBJECT_LIMIT_JOB_MEMORY
            | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        mib = 1024 * 1024
        info.ProcessMemoryLimit = int(self._policy.process_memory_mib) * mib
        info.JobMemoryLimit = int(self._policy.job_memory_mib) * mib
        ok = self._k32.SetInformationJobObject(
            h,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not ok:
            err = ctypes.get_last_error()
            self.close()
            raise WorkerIsolationError(f"SetInformationJobObject failed: {err}")

    def assign(self, process_handle: int) -> None:
        if self._closed or not self._handle:
            raise WorkerIsolationError("job already closed")
        ok = self._k32.AssignProcessToJobObject(self._handle, process_handle)
        if not ok:
            raise WorkerIsolationError(
                f"AssignProcessToJobObject failed: {self._ctypes.get_last_error()}"
            )

    def terminate(self, exit_code: int = 0xDEAD) -> None:
        if not self._closed and self._handle:
            self._k32.TerminateJobObject(self._handle, int(exit_code))

    def close(self) -> None:
        if not self._closed and self._handle:
            self._k32.CloseHandle(self._handle)
            self._closed = True
            self._handle = None


class WorkerSupervisor:
    def __init__(self, *, allow_non_windows_test_mode: bool = False):
        self.allow_non_windows_test_mode = bool(allow_non_windows_test_mode)

    @staticmethod
    def _creation_flags(policy: WorkerPolicy) -> int:
        if os.name != "nt":
            return 0
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if policy.background_priority:
            # BELOW_NORMAL_PRIORITY_CLASS
            flags |= 0x00004000
        return flags

    @staticmethod
    def _cap(data: bytes | None, limit: int) -> bytes:
        raw = data or b""
        if len(raw) <= limit:
            return raw
        marker = b"\n...[TRUNCATED_BY_BCP_WORKER_SUPERVISOR]...\n"
        keep = max(0, limit - len(marker))
        return raw[:keep] + marker

    @staticmethod
    def _bootstrap_path() -> Path:
        p = Path(__file__).with_name("worker_bootstrap.py").resolve()
        if not p.is_file():
            raise WorkerBootstrapError(f"worker bootstrap missing: {p}")
        return p

    @staticmethod
    def _plan_bytes(
        argv: Sequence[str], policy: WorkerPolicy, input_bytes: bytes | None, cwd: str | None
    ) -> bytes:
        args = [str(x) for x in argv]
        if not args or any(not x for x in args):
            raise ValueError("invalid argv")
        raw_input = input_bytes or b""
        if len(raw_input) > MAX_INLINE_INPUT_BYTES:
            raise ValueError(
                f"inline worker input too large ({len(raw_input)} bytes); use a spool/artifact reference"
            )
        plan = {
            "argv": args,
            "cwd": cwd,
            "timeout_seconds": float(policy.timeout_seconds),
            "max_stdout_bytes": int(policy.max_stdout_bytes),
            "max_stderr_bytes": int(policy.max_stderr_bytes),
            "input_b64": base64.b64encode(raw_input).decode("ascii") if raw_input else "",
        }
        encoded = json.dumps(plan, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(encoded) > 1024 * 1024:
            raise ValueError("worker plan exceeds 1 MiB")
        return encoded

    def run(
        self,
        argv: Sequence[str],
        policy: WorkerPolicy,
        *,
        input_bytes: bytes | None = None,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> WorkerResult:
        policy.validate()
        plan = self._plan_bytes(argv, policy, input_bytes, cwd)

        if os.name != "nt" and policy.require_windows_job_object and not self.allow_non_windows_test_mode:
            raise WorkerIsolationError("Windows Job Object required by policy")

        bootstrap = self._bootstrap_path()
        started = time.monotonic()
        popen_env = None if env is None else {str(k): str(v) for k, v in env.items()}
        # -I isolates the bootstrap from user Python path/site/environment injection. The real
        # worker still receives the OS environment but is created only after the job boundary.
        proc = subprocess.Popen(
            [sys.executable, "-I", str(bootstrap)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=popen_env,
            creationflags=self._creation_flags(policy),
        )

        job = None
        isolation = "NON_WINDOWS_TEST_MODE"
        try:
            if os.name == "nt":
                try:
                    job = _WindowsJob(policy)
                    # At this point bootstrap is blocked waiting for stdin; arbitrary project work
                    # has not been created yet. Attach first, deliver the plan second.
                    job.assign(int(proc._handle))  # type: ignore[attr-defined]
                    isolation = "WINDOWS_JOB_OBJECT_START_GATED"
                except Exception:
                    try:
                        proc.kill()
                        proc.communicate(timeout=2.0)
                    except Exception:
                        pass
                    if job is not None:
                        job.close()
                    if policy.require_windows_job_object:
                        raise
                    isolation = "WINDOWS_UNISOLATED_DEGRADED"

            parent_timeout = float(policy.timeout_seconds) + BOOTSTRAP_OVERHEAD_SECONDS
            try:
                out, err = proc.communicate(input=plan, timeout=parent_timeout)
            except subprocess.TimeoutExpired as exc:
                if job is not None:
                    job.terminate()
                else:
                    proc.kill()
                out, err = proc.communicate()
                result = WorkerResult(
                    name=policy.name,
                    pid=proc.pid,
                    returncode=proc.returncode if proc.returncode is not None else -1,
                    duration_ms=(time.monotonic() - started) * 1000.0,
                    stdout=self._cap(out, policy.max_stdout_bytes),
                    stderr=self._cap(err, policy.max_stderr_bytes),
                    isolation=isolation,
                    timed_out=True,
                )
                raise WorkerTimeout(result) from exc

            duration_ms = (time.monotonic() - started) * 1000.0
            out = self._cap(out, policy.max_stdout_bytes)
            err = self._cap(err, policy.max_stderr_bytes)
            if proc.returncode == BOOTSTRAP_TIMEOUT_EXIT:
                result = WorkerResult(
                    name=policy.name,
                    pid=proc.pid,
                    returncode=BOOTSTRAP_TIMEOUT_EXIT,
                    duration_ms=duration_ms,
                    stdout=out,
                    stderr=err,
                    isolation=isolation,
                    timed_out=True,
                )
                raise WorkerTimeout(result)
            if proc.returncode == BOOTSTRAP_ERROR_EXIT:
                raise WorkerBootstrapError(err.decode("utf-8", errors="replace")[-4000:])

            return WorkerResult(
                name=policy.name,
                pid=proc.pid,
                returncode=int(proc.returncode or 0),
                duration_ms=duration_ms,
                stdout=out,
                stderr=err,
                isolation=isolation,
                timed_out=False,
            )
        finally:
            if job is not None:
                job.close()


def field_policy_for_mode(name: str, mode: str, timeout_seconds: float) -> WorkerPolicy:
    """Conservative prototype caps aligned with the existing G6 resource governor."""
    m = str(mode).upper()
    caps = {
        "GREEN": (192, 224),
        "AMBER": (96, 112),
        "RED": (64, 72),
        "CRITICAL": (48, 56),
    }
    if m not in caps:
        raise ValueError(f"unknown resource mode: {mode}")
    process_mib, job_mib = caps[m]
    return WorkerPolicy(
        name=name,
        timeout_seconds=timeout_seconds,
        process_memory_mib=process_mib,
        job_memory_mib=job_mib,
        require_windows_job_object=True,
        background_priority=True,
    )


__all__ = [
    "WorkerPolicy",
    "WorkerResult",
    "WorkerSupervisor",
    "WorkerSupervisorError",
    "WorkerIsolationError",
    "WorkerBootstrapError",
    "WorkerTimeout",
    "field_policy_for_mode",
]
