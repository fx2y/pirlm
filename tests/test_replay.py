from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tests.common import run_cli


class ReplayTests(unittest.TestCase):
    def test_replay_mode_does_not_execute_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            live_out = base / "live"
            replay_out = base / "replay"

            live = run_cli(program="tests/prog_ok.py", out_dir=live_out)
            self.assertEqual(live.returncode, 0, live.stderr)

            replay_env = dict(os.environ)
            replay_env["PIRML_BLOCK_TOOLS"] = "1"
            replay = run_cli(
                program="tests/prog_ok.py",
                out_dir=replay_out,
                replay=live_out / "trace.ndjson",
                env=replay_env,
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)

            self.assertEqual(
                (live_out / "final.json").read_bytes(),
                (replay_out / "final.json").read_bytes(),
            )

    def test_final_and_trace_are_byte_stable_across_three_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            finals: list[bytes] = []
            traces: list[bytes] = []
            for idx in range(3):
                out_dir = base / f"run-{idx}"
                completed = run_cli(program="tests/prog_ok.py", out_dir=out_dir)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                finals.append((out_dir / "final.json").read_bytes())
                traces.append((out_dir / "trace.ndjson").read_bytes())

            self.assertEqual(finals[0], finals[1])
            self.assertEqual(finals[1], finals[2])
            self.assertEqual(traces[0], traces[1])
            self.assertEqual(traces[1], traces[2])


if __name__ == "__main__":
    unittest.main()
