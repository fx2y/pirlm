from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from pirml.cli_common import parse_runner_config, parse_suite_config
from pirml.eval_runner import replay_env, run_suite_shard
from pirml.eval_runner.replay_guard import ReplaySnapshot, check_task_replay


class Spec08C2ReplayGuardTests(unittest.TestCase):
    def test_replay_match_preserved_for_deterministic_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "dataset.jsonl"
            dataset.write_text(
                '{"task_id":"Q1","query":"alpha","expected_answer":"alpha"}\n',
                encoding="utf-8",
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
            self.assertTrue(rows[0]["ok"])
            self.assertEqual(rows[0]["replay_match"], True)
            self.assertEqual(rows[0].get("note", ""), "")

    def test_replay_mismatch_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "dataset.jsonl"
            dataset.write_text(
                '{"task_id":"Q1","query":"alpha","expected_answer":"alpha"}\n',
                encoding="utf-8",
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
            previous = os.environ.get("PIRML_REPLAY_FORCE_MISMATCH")
            os.environ["PIRML_REPLAY_FORCE_MISMATCH"] = "Q1"
            try:
                rows = run_suite_shard(suite_cfg=suite_cfg, runner_cfg=runner_cfg)
            finally:
                if previous is None:
                    os.environ.pop("PIRML_REPLAY_FORCE_MISMATCH", None)
                else:
                    os.environ["PIRML_REPLAY_FORCE_MISMATCH"] = previous
            self.assertEqual(rows[0]["fail_tag"], "REPLAY_MISMATCH")
            self.assertFalse(rows[0]["ok"])
            self.assertEqual(rows[0]["replay_match"], False)
            self.assertEqual(rows[0]["note"], "replay_guard:forced_mismatch")

    def test_replay_block_tools(self) -> None:
        env = replay_env()
        self.assertEqual(env["PIRML_BLOCK_TOOLS"], "1")

    def test_replay_check_sets_and_restores_block_tools_env(self) -> None:
        previous = os.environ.get("PIRML_BLOCK_TOOLS")
        os.environ["PIRML_BLOCK_TOOLS"] = "0"
        try:
            seen: list[str] = []

            def _replay_run() -> ReplaySnapshot:
                seen.append(os.environ.get("PIRML_BLOCK_TOOLS", ""))
                return ReplaySnapshot(ok=True, fail_tag="", latency_ms=1.0)

            check = check_task_replay(
                task_id="Q1",
                live=ReplaySnapshot(ok=True, fail_tag="", latency_ms=1.0),
                replay_run=_replay_run,
            )
            self.assertTrue(check.match)
            self.assertEqual(seen, ["1"])
            self.assertEqual(os.environ.get("PIRML_BLOCK_TOOLS"), "0")
        finally:
            if previous is None:
                os.environ.pop("PIRML_BLOCK_TOOLS", None)
            else:
                os.environ["PIRML_BLOCK_TOOLS"] = previous


if __name__ == "__main__":
    unittest.main()
