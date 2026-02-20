from __future__ import annotations

import unittest

from pirml.web.urlnorm import normalize_url


class TestURLNorm(unittest.TestCase):
    def test_basic(self) -> None:
        self.assertEqual(normalize_url("http://EXAMPLE.com"), "http://example.com/")
        self.assertEqual(normalize_url("https://example.com/path/"), "https://example.com/path/")

    def test_fragment_stripped(self) -> None:
        self.assertEqual(normalize_url("https://example.com/path#fragment"), "https://example.com/path")

    def test_utm_params_stripped(self) -> None:
        self.assertEqual(
            normalize_url("https://example.com/path?utm_source=google&q=search&utm_medium=email"),
            "https://example.com/path?q=search",
        )

    def test_query_sorted(self) -> None:
        self.assertEqual(
            normalize_url("https://example.com/path?b=2&a=1&c=3"),
            "https://example.com/path?a=1&b=2&c=3",
        )

    def test_empty_query_stripped(self) -> None:
        self.assertEqual(normalize_url("https://example.com/path?"), "https://example.com/path")
        self.assertEqual(normalize_url("https://example.com/path?utm_campaign=xyz"), "https://example.com/path")

    def test_idempotent(self) -> None:
        url = "https://EXAMPLE.COM/Path?B=2&utm_X=Y&A=1#FRAG"
        norm1 = normalize_url(url)
        norm2 = normalize_url(norm1)
        self.assertEqual(norm1, norm2)
        self.assertEqual(norm1, "https://example.com/Path?A=1&B=2")


if __name__ == "__main__":
    unittest.main()
