from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from pirml.runtime.lint import lint_catalog, lint_manifest
from pirml.runtime.load import load_catalog


class TestToolSearchLint(unittest.TestCase):
    def test_manifest_validation(self) -> None:
        # Good manifest
        m_good = {
            "name": "svc.tool",
            "description": "This is a tool. It does things. When NOT to use: don't use it for other things.",
            "input_schema": {"type": "object"},
            "defer_loading": True,
        }
        self.assertEqual(lint_manifest(m_good), [])

        # Bad name: no dots
        m_bad_name = m_good | {"name": "tool"}
        errors = lint_manifest(m_bad_name)
        self.assertTrue(any(e["code"] == "M1" for e in errors))

        # Bad name: too long
        m_long_name = m_good | {"name": "svc." + "a" * 65}
        errors = lint_manifest(m_long_name)
        self.assertTrue(any(e["code"] == "M1" for e in errors))

        # Bad desc: too short
        m_bad_desc = m_good | {"description": "Too short."}
        errors = lint_manifest(m_bad_desc)
        self.assertTrue(any(e["code"] == "M2" for e in errors))

        # Bad desc: missing "when not to use"
        m_no_guidance = m_good | {"description": "First sentence. Second sentence. Third sentence."}
        errors = lint_manifest(m_no_guidance)
        self.assertTrue(any(e["code"] == "M2" for e in errors))

        # Missing input_schema
        m_no_schema = dict(m_good)
        del m_no_schema["input_schema"]
        errors = lint_manifest(m_no_schema)
        self.assertTrue(any(e["code"] == "M3" for e in errors))

    def test_catalog_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)

            def write_tool(name: str, hot: bool, content: dict[str, Any] | None = None) -> None:
                m = content or {
                    "name": f"svc.{name}",
                    "description": "Sentence one. Sentence two. When NOT to use: none. Extra padding to reach 30 chars.",
                    "input_schema": {},
                    "defer_loading": not hot,
                }
                (d / f"{name}.json").write_text(json.dumps(m))

            # Case 1: All deferred (should fail C1 and C2)
            write_tool("t1", hot=False)
            catalog = load_catalog(d)
            errors = lint_catalog(catalog)
            self.assertTrue(any(e["code"] == "C1" for e in errors))
            self.assertTrue(any(e["code"] == "C2" for e in errors))

            # Case 2: 3 hot tools (should pass)
            for f in d.glob("*.json"):
                f.unlink()
            write_tool("t1", hot=True)
            write_tool("t2", hot=True)
            write_tool("t3", hot=True)
            write_tool("t4", hot=False)
            catalog = load_catalog(d)
            self.assertEqual(lint_catalog(catalog), [])

            # Case 3: 6 hot tools (should fail C2)
            for i in range(4, 7):
                write_tool(f"t{i}", hot=True)
            catalog = load_catalog(d)
            errors = lint_catalog(catalog)
            self.assertTrue(any(e["code"] == "C2" for e in errors))

    def test_strict_validation(self) -> None:
        # Unknown key
        m_unknown = cast(
            "dict[str, Any]",
            {
                "name": "svc.tool",
                "description": "Sentence one. Sentence two. When NOT to use: none. Long enough.",
                "input_schema": {},
                "unknown_field": 123,
            },
        )
        errors = lint_manifest(m_unknown)
        self.assertTrue(any(e["code"] == "schema" and "unknown_field" in e["msg"] for e in errors))

        # Bad example vs schema
        m_bad_example = {
            "name": "svc.tool",
            "description": "Sentence one. Sentence two. When NOT to use: none. Long enough.",
            "input_schema": {"type": "object", "properties": {"a": {"type": "string"}}},
            "input_examples": [{"b": 1}],
        }
        errors = lint_manifest(m_bad_example)
        self.assertTrue(any(e["code"] == "example_invalid" for e in errors))

    def test_strict_loader(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "t1.json").write_text(
                '{"name": "svc.t1", "description": "...", "input_schema": {}}'
            )
            (d / "t2.json").write_text(
                '{"name": "svc.t1", "description": "...", "input_schema": {}}'
            )

            # Duplicate name should raise HydrationError in strict mode
            from pirml.toolsearch.loader import HydrationError

            with self.assertRaises(HydrationError) as cm:
                load_catalog(d, strict=True)
            self.assertEqual(cm.exception.type, "duplicate_name")

            # Malformed JSON
            (d / "t2.json").write_text("{malformed")
            with self.assertRaises(HydrationError) as cm:
                load_catalog(d, strict=True)
            self.assertEqual(cm.exception.type, "load_failed")


if __name__ == "__main__":
    unittest.main()
