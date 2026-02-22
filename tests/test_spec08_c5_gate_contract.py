from __future__ import annotations

import unittest


@unittest.skip("Spec08 C5 gate contract declared in C0; implementation lands in C5.")
class Spec08C5GateContractTests(unittest.TestCase):
    def test_ci_order_unchanged(self) -> None:
        pass

    def test_ci_order_unchanged_with_new_eval_tasks(self) -> None:
        pass

    def test_fast_scope_unchanged(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
