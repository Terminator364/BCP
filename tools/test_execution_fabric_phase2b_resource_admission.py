from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "windows" / "execution_fabric"
sys.path.insert(0, str(RUNTIME))

from resource_admission import decide_admission  # noqa: E402


class ResourceAdmissionTests(unittest.TestCase):
    def test_green_allows_non_local_ai_classes(self):
        for rc in ["R0_TINY", "R1_LIGHT", "R2_MEDIUM", "R3_HEAVY"]:
            d = decide_admission(mode="GREEN", resource_class=rc, priority="NORMAL_PROJECT")
            self.assertTrue(d.admitted, rc)
            self.assertEqual(d.state, "ADMITTED")

    def test_local_ai_stays_policy_gated(self):
        d = decide_admission(
            mode="GREEN",
            resource_class="R4_LOCAL_AI",
            priority="NORMAL_PROJECT",
            local_ai_enabled=False,
        )
        self.assertFalse(d.admitted)
        self.assertEqual(d.state, "WAITING_POLICY")

    def test_amber_defers_medium_and_heavy(self):
        for rc in ["R2_MEDIUM", "R3_HEAVY"]:
            d = decide_admission(mode="AMBER", resource_class=rc, priority="NORMAL_PROJECT")
            self.assertFalse(d.admitted)
            self.assertEqual(d.state, "WAITING_RESOURCE")

    def test_amber_background_only_allows_tiny(self):
        tiny = decide_admission(
            mode="AMBER",
            resource_class="R0_TINY",
            priority="BACKGROUND_IMPROVEMENT",
        )
        light = decide_admission(
            mode="AMBER",
            resource_class="R1_LIGHT",
            priority="BACKGROUND_IMPROVEMENT",
        )
        self.assertTrue(tiny.admitted)
        self.assertFalse(light.admitted)

    def test_red_only_tiny_foreground_or_recovery(self):
        self.assertTrue(
            decide_admission(
                mode="RED",
                resource_class="R0_TINY",
                priority="USER_INTERACTIVE",
            ).admitted
        )
        self.assertFalse(
            decide_admission(
                mode="RED",
                resource_class="R1_LIGHT",
                priority="USER_INTERACTIVE",
            ).admitted
        )
        self.assertFalse(
            decide_admission(
                mode="RED",
                resource_class="R0_TINY",
                priority="BACKGROUND_IMPROVEMENT",
            ).admitted
        )

    def test_critical_only_allows_tiny_integrity_recovery(self):
        allowed = decide_admission(
            mode="CRITICAL",
            resource_class="R0_TINY",
            priority="CRITICAL_INTEGRITY_RECOVERY",
        )
        denied = decide_admission(
            mode="CRITICAL",
            resource_class="R0_TINY",
            priority="USER_INTERACTIVE",
        )
        self.assertTrue(allowed.admitted)
        self.assertFalse(denied.admitted)

    def test_unknown_values_fail_closed(self):
        with self.assertRaises(ValueError):
            decide_admission(mode="BLUE", resource_class="R0_TINY", priority="NORMAL_PROJECT")
        with self.assertRaises(ValueError):
            decide_admission(mode="GREEN", resource_class="R9", priority="NORMAL_PROJECT")
        with self.assertRaises(ValueError):
            decide_admission(mode="GREEN", resource_class="R0_TINY", priority="WHATEVER")


if __name__ == "__main__":
    unittest.main()
