from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pirml.cli_common import CliFailure, parse_runner_config, parse_suite_config
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
            for row in first:
                if row.get("terminal") is True:
                    trace_ptr = str(row["pi_ptr"]["trace_ptr"])
                    self.assertTrue(Path(trace_ptr).is_file(), trace_ptr)
                    self.assertNotEqual(trace_ptr, str(output))

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

    def test_duplicate_dataset_task_ids_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = self._write_dataset(
                root,
                [
                    {"task_id": "Q1", "query": "alpha", "expected_answer": "alpha"},
                    {"task_id": "Q1", "query": "beta", "expected_answer": "beta"},
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
            with self.assertRaisesRegex(CliFailure, "duplicate task_id"):
                run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)

    def test_resume_fails_on_duplicate_terminal_in_existing_shard(self) -> None:
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
            out = shard_path(out_dir=runner_cfg.out_dir, suite=suite_cfg.suite, shard=runner_cfg.shard)
            out.parent.mkdir(parents=True, exist_ok=True)
            row = {
                "seq": 1,
                "task_id": "Q1",
                "suite": "golden50",
                "shard": 0,
                "attempt": 0,
                "terminal": True,
                "ok": True,
                "acc": 1.0,
                "latency_ms": 1.0,
                "cost_usd": 0.0,
            }
            out.write_text(
                json.dumps(row, sort_keys=True)
                + "\n"
                + json.dumps({**row, "seq": 2}, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CliFailure, "duplicate terminal"):
                run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)

    def test_resume_fails_on_seq_drift(self) -> None:
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
            out = shard_path(out_dir=runner_cfg.out_dir, suite=suite_cfg.suite, shard=runner_cfg.shard)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                "\n".join(
                    [
                        json.dumps({"seq": 1, "task_id": "Q1", "terminal": False}, sort_keys=True),
                        json.dumps({"seq": 3, "task_id": "Q1", "terminal": True, "ok": True}, sort_keys=True),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CliFailure, "seq drift"):
                run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)

    def test_ctx_byte_cap_can_fail_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = self._write_dataset(
                root,
                [{"task_id": "Q1", "query": "abcd", "expected_answer": "abcd"}],
            )
            suite_cfg = parse_suite_config(suite="golden50", dataset=str(dataset))
            runner_cfg = parse_runner_config(
                jobs=1,
                shards=1,
                shard=0,
                timeout_s=10.0,
                ctx_byte_cap=2,
                seed=7,
                out_dir=str(root / "out"),
            )
            rows = run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)
            self.assertEqual(rows[0]["fail_tag"], "CTX_BLOAT")
            self.assertFalse(rows[0]["ok"])

    def test_jobs_gt_one_typed_unsupported_until_parallel_runner_lands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = self._write_dataset(
                root,
                [{"task_id": "Q1", "query": "alpha", "expected_answer": "alpha"}],
            )
            suite_cfg = parse_suite_config(suite="golden50", dataset=str(dataset))
            runner_cfg = parse_runner_config(
                jobs=2,
                shards=1,
                shard=0,
                timeout_s=10.0,
                ctx_byte_cap=1024,
                seed=0,
                out_dir=str(root / "out"),
            )
            with self.assertRaisesRegex(CliFailure, "jobs > 1"):
                run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)


if __name__ == "__main__":
    unittest.main()
