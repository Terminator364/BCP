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
from execution_fabric.release_controller import (  # noqa: E402
    ReleaseController,
    ReleasePublicationConflict,
    ReleaseValidationError,
)


ARTIFACT_A = "a" * 64
ARTIFACT_B = "b" * 64


def candidate(
    release_id: str,
    sequence: int,
    artifact_sha: str,
    *,
    field_qual: bool = False,
    field_activation: bool = False,
    migration_class: str = "NONE",
    rollback_compatible: bool = True,
) -> dict:
    return {
        "schema": "bcp.release_candidate/1",
        "release_id": release_id,
        "project_id": "MED_REBUILD",
        "sequence": sequence,
        "version": f"1.0.{sequence}",
        "source": {
            "repository": "Terminator364/ChatGPT-PC",
            "revision": f"{sequence:040x}",
            "path": "med-rebuild-study-hub/v1.5-prototype",
        },
        "artifact": {
            "transport": "GITHUB_BLOB",
            "locator": f"git-blob:{artifact_sha}",
            "sha256": artifact_sha,
            "size_bytes": 12345,
        },
        "provenance": {
            "builder_class": "GITHUB_ACTIONS",
            "build_recipe_ref": ".github/workflows/med-rebuild.yml",
            "dependency_lock_ref": None,
            "signer": None,
            "signature_ref": None,
        },
        "qualification_policy": {
            "required_capabilities": ["med_rebuild.release.verify"],
            "field_evidence_required": field_qual,
        },
        "activation_policy": {
            "rollback_required": True,
            "field_activation_required": field_activation,
            "migration": {
                "class": migration_class,
                "rollback_compatible": rollback_compatible,
                "migration_ref": "migration-v1" if migration_class == "MIGRATION_REQUIRED" else None,
            },
        },
        "notes": [],
        "created_at": "2026-10-05T22:00:00Z",
    }


def adapter(*, missing: str | None = None, update_resource: str = "R1_LIGHT") -> dict:
    rows = [
        ("RELEASE_VERIFY", "med_rebuild.release.verify", "P0_READ", "R1_LIGHT", ["HASH", "GIT_REVISION"]),
        ("UPDATE_ACTIVATE", "med_rebuild.update.activate", "P2_PROJECT_MUTATION", update_resource, ["HASH", "FILE_READBACK"]),
        ("HEALTHCHECK", "med_rebuild.healthcheck", "P0_READ", "R0_TINY", ["PROCESS_HEALTH", "HASH"]),
        ("ROLLBACK", "med_rebuild.rollback", "P2_PROJECT_MUTATION", "R1_LIGHT", ["FILE_READBACK", "PROCESS_HEALTH"]),
    ]
    bindings = []
    for operation, cap, perm, resource, evidence in rows:
        bindings.append({
            "operation": operation,
            "capability_id": cap,
            "provider_id": "MED_REBUILD_NATIVE",
            "state": "WAITING_BINDING" if operation == missing else "BOUND",
            "permission_class": perm,
            "resource_class": resource,
            "evidence_contract": evidence,
            "input_defaults": {},
            "binding_reason": None,
        })
    return {
        "schema": "bcp.project_adapter/1",
        "adapter_id": "med_rebuild.native.v1",
        "project_id": "MED_REBUILD",
        "version": "1",
        "bindings": bindings,
        "source_revision": "PHASE5_TEST",
        "notes": [],
    }


