from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"
sys.path.insert(0, str(WINDOWS))

from execution_fabric.critical_store import CriticalStore  # noqa: E402
from execution_fabric.desired_state_registry import (  # noqa: E402
    DesiredGenerationConflict,
    DesiredStateRegistry,
)


def desired(generation: int = 1, *, mode: str = "AUTO_SAFE", phase: str = "UNKNOWN") -> dict:
    return {
        "schema": "bcp.desired_state_resource/1",
        "api_version": "bcp/v1",
        "kind": "BcpRuntime",
        "metadata": {
            "resource_id": "bcp-runtime",
            "project_id": "BCP_CORE",
            "generation": generation,
            "created_at": "2026-10-05T21:30:00Z",
            "updated_at": None,
            "owner": "BCP_POLICY",
        },
        "spec": {
            "desired": {
                "healthy": True,
                "primary_startup": "HKCU_RUN",
                "single_resident_process": True,
            },
            "reconcile_policy": {
                "mode": mode,
                "max_permission_class": "P1_SAFE_WRITE",
                "resource_ceiling": "R1_LIGHT",
                "repair_backoff_seconds": 30,
                "max_attempts_per_incident": 3,
            },
            "evidence_contract": ["PROCESS_HEALTH", "FILE_READBACK"],
            "dependencies": [],
        },
        "status": {
            "observed_generation": 0,
            "phase": phase,
            "last_observed_at": None,
            "last_reconciled_at": None,
            "conditions": [],
        },
    }


class DesiredStateRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CriticalStore(pathlib.Path(self.tmp.name) / "bcp.sqlite3")
        self.registry = DesiredStateRegistry(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_generation_must_be_one(self):
        with self.assertRaises(DesiredGenerationConflict):
            self.registry.put_spec(desired(2), owner_id="test")

    def test_first_generation_cannot_self_certify_in_sync(self):
        bad = desired(1, phase="IN_SYNC")
        bad["status"]["observed_generation"] = 1
        with self.assertRaises(DesiredGenerationConflict):
            self.registry.put_spec(bad, owner_id="writer")

    def test_in_sync_requires_observation_of_current_generation(self):
        bad = desired(1, phase="IN_SYNC")
        bad["status"]["observed_generation"] = 0
        with self.assertRaises(ValueError):
            from execution_fabric.desired_state_registry import validate_resource
            validate_resource(bad)

    def test_new_generation_cannot_self_observe(self):
        self.registry.put_spec(desired(1), owner_id="a")
        bad = desired(2)
        bad["status"]["observed_generation"] = 2
        with self.assertRaises(DesiredGenerationConflict):
            self.registry.put_spec(bad, owner_id="b")

    def test_schema_drift_and_bool_generation_fail_closed(self):
        from execution_fabric.desired_state_registry import validate_resource

        bad = desired(1)
        bad["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "top-level"):
            validate_resource(bad)

        bad = desired(1)
        bad["spec"]["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "spec fields"):
            validate_resource(bad)

        bad = desired(1)
        bad["spec"]["reconcile_policy"]["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "reconcile_policy fields"):
            validate_resource(bad)

        bad = desired(1)
        bad["status"]["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "status fields"):
            validate_resource(bad)

        bad = desired(1)
        bad["metadata"]["generation"] = True
        with self.assertRaisesRegex(ValueError, "generation"):
            validate_resource(bad)

    def test_create_and_exact_same_generation_is_unchanged(self):
        first = self.registry.put_spec(desired(1), owner_id="a")
        second = self.registry.put_spec(desired(1), owner_id="b")
        self.assertEqual(first["status"], "DURABLE_LOCAL")
        self.assertEqual(second["status"], "UNCHANGED")
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(self.registry.get("BCP_CORE", "bcp-runtime")["revision"], 1)

    def test_same_generation_cannot_mutate_desired_spec(self):
        self.registry.put_spec(desired(1), owner_id="a")
        changed = desired(1)
        changed["spec"]["desired"]["healthy"] = False
        with self.assertRaisesRegex(DesiredGenerationConflict, "same generation"):
            self.registry.put_spec(changed, owner_id="b")

    def test_generation_must_advance_exactly_one(self):
        self.registry.put_spec(desired(1), owner_id="a")
        with self.assertRaisesRegex(DesiredGenerationConflict, "exactly by one"):
            self.registry.put_spec(desired(3), owner_id="b")
        receipt = self.registry.put_spec(desired(2), owner_id="b")
        self.assertEqual(receipt["generation"], 2)

    def test_status_update_preserves_desired_spec_and_generation(self):
        self.registry.put_spec(desired(1), owner_id="a")
        before = self.registry.get("BCP_CORE", "bcp-runtime")["resource"]["spec"]
        receipt = self.registry.update_status(
            "BCP_CORE",
            "bcp-runtime",
            {
                "observed_generation": 1,
                "phase": "IN_SYNC",
                "last_observed_at": "2026-10-05T21:31:00Z",
                "last_reconciled_at": None,
                "conditions": [{"type":"Healthy","status":"TRUE","reason":"readback","evidence_ref":"rcpt-1"}],
            },
            expected_generation=1,
            owner_id="observer",
            updated_at="2026-10-05T21:31:00Z",
        )
        self.assertEqual(receipt["generation"], 1)
        after = self.registry.get("BCP_CORE", "bcp-runtime")
        self.assertEqual(after["resource"]["spec"], before)
        self.assertEqual(after["resource"]["status"]["phase"], "IN_SYNC")

    def test_stale_status_generation_fails_closed(self):
        self.registry.put_spec(desired(1), owner_id="a")
        with self.assertRaises(DesiredGenerationConflict):
            self.registry.update_status(
                "BCP_CORE", "bcp-runtime",
                {"observed_generation":0,"phase":"UNKNOWN","conditions":[]},
                expected_generation=0,
                owner_id="stale",
            )

    def test_status_cannot_observe_future_generation(self):
        self.registry.put_spec(desired(1), owner_id="a")
        with self.assertRaises(ValueError):
            self.registry.update_status(
                "BCP_CORE", "bcp-runtime",
                {"observed_generation":2,"phase":"IN_SYNC","conditions":[]},
                expected_generation=1,
                owner_id="bad-observer",
            )

    def test_desired_state_uses_transactional_outbox(self):
        receipt = self.registry.put_spec(desired(1), owner_id="a")
        due = self.store.due_outbox(limit=10)
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["message_id"], receipt["outbox_message_id"])
        self.assertEqual(due[0]["destination"], "BCP_DESIRED_STATE")


if __name__ == "__main__":
    unittest.main()
