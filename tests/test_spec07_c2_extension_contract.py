from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
