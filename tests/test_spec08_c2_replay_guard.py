from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from pirml.cli_common import parse_runner_config, parse_suite_config
from pirml.eval_runner import replay_env, run_suite_shard


class Spec08C2ReplayGuardTests(unittest.TestCase):
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

    def test_replay_block_tools(self) -> None:
        env = replay_env()
        self.assertEqual(env["PIRML_BLOCK_TOOLS"], "1")


if __name__ == "__main__":
    unittest.main()
