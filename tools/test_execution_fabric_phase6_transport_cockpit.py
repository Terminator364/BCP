from __future__ import annotations

import copy
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"
sys.path.insert(0, str(WINDOWS))

from execution_fabric.action_receipt_registry import ActionReceiptRegistry  # noqa: E402
from execution_fabric.critical_store import CriticalStore  # noqa: E402
from execution_fabric.transport_cockpit import (  # noqa: E402
    CockpitProjectionError,
    DeliveryCollision,
    DeliveryTransitionError,
    TransportController,
    build_cockpit_projection,
    select_transport_route,
)


NOW = "2026-10-06T15:40:00+01:00"
FUTURE = "2026-10-06T18:40:00+01:00"


def obs(
    transport: str,
    *,
    state: str = "AVAILABLE",
    evidence_class: str = "SIMULATION",
    provider: str | None = None,
    capability: str | None = None,
    surface: str = "TELEGRAM",
    delivery_mode: str = "LIVE",
    low_data: bool = True,
    store_targets: list[str] | None = None,
    evidence_contract: list[str] | None = None,
    fresh: bool = True,
) -> dict:
    return {
        "schema": "bcp.capability_observation/1",
        "observation_id": f"obs-{transport.lower()}-{state.lower()}",
        "project_id": "BCP_CORE",
        "capability_id": capability or f"transport.{transport.lower()}.deliver",
        "provider_id": provider or f"{transport}_PROVIDER",
        "node_id": f"{transport}_NODE",
        "state": state,
        "transport": transport,
        "evidence_class": evidence_class,
        "details": {
            "surfaces": [surface],
            "direction": "EGRESS",
            "delivery_mode": delivery_mode,
            "low_data_supported": low_data,
            "store_forward_surfaces": store_targets or [],
            "evidence_contract": evidence_contract or [
                "PROVIDER_ACK",
                "DESTINATION_READBACK",
            ],
            "secret_canary": "MUST_NOT_APPEAR_IN_COCKPIT",
        },
        "source_revision": "phase6-test",
        "observed_at": "2026-10-06T15:39:00+01:00",
        "expires_at": FUTURE,
        "fresh": fresh,
    }


def snapshot(
    *,
    state: str = "RUNNING",
    plan_finite: bool = False,
    proof_at: str = "2026-10-06T15:39:30+01:00",
) -> dict:
    return {
        "project_id": "BCP_CORE",
        "mission_id": "mission-phase6",
        "canonical_state": state,
        "source_revision": "mission-rev-42",
        "plan_finite": plan_finite,
        "plan_revision": "plan-3" if plan_finite else None,
        "plan": [
            {"step_id": "s1", "label": "Vérifier", "state": "VERIFIED", "verified": True},
            {"step_id": "s2", "label": "Publier", "state": "RUNNING", "verified": False},
            {"step_id": "s3", "label": "Relire", "state": "PENDING", "verified": False},
        ] if plan_finite else [],
        "current_step": "Publier la projection",
        "last_completed_step": "Vérifier la projection",
        "next_step": "Relire la preuve de livraison",
        "human_action": {"state": "NONE", "instruction": None},
        "events": [
            {
                "sequence": 7,
                "state": "DISPATCHED",
                "summary": "Projection envoyée au provider",
                "source_node": "BCP_PC",
                "observed_at": proof_at,
                "evidence_refs": ["receipt-dispatch-7"],
                "durable": True,
            },
            {
                "sequence": 8,
                "state": "MODEL_THINKING",
                "summary": "État non durable à ignorer",
                "source_node": "CHAT_UI",
                "observed_at": "2026-10-06T15:39:50+01:00",
                "evidence_refs": [],
                "durable": False,
            },
        ],
        "technical_refs": ["git:df91abb", "workflow:phase6"],
    }


def projection(*, plan_finite: bool = True, observations: list[dict] | None = None) -> dict:
    return build_cockpit_projection(
        snapshot(plan_finite=plan_finite),
        observations or [obs("TELEGRAM")],
        generated_at=NOW,
        stale_after_seconds=60,
    )


