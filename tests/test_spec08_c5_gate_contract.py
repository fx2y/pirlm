from __future__ import annotations

import unittest

from tests.mise_contract import CI_RUN_EXPECTED, assert_ci_order_unchanged, load_mise


class Spec08C5GateContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = load_mise()

    def test_ci_order_unchanged(self) -> None:
        self.assertEqual(self.data["tasks"]["ci"]["run"], CI_RUN_EXPECTED)
        assert_ci_order_unchanged(self.data)

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
