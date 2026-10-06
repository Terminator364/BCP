from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"
sys.path.insert(0, str(WINDOWS))

from execution_fabric.critical_store import CriticalStore  # noqa: E402
from execution_fabric.project_registry import (  # noqa: E402
    ProjectAliasAmbiguous,
    ProjectRegistry,
    ProjectRevisionConflict,
    validate_project_record,
)


def record(project_id: str, alias: str, *, updated_at: str = "2026-10-05T21:20:00Z") -> dict:
    return {
        "schema": "bcp.project_record/1",
        "project_id": project_id,
        "display_name": project_id,
        "aliases": [alias],
        "profile": "SOFTWARE_ENGINEERING",
        "status": "BINDING_INCOMPLETE",
        "authority": {
            "engineering": "GITHUB",
            "runtime": "PC",
            "artifacts": "UNRESOLVED",
            "conversation": "NON_AUTHORITATIVE",
        },
        "origins": {
            "local_roots": [{"status": "UNRESOLVED", "path": None, "authority": "UNRESOLVED"}],
            "repos": [{
                "status": "BOUND",
                "repository": "Terminator364/ChatGPT-PC",
                "branch": "main",
                "path": "example",
                "authority": "ENGINEERING",
            }],
            "drive_refs": [],
        },
        "adapters": ["GITHUB_REPOSITORY"],
        "resource_profile": {
            "resource_class": "R1_LIGHT",
            "heavy_work": False,
            "offline_capable": True,
            "background_policy": "GREEN_ONLY",
        },
        "permission_profile": {
            "max_permission_class": "P2_PROJECT_MUTATION",
            "read_allowed": True,
            "project_write_policy": "POLICY",
            "system_modify_policy": "GATED",
        },
        "update_profile": {
            "mode": "PROJECT_DEFINED",
            "rollback_required": True,
            "channel": None,
        },
        "updated_at": updated_at,
    }


class ProjectRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CriticalStore(pathlib.Path(self.tmp.name) / "bcp.sqlite3")
        self.registry = ProjectRegistry(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_register_get_list_and_alias_resolve(self):
        rec = record("MED_REBUILD", "Med Rebuild")
        receipt = self.registry.put(rec, owner_id="test")
        self.assertEqual(receipt["status"], "DURABLE_LOCAL")
        self.assertFalse(receipt["field_certified"])
        got = self.registry.get("MED_REBUILD")
        self.assertEqual(got["record"]["project_id"], "MED_REBUILD")
        self.assertEqual(got["revision"], 1)
        self.assertEqual(len(self.registry.list()), 1)
        self.assertEqual(self.registry.resolve("med rebuild")["record"]["project_id"], "MED_REBUILD")
        self.assertEqual(self.registry.resolve("med_rebuild")["record"]["project_id"], "MED_REBUILD")

    def test_identical_put_is_unchanged_without_revision_churn(self):
        rec = record("MED_REBUILD", "Med Rebuild")
        self.registry.put(rec, owner_id="writer-a")
        second = self.registry.put(rec, owner_id="writer-b")
        self.assertEqual(second["status"], "UNCHANGED")
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(self.registry.get("MED_REBUILD")["revision"], 1)

    def test_update_increments_revision_and_stale_expected_fails(self):
        rec = record("MED_REBUILD", "Med Rebuild")
        self.registry.put(rec, owner_id="writer-a")
        changed = record("MED_REBUILD", "Med Rebuild", updated_at="2026-10-05T21:21:00Z")
        changed["status"] = "ACTIVE"
        receipt = self.registry.put(changed, owner_id="writer-b", expected_revision=1)
        self.assertEqual(receipt["revision"], 2)
        with self.assertRaises(ProjectRevisionConflict):
            self.registry.put(rec, owner_id="stale", expected_revision=1)

    def test_unresolved_local_root_cannot_assert_path(self):
        rec = record("XENON", "Xenon")
        rec["origins"]["local_roots"][0]["path"] = r"C:\\Invented\\Xenon"
        with self.assertRaisesRegex(ValueError, "UNRESOLVED local root"):
            validate_project_record(rec)

    def test_partial_local_root_is_rejected(self):
        rec = record("XENON", "Xenon")
        rec["origins"]["local_roots"][0]["status"] = "PARTIAL"
        with self.assertRaisesRegex(ValueError, "invalid local_roots status"):
            validate_project_record(rec)

    def test_candidate_drive_status_is_rejected(self):
        rec = record("XENON", "Xenon")
        rec["origins"]["drive_refs"] = [{
            "status": "CANDIDATE",
            "id": None,
            "role": "ARTIFACT",
            "authority": "CANDIDATE",
        }]
        with self.assertRaisesRegex(ValueError, "invalid drive_refs status"):
            validate_project_record(rec)

    def test_unexpected_top_level_field_is_rejected(self):
        rec = record("XENON", "Xenon")
        rec["guessed_root"] = r"C:\\Invented"
        with self.assertRaisesRegex(ValueError, "unexpected project record field"):
            validate_project_record(rec)

    def test_invalid_profile_and_authority_are_rejected(self):
        rec = record("XENON", "Xenon")
        rec["profile"] = "MAGIC"
        with self.assertRaisesRegex(ValueError, "invalid project profile"):
            validate_project_record(rec)
        rec = record("XENON", "Xenon")
        rec["authority"]["runtime"] = "LAPTOP_GUESS"
        with self.assertRaisesRegex(ValueError, "invalid runtime authority"):
            validate_project_record(rec)

    def test_bound_repo_requires_repository(self):
        rec = record("XENON", "Xenon")
        rec["origins"]["repos"][0]["repository"] = None
        with self.assertRaisesRegex(ValueError, "BOUND repo"):
            validate_project_record(rec)

    def test_conversation_never_becomes_authority(self):
        rec = record("XENON", "Xenon")
        rec["authority"]["conversation"] = "CANONICAL"
        with self.assertRaisesRegex(ValueError, "conversation"):
            validate_project_record(rec)

    def test_alias_ambiguity_fails_closed(self):
        self.registry.put(record("ONE", "shared"), owner_id="one")
        self.registry.put(record("TWO", "shared"), owner_id="two")
        with self.assertRaises(ProjectAliasAmbiguous):
            self.registry.resolve("shared")

    def test_project_registry_uses_same_transactional_outbox(self):
        rec = record("MED_REBUILD", "Med Rebuild")
        receipt = self.registry.put(rec, owner_id="writer")
        due = self.store.due_outbox(limit=10)
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["message_id"], receipt["outbox_message_id"])
        self.assertEqual(due[0]["destination"], "BCP_PROJECT_REGISTRY")

    def test_med_rebuild_example_keeps_pc_root_unresolved(self):
        example = json.loads(
            (ROOT / "docs" / "examples" / "execution-fabric" / "med-rebuild.project-record.example.json")
            .read_text(encoding="utf-8")
        )
        validate_project_record(example)
        local = example["origins"]["local_roots"][0]
        self.assertEqual(local["status"], "UNRESOLVED")
        self.assertIsNone(local["path"])
        repo = example["origins"]["repos"][0]
        self.assertEqual(repo["repository"], "Terminator364/ChatGPT-PC")
        self.assertEqual(repo["path"], "med-rebuild-study-hub/v1.5-prototype")


if __name__ == "__main__":
    unittest.main()