def action_receipt(
    *,
    receipt_id: str = "receipt-transport-ok",
    provider_id: str = "TELEGRAM_PROVIDER",
    capability_id: str = "transport.telegram.deliver",
    field: bool = False,
    evidence_contract: list[str] | None = None,
    idempotency_key: str = "idem-delivery-phase6-001",
    committed_at: str = NOW,
) -> dict:
    kinds = evidence_contract or ["PROVIDER_ACK", "DESTINATION_READBACK"]
    return {
        "schema": "bcp.action_receipt/1",
        "receipt_id": receipt_id,
        "mission_id": "mission-phase6",
        "project_id": "BCP_CORE",
        "action_id": "deliver-cockpit",
        "job_id": "job-phase6",
        "step_id": "transport",
        "capability_id": capability_id,
        "provider_id": provider_id,
        "node_id": "TRANSPORT_NODE",
        "idempotency_key": idempotency_key,
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
        "source_revision": "phase6-test",
        "environment_fingerprint": "transport-test",
        "outbox_message_id": None,
        "idempotent_replay": False,
        "evidence": [
            {
                "evidence_id": f"proof-{kind.lower()}",
                "kind": kind,
                "status": "PASS",
                "value": {"delivered": True},
                "sha256": None,
                "source": "phase6-test",
                "observed_at": NOW,
            }
            for kind in kinds
        ],
        "readback": {
            "status": "PASS",
            "summary": "Provider destination confirmed",
            "observed_revision": "phase6",
        },
        "side_effects": [],
        "error": None,
        "created_at": NOW,
        "committed_at": committed_at,
    }


class CockpitProjectionTests(unittest.TestCase):
    def test_no_percentage_without_persisted_finite_plan(self):
        p = projection(plan_finite=False)
        self.assertIsNone(p["finite_progress"])

    def test_finite_progress_is_machine_derived(self):
        p = projection(plan_finite=True)
        self.assertEqual(p["finite_progress"]["completed"], 1)
        self.assertEqual(p["finite_progress"]["total"], 3)
        self.assertEqual(p["finite_progress"]["percent"], 33)

    def test_completed_state_without_verified_flag_does_not_inflate_progress(self):
        snap = snapshot(plan_finite=True)
        snap["plan"][1]["state"] = "COMPLETED"
        snap["plan"][1]["verified"] = False
        p = build_cockpit_projection(snap, [obs("TELEGRAM")], generated_at=NOW)
        self.assertEqual(p["finite_progress"]["completed"], 1)
        self.assertEqual(p["finite_progress"]["percent"], 33)

    def test_done_without_durable_evidence_is_not_presented_as_done(self):
        snap = snapshot(state="DONE", plan_finite=False)
        snap["events"] = []
        p = build_cockpit_projection(snap, [obs("TELEGRAM")], generated_at=NOW)
        self.assertEqual(p["canonical_state"], "DONE")
        self.assertEqual(p["human_state"], "UNKNOWN")
        self.assertEqual(p["activity"], "UNKNOWN")

    def test_non_durable_ui_event_is_not_last_proof(self):
        p = projection(plan_finite=True)
        self.assertEqual(p["last_proof"]["sequence"], 7)
        self.assertEqual(p["last_proof"]["source_node"], "BCP_PC")
        self.assertNotEqual(p["last_proof"]["state"], "MODEL_THINKING")

    def test_stale_evidence_is_reported_honestly(self):
        p = build_cockpit_projection(
            snapshot(state="WAITING_PROVIDER", proof_at="2026-10-06T15:30:00+01:00"),
            [obs("TELEGRAM")],
            generated_at=NOW,
            stale_after_seconds=60,
        )
        self.assertEqual(p["human_state"], "WAITING")
        self.assertEqual(p["activity"], "NO_NEW_EXTERNAL_EVIDENCE")

    def test_recent_waiting_evidence_is_waiting_external(self):
        p = build_cockpit_projection(
            snapshot(state="WAITING_PROVIDER"),
            [obs("TELEGRAM")],
            generated_at=NOW,
            stale_after_seconds=60,
        )
        self.assertEqual(p["activity"], "WAITING_EXTERNAL")

    def test_hidden_reasoning_field_is_rejected_not_exported(self):
        bad = snapshot()
        bad["chain_of_thought"] = "secret reasoning"
        with self.assertRaises(CockpitProjectionError):
            build_cockpit_projection(bad, [obs("TELEGRAM")], generated_at=NOW)

    def test_connectivity_projection_strips_provider_details_and_canaries(self):
        p = projection(observations=[obs("TELEGRAM")])
        encoded = repr(p["connectivity"])
        self.assertNotIn("secret_canary", encoded)
        self.assertNotIn("MUST_NOT_APPEAR", encoded)


