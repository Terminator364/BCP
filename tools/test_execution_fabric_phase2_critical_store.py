from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"
sys.path.insert(0, str(WINDOWS))

from execution_fabric.critical_store import (  # noqa: E402
    CriticalStore,
    FencingConflict,
    RevisionConflict,
)
from execution_fabric.local_path_policy import NonLocalStatePath  # noqa: E402


class CriticalStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = pathlib.Path(self.tmp.name) / "critical.sqlite3"
        self.store = CriticalStore(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def fence(self, stream="bcp/core", owner="writer-A"):
        return self.store.acquire_writer_fence(stream, owner)

    def test_provider_synced_hot_db_is_rejected(self):
        with self.assertRaises(NonLocalStatePath):
            CriticalStore(r"C:\\Users\\Blessing\\OneDrive\\BCP\\state.sqlite3")

    def test_critical_database_uses_wal_full_and_no_mmap(self):
        p = self.store.pragmas()
        self.assertEqual(str(p["journal_mode"]).lower(), "wal")
        self.assertEqual(int(p["synchronous"]), 2)
        self.assertEqual(int(p["mmap_size"]), 0)

    def test_transition_requires_acquired_writer_fence(self):
        with self.assertRaises(FencingConflict):
            self.store.commit_transition(
                stream_id="bcp/core",
                expected_revision=0,
                new_revision=1,
                fencing_token=1,
                payload={"x": 1},
            )

    def test_fence_tokens_are_monotonic(self):
        a = self.fence(owner="A")
        b = self.fence(owner="B")
        c = self.fence(owner="C")
        self.assertEqual((a, b, c), (1, 2, 3))
        current = self.store.current_writer_fence("bcp/core")
        self.assertEqual(current["fencing_token"], 3)
        self.assertEqual(current["owner_id"], "C")

    def test_transition_and_outbox_commit_together(self):
        fence = self.fence()
        r = self.store.commit_transition(
            stream_id="bcp/core",
            expected_revision=0,
            new_revision=1,
            fencing_token=fence,
            payload={"mission": "x", "value": 1},
            now_epoch=1000,
        )
        self.assertEqual(r.status, "DURABLE_LOCAL")
        state = self.store.get_state("bcp/core")
        self.assertEqual(state["revision"], 1)
        self.assertEqual(state["fencing_token"], fence)
        due = self.store.due_outbox(now_epoch=1000)
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["message_id"], r.outbox_message_id)
        self.assertEqual(due[0]["envelope"]["content_hash"], r.content_hash)

    def test_exact_replay_is_idempotent_while_fence_is_current(self):
        fence = self.fence()
        args = dict(
            stream_id="bcp/core",
            expected_revision=0,
            new_revision=1,
            fencing_token=fence,
            payload={"a": 1},
            now_epoch=1000,
        )
        first = self.store.commit_transition(**args)
        second = self.store.commit_transition(**args)
        self.assertTrue(second.idempotent_replay)
        self.assertEqual(first.outbox_message_id, second.outbox_message_id)
        self.assertEqual(len(self.store.history("bcp/core")), 1)

    def test_same_revision_different_payload_fails_closed(self):
        fence = self.fence()
        self.store.commit_transition(
            stream_id="bcp/core", expected_revision=0, new_revision=1,
            fencing_token=fence, payload={"a": 1}
        )
        with self.assertRaises(RevisionConflict):
            self.store.commit_transition(
                stream_id="bcp/core", expected_revision=0, new_revision=1,
                fencing_token=fence, payload={"a": 2}
            )
        self.assertEqual(self.store.get_state("bcp/core")["payload"], {"a": 1})

    def test_new_fence_immediately_revokes_old_writer_before_new_state(self):
        old = self.fence(owner="old")
        self.store.commit_transition(
            stream_id="bcp/core", expected_revision=0, new_revision=1,
            fencing_token=old, payload={"a": 1}
        )
        new = self.fence(owner="new")
        self.assertGreater(new, old)
        with self.assertRaises(FencingConflict):
            self.store.commit_transition(
                stream_id="bcp/core", expected_revision=1, new_revision=2,
                fencing_token=old, payload={"a": "stale"}
            )
        self.assertEqual(self.store.get_state("bcp/core")["revision"], 1)

    def test_revoked_writer_cannot_even_receive_idempotent_ack(self):
        old = self.fence(owner="old")
        args = dict(
            stream_id="bcp/core", expected_revision=0, new_revision=1,
            fencing_token=old, payload={"a": 1}
        )
        self.store.commit_transition(**args)
        self.fence(owner="new")
        with self.assertRaises(FencingConflict):
            self.store.commit_transition(**args)

    def test_same_current_writer_token_may_advance_multiple_revisions(self):
        fence = self.fence()
        r1 = self.store.commit_transition(
            stream_id="bcp/core", expected_revision=0, new_revision=1,
            fencing_token=fence, payload={"a": 1}
        )
        r2 = self.store.commit_transition(
            stream_id="bcp/core", expected_revision=1, new_revision=2,
            fencing_token=fence, payload={"a": 2}
        )
        self.assertEqual(r2.predecessor_hash, r1.content_hash)
        self.assertEqual(self.store.get_state("bcp/core")["revision"], 2)

    def test_new_writer_higher_fence_may_take_over(self):
        old = self.fence(owner="old")
        self.store.commit_transition(
            stream_id="bcp/core", expected_revision=0, new_revision=1,
            fencing_token=old, payload={"a": 1}
        )
        new = self.fence(owner="new")
        self.store.commit_transition(
            stream_id="bcp/core", expected_revision=1, new_revision=2,
            fencing_token=new, payload={"a": 2}
        )
        self.assertEqual(self.store.get_state("bcp/core")["fencing_token"], new)

    def test_outbox_failure_backoff_and_delivery(self):
        fence = self.store.acquire_writer_fence("mission/x", "writer")
        r = self.store.commit_transition(
            stream_id="mission/x", expected_revision=0, new_revision=1,
            fencing_token=fence, payload={"x": True}, now_epoch=100
        )
        self.store.mark_attempt_failed(r.outbox_message_id, "network down", now_epoch=100)
        self.assertEqual(self.store.due_outbox(now_epoch=101), [])
        due = self.store.due_outbox(now_epoch=102)
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["attempts"], 1)
        self.store.mark_delivered(r.outbox_message_id, delivered_epoch=103)
        self.assertEqual(self.store.due_outbox(now_epoch=9999), [])

    def test_state_and_fence_survive_close_and_reopen(self):
        fence = self.fence(owner="A")
        self.store.commit_transition(
            stream_id="bcp/core", expected_revision=0, new_revision=1,
            fencing_token=fence, payload={"durable": True}
        )
        reopened = CriticalStore(self.db)
        self.assertEqual(reopened.get_state("bcp/core")["payload"], {"durable": True})
        self.assertEqual(reopened.current_writer_fence("bcp/core")["fencing_token"], fence)
        self.assertEqual(reopened.integrity_check(), "ok")


if __name__ == "__main__":
    unittest.main()
