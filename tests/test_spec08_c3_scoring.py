from __future__ import annotations

import unittest

from pirml.web.score import normalize_exact, score_exact_match


class Spec08C3ScoringTests(unittest.TestCase):
    def test_nfkc_ws_normalize(self) -> None:
        self.assertEqual(normalize_exact("Ａ  b\tc\n"), "A b c")

    def test_no_citation_forces_fail(self) -> None:
        score = score_exact_match(
            expected="answer",
            actual="answer",
            citation_count=0,
            require_citations=True,
        )
        self.assertEqual(score, 0.0)


if __name__ == "__main__":
    unittest.main()
