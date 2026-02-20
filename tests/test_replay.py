from __future__ import annotations

import hashlib
import json
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

    def test_replay_trace_contains_hash_parity_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            live_out = base / "live"
            replay_out = base / "replay"

            live = run_cli(program="tests/prog_ok.py", out_dir=live_out)
            self.assertEqual(live.returncode, 0, live.stderr)
            replay = run_cli(
                program="tests/prog_ok.py",
                out_dir=replay_out,
                replay=live_out / "trace.ndjson",
                env={**os.environ, "PIRML_BLOCK_TOOLS": "1"},
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)

            live_sha = hashlib.sha256((live_out / "final.json").read_bytes()).hexdigest()
            replay_sha = hashlib.sha256((replay_out / "final.json").read_bytes()).hexdigest()
            self.assertEqual(live_sha, replay_sha)

            replay_frames = [
                json.loads(line)
                for line in (replay_out / "trace.ndjson").read_text(encoding="utf-8").splitlines()
                if line
            ]
            final_frame = replay_frames[-1]
            meta = final_frame.get("meta")
            self.assertIsInstance(meta, dict)
            assert isinstance(meta, dict)
            self.assertTrue(meta["replay_match"])
            self.assertEqual(meta["replay_expected_final_sha256"], live_sha)
            self.assertEqual(meta["replay_actual_final_sha256"], replay_sha)

    def test_replay_fails_when_cassette_entry_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            live_out = base / "live"
            replay_out = base / "replay"
            bad_trace = base / "bad-trace.ndjson"

            live = run_cli(program="tests/prog_ok.py", out_dir=live_out)
            self.assertEqual(live.returncode, 0, live.stderr)
            frames = [
                json.loads(line)
                for line in (live_out / "trace.ndjson").read_text(encoding="utf-8").splitlines()
                if line
            ]
            pruned = [
                frame
                for frame in frames
                if not (frame.get("op") == "result" and frame["id"] == "c00001")
            ]
            bad_trace.write_text(
                "".join(
                    json.dumps(frame, sort_keys=True, separators=(",", ":")) + "\n"
                    for frame in pruned
                ),
                encoding="utf-8",
            )

            replay = run_cli(
                program="tests/prog_ok.py",
                out_dir=replay_out,
                replay=bad_trace,
                env={**os.environ, "PIRML_BLOCK_TOOLS": "1"},
            )
            self.assertEqual(replay.returncode, 2)
            self.assertIn("Replay error: missing cassette entry for call id c00001", replay.stderr)

    def test_replay_fails_on_call_sequence_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            live_out = base / "live"
            replay_out = base / "replay"
            prog = base / "prog_bad_order.py"
            prog.write_text(
                "\n".join(
                    [
                        "import sys",
                        "from pirml.protocol import read_frame, send_final, write_frame",
                        "",
                        "write_frame(sys.stdout, {'op':'call','id':'c00999','tool':'echo','args':{'text':'x'},'ts':0})",
                        "read_frame(sys.stdin)",
                        "send_final(True, {'ok': True, 'results': [{'id':'c00999','tool':'echo','ok': True}]})",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            live = run_cli(program="tests/prog_ok.py", out_dir=live_out)
            self.assertEqual(live.returncode, 0, live.stderr)
            replay = run_cli(
                program=str(prog),
                out_dir=replay_out,
                replay=live_out / "trace.ndjson",
                env={**os.environ, "PIRML_BLOCK_TOOLS": "1"},
            )
            self.assertEqual(replay.returncode, 2)
            self.assertIn("Replay error: expected call id c00001, got c00999", replay.stderr)

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
