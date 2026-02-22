from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class TestSpec07C2ExtensionContract(unittest.TestCase):
    def test_ts_contract_passes(self):
        # C2 verified via `npx tsx` mock-pi harness
        # spec-0/00-learnings.jsonl:28
        ts_test = Path("tests/test_spec07_c2_extension_contract.ts")
        if not ts_test.exists():
            self.skipTest("TS test missing")

        cmd = ["npx", "tsx", str(ts_test)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"TS contract failed: {res.stdout}\n{res.stderr}")

    def test_runtime_bridge_live_lane(self):
        with TemporaryDirectory() as td:
            out_dir = Path(td) / "out_r1"
            cmd = [
                sys.executable,
                "-m",
                "scripts.pirml_run",
                "--prog",
                "tests/prog_ok.py",
                "--out-dir",
                str(out_dir),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            row = json.loads(res.stdout)
            self.assertTrue(row["ok"])
            self.assertTrue((out_dir / "trace.ndjson").exists())
            self.assertTrue((out_dir / "final.json").exists())


if __name__ == "__main__":
    unittest.main()
