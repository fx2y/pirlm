from __future__ import annotations

import unittest

from tests.mise_contract import (
    CI_RUN_EXPECTED,
    assert_ci_order_unchanged,
    assert_helper_tasks_additive_only,
    load_mise,
    mutated_with_ci_run,
)


class Spec09C6GateContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = load_mise()

    def test_ci_order_unchanged(self) -> None:
        self.assertEqual(self.data["tasks"]["ci"]["run"], CI_RUN_EXPECTED)
        assert_ci_order_unchanged(self.data)

    def test_helper_tasks_additive_only(self) -> None:
        assert_helper_tasks_additive_only(
            self.data, helpers=("spec09-golden", "spec09-chaos", "spec09-report")
        )
        for helper in ("spec09-golden", "spec09-chaos", "spec09-report"):
            self.assertIn("smoke", str(self.data["tasks"][helper]["description"]).lower())

    def test_ci_order_drift_fails(self) -> None:
        drifted = mutated_with_ci_run(
            self.data,
            self.data["tasks"]["ci"]["run"].replace(
                "mise run lint", "mise run unit && mise run lint", 1
            ),
        )
        with self.assertRaises(AssertionError):
            assert_ci_order_unchanged(drifted)


if __name__ == "__main__":
    unittest.main()
