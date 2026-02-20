from __future__ import annotations

import unittest

from pirml.contracts.schemas import ToolManifest
from pirml.toolsearch.index import K_CAP
from pirml.toolsearch.search import SearchError, is_regex_query, search_tools, to_tool_references


class TestToolSearch(unittest.TestCase):
    def setUp(self):
        # A simple catalog for testing
        self.catalog: dict[str, ToolManifest] = {
            "echo": {
                "name": "echo",
                "description": "Returns the input string. Use for identity operations. Do not use for logging.",
                "input_schema": {
                    "type": "object",
                    "properties": {"text": {"type": "string", "description": "The text to echo"}},
                },
                "defer_loading": False,  # Hot tool
                "tags": ["utility", "debug"],
            },
            "readfile": {
                "name": "readfile",
                "description": "Reads a file from disk. Use for local access. Do not use for network files.",
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "The file path"}},
                },
                "defer_loading": False,  # Hot tool
                "tags": ["fs", "io"],
            },
            "bash": {
                "name": "bash",
                "description": "Executes a bash command. Use for scripting. Do not use for complex logic.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The command string"}
                    },
                },
                "defer_loading": True,  # Deferred tool
                "tags": ["script", "os"],
            },
            "grep": {
                "name": "grep",
                "description": "Searches for a pattern in a file. Use for text processing. Do not use for binary data.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "The regex pattern"},
                        "path": {"type": "string", "description": "The file path"},
                    },
                },
                "defer_loading": True,
                "tags": ["fs", "search"],
            },
            "ls": {
                "name": "ls",
                "description": "Lists files in a directory. Use for exploration. Do not use for bulk metadata.",
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "The directory path"}},
                },
                "defer_loading": True,
                "tags": ["fs", "exploration"],
            },
            "mkdir": {
                "name": "mkdir",
                "description": "Creates a directory. Use for setup. Do not use for temporary files.",
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "The directory path"}},
                },
                "defer_loading": True,
                "tags": ["fs", "setup"],
            },
        }

    def test_search_top_k(self):
        # Query matching multiple FS tools
        results = search_tools(self.catalog, "file", k=3)
        self.assertEqual(len(results), 3)
        # readfile and grep have "file" in description or schema description
        self.assertIn("readfile", results)
        self.assertIn("grep", results)

    def test_search_deterministic_tie_break(self):
        # Tools with same score (no match in any) should be sorted by hot_rank, arg_count, name
        results1 = search_tools(self.catalog, "nonexistent", k=10)
        results2 = search_tools(self.catalog, "nonexistent", k=10)
        self.assertEqual(results1, results2)
        # Hot tools should come first: echo, readfile (hot_rank 0)
        # Then bash, grep, ls, mkdir (hot_rank 1)
        self.assertEqual(results1[:2], ["echo", "readfile"])

    def test_regex_search(self):
        results = search_tools(self.catalog, r"^e.h.$", mode="regex")
        self.assertEqual(results, ["echo"])

    def test_regex_invalid_pattern(self):
        with self.assertRaises(SearchError) as cm:
            search_tools(self.catalog, "[", mode="regex")
        self.assertEqual(cm.exception.type, "invalid_pattern")

    def test_regex_pattern_too_long(self):
        long_pattern = "a" * 201
        with self.assertRaises(SearchError) as cm:
            search_tools(self.catalog, long_pattern, mode="regex")
        self.assertEqual(cm.exception.type, "pattern_too_long")

    def test_all_deferred_fail(self):
        # Mark all as deferred
        from typing import cast

        all_deferred = {
            k: cast(ToolManifest, {**v, "defer_loading": True}) for k, v in self.catalog.items()
        }
        with self.assertRaises(SearchError) as cm:
            search_tools(all_deferred, "echo")
        self.assertEqual(cm.exception.type, "all_deferred")

    def test_empty_catalog_fail(self):
        with self.assertRaises(SearchError) as cm:
            search_tools({}, "echo")
        self.assertEqual(cm.exception.type, "missing_tool_definition")

    def test_field_coverage(self):
        # Search for tag "os" -> bash
        self.assertEqual(search_tools(self.catalog, "os", k=1), ["bash"])
        # Search for arg name "command" -> bash
        self.assertEqual(search_tools(self.catalog, "command", k=1), ["bash"])
        # Search for arg desc "identity" -> echo
        self.assertEqual(search_tools(self.catalog, "identity", k=1), ["echo"])

    # G.P1.6: field weighting — name queries must rank the exact-named tool first
    def test_field_weight_name_boost(self):
        # 'echo' as query should surface echo first due to name*3 weighting
        results = search_tools(self.catalog, "echo", k=2)
        self.assertEqual(results[0], "echo")

    # G.P1.7: k-cap enforced even when caller passes k > K_CAP
    def test_k_cap_enforced(self):
        results = search_tools(self.catalog, "file", k=K_CAP + 10)
        self.assertLessEqual(len(results), K_CAP)

    def test_k_cap_constant_value(self):
        self.assertEqual(K_CAP, 5)

    # G.P2.6: auto-mode detection from query shape
    def test_auto_mode_regex_metachar(self):
        self.assertTrue(is_regex_query(r"^echo$"))
        self.assertTrue(is_regex_query("file.*"))
        self.assertTrue(is_regex_query("[abc]"))
        self.assertFalse(is_regex_query("read file"))
        self.assertFalse(is_regex_query("list files in directory"))

    def test_auto_mode_dispatches_regex_for_pattern(self):
        # Pattern with ^ should auto-route to regex mode and match exactly
        results = search_tools(self.catalog, r"^echo$")
        self.assertEqual(results, ["echo"])

    def test_auto_mode_dispatches_bm25_for_plain(self):
        # No metacharacters → bm25 mode; should not raise
        results = search_tools(self.catalog, "file read")
        self.assertIsInstance(results, list)

    # G.P2.7: namespace prefix boost
    def test_namespace_boost_in_bets_catalog(self):
        ns_catalog: dict[str, ToolManifest] = {
            "svc.list_files": {
                "name": "svc.list_files",
                "description": "Lists files. Use for exploration. Do not use for deletion.",
                "input_schema": {"type": "object"},
                "defer_loading": False,
            },
            "core.list_items": {
                "name": "core.list_items",
                "description": "Lists items. Use for inspection. Do not use for deletion.",
                "input_schema": {"type": "object"},
                "defer_loading": False,
            },
        }
        results = search_tools(ns_catalog, "svc.list", k=2)
        self.assertEqual(results[0], "svc.list_files")

    # G.P2.8: to_tool_references produces vendor-compatible blocks
    def test_to_tool_references_shape(self):
        refs = to_tool_references(["echo", "readfile", "bash"])
        self.assertEqual(len(refs), 3)
        for ref in refs:
            self.assertEqual(ref["type"], "tool_use")
            self.assertIn(ref["name"], ["echo", "readfile", "bash"])

    def test_to_tool_references_cap(self):
        long_names = [f"tool_{i}" for i in range(K_CAP + 5)]
        refs = to_tool_references(long_names)
        self.assertEqual(len(refs), K_CAP)

    def test_to_tool_references_empty(self):
        self.assertEqual(to_tool_references([]), [])
