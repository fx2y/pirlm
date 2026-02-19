from __future__ import annotations

import unittest

from pirml.clock import SequenceClock
from pirml.engine import run_live
from pirml.protocol import ProtocolError, validate_trace
from pirml.tools import ToolRegistry


class ReconcileTests(unittest.TestCase):
    def test_op_log_is_rejected(self) -> None:
        """C0.T1: op=log must be rejected by protocol validator"""
        frames = [
            {"op": "call", "id": "c0001", "tool": "echo", "args": {}},
            {"op": "log", "msg": "hello"},
            {"op": "result", "id": "c0001", "ok": True, "output": ""},
            {"op": "final", "ok": True, "result": {"ok": True, "results": []}}
        ]
        with self.assertRaisesRegex(ProtocolError, "unknown op.*log"):
            validate_trace(frames)

    @unittest.expectedFailure
    def test_id_width_five(self) -> None:
        """C0.T1: IDs must be c00001 (width 5), current is c0001"""
        # This will fail because current id width is 4
        from pirml.engine import _new_call_id
        self.assertEqual(_new_call_id(1), "c00001")

    @unittest.expectedFailure
    def test_retryable_behavior_triggers_retry(self) -> None:
        """C0.T5: tool with retryable=true should be retried (pending)"""
        # We'll need a way to inject a failing tool that then succeeds or just count calls
        # This is pending the C2/C3 implementation of the retry loop
        registry = ToolRegistry()
        def fail_once(args):
            raise Exception("retryable failure") # Current engine doesn't know about retryable
        
        registry.register("fail", fail_once)
        program = [{"tool": "fail", "args": {}}]
        
        # This will fail because it only tries once and returns ok=False
        output = run_live(program, registry, SequenceClock(), 8192)
        
        # We expect at least 2 call frames for 'fail' if retry happened
        call_count = len([f for f in output.frames if f.get("op") == "call" and f.get("tool") == "fail"])
        self.assertGreater(call_count, 1, "Should have retried the tool call")

    @unittest.expectedFailure
    def test_subprocess_supervisor_usage(self) -> None:
        """C0.T5: supervisor must use subprocess.Popen (pending impl)"""
        # This is a placeholder for the architectural change in C2
        # We'll check if pirml.runtime.exec exists and uses Popen
        import importlib.util
        spec = importlib.util.find_spec("pirml.runtime.exec")
        self.assertIsNotNone(spec, "pirml.runtime.exec must exist (C1/C2)")

if __name__ == "__main__":
    unittest.main()
