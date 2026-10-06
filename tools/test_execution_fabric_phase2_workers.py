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
    def test_mbpmc_normal_high_ram_band(self):
        total = 4 * 1024 * MB
        disk = 5 * 1024 * MB
        # 80-95% load is the observed normal envelope on MBMPC when real headroom exists.
        self.assertEqual(classify_mode(total, 820 * MB, 80, disk, 2 * 1024 * MB), "GREEN")
        self.assertEqual(classify_mode(total, 410 * MB, 90, disk, 1500 * MB), "GREEN")
        self.assertEqual(classify_mode(total, 205 * MB, 95, disk, 900 * MB), "GREEN")
        self.assertEqual(classify_mode(total, 150 * MB, 96, disk, 700 * MB), "AMBER")
        self.assertEqual(classify_mode(total, 90 * MB, 98, disk, 400 * MB), "RED")
        self.assertEqual(classify_mode(total, 60 * MB, 99, disk, 200 * MB), "CRITICAL")

    def test_pagefile_and_disk_headroom_override_normal_load(self):
        total = 4 * 1024 * MB
        disk = 5 * 1024 * MB
        self.assertEqual(classify_mode(total, 500 * MB, 90, disk, 400 * MB), "AMBER")
        self.assertEqual(classify_mode(total, 500 * MB, 90, disk, 200 * MB), "RED")
        self.assertEqual(classify_mode(total, 500 * MB, 90, disk, 100 * MB), "CRITICAL")
        self.assertEqual(classify_mode(total, 500 * MB, 90, 900 * MB, 2 * 1024 * MB), "RED")

    def test_admission_matrix(self):
        self.assertTrue(decide("R3_HEAVY", mode="GREEN").allowed)
        self.assertFalse(decide("R2_MEDIUM", mode="AMBER").allowed)
        self.assertTrue(decide("R1_LIGHT", mode="AMBER").allowed)
        self.assertFalse(decide("R1_LIGHT", mode="RED").allowed)
        self.assertTrue(decide("R0_TINY", mode="RED").allowed)
        self.assertFalse(decide("R0_TINY", mode="CRITICAL").allowed)
        self.assertTrue(decide("R0_TINY", mode="CRITICAL", essential=True).allowed)

    def test_green_mode_still_checks_real_worker_headroom_when_known(self):
        # GREEN does not mean a heavy worker may consume the user's last free MiB.
        d = decide("R3_HEAVY", mode="GREEN", available_bytes=300 * MB)
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "RESOURCE_HOLD_HEADROOM")

        d = decide("R1_LIGHT", mode="GREEN", available_bytes=220 * MB)
        self.assertTrue(d.allowed)

    def test_95_percent_is_not_automatically_red(self):
        total = 4 * 1024 * MB
        self.assertEqual(
            classify_mode(total, 205 * MB, 95, 5 * 1024 * MB, 900 * MB),
            "GREEN",
        )

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
