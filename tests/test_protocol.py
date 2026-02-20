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

    def test_max_line_bytes_enforced_with_explicit_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            completed = run_cli(program="tests/prog_long.py", out_dir=out_dir, max_line_bytes=300)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            frames = parse_stdout_frames(completed.stdout)
            result_frames = [frame for frame in frames if frame["op"] == "result"]
            self.assertEqual(len(result_frames), 1)

            result = result_frames[0]
            self.assertTrue(result["truncated"])
            self.assertGreater(result["truncated_bytes"], 0)

            for line in completed.stdout.splitlines():
                self.assertLessEqual(len(line.encode("utf-8")), 300)


if __name__ == "__main__":
    unittest.main()
