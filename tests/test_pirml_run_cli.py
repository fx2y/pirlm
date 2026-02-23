from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PirmlRunCliTests(unittest.TestCase):
    def _run(self, out_dir: Path, *, human: bool) -> subprocess.CompletedProcess[str]:
        cmd = [
            sys.executable,
            "-m",
            "scripts.pirml_run",
            "--prog",
            "tests/prog_ok.py",
            "--out-dir",
            str(out_dir),
            "--project-root",
            str(out_dir.parent),
        ]
        if human:
            cmd.append("--human")
        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    def test_default_outputs_json_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            res = self._run(out_dir, human=False)
            self.assertEqual(res.returncode, 0, res.stderr)
            payload = json.loads(res.stdout)
            self.assertIn("runId", payload)
            self.assertIn("ok", payload)
            self.assertIn("summary", payload)
            self.assertIn("pointer", payload)

    def test_human_outputs_concise_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            res = self._run(out_dir, human=True)
            self.assertEqual(res.returncode, 0, res.stderr)
            lines = [line for line in res.stdout.splitlines() if line.strip()]
            self.assertTrue(any(line.startswith("runId: ") for line in lines))
            self.assertTrue(any(line.startswith("ok: ") for line in lines))
            self.assertTrue(any(line.startswith("trace: ") for line in lines))
            self.assertTrue(any(line.startswith("final: ") for line in lines))


if __name__ == "__main__":
    unittest.main()
