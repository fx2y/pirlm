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
                {"op": "call", "id": "c0001", "tool": "echo", "args": {"text": "a"}, "ts": 1},
                {"op": "result", "id": "c9999", "ok": True, "output": "a", "ts": 2},
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
            big_frame = {"op": "call", "id": "c1", "tool": "echo", "args": {"text": "A" * 1000}}
            with self.assertRaisesRegex(ProtocolError, "non-result frame exceeds max_line_bytes"):
                write_frame(tmp, big_frame, max_line_bytes=100)


if __name__ == "__main__":
    unittest.main()
