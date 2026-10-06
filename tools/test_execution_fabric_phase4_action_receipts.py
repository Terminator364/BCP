from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"
sys.path.insert(0, str(WINDOWS))

from execution_fabric.critical_store import CriticalStore  # noqa: E402
from execution_fabric.action_receipt_registry import (  # noqa: E402
    ActionReceiptRegistry,
    ActionReceiptCollision,
    ActionReceiptValidationError,
)


def receipt(
    receipt_id: str = "receipt-success-1",
    *,
    capability_id: str = "bcp.runtime.restart",
    project_id: str = "BCP_CORE",
    field: bool = False,
    evidence_status: str = "PASS",
) -> dict:
    return {
        "schema": "bcp.action_receipt/1",
        "receipt_id": receipt_id,
        "mission_id": "mission-phase4",
        "project_id": project_id,
        "action_id": "restart-runtime",
        "job_id": "job-phase4",
        "step_id": "restart",
        "capability_id": capability_id,
        "provider_id": "BCP_NATIVE_PC",
        "node_id": "PC",
        "idempotency_key": "phase4-receipt-idempotency",
        "status": "SUCCEEDED",
        "result": "PASS",
        "proof_scope": "FIELD" if field else "SIMULATION",
        "field_certified": field,
        "durability": "DURABLE_LOCAL",
        "committed_revision": 1,
        "fencing_token": 1,
        "content_hash": None,
        "predecessor_hash": None,
        "output_hash": None,
        "source_revision": "PHASE4_TEST",
        "environment_fingerprint": "windows-11-4gb",
        "outbox_message_id": None,
        "idempotent_replay": False,
        "evidence": [
            {
                "evidence_id": "health-proof",
                "kind": "PROCESS_HEALTH",
                "status": evidence_status,
                "value": {"healthy": evidence_status == "PASS"},
                "sha256": None,
                "source": "phase4-test",
                "observed_at": "2026-10-05T21:31:00Z",
            }
        ],
        "readback": {
            "status": "PASS" if evidence_status == "PASS" else "FAIL",
            "summary": "test readback",
            "observed_revision": "phase4",
        },
        "side_effects": [],
        "error": None,
        "created_at": "2026-10-05T21:31:00Z",
        "committed_at": "2026-10-05T21:31:01Z",
    }


class ActionReceiptRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CriticalStore(pathlib.Path(self.tmp.name) / "bcp.sqlite3")
        self.receipts = ActionReceiptRegistry(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_receipt_is_immutable_and_idempotent(self):
        first = self.receipts.put(receipt(), owner_id="writer-a")
        second = self.receipts.put(receipt(), owner_id="writer-b")
        self.assertEqual(first["revision"], 1)
        self.assertEqual(second["revision"], 1)
        changed = receipt()
        changed["action_id"] = "different"
        with self.assertRaises(ActionReceiptCollision):
            self.receipts.put(changed, owner_id="writer-c")

    def test_success_reference_must_be_durable_pass(self):
        self.receipts.put(receipt(), owner_id="writer")
        state = self.receipts.require_success(
            "receipt-success-1",
            project_scopes=["BCP_CORE"],
        )
        self.assertEqual(state["payload"]["status"], "SUCCEEDED")
        self.assertEqual(state["payload"]["result"], "PASS")

    def test_project_scope_is_enforced(self):
        self.receipts.put(receipt(project_id="OTHER"), owner_id="writer")
        with self.assertRaises(ActionReceiptValidationError):
            self.receipts.require_success(
                "receipt-success-1",
                project_scopes=["BCP_CORE"],
            )

    def test_field_requirement_is_real_not_label_only(self):
        self.receipts.put(receipt(), owner_id="writer")
        with self.assertRaises(ActionReceiptValidationError):
            self.receipts.require_success("receipt-success-1", field=True)

        self.receipts.put(receipt("receipt-field-1", field=True), owner_id="writer")
        state = self.receipts.require_success("receipt-field-1", field=True)
        self.assertTrue(state["payload"]["field_certified"])
        self.assertEqual(state["payload"]["proof_scope"], "FIELD")

    def test_failed_evidence_cannot_be_success_proof(self):
        bad = receipt(evidence_status="FAIL")
        self.receipts.put(bad, owner_id="writer")
        with self.assertRaises(ActionReceiptValidationError):
            self.receipts.require_success("receipt-success-1")

    def test_field_certified_requires_field_scope(self):
        bad = receipt()
        bad["field_certified"] = True
        with self.assertRaises(ActionReceiptValidationError):
            self.receipts.put(bad, owner_id="writer")


if __name__ == "__main__":
    unittest.main()
