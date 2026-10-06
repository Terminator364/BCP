from __future__ import annotations

"""BCP Phase 5 generic release transaction controller.

This module never downloads, installs, launches or rolls back project bytes itself.
It orchestrates typed Project Adapter operations and persists release truth in the
shared fenced CriticalStore.
"""

from copy import deepcopy
import datetime as dt
import re
from typing import Any

from .critical_store import CriticalStore, RevisionConflict
from .resource_admission import RESOURCE_ORDER

RELEASE_PERMISSION_ORDER = {
    "P0_READ": 0,
    "P1_SAFE_WRITE": 1,
    "P2_PROJECT_MUTATION": 2,
    "P3_BOUNDED_SYSTEM_CHANGE": 3,
    "P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE": 4,
}
from .resource_admission import decide as resource_decide

RELEASE_PREFIX = "release/"
PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
RELEASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,159}$")
SHA_RE = re.compile(r"^[a-f0-9]{64}$")

TERMINAL_STATES = {"COMMITTED", "ROLLED_BACK", "SUPERSEDED_NO_ROLLBACK", "FAILED_SAFE"}
REQUIRED_OPERATIONS = ("RELEASE_VERIFY", "UPDATE_STAGE", "UPDATE_ACTIVATE", "HEALTHCHECK", "ROLLBACK")
SCOPE_ORDER = {"REPOSITORY": 0, "SIMULATION": 1, "PROVIDER": 2, "FIELD": 3}

OP_STATE = {
    "RELEASE_VERIFY": "VERIFY_READY",
    "UPDATE_STAGE": "STAGE_READY",
    "UPDATE_ACTIVATE": "ACTIVATE_READY",
    "HEALTHCHECK": "HEALTH_PENDING",
    "ROLLBACK": "ROLLBACK_READY",
}


class ReleaseControllerError(RuntimeError):
    pass


class ReleaseNotFound(ReleaseControllerError):
    pass


class ReleaseRevisionConflict(ReleaseControllerError):
    pass


