from __future__ import annotations

"""Fail-closed local state-root policy for the BCP execution fabric.

Adapted unchanged in semantics from ChatGPT-PC vNext local_path_policy.py,
source commit 6bf6e32b36008957dda014542742657af6b9e017.

Transactional SQLite/WAL state must remain local. Provider-synced and UNC/network
roots are replication targets, never hot authority databases. Native Windows field
certification must still verify the underlying volume/reparse point.
"""

from pathlib import Path
import re


class NonLocalStatePath(ValueError):
    pass


_PROVIDER_COMPONENTS = (
    "mon drive",
    "my drive",
    "google drive",
    "googledrive",
    "drivefs",
    "onedrive",
    "dropbox",
    "icloud drive",
    "iclouddrive",
    "box sync",
    "box drive",
)


def _normalize(value: str) -> str:
    raw = str(value).replace("/", "\\").casefold().strip()
    return re.sub(r"\\+", r"\\", raw)


def _looks_nonlocal(value: str) -> bool:
    raw = str(value).replace("/", "\\").casefold().strip()
    if raw.startswith("\\\\") or raw.startswith("\\?\\unc\\"):
        return True
    compact = _normalize(raw)
    padded = "\\" + compact.strip("\\") + "\\"
    for component in _PROVIDER_COMPONENTS:
        marker = "\\" + component + "\\"
        if marker in padded:
            return True
    return False


def assert_local_state_root(path: str | Path) -> Path:
    p = Path(path)
    if _looks_nonlocal(str(path)):
        raise NonLocalStatePath(
            f"transactional state root must be local, not provider/network-synced: {path}"
        )
    try:
        resolved = p.expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        resolved = p
    if str(resolved) != str(path) and _looks_nonlocal(str(resolved)):
        raise NonLocalStatePath(
            f"transactional state root resolves to provider/network-synced storage: {path} -> {resolved}"
        )
    return p


__all__ = ["assert_local_state_root", "NonLocalStatePath"]
