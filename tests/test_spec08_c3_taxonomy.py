from __future__ import annotations

import unittest


@unittest.skip("Spec08 C3 taxonomy declared in C0; implementation lands in C3.")
class Spec08C3TaxonomyTests(unittest.TestCase):
    def test_single_label_only(self) -> None:
        pass

    def test_unknown_maps_fail_closed(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