class ReleaseTransitionError(ReleaseControllerError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _text(value: Any, field: str, cap: int) -> str:
    text = str(value or "").strip()
    if not text or len(text) > cap:
        raise ValueError(f"invalid {field}")
    return text


def _validate_release_ref(value: Any, *, lkg: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("release ref must be object")
    allowed = {
        "version", "sequence", "artifact_sha256", "manifest_ref",
        "source_revision", "qualification",
    }
    if lkg:
        allowed |= {"proof_scope", "proven"}
    if set(value) != allowed:
        raise ValueError("invalid release ref fields")
    _text(value.get("version"), "release version", 128)
    if type(value.get("sequence")) is not int or value["sequence"] < 1:
        raise ValueError("invalid release sequence")
    sha = str(value.get("artifact_sha256") or "").lower()
    if not SHA_RE.fullmatch(sha):
        raise ValueError("invalid artifact sha256")
    _text(value.get("manifest_ref"), "manifest_ref", 512)
    _text(value.get("source_revision"), "source_revision", 256)
    if value.get("qualification") not in {
        "CANDIDATE", "CI_QUALIFIED", "PROVIDER_VERIFIED", "FIELD_VERIFIED"
    }:
        raise ValueError("invalid qualification")
    if lkg:
        if value.get("proof_scope") not in {"REPOSITORY", "SIMULATION", "PROVIDER", "FIELD"}:
            raise ValueError("invalid LKG proof_scope")
        if type(value.get("proven")) is not bool:
            raise ValueError("invalid LKG proven")
    out = deepcopy(value)
    out["artifact_sha256"] = sha
    return out


def operation_bindings_from_adapter(adapter: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(adapter, dict) or adapter.get("schema") != "bcp.project_adapter/1":
        raise ValueError("invalid project adapter")
    bindings = adapter.get("bindings")
    if not isinstance(bindings, list):
        raise ValueError("invalid adapter bindings")
    by_operation: dict[str, dict[str, Any]] = {}
    for binding in bindings:
        if not isinstance(binding, dict):
            raise ValueError("invalid adapter binding")
        op = str(binding.get("operation") or "")
        if op in by_operation:
            raise ValueError(f"duplicate adapter operation: {op}")
        by_operation[op] = binding
    out: dict[str, dict[str, Any]] = {}
    for op in REQUIRED_OPERATIONS:
        b = by_operation.get(op)
        if b is None:
            out[op] = {
                "capability_id": None,
                "provider_id": None,
                "state": "UNSUPPORTED",
                "permission_class": None,
                "resource_class": None,
                "evidence_contract": [],
            }
            continue
        out[op] = {
            "capability_id": _text(b.get("capability_id"), f"{op} capability_id", 160),
            "provider_id": _text(b.get("provider_id"), f"{op} provider_id", 160),
            "state": str(b.get("state") or ""),
            "permission_class": str(b.get("permission_class") or ""),
            "resource_class": str(b.get("resource_class") or ""),
            "evidence_contract": list(b.get("evidence_contract") or []),
        }
        if out[op]["state"] not in {"BOUND", "WAITING_BINDING", "TEMP_UNAVAILABLE", "UNSUPPORTED"}:
            raise ValueError(f"invalid {op} binding state")
        if out[op]["permission_class"] not in RELEASE_PERMISSION_ORDER:
            raise ValueError(f"invalid {op} permission")
        if out[op]["resource_class"] not in RESOURCE_ORDER:
            raise ValueError(f"invalid {op} resource")
        if not out[op]["evidence_contract"]:
            raise ValueError(f"missing {op} evidence contract")
    return out


def release_stream_id(project_id: str, release_id: str) -> str:
    project = _text(project_id, "project_id", 128)
    rid = _text(release_id, "release_id", 160)
    if not PROJECT_ID_RE.fullmatch(project):
        raise ValueError("invalid project_id")
    if not RELEASE_ID_RE.fullmatch(rid):
        raise ValueError("invalid release_id")
    return f"{RELEASE_PREFIX}{project}/{rid}"


def _operation_hold_reason(tx: dict[str, Any], operation: str, resource_mode: str) -> tuple[str | None, str | None]:
    binding = tx["operations"][operation]
    if binding["state"] != "BOUND":
        return "WAITING_CAPABILITY", f"{operation}_{binding['state']}"
    policy = tx["policy"]
    if RELEASE_PERMISSION_ORDER[binding["permission_class"]] > RELEASE_PERMISSION_ORDER[policy["max_permission_class"]]:
        return "WAITING_APPROVAL", f"{operation}_PERMISSION_CEILING"
    if RESOURCE_ORDER[binding["resource_class"]] > RESOURCE_ORDER[policy["resource_ceiling"]]:
        return "WAITING_RESOURCE", f"{operation}_RESOURCE_CEILING"
    admission = resource_decide(
        binding["resource_class"], mode=resource_mode, background=False, essential=False
    )
    if not admission.allowed:
        return "WAITING_RESOURCE", admission.reason
    return None, None


def validate_transaction(tx: Any) -> dict[str, Any]:
    if not isinstance(tx, dict) or tx.get("schema") != "bcp.release_transaction/1":
        raise ValueError("invalid release transaction")
    required = {
        "schema", "release_id", "project_id", "state", "candidate", "current", "lkg",
        "migration", "policy", "operations", "receipts", "readback", "created_at", "updated_at",
    }
    optional = {"rollback_readback", "failure"}
    if set(tx) - required - optional or not required <= set(tx):
        raise ValueError("invalid release transaction fields")
    release_stream_id(tx["project_id"], tx["release_id"])
    candidate = _validate_release_ref(tx["candidate"])
    current = _validate_release_ref(tx["current"]) if tx["current"] is not None else None
    lkg = _validate_release_ref(tx["lkg"], lkg=True) if tx["lkg"] is not None else None

    migration = tx["migration"]
    if not isinstance(migration, dict) or set(migration) != {
        "class", "approval_granted", "rollback_capability_required", "notes"
    }:
        raise ValueError("invalid migration")
    if migration["class"] not in {"NONE", "BACKWARD_COMPATIBLE", "REVERSIBLE", "IRREVERSIBLE"}:
        raise ValueError("invalid migration class")
    if type(migration["approval_granted"]) is not bool or type(migration["rollback_capability_required"]) is not bool:
        raise ValueError("invalid migration booleans")

    policy = tx["policy"]
    if not isinstance(policy, dict) or set(policy) != {
        "target_scope", "rollback_required", "anti_downgrade", "exact_readback_required",
        "healthcheck_required", "max_permission_class", "resource_ceiling"
    }:
        raise ValueError("invalid release policy")
    if policy["target_scope"] not in {"REPOSITORY", "SIMULATION", "PROVIDER", "FIELD"}:
        raise ValueError("invalid target_scope")
    if type(policy["rollback_required"]) is not bool or type(policy["anti_downgrade"]) is not bool:
        raise ValueError("invalid release policy booleans")
    if policy["exact_readback_required"] is not True or policy["healthcheck_required"] is not True:
        raise ValueError("release proof cannot be weakened")
    if policy["max_permission_class"] not in RELEASE_PERMISSION_ORDER or policy["max_permission_class"] == "P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE":
        raise ValueError("invalid release permission ceiling")
    if policy["resource_ceiling"] not in RESOURCE_ORDER:
        raise ValueError("invalid release resource ceiling")

    operations = tx["operations"]
    if not isinstance(operations, dict) or set(operations) != set(REQUIRED_OPERATIONS):
        raise ValueError("invalid release operations")
    for op, binding in operations.items():
        if not isinstance(binding, dict):
            raise ValueError(f"invalid {op} operation binding")
        expected = {
            "capability_id", "provider_id", "state", "permission_class",
            "resource_class", "evidence_contract"
        }
        if set(binding) != expected:
            raise ValueError(f"invalid {op} binding fields")
        if binding["state"] not in {"BOUND", "WAITING_BINDING", "TEMP_UNAVAILABLE", "UNSUPPORTED"}:
            raise ValueError(f"invalid {op} state")
        if binding["state"] == "BOUND":
            _text(binding["capability_id"], f"{op} capability", 160)
            _text(binding["provider_id"], f"{op} provider", 160)
            if binding["permission_class"] not in RELEASE_PERMISSION_ORDER or binding["resource_class"] not in RESOURCE_ORDER:
                raise ValueError(f"invalid {op} policy class")
            if not isinstance(binding["evidence_contract"], list) or not binding["evidence_contract"]:
                raise ValueError(f"invalid {op} evidence contract")
        else:
            if binding["capability_id"] is not None:
                _text(binding["capability_id"], f"{op} capability", 160)
            if binding["provider_id"] is not None:
                _text(binding["provider_id"], f"{op} provider", 160)
            if binding["permission_class"] is not None and binding["permission_class"] not in RELEASE_PERMISSION_ORDER:
                raise ValueError(f"invalid {op} permission")
            if binding["resource_class"] is not None and binding["resource_class"] not in RESOURCE_ORDER:
                raise ValueError(f"invalid {op} resource")
            if not isinstance(binding["evidence_contract"], list):
                raise ValueError(f"invalid {op} evidence contract")

    receipts = tx["receipts"]
    if not isinstance(receipts, dict) or set(receipts) - set(REQUIRED_OPERATIONS):
        raise ValueError("invalid receipts")
    for value in receipts.values():
        if value is not None and (not isinstance(value, str) or not value or len(value) > 200):
            raise ValueError("invalid receipt id")

    for field in ("readback", "rollback_readback"):
        rb = tx.get(field)
        if field == "rollback_readback" and rb is None:
            continue
        if not isinstance(rb, dict):
            raise ValueError(f"invalid {field}")
        if set(rb) != {"status", "observed_version", "observed_sequence", "observed_sha256", "health", "observed_at"}:
            raise ValueError(f"invalid {field} fields")
        if rb["status"] not in {"NOT_RUN", "PASS", "FAIL"} or rb["health"] not in {"UNKNOWN", "PASS", "FAIL"}:
            raise ValueError(f"invalid {field} state")
        if rb["observed_sequence"] is not None and (type(rb["observed_sequence"]) is not int or rb["observed_sequence"] < 0):
            raise ValueError(f"invalid {field} sequence")
        if rb["observed_sha256"] is not None and not SHA_RE.fullmatch(str(rb["observed_sha256"]).lower()):
            raise ValueError(f"invalid {field} hash")

    if tx["state"] not in {
        "DISCOVERED", "WAITING_LKG", "WAITING_APPROVAL", "WAITING_CAPABILITY",
        "WAITING_RESOURCE", "VERIFY_READY", "STAGE_READY", "ACTIVATE_READY",
        "HEALTH_PENDING", "COMMIT_READY", "COMMITTED", "ROLLBACK_REQUIRED",
        "ROLLBACK_READY", "ROLLBACK_READBACK_PENDING", "ROLLED_BACK",
        "SUPERSEDED_NO_ROLLBACK", "FAILED_SAFE",
    }:
        raise ValueError("invalid release state")
    out = deepcopy(tx)
    out["candidate"] = candidate
    out["current"] = current
    out["lkg"] = lkg
    return out


class ReleaseController:
    def __init__(self, store: CriticalStore):
        self.store = store

    def _put(self, tx: dict[str, Any], *, owner_id: str) -> dict[str, Any]:
        clean = validate_transaction(tx)
        sid = release_stream_id(clean["project_id"], clean["release_id"])
        current = self.store.get_state(sid)
        rev = int(current["revision"]) if current else 0
        if current and current["payload"] == clean:
            return {"status": "UNCHANGED", "revision": rev, "content_hash": current["content_hash"]}
        fence = self.store.acquire_writer_fence(sid, owner_id)
        try:
            receipt = self.store.commit_transition(
                stream_id=sid,
                expected_revision=rev,
                new_revision=rev + 1,
                fencing_token=fence,
                payload=clean,
                destination="BCP_RELEASE_TRANSACTION",
            )
        except RevisionConflict as exc:
            raise ReleaseRevisionConflict(str(exc)) from exc
        return {
            "status": receipt.status,
            "revision": receipt.revision,
            "content_hash": receipt.content_hash,
            "outbox_message_id": receipt.outbox_message_id,
        }

    def get(self, project_id: str, release_id: str) -> dict[str, Any]:
        state = self.store.get_state(release_stream_id(project_id, release_id))
        if state is None:
            raise ReleaseNotFound(release_id)
        return {
            "transaction": state["payload"],
            "revision": state["revision"],
            "content_hash": state["content_hash"],
            "committed_epoch": state["committed_epoch"],
        }

    def list(self, project_id: str | None = None, *, limit: int = 512) -> list[dict[str, Any]]:
        prefix = RELEASE_PREFIX if project_id is None else f"{RELEASE_PREFIX}{_text(project_id, 'project_id', 128)}/"
        return [
            {
                "transaction": s["payload"],
                "revision": s["revision"],
                "content_hash": s["content_hash"],
                "committed_epoch": s["committed_epoch"],
            }
            for s in self.store.list_states(prefix, limit=limit)
        ]

    def latest_committed(self, project_id: str) -> dict[str, Any] | None:
        committed = [
            item for item in self.list(project_id, limit=2048)
            if item["transaction"]["state"] == "COMMITTED"
        ]
        if not committed:
            return None
        committed.sort(
            key=lambda item: (
                int(item["transaction"]["candidate"]["sequence"]),
                item["transaction"]["release_id"],
            ),
            reverse=True,
        )
        return committed[0]

    def create(
        self,
        *,
        release_id: str,
        project_id: str,
        candidate: dict[str, Any],
        current: dict[str, Any] | None,
        lkg: dict[str, Any] | None,
        migration: dict[str, Any],
        policy: dict[str, Any],
        adapter: dict[str, Any],
        resource_mode: str,
        owner_id: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        now = now or utc_now()
        candidate = _validate_release_ref(candidate)
        current = _validate_release_ref(current) if current is not None else None
        lkg = _validate_release_ref(lkg, lkg=True) if lkg is not None else None
        if str(adapter.get("project_id") or "") != project_id:
            raise ValueError("project adapter does not match release project")
        operations = operation_bindings_from_adapter(adapter)
        if lkg is not None and current is not None and lkg["sequence"] > current["sequence"]:
            raise ValueError("LKG cannot be newer than current release")
        tx = {
            "schema": "bcp.release_transaction/1",
            "release_id": release_id,
            "project_id": project_id,
            "state": "DISCOVERED",
            "candidate": candidate,
            "current": current,
            "lkg": lkg,
            "migration": deepcopy(migration),
            "policy": deepcopy(policy),
            "operations": operations,
            "receipts": {},
            "readback": {
                "status": "NOT_RUN", "observed_version": None, "observed_sequence": None,
                "observed_sha256": None, "health": "UNKNOWN", "observed_at": None,
            },
            "rollback_readback": None,
            "failure": None,
            "created_at": now,
            "updated_at": now,
        }
        validate_transaction(tx)

        if current is not None and policy["anti_downgrade"] and candidate["sequence"] <= current["sequence"]:
            tx["state"] = "SUPERSEDED_NO_ROLLBACK"
            tx["failure"] = {
                "operation": None,
                "code": "RELEASE_LINE_RECONCILIATION_REQUIRED",
                "detail": "candidate sequence is not newer than current; normal activation is forbidden",
            }
        elif policy["rollback_required"] and (
            lkg is None
            or not lkg["proven"]
            or (policy["target_scope"] == "FIELD" and lkg["proof_scope"] != "FIELD")
        ):
            tx["state"] = "WAITING_LKG"
        elif migration["class"] == "IRREVERSIBLE" and not migration["approval_granted"]:
            tx["state"] = "WAITING_APPROVAL"
        else:
            for op in REQUIRED_OPERATIONS:
                if op == "ROLLBACK" and not policy["rollback_required"]:
                    continue
                hold, reason = _operation_hold_reason(tx, op, resource_mode)
                if hold:
                    tx["state"] = hold
                    tx["failure"] = {"operation": op, "code": reason, "detail": None}
                    break
            else:
                tx["state"] = "VERIFY_READY"

        self._put(tx, owner_id=owner_id)
        return tx

    def _load_mutable(self, project_id: str, release_id: str) -> dict[str, Any]:
        return deepcopy(self.get(project_id, release_id)["transaction"])

    @staticmethod
    def _receipt_ok(receipt: Any, tx: dict[str, Any], operation: str) -> str:
        if not isinstance(receipt, dict) or receipt.get("schema") != "bcp.action_receipt/1":
            raise ValueError("invalid action receipt")
        if receipt.get("project_id") != tx["project_id"]:
            raise ReleaseTransitionError("receipt project mismatch")
        binding = tx["operations"][operation]
        if binding["state"] != "BOUND":
            raise ReleaseTransitionError("operation is not bound")
        if receipt.get("capability_id") != binding["capability_id"]:
            raise ReleaseTransitionError("receipt capability mismatch")
        if receipt.get("provider_id") != binding["provider_id"]:
            raise ReleaseTransitionError("receipt provider mismatch")
        proof_scope = str(receipt.get("proof_scope") or "")
        if proof_scope not in SCOPE_ORDER:
            raise ReleaseTransitionError("receipt proof scope missing")
        target_scope = tx["policy"]["target_scope"]
        min_scope = target_scope if operation in {"UPDATE_ACTIVATE", "HEALTHCHECK", "ROLLBACK"} else "REPOSITORY"
        if SCOPE_ORDER[proof_scope] < SCOPE_ORDER[min_scope]:
            raise ReleaseTransitionError(f"{operation} receipt proof scope too weak")
        if target_scope == "FIELD" and operation in {"UPDATE_ACTIVATE", "HEALTHCHECK", "ROLLBACK"}:
            if receipt.get("field_certified") is not True or proof_scope != "FIELD":
                raise ReleaseTransitionError(f"{operation} requires field-certified receipt")

        evidence = receipt.get("evidence")
        if not isinstance(evidence, list):
            raise ReleaseTransitionError("receipt evidence missing")
        passed_kinds = {
            str(item.get("kind"))
            for item in evidence
            if isinstance(item, dict) and item.get("status") in {"PASS", "OBSERVED"}
        }
        missing = set(binding["evidence_contract"]) - passed_kinds
        if missing:
            raise ReleaseTransitionError(
                "receipt evidence contract incomplete: " + ",".join(sorted(missing))
            )
        rid = _text(receipt.get("receipt_id"), "receipt_id", 200)
        return rid

    def record_operation_receipt(
        self,
        project_id: str,
        release_id: str,
        operation: str,
        receipt: dict[str, Any],
        *,
        owner_id: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        now = now or utc_now()
        tx = self._load_mutable(project_id, release_id)
        if operation not in OP_STATE:
            raise ReleaseTransitionError("unsupported release operation")
        if tx["state"] != OP_STATE[operation]:
            raise ReleaseTransitionError(f"{operation} not expected in state {tx['state']}")
        rid = self._receipt_ok(receipt, tx, operation)
        tx["receipts"][operation] = rid
        passed = receipt.get("status") == "SUCCEEDED" and receipt.get("result") == "PASS"

        if not passed:
            tx["failure"] = {
                "operation": operation,
                "code": "ACTION_RECEIPT_FAILED",
                "detail": str((receipt.get("error") or {}).get("code") or receipt.get("result") or "FAIL")[:2000],
            }
            if operation in {"UPDATE_ACTIVATE", "HEALTHCHECK"} and tx["policy"]["rollback_required"] and tx["lkg"]:
                tx["state"] = "ROLLBACK_REQUIRED"
            else:
                tx["state"] = "FAILED_SAFE"
        else:
            tx["failure"] = None
            tx["state"] = {
                "RELEASE_VERIFY": "STAGE_READY",
                "UPDATE_STAGE": "ACTIVATE_READY",
                "UPDATE_ACTIVATE": "HEALTH_PENDING",
                "HEALTHCHECK": "HEALTH_PENDING",
                "ROLLBACK": "ROLLBACK_READBACK_PENDING",
            }[operation]
        tx["updated_at"] = now
        self._put(tx, owner_id=owner_id)
        return tx

    def record_candidate_readback(
        self,
        project_id: str,
        release_id: str,
        *,
        observed_version: str,
        observed_sequence: int,
        observed_sha256: str,
        health: str,
        owner_id: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        now = now or utc_now()
        tx = self._load_mutable(project_id, release_id)
        if tx["state"] != "HEALTH_PENDING":
            raise ReleaseTransitionError("candidate readback not expected")
        if not tx["receipts"].get("UPDATE_ACTIVATE") or not tx["receipts"].get("HEALTHCHECK"):
            raise ReleaseTransitionError("activation and health receipts required before readback")
        candidate = tx["candidate"]
        exact = (
            str(observed_version) == candidate["version"]
            and int(observed_sequence) == candidate["sequence"]
            and str(observed_sha256).lower() == candidate["artifact_sha256"]
            and health == "PASS"
        )
        tx["readback"] = {
            "status": "PASS" if exact else "FAIL",
            "observed_version": str(observed_version),
            "observed_sequence": int(observed_sequence),
            "observed_sha256": str(observed_sha256).lower(),
            "health": health,
            "observed_at": now,
        }
        if exact:
            tx["state"] = "COMMIT_READY"
            tx["failure"] = None
        elif tx["policy"]["rollback_required"] and tx["lkg"]:
            tx["state"] = "ROLLBACK_REQUIRED"
            tx["failure"] = {"operation": "READBACK", "code": "CANDIDATE_READBACK_MISMATCH", "detail": None}
        else:
            tx["state"] = "FAILED_SAFE"
            tx["failure"] = {"operation": "READBACK", "code": "CANDIDATE_READBACK_MISMATCH", "detail": None}
        tx["updated_at"] = now
        self._put(tx, owner_id=owner_id)
        return tx

    def commit(
        self, project_id: str, release_id: str, *, owner_id: str, now: str | None = None
    ) -> dict[str, Any]:
        now = now or utc_now()
        tx = self._load_mutable(project_id, release_id)
        if tx["state"] != "COMMIT_READY" or tx["readback"]["status"] != "PASS":
            raise ReleaseTransitionError("release not ready to commit")
        tx["state"] = "COMMITTED"
        tx["updated_at"] = now
        self._put(tx, owner_id=owner_id)
        return tx

    def prepare_rollback(
        self, project_id: str, release_id: str, *, owner_id: str, resource_mode: str, now: str | None = None
    ) -> dict[str, Any]:
        now = now or utc_now()
        tx = self._load_mutable(project_id, release_id)
        if tx["state"] != "ROLLBACK_REQUIRED":
            raise ReleaseTransitionError("rollback not required")
        lkg = tx["lkg"]
        if not lkg or not lkg["proven"]:
            tx["state"] = "FAILED_SAFE"
            tx["failure"] = {"operation": "ROLLBACK", "code": "NO_PROVEN_LKG", "detail": None}
        else:
            hold, reason = _operation_hold_reason(tx, "ROLLBACK", resource_mode)
            if hold:
                tx["state"] = hold
                tx["failure"] = {"operation": "ROLLBACK", "code": reason, "detail": None}
            else:
                tx["state"] = "ROLLBACK_READY"
        tx["updated_at"] = now
        self._put(tx, owner_id=owner_id)
        return tx

    def record_rollback_readback(
        self,
        project_id: str,
        release_id: str,
        *,
        observed_version: str,
        observed_sequence: int,
        observed_sha256: str,
        health: str,
        owner_id: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        now = now or utc_now()
        tx = self._load_mutable(project_id, release_id)
        if tx["state"] != "ROLLBACK_READBACK_PENDING":
            raise ReleaseTransitionError("rollback readback not expected")
        lkg = tx["lkg"]
        if not lkg:
            raise ReleaseTransitionError("LKG missing")
        exact = (
            str(observed_version) == lkg["version"]
            and int(observed_sequence) == lkg["sequence"]
            and str(observed_sha256).lower() == lkg["artifact_sha256"]
            and health == "PASS"
        )
        tx["rollback_readback"] = {
            "status": "PASS" if exact else "FAIL",
            "observed_version": str(observed_version),
            "observed_sequence": int(observed_sequence),
            "observed_sha256": str(observed_sha256).lower(),
            "health": health,
            "observed_at": now,
        }
        tx["state"] = "ROLLED_BACK" if exact else "FAILED_SAFE"
        if not exact:
            tx["failure"] = {"operation": "ROLLBACK_READBACK", "code": "ROLLBACK_READBACK_MISMATCH", "detail": None}
        tx["updated_at"] = now
        self._put(tx, owner_id=owner_id)
        return tx

    def recover_incomplete(
        self, project_id: str, release_id: str, *, owner_id: str, now: str | None = None
    ) -> dict[str, Any]:
        now = now or utc_now()
        tx = self._load_mutable(project_id, release_id)
        if tx["state"] in TERMINAL_STATES:
            return tx
        latest = self.latest_committed(project_id)
        if latest and latest["transaction"]["release_id"] != release_id:
            latest_seq = int(latest["transaction"]["candidate"]["sequence"])
            if latest_seq >= int(tx["candidate"]["sequence"]):
                tx["state"] = "SUPERSEDED_NO_ROLLBACK"
                tx["failure"] = {
                    "operation": None,
                    "code": "SUPERSEDED_NO_ROLLBACK",
                    "detail": f"newer/equal committed sequence {latest_seq} must not be overwritten by stale recovery",
                }
                tx["updated_at"] = now
                self._put(tx, owner_id=owner_id)
                return tx

        if tx["state"] in {"HEALTH_PENDING", "COMMIT_READY"}:
            if tx["policy"]["rollback_required"] and tx["lkg"]:
                tx["state"] = "ROLLBACK_REQUIRED"
                tx["failure"] = {"operation": "RECOVERY", "code": "INTERRUPTED_AFTER_ACTIVATION", "detail": None}
            else:
                tx["state"] = "FAILED_SAFE"
                tx["failure"] = {"operation": "RECOVERY", "code": "INTERRUPTED_WITHOUT_LKG", "detail": None}
            tx["updated_at"] = now
            self._put(tx, owner_id=owner_id)
        return tx


__all__ = [
    "ReleaseController", "ReleaseControllerError", "ReleaseNotFound",
    "ReleaseRevisionConflict", "ReleaseTransitionError", "validate_transaction",
    "operation_bindings_from_adapter", "release_stream_id", "TERMINAL_STATES",
]
