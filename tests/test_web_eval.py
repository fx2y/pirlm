from __future__ import annotations

import unittest
from typing import Any

from pirml.web.pipeline import WebPlan


class WebEvalTests(unittest.IsolatedAsyncioTestCase):
    def test_web_plan_polymorphism(self) -> None:
        """C3.I1: WebPlan polymorphic execution without core if-else explosion."""
        plan = WebPlan(
            provider="mock", cache="memory", parser="html", scorer="bm25", cite_mode="quote"
        )
        self.assertEqual(plan.provider, "mock")
        self.assertEqual(plan.cache, "memory")
        self.assertEqual(plan.parser, "html")
        self.assertEqual(plan.scorer, "bm25")
        self.assertEqual(plan.cite_mode, "quote")

    def test_web_plan_fails_on_invalid_config(self) -> None:
        """C3.I1: WebPlan fail path with invalid config."""
        with self.assertRaises(TypeError):
            # Missing required field
            WebPlan(provider="mock")  # type: ignore

    def test_winner_selection_is_deterministic(self) -> None:
        """C3.I2: Winner selection is deterministic lexicographic max on (acc, -bytes, -chunks, -fetches, cache_hit)."""
        # Metric tuple: (acc, -bytes, -chunks, -fetches, cache_hit)
        from scripts.web_eval import select_winner

        runs: list[dict[str, Any]] = [
            {
                "plan_id": "P1",
                "acc": 0.8,
                "bytes": 1000,
                "chunks": 20,
                "fetches": 5,
                "cache_hit": 0.5,
            },
            {
                "plan_id": "P2",
                "acc": 0.9,  # Better accuracy
                "bytes": 2000,
                "chunks": 30,
                "fetches": 8,
                "cache_hit": 0.2,
            },
            {
                "plan_id": "P3",
                "acc": 0.9,  # Same accuracy as P2
                "bytes": 1500,  # But fewer bytes
                "chunks": 30,
                "fetches": 8,
                "cache_hit": 0.2,
            },
        ]

        # P3 should win over P2 because of fewer bytes.
        # P2/P3 win over P1 because of higher accuracy.
        winner = select_winner(runs)
        self.assertEqual(winner, "P3")

    def test_winner_selection_fails_on_empty_metrics(self) -> None:
        """C3.I2: Winner selection fail path with empty run list."""
        from scripts.web_eval import select_winner

        with self.assertRaises(ValueError):
            select_winner([])


if __name__ == "__main__":
    unittest.main()
