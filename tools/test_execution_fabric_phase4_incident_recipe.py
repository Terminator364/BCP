from __future__ import annotations

import copy
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"
sys.path.insert(0, str(WINDOWS))

from execution_fabric.critical_store import CriticalStore  # noqa: E402
from execution_fabric.incident_recipe import (  # noqa: E402
    FrictionRegistry,
    IncidentRegistry,
    RecipeRegistry,
    RecipeValidationError,
    ReconcilePlanner,
    causal_signature,
)
from execution_fabric.desired_state_registry import deep_drift, validate_resource  # noqa: E402


DRIFT_OBSERVED = {"healthy": False, "port": 8765}
DRIFT_SYMPTOMS = {
    "drift_paths": ["$/healthy"],
    "drift_reasons": ["VALUE_MISMATCH"],
}


def desired(*, generation=1, mode="AUTO_SAFE", permission="P1_SAFE_WRITE", resource="R1_LIGHT", attempts=3) -> dict:
    obj = {
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
            "desired": {"healthy": True, "port": 8765},
            "reconcile_policy": {
                "mode": mode,
                "max_permission_class": permission,
                "resource_ceiling": resource,
                "repair_backoff_seconds": 30,
                "max_attempts_per_incident": attempts,
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
    validate_resource(obj)
    return obj


def candidate(recipe_id="recipe-bcp-runtime-restart", *, perm="P1_SAFE_WRITE", resource="R1_LIGHT", field_required=False):
    sig = causal_signature("BCP_CORE", "bcp-runtime", DRIFT_SYMPTOMS)
    return {
        "schema": "bcp.repair_recipe/1",
        "recipe_id": recipe_id,
        "signature": sig,
        "status": "CANDIDATE",
        "project_scopes": ["BCP_CORE"],
        "max_permission_class": perm,
        "max_resource_class": resource,
        "steps": [
            {
                "step_id": "restart",
                "capability_id": "bcp.runtime.restart",
                "permission_class": perm,
                "resource_class": resource,
                "input_template": {"component": "bcp-core"},
                "evidence_contract": ["PROCESS_HEALTH", "FILE_READBACK"],
                "optional": False,
            }
        ],
        "validation": {
            "successful_receipt_refs": [],
            "regression_refs": [],
            "field_evidence_required": field_required,
            "field_evidence_refs": [],
        },
        "created_at": "2026-10-05T21:30:00Z",
        "updated_at": "2026-10-05T21:30:00Z",
        "promoted_at": None,
        "notes": [],
    }


def action_receipt(
    receipt_id: str,
    *,
    capability_id: str = "bcp.runtime.restart",
    field: bool = False,
    project_id: str = "BCP_CORE",
) -> dict:
    return {
        "schema": "bcp.action_receipt/1",
        "receipt_id": receipt_id,
        "mission_id": "mission-phase4",
        "project_id": project_id,
        "action_id": "repair-step",
        "job_id": "job-phase4",
        "step_id": "restart",
        "capability_id": capability_id,
        "provider_id": "BCP_NATIVE_PC",
        "node_id": "PC",
        "idempotency_key": "phase4-recipe-proof-" + receipt_id,
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
        "evidence": [{
            "evidence_id": "repair-proof",
            "kind": "PROCESS_HEALTH",
            "status": "PASS",
            "value": {"healthy": True},
            "sha256": None,
            "source": "phase4-test",
            "observed_at": "2026-10-05T21:31:00Z",
        }],
        "readback": {
            "status": "PASS",
            "summary": "repair verified",
            "observed_revision": "phase4",
        },
        "side_effects": [],
        "error": None,
        "created_at": "2026-10-05T21:31:00Z",
        "committed_at": "2026-10-05T21:31:01Z",
    }


class IncidentRecipeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CriticalStore(pathlib.Path(self.tmp.name) / "bcp.sqlite3")
        self.incidents = IncidentRegistry(self.store)
        self.recipes = RecipeRegistry(self.store)
        self.planner = ReconcilePlanner(self.incidents, self.recipes)
        self.frictions = FrictionRegistry(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def observation(self, observed=None):
        return {
            "observed": copy.deepcopy(DRIFT_OBSERVED if observed is None else observed),
            "evidence_refs": [],
        }

    def promote(self, rec=None, *, field_refs=None):
        rec = rec or candidate()
        self.recipes.register_candidate(rec, owner_id="author")
        self.recipes.receipts.put(
            action_receipt(
                "receipt-success-1",
                capability_id=rec["steps"][0]["capability_id"],
            ),
            owner_id="receipt-writer",
        )
        for ref in field_refs or []:
            self.recipes.receipts.put(
                action_receipt(
                    ref,
                    capability_id=rec["steps"][0]["capability_id"],
                    field=True,
                ),
                owner_id="field-receipt-writer",
            )
        return self.recipes.promote(
            rec["recipe_id"],
            owner_id="validator",
            successful_receipt_refs=["receipt-success-1"],
            regression_refs=["tests/test_bcp_runtime_restart.py"],
            promoted_at="2026-10-05T21:31:00Z",
            field_evidence_refs=field_refs,
        )

    def plan(
        self,
        ds=None,
        *,
        mode="GREEN",
        at="2026-10-05T21:32:00Z",
        capabilities=None,
        observed=None,
    ):
        return self.planner.plan(
            ds or desired(),
            self.observation(observed),
            capability_states=(
                {"bcp.runtime.restart": {"state": "AVAILABLE"}}
                if capabilities is None else capabilities
            ),
            environment_fingerprint="windows-11-4gb",
            resource_mode=mode,
            observed_at=at,
            owner_id="planner",
        )

    def test_causal_signature_is_stable_and_context_bound(self):
        a = causal_signature("BCP_CORE", "bcp-runtime", DRIFT_SYMPTOMS)
        b = causal_signature("BCP_CORE", "bcp-runtime", dict(DRIFT_SYMPTOMS))
        c = causal_signature("OTHER", "bcp-runtime", DRIFT_SYMPTOMS)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_bcp_computes_drift_and_ignores_extra_observed_fields(self):
        self.assertEqual(
            deep_drift({"healthy": True}, {"healthy": True, "extra": "ok"}),
            [],
        )
        self.assertEqual(
            deep_drift({"healthy": True}, {"healthy": False}),
            [{"path": "$/healthy", "reason": "VALUE_MISMATCH"}],
        )

    def test_provider_cannot_claim_matches_desired(self):
        with self.assertRaisesRegex(ValueError, "observation fields"):
            self.planner.plan(
                desired(),
                {"matches_desired": True, "observed": {"healthy": False, "port": 8765}},
                capability_states={},
                environment_fingerprint="windows-11-4gb",
                resource_mode="GREEN",
                observed_at="2026-10-05T21:32:00Z",
                owner_id="planner",
            )

    def test_candidate_recipe_never_auto_executes(self):
        self.recipes.register_candidate(candidate(), owner_id="author")
        plan = self.plan()
        self.assertEqual(plan["decision"], "NEEDS_REASONING")
        self.assertEqual(plan["reason"], "NO_VALIDATED_RECIPE")
        self.assertEqual(plan["steps"], [])

    def test_recipe_cannot_smuggle_command_mechanics(self):
        rec = candidate()
        rec["steps"][0]["input_template"] = {"command": "powershell.exe -c whoami"}
        with self.assertRaises(RecipeValidationError):
            self.recipes.register_candidate(rec, owner_id="author")

    def test_promotion_requires_success_receipt_and_regression(self):
        rec = candidate()
        self.recipes.register_candidate(rec, owner_id="author")
        with self.assertRaises(RecipeValidationError):
            self.recipes.promote(
                rec["recipe_id"],
                owner_id="validator",
                successful_receipt_refs=[],
                regression_refs=[],
                promoted_at="2026-10-05T21:31:00Z",
            )

    def test_p3_recipe_must_require_field_evidence(self):
        rec = candidate(perm="P3_BOUNDED_SYSTEM_CHANGE", field_required=False)
        with self.assertRaisesRegex(RecipeValidationError, "P3 recipe"):
            self.recipes.register_candidate(rec, owner_id="author")

    def test_field_required_recipe_needs_field_evidence(self):
        rec = candidate(field_required=True)
        self.recipes.register_candidate(rec, owner_id="author")
        self.recipes.receipts.put(action_receipt("receipt-success-1"), owner_id="receipt-writer")
        with self.assertRaises(RecipeValidationError):
            self.recipes.promote(
                rec["recipe_id"],
                owner_id="validator",
                successful_receipt_refs=["receipt-success-1"],
                regression_refs=["regression-1"],
                promoted_at="2026-10-05T21:31:00Z",
            )
        self.recipes.receipts.put(
            action_receipt("field-receipt-1", field=True),
            owner_id="field-receipt-writer",
        )
        promoted = self.recipes.promote(
            rec["recipe_id"],
            owner_id="validator",
            successful_receipt_refs=["receipt-success-1"],
            regression_refs=["regression-1"],
            promoted_at="2026-10-05T21:31:00Z",
            field_evidence_refs=["field-receipt-1"],
        )
        self.assertEqual(promoted["payload"]["status"], "VALIDATED")

    def test_invented_receipt_reference_cannot_promote(self):
        rec = candidate()
        self.recipes.register_candidate(rec, owner_id="author")
        with self.assertRaises(RecipeValidationError):
            self.recipes.promote(
                rec["recipe_id"],
                owner_id="validator",
                successful_receipt_refs=["receipt-does-not-exist"],
                regression_refs=["regression-1"],
                promoted_at="2026-10-05T21:31:00Z",
            )

    def test_unrelated_capability_receipt_cannot_promote(self):
        rec = candidate()
        self.recipes.register_candidate(rec, owner_id="author")
        self.recipes.receipts.put(
            action_receipt("receipt-success-1", capability_id="other.capability"),
            owner_id="receipt-writer",
        )
        with self.assertRaises(RecipeValidationError):
            self.recipes.promote(
                rec["recipe_id"],
                owner_id="validator",
                successful_receipt_refs=["receipt-success-1"],
                regression_refs=["regression-1"],
                promoted_at="2026-10-05T21:31:00Z",
            )

    def test_validated_recipe_cannot_be_overwritten_by_candidate(self):
        self.promote()
        changed = candidate()
        changed["notes"] = ["attempted downgrade"]
        with self.assertRaises(RecipeValidationError):
            self.recipes.register_candidate(changed, owner_id="author-2")

    def test_validated_recipe_produces_only_typed_plan(self):
        self.promote()
        plan = self.plan()
        self.assertEqual(plan["decision"], "EXECUTE_TYPED_PLAN")
        self.assertEqual(plan["recipe_id"], "recipe-bcp-runtime-restart")
        self.assertEqual(plan["steps"][0]["capability_id"], "bcp.runtime.restart")
        self.assertNotIn("command", plan["steps"][0])
        self.assertNotIn("argv", plan["steps"][0])
        self.assertFalse(plan["field_certified"])

    def test_observe_only_never_executes_validated_recipe(self):
        self.promote()
        plan = self.plan(desired(mode="OBSERVE_ONLY"))
        self.assertEqual(plan["decision"], "OBSERVE_ONLY_DRIFT")
        self.assertEqual(plan["steps"], [])

    def test_permission_ceiling_blocks_recipe(self):
        rec = candidate(perm="P2_PROJECT_MUTATION")
        self.promote(rec)
        plan = self.plan(desired(mode="AUTO_PROJECT", permission="P1_SAFE_WRITE", resource="R1_LIGHT"))
        self.assertEqual(plan["decision"], "POLICY_BLOCKED")
        self.assertIn("PERMISSION", plan["reason"])

    def test_resource_ceiling_blocks_recipe(self):
        rec = candidate(resource="R2_MEDIUM")
        self.promote(rec)
        plan = self.plan(desired(mode="AUTO_PROJECT", permission="P2_PROJECT_MUTATION", resource="R1_LIGHT"))
        self.assertEqual(plan["decision"], "POLICY_BLOCKED")
        self.assertIn("RESOURCE", plan["reason"])

    def test_unavailable_capability_defers_without_execution(self):
        self.promote()
        plan = self.plan(capabilities={"bcp.runtime.restart": {"state": "TEMP_UNAVAILABLE"}})
        self.assertEqual(plan["decision"], "WAITING_CAPABILITY")
        self.assertEqual(plan["steps"], [])

    def test_current_resource_pressure_defers_without_execution(self):
        rec = candidate(resource="R2_MEDIUM", perm="P1_SAFE_WRITE")
        self.promote(rec)
        plan = self.plan(
            desired(mode="AUTO_PROJECT", permission="P2_PROJECT_MUTATION", resource="R2_MEDIUM"),
            mode="AMBER",
        )
        self.assertEqual(plan["decision"], "WAITING_RESOURCE")
        self.assertEqual(plan["steps"], [])

    def test_backoff_blocks_repeated_attempt(self):
        self.promote()
        first = self.plan(at="2026-10-05T21:32:00Z")
        sig = causal_signature("BCP_CORE", "bcp-runtime", DRIFT_SYMPTOMS)
        self.incidents.set_state(
            "BCP_CORE", "bcp-runtime", sig,
            status="RECONCILING", owner_id="dispatcher",
            matched_recipe_id=first["recipe_id"], increment_attempt=True,
        )
        self.incidents.mark_attempt_failed(
            "BCP_CORE", "bcp-runtime", sig,
            owner_id="dispatcher", now="2026-10-05T21:32:05Z",
            backoff_seconds=30, max_attempts=3,
            error={"class":"HealthCheckFailed"}, receipt_ref="receipt-fail-1",
        )
        plan = self.plan(at="2026-10-05T21:32:20Z")
        self.assertEqual(plan["decision"], "WAITING_BACKOFF")

    def test_max_attempts_fails_safe(self):
        self.promote()
        self.plan()
        sig = causal_signature("BCP_CORE", "bcp-runtime", DRIFT_SYMPTOMS)
        for _ in range(2):
            self.incidents.set_state(
                "BCP_CORE", "bcp-runtime", sig,
                status="RECONCILING", owner_id="dispatcher",
                matched_recipe_id="recipe-bcp-runtime-restart", increment_attempt=True,
            )
        plan = self.plan(desired(attempts=2), at="2026-10-05T21:40:00Z")
        self.assertEqual(plan["decision"], "FAILED_SAFE")
        self.assertEqual(plan["reason"], "MAX_ATTEMPTS_REACHED")

    def test_new_desired_generation_resets_old_incident_attempt_episode(self):
        self.promote()
        first = self.plan(at="2026-10-05T21:32:00Z")
        sig = causal_signature("BCP_CORE", "bcp-runtime", DRIFT_SYMPTOMS)
        self.incidents.set_state(
            "BCP_CORE", "bcp-runtime", sig,
            status="RECONCILING", owner_id="dispatcher",
            matched_recipe_id=first["recipe_id"], increment_attempt=True,
        )
        self.incidents.mark_attempt_failed(
            "BCP_CORE", "bcp-runtime", sig,
            owner_id="dispatcher", now="2026-10-05T21:32:05Z",
            backoff_seconds=300, max_attempts=3,
            error={"class":"HealthCheckFailed"}, receipt_ref="receipt-fail-old-gen",
        )
        plan = self.plan(ds=desired(generation=2), at="2026-10-05T21:32:20Z")
        self.assertEqual(plan["decision"], "EXECUTE_TYPED_PLAN")
        incident = self.incidents.get("BCP_CORE", "bcp-runtime", sig)["payload"]
        self.assertEqual(incident["desired_generation"], 2)
        self.assertEqual(incident["attempts"], 0)
        self.assertIsNone(incident["next_retry_at"])
        self.assertEqual(incident["receipt_refs"], [])

    def test_action_pass_alone_does_not_resolve_incident(self):
        self.promote()
        plan = self.plan()
        sig = causal_signature("BCP_CORE", "bcp-runtime", DRIFT_SYMPTOMS)
        before = self.incidents.get("BCP_CORE", "bcp-runtime", sig)["payload"]
        self.assertEqual(before["status"], "OPEN")

        self.recipes.receipts.put(
            action_receipt("receipt-after-plan"),
            owner_id="receipt-writer",
        )
        still_open = self.incidents.get("BCP_CORE", "bcp-runtime", sig)["payload"]
        self.assertEqual(still_open["status"], "OPEN")

        in_sync = self.plan(observed={"healthy": True, "port": 8765, "extra": "ok"})
        self.assertEqual(in_sync["decision"], "IN_SYNC")
        after = self.incidents.get("BCP_CORE", "bcp-runtime", sig)["payload"]
        self.assertEqual(after["status"], "RESOLVED")

    def test_friction_is_durable_and_deduplicated(self):
        a = self.frictions.record(
            project_id="BCP_CORE",
            category="REPEATED_MANUAL_QR",
            detail="User had to repeat pairing mechanics",
            source="CHATGPT",
            avoidable=True,
            user_action_required=True,
            observed_at="2026-10-05T21:50:00Z",
            owner_id="friction",
        )
        b = self.frictions.record(
            project_id="BCP_CORE",
            category="REPEATED_MANUAL_QR",
            detail="User had to repeat pairing mechanics",
            source="CHATGPT",
            avoidable=True,
            user_action_required=True,
            observed_at="2026-10-05T21:51:00Z",
            owner_id="friction",
        )
        self.assertEqual(a["stream_id"], b["stream_id"])
        self.assertEqual(b["payload"]["occurrence_count"], 2)
        self.assertFalse(b["payload"]["field_certified"])
        self.assertEqual(len(self.frictions.list("BCP_CORE")), 1)

    def test_ambiguous_validated_recipes_fail_safe(self):
        a = candidate("recipe-bcp-runtime-a")
        b = candidate("recipe-bcp-runtime-b")
        self.promote(a)
        self.promote(b)
        plan = self.plan()
        self.assertEqual(plan["decision"], "FAILED_SAFE")
        self.assertEqual(plan["reason"], "MULTIPLE_VALIDATED_RECIPES_FOR_SIGNATURE")

    def test_in_sync_needs_no_incident_or_recipe(self):
        plan = self.planner.plan(
            desired(),
            {"observed": {"healthy": True, "port": 8765, "extra": "ok"}, "evidence_refs": []},
            capability_states={},
            environment_fingerprint="windows-11-4gb",
            resource_mode="GREEN",
            observed_at="2026-10-05T21:32:00Z",
            owner_id="planner",
        )
        self.assertEqual(plan["decision"], "IN_SYNC")
        self.assertIsNone(plan["incident_id"])
        self.assertEqual(self.incidents.store.list_states("incident/"), [])


if __name__ == "__main__":
    unittest.main()
