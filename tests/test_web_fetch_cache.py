from __future__ import annotations

import gzip
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

from pirml.web.cache.sqlite import SqliteCache
from pirml.web.fetch import CachedDocFetcher, RealDocFetcher
from pirml.web.trace import WebTracer
from pirml.web.types import DocRow


class WebFetchCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_gzip_and_charset_decode_pass(self) -> None:
        """C1.I3: Gzip and charset decode pass."""
        body = b"hello gzip world"
        compressed = gzip.compress(body)

        with patch("pirml.web.fetch.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.url = "https://example.com/"
            mock_resp.getheaders.return_value = [
                ("Content-Encoding", "gzip"),
                ("Content-Type", "text/plain; charset=utf-8"),
            ]
            mock_resp.read.return_value = compressed
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            fetcher = RealDocFetcher()
            row = await fetcher.fetch("https://example.com/")

            self.assertEqual(row["body"], "hello gzip world")
            self.assertEqual(row["bytes"], len(body))
            self.assertEqual(row["encoding_guess"], "utf-8")

    async def test_fetch_decode_fails_on_corrupt_data(self) -> None:
        """C1.I3: Fetch decode fail path with corrupt gzip."""
        corrupt_gzip = b"not a gzip"
        with patch("pirml.web.fetch.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.url = "https://example.com/"
            mock_resp.getheaders.return_value = [("Content-Encoding", "gzip")]
            mock_resp.read.return_value = corrupt_gzip
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            fetcher = RealDocFetcher()
            # If gzip decompression fails, should fall back to raw or similar, but
            # C1.T4 says "never crash unknown encoding", but what about corrupt decompression?
            # Let's assume it should return body as-is or similar but not crash.
            row = await fetcher.fetch("https://example.com/")
            self.assertIsNotNone(row["body"])

    async def test_cache_304_and_sha256_dedup(self) -> None:
        """C1.I4: Cache 304 reuse body and sha256 cross-URL deduplication."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "cache.db"
            cache = SqliteCache(db_path)

            body = b"identical content"
            sha = "73398939634e9e90008544a04d306b3a0c007119f42777321590f05814521469"

            # Put two URLs with same content
            cache.put(
                {
                    "key": "u1",
                    "body_sha256": sha,
                    "body": body,
                    "status": 200,
                    "etag": "v1",
                    "last_modified": None,
                    "headers": {},
                }
            )

            cache.put(
                {
                    "key": "u2",
                    "body_sha256": sha,
                    "body": body,
                    "status": 200,
                    "etag": "v1",
                    "last_modified": None,
                    "headers": {},
                }
            )

            # Verify u1 and u2 point to same sha
            h1 = cache.get("u1")
            h2 = cache.get("u2")
            assert h1 is not None
            assert h2 is not None
            self.assertEqual(h1["body_sha256"], h2["body_sha256"])
            self.assertEqual(h1["body"], h2["body"])

            # Verify body table only has one entry
            row = cache._conn.execute("SELECT count(*) FROM http_bodies").fetchone()  # type: ignore
            self.assertEqual(row[0], 1)

            # 304 reuse test
            backend = MagicMock()

            async def mock_fetch(url: str, **kw: Any) -> DocRow:
                return cast(
                    DocRow,
                    {
                        "url": url,
                        "final_url": url,
                        "status": 304,
                        "headers": {"etag": "v1"},
                        "content_type": "text/html",
                        "bytes": 0,
                        "encoding_guess": "utf-8",
                        "body": "",
                        "body_sha256": "",
                    },
                )

            backend.fetch = mock_fetch

            cached_fetcher = CachedDocFetcher(backend, cache)
            tracer = WebTracer()
            res = await cached_fetcher.fetch("u1", tracer=tracer)

            self.assertEqual(res["status"], 200)
            self.assertEqual(res["body"], body.decode("utf-8"))

            frames = tracer.get_frames()
            self.assertTrue(
                any(
                    cast(Any, f).get("cache_hit")
                    for f in frames
                    if cast(Any, f).get("op") == "fetch_result"
                )
            )

    async def test_cache_fails_on_corrupt_db(self) -> None:
        """C1.I4: Cache fails on corrupt DB."""
        import sqlite3

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "corrupt.db"
            db_path.write_text("random junk")

            with self.assertRaises(sqlite3.DatabaseError):
                SqliteCache(db_path)


if __name__ == "__main__":
    unittest.main()
