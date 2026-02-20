from __future__ import annotations

import unittest
from pirml.toolsearch.search import search_tools, SearchError
from pirml.contracts.schemas import ToolManifest


class TestToolSearch(unittest.TestCase):
    def setUp(self):
        # A simple catalog for testing
        self.catalog: dict[str, ToolManifest] = {
            "echo": {
                "name": "echo",
                "description": "Returns the input string. Use for identity operations. Do not use for logging.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "The text to echo"}
                    }
                },
                "defer_loading": False,  # Hot tool
                "tags": ["utility", "debug"]
            },
            "readfile": {
                "name": "readfile",
                "description": "Reads a file from disk. Use for local access. Do not use for network files.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "The file path"}
                    }
                },
                "defer_loading": False,  # Hot tool
                "tags": ["fs", "io"]
            },
            "bash": {
                "name": "bash",
                "description": "Executes a bash command. Use for scripting. Do not use for complex logic.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The command string"}
                    }
                },
                "defer_loading": True,  # Deferred tool
                "tags": ["script", "os"]
            },
            "grep": {
                "name": "grep",
                "description": "Searches for a pattern in a file. Use for text processing. Do not use for binary data.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "The regex pattern"},
                        "path": {"type": "string", "description": "The file path"}
                    }
                },
                "defer_loading": True,
                "tags": ["fs", "search"]
            },
            "ls": {
                "name": "ls",
                "description": "Lists files in a directory. Use for exploration. Do not use for bulk metadata.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "The directory path"}
                    }
                },
                "defer_loading": True,
                "tags": ["fs", "exploration"]
            },
            "mkdir": {
                "name": "mkdir",
                "description": "Creates a directory. Use for setup. Do not use for temporary files.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "The directory path"}
                    }
                },
                "defer_loading": True,
                "tags": ["fs", "setup"]
            }
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
        all_deferred = {k: {**v, "defer_loading": True} for k, v in self.catalog.items()}
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
