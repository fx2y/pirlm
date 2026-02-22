from __future__ import annotations

import unittest


@unittest.skip("Spec08 C1 declared in C0; implementation lands in C1.")
class Spec08C1CliSurfaceTests(unittest.TestCase):
    def test_modules_invocable(self) -> None:
        pass

    def test_required_modules_exist(self) -> None:
        pass

    def test_unknown_suite_typed_fail(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
