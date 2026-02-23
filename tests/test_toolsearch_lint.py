from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any

from pirml.runtime.lint import lint_catalog, lint_manifest
from pirml.runtime.load import load_catalog


def _base_manifest(name: str = "svc.tool", **overrides: object) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "name": name,
        "description": (
            "This is a tool. It does things. When NOT to use: avoid this for unrelated workflows."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        },
        "input_examples": [{"a": "v1"}, {"a": "v2"}, {"a": "v3"}],
        "idempotent": True,
        "cacheable": True,
        "max_payload_bytes": 4096,
        "timeout_s": 5,
        "retry": {"max_attempts": 1},
        "allowed_callers": ["code_exec"],
        "defer_loading": True,
    }
    manifest.update(overrides)
    return manifest


class TestToolSearchLint(unittest.TestCase):
    def test_manifest_validation(self) -> None:
        m_good = _base_manifest()
        self.assertEqual(lint_manifest(m_good), [])

        m_bad_name = _base_manifest(name="tool")
        self.assertTrue(any(e["code"] == "M1" for e in lint_manifest(m_bad_name)))

        m_long_name = _base_manifest(name="svc." + "a" * 65)
        self.assertTrue(any(e["code"] == "M1" for e in lint_manifest(m_long_name)))

        m_bad_desc = _base_manifest(description="Too short.")
        self.assertTrue(any(e["code"] == "M2" for e in lint_manifest(m_bad_desc)))

        m_no_guidance = _base_manifest(
            description="First sentence. Second sentence. Third sentence."
        )
        self.assertTrue(any(e["code"] == "M2" for e in lint_manifest(m_no_guidance)))

        m_no_schema = _base_manifest()
        del m_no_schema["input_schema"]
        self.assertTrue(any(e["code"] == "M3" for e in lint_manifest(m_no_schema)))

    def test_ambiguous_tool_requires_examples(self) -> None:
        m_alias = _base_manifest(aliases=["other.name"], input_examples=[])
        errors = lint_manifest(m_alias)
        self.assertTrue(any(e["code"] == "M4" and "ambiguous" in e["msg"] for e in errors))

        m_optional = _base_manifest(
            input_schema={
                "type": "object",
                "properties": {"a": {"type": "string"}},
                "required": [],
            },
            input_examples=[],
        )
        errors = lint_manifest(m_optional)
        self.assertTrue(any(e["code"] == "M4" and "ambiguous" in e["msg"] for e in errors))

        m_optional_ok = _base_manifest(
            input_schema={
                "type": "object",
                "properties": {"a": {"type": "string"}},
                "required": [],
            },
            input_examples=[{"a": "val"}, {"a": "alt"}, {"a": "ok"}],
        )
        self.assertEqual(lint_manifest(m_optional_ok), [])

    def test_catalog_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)

            def write_tool(name: str, hot: bool, content: dict[str, Any] | None = None) -> None:
                m = content or _base_manifest(
                    name=f"svc.{name}",
                    defer_loading=not hot,
                    input_examples=[{"a": "x1"}, {"a": "x2"}, {"a": "x3"}],
                )
                (d / f"{name}.json").write_text(json.dumps(m), encoding="utf-8")

            write_tool("t1", hot=False)
            catalog = load_catalog(d)
            errors = lint_catalog(catalog)
            self.assertTrue(any(e["code"] == "C1" for e in errors))
            self.assertTrue(any(e["code"] == "C2" for e in errors))
            self.assertEqual(lint_catalog(catalog, enforce_hot_count=False), [])

            for f in d.glob("*.json"):
                f.unlink()
            write_tool("t1", hot=True)
            write_tool("t2", hot=True)
            write_tool("t3", hot=True)
            write_tool("t4", hot=False)
            self.assertEqual(lint_catalog(load_catalog(d)), [])

            for i in range(4, 7):
                write_tool(f"t{i}", hot=True)
            errors = lint_catalog(load_catalog(d))
            self.assertTrue(any(e["code"] == "C2" for e in errors))

    def test_strict_validation(self) -> None:
        m_unknown = _base_manifest(unknown_field=123)
        errors = lint_manifest(m_unknown)
        self.assertTrue(any(e["code"] == "schema" and "unknown_field" in e["msg"] for e in errors))

        m_bad_example = _base_manifest(input_examples=[{"b": 1}, {"a": "ok"}, {"a": "ok2"}])
        errors = lint_manifest(m_bad_example)
        self.assertTrue(any(e["code"] == "example_invalid" for e in errors))

        m_bad_allowed = _base_manifest(allowed_callers=["direct", "code_exec"])
        self.assertTrue(any(e["code"] == "M8" for e in lint_manifest(m_bad_allowed)))

    def test_strict_loader(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "t1.json").write_text(
                json.dumps(_base_manifest(name="svc.t1")),
                encoding="utf-8",
            )
            (d / "t2.json").write_text(
                json.dumps(_base_manifest(name="svc.t1")),
                encoding="utf-8",
            )

            from pirml.toolsearch.loader import HydrationError

            with self.assertRaises(HydrationError) as cm:
                load_catalog(d, strict=True)
            self.assertEqual(cm.exception.type, "duplicate_name")

            (d / "t2.json").write_text("{malformed", encoding="utf-8")
            with self.assertRaises(HydrationError) as cm:
                load_catalog(d, strict=True)
            self.assertEqual(cm.exception.type, "load_failed")

    def test_schema_and_lint_name_rule_match(self) -> None:
        schema = json.loads(
            Path("pirml/contracts/tool_manifest.schema.json").read_text(encoding="utf-8")
        )
        pattern = schema["properties"]["name"]["pattern"]

        self.assertIsNotNone(re.match(pattern, "svc.tool"))
        self.assertIsNone(re.match(pattern, "tool"))

        good = _base_manifest(name="svc.tool")
        bad = _base_manifest(name="tool")
        self.assertFalse(any(e["code"] == "M1" for e in lint_manifest(good)))
        self.assertTrue(any(e["code"] == "M1" for e in lint_manifest(bad)))


if __name__ == "__main__":
    unittest.main()
