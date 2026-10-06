from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"
sys.path.insert(0, str(WINDOWS))

from execution_fabric.capability_factory import (  # noqa: E402
    CapabilityFactory,
    CandidateTransitionError,
    RegistrationCollision,
)
from execution_fabric.critical_store import CriticalStore  # noqa: E402


NOW = "2026-10-06T16:00:00+01:00"
ARTIFACT_SHA = "a" * 64

GATE_CAP = {
    "reuse_search": "factory.reuse.search",
    "source_trust": "factory.source.verify",
    "license_policy": "factory.license.verify",
    "build_adapter": "factory.adapter.build",
    "static_validate": "factory.static.validate",
    "sandbox_test": "factory.sandbox.test",
    "resource_test": "factory.resource.test",
    "rollback_test": "factory.rollback.test",
    "security_test": "factory.security.test",
    "canary": "factory.canary.run",
}
GATE_EVIDENCE = {
    "reuse_search": "CUSTOM_VALIDATOR",
    "source_trust": "HASH",
    "license_policy": "CUSTOM_VALIDATOR",
    "build_adapter": "ARTIFACT_SIGNATURE",
    "static_validate": "TEST_RESULT",
    "sandbox_test": "TEST_RESULT",
    "resource_test": "TEST_RESULT",
    "rollback_test": "TEST_RESULT",
    "security_test": "TEST_RESULT",
    "canary": "TEST_RESULT",
}


def manifest(
    *,
    permission: str = "P1_SAFE_WRITE",
    resource: str = "R1_LIGHT",
    version: str = "1.0.0",
    description: str = "Test capability",
) -> dict:
    return {
        "schema": "bcp.capability_manifest/1",
        "capability_id": "demo.capability",
        "provider_id": "DEMO_PROVIDER",
        "version": version,
        "description": description,
        "project_scopes": ["BCP_CORE"],
        "availability": "AVAILABLE",
        "effect_class": "SAFE_WRITE",
        "permission_class": permission,
        "resource_class": resource,
        "requires_network": False,
        "requires_pc": True,
        "requires_bedge": False,
        "requires_admin": False,
        "preemptible": True,
        "timeout_seconds": 60,
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "preconditions": [],
        "rollback": {"required": True, "strategy": "typed rollback capability"},
        "evidence_contract": ["TEST_RESULT"],
        "executor": {
            "kind": "INTERNAL",
            "entrypoint": "provider-owned",
            "pinned_version": "1.0.0",
            "sha256": ARTIFACT_SHA,
        },
    }


def policy(
    *,
    permission: str = "P3_BOUNDED_SYSTEM_CHANGE",
    resource: str = "R3_HEAVY",
    target_scope: str = "SIMULATION",
    sandbox: bool = True,
    rollback: bool = True,
    security: bool = True,
    canary: bool = True,
) -> dict:
    return {
        "max_permission_class": permission,
        "max_resource_class": resource,
        "allowed_trust_classes": [
            "T0_BUILTIN", "T1_VERIFIED_LOCAL", "T2_VERIFIED_REMOTE"
        ],
        "require_sandbox": sandbox,
        "require_rollback": rollback,
        "require_security_test": security,
        "require_canary": canary,
        "target_scope": target_scope,
    }


def source() -> dict:
    return {
        "kind": "GENERATED_ADAPTER",
        "locator": "repo://candidate/demo",
        "revision": "source-r1",
        "artifact_sha256": None,
        "publisher": "BCP_FACTORY_TEST",
    }


def license_unknown() -> dict:
    return {"status": "UNKNOWN", "identifier": None, "evidence_refs": []}


def receipt(
    candidate_id: str,
    gate: str,
    *,
    scope: str = "SIMULATION",
    evidence_kind: str | None = None,
    source_revision: str = "source-r1",
    idempotency_key: str | None = None,
) -> dict:
    kind = evidence_kind or GATE_EVIDENCE[gate]
    field = scope == "FIELD"
    return {
        "schema": "bcp.action_receipt/1",
        "receipt_id": f"receipt-{candidate_id}-{gate}",
        "mission_id": "mission-phase7",
        "project_id": "BCP_CORE",
        "action_id": f"factory-{gate}",
        "job_id": f"job-{gate}",
        "step_id": gate,
        "capability_id": GATE_CAP[gate],
        "provider_id": "FACTORY_TEST_PROVIDER",
        "node_id": "CI",
        "idempotency_key": idempotency_key or f"factory:{candidate_id}:{gate}",
        "status": "SUCCEEDED",
        "result": "PASS",
        "proof_scope": scope,
        "field_certified": field,
        "durability": "DURABLE_LOCAL",
        "committed_revision": 1,
        "fencing_token": 1,
        "content_hash": None,
        "predecessor_hash": None,
        "output_hash": ARTIFACT_SHA if gate == "build_adapter" else None,
        "source_revision": source_revision,
        "environment_fingerprint": "phase7-test",
        "outbox_message_id": None,
        "idempotent_replay": False,
        "evidence": [
            {
                "evidence_id": f"proof-{gate}",
                "kind": kind,
                "status": "PASS",
                "value": {"gate": gate},
                "sha256": ARTIFACT_SHA if kind in {"HASH", "ARTIFACT_SIGNATURE"} else None,
                "source": "phase7-test",
                "observed_at": NOW,
            }
        ],
        "readback": {
            "status": "PASS",
            "summary": f"{gate} passed",
            "observed_revision": source_revision,
        },
        "side_effects": [],
        "error": None,
        "created_at": NOW,
        "committed_at": NOW,
    }


class CapabilityFactoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CriticalStore(pathlib.Path(self.tmp.name) / "bcp.sqlite3")
        self.factory = CapabilityFactory(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def create(
        self,
        candidate_id: str = "candidate-phase7-001",
        *,
        trust: str = "T3_CANDIDATE",
        license_info: dict | None = None,
        manifest_obj: dict | None = None,
        policy_obj: dict | None = None,
    ):
        return self.factory.create(
            candidate_id=candidate_id,
            project_id="BCP_CORE",
            original_mission_id="mission-phase7",
            requested_capability_id="demo.capability",
            trust_class=trust,
            source=source(),
            license_info=license_info or license_unknown(),
            proposed_manifest=manifest_obj or manifest(),
            policy=policy_obj or policy(),
            owner_id="factory-test",
            now=NOW,
        )

    def put_and_record(
        self,
        candidate_id: str,
        gate: str,
        *,
        scope: str = "SIMULATION",
        evidence_kind: str | None = None,
        trust_class: str | None = None,
        license_status: str | None = None,
        source_revision: str = "source-r1",
        idempotency_key: str | None = None,
    ):
        rec = receipt(
            candidate_id,
            gate,
            scope=scope,
            evidence_kind=evidence_kind,
            source_revision=source_revision,
            idempotency_key=idempotency_key,
        )
        self.factory.receipts.put(rec, owner_id="receipt-writer")
        return self.factory.record_gate(
            "BCP_CORE",
            candidate_id,
            gate=gate,
            receipt_id=rec["receipt_id"],
            owner_id="factory-transition",
            now=NOW,
            trust_class=trust_class,
            license_status=license_status,
            license_identifier="MIT" if license_status == "APPROVED" else None,
        )

    def qualify(
        self,
        candidate_id: str = "candidate-phase7-001",
        *,
        target_scope: str = "SIMULATION",
        optional: bool = False,
    ):
        self.create(
            candidate_id,
            policy_obj=policy(
                target_scope=target_scope,
                sandbox=not optional,
                rollback=not optional,
                security=not optional,
                canary=not optional,
            ),
        )
        self.put_and_record(candidate_id, "reuse_search")
        self.put_and_record(candidate_id, "source_trust", trust_class="T2_VERIFIED_REMOTE")
        self.put_and_record(candidate_id, "license_policy", license_status="APPROVED")
        self.put_and_record(candidate_id, "build_adapter")
        self.put_and_record(candidate_id, "static_validate")
        if not optional:
            self.put_and_record(candidate_id, "sandbox_test")
        self.put_and_record(candidate_id, "resource_test")
        if not optional:
            self.put_and_record(candidate_id, "rollback_test")
            self.put_and_record(candidate_id, "security_test")
            self.put_and_record(
                candidate_id,
                "canary",
                scope="FIELD" if target_scope == "FIELD" else target_scope,
            )
        return self.factory.get("BCP_CORE", candidate_id)

    def test_candidate_starts_at_reuse_search_with_typed_plan(self):
        self.create()
        plan = self.factory.plan_next(
            "BCP_CORE", "candidate-phase7-001", resource_mode="GREEN"
        )
        self.assertEqual(plan["decision"], "EXECUTE_TYPED_GATE")
        self.assertEqual(plan["gate"], "reuse_search")
        self.assertEqual(plan["capability_id"], "factory.reuse.search")
        self.assertEqual(
            plan["input"]["idempotency_key"],
            "factory:candidate-phase7-001:reuse_search",
        )
        encoded = repr(plan).casefold()
        for forbidden in ("'command'", "'argv'", "'shell'", "powershell.exe", "cmd.exe"):
            self.assertNotIn(forbidden, encoded)

    def test_receipt_cannot_be_reused_for_another_candidate_gate(self):
        self.create()
        bad = receipt(
            "candidate-phase7-001",
            "reuse_search",
            idempotency_key="factory:candidate-other-0001:reuse_search",
        )
        self.factory.receipts.put(bad, owner_id="receipt")
        with self.assertRaisesRegex(CandidateTransitionError, "idempotency"):
            self.factory.record_gate(
                "BCP_CORE", "candidate-phase7-001",
                gate="reuse_search", receipt_id=bad["receipt_id"],
                owner_id="transition", now=NOW,
            )

    def test_wrong_source_revision_is_rejected(self):
        self.create()
        bad = receipt(
            "candidate-phase7-001", "reuse_search", source_revision="wrong-revision"
        )
        self.factory.receipts.put(bad, owner_id="receipt")
        with self.assertRaisesRegex(CandidateTransitionError, "source revision"):
            self.factory.record_gate(
                "BCP_CORE", "candidate-phase7-001",
                gate="reuse_search", receipt_id=bad["receipt_id"],
                owner_id="transition", now=NOW,
            )

    def test_missing_gate_evidence_is_rejected(self):
        self.create()
        bad = receipt(
            "candidate-phase7-001", "reuse_search", evidence_kind="TEST_RESULT"
        )
        self.factory.receipts.put(bad, owner_id="receipt")
        with self.assertRaisesRegex(CandidateTransitionError, "evidence incomplete"):
            self.factory.record_gate(
                "BCP_CORE", "candidate-phase7-001",
                gate="reuse_search", receipt_id=bad["receipt_id"],
                owner_id="transition", now=NOW,
            )

    def test_t4_source_is_quarantined_at_creation(self):
        state = self.create(trust="T4_QUARANTINED")
        self.assertEqual(state["payload"]["stage"], "QUARANTINED")
        self.assertEqual(state["payload"]["status"], "HOLD")
        self.assertEqual(state["payload"]["failure"]["code"], "SOURCE_QUARANTINED")

    def test_denied_license_is_quarantined_at_creation(self):
        state = self.create(
            license_info={"status": "DENIED", "identifier": "NOPE", "evidence_refs": []}
        )
        self.assertEqual(state["payload"]["stage"], "QUARANTINED")
        self.assertEqual(state["payload"]["failure"]["code"], "LICENSE_DENIED")

    def test_source_trust_must_be_verified_for_auto_path(self):
        self.create()
        self.put_and_record("candidate-phase7-001", "reuse_search")
        state = self.put_and_record(
            "candidate-phase7-001", "source_trust", trust_class="T3_CANDIDATE"
        )
        self.assertEqual(state["payload"]["stage"], "WAITING_APPROVAL")
        self.assertEqual(state["payload"]["status"], "HOLD")

    def test_license_review_holds_without_fake_progress(self):
        self.create()
        self.put_and_record("candidate-phase7-001", "reuse_search")
        self.put_and_record(
            "candidate-phase7-001", "source_trust", trust_class="T2_VERIFIED_REMOTE"
        )
        state = self.put_and_record(
            "candidate-phase7-001", "license_policy", license_status="REVIEW_REQUIRED"
        )
        self.assertEqual(state["payload"]["stage"], "WAITING_APPROVAL")
        self.assertEqual(state["payload"]["failure"]["code"], "LICENSE_REVIEW_REQUIRED")

    def test_build_gate_binds_artifact_hash_from_receipt(self):
        self.create()
        self.put_and_record("candidate-phase7-001", "reuse_search")
        self.put_and_record(
            "candidate-phase7-001", "source_trust", trust_class="T2_VERIFIED_REMOTE"
        )
        self.put_and_record(
            "candidate-phase7-001", "license_policy", license_status="APPROVED"
        )
        state = self.put_and_record("candidate-phase7-001", "build_adapter")
        self.assertEqual(state["payload"]["source"]["artifact_sha256"], ARTIFACT_SHA)

    def test_factory_gate_permission_ceiling_holds(self):
        self.create(policy_obj=policy(permission="P1_SAFE_WRITE"))
        self.put_and_record("candidate-phase7-001", "reuse_search")
        self.put_and_record(
            "candidate-phase7-001", "source_trust", trust_class="T2_VERIFIED_REMOTE"
        )
        self.put_and_record(
            "candidate-phase7-001", "license_policy", license_status="APPROVED"
        )
        plan = self.factory.plan_next(
            "BCP_CORE", "candidate-phase7-001", resource_mode="GREEN"
        )
        self.assertEqual(plan["gate"], "build_adapter")
        self.assertEqual(plan["decision"], "WAITING_APPROVAL")

    def test_factory_gate_resource_ceiling_holds(self):
        self.create(policy_obj=policy(resource="R1_LIGHT"))
        self.put_and_record("candidate-phase7-001", "reuse_search")
        self.put_and_record(
            "candidate-phase7-001", "source_trust", trust_class="T2_VERIFIED_REMOTE"
        )
        self.put_and_record(
            "candidate-phase7-001", "license_policy", license_status="APPROVED"
        )
        plan = self.factory.plan_next(
            "BCP_CORE", "candidate-phase7-001", resource_mode="GREEN"
        )
        self.assertEqual(plan["gate"], "build_adapter")
        self.assertEqual(plan["decision"], "WAITING_RESOURCE")

    def test_runtime_resource_pressure_holds_gate(self):
        self.create()
        self.put_and_record("candidate-phase7-001", "reuse_search")
        self.put_and_record(
            "candidate-phase7-001", "source_trust", trust_class="T2_VERIFIED_REMOTE"
        )
        self.put_and_record(
            "candidate-phase7-001", "license_policy", license_status="APPROVED"
        )
        plan = self.factory.plan_next(
            "BCP_CORE", "candidate-phase7-001", resource_mode="AMBER"
        )
        self.assertEqual(plan["decision"], "WAITING_RESOURCE")

    def test_optional_gates_are_skipped_by_policy(self):
        state = self.qualify("candidate-phase7-optional", optional=True)
        self.assertEqual(state["payload"]["stage"], "REGISTER")
        self.assertNotIn("sandbox_test", state["payload"]["gate_receipts"])
        self.assertNotIn("rollback_test", state["payload"]["gate_receipts"])
        self.assertNotIn("security_test", state["payload"]["gate_receipts"])
        self.assertNotIn("canary", state["payload"]["gate_receipts"])

    def test_field_canary_requires_real_field_receipt(self):
        candidate_id = "candidate-phase7-field"
        self.create(
            candidate_id,
            policy_obj=policy(target_scope="FIELD"),
        )
        for gate in (
            "reuse_search", "source_trust", "license_policy", "build_adapter",
            "static_validate", "sandbox_test", "resource_test",
            "rollback_test", "security_test",
        ):
            self.put_and_record(
                candidate_id,
                gate,
                trust_class="T2_VERIFIED_REMOTE" if gate == "source_trust" else None,
                license_status="APPROVED" if gate == "license_policy" else None,
            )
        rec = receipt(candidate_id, "canary", scope="SIMULATION")
        self.factory.receipts.put(rec, owner_id="receipt")
        with self.assertRaises(CandidateTransitionError):
            self.factory.record_gate(
                "BCP_CORE", candidate_id,
                gate="canary", receipt_id=rec["receipt_id"],
                owner_id="transition", now=NOW,
            )
        state = self.put_and_record(candidate_id, "canary", scope="FIELD")
        self.assertEqual(state["payload"]["stage"], "REGISTER")

    def test_full_qualified_candidate_registers_immutably(self):
        state = self.qualify()
        self.assertEqual(state["payload"]["stage"], "REGISTER")
        registered = self.factory.register(
            "BCP_CORE", "candidate-phase7-001",
            owner_id="register", now=NOW,
        )
        payload = registered["payload"]
        self.assertEqual(payload["schema"], "bcp.capability_registration/1")
        self.assertEqual(payload["capability_id"], "demo.capability")
        self.assertEqual(payload["trust_class"], "T2_VERIFIED_REMOTE")
        self.assertFalse(payload["field_certified"])
        final = self.factory.get("BCP_CORE", "candidate-phase7-001")["payload"]
        self.assertEqual(final["stage"], "REGISTERED")
        self.assertEqual(final["status"], "REGISTERED")

        replay = self.factory.registry.put(payload, owner_id="replay")
        self.assertEqual(replay["revision"], 1)
        changed = dict(payload)
        changed["source_revision"] = "different"
        with self.assertRaises(RegistrationCollision):
            self.factory.registry.put(changed, owner_id="collision")

    def test_p4_capability_is_not_auto_factory_path(self):
        state = self.create(
            manifest_obj=manifest(permission="P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE"),
        )
        self.assertEqual(state["payload"]["stage"], "WAITING_APPROVAL")
        self.assertEqual(state["payload"]["status"], "HOLD")

    def test_factory_module_has_no_direct_execution_or_network_provider(self):
        source_text = (
            ROOT / "windows" / "execution_fabric" / "capability_factory.py"
        ).read_text(encoding="utf-8").casefold()
        for forbidden in (
            "subprocess.",
            "os.system",
            "shell=true",
            "requests.",
            "urllib.request",
            "powershell.exe",
            "cmd.exe",
            "safe_extract(",
        ):
            self.assertNotIn(forbidden, source_text)


if __name__ == "__main__":
    unittest.main()
