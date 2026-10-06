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
from execution_fabric.project_registry import ProjectRegistry  # noqa: E402
from execution_fabric.project_adapter_registry import (  # noqa: E402
    ProjectAdapterAmbiguous,
    ProjectAdapterCollision,
    ProjectAdapterNotFound,
    ProjectAdapterRegistry,
    validate_adapter,
)


CATALOG = (
    ROOT / "windows" / "execution_fabric" / "catalogs" / "phase8_cross_project.json"
)


class Phase8CrossProjectAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CriticalStore(pathlib.Path(self.tmp.name) / "bcp.sqlite3")
        self.projects = ProjectRegistry(self.store)
        self.adapters = ProjectAdapterRegistry(self.store)
        self.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    def tearDown(self):
        self.tmp.cleanup()

    def seed(self):
        for project in self.catalog["projects"]:
            self.projects.put(project, owner_id="phase8-test")
        for adapter in self.catalog["adapters"]:
            self.adapters.put(adapter, owner_id="phase8-test")

    def adapter(self, project_id: str):
        return next(x for x in self.catalog["adapters"] if x["project_id"] == project_id)

    def project(self, project_id: str):
        return next(x for x in self.catalog["projects"] if x["project_id"] == project_id)

    def test_catalog_has_exact_phase8_projects(self):
        ids = {x["project_id"] for x in self.catalog["projects"]}
        self.assertEqual(
            ids,
            {
                "TLIB",
                "EXCELLENTIA",
                "DELIVERY",
                "BUILDHUB",
                "PC_COMMAND",
                "PHONEMOUSE",
                "P2PCR95",
            },
        )
        self.assertEqual(
            {x["project_id"] for x in self.catalog["adapters"]},
            ids,
        )

    def test_all_catalog_adapters_validate_without_executable_mechanics(self):
        serialized = json.dumps(self.catalog["adapters"], sort_keys=True).casefold()
        for forbidden in (
            '"command"',
            '"argv"',
            '"shell"',
            '"script"',
            '"executable"',
            "powershell.exe",
            "cmd.exe",
        ):
            self.assertNotIn(forbidden, serialized)
        for adapter in self.catalog["adapters"]:
            validate_adapter(adapter)

    def test_catalog_registers_on_one_shared_critical_store(self):
        self.seed()
        self.assertEqual(len(self.projects.list()), 7)
        self.assertEqual(len(self.adapters.list()), 7)
        outbox = self.store.due_outbox(limit=64)
        destinations = {x["destination"] for x in outbox}
        self.assertIn("BCP_PROJECT_REGISTRY", destinations)
        self.assertIn("BCP_PROJECT_ADAPTER_REGISTRY", destinations)

    def test_excellentia_release_verify_is_bound_to_observed_manifest(self):
        self.seed()
        resolved = self.adapters.resolve("EXCELLENTIA", "RELEASE_VERIFY")
        binding = resolved["binding"]
        self.assertEqual(binding["state"], "BOUND")
        self.assertEqual(binding["provider_id"], "GITHUB_REPOSITORY")
        self.assertEqual(
            binding["input_defaults"]["repository"],
            "Terminator364/ChatGPT-PC",
        )
        self.assertEqual(
            binding["input_defaults"]["release_manifest"],
            "excellentia-study-cockpit/release/current.json",
        )

    def test_tlib_source_is_not_invented(self):
        project = self.project("TLIB")
        origin = project["origins"]["repos"][0]
        self.assertEqual(origin["status"], "UNRESOLVED")
        self.assertIsNone(origin["repository"])
        self.assertIsNone(origin["path"])
        self.seed()
        with self.assertRaises(ProjectAdapterNotFound):
            self.adapters.resolve("TLIB", "INSPECT", require_bound=True)
        waiting = self.adapters.resolve("TLIB", "INSPECT", require_bound=False)
        self.assertEqual(waiting["binding"]["state"], "WAITING_BINDING")
        self.assertEqual(waiting["binding"]["input_defaults"], {})

    def test_pc_native_operations_remain_unbound_without_local_roots(self):
        self.seed()
        for project_id in (
            "EXCELLENTIA",
            "DELIVERY",
            "BUILDHUB",
            "PC_COMMAND",
            "PHONEMOUSE",
            "P2PCR95",
        ):
            with self.assertRaises(ProjectAdapterNotFound):
                self.adapters.resolve(project_id, "HEALTHCHECK", require_bound=True)
            waiting = self.adapters.resolve(project_id, "HEALTHCHECK", require_bound=False)
            self.assertEqual(waiting["binding"]["state"], "WAITING_BINDING")

    def test_bound_repository_must_exist_in_project_record(self):
        project = self.project("PHONEMOUSE")
        adapter = self.adapter("PHONEMOUSE")
        self.projects.put(project, owner_id="writer")
        bad = json.loads(json.dumps(adapter))
        inspect = next(x for x in bad["bindings"] if x["operation"] == "INSPECT")
        inspect["input_defaults"]["repository"] = "Terminator364/Invented"
        with self.assertRaisesRegex(ValueError, "observed project repository"):
            self.adapters.put(bad, owner_id="writer")

    def test_bound_pc_operation_requires_observed_local_root(self):
        project = self.project("P2PCR95")
        adapter = self.adapter("P2PCR95")
        self.projects.put(project, owner_id="writer")
        bad = json.loads(json.dumps(adapter))
        health = next(x for x in bad["bindings"] if x["operation"] == "HEALTHCHECK")
        health["state"] = "BOUND"
        with self.assertRaisesRegex(ValueError, "observed local project root"):
            self.adapters.put(bad, owner_id="writer")

    def test_adapter_version_is_immutable(self):
        self.seed()
        adapter = self.adapter("BUILDHUB")
        replay = self.adapters.put(adapter, owner_id="replay")
        self.assertEqual(replay["revision"], 1)

        changed = json.loads(json.dumps(adapter))
        changed["notes"].append("different content")
        with self.assertRaises(ProjectAdapterCollision):
            self.adapters.put(changed, owner_id="collision")

    def test_duplicate_bound_operation_fails_closed(self):
        self.seed()
        second = json.loads(json.dumps(self.adapter("EXCELLENTIA")))
        second["adapter_id"] = "excellentia.second-adapter"
        second["version"] = "0.1.0-r3-phase8-second"
        self.adapters.put(second, owner_id="second")
        with self.assertRaises(ProjectAdapterAmbiguous):
            self.adapters.resolve("EXCELLENTIA", "INSPECT")

    def test_pc_command_state_repo_is_not_mislabeled_as_engineering_source(self):
        project = self.project("PC_COMMAND")
        self.assertEqual(project["authority"]["engineering"], "UNRESOLVED")
        origin = project["origins"]["repos"][0]
        self.assertEqual(origin["repository"], "Terminator364/PC-COMMAND-STATE")
        self.assertEqual(origin["authority"], "COMPATIBILITY")

    def test_delivery_release_verify_remains_waiting_binding(self):
        self.seed()
        with self.assertRaises(ProjectAdapterNotFound):
            self.adapters.resolve("DELIVERY", "RELEASE_VERIFY")
        waiting = self.adapters.resolve("DELIVERY", "RELEASE_VERIFY", require_bound=False)
        self.assertEqual(waiting["binding"]["state"], "WAITING_BINDING")
        self.assertEqual(waiting["binding"]["provider_id"], "DELIVERY")


if __name__ == "__main__":
    unittest.main()
