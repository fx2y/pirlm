from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.spec08_support import load_jsonl, repo_path


class Spec08C7HardeningSyncTests(unittest.TestCase):
    @staticmethod
    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, *args], check=False, capture_output=True, text=True)

    def test_spec08_snippets_match_current_cli_contracts(self) -> None:
        rows = {str(row.get("id")): row for row in load_jsonl("spec-0/08/95-snippets.jsonl")}
        self.assertIn("--dataset", str(rows["S01"]["snip"]))
        self.assertIn("--dataset", str(rows["S02"]["snip"]))
        self.assertIn("--dataset", str(rows["S26"]["snip"]))
        self.assertIn("--out ", str(rows["S03"]["snip"]))
        self.assertIn("/runs/browsecomp/", str(rows["S03"]["snip"]))
        self.assertIn("--out ", str(rows["S16"]["snip"]))
        self.assertIn("--compare", str(rows["S16"]["snip"]))
        self.assertIn("/runs/golden50/", str(rows["S16"]["snip"]))
        self.assertIn("--out ", str(rows["S36"]["snip"]))
        self.assertIn("--compare", str(rows["S36"]["snip"]))
        self.assertIn("/runs/browsecomp/", str(rows["S36"]["snip"]))
        self.assertNotIn("--gate-thresholds", str(rows["S16"]["snip"]))
        self.assertNotIn("--require ", str(rows["S36"]["snip"]))
        self.assertIn("tests/fixtures/web/corpus.jsonl", str(rows["S02"]["snip"]))

    def test_spec08_markdown_has_no_stale_cli_examples(self) -> None:
        text = repo_path("spec-0/08-spec.md").read_text(encoding="utf-8")
        stale_patterns = (
            "python -m pirml.eval --suite golden50 --jobs 8 --out ",
            "python -m pirml.eval --suite browsecomp --shards 32 --shard $I --out ",
            "python -m pirml.report runs/bc_*.ndjson > report.json",
            "python -m pirml.select_golden --in browsecomp.jsonl --n 50 --out suites/golden50.txt",
            "--gate-thresholds",
            "--require acc_per_$_nondecrease",
        )
        for pattern in stale_patterns:
            with self.subTest(pattern=pattern):
                self.assertNotIn(pattern, text)
        for line in text.splitlines():
            if "python -m pirml.eval " in line:
                with self.subTest(line=line):
                    self.assertIn("--dataset", line)
        mise = repo_path(".mise.toml").read_text(encoding="utf-8")
        self.assertIn("out/eval/full/runs/browsecomp/*.ndjson", mise)

    def test_doc_snippet_smoke_commands_execute_with_repo_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            eval_out = root / "eval"
            report_out = root / "report.json"
            pareto_out = root / "pareto.json"
            md_out = root / "report.md"
            delta_out = root / "delta.json"
            prev = root / "prev.json"
            now = root / "now.json"

            eval_proc = self._run(
                "-m",
                "pirml.eval",
                "--suite",
                "golden50",
                "--dataset",
                "spec-0/08/golden50.jsonl",
                "--jobs",
                "1",
                "--shards",
                "8",
                "--shard",
                "0",
                "--out-dir",
                str(eval_out),
            )
            self.assertEqual(eval_proc.returncode, 0, eval_proc.stderr)

            shard_inputs = sorted((eval_out / "runs" / "golden50").glob("*.ndjson"))
            self.assertTrue(shard_inputs)

            report_proc = self._run(
                "-m",
                "pirml.report",
                *(str(p) for p in shard_inputs),
                "--out",
                str(report_out),
                "--pareto-out",
                str(pareto_out),
                "--art-root",
                str(root / "art"),
            )
            self.assertEqual(report_proc.returncode, 0, report_proc.stderr)

            md_proc = self._run("-m", "pirml.md", str(report_out))
            self.assertEqual(md_proc.returncode, 0, md_proc.stderr)
            md_out.write_text(md_proc.stdout, encoding="utf-8")
            self.assertTrue(md_out.read_text(encoding="utf-8"))

            prev.write_text(
                json.dumps(
                    {
                        "acc": 0.0,
                        "median_cost": 0.0,
                        "median_latency": 1.0,
                        "acc_per_$": 0.0,
                        "acc_per_min": 0.0,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            now.write_text(report_out.read_text(encoding="utf-8"), encoding="utf-8")

            compare_proc = self._run(
                "-m",
                "pirml.report",
                *(str(p) for p in shard_inputs),
                "--out",
                str(root / "report-compare.json"),
                "--compare",
                str(prev),
                str(now),
                "--acc-min-delta",
                "-1",
                "--cost-max-delta",
                "999999",
                "--latency-max-delta",
                "999999",
                "--acc-per-dollar-min-delta",
                "-999999",
                "--acc-per-min-min-delta",
                "-999999",
                "--delta-out",
                str(delta_out),
                "--art-root",
                str(root / "art2"),
            )
            self.assertEqual(compare_proc.returncode, 0, compare_proc.stderr)
            delta = json.loads(delta_out.read_text(encoding="utf-8"))
            self.assertIn("ok", delta)


if __name__ == "__main__":
    unittest.main()
