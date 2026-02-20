from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from typing import cast

from pirml.clock import SequenceClock
from pirml.web.cite import pack_citations
from pirml.web.etl.core import fallback_extract, kill_boilerplate
from pirml.web.etl.html_chunks import extract_html_chunks
from pirml.web.etl.join import join_chunks
from pirml.web.etl.score import score_bm25, score_query_overlap
from pirml.web.fetch import FixtureDocFetcher
from pirml.web.pipeline import WebPipeline, WebPlan
from pirml.web.search import MockProvider
from pirml.web.trace import WebTracer
from pirml.web.types import ChunkRow


class WebC2Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = SequenceClock.from_env()
        self.tracer = WebTracer()

    def test_html_extraction(self):
        html = """
        <html>
            <head><title>Test Title</title></head>
            <body>
                <h1>Header 1</h1>
                <p>Paragraph text here.</p>
                <ul><li>Item 1</li></ul>
                <nav><a href="/">Home</a></nav>
            </body>
        </html>
        """
        chunks = extract_html_chunks(html, url="u1", doc_sha256="s1", source_rank=1, doc_rank=1)
        kinds = [c["kind"] for c in chunks]
        self.assertIn("title", kinds)
        self.assertIn("h1", kinds)
        self.assertIn("p", kinds)
        self.assertIn("li", kinds)

        # Verify 800 char cap
        long_html = "<p>" + "a" * 1000 + "</p>"
        chunks = extract_html_chunks(
            long_html, url="u1", doc_sha256="s1", source_rank=1, doc_rank=1
        )
        self.assertEqual(len(chunks[0]["text"]), 800)

    def test_fallback_extract(self):
        html = "No tags here but some text."
        # If parser yields low coverage, fallback should trigger in pipeline
        # But we test it directly here
        chunks = fallback_extract(html, url="u1", doc_sha256="s1", source_rank=1, doc_rank=1)
        self.assertTrue(len(chunks) > 0)
        self.assertEqual(chunks[0]["kind"], "fallback")

    def test_boilerplate_kill(self):
        from collections import Counter

        chunks = cast(
            list[ChunkRow],
            [
                {
                    "text": "This is some repeated boilerplate that should be killed.",
                    "kind": "p",
                    "doc_sha256": "s1",
                    "url": "u1",
                    "chunk_id": "c1",
                    "score": 0.0,
                    "source_rank": 1,
                    "doc_rank": 1,
                },
                {
                    "text": "This is some unique content that should definitely be kept because it is long enough.",
                    "kind": "p",
                    "doc_sha256": "s2",
                    "url": "u2",
                    "chunk_id": "c2",
                    "score": 0.0,
                    "source_rank": 2,
                    "doc_rank": 2,
                },
            ],
        )
        import hashlib
        import re

        def get_h(t: str) -> str:
            clean = re.sub(r"\s+", " ", t).strip().lower()
            return hashlib.sha256(clean.encode()).hexdigest()[:16]

        h_repeated = get_h(chunks[0]["text"])
        counts = Counter({h_repeated: 3})

        filtered = kill_boilerplate(chunks, global_counts=counts)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["text"], chunks[1]["text"])

    def test_scorers(self):
        chunk = cast(
            ChunkRow,
            {
                "text": "Python is a programming language created in 1991.",
                "kind": "p",
                "doc_sha256": "s1",
                "url": "u1",
                "chunk_id": "c1",
                "score": 0.0,
                "source_rank": 1,
                "doc_rank": 1,
            },
        )

        # Overlap + shape
        s1 = score_query_overlap(chunk, query="Python programming")
        self.assertTrue(s1 > 0.5)  # Overlap + Year + Def-like "is a"

        # BM25
        chunks = cast(
            list[ChunkRow],
            [
                chunk,
                {
                    "text": "Cooking pasta is easy.",
                    "kind": "p",
                    "doc_sha256": "s2",
                    "url": "u2",
                    "chunk_id": "c2",
                    "score": 0.0,
                    "source_rank": 2,
                    "doc_rank": 2,
                },
            ],
        )
        scored = score_bm25(chunks, query="Python programming")
        self.assertTrue(scored[0]["score"] > scored[1]["score"])

    def test_join_dedup(self):
        chunks = cast(
            list[ChunkRow],
            [
                {
                    "text": "Same text",
                    "kind": "p",
                    "doc_sha256": "s1",
                    "url": "u1",
                    "chunk_id": "c1",
                    "score": 1.0,
                    "source_rank": 1,
                    "doc_rank": 1,
                },
                {
                    "text": "same text ",
                    "kind": "p",
                    "doc_sha256": "s2",
                    "url": "u2",
                    "chunk_id": "c2",
                    "score": 0.5,
                    "source_rank": 2,
                    "doc_rank": 2,
                },
            ],
        )
        joined = join_chunks(chunks)
        self.assertEqual(len(joined), 1)
        self.assertEqual(joined[0]["score"], 1.0)

    def test_citation_packing(self):
        chunks = cast(
            list[ChunkRow],
            [
                {
                    "text": "PIRML is deterministic.",
                    "kind": "p",
                    "doc_sha256": "s1",
                    "url": "u1",
                    "chunk_id": "ck0001",
                    "score": 1.0,
                    "source_rank": 1,
                    "doc_rank": 1,
                },
            ],
        )
        cites = pack_citations(chunks, clock=self.clock, query="PIRML")
        self.assertEqual(len(cites), 1)
        self.assertEqual(cites[0]["chunk_id"], "ck0001")
        self.assertIn("PIRML", cites[0]["quote"])

    async def test_full_pipeline(self):
        # Mock Provider
        provider = MockProvider(
            {
                "what is pirml?": [
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

        # Fixture fetcher
        fetcher = FixtureDocFetcher(Path("tests/fixtures/web/responses.json"))
        fetcher._records["https://example.com/p"] = fetcher._records[  # type: ignore
            "https://example.com/docs/page?a=1&b=2"
        ]

        pipeline = WebPipeline(
            provider=provider, fetcher=fetcher, clock=self.clock, tracer=self.tracer
        )

        plan = WebPlan(
            provider="mock", cache="memory", parser="html", scorer="bm25", cite_mode="quote"
        )

        result = await pipeline.run("what is pirml?", plan)
        self.assertTrue(len(result["citations"]) > 0)
        self.assertIn("Deterministic Fixture", result["answer"])

        # Golden verification
        golden_path = Path("tests/golden/web/pipeline_result.json")
        actual_json = json.dumps(result, indent=2, sort_keys=True)

        if os.getenv("PIRML_UPDATE_GOLDEN") == "1":
            golden_path.write_text(actual_json)

        if golden_path.exists():
            expected_json = golden_path.read_text()
            self.assertEqual(actual_json, expected_json)


if __name__ == "__main__":
    unittest.main()
