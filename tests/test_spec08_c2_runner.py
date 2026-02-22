from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pirml.cli_common import parse_runner_config, parse_suite_config
from pirml.eval_runner import run_suite_shard, shard_path


class Spec08C2RunnerTests(unittest.TestCase):
    def _write_dataset(self, root: Path, rows: list[dict[str, str]]) -> Path:
        path = root / "dataset.jsonl"
        path.write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8"
        )
        return path

    def test_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = self._write_dataset(
                root,
                [
                    {"task_id": "Q1", "query": "alpha", "expected_answer": "alpha"},
                    {"task_id": "Q2", "query": "bravo", "expected_answer": "bravo"},
                ],
            )
            suite_cfg = parse_suite_config(suite="golden50", dataset=str(dataset))
            runner_cfg = parse_runner_config(
                jobs=1,
                shards=1,
                shard=0,
                timeout_s=10.0,
                ctx_byte_cap=1024,
                seed=0,
                out_dir=str(root / "out"),
            )
            first = run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)
            output = shard_path(
                out_dir=runner_cfg.out_dir, suite=suite_cfg.suite, shard=runner_cfg.shard
            )
            prefix = output.read_bytes()
            second = run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)
            suffix = output.read_bytes()
            self.assertEqual(len([row for row in first if row.get("terminal") is True]), 2)
            self.assertEqual(len([row for row in second if row.get("terminal") is False]), 2)
            self.assertTrue(suffix.startswith(prefix))

    def test_append_only_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = self._write_dataset(
                root,
                [{"task_id": "Q1", "query": "alpha", "expected_answer": "alpha"}],
            )
            suite_cfg = parse_suite_config(suite="golden50", dataset=str(dataset))
            runner_cfg = parse_runner_config(
                jobs=1,
                shards=1,
                shard=0,
                timeout_s=10.0,
                ctx_byte_cap=1024,
                seed=0,
                out_dir=str(root / "out"),
            )
            run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)
            run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)
            output = shard_path(
                out_dir=runner_cfg.out_dir, suite=suite_cfg.suite, shard=runner_cfg.shard
            )
            rows = [
                json.loads(line)
                for line in output.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            terminals = [row for row in rows if row.get("terminal") is True]
            skips = [row for row in rows if row.get("terminal") is False]
            self.assertEqual(len(terminals), 1)
            self.assertEqual(len(skips), 1)
            self.assertEqual(skips[0]["note"], "resume_skip:terminal_exists")

    def test_resume_skips_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = self._write_dataset(
                root,
                [{"task_id": "Q1", "query": "alpha", "expected_answer": "alpha"}],
            )
            suite_cfg = parse_suite_config(suite="golden50", dataset=str(dataset))
            runner_cfg = parse_runner_config(
                jobs=1,
                shards=1,
                shard=0,
                timeout_s=10.0,
                ctx_byte_cap=1024,
                seed=0,
                out_dir=str(root / "out"),
            )
            run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)
            resume_rows = run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)
            self.assertEqual(len(resume_rows), 1)
            self.assertEqual(resume_rows[0]["note"], "resume_skip:terminal_exists")

    def test_timeout_tagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = self._write_dataset(
                root,
                [{"task_id": "Q1", "query": "__timeout__ task", "expected_answer": "x"}],
            )
            suite_cfg = parse_suite_config(suite="golden50", dataset=str(dataset))
            runner_cfg = parse_runner_config(
                jobs=1,
                shards=1,
                shard=0,
                timeout_s=10.0,
                ctx_byte_cap=1024,
                seed=0,
                out_dir=str(root / "out"),
            )
            rows = run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)
            self.assertEqual(rows[0]["fail_tag"], "TIMEOUT")
            self.assertFalse(rows[0]["ok"])

    def test_worker_continues_after_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = self._write_dataset(
                root,
                [
                    {"task_id": "Q1", "query": "__timeout__ task", "expected_answer": "x"},
                    {"task_id": "Q2", "query": "bravo", "expected_answer": "bravo"},
                ],
            )
            suite_cfg = parse_suite_config(suite="golden50", dataset=str(dataset))
            runner_cfg = parse_runner_config(
                jobs=1,
                shards=1,
                shard=0,
                timeout_s=10.0,
                ctx_byte_cap=1024,
                seed=0,
                out_dir=str(root / "out"),
            )
            rows = run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)
            by_task = {str(row["task_id"]): row for row in rows if row.get("terminal") is True}
            self.assertEqual(by_task["Q1"]["fail_tag"], "TIMEOUT")
            self.assertTrue(by_task["Q2"]["ok"])


if __name__ == "__main__":
    unittest.main()
