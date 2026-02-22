from __future__ import annotations

import unittest

from tests.spec09_placeholders import Spec09PlaceholderCase


class Spec09C6GateContractTests(Spec09PlaceholderCase):
    @unittest.expectedFailure
    def test_ci_order_unchanged(self) -> None:
        self._todo("C6.I19 pass lane")

    @unittest.expectedFailure
    def test_helper_tasks_additive_only(self) -> None:
        self._todo("C6.I19 additivity lane")

    @unittest.expectedFailure
    def test_ci_order_drift_fails(self) -> None:
        self._todo("C6.I19 fail lane")


if __name__ == "__main__":
    unittest.main()
