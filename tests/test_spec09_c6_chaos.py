from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from pirml.cli_common import CliFailure, parse_runner_config, parse_suite_config
from pirml.eval_runner import run_suite_shard, shard_path


class Spec09C6ChaosTests(unittest.TestCase):
    @staticmethod
    def _write_dataset(root: Path, name: str, rows: list[dict[str, str]]) -> Path:
        path = root / name
        path.write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _runner_cfg(root: Path, lane: str):
        return parse_runner_config(
            jobs=1,
            shards=1,
            shard=0,
            timeout_s=10.0,
            ctx_byte_cap=1024,
            seed=0,
            out_dir=str(root / "out" / lane),
        )

    def test_timeout_lane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = self._write_dataset(
                root,
                "timeout.jsonl",
                [{"task_id": "Q1", "query": "__timeout__ task", "expected_answer": "x"}],
            )
            rows = run_suite_shard(
                suite_cfg=parse_suite_config(suite="golden50", dataset=str(dataset)),
                runner_cfg=self._runner_cfg(root, "timeout"),
            )
            self.assertEqual(rows[0]["fail_tag"], "TIMEOUT")
            self.assertFalse(bool(rows[0]["ok"]))

    def test_invalid_json_lane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "invalid.jsonl"
            dataset.write_text(
                '{"task_id":"Q1","query":"alpha","expected_answer":"alpha"}\n{bad}\n'
            )
            with self.assertRaisesRegex(CliFailure, "invalid dataset JSON line 2"):
                run_suite_shard(
                    suite_cfg=parse_suite_config(suite="golden50", dataset=str(dataset)),
                    runner_cfg=self._runner_cfg(root, "invalid"),
                )

    def test_resume_after_forced_interrupt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = self._write_dataset(
                root,
                "resume.jsonl",
                [{"task_id": "Q1", "query": "alpha", "expected_answer": "alpha"}],
            )
            suite_cfg = parse_suite_config(suite="golden50", dataset=str(dataset))
            runner_cfg = self._runner_cfg(root, "resume")
            out_path = shard_path(
                out_dir=runner_cfg.out_dir, suite=suite_cfg.suite, shard=runner_cfg.shard
            )
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(
                    {
                        "seq": 1,
                        "task_id": "Q1",
                        "suite": "golden50",
                        "shard": 0,
                        "attempt": 0,
                        "terminal": False,
                        "note": "forced_interrupt:partial",
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            first = run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)
            second = run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)
            self.assertEqual(len(first), 1)
            self.assertTrue(bool(first[0]["terminal"]))
            self.assertEqual(first[0]["seq"], 2)
            self.assertEqual(len(second), 1)
            self.assertFalse(bool(second[0]["terminal"]))
            self.assertEqual(second[0]["note"], "resume_skip:terminal_exists")
            lines = [line for line in out_path.read_text(encoding="utf-8").splitlines() if line]
            self.assertEqual(len(lines), 3)

    def test_replay_mismatch_lane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = self._write_dataset(
                root,
                "replay.jsonl",
                [{"task_id": "Q1", "query": "alpha", "expected_answer": "alpha"}],
            )
            prior = os.environ.get("PIRML_REPLAY_FORCE_MISMATCH")
            os.environ["PIRML_REPLAY_FORCE_MISMATCH"] = "Q1"
            try:
                rows = run_suite_shard(
                    suite_cfg=parse_suite_config(suite="golden50", dataset=str(dataset)),
                    runner_cfg=self._runner_cfg(root, "replay"),
                )
            finally:
                if prior is None:
                    os.environ.pop("PIRML_REPLAY_FORCE_MISMATCH", None)
                else:
                    os.environ["PIRML_REPLAY_FORCE_MISMATCH"] = prior
            row = rows[0]
            self.assertEqual(row["fail_tag"], "REPLAY_MISMATCH")
            self.assertFalse(bool(row["ok"]))
            self.assertFalse(bool(row["replay_match"]))
            self.assertIn("replay_guard", str(row["note"]))


if __name__ == "__main__":
    unittest.main()
