from __future__ import annotations

import unittest
from pathlib import Path

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

    def test_eval_shard_does_not_persist_jitter_in_acc(self) -> None:
        text = Path("pirml/web/eval_shard.py").read_text(encoding="utf-8")
        self.assertNotIn("deterministic_jitter(", text)


if __name__ == "__main__":
    unittest.main()
