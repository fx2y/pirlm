from __future__ import annotations

import unittest


@unittest.skip("Spec08 C5 golden gate declared in C0; implementation lands in C5.")
class Spec08C5GoldenDeltaTests(unittest.TestCase):
    def test_acc_regression_fails(self) -> None:
        pass

    def test_cost_regression_fails(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
