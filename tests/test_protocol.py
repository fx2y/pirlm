from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.common import parse_stdout_frames, run_cli


class ProtocolTests(unittest.TestCase):
    def test_stdout_ndjson_single_final_and_result_id_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            completed = run_cli(program="tests/prog_ok.py", out_dir=out_dir)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            frames = parse_stdout_frames(completed.stdout)
            self.assertGreater(len(frames), 0)

            call_ids: set[str] = set()
            final_count = 0
            for frame in frames:
                op = frame["op"]
                if op == "call":
                    call_ids.add(frame["id"])
                elif op == "result":
                    self.assertIn(frame["id"], call_ids)
                elif op == "final":
                    final_count += 1
            self.assertEqual(final_count, 1)

    def test_parallel_fan_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            completed = run_cli(program="tests/prog_parallel.py", out_dir=out_dir)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            frames = parse_stdout_frames(completed.stdout)

            # Expect 3 calls and 3 results (any order) + 1 final
            calls = [f for f in frames if f["op"] == "call"]
            results = [f for f in frames if f["op"] == "result"]
            finals = [f for f in frames if f["op"] == "final"]

            self.assertEqual(len(calls), 3)
            self.assertEqual(len(results), 3)
            self.assertEqual(len(finals), 1)

            final = finals[0]
            self.assertTrue(final["ok"])
            self.assertEqual(len(final["result"]["output"]), 3)
            self.assertIn("msg-0", final["result"]["output"])
            self.assertIn("msg-1", final["result"]["output"])
            self.assertIn("msg-2", final["result"]["output"])

    def test_unknown_result_id_is_hard_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "trace.ndjson"
            bad_lines: list[dict[str, object]] = [
                {"op": "call", "id": "c00001", "tool": "echo", "args": {"text": "a"}, "ts": 1},
                {"op": "result", "id": "c99999", "ok": True, "output": "a", "ts": 2},
                {"op": "final", "ok": True, "result": {"ok": True, "results": []}, "ts": 3},
            ]
            trace.write_text(
                "\n".join(json.dumps(line, sort_keys=True) for line in bad_lines) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.proto_lint",
                    "--trace",
                    str(trace),
                ],
                capture_output=True,
                check=False,
                text=True,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("unknown result id", completed.stderr)

    def test_global_timeout_reached(self) -> None:
        # Program that sleeps in an infinite loop
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            prog = base / "prog_hang.py"
            prog.write_text(
                "\n".join(
                    [
                        "import time",
                        "import sys",
                        "from pirml.protocol import read_frame",
                        "while True:",
                        "    time.sleep(1)",
                        "    # Just to keep it from dying too fast",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = run_cli(program=str(prog), out_dir=base, timeout=0.1)
            self.assertEqual(completed.returncode, 2)
            self.assertIn("global timeout reached (0.1s)", completed.stderr)

    def test_duplicate_final_is_hard_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "trace.ndjson"
            bad_lines: list[dict[str, object]] = [
                {"op": "final", "ok": True, "result": {"ok": True, "results": []}, "ts": 1},
                {"op": "final", "ok": True, "result": {"ok": True, "results": []}, "ts": 2},
            ]
            trace.write_text(
                "\n".join(json.dumps(line, sort_keys=True) for line in bad_lines) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, "-m", "scripts.proto_lint", "--trace", str(trace)],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertRegex(
                completed.stderr,
                r"(frame after final|final frame must be last)",
            )

    def test_non_result_overflow_is_hard_fail(self) -> None:
        # Non-result frames cannot be truncated and must fail if they exceed max_line_bytes
        from pirml.runtime.rpc import ProtocolError, write_frame

        with tempfile.TemporaryFile(mode="w") as tmp:
            big_frame = {"op": "call", "id": "c00001", "tool": "echo", "args": {"text": "A" * 1000}}
            with self.assertRaisesRegex(ProtocolError, "non-result frame exceeds max_line_bytes"):
                write_frame(tmp, big_frame, max_line_bytes=100)

    def test_G1_fatal_path_persists_artifacts(self) -> None:
        """G1: fatal path drops artifacts (trace/final)"""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            # Program that crashes immediately without sending final
            prog = out_dir / "crash.py"
            prog.write_text("import sys; sys.exit(1)\n", encoding="utf-8")

            completed = run_cli(program=str(prog), out_dir=out_dir)
            self.assertNotEqual(completed.returncode, 0)

            # Check if artifacts exist
            self.assertTrue((out_dir / "trace.ndjson").exists(), "trace.ndjson missing on crash")
            self.assertTrue((out_dir / "final.json").exists(), "final.json missing on crash")

            final = json.loads((out_dir / "final.json").read_text())
            self.assertFalse(final["ok"], "final.ok should be false on crash")

    def test_G2_global_timeout_during_tool_dispatch(self) -> None:
        """G2: global timeout only polled in read loop; hang in tool dispatch bypasses it"""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            prog = out_dir / "hang_in_tool.py"
            prog.write_text(
                "from pirml.protocol import call, send_final\n"
                "call('bash', {'command': 'sleep 5'})\n"
                "send_final(True, {'ok': True, 'results': []})\n",
                encoding="utf-8",
            )

            import time

            start = time.time()
            completed = run_cli(program=str(prog), out_dir=out_dir, timeout=0.5)
            duration = time.time() - start

            self.assertEqual(completed.returncode, 2)
            self.assertLess(duration, 2.0, f"Timeout took too long: {duration}s")

    def test_G3_id_policy_enforcement(self) -> None:
        """G3: validator accepts arbitrary/non-monotonic ids"""
        from pirml.protocol import ProtocolError, StreamValidator

        # Test non-monotonic
        v = StreamValidator()
        v.validate_frame({"op": "call", "id": "c00002", "tool": "echo", "args": {}, "ts": 1})
        with self.assertRaisesRegex(ProtocolError, "non-monotonic"):
            v.validate_frame({"op": "call", "id": "c00001", "tool": "echo", "args": {}, "ts": 2})

        # Test bad format
        v = StreamValidator()
        with self.assertRaisesRegex(ProtocolError, "invalid id format"):
            v.validate_frame({"op": "call", "id": "z1", "tool": "echo", "args": {}, "ts": 1})

    def test_G4_final_json_compact(self) -> None:
        """G4: runtime trusts prog final.result; leaks raw/debug fields"""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            prog = out_dir / "bloated_final.py"
            prog.write_text(
                "from pirml.protocol import send_final\n"
                "send_final(True, {'ok': True, 'results': [], 'debug_leak': 'SHOULD_NOT_BE_IN_FINAL_JSON'})\n",
                encoding="utf-8",
            )

            completed = run_cli(program=str(prog), out_dir=out_dir)
            self.assertEqual(completed.returncode, 0)

            final = json.loads((out_dir / "final.json").read_text())
            self.assertNotIn("debug_leak", final)
            self.assertIn("ok", final)

    def test_G8_shared_id_allocator(self) -> None:
        """G8: call() and AsyncRpcClient use separate counters"""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            prog = out_dir / "mixed_calls.py"
            prog.write_text(
                "import asyncio\n"
                "from pirml.runtime.rpc import call, send_final, AsyncRpcClient\n"
                "async def main():\n"
                "    call('echo', {'text': 'sync'})\n"
                "    async with AsyncRpcClient() as client:\n"
                "        await client.call('echo', {'text': 'async'})\n"
                "    send_final(True, {'ok': True, 'results': []})\n"
                "asyncio.run(main())\n",
                encoding="utf-8",
            )

            completed = run_cli(program=str(prog), out_dir=out_dir)
            self.assertEqual(completed.returncode, 0, completed.stderr)

            frames = [
                json.loads(line) for line in (out_dir / "trace.ndjson").read_text().splitlines()
            ]
            call_ids = [f["id"] for f in frames if f["op"] == "call"]
            self.assertEqual(len(set(call_ids)), 2, f"Duplicate IDs found: {call_ids}")
            self.assertEqual(call_ids, ["c00001", "c00002"])


if __name__ == "__main__":
    unittest.main()
