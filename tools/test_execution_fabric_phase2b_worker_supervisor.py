from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
sys.path.insert(0, str(RUNTIME))

from worker_supervisor import (  # noqa: E402
    MAX_INLINE_INPUT_BYTES,
    WorkerIsolationError,
    WorkerPolicy,
    WorkerSupervisor,
    WorkerTimeout,
    field_policy_for_mode,
)


class WorkerSupervisorTests(unittest.TestCase):
    def setUp(self):
        # CI is Linux. Real Windows Job Object behavior remains a Windows field/platform gate.
        self.sup = WorkerSupervisor(allow_non_windows_test_mode=True)

    def policy(self, **kw):
        base = dict(
            name="unit",
            timeout_seconds=3.0,
            process_memory_mib=64,
            job_memory_mib=72,
            require_windows_job_object=True,
        )
        base.update(kw)
        return WorkerPolicy(**base)

    def test_success_and_output_capture(self):
        r = self.sup.run([sys.executable, "-c", "print('ok')"], self.policy())
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), b"ok")
        self.assertFalse(r.timed_out)

    def test_inline_stdin_is_delivered_after_bootstrap_gate(self):
        r = self.sup.run(
            [sys.executable, "-c", "import sys; data=sys.stdin.buffer.read(); sys.stdout.buffer.write(data[::-1])"],
            self.policy(),
            input_bytes=b"abcdef",
        )
        self.assertEqual(r.stdout, b"fedcba")

    def test_nonzero_exit_is_observable(self):
        r = self.sup.run(
            [sys.executable, "-c", "import sys; print('bad', file=sys.stderr); sys.exit(7)"],
            self.policy(),
        )
        self.assertEqual(r.returncode, 7)
        self.assertIn(b"bad", r.stderr)

    def test_timeout_kills_worker(self):
        with self.assertRaises(WorkerTimeout) as cm:
            self.sup.run(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                self.policy(timeout_seconds=0.2),
            )
        result = cm.exception.args[0]
        self.assertTrue(result.timed_out)
        self.assertEqual(result.returncode, 124)
        self.assertIn(b"CHATGPT_PC_WORKER_TIMEOUT", result.stderr)

    def test_large_output_is_stream_drained_and_bounded(self):
        # Large enough to overflow a normal pipe many times; bootstrap must drain continuously.
        r = self.sup.run(
            [sys.executable, "-c", "import sys; sys.stdout.write('x'*(2*1024*1024))"],
            self.policy(max_stdout_bytes=4096),
        )
        self.assertLessEqual(len(r.stdout), 4096)
        self.assertIn(b"TRUNCATED_BY_CHATGPT_PC_WORKER_BOOTSTRAP", r.stdout)

    def test_inline_input_cap_prevents_plan_memory_bloat(self):
        with self.assertRaises(ValueError):
            self.sup.run(
                [sys.executable, "-c", "pass"],
                self.policy(),
                input_bytes=b"x" * (MAX_INLINE_INPUT_BYTES + 1),
            )

    def test_bootstrap_does_not_start_work_without_plan(self):
        bootstrap = RUNTIME / "worker_bootstrap.py"
        p = subprocess.run(
            [sys.executable, "-I", str(bootstrap)],
            input=b"",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=3,
        )
        self.assertEqual(p.returncode, 125)
        self.assertIn(b"CHATGPT_PC_WORKER_BOOTSTRAP_ERROR", p.stderr)

    def test_policy_caps_match_field_modes(self):
        expected = {
            "GREEN": (192, 224),
            "AMBER": (96, 112),
            "RED": (64, 72),
            "CRITICAL": (48, 56),
        }
        for mode, caps in expected.items():
            p = field_policy_for_mode("x", mode, 1.0)
            self.assertEqual((p.process_memory_mib, p.job_memory_mib), caps)

    def test_policy_rejects_invalid_limits(self):
        with self.assertRaises(ValueError):
            WorkerPolicy(
                name="x",
                timeout_seconds=1,
                process_memory_mib=100,
                job_memory_mib=50,
            ).validate()

    def test_job_object_is_required_by_default_outside_test_mode(self):
        if sys.platform.startswith("win"):
            self.skipTest("non-Windows contract test")
        sup = WorkerSupervisor(allow_non_windows_test_mode=False)
        with self.assertRaises(WorkerIsolationError):
            sup.run([sys.executable, "-c", "print('x')"], self.policy())


if __name__ == "__main__":
    unittest.main()
