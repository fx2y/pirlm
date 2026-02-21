from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from typing import Any, cast

from pirml.clock import SequenceClock
from pirml.web.cite import pack_citations
from pirml.web.etl import fallback_extract
from pirml.web.fetch import FixtureDocFetcher
from pirml.web.pipeline import WebPipeline, WebPlan
from pirml.web.search import MockProvider
from pirml.web.trace import WebTracer
from pirml.web.types import ChunkRow


class WebGoldenTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = SequenceClock.from_env()
        self.tracer = WebTracer()
        self.golden_dir = Path("tests/golden/web")
        self.golden_dir.mkdir(parents=True, exist_ok=True)

    def _assert_golden(self, name: str, actual: Any) -> None:
        golden_path = self.golden_dir / f"{name}.json"
        actual_json = json.dumps(actual, indent=2, sort_keys=True)

        if os.getenv("PIRML_UPDATE_GOLDEN") == "1":
            golden_path.write_text(actual_json)

        if not golden_path.exists():
            self.fail(
                f"Golden artifact missing: {golden_path}. Run with PIRML_UPDATE_GOLDEN=1 to create it."
            )

        expected_json = golden_path.read_text()
        self.assertEqual(actual_json, expected_json.rstrip("\n"), f"Golden drift for {name}")

    def test_extract_golden(self) -> None:
        """C4.T1: Golden artifact for extraction (robust text)."""
        html = Path("tests/fixtures/web/docs/page.html").read_text()
        # Winner B3b: robust text extraction
        chunks = fallback_extract(
            html, url="https://example.com/p", doc_sha256="s1", source_rank=1, doc_rank=1
        )
        self._assert_golden("extract_page", chunks)

    def test_citation_golden(self) -> None:
        """C4.T1: Golden artifact for citation."""
        chunks = cast(
            list[ChunkRow],
            [
                {
                    "url": "https://example.com/a",
                    "doc_sha256": "a" * 64,
                    "chunk_id": "ck001",
                    "text": "PIRML is a deterministic substrate for LLM orchestration.",
                    "kind": "p",
                    "path_hint": "p",
                    "score": 1.0,
                    "source_rank": 0,
                    "doc_rank": 0,
                }
            ],
        )
        cites = pack_citations(chunks, clock=self.clock, query="PIRML")
        self._assert_golden("citation_one", cites)

    async def test_pipeline_golden(self) -> None:
        """C4.T1: Golden artifact for full pipeline."""
        provider = MockProvider(
            {
                "pirml": [
                    {
                        "url": "https://example.com/p",
                        "title": "PIRML",
                        "snippet": "...",
                        "rank": 1,
                        "source": "test",
                    }
                ]
            }
        )
        fetcher = FixtureDocFetcher(Path("tests/fixtures/web/responses.json"))
        # Map our test URL to an existing fixture URL
        fetcher.add_alias("https://example.com/p", "https://example.com/docs/page?a=1&b=2")

        pipeline = WebPipeline(
            provider=provider, fetcher=fetcher, clock=self.clock, tracer=self.tracer
        )
        plan = WebPlan(provider="mock", cache="memory")

        result = await pipeline.run("pirml", plan)
        self._assert_golden("pipeline_pirml", result)


if __name__ == "__main__":
    unittest.main()
