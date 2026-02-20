from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, cast

from pirml.clock import SequenceClock
from pirml.runtime.tools import default_registry
from pirml.web.cite import pack_citations
from pirml.web.fetch import load_fixture_fetcher
from pirml.web.search import rank_and_diversify
from pirml.web.types import SerpRow


def _assert_runtime_tool_surface(tool_names: set[str]) -> None:
    expected = {"echo", "readfile", "bash"}
    if tool_names != expected:
        raise AssertionError(f"runtime tool surface drifted: {tool_names} != {expected}")


class WebC0Tests(unittest.IsolatedAsyncioTestCase):
    def test_runtime_tool_surface_remains_frozen(self) -> None:
        registry = default_registry()
        tools_map = cast(dict[str, Any], vars(registry).get("_tools", {}))
        _assert_runtime_tool_surface(set(tools_map.keys()))

    def test_runtime_tool_surface_guard_detects_drift(self) -> None:
        with self.assertRaises(AssertionError):
            _assert_runtime_tool_surface({"echo", "readfile", "bash", "web_fetch"})

    def test_citation_retrieved_at_uses_sequence_clock_deterministically(self) -> None:
        claims = [
            (
                "https://example.com/a",
                "a" * 64,
                "chunk-001",
                "one two three four five six seven eight nine ten "
                "eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen "
                "nineteen twenty twentyone twentytwo twentythree twentyfour twentyfive "
                "twentysix",
            ),
            ("https://example.com/b", "b" * 64, "chunk-002", "short quote"),
        ]

        serialized_runs: list[str] = []
        for _ in range(3):
            clock = SequenceClock(start=1_700_000_000)
            citations = pack_citations(claims, clock=clock)
            serialized_runs.append(
                json.dumps(citations, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
            )
            self.assertEqual(citations[0]["retrieved_at"], 1_700_000_000)
            self.assertEqual(citations[1]["retrieved_at"], 1_700_000_001)
            self.assertLessEqual(len(citations[0]["quote"].split()), 25)

        self.assertEqual(serialized_runs[0], serialized_runs[1])
        self.assertEqual(serialized_runs[1], serialized_runs[2])

    async def test_fixture_fetcher_loads_local_artifacts_only(self) -> None:
        fetcher = load_fixture_fetcher(Path("tests/fixtures/web/responses.json"))
        row = await fetcher.fetch("https://example.com/docs/page?utm_medium=x&b=2&a=1#frag")

        self.assertEqual(row["url"], "https://example.com/docs/page?a=1&b=2")
        self.assertEqual(row["final_url"], "https://example.com/docs/page?a=1&b=2")
        self.assertEqual(row["status"], 200)
        self.assertEqual(row["content_type"], "text/html")
        self.assertGreater(row["bytes"], 0)
        self.assertEqual(len(row["body_sha256"]), 64)

    async def test_fixture_fetcher_unknown_url_is_typed_failure(self) -> None:
        fetcher = load_fixture_fetcher(Path("tests/fixtures/web/responses.json"))
        with self.assertRaises(KeyError):
            await fetcher.fetch("https://example.com/missing")

    def test_rank_and_diversify_is_stable(self) -> None:
        rows: list[SerpRow] = [
            {
                "url": "https://a.example/x?utm_source=ads",
                "title": "t1",
                "snippet": "s1",
                "rank": 0,
                "source": "fixture",
            },
            {
                "url": "https://a.example/y",
                "title": "t2",
                "snippet": "s2",
                "rank": 1,
                "source": "fixture",
            },
            {
                "url": "https://a.example/z",
                "title": "t3",
                "snippet": "s3",
                "rank": 2,
                "source": "fixture",
            },
            {
                "url": "https://b.example/p",
                "title": "t4",
                "snippet": "s4",
                "rank": 3,
                "source": "fixture",
            },
        ]

        result = rank_and_diversify(rows, k=8, per_domain_cap=2)
        self.assertEqual(
            [row["url"] for row in result],
            [
                "https://a.example/x",
                "https://a.example/y",
                "https://b.example/p",
            ],
        )


if __name__ == "__main__":
    unittest.main()
