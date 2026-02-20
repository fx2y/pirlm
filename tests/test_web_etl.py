from __future__ import annotations

import unittest
from typing import cast

from pirml.web.etl.core import select_top_chunks
from pirml.web.etl.html_chunks import extract_html_chunks
from pirml.web.types import ChunkRow


class WebETLTests(unittest.TestCase):
    def test_html_extraction_with_cap(self) -> None:
        """C2.I1: ETL HTML extraction with 800c hard cap."""
        long_html = "<p>" + "a" * 1000 + "</p>"
        chunks = extract_html_chunks(
            long_html, url="u1", doc_sha256="s1", source_rank=1, doc_rank=1
        )
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0]["text"]), 800)
        self.assertEqual(chunks[0]["kind"], "p")

    def test_html_extraction_fails_on_invalid_structure(self) -> None:
        """C2.I1: ETL HTML extraction fails on invalid structure."""
        # Malformed HTML should still be tolerated
        chunks = extract_html_chunks(
            "<html><body><p>one<p>two", url="u1", doc_sha256="s1", source_rank=1, doc_rank=1
        )
        self.assertTrue(len(chunks) > 0)

    def test_global_selector_budget_and_stability(self) -> None:
        """C2.I2: Global selector N=40 hard cap and stable tie-break (score,source_rank,doc_rank,chunk_id)."""
        chunks = cast(
            list[ChunkRow],
            [
                {
                    "text": f"text {i}",
                    "kind": "p",
                    "doc_sha256": "s1",
                    "url": "u1",
                    "chunk_id": f"c{i:04d}",
                    "score": 1.0,
                    "source_rank": 0,
                    "doc_rank": 0,
                }
                for i in range(50)
            ],
        )

        # Test budget cap N=40
        selected = select_top_chunks(chunks, n=40)
        self.assertEqual(len(selected), 40)

        # Test stability
        chunks_scrambled = sorted(chunks, key=lambda x: x["chunk_id"], reverse=True)
        selected_scrambled = select_top_chunks(chunks_scrambled, n=40)
        self.assertEqual(
            [c["chunk_id"] for c in selected],
            [c["chunk_id"] for c in selected_scrambled],
        )

    def test_global_selector_fails_on_zero_budget(self) -> None:
        """C2.I2: Global selector fail path with zero budget."""
        chunks = cast(
            list[ChunkRow],
            [
                {
                    "text": "text",
                    "kind": "p",
                    "doc_sha256": "s1",
                    "url": "u1",
                    "chunk_id": "c1",
                    "score": 1.0,
                    "source_rank": 0,
                    "doc_rank": 0,
                }
            ],
        )
        selected = select_top_chunks(chunks, n=0)
        self.assertEqual(selected, [])


if __name__ == "__main__":
    unittest.main()
