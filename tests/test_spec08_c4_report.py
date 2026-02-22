from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class Spec08C4ReportTests(unittest.TestCase):
    @staticmethod
    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_report_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shard_a = root / "a.ndjson"
            shard_b = root / "b.ndjson"
            out_a = root / "report_a.json"
            out_b = root / "report_b.json"
            pareto_a = root / "pareto_a.json"
            pareto_b = root / "pareto_b.json"
            art_root = root / "art"

            # Include non-terminal rows; aggregator must ignore them.
            shard_a.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "seq": 3,
                                "task_id": "T2",
                                "attempt": 0,
                                "shard": 1,
                                "suite": "golden50",
                        "ok": False,
                        "terminal": True,
                        "fail_tag": "NO_CITE",
                        "latency_ms": 100.0,
                        "cost_usd": 0.02,
                    },
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "seq": 1,
                                "task_id": "T1",
                                "attempt": 0,
                                "shard": 0,
                                "suite": "golden50",
                                "ok": True,
                                "terminal": True,
                                "latency_ms": 20.0,
                                "cost_usd": 0.01,
                            },
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "seq": 7,
                                "task_id": "T2",
                                "attempt": 0,
                                "shard": 1,
                                "suite": "golden50",
                                "terminal": False,
                                "note": "resume_skip:terminal_exists",
                            },
                            sort_keys=True,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            shard_b.write_text(
                json.dumps(
                    {
                        "seq": 2,
                        "task_id": "T3",
                        "attempt": 0,
                        "shard": 0,
                        "suite": "golden50",
                        "ok": False,
                        "terminal": True,
                        "fail_tag": "TIMEOUT",
                        "latency_ms": 40.0,
                        "cost_usd": 0.0,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            proc_a = self._run(
                "-m",
                "pirml.report",
                str(shard_b),
                str(shard_a),
                "--out",
                str(out_a),
                "--pareto-out",
                str(pareto_a),
                "--art-root",
                str(art_root),
            )
            proc_b = self._run(
                "-m",
                "pirml.report",
                str(shard_a),
                str(shard_b),
                "--out",
                str(out_b),
                "--pareto-out",
                str(pareto_b),
                "--art-root",
                str(art_root),
            )
            self.assertEqual(proc_a.returncode, 0, proc_a.stderr)
            self.assertEqual(proc_b.returncode, 0, proc_b.stderr)
            self.assertEqual(out_a.read_bytes(), out_b.read_bytes())
            self.assertEqual(pareto_a.read_bytes(), pareto_b.read_bytes())

            report = json.loads(out_a.read_text(encoding="utf-8"))
            self.assertEqual(report["total_tasks"], 3)
            self.assertEqual(report["acc"], 0.333333)
            self.assertEqual(report["median_latency"], 40.0)
            self.assertEqual(report["median_cost"], 0.01)
            self.assertEqual(report["timeout_rate"], 0.333333)
            self.assertEqual(report["no_cite_rate"], 0.333333)
            self.assertTrue(isinstance(report["artifacts"]["report_aid"], str))
            self.assertTrue(isinstance(report["artifacts"]["pareto_aid"], str))
            self.assertEqual(report["fail_pareto"][0]["fail_tag"], "NO_CITE")
            self.assertEqual(report["fail_pareto"][0]["count"], 1)
            self.assertEqual(report["meta"]["notes"], [])
            tags = {row["fail_tag"]: row["count"] for row in report["fail_pareto"]}
            self.assertEqual(tags["NO_CITE"], 1)
            self.assertEqual(tags["TIMEOUT"], 1)

    def test_missing_input_typed_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "report.json"
            proc = self._run(
                "-m",
                "pirml.report",
                str(root / "missing.ndjson"),
                "--out",
                str(out),
            )
            self.assertEqual(proc.returncode, 1)
            err = json.loads(proc.stderr.strip())
            self.assertEqual(err["type"], "unsupported")

    def test_duplicate_terminal_rows_fail_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shard = root / "rows.ndjson"
            out = root / "report.json"
            row = {
                "seq": 1,
                "task_id": "T1",
                "attempt": 0,
                "shard": 0,
                "suite": "golden50",
                "ok": True,
                "terminal": True,
                "latency_ms": 1.0,
                "cost_usd": 0.0,
            }
            shard.write_text(
                json.dumps(row, sort_keys=True) + "\n" + json.dumps({**row, "seq": 2}, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            proc = self._run("-m", "pirml.report", str(shard), "--out", str(out))
            self.assertEqual(proc.returncode, 2, proc.stderr)
            err = json.loads(proc.stderr.strip())
            self.assertEqual(err["type"], "integrity")

    def test_corrupt_ndjson_is_integrity_code2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shard = root / "rows.ndjson"
            out = root / "report.json"
            shard.write_text("{not json}\n", encoding="utf-8")
            proc = self._run("-m", "pirml.report", str(shard), "--out", str(out))
            self.assertEqual(proc.returncode, 2, proc.stderr)
            err = json.loads(proc.stderr.strip())
            self.assertEqual(err["type"], "integrity")


if __name__ == "__main__":
    unittest.main()
