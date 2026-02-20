from __future__ import annotations

import unittest
from typing import cast

from pirml.clock import SequenceClock
from pirml.web.cite import pack_citations
from pirml.web.types import ChunkRow


class WebCiteTests(unittest.TestCase):
    def test_citation_resolvability_and_limits(self) -> None:
        """C2.I3: Citation resolvability, 25 word cap, and clock-linked retrieved_at."""
        chunks = cast(
            list[ChunkRow],
            [
                {
                    "url": "https://example.com/a",
                    "doc_sha256": "a" * 64,
                    "chunk_id": "chunk-001",
                    "text": "one two three four five six seven eight nine ten "
                    "eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen "
                    "nineteen twenty twentyone twentytwo twentythree twentyfour twentyfive "
                    "twentysix",
                    "kind": "p",
                    "path_hint": "p",
                    "score": 1.0,
                    "source_rank": 0,
                    "doc_rank": 0,
                }
            ],
        )

        clock = SequenceClock(start=1_700_000_000)
        citations = pack_citations(chunks, clock=clock, query="one two")

        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["retrieved_at"], 1_700_000_000)

        # Word cap test: 25 words max
        quote_words = citations[0]["quote"].replace("...", "").split()
        self.assertLessEqual(len(quote_words), 25)

        # Resolvability test: query should be present in quote if possible
        self.assertIn("one two", citations[0]["quote"])

    def test_citation_fails_on_missing_chunk(self) -> None:
        """C2.I3: Citation fail path with empty chunk list."""
        clock = SequenceClock(start=1_700_000_000)
        citations = pack_citations([], clock=clock)
        self.assertEqual(citations, [])


if __name__ == "__main__":
    unittest.main()