class TransportRoutingTests(unittest.TestCase):
    def policy(self, **overrides):
        out = {
            "low_data": True,
            "allow_degraded": True,
            "allow_store_forward": True,
        }
        out.update(overrides)
        return out

    def route(self, observations, *, scope="SIMULATION", preferred=None, policy=None):
        return select_transport_route(
            surface="TELEGRAM",
            preferred_transports=preferred or ["TELEGRAM", "NEXUS"],
            observations=observations,
            target_scope=scope,
            policy=policy or self.policy(),
            now=NOW,
        )

    def test_direct_telegram_is_preferred_when_qualified(self):
        r = self.route([obs("NEXUS"), obs("TELEGRAM")])
        self.assertEqual(r["state"], "LIVE_READY")
        self.assertEqual(r["selected_transport"], "TELEGRAM")

    def test_nexus_is_live_fallback_not_authority(self):
        direct = obs("TELEGRAM", state="TEMP_UNAVAILABLE")
        nexus = obs("NEXUS", provider="NEXUS_PROVIDER", capability="transport.nexus.telegram")
        r = self.route([direct, nexus])
        self.assertEqual(r["selected_transport"], "NEXUS")
        self.assertFalse(r["store_forward"])

    def test_drive_store_forward_when_live_routes_unavailable(self):
        drive = obs(
            "DRIVE",
            provider="DRIVE_PROVIDER",
            capability="transport.drive.store_forward",
            surface="DRIVE",
            delivery_mode="STORE_FORWARD",
            store_targets=["TELEGRAM"],
        )
        r = self.route([
            obs("TELEGRAM", state="TEMP_UNAVAILABLE"),
            obs("NEXUS", state="TEMP_UNAVAILABLE"),
            drive,
        ])
        self.assertEqual(r["state"], "STORE_FORWARD_READY")
        self.assertEqual(r["selected_transport"], "DRIVE")
        self.assertTrue(r["store_forward"])

    def test_auth_required_is_explicit_hold(self):
        r = self.route([obs("TELEGRAM", state="AUTH_REQUIRED")])
        self.assertEqual(r["state"], "WAITING_AUTH")
        self.assertIsNone(r["selected_transport"])

    def test_field_route_rejects_non_field_capability_observation(self):
        r = self.route([obs("TELEGRAM", evidence_class="PROVIDER_PROBE")], scope="FIELD")
        self.assertEqual(r["state"], "WAITING_NETWORK")
        field_obs = obs("TELEGRAM", evidence_class="FIELD_READBACK")
        r2 = self.route([field_obs], scope="FIELD")
        self.assertEqual(r2["state"], "LIVE_READY")

    def test_low_data_policy_skips_route_that_does_not_support_it(self):
        direct = obs("TELEGRAM", low_data=False)
        drive = obs(
            "DRIVE",
            surface="DRIVE",
            delivery_mode="STORE_FORWARD",
            store_targets=["TELEGRAM"],
            low_data=True,
        )
        r = self.route([direct, drive])
        self.assertEqual(r["selected_transport"], "DRIVE")


class TransportControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CriticalStore(pathlib.Path(self.tmp.name) / "bcp.sqlite3")
        self.controller = TransportController(self.store)
        self.receipts = ActionReceiptRegistry(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def prepare(self, *, delivery_id="delivery-phase6-001", scope="SIMULATION", observations=None):
        p = projection(observations=observations or [obs("TELEGRAM")])
        return self.controller.prepare(
            delivery_id=delivery_id,
            surface="TELEGRAM",
            payload_kind="STATUS",
            projection=p,
            preferred_transports=["TELEGRAM", "NEXUS"],
            target_scope=scope,
            policy={
                "low_data": True,
                "allow_degraded": True,
                "allow_store_forward": True,
            },
            observations=observations or [obs("TELEGRAM")],
            idempotency_key=f"idem-{delivery_id}",
            created_at=NOW,
            expires_at=FUTURE,
            owner_id="phase6-test",
        )

    def test_delivery_is_durable_and_exact_replay_does_not_churn_revision(self):
        first = self.prepare()
        second = self.prepare()
        self.assertEqual(first["revision"], 1)
        self.assertEqual(second["revision"], 1)
        self.assertEqual(first["delivery"]["status"], "DISPATCH_READY")

    def test_same_idempotency_key_cannot_create_second_delivery(self):
        self.prepare(delivery_id="delivery-phase6-001")
        p = projection()
        with self.assertRaisesRegex(DeliveryCollision, "idempotency_key"):
            self.controller.prepare(
                delivery_id="delivery-phase6-002",
                surface="TELEGRAM",
                payload_kind="STATUS",
                projection=p,
                preferred_transports=["TELEGRAM", "NEXUS"],
                target_scope="SIMULATION",
                policy={
                    "low_data": True,
                    "allow_degraded": True,
                    "allow_store_forward": True,
                },
                observations=[obs("TELEGRAM")],
                idempotency_key="idem-delivery-phase6-001",
                created_at=NOW,
                expires_at=FUTURE,
                owner_id="phase6-test",
            )

    def test_expiry_must_be_after_creation(self):
        p = projection()
        with self.assertRaisesRegex(Exception, "expiry"):
            self.controller.prepare(
                delivery_id="delivery-phase6-expired",
                surface="TELEGRAM",
                payload_kind="STATUS",
                projection=p,
                preferred_transports=["TELEGRAM"],
                target_scope="SIMULATION",
                policy={
                    "low_data": True,
                    "allow_degraded": True,
                    "allow_store_forward": True,
                },
                observations=[obs("TELEGRAM")],
                idempotency_key="idem-delivery-phase6-expired",
                created_at=NOW,
                expires_at="2026-10-06T15:39:00+01:00",
                owner_id="phase6-test",
            )

    def test_same_delivery_id_cannot_change_projection(self):
        self.prepare()
        changed = projection()
        changed["source_revision"] = "mission-rev-other"
        # Rebuild identity/hash by constructing a genuinely different valid projection.
        changed = build_cockpit_projection(
            {**snapshot(plan_finite=True), "source_revision": "mission-rev-other"},
            [obs("TELEGRAM")],
            generated_at=NOW,
        )
        with self.assertRaises(DeliveryCollision):
            self.controller.prepare(
                delivery_id="delivery-phase6-001",
                surface="TELEGRAM",
                payload_kind="STATUS",
                projection=changed,
                preferred_transports=["TELEGRAM", "NEXUS"],
                target_scope="SIMULATION",
                policy={
                    "low_data": True,
                    "allow_degraded": True,
                    "allow_store_forward": True,
                },
                observations=[obs("TELEGRAM")],
                idempotency_key="idem-delivery-phase6-001",
                created_at=NOW,
                expires_at=FUTURE,
                owner_id="phase6-test",
            )

    def test_dispatch_plan_is_typed_and_contains_no_command_surface(self):
        self.prepare()
        plan = self.controller.dispatch_plan("BCP_CORE", "delivery-phase6-001")
        self.assertEqual(plan["capability_id"], "transport.telegram.deliver")
        encoded = repr(plan).lower()
        for forbidden in ("powershell", "cmd.exe", "'command'", "'argv'", "'shell'"):
            self.assertNotIn(forbidden, encoded)

    def test_expired_delivery_cannot_dispatch(self):
        self.prepare()
        with self.assertRaisesRegex(DeliveryTransitionError, "expired"):
            self.controller.dispatch_plan(
                "BCP_CORE",
                "delivery-phase6-001",
                now="2026-10-06T19:00:00+01:00",
            )

    def test_receipt_for_other_delivery_cannot_acknowledge(self):
        self.prepare()
        self.receipts.put(
            action_receipt(
                receipt_id="receipt-wrong-idem",
                idempotency_key="idem-another-delivery",
            ),
            owner_id="receipt",
        )
        with self.assertRaisesRegex(DeliveryTransitionError, "idempotency"):
            self.controller.acknowledge(
                "BCP_CORE",
                "delivery-phase6-001",
                "receipt-wrong-idem",
                owner_id="ack",
            )

    def test_late_receipt_cannot_acknowledge_expired_delivery(self):
        self.prepare()
        self.receipts.put(
            action_receipt(
                receipt_id="receipt-late",
                committed_at="2026-10-06T19:00:00+01:00",
            ),
            owner_id="receipt",
        )
        with self.assertRaisesRegex(DeliveryTransitionError, "expired|expiry"):
            self.controller.acknowledge(
                "BCP_CORE",
                "delivery-phase6-001",
                "receipt-late",
                owner_id="ack",
                now="2026-10-06T17:00:00+01:00",
            )

    def test_invented_receipt_cannot_acknowledge_delivery(self):
        self.prepare()
        with self.assertRaises(DeliveryTransitionError):
            self.controller.acknowledge(
                "BCP_CORE", "delivery-phase6-001", "receipt-does-not-exist",
                owner_id="ack",
            )

    def test_wrong_provider_or_capability_receipt_is_rejected(self):
        self.prepare()
        self.receipts.put(
            action_receipt(provider_id="WRONG_PROVIDER"),
            owner_id="receipt",
        )
        with self.assertRaisesRegex(DeliveryTransitionError, "provider"):
            self.controller.acknowledge(
                "BCP_CORE", "delivery-phase6-001", "receipt-transport-ok",
                owner_id="ack",
            )

        self.receipts.put(
            action_receipt(
                receipt_id="receipt-wrong-cap",
                capability_id="transport.other.deliver",
            ),
            owner_id="receipt",
        )
        with self.assertRaisesRegex(DeliveryTransitionError, "capability"):
            self.controller.acknowledge(
                "BCP_CORE", "delivery-phase6-001", "receipt-wrong-cap",
                owner_id="ack",
            )

    def test_missing_delivery_evidence_contract_is_rejected(self):
        self.prepare()
        self.receipts.put(
            action_receipt(
                receipt_id="receipt-incomplete",
                evidence_contract=["PROVIDER_ACK"],
            ),
            owner_id="receipt",
        )
        with self.assertRaisesRegex(DeliveryTransitionError, "evidence contract incomplete"):
            self.controller.acknowledge(
                "BCP_CORE", "delivery-phase6-001", "receipt-incomplete",
                owner_id="ack",
            )

    def test_matching_receipt_acknowledges_and_is_idempotent(self):
        first = self.prepare()
        self.assertEqual(first["delivery"]["status"], "DISPATCH_READY")
        self.receipts.put(action_receipt(), owner_id="receipt")
        ack = self.controller.acknowledge(
            "BCP_CORE", "delivery-phase6-001", "receipt-transport-ok",
            owner_id="ack",
        )
        self.assertEqual(ack["delivery"]["status"], "ACKNOWLEDGED")
        self.assertEqual(ack["delivery"]["route"]["state"], "ACKNOWLEDGED")
        self.assertEqual(ack["delivery"]["receipt_ref"], "receipt-transport-ok")
        replay = self.controller.acknowledge(
            "BCP_CORE", "delivery-phase6-001", "receipt-transport-ok",
            owner_id="ack-2",
        )
        self.assertEqual(replay["revision"], ack["revision"])

    def test_field_delivery_requires_field_certified_receipt(self):
        field_obs = obs("TELEGRAM", evidence_class="FIELD_READBACK")
        self.prepare(scope="FIELD", observations=[field_obs])
        self.receipts.put(action_receipt(), owner_id="receipt")
        with self.assertRaises(DeliveryTransitionError):
            self.controller.acknowledge(
                "BCP_CORE", "delivery-phase6-001", "receipt-transport-ok",
                owner_id="ack",
            )

        self.receipts.put(
            action_receipt(receipt_id="receipt-field-ok", field=True),
            owner_id="receipt",
        )
        ack = self.controller.acknowledge(
            "BCP_CORE", "delivery-phase6-001", "receipt-field-ok",
            owner_id="ack",
        )
        self.assertEqual(ack["delivery"]["status"], "ACKNOWLEDGED")

    def test_latest_projection_is_read_only_projection_of_transport_state(self):
        self.prepare()
        p = self.controller.latest_projection("BCP_CORE")
        self.assertEqual(p["schema"], "bcp.cockpit_projection/1")
        self.assertFalse(p["field_certified"])


if __name__ == "__main__":
    unittest.main()
