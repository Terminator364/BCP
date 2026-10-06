from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"
sys.path.insert(0, str(WINDOWS))

from execution_fabric.critical_store import CriticalStore  # noqa: E402
from execution_fabric.desired_state_registry import deep_drift  # noqa: E402
from execution_fabric.incident_recipe import IncidentRegistry, RecipeRegistry, ReconcilePlanner  # noqa: E402


def desired() -> dict:
    return {
        "schema": "bcp.desired_state_resource/1",
        "api_version": "bcp/v1",
        "kind": "DemoResource",
        "metadata": {
            "resource_id": "demo-resource",
            "project_id": "BCP_CORE",
            "generation": 1,
            "created_at": "2026-10-06T14:00:00Z",
            "updated_at": None,
            "owner": "BCP_POLICY",
        },
        "spec": {
            "desired": {"enabled": True, "version": "1"},
            "reconcile_policy": {
                "mode": "AUTO_SAFE",
                "max_permission_class": "P1_SAFE_WRITE",
                "resource_ceiling": "R1_LIGHT",
                "repair_backoff_seconds": 30,
                "max_attempts_per_incident": 3,
            },
            "evidence_contract": ["PROCESS_HEALTH"],
            "dependencies": [],
        },
        "status": {
            "observed_generation": 0,
            "phase": "UNKNOWN",
            "last_observed_at": None,
            "last_reconciled_at": None,
            "conditions": [],
        },
    }


def receipt(receipt_id: str = "receipt-convergence-0001") -> dict:
    return {
        "schema": "bcp.action_receipt/1",
        "receipt_id": receipt_id,
        "mission_id": "mission-convergence",
        "project_id": "BCP_CORE",
        "action_id": "repair-demo",
        "job_id": "job-convergence",
        "step_id": "repair",
        "capability_id": "demo.repair",
        "provider_id": "BCP_NATIVE_PC",
        "node_id": "SIM",
        "idempotency_key": "convergence-receipt-idem",
        "status": "SUCCEEDED",
        "result": "PASS",
        "proof_scope": "SIMULATION",
        "field_certified": False,
        "durability": "DURABLE_LOCAL",
        "committed_revision": 1,
        "fencing_token": 1,
        "content_hash": None,
        "predecessor_hash": None,
        "output_hash": None,
        "source_revision": "PHASE4_CONVERGENCE",
        "environment_fingerprint": "simulation",
        "outbox_message_id": None,
        "idempotent_replay": False,
        "evidence": [{
            "evidence_id": "repair-health",
            "kind": "PROCESS_HEALTH",
            "status": "PASS",
            "value": {"healthy": True},
            "sha256": None,
            "source": "convergence-test",
            "observed_at": "2026-10-06T14:01:00Z",
        }],
        "readback": {
            "status": "PASS",
            "summary": "action completed",
            "observed_revision": "sim",
        },
        "side_effects": [],
        "error": None,
        "created_at": "2026-10-06T14:01:00Z",
        "committed_at": "2026-10-06T14:01:01Z",
    }


class Phase4ConvergenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CriticalStore(pathlib.Path(self.tmp.name) / "bcp.sqlite3")
        self.incidents = IncidentRegistry(self.store)
        self.recipes = RecipeRegistry(self.store)
        self.planner = ReconcilePlanner(self.incidents, self.recipes)

    def tearDown(self):
        self.tmp.cleanup()

    def test_subset_drift_is_deterministic_and_tolerates_extra_observed_fields(self):
        self.assertEqual(
            deep_drift({"enabled": True}, {"enabled": True, "extra": "ignored"}),
            [],
        )
        drift = deep_drift(
            {"enabled": True, "version": "1"},
            {"enabled": False, "extra": "ignored"},
        )
        self.assertEqual(
            [item["path"] for item in drift],
            ["$/enabled", "$/version"],
        )

    def test_friction_is_durable_and_deduplicated(self):
        a = self.incidents.record_friction(
            project_id="BCP_CORE",
            category="REPEATED_MANUAL_QR",
            detail="User had to repeat pairing mechanics",
            source="CHATGPT",
            avoidable=True,
            user_action_required=True,
            observed_at="2026-10-06T14:02:00Z",
            owner_id="friction",
        )
        b = self.incidents.record_friction(
            project_id="BCP_CORE",
            category="REPEATED_MANUAL_QR",
            detail="User had to repeat pairing mechanics",
            source="CHATGPT",
            avoidable=True,
            user_action_required=True,
            observed_at="2026-10-06T14:03:00Z",
            owner_id="friction",
        )
        self.assertEqual(a["payload"]["signature"], b["payload"]["signature"])
        self.assertEqual(b["payload"]["observation"]["occurrence_count"], 2)
        self.assertEqual(
            b["payload"]["observation"]["incident_class"],
            "FRICTION",
        )

    def test_provider_boolean_cannot_override_observed_drift(self):
        with self.assertRaisesRegex(ValueError, "observation fields"):
            self.planner.plan(
                desired(),
                {
                    "matches_desired": True,
                    "observed": {"enabled": False, "version": "1"},
                },
                capability_states={},
                environment_fingerprint="sim",
                resource_mode="GREEN",
                observed_at="2026-10-06T14:04:00Z",
                owner_id="observer",
            )

    def test_action_pass_does_not_recover_until_fresh_conforming_observation(self):
        symptoms = {"kind": "DESIRED_STATE_DRIFT", "drift_paths": ["$/enabled"]}
        incident = self.incidents.observe(
            project_id="BCP_CORE",
            resource_id="demo-resource",
            symptoms=symptoms,
            environment_fingerprint="sim",
            desired_generation=1,
            observed_at="2026-10-06T14:04:00Z",
            owner_id="observer",
        )
        sig = incident["payload"]["signature"]
        self.incidents.set_state(
            "BCP_CORE",
            "demo-resource",
            sig,
            status="RECONCILING",
            owner_id="dispatcher",
            matched_recipe_id="recipe-demo",
            increment_attempt=True,
        )

        self.incidents.receipts.put(receipt(), owner_id="receipt-writer")
        after_action = self.incidents.record_action_receipt(
            "BCP_CORE",
            "demo-resource",
            sig,
            receipt_id="receipt-convergence-0001",
            expected_capability_id="demo.repair",
            owner_id="dispatcher",
        )
        self.assertEqual(after_action["payload"]["status"], "RECONCILING")

        result = self.planner.plan(
            desired(),
            {"observed": {"enabled": True, "version": "1", "extra": "ok"}},
            capability_states={},
            environment_fingerprint="sim",
            resource_mode="GREEN",
            observed_at="2026-10-06T14:05:00Z",
            owner_id="observer",
        )
        self.assertEqual(result["decision"], "IN_SYNC")
        resolved = self.incidents.get("BCP_CORE", "demo-resource", sig)
        self.assertEqual(resolved["payload"]["status"], "RESOLVED")


if __name__ == "__main__":
    unittest.main()
