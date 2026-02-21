from __future__ import annotations
import unittest
from pirml.web.etl import chunk_views, pack_batches

class TestWebBatch(unittest.TestCase):
    def test_chunk_views_deterministic(self) -> None:
        text = "Hello world\n\nSection 1\n" + "A" * 5000 + "\n\nSection 2"
        # max_chars=2000
        chunks = chunk_views([text], max_chars=2000)
        self.assertTrue(len(chunks) >= 3)
        self.assertEqual("".join(chunks).replace("\n\n", ""), text.replace("\n\n", ""))
        
        # Test hard cut
        text2 = "B" * 3000
        chunks2 = chunk_views([text2], max_chars=1000)
        self.assertEqual(len(chunks2), 3)
        self.assertEqual("".join(chunks2), text2)

    def test_pack_batches(self) -> None:
        chunks = ["Chunk 1", "Chunk 2", "Chunk 3"]
        batches = pack_batches(chunks, max_chars=15)
        self.assertEqual(len(batches), 2)
        self.assertIn("Chunk 1\n---\nChunk 2", batches[0])
        self.assertEqual(batches[1], "Chunk 3")

if __name__ == "__main__":
    unittest.main()
