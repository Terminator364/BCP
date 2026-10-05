from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"
sys.path.insert(0, str(WINDOWS))

from execution_fabric.resource_admission import (  # noqa: E402
    MB,
    classify_mode,
    decide,
    worker_policy,
)
from execution_fabric.worker_supervisor import WorkerSupervisor, WorkerTimeout  # noqa: E402


class ResourceAdmissionTests(unittest.TestCase):
    def test_g6_constrained_pc_thresholds(self):
        total = 4 * 1024 * MB
        self.assertEqual(classify_mode(total, 1200 * MB, 70, 5 * 1024 * MB), "GREEN")
        self.assertEqual(classify_mode(total, 700 * MB, 80, 5 * 1024 * MB), "AMBER")
        self.assertEqual(classify_mode(total, 250 * MB, 91, 5 * 1024 * MB), "RED")
        self.assertEqual(classify_mode(total, 120 * MB, 96, 5 * 1024 * MB), "CRITICAL")

    def test_admission_matrix(self):
        self.assertTrue(decide("R3_HEAVY", mode="GREEN").allowed)
        self.assertFalse(decide("R2_MEDIUM", mode="AMBER").allowed)
        self.assertTrue(decide("R1_LIGHT", mode="AMBER").allowed)
        self.assertFalse(decide("R1_LIGHT", mode="RED").allowed)
        self.assertTrue(decide("R0_TINY", mode="RED").allowed)
        self.assertFalse(decide("R0_TINY", mode="CRITICAL").allowed)
        self.assertTrue(decide("R0_TINY", mode="CRITICAL", essential=True).allowed)

    def test_background_is_more_restrictive(self):
        self.assertTrue(decide("R1_LIGHT", mode="GREEN", background=True).allowed)
        d = decide("R1_LIGHT", mode="AMBER", background=True)
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "BACKGROUND_HOLD_AMBER")

    def test_local_ai_is_disabled_in_phase2(self):
        for mode in ("GREEN", "AMBER", "RED", "CRITICAL"):
            d = decide("R4_LOCAL_AI", mode=mode, local_ai_enabled=True)
            self.assertFalse(d.allowed)
            self.assertEqual(d.reason, "LOCAL_AI_DISABLED_PHASE2")
            self.assertFalse(d.local_ai_enabled)

    def test_worker_policy_requires_windows_job_object(self):
        d, p = worker_policy("light-test", "R1_LIGHT", 5, mode="GREEN")
        self.assertTrue(d.allowed)
        self.assertIsNotNone(p)
        self.assertTrue(p.require_windows_job_object)
        self.assertLessEqual(p.process_memory_mib, 96)

    def test_worker_supervisor_non_windows_simulation(self):
        d, p = worker_policy("sim-echo", "R0_TINY", 5, mode="GREEN")
        self.assertTrue(d.allowed)
        sup = WorkerSupervisor(allow_non_windows_test_mode=True)
        result = sup.run(
            [sys.executable, "-c", "print('BCP_WORKER_OK')"],
            p,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"BCP_WORKER_OK", result.stdout)
        self.assertIn(result.isolation, {"NON_WINDOWS_TEST_MODE", "WINDOWS_JOB_OBJECT_START_GATED"})

    def test_worker_timeout_is_bounded(self):
        d, p = worker_policy("sim-timeout", "R0_TINY", 0.1, mode="GREEN")
        self.assertTrue(d.allowed)
        sup = WorkerSupervisor(allow_non_windows_test_mode=True)
        with self.assertRaises(WorkerTimeout):
            sup.run(
                [sys.executable, "-c", "import time; time.sleep(2)"],
                p,
            )


if __name__ == "__main__":
    unittest.main()
