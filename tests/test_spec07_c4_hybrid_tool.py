from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


class TestSpec07C4HybridTool(unittest.TestCase):
    def test_ts_contract_passes(self):
        # C4 verified via `npx tsx` hybrid test
        ts_test = Path("tests/test_spec07_c4_hybrid_tool.ts")
        if not ts_test.exists():
            self.skipTest("TS test missing")

        cmd = ["npx", "tsx", str(ts_test)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"TS hybrid test failed: {res.stdout}\n{res.stderr}")


if __name__ == "__main__":
    unittest.main()
