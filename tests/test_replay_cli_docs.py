from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ReplayCliDocTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "pirml", *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_replay_snippet_is_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live_out = root / "live"
            replay_out = root / "replay"

            live = self._run(
                "--prog",
                "tests/prog_ok.py",
                "--out-dir",
                str(live_out),
            )
            self.assertEqual(live.returncode, 0, live.stderr)

            replay = self._run(
                "--prog",
                "tests/prog_ok.py",
                "--replay",
                str(live_out / "trace.ndjson"),
                "--out-dir",
                str(replay_out),
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertEqual(
                (live_out / "final.json").read_bytes(),
                (replay_out / "final.json").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
