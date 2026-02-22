from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class Spec08C4ParetoTests(unittest.TestCase):
    @staticmethod
    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_single_label_taxonomy_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shard = root / "rows.ndjson"
            out = root / "report.json"
            shard.write_text(
                json.dumps(
                    {
                        "seq": 1,
                        "task_id": "T1",
                        "attempt": 0,
                        "shard": 0,
                        "suite": "golden50",
                        "ok": False,
                        "terminal": True,
                        "fail_tag": "TIMEOUT|OUTPUT_INVALID",
                        "latency_ms": 1.0,
                        "cost_usd": 0.0,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            proc = self._run("-m", "pirml.report", str(shard), "--out", str(out))
            self.assertEqual(proc.returncode, 1)
            err = json.loads(proc.stderr.strip())
            self.assertEqual(err["type"], "validation")
            self.assertIn("single-label", err["msg"])


if __name__ == "__main__":
    unittest.main()
