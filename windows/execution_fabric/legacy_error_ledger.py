from __future__ import annotations

"""Read-only projection of the historical BCP Error Ledger into recipe candidates.

Historical FIXED incidents are useful knowledge, not executable authority. This module never
creates RepairRecipe steps and never marks a historical row VALIDATED.
"""

import hashlib
import json
from pathlib import Path
from typing import Any


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def load_error_ledger_candidates(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    out: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid error ledger json line {line_no}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"error ledger line {line_no} must be object")
            project = str(row.get("project") or "BCP")
            error_id = str(row.get("id") or f"line-{line_no}")
            symptom = str(row.get("symptom") or "")
            mechanism = str(row.get("mechanism") or "")
            signature_payload = {
                "project": project,
                "error_id": error_id,
                "symptom": symptom,
                "mechanism": mechanism,
            }
            signature = hashlib.sha256(_canonical(signature_payload)).hexdigest()
            status = str(row.get("status") or "UNKNOWN")
            regression = row.get("regression")
            prevention = row.get("prevention")
            repair = row.get("repair")
            closed_for_learning = status.startswith("FIXED") or status == "CORRECTED"
            candidate_ready = bool(
                closed_for_learning
                and regression
                and (prevention or repair)
            )
            out.append({
                "schema": "bcp.legacy_incident_candidate/1",
                "source": str(p),
                "line": line_no,
                "project_id": project,
                "legacy_error_id": error_id,
                "signature": signature,
                "status": status,
                "symptom": symptom,
                "mechanism": mechanism,
                "prevention": prevention or [],
                "repair": repair,
                "regression_ref": regression,
                "candidate_for_recipe_authoring": candidate_ready,
                "executable": False,
                "recipe_status": "CANDIDATE_ONLY",
                "field_certified": False,
            })
    return out


__all__ = ["load_error_ledger_candidates"]