def receipt(
    receipt_id: str,
    capability_id: str,
    artifact_sha: str,
    *,
    field: bool = False,
    project_id: str = "MED_REBUILD",
) -> dict:
    return {
        "schema": "bcp.action_receipt/1",
        "receipt_id": receipt_id,
        "mission_id": "mission-phase5",
        "project_id": project_id,
        "action_id": "release-action",
        "job_id": "job-phase5",
        "step_id": "release-step",
        "capability_id": capability_id,
        "provider_id": "MED_REBUILD_NATIVE",
        "node_id": "PC",
        "idempotency_key": "phase5-" + receipt_id,
        "status": "SUCCEEDED",
        "result": "PASS",
        "proof_scope": "FIELD" if field else "SIMULATION",
        "field_certified": field,
        "durability": "DURABLE_LOCAL",
        "committed_revision": 1,
        "fencing_token": 1,
        "content_hash": None,
        "predecessor_hash": None,
        "output_hash": artifact_sha,
        "source_revision": "PHASE5_TEST",
        "environment_fingerprint": "windows-11-4gb",
        "outbox_message_id": None,
        "idempotent_replay": False,
        "evidence": [{
            "evidence_id": "artifact-proof",
            "kind": "HASH",
            "status": "PASS",
            "value": {"active": True},
            "sha256": artifact_sha,
            "source": "phase5-test",
            "observed_at": "2026-10-05T22:01:00Z",
        }],
        "readback": {
            "status": "PASS",
            "summary": "verified",
            "observed_revision": "phase5",
        },
        "side_effects": [],
        "error": None,
        "created_at": "2026-10-05T22:01:00Z",
        "committed_at": "2026-10-05T22:01:01Z",
    }


class ReleaseControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CriticalStore(pathlib.Path(self.tmp.name) / "bcp.sqlite3")
        self.controller = ReleaseController(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def seed_qualified(
        self,
        rec: dict,
        *,
        field_qualification: bool | None = None,
    ):
        self.controller.register_candidate(rec, owner_id="candidate-writer")
        verify_id = f"verify-{rec['release_id']}"
        self.controller.receipts.put(
            receipt(
                verify_id,
                "med_rebuild.release.verify",
                rec["artifact"]["sha256"],
                field=False,
            ),
            owner_id="receipt-writer",
        )
        field_refs = []
        required = (
            rec["qualification_policy"]["field_evidence_required"]
            if field_qualification is None
            else field_qualification
        )
        if required:
            field_id = f"field-verify-{rec['release_id']}"
            self.controller.receipts.put(
                receipt(
                    field_id,
                    "med_rebuild.release.verify",
                    rec["artifact"]["sha256"],
                    field=True,
                ),
                owner_id="field-receipt-writer",
            )
            field_refs.append(field_id)
        return self.controller.qualify(
            "MED_REBUILD",
            rec["release_id"],
            successful_receipt_refs=[verify_id],
            regression_refs=["tests/release-regression"],
            field_receipt_refs=field_refs,
            qualified_at="2026-10-05T22:02:00Z",
            owner_id="qualifier",
        )

    def activate(self, rec: dict, *, field: bool = False):
        aid = f"activate-{rec['release_id']}"
        hid = f"health-{rec['release_id']}"
        self.controller.receipts.put(
            receipt(aid, "med_rebuild.update.activate", rec["artifact"]["sha256"], field=field),
            owner_id="activation-receipt",
        )
        self.controller.receipts.put(
            receipt(hid, "med_rebuild.healthcheck", rec["artifact"]["sha256"], field=field),
            owner_id="health-receipt",
        )
        return self.controller.commit_activation(
            "MED_REBUILD",
            rec["release_id"],
            adapter(),
            activation_receipt_ref=aid,
            health_receipt_ref=hid,
            promoted_at="2026-10-05T22:03:00Z",
            owner_id="release-controller",
        )

    def test_candidate_is_immutable_and_idempotent(self):
        rec = candidate("med-rebuild-r1", 1, ARTIFACT_A)
        first = self.controller.register_candidate(rec, owner_id="a")
        second = self.controller.register_candidate(copy.deepcopy(rec), owner_id="b")
        self.assertEqual(first["revision"], 1)
        self.assertEqual(second["revision"], 1)
        changed = copy.deepcopy(rec)
        changed["version"] = "different"
        with self.assertRaises(ReleasePublicationConflict):
            self.controller.register_candidate(changed, owner_id="c")

    def test_same_sequence_different_release_fails_publication_fencing(self):
        self.controller.register_candidate(
            candidate("med-rebuild-r1", 1, ARTIFACT_A),
            owner_id="a",
        )
        with self.assertRaises(ReleasePublicationConflict):
            self.controller.register_candidate(
                candidate("med-rebuild-r1b", 1, ARTIFACT_B),
                owner_id="b",
            )

    def test_qualification_requires_real_receipt_and_artifact_hash(self):
        rec = candidate("med-rebuild-r1", 1, ARTIFACT_A)
        self.controller.register_candidate(rec, owner_id="a")
        with self.assertRaises(ReleaseValidationError):
            self.controller.qualify(
                "MED_REBUILD",
                rec["release_id"],
                successful_receipt_refs=["missing-receipt"],
                regression_refs=["regression"],
                qualified_at="2026-10-05T22:02:00Z",
                owner_id="q",
            )

        wrong = receipt("verify-wrong", "med_rebuild.release.verify", ARTIFACT_B)
        self.controller.receipts.put(wrong, owner_id="receipt")
        with self.assertRaisesRegex(ReleaseValidationError, "artifact sha256"):
            self.controller.qualify(
                "MED_REBUILD",
                rec["release_id"],
                successful_receipt_refs=["verify-wrong"],
                regression_refs=["regression"],
                qualified_at="2026-10-05T22:02:00Z",
                owner_id="q",
            )

    def test_field_qualification_requires_real_field_receipt(self):
        rec = candidate("med-rebuild-fieldq", 1, ARTIFACT_A, field_qual=True)
        self.controller.register_candidate(rec, owner_id="a")
        self.controller.receipts.put(
            receipt("verify-sim", "med_rebuild.release.verify", ARTIFACT_A),
            owner_id="receipt",
        )
        with self.assertRaises(ReleaseValidationError):
            self.controller.qualify(
                "MED_REBUILD",
                rec["release_id"],
                successful_receipt_refs=["verify-sim"],
                regression_refs=["regression"],
                field_receipt_refs=[],
                qualified_at="2026-10-05T22:02:00Z",
                owner_id="q",
            )

    def test_plan_is_typed_and_has_no_executable_mechanics(self):
        rec = candidate("med-rebuild-r1", 1, ARTIFACT_A)
        self.seed_qualified(rec)
        plan = self.controller.plan_activation(
            "MED_REBUILD", rec["release_id"], adapter(), resource_mode="GREEN"
        )
        self.assertEqual(plan["decision"], "EXECUTE_TYPED_PLAN")
        self.assertEqual(
            [x["operation"] for x in plan["steps"]],
            ["RELEASE_VERIFY", "UPDATE_ACTIVATE", "HEALTHCHECK"],
        )
        blob = repr(plan).lower()
        for forbidden in ("powershell.exe", "cmd.exe", "'command':", "'argv':"):
            self.assertNotIn(forbidden, blob)

    def test_missing_binding_and_resource_pressure_hold(self):
        rec = candidate("med-rebuild-r1", 1, ARTIFACT_A)
        self.seed_qualified(rec)
        plan = self.controller.plan_activation(
            "MED_REBUILD",
            rec["release_id"],
            adapter(missing="UPDATE_ACTIVATE"),
            resource_mode="GREEN",
        )
        self.assertEqual(plan["decision"], "HOLD_BINDING_UPDATE_ACTIVATE")

        plan = self.controller.plan_activation(
            "MED_REBUILD",
            rec["release_id"],
            adapter(update_resource="R3_HEAVY"),
            resource_mode="AMBER",
        )
        self.assertTrue(plan["decision"].startswith("HOLD_RESOURCE_UPDATE_ACTIVATE"))

    def test_irreversible_migration_holds_before_activation(self):
        rec = candidate(
            "med-rebuild-migrate",
            1,
            ARTIFACT_A,
            migration_class="MIGRATION_REQUIRED",
            rollback_compatible=False,
        )
        self.seed_qualified(rec)
        plan = self.controller.plan_activation(
            "MED_REBUILD", rec["release_id"], adapter(), resource_mode="GREEN"
        )
        self.assertEqual(plan["decision"], "HOLD_MIGRATION_SAFETY")

    def test_commit_requires_matching_activation_and_health_capabilities(self):
        rec = candidate("med-rebuild-r1", 1, ARTIFACT_A)
        self.seed_qualified(rec)
        self.controller.receipts.put(
            receipt("activate-r1", "wrong.capability", ARTIFACT_A),
            owner_id="receipt",
        )
        self.controller.receipts.put(
            receipt("health-r1", "med_rebuild.healthcheck", ARTIFACT_A),
            owner_id="receipt",
        )
        with self.assertRaisesRegex(ReleaseValidationError, "capability mismatch"):
            self.controller.commit_activation(
                "MED_REBUILD",
                rec["release_id"],
                adapter(),
                activation_receipt_ref="activate-r1",
                health_receipt_ref="health-r1",
                promoted_at="2026-10-05T22:03:00Z",
                owner_id="release-controller",
            )

    def test_current_and_lkg_move_atomically_after_health_success(self):
        r1 = candidate("med-rebuild-r1", 1, ARTIFACT_A)
        self.seed_qualified(r1)
        c1 = self.activate(r1)
        self.assertEqual(c1["payload"]["current"]["release_id"], r1["release_id"])
        self.assertIsNone(c1["payload"]["lkg"])

        r2 = candidate("med-rebuild-r2", 2, ARTIFACT_B)
        self.seed_qualified(r2)
        plan = self.controller.plan_activation(
            "MED_REBUILD", r2["release_id"], adapter(), resource_mode="GREEN"
        )
        self.assertEqual(plan["decision"], "EXECUTE_TYPED_PLAN")
        self.assertEqual(plan["rollback"]["input"]["target"]["release_id"], r1["release_id"])

        c2 = self.activate(r2)
        self.assertEqual(c2["payload"]["current"]["release_id"], r2["release_id"])
        self.assertEqual(c2["payload"]["lkg"]["release_id"], r1["release_id"])
        self.assertEqual(c2["revision"], 2)

    def test_anti_downgrade_and_same_sequence_noop(self):
        r2 = candidate("med-rebuild-r2", 2, ARTIFACT_B)
        self.seed_qualified(r2)
        self.activate(r2)

        same = self.controller.plan_activation(
            "MED_REBUILD", r2["release_id"], adapter(), resource_mode="GREEN"
        )
        self.assertEqual(same["decision"], "NOOP_ALREADY_CURRENT")

        old = candidate("med-rebuild-r1", 1, ARTIFACT_A)
        self.seed_qualified(old)
        held = self.controller.plan_activation(
            "MED_REBUILD", old["release_id"], adapter(), resource_mode="GREEN"
        )
        self.assertEqual(held["decision"], "HOLD_ANTI_DOWNGRADE")

    def test_field_activation_requires_field_receipts(self):
        rec = candidate(
            "med-rebuild-fieldact",
            1,
            ARTIFACT_A,
            field_activation=True,
        )
        self.seed_qualified(rec)
        aid = "activate-field-required"
        hid = "health-field-required"
        self.controller.receipts.put(
            receipt(aid, "med_rebuild.update.activate", ARTIFACT_A, field=False),
            owner_id="receipt",
        )
        self.controller.receipts.put(
            receipt(hid, "med_rebuild.healthcheck", ARTIFACT_A, field=False),
            owner_id="receipt",
        )
        with self.assertRaises(ReleaseValidationError):
            self.controller.commit_activation(
                "MED_REBUILD",
                rec["release_id"],
                adapter(),
                activation_receipt_ref=aid,
                health_receipt_ref=hid,
                promoted_at="2026-10-05T22:03:00Z",
                owner_id="release-controller",
            )


if __name__ == "__main__":
    unittest.main()
