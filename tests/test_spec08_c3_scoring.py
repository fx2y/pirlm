from __future__ import annotations

import unittest


@unittest.skip("Spec08 C3 scoring declared in C0; implementation lands in C3.")
class Spec08C3ScoringTests(unittest.TestCase):
    def test_nfkc_ws_normalize(self) -> None:
        pass

    def test_no_citation_forces_fail(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
