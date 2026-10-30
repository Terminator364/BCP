"""BCP G4: scoped, HMAC-sealed short-lived grants for low-risk Windows actions.

No admin elevation. No shell, executable, overwrite or deletion under a grant.
Only the local Windows approval UI can seal a grant_session ticket.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import time

_ALLOWED = frozenset(("mkdir", "write_text_new"))
_TEXT_SUFFIXES = frozenset((".txt", ".md", ".csv"))
_GRANT_ID = re.compile(r"^[a-f0-9]{32}$")
_OPERATION_ID = re.compile(r"^[a-f0-9]{32}$")
_MAX_SECONDS = 1800
_MAX_ACTIONS = 20
_MAX_BYTES = 65536


def _reparse(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _no_reparse_components(path: Path, home: Path) -> None:
    try:
        parts = path.relative_to(home).parts
    except ValueError:
        raise ValueError("SESSION_OUTSIDE_USER_HOME") from None
    cursor = home
    if _reparse(cursor):
        raise ValueError("SESSION_REPARSE_DENIED")
    for part in parts:
        cursor = cursor / part
        if _reparse(cursor):
            raise ValueError("SESSION_REPARSE_DENIED")


def make_grant_spec(payload, safe_target):
    if not isinstance(payload, dict) or payload.get("kind") != "grant_session":
        raise ValueError("SESSION_SPEC_INVALID")
    root = safe_target(payload.get("root"))
    if not root.is_dir():
        raise ValueError("SESSION_ROOT_NOT_DIRECTORY")
    home = Path.home().resolve(strict=True)
    try:
        rel = root.relative_to(home)
    except ValueError:
        raise ValueError("SESSION_ROOT_OUTSIDE_HOME") from None
    if len(rel.parts) < 2:
        raise ValueError("SESSION_SCOPE_TOO_BROAD")
    _no_reparse_components(root, home)
    actions = payload.get("actions", ["mkdir", "write_text_new"])
    if not isinstance(actions, list) or not actions or len(actions) != len(set(actions)):
        raise ValueError("SESSION_ACTIONS_INVALID")
    if any(x not in _ALLOWED for x in actions):
        raise ValueError("SESSION_ACTION_NOT_ALLOWED")
    seconds = payload.get("duration_seconds", 900)
    operations = payload.get("max_operations", 10)
    max_bytes = payload.get("max_total_bytes", 16384)
    if (type(seconds) is not int or not 60 <= seconds <= _MAX_SECONDS or
        type(operations) is not int or not 1 <= operations <= _MAX_ACTIONS or
        type(max_bytes) is not int or not 0 <= max_bytes <= _MAX_BYTES):
        raise ValueError("SESSION_LIMITS_INVALID")
    return {
        "kind": "grant_session",
        "root": str(root),
        "actions": sorted(actions),
        "duration_seconds": seconds,
        "max_operations": operations,
        "max_total_bytes": max_bytes,
    }


def _signed(data, secret):
    body = {key: value for key, value in data.items() if key != "mac"}
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":")).encode("utf8")
    return hmac.new(secret, raw, hashlib.sha256).hexdigest()


def _read(grant_path, secret):
    if not grant_path.is_file():
        raise ValueError("SESSION_NOT_FOUND")
    state = json.loads(grant_path.read_text("utf8"))
    actual = state.get("mac", "")
    if (not isinstance(actual, str) or
        not hmac.compare_digest(actual, _signed(state, secret))):
        raise ValueError("SESSION_TAMPERED")
    return state


def _write(file, data, secret, json_atomic):
    data = dict(data)
    data["mac"] = _signed(data, secret)
    json_atomic(file, data)


def _grant_file(grant_dir, ident):
    if not isinstance(ident, str) or not _GRANT_ID.fullmatch(ident):
        raise ValueError("SESSION_ID_INVALID")
    return grant_dir / (ident + ".json")


def issue(ticket, spec, secret, directory, json_atomic, now=None):
    """Called ONLY after commit verified a local Windows HMAC-sealed approval."""
    now = int(time.time() if now is None else now)
    if spec.get("kind") != "grant_session":
        raise ValueError("SESSION_SPEC_INVALID")
    directory.mkdir(parents=True, exist_ok=True)
    file = _grant_file(directory, ticket)
    if file.exists():
        raise ValueError("SESSION_ALREADY_ISSUED")
    grant = {
        "schema": "BCP_G4_SESSION_V1", "id": ticket,
        "root": spec["root"], "actions": spec["actions"],
        "created": now, "expires": now + spec["duration_seconds"],
        "max_operations": spec["max_operations"],
        "max_total_bytes": spec["max_total_bytes"],
        "used_operations": 0, "used_bytes": 0,
        "state": "ACTIVE", "last_operation": None,
    }
    _write(file, grant, secret, json_atomic)
    return {
        "grant_id": ticket, "root": spec["root"],
        "expires": grant["expires"], "operations_left": spec["max_operations"],
        "allowed": spec["actions"], "state": "ACTIVE",
    }


def status(ident, secret, directory):
    state = _read(_grant_file(directory, ident), secret)
    return {
        "grant_id": state["id"], "root": state["root"],
        "state": state["state"], "expires": state["expires"],
        "expired": int(time.time()) > state["expires"],
        "allowed": state["actions"],
        "operations_left": max(0, state["max_operations"] - state["used_operations"]),
        "bytes_left": max(0, state["max_total_bytes"] - state["used_bytes"]),
    }


def revoke(ident, secret, directory, json_atomic):
    file = _grant_file(directory, ident)
    lock = directory / (ident + ".lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("SESSION_BUSY")
    os.close(fd)
    try:
        state = _read(file, secret)
        state["state"] = "REVOKED"
        _write(file, state, secret, json_atomic)
        return {"grant_id": ident, "state": "REVOKED"}
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def _path_check(raw, root_raw, operation, safe_target):
    if not isinstance(raw, str) or len(raw) > 512:
        raise ValueError("SESSION_PATH_INVALID")
    root = Path(root_raw)
    if not root.is_dir() or _reparse(root):
        raise ValueError("SESSION_ROOT_REPLACED")
    path = Path(raw)
    if not path.is_absolute() or path == root:
        raise ValueError("SESSION_PATH_INVALID")
    # Require the syntactic path to be beneath the approved root before resolving.
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise ValueError("SESSION_PATH_OUTSIDE_SCOPE") from None
    if not relative.parts or any(x in (".", "..") for x in relative.parts):
        raise ValueError("SESSION_TRAVERSAL_DENIED")
    _no_reparse_components(path, root)
    canonical = safe_target(str(path), create=True)
    try:
        canonical.relative_to(root)
    except ValueError:
        raise ValueError("SESSION_PATH_OUTSIDE_SCOPE") from None
    # No nested folder creation in one operation; scope is explicit.
    if operation == "mkdir":
        if path.exists():
            raise ValueError("SESSION_TARGET_EXISTS")
    elif operation == "write_text_new":
        if canonical.suffix.lower() not in _TEXT_SUFFIXES:
            raise ValueError("SESSION_FILE_TYPE_DENIED")
        if path.exists():
            raise ValueError("SESSION_OVERWRITE_DENIED")
    else:
        raise ValueError("SESSION_ACTION_NOT_ALLOWED")
    return canonical


def apply(payload, secret, directory, json_atomic, safe_target, record):
    if not isinstance(payload, dict):
        raise ValueError("SESSION_PAYLOAD_INVALID")
    ident = payload.get("grant_id")
    op_id = payload.get("operation_id")
    operation = payload.get("kind")
    if not isinstance(op_id, str) or not _OPERATION_ID.fullmatch(op_id):
        raise ValueError("SESSION_OPERATION_ID_REQUIRED")
    file = _grant_file(directory, ident)
    lock = directory / (ident + ".lock")
    # Atomic exclusive claim, cross-process. A stale lock fails closed.
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("SESSION_BUSY")
    os.close(fd)
    try:
        state = _read(file, secret)
        if state["state"] != "ACTIVE" or time.time() > state["expires"]:
            raise ValueError("SESSION_EXPIRED_OR_REVOKED")
        if operation not in state["actions"]:
            raise ValueError("SESSION_ACTION_NOT_ALLOWED")
        if state["used_operations"] >= state["max_operations"]:
            raise ValueError("SESSION_QUOTA_EXHAUSTED")
        operation_log = directory / (ident + ".ops")
        if operation_log.exists():
            prior_ids = {line.strip() for line in operation_log.read_text("ascii").splitlines()}
            if op_id in prior_ids:
                raise ValueError("SESSION_OPERATION_REPLAY")
        target = _path_check(payload.get("path"), state["root"], operation, safe_target)
        body = b""
        if operation == "write_text_new":
            content = payload.get("text")
            if not isinstance(content, str):
                raise ValueError("SESSION_TEXT_INVALID")
            body = content.encode("utf8")
            if len(body) > 8192:
                raise ValueError("SESSION_TEXT_TOO_LARGE")
        if state["used_bytes"] + len(body) > state["max_total_bytes"]:
            raise ValueError("SESSION_BYTE_QUOTA_EXHAUSTED")
        # Reserve quota and idempotency token before touching disk; failures fail closed.
        state["used_operations"] += 1
        state["used_bytes"] += len(body)
        state["last_operation"] = op_id
        _write(file, state, secret, json_atomic)
        with operation_log.open("a", encoding="ascii") as out:
            out.write(op_id + "\n")
            out.flush()
            os.fsync(out.fileno())
        # Last-minute parent path check. Not a guarantee against malicious local
        # concurrent junction swaps; Windows OS file permissions remain authoritative.
        _path_check(str(target), state["root"], operation, safe_target)
        if operation == "mkdir":
            target.mkdir(exist_ok=False)
            result = {"created": str(target)}
        else:
            with target.open("xb") as out:
                out.write(body)
                out.flush()
                os.fsync(out.fileno())
            result = {"created": str(target), "bytes": len(body),
                      "sha256": hashlib.sha256(body).hexdigest()}
        record("g4_session_" + operation, "DONE", ident)
        return {
            "status": "DONE", "grant_id": ident,
            "remaining": state["max_operations"] - state["used_operations"],
            "result": result,
        }
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass
