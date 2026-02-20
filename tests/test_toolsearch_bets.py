import os
import unittest

from pirml.contracts.schemas import ToolManifest
from pirml.toolsearch.search import (
    BACKENDS,
    SEARCH_CACHE,
    SearchError,
    build_rewrite_map,
    cache_key,
    jaccard_similarity,
    rewrite_query,
    search_tools,
    search_with_cache,
)


class StubExtBackend:
    def search(self, catalog, query, k=5):
        if "fail" in query:
            raise SearchError("ext_fail", "External search failed")
        return ["svc.ext_tool"]


class TestToolSearchBets(unittest.TestCase):
    def setUp(self):
        SEARCH_CACHE.clear()
        self.catalog: dict[str, ToolManifest] = {
            "svc.list_files": {
                "name": "svc.list_files",
                "description": "Lists files in a directory. Use for exploration. Do not use for deletion.",
                "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
                "defer_loading": True,
                "verbs": ["ls", "dir"],
                "nouns": ["directory", "folder"],
                "aliases": ["list_files_alias"],
            },
            "svc.read_file": {
                "name": "svc.read_file",
                "description": "Reads content of a file. Use for analysis. Do not use for binary files.",
                "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
                "defer_loading": False,  # Hot tool
                "verbs": ["cat", "read"],
                "nouns": ["file", "document"],
            },
            "core.echo": {
                "name": "core.echo",
                "description": "Echoes back the input. Use for testing. Do not use for logging.",
                "input_schema": {"type": "object", "properties": {"msg": {"type": "string"}}},
                "defer_loading": False,  # Hot tool
            },
        }

    def test_alias_rewrite_recall_lift(self):
        rewrite_map = build_rewrite_map(self.catalog)
        query = "ls home"
        # We test rewrite_query directly
        rewritten = rewrite_query(query, rewrite_map)
        self.assertIn("svc.list_files", rewritten)

        # search_tools internally calls rewrite_query for BM25
        results = search_tools(self.catalog, query)
        self.assertEqual(results[0], "svc.list_files")

    def test_baseline_preservation(self):
        query = "read_file"
        results = search_tools(self.catalog, query)
        self.assertEqual(results[0], "svc.read_file")

    def test_search_cache_direct_hit(self):
        query = "read file"
        # First search should be a miss
        res1 = search_with_cache(self.catalog, query)
        self.assertEqual(len(SEARCH_CACHE), 1)

        # Second search should be a hit
        res2 = search_with_cache(self.catalog, query)
        self.assertEqual(res1, res2)
        self.assertEqual(len(SEARCH_CACHE), 1)

    def test_search_stability_reuse(self):
        # Ensure CI is not set to true for this test
        orig_ci = os.getenv("CI")
        if orig_ci:
            os.environ["CI"] = "0"

        try:
            query1 = "read file contents"
            res1 = search_with_cache(self.catalog, query1, stability_threshold=0.5)

            query2 = "read file"
            res2 = search_with_cache(self.catalog, query2, stability_threshold=0.5)

            self.assertEqual(res1, res2)
            key2 = cache_key(query2, self.catalog, "bm25", 5)
            self.assertNotIn(key2, SEARCH_CACHE)
        finally:
            if orig_ci:
                os.environ["CI"] = orig_ci
            else:
                os.environ.pop("CI", None)

    def test_jaccard_similarity(self):
        self.assertEqual(jaccard_similarity("a b c", "a b c"), 1.0)
        self.assertEqual(jaccard_similarity("a b", "a c"), 0.3333333333333333)
        self.assertEqual(jaccard_similarity("", ""), 1.0)

    def test_ext_backend_stub(self):
        BACKENDS["ext"] = StubExtBackend()
        try:
            results = search_tools(self.catalog, "some query", mode="ext")
            self.assertEqual(results, ["svc.ext_tool"])

            with self.assertRaises(SearchError) as cm:
                search_tools(self.catalog, "fail please", mode="ext")
            self.assertEqual(cm.exception.type, "ext_fail")
        finally:
            del BACKENDS["ext"]

    def test_invalid_mode(self):
        with self.assertRaises(SearchError) as cm:
            search_tools(self.catalog, "query", mode="invalid")
        self.assertEqual(cm.exception.type, "invalid_mode")


if __name__ == "__main__":
    unittest.main()
