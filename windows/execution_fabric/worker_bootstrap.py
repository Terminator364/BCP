from __future__ import annotations

"""Managed worker bootstrap used by the BCP Execution Fabric supervisor.\n\nReused from ChatGPT-PC vNext source commit 6bf6e32b36008957dda014542742657af6b9e017.

The bootstrap performs no project work before receiving a start plan on stdin. On
Windows this lets the parent attach the bootstrap process to a Job Object first; only
then is the real command created, so descendants inherit the job and the assign-after-
spawn race cannot escape the job boundary.

Output is drained continuously and retained only up to configured caps. This prevents a
worker that prints unbounded output from turning stdout/stderr capture into a RAM leak.
Large inputs belong in bounded spool/artifact files referenced by the plan, not inline.
"""

import base64
import json
import subprocess
import sys
import threading
from typing import BinaryIO


MAX_PLAN_BYTES = 1 * 1024 * 1024
MAX_INPUT_BYTES = 512 * 1024
TIMEOUT_EXIT = 124
TRUNCATION_MARKER = b"\n...[TRUNCATED_BY_CHATGPT_PC_WORKER_BOOTSTRAP]...\n"


def _read_plan() -> dict:
    raw = sys.stdin.buffer.readline(MAX_PLAN_BYTES + 1)
    if not raw or len(raw) > MAX_PLAN_BYTES:
        raise ValueError("invalid or oversized worker plan")
    plan = json.loads(raw.decode("utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("worker plan must be object")
    return plan


def _bounded_drain(pipe: BinaryIO, cap: int, out: bytearray) -> None:
    truncated = False
    while True:
        chunk = pipe.read(65536)
        if not chunk:
            break
        if len(out) < cap:
            room = cap - len(out)
            out.extend(chunk[:room])
            if len(chunk) > room:
                truncated = True
        else:
            truncated = True
    if truncated:
        if len(TRUNCATION_MARKER) <= cap:
            keep = cap - len(TRUNCATION_MARKER)
            del out[keep:]
            out.extend(TRUNCATION_MARKER)
        else:
            del out[cap:]


def main() -> int:
    try:
        plan = _read_plan()
        argv = plan.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
            raise ValueError("invalid argv")
        timeout = float(plan.get("timeout_seconds"))
        if not (0.1 <= timeout <= 86400):
            raise ValueError("invalid timeout")
        stdout_cap = int(plan.get("max_stdout_bytes"))
        stderr_cap = int(plan.get("max_stderr_bytes"))
        if not (4096 <= stdout_cap <= 16 * 1024 * 1024):
            raise ValueError("invalid stdout cap")
        if not (4096 <= stderr_cap <= 16 * 1024 * 1024):
            raise ValueError("invalid stderr cap")
        cwd = plan.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            raise ValueError("invalid cwd")
        input_b64 = plan.get("input_b64") or ""
        if not isinstance(input_b64, str):
            raise ValueError("invalid input")
        input_bytes = base64.b64decode(input_b64.encode("ascii"), validate=True) if input_b64 else b""
        if len(input_bytes) > MAX_INPUT_BYTES:
            raise ValueError("worker input exceeds cap")

        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out = bytearray()
        err = bytearray()
        t_out = threading.Thread(target=_bounded_drain, args=(proc.stdout, stdout_cap, out), daemon=True)
        t_err = threading.Thread(target=_bounded_drain, args=(proc.stderr, stderr_cap, err), daemon=True)
        t_out.start(); t_err.start()

        if proc.stdin is not None:
            try:
                if input_bytes:
                    proc.stdin.write(input_bytes)
                    proc.stdin.flush()
            finally:
                proc.stdin.close()

        timed_out = False
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            rc = proc.wait()

        t_out.join(timeout=5.0)
        t_err.join(timeout=5.0)
        if t_out.is_alive() or t_err.is_alive():
            proc.kill()
            raise RuntimeError("output drain did not terminate")

        if out:
            sys.stdout.buffer.write(out)
            sys.stdout.buffer.flush()
        if err:
            sys.stderr.buffer.write(err)
        if timed_out:
            sys.stderr.buffer.write(b"\nCHATGPT_PC_WORKER_TIMEOUT\n")
            sys.stderr.buffer.flush()
            return TIMEOUT_EXIT
        sys.stderr.buffer.flush()
        return int(rc)
    except Exception as exc:
        sys.stderr.write(f"CHATGPT_PC_WORKER_BOOTSTRAP_ERROR:{type(exc).__name__}:{exc}\n")
        sys.stderr.flush()
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
