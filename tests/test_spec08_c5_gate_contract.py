from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


class Spec08C5GateContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = tomllib.loads(Path(".mise.toml").read_text(encoding="utf-8"))

    def test_ci_order_unchanged(self) -> None:
        ci_run = self.data["tasks"]["ci"]["run"]
        expected = "mise run fmt && mise run lint && mise run types && mise run unit && mise run proto && mise run trace && mise run schemas && mise run replay"
        self.assertEqual(ci_run, expected)

    def test_ci_order_unchanged_with_new_eval_tasks(self) -> None:
        tasks = self.data["tasks"]
        for name in ("eval-golden", "eval-full", "eval-report"):
            self.assertIn(name, tasks)
        self.assertEqual(
            self.data["tasks"]["ci"]["run"].count("eval-"),
            0,
            "CI ladder must not inline heavy eval helpers",
        )

    def test_fast_scope_unchanged(self) -> None:
        fast_run = self.data["tasks"]["fast"]["run"]
        for heavy in (
            "proto",
            "trace",
            "schemas",
            "replay",
            "eval-golden",
            "eval-full",
            "eval-report",
        ):
            self.assertNotIn(f"run {heavy}", fast_run)


if __name__ == "__main__":
    unittest.main()
