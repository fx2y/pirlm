from __future__ import annotations

import unittest


@unittest.skip("Spec08 C4 pareto declared in C0; implementation lands in C4.")
class Spec08C4ParetoTests(unittest.TestCase):
    def test_single_label_taxonomy_only(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
