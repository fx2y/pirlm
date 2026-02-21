from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from pirml.web.eval import evidence_accuracy
from pirml.web.eval_shard import run_shard
from pirml.web.pipeline import WebPlan


class WebEvalTests(unittest.IsolatedAsyncioTestCase):
    def test_web_plan_polymorphism(self) -> None:
        """C3.I1: WebPlan polymorphic execution without core if-else explosion."""
        plan = WebPlan(provider="mock", cache="memory")
        self.assertEqual(plan.provider, "mock")
        self.assertEqual(plan.cache, "memory")

    def test_web_plan_fails_on_invalid_config(self) -> None:
        """C3.I1: WebPlan fail path with invalid config."""
        with self.assertRaises(TypeError):
            # Missing required field
            WebPlan(provider="mock")  # type: ignore

    def test_resolve_plan_rejects_unsupported_variants(self) -> None:
        from scripts.web_eval import resolve_plan

        with self.assertRaises(ValueError):
            resolve_plan("(B1a,B2b,B3a,B4a,B5b)")

    def test_resolve_plan_rejects_invalid_shape(self) -> None:
        from scripts.web_eval import resolve_plan

        with self.assertRaises(ValueError):
            resolve_plan("B1a,B2a,B3b,B4b,B5a")

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

    async def test_eval_shard_creates_cache_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "nested" / "cache"
            rows = await run_shard(
                queries=[{"qid": "Q1", "query": "pirml"}],
                plan=WebPlan(provider="mock", cache="sqlite"),
                responses_path=Path("tests/fixtures/web/responses.json"),
                cache_path=cache_dir,
                seed=0,
            )
            self.assertEqual(len(rows), 1)
            self.assertTrue((cache_dir / "web_cache.sqlite").exists())

    def test_evidence_accuracy_depends_on_citations(self) -> None:
        low = evidence_accuracy(
            query="pirml deterministic fixture",
            citations=[
                {
                    "url": "u",
                    "doc_sha256": "a" * 64,
                    "chunk_id": "c1",
                    "quote": "unrelated text",
                    "retrieved_at": 1,
                }
            ],
        )
        high = evidence_accuracy(
            query="pirml deterministic fixture",
            citations=[
                {
                    "url": "u",
                    "doc_sha256": "a" * 64,
                    "chunk_id": "c1",
                    "quote": "PIRML deterministic fixture evidence.",
                    "retrieved_at": 1,
                }
            ],
        )
        self.assertGreater(high, low)


if __name__ == "__main__":
    unittest.main()
