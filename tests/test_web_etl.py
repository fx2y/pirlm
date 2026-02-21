from __future__ import annotations

import unittest
from typing import cast

from pirml.web.etl import fallback_extract, select_top_chunks
from pirml.web.types import ChunkRow


class WebETLTests(unittest.TestCase):
    def test_html_extraction_with_cap(self) -> None:
        """C2.I1: ETL HTML extraction with 800c hard cap (robust text chunks)."""
        long_html = "<p>" + "a" * 1000 + "</p>"
        # B3b fallback: robust text extraction
        chunks = fallback_extract(long_html, url="u1", doc_sha256="s1", source_rank=1, doc_rank=1)
        self.assertTrue(len(chunks) >= 1)
        # fallback_extract in core.py uses 600c window currently, but final clamp is 800c in pipeline
        # Actually it uses text[i : i + chunk_size] where chunk_size=600.
        self.assertTrue(len(chunks[0]["text"]) <= 800)
        self.assertEqual(chunks[0]["kind"], "fallback")

    def test_html_extraction_fails_on_invalid_structure(self) -> None:
        """C2.I1: ETL fail path is typed for empty/invalid payload."""
        with self.assertRaises(ValueError):
            fallback_extract("", url="u1", doc_sha256="s1", source_rank=1, doc_rank=1)

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
        with self.assertRaises(ValueError):
            select_top_chunks(chunks, n=0)


if __name__ == "__main__":
    unittest.main()
