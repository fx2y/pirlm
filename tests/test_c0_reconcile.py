from __future__ import annotations

import importlib.util
import unittest
from collections.abc import Mapping
from typing import Any

from pirml.clock import SequenceClock
from pirml.engine import run_live
from pirml.protocol import JSONObject, ProtocolError, validate_trace
from pirml.tools import ToolRegistry


class ReconcileTests(unittest.TestCase):
    def test_op_log_is_rejected(self) -> None:
        """C0.T1: op=log must be rejected by protocol validator"""
        frames: list[JSONObject] = [
            {"op": "call", "id": "c0001", "tool": "echo", "args": {}},
            {"op": "log", "msg": "hello"},
            {"op": "result", "id": "c0001", "ok": True, "output": ""},
            {"op": "final", "ok": True, "result": {"ok": True, "results": []}},
        ]
        with self.assertRaisesRegex(ProtocolError, "unknown op.*log"):
            validate_trace(frames)

    def test_id_width_five(self) -> None:
        """C0.T1: IDs must be c00001 (width 5), current is c0001"""
        from pirml.engine import new_call_id

        self.assertEqual(new_call_id(1), "c00001")

    def test_retryable_behavior_triggers_retry(self) -> None:
        """C3.T5: tool with retryable=true should be retried"""
        import tempfile
        from pathlib import Path

        from pirml.runtime.tools import ErrorType, ToolResult

        registry = ToolRegistry()
        fail_count = 0

        def fail_once(args: Mapping[str, Any], timeout: float | None = None) -> ToolResult:
            _ = timeout
            nonlocal fail_count
            fail_count += 1
            if fail_count == 1:
                return {
                    "ok": False,
                    "error": {
                        "type": ErrorType.EXECUTION_ERROR,
                        "msg": "retryable failure",
                        "retryable": True,
                    },
                }
            return {"ok": True, "output": "finally success"}

        registry.register("fail", fail_once)

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tmp:
            tmp.write("from pirml.protocol import call, send_final\n")
            tmp.write("def main():\n")
            tmp.write("    call('fail', {})\n")
            tmp.write("    send_final(True, {'ok': True, 'results': []})\n")
            tmp.write("if __name__ == '__main__': main()\n")
            tmp_path = Path(tmp.name)

        try:
            output = run_live(tmp_path, registry, SequenceClock(1700000000), 8192)

            # We expect 2 result frames for 'fail' if retry happened?
            # No, supervisor retries internally, it only sends ONE result to the program.
            # Wait, if supervisor retries, it should only send the FINAL result to the program.
            # Let's check my impl in exec.py

            self.assertEqual(fail_count, 2, "Should have retried the tool call")

            # Check frames
            results = [f for f in output.frames if f.get("op") == "result"]
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].get("ok"))
            self.assertEqual(results[0].get("output"), "finally success")
            self.assertEqual(results[0].get("meta", {}).get("retries"), 1)

        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_subprocess_supervisor_usage(self) -> None:
        """C0.T5: supervisor must use subprocess.Popen (pending impl)"""
        # This is a placeholder for the architectural change in C2
        # We'll check if pirml.runtime.exec exists and uses Popen
        spec = importlib.util.find_spec("pirml.runtime.exec")
        self.assertIsNotNone(spec, "pirml.runtime.exec must exist (C1/C2)")


if __name__ == "__main__":
    unittest.main()
