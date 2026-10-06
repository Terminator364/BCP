from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"
sys.path.insert(0, str(WINDOWS))

from execution_fabric.critical_store import CriticalStore  # noqa: E402
from execution_fabric.memory_fabric import (  # noqa: E402
    MemoryAdmissionHold,
    MemoryClaimConflict,
    MemoryFabric,
)


def claim(
    claim_id: str,
    *,
    project: str = "BCP_CORE",
    scope: str = "PROJECT_MEMORY",
    key: str = "architecture.primary",
    value=None,
    evidence: str = "SOURCE_VERIFIED",
    category: str = "DESCRIPTIVE",
    pinned: bool = False,
    idem: str | None = None,
    observed_at: str = "2026-10-06T14:00:00Z",
    expires_at=None,
    llm_exportable: bool = True,
    sensitivity: str = "INTERNAL",
    supersedes=None,
):
    return {
        "schema": "bcp.memory_claim/1",
        "claim_id": claim_id,
        "project_id": project,
        "scope": scope,
        "memory_key": key,
        "category": category,
        "payload": value if value is not None else {"value": claim_id},
        "evidence_class": evidence,
        "source": "PHASE6_TEST",
        "authority": "TEST",
        "provenance": "repo://phase6/tests",
        "source_revision": "phase6-test",
        "source_hash": "a" * 64,
        "sensitivity": sensitivity,
        "llm_exportable": llm_exportable,
        "pinned": pinned,
        "expires_at": expires_at,
        "supersedes_claim_id": supersedes,
        "idempotency_key": idem or ("idem-" + claim_id),
        "observed_at": observed_at,
    }


class MemoryFabricTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CriticalStore(pathlib.Path(self.tmp.name) / "bcp.sqlite3")
        self.memory = MemoryFabric(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_user_memory_requires_privileged_evidence(self):
        bad = claim(
            "mcl-user-model-0001",
            scope="USER_MEMORY",
            key="preference.output",
            evidence="MODEL_PROPOSED",
            category="NORMATIVE",
        )
        with self.assertRaises(ValueError):
            self.memory.admit(bad, owner_id="model")
        self.assertEqual(self.store.list_states("memory/"), [])

        good = claim(
            "mcl-user-declared-0001",
            scope="USER_MEMORY",
            key="preference.output",
            evidence="USER_DECLARED",
            category="NORMATIVE",
            value={"concise": True},
            pinned=True,
        )
        receipt = self.memory.admit(good, owner_id="user")
        self.assertEqual(receipt["result"], "ADMITTED")
        self.assertEqual(receipt["canonical"]["payload"], {"concise": True})

    def test_lower_rank_claim_is_rejected_without_changing_canonical_hash(self):
        strong = claim(
            "mcl-machine-verified-0001",
            evidence="MACHINE_VERIFIED",
            value={"version": "2.0"},
        )
        first = self.memory.admit(strong, owner_id="machine")
        before = self.memory.canonical("BCP_CORE")[0]

        weaker = claim(
            "mcl-cache-weaker-0001",
            evidence="CACHE",
            value={"version": "1.0"},
            observed_at="2026-10-06T14:01:00Z",
        )
        second = self.memory.admit(weaker, owner_id="cache")
        after = self.memory.canonical("BCP_CORE")[0]

        self.assertEqual(first["result"], "ADMITTED")
        self.assertEqual(second["result"], "REJECTED")
        self.assertEqual(after["payload"], {"version": "2.0"})
        self.assertEqual(before["slot_content_hash"], after["slot_content_hash"])
        self.assertNotEqual(before["slot_state_hash"], after["slot_state_hash"])

    def test_equal_rank_can_supersede_and_inherits_supersession_link(self):
        self.memory.admit(
            claim("mcl-source-one-0001", evidence="SOURCE_VERIFIED", value={"v": 1}),
            owner_id="writer-a",
        )
        second = self.memory.admit(
            claim(
                "mcl-source-two-0001",
                evidence="SOURCE_VERIFIED",
                value={"v": 2},
                observed_at="2026-10-06T14:02:00Z",
            ),
            owner_id="writer-b",
        )
        self.assertEqual(second["result"], "ADMITTED")
        self.assertEqual(second["canonical"]["payload"], {"v": 2})
        self.assertEqual(second["claim"]["supersedes_claim_id"], "mcl-source-one-0001")

    def test_pinned_high_rank_rejects_lower_rank(self):
        self.memory.admit(
            claim(
                "mcl-pinned-system-0001",
                scope="POLICY",
                key="policy.zero_usd",
                evidence="SYSTEM_POLICY",
                category="NORMATIVE",
                pinned=True,
                value={"budget_usd": 0},
            ),
            owner_id="policy",
        )
        with self.assertRaises(ValueError):
            # POLICY + SOURCE_VERIFIED is rejected before persistence.
            self.memory.admit(
                claim(
                    "mcl-policy-source-0001",
                    scope="POLICY",
                    key="policy.zero_usd",
                    evidence="SOURCE_VERIFIED",
                    category="NORMATIVE",
                    value={"budget_usd": 10},
                ),
                owner_id="source",
            )
        current = self.memory.canonical("BCP_CORE", scopes=["POLICY"])[0]
        self.assertEqual(current["payload"], {"budget_usd": 0})

    def test_idempotency_replay_does_not_roll_back_later_canonical(self):
        one = claim("mcl-idem-one-0001", value={"v": 1}, idem="idem-memory-one")
        self.memory.admit(one, owner_id="one")
        self.memory.admit(
            claim(
                "mcl-idem-two-0001",
                value={"v": 2},
                idem="idem-memory-two",
                observed_at="2026-10-06T14:02:00Z",
            ),
            owner_id="two",
        )
        replay = self.memory.admit(one, owner_id="replay")
        self.assertEqual(replay["result"], "ALREADY_RECORDED")
        self.assertEqual(self.memory.canonical("BCP_CORE")[0]["payload"], {"v": 2})
        self.assertEqual(len(self.memory.claim_ledger("BCP_CORE")), 2)

    def test_idempotency_collision_fails_closed(self):
        one = claim("mcl-idem-collision-a", idem="idem-shared-claim", value={"v": 1})
        self.memory.admit(one, owner_id="one")
        two = claim(
            "mcl-idem-collision-b",
            idem="idem-shared-claim",
            value={"v": 2},
            observed_at="2026-10-06T14:03:00Z",
        )
        with self.assertRaises(MemoryClaimConflict):
            self.memory.admit(two, owner_id="two")

    def test_invalid_explicit_supersedes_fails_closed(self):
        self.memory.admit(claim("mcl-valid-first-0001"), owner_id="one")
        bad = claim(
            "mcl-invalid-super-0001",
            supersedes="mcl-does-not-exist",
            observed_at="2026-10-06T14:03:00Z",
        )
        with self.assertRaises(MemoryClaimConflict):
            self.memory.admit(bad, owner_id="two")

    def test_secret_no_store_never_reaches_critical_store(self):
        secret = claim(
            "mcl-secret-no-store-0001",
            key="secret.api_key",
            sensitivity="SECRET_NO_STORE",
            llm_exportable=False,
            value={"token": "must-not-persist"},
        )
        with self.assertRaises(MemoryAdmissionHold):
            self.memory.admit(secret, owner_id="secret-source")
        self.assertEqual(self.store.list_states("memory/"), [])

    def test_expired_memory_is_not_canonical_projection(self):
        self.memory.admit(
            claim(
                "mcl-expired-0001",
                key="operating.old_state",
                scope="OPERATING_STATE",
                evidence="MACHINE_READBACK",
                expires_at="2026-10-06T14:00:01Z",
                observed_at="2026-10-06T14:00:00Z",
            ),
            owner_id="machine",
        )
        self.assertEqual(self.memory.canonical("BCP_CORE"), [])

    def test_cross_project_isolation(self):
        self.memory.admit(
            claim("mcl-bcp-only-0001", project="BCP_CORE", key="private.bcp"),
            owner_id="bcp",
        )
        self.memory.admit(
            claim("mcl-med-only-0001", project="MED_REBUILD", key="private.med"),
            owner_id="med",
        )
        bcp = self.memory.canonical("BCP_CORE")
        med = self.memory.canonical("MED_REBUILD")
        self.assertEqual({x["memory_key"] for x in bcp}, {"private.bcp"})
        self.assertEqual({x["memory_key"] for x in med}, {"private.med"})

    def test_claim_history_is_chronicle_payload_not_only_hashes(self):
        self.memory.admit(claim("mcl-history-one-0001", value={"v": 1}), owner_id="one")
        self.memory.admit(
            claim(
                "mcl-history-two-0001",
                value={"v": 2},
                observed_at="2026-10-06T14:02:00Z",
            ),
            owner_id="two",
        )
        ledger = self.memory.claim_ledger("BCP_CORE")
        self.assertEqual(len(ledger), 2)
        self.assertTrue(all("state" in x and "reason" in x for x in ledger))


if __name__ == "__main__":
    unittest.main()
