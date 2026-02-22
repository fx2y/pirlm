from __future__ import annotations

import unittest

from pirml.web.taxonomy import FAIL_TAGS, classify_fail_tag


class Spec08C3TaxonomyTests(unittest.TestCase):
    def test_single_label_only(self) -> None:
        tag = classify_fail_tag(
            timed_out=False,
            replay_match=True,
            invalid_output=True,
            no_cite=False,
        )
        self.assertEqual(tag, "OUTPUT_INVALID")
        self.assertIn(tag, FAIL_TAGS)

    def test_unknown_maps_fail_closed(self) -> None:
        tag = classify_fail_tag(
            timed_out=False,
            replay_match=True,
            invalid_output=False,
            no_cite=False,
        )
        self.assertEqual(tag, "")


if __name__ == "__main__":
    unittest.main()
