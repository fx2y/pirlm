from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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

            def write_tool(name: str, hot: bool) -> None:
                (d / f"{name}.json").write_text(
                    json.dumps(
                        {
                            "name": f"svc.{name}",
                            "description": "Sentence one. Sentence two. When NOT to use: none.",
                            "input_schema": {},
                            "defer_loading": not hot,
                        }
                    )
                )

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


if __name__ == "__main__":
    unittest.main()
