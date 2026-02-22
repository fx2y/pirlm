from __future__ import annotations

import unittest


@unittest.skip("Spec08 C3 determinism declared in C0; implementation lands in C3.")
class Spec08C3DeterminismTests(unittest.TestCase):
    def test_no_time_time_calls(self) -> None:
        pass

    def test_metrics_byte_stable_x3(self) -> None:
        pass

    def test_search_metrics_byte_stable_x3(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
