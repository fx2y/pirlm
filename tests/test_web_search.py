from __future__ import annotations

import unittest
from typing import cast

from pirml.web.search import MockProvider, rank_and_diversify
from pirml.web.types import SerpRow


class WebSearchTests(unittest.IsolatedAsyncioTestCase):
    def test_serp_pruning_is_deterministic_and_capped(self) -> None:
        """C1.I2: SERP pruning is deterministic and capped at k=8 and per_domain_cap=2."""
        rows: list[SerpRow] = [
            cast(
                SerpRow,
                {
                    "url": f"https://a.example/{i}",
                    "title": f"t{i}",
                    "snippet": f"s{i}",
                    "rank": i,
                    "source": "fixture",
                },
            )
            for i in range(5)
        ] + [
            cast(
                SerpRow,
                {
                    "url": f"https://b.example/{i}",
                    "title": f"t{i}",
                    "snippet": f"s{i}",
                    "rank": i + 5,
                    "source": "fixture",
                },
            )
            for i in range(5)
        ]

        # Domain cap check: only 2 per domain should remain
        result = rank_and_diversify(rows, k=8, per_domain_cap=2)
        urls = [row["url"] for row in result]
        self.assertEqual(
            urls,
            [
                "https://a.example/0",
                "https://a.example/1",
                "https://b.example/0",
                "https://b.example/1",
            ],
        )

        # Capped check: k=3 should return only 3 rows
        result_k3 = rank_and_diversify(rows, k=3, per_domain_cap=2)
        self.assertEqual(len(result_k3), 3)

        # Determinism check: same rows, same result
        result_2 = rank_and_diversify(rows, k=8, per_domain_cap=2)
        self.assertEqual(result, result_2)

    def test_serp_pruning_fails_on_empty_results(self) -> None:
        """C1.I2: SERP pruning fail path with empty input."""
        result = rank_and_diversify([], k=8, per_domain_cap=2)
        self.assertEqual(result, [])

    async def test_mock_provider_hot_swap(self) -> None:
        """C1.I1 (indirectly): MockProvider hot-swap readiness."""
        provider = MockProvider(
            {
                "q1": [
                    {
                        "url": "https://e.com/1",
                        "title": "t1",
                        "snippet": "s1",
                        "rank": 1,
                        "source": "test",
                    }
                ]
            }
        )
        results = await provider.search("q1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://e.com/1")

    async def test_mock_provider_unknown_query_is_empty(self) -> None:
        """C1.I1 (indirectly): MockProvider unknown query returns empty list."""
        provider = MockProvider({})
        results = await provider.search("q2")
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
