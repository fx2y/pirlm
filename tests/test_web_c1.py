from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pirml.web.cache.sqlite import SqliteCache
from pirml.web.fetch import CachedDocFetcher, FixtureDocFetcher, RealDocFetcher
from pirml.web.trace import WebTracer


class WebC1Tests(unittest.IsolatedAsyncioTestCase):
    async def test_cached_fetch_304(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "cache.db"
            cache = SqliteCache(db_path)
            
            # Use fixture fetcher as the backend
            backend = FixtureDocFetcher(Path("tests/fixtures/web/responses.json"))
            cached = CachedDocFetcher(backend, cache)
            
            url = "https://example.com/docs/page?a=1&b=2"
            tracer = WebTracer()
            
            # First fetch - should be 200 and store in cache
            row1 = await cached.fetch(url, tracer=tracer)
            self.assertEqual(row1["status"], 200)
            self.assertIsNotNone(cache.get(row1["url"]))
            
            # Second fetch - Mock a 304 response
            class Mock304Fetcher:
                async def fetch(self, url, *, etag=None, last_modified=None, tracer=None):
                    return {
                        "url": url,
                        "final_url": url,
                        "status": 304,
                        "headers": {"etag": "v1"},
                        "content_type": "text/html",
                        "bytes": 0,
                        "encoding_guess": "",
                        "body": "",
                        "body_sha256": ""
                    }
            
            cached_mock = CachedDocFetcher(Mock304Fetcher(), cache) # type: ignore
            row2 = await cached_mock.fetch(url, tracer=tracer)
            
            self.assertEqual(row2["status"], 200) # CachedDocFetcher returns 200 on 304 hit
            self.assertEqual(row2["body"], row1["body"])
            
            frames = tracer.get_frames()
            results = [f for f in frames if f["op"] == "fetch_result"]
            self.assertTrue(any(f.get("cache_hit") for f in results))

    async def test_gzip_decompression(self) -> None:
        import gzip
        
        body = b"hello gzip world"
        compressed = gzip.compress(body)
        
        with patch("pirml.web.fetch.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.url = "https://example.com/"
            mock_resp.getheaders.return_value = [
                ("Content-Encoding", "gzip"),
                ("Content-Type", "text/plain; charset=utf-8")
            ]
            mock_resp.read.return_value = compressed
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp
            
            fetcher = RealDocFetcher()
            row = await fetcher.fetch("https://example.com/")
            
            self.assertEqual(row["body"], "hello gzip world")
            self.assertEqual(row["bytes"], len(body))

    async def test_sha256_deduplication(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "cache.db"
            cache = SqliteCache(db_path)
            
            body = b"identical content"
            sha = "73398939634e9e90008544a04d306b3a0c007119f42777321590f05814521469"
            
            cache.put({
                "key": "u1",
                "body_sha256": sha,
                "body": body,
                "status": 200,
                "etag": "v1",
                "last_modified": None,
                "headers": {}
            })
            
            cache.put({
                "key": "u2",
                "body_sha256": sha,
                "body": body,
                "status": 200,
                "etag": "v1",
                "last_modified": None,
                "headers": {}
            })
            
            # Verify u1 and u2 point to same sha
            h1 = cache.get("u1")
            h2 = cache.get("u2")
            self.assertEqual(h1["body_sha256"], h2["body_sha256"])
            self.assertEqual(h1["body"], h2["body"])
            
            # Verify body table only has one entry?
            # We can't easily check unless we query http_bodies directly
            row = cache._conn.execute("SELECT count(*) FROM http_bodies").fetchone() # type: ignore
            self.assertEqual(row[0], 1)
        tracer = WebTracer()
        tracer.emit("search_call", q="test")
        tracer.emit("search_result", status=200, ms=10)
        
        frames = tracer.get_frames()
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0]["op"], "search_call")
        self.assertEqual(frames[1]["op"], "search_result")
        self.assertEqual(frames[1]["ms"], 10)

if __name__ == "__main__":
    unittest.main()
