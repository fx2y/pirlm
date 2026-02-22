from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class Spec08C1CliSurfaceTests(unittest.TestCase):
    @staticmethod
    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, *args]
        return subprocess.run(cmd, check=False, capture_output=True, text=True)

    def test_modules_invocable(self) -> None:
        for module in ("pirml.eval", "pirml.report", "pirml.select_golden", "pirml.md"):
            with self.subTest(module=module):
                proc = self._run("-m", module, "--help")
                self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_required_modules_exist(self) -> None:
        for module in ("pirml.eval", "pirml.report", "pirml.select_golden", "pirml.md"):
            with self.subTest(module=module):
                imported = importlib.import_module(module)
                self.assertTrue(callable(getattr(imported, "main", None)), module)

    def test_unknown_suite_typed_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "dataset.jsonl"
            dataset.write_text('{"task_id":"Q1","query":"q"}\n', encoding="utf-8")
            proc = self._run(
                "-m",
                "pirml.eval",
                "--suite",
                "nope",
                "--dataset",
                str(dataset),
            )
            self.assertEqual(proc.returncode, 1)
            err = json.loads(proc.stderr.strip())
            self.assertEqual(err["type"], "unsupported")
            self.assertEqual(err["retryable"], False)

    def test_missing_dataset_typed_unsupported(self) -> None:
        proc = self._run("-m", "pirml.eval", "--suite", "golden50")
        self.assertEqual(proc.returncode, 1)
        err = json.loads(proc.stderr.strip())
        self.assertEqual(err["type"], "unsupported")

    def test_eval_unknown_flag_is_typed_config_error(self) -> None:
        proc = self._run("-m", "pirml.eval", "--bogus")
        self.assertEqual(proc.returncode, 2)
        err = json.loads(proc.stderr.strip())
        self.assertEqual(err["type"], "config")

    def test_eval_argparse_type_error_is_typed_config_error(self) -> None:
        proc = self._run("-m", "pirml.eval", "--jobs", "oops")
        self.assertEqual(proc.returncode, 2)
        self.assertTrue(proc.stderr.strip())
        err = json.loads(proc.stderr.strip())
        self.assertEqual(err["type"], "config")

    def test_eval_zero_flags_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "dataset.jsonl"
            dataset.write_text('{"task_id":"Q1","query":"q","expected_answer":"a"}\n', encoding="utf-8")
            for flag in ("--jobs", "--shards", "--timeout-s", "--ctx-byte-cap"):
                with self.subTest(flag=flag):
                    proc = self._run(
                        "-m",
                        "pirml.eval",
                        "--suite",
                        "golden50",
                        "--dataset",
                        str(dataset),
                        flag,
                        "0",
                    )
                    self.assertEqual(proc.returncode, 1, proc.stderr)
                    err = json.loads(proc.stderr.strip())
                    self.assertEqual(err["type"], "validation")

    def test_eval_config_type_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "dataset.jsonl"
            cfg = root / "cfg.json"
            dataset.write_text('{"task_id":"Q1","query":"q","expected_answer":"a"}\n', encoding="utf-8")
            cfg.write_text(
                json.dumps({"suite": "golden50", "dataset": str(dataset), "jobs": "oops"}, sort_keys=True),
                encoding="utf-8",
            )
            proc = self._run("-m", "pirml.eval", "--config", str(cfg))
            self.assertEqual(proc.returncode, 2, proc.stderr)
            err = json.loads(proc.stderr.strip())
            self.assertEqual(err["type"], "config")

    def test_eval_config_bool_string_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "dataset.jsonl"
            cfg = root / "cfg.json"
            dataset.write_text('{"task_id":"Q1","query":"q","expected_answer":"a"}\n', encoding="utf-8")
            cfg.write_text(
                json.dumps(
                    {
                        "suite": "golden50",
                        "dataset": str(dataset),
                        "require_citations": "false",
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            proc = self._run("-m", "pirml.eval", "--config", str(cfg))
            self.assertEqual(proc.returncode, 2, proc.stderr)
            err = json.loads(proc.stderr.strip())
            self.assertEqual(err["type"], "config")

    def test_select_golden_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            in_path = root / "in.jsonl"
            out_a = root / "a.jsonl"
            out_b = root / "b.jsonl"
            rows = [
                {"task_id": "Q1", "category": "c1", "failure_mode": "f1", "expected_answer": "a1"},
                {"task_id": "Q2", "category": "c1", "failure_mode": "f2", "expected_answer": "a2"},
                {"task_id": "Q3", "category": "c2", "failure_mode": "f1", "expected_answer": "a3"},
                {"task_id": "Q4", "category": "c2", "failure_mode": "f2", "expected_answer": "a4"},
            ]
            in_path.write_text(
                "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n",
                encoding="utf-8",
            )
            proc_a = self._run(
                "-m",
                "pirml.select_golden",
                "--in",
                str(in_path),
                "--n",
                "4",
                "--seed",
                "0",
                "--out",
                str(out_a),
            )
            proc_b = self._run(
                "-m",
                "pirml.select_golden",
                "--in",
                str(in_path),
                "--n",
                "4",
                "--seed",
                "0",
                "--out",
                str(out_b),
            )
            self.assertEqual(proc_a.returncode, 0, proc_a.stderr)
            self.assertEqual(proc_b.returncode, 0, proc_b.stderr)
            self.assertEqual(out_a.read_bytes(), out_b.read_bytes())

    def test_md_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report.json"
            report.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "total_tasks": 2,
                        "acc": 0.5,
                        "median_latency": 10.0,
                        "median_cost": 0.02,
                        "fail_pareto": [{"fail_tag": "NO_CITE", "count": 1}],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            proc_a = self._run("-m", "pirml.md", str(report))
            proc_b = self._run("-m", "pirml.md", str(report))
            self.assertEqual(proc_a.returncode, 0, proc_a.stderr)
            self.assertEqual(proc_b.returncode, 0, proc_b.stderr)
            self.assertEqual(proc_a.stdout, proc_b.stdout)


if __name__ == "__main__":
    unittest.main()
