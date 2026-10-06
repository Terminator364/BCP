from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"
sys.path.insert(0, str(WINDOWS))

from execution_fabric.legacy_error_ledger import load_error_ledger_candidates  # noqa: E402


class LegacyErrorLedgerProjectionTests(unittest.TestCase):
    def test_historical_errors_are_candidate_knowledge_not_executable_authority(self):
        rows = load_error_ledger_candidates(ROOT / ".project-memory" / "ERROR_LEDGER.jsonl")
        self.assertGreaterEqual(len(rows), 5)
        self.assertTrue(all(r["executable"] is False for r in rows))
        self.assertTrue(all(r["recipe_status"] == "CANDIDATE_ONLY" for r in rows))
        self.assertTrue(all(r["field_certified"] is False for r in rows))

    def test_known_lifecycle_duplication_incident_is_discoverable_but_not_promoted(self):
        rows = load_error_ledger_candidates(ROOT / ".project-memory" / "ERROR_LEDGER.jsonl")
        row = next(r for r in rows if r["legacy_error_id"] == "BCP-ARCH-0003")
        self.assertIn("duplicated", row["symptom"].lower())
        self.assertTrue(row["candidate_for_recipe_authoring"])
        self.assertFalse(row["executable"])
        self.assertEqual(len(row["signature"]), 64)

    def test_fixed_incident_without_recipe_steps_cannot_be_called_validated_recipe(self):
        rows = load_error_ledger_candidates(ROOT / ".project-memory" / "ERROR_LEDGER.jsonl")
        for row in rows:
            if row["candidate_for_recipe_authoring"]:
                self.assertNotIn("steps", row)
                self.assertNotEqual(row["recipe_status"], "VALIDATED")


if __name__ == "__main__":
    unittest.main()
