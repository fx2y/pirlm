from __future__ import annotations

import unittest


@unittest.skip("Spec08 C4 report declared in C0; implementation lands in C4.")
class Spec08C4ReportTests(unittest.TestCase):
    def test_report_deterministic(self) -> None:
        pass

    def test_missing_input_typed_fail(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
