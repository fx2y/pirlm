from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class Spec08C5GoldenDeltaTests(unittest.TestCase):
    @staticmethod
    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, *args], check=False, capture_output=True, text=True)

    def test_golden_manifest_frozen_shape(self) -> None:
        manifest = Path("spec-0/08/golden50.jsonl")
        self.assertTrue(manifest.is_file())
        rows = [
            json.loads(line)
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(rows), 50)
        seen_ids: set[str] = set()
        for row in rows:
            self.assertIn("task_id", row)
            self.assertIn("expected_answer", row)
            self.assertIn("query", row)
            self.assertIn("citation_required", row)
            self.assertIn("category", row)
            self.assertIn("failure_mode", row)
            self.assertNotEqual(row["query"], row["expected_answer"])
            self.assertNotIn(row["task_id"], seen_ids)
            seen_ids.add(row["task_id"])

    def test_acc_regression_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prev = root / "prev.json"
            now = root / "now.json"
            out = root / "report.json"
            delta = root / "delta.json"
            shard = root / "rows.ndjson"
            shard.write_text(
                json.dumps(
                    {
                        "seq": 1,
                        "task_id": "T1",
                        "attempt": 0,
                        "shard": 0,
                        "suite": "golden50",
                        "ok": True,
                        "terminal": True,
                        "latency_ms": 10.0,
                        "cost_usd": 0.01,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            prev.write_text(
                json.dumps(
                    {
                        "acc": 0.9,
                        "median_cost": 0.01,
                        "median_latency": 10.0,
                        "acc_per_$": 100.0,
                        "acc_per_min": 6.0,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            now.write_text(
                json.dumps(
                    {
                        "acc": 0.5,
                        "median_cost": 0.01,
                        "median_latency": 10.0,
                        "acc_per_$": 50.0,
                        "acc_per_min": 3.0,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            proc = self._run(
                "-m",
                "pirml.report",
                str(shard),
                "--out",
                str(out),
                "--compare",
                str(prev),
                str(now),
                "--acc-min-delta",
                "-0.1",
                "--delta-out",
                str(delta),
            )
            self.assertEqual(proc.returncode, 1)
            err = json.loads(proc.stderr.strip())
            self.assertEqual(err["type"], "validation")
            cmp = json.loads(delta.read_text(encoding="utf-8"))
            self.assertEqual(cmp["ok"], False)
            self.assertIn("acc_delta", cmp)

    def test_cost_regression_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prev = root / "prev.json"
            now = root / "now.json"
            out = root / "report.json"
            shard = root / "rows.ndjson"
            shard.write_text(
                json.dumps(
                    {
                        "seq": 1,
                        "task_id": "T1",
                        "attempt": 0,
                        "shard": 0,
                        "suite": "golden50",
                        "ok": True,
                        "terminal": True,
                        "latency_ms": 10.0,
                        "cost_usd": 0.01,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            prev.write_text(
                json.dumps(
                    {
                        "acc": 0.5,
                        "median_cost": 0.01,
                        "median_latency": 10.0,
                        "acc_per_$": 100.0,
                        "acc_per_min": 6.0,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            now.write_text(
                json.dumps(
                    {
                        "acc": 0.5,
                        "median_cost": 0.01,
                        "median_latency": 10.0,
                        "acc_per_$": 90.0,
                        "acc_per_min": 5.0,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            proc = self._run(
                "-m",
                "pirml.report",
                str(shard),
                "--out",
                str(out),
                "--compare",
                str(prev),
                str(now),
                "--acc-per-dollar-min-delta",
                "-5",
                "--acc-per-min-min-delta",
                "-0.5",
            )
            self.assertEqual(proc.returncode, 1)
            err = json.loads(proc.stderr.strip())
            self.assertEqual(err["type"], "validation")

    def test_missing_baseline_compare_file_typed_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "report.json"
            shard = root / "rows.ndjson"
            now = root / "now.json"
            shard.write_text(
                json.dumps(
                    {
                        "seq": 1,
                        "task_id": "T1",
                        "attempt": 0,
                        "shard": 0,
                        "suite": "golden50",
                        "ok": True,
                        "terminal": True,
                        "latency_ms": 10.0,
                        "cost_usd": 0.01,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            now.write_text(
                json.dumps(
                    {"acc": 1.0, "median_cost": 0.01, "median_latency": 10.0}, sort_keys=True
                ),
                encoding="utf-8",
            )
            proc = self._run(
                "-m",
                "pirml.report",
                str(shard),
                "--out",
                str(out),
                "--compare",
                str(root / "missing.json"),
                str(now),
            )
            self.assertEqual(proc.returncode, 1)
            err = json.loads(proc.stderr.strip())
            self.assertEqual(err["type"], "unsupported")


if __name__ == "__main__":
    unittest.main()
