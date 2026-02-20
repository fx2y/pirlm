from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pirml.compiler.compile import compile_task
from pirml.compiler.extract import ExtractionError, extract_blocks


class TestCompileExtract(unittest.TestCase):
    def test_extract_ok(self):
        raw = """<<<PROG>>>
import asyncio
async def main():
    print('hello')
<<<CONTRACT>>>
{"tool_deps": []}"""
        prog, contract = extract_blocks(raw)
        self.assertEqual(prog, "import asyncio\nasync def main():\n    print('hello')")
        self.assertEqual(contract, '{"tool_deps": []}')

    def test_extract_with_leading_whitespace(self):
        # Leading whitespace is okay if it's JUST whitespace?
        # Actually, extract.py says: if m[0].strip(): raise ExtractionError("extra_prose", ...)
        # So m[0] can contain whitespace.
        raw = "  \n<<<PROG>>>\ncode\n<<<CONTRACT>>>\n{}"
        prog, contract = extract_blocks(raw)
        self.assertEqual(prog, "code")
        self.assertEqual(contract, "{}")

    def test_fail_leading_prose(self):
        raw = "Here is the code:\n<<<PROG>>>\ncode\n<<<CONTRACT>>>\n{}"
        with self.assertRaisesRegex(ExtractionError, "extra_prose"):
            extract_blocks(raw)

    def test_fail_missing_sentinel(self):
        raw = "<<<PROG>>>\ncode\n{}"
        with self.assertRaisesRegex(ExtractionError, "sentinel_cardinality"):
            extract_blocks(raw)

    def test_fail_duplicate_sentinel(self):
        raw = "<<<PROG>>>\ncode\n<<<PROG>>>\nmore code\n<<<CONTRACT>>>\n{}"
        with self.assertRaisesRegex(ExtractionError, "sentinel_cardinality"):
            extract_blocks(raw)

    def test_fail_invalid_order(self):
        raw = "<<<CONTRACT>>>\n{}\n<<<PROG>>>\ncode"
        with self.assertRaisesRegex(ExtractionError, "invalid_order"):
            extract_blocks(raw)

    def test_extract_failure_uses_compile_error_file_shape(self):
        with tempfile.TemporaryDirectory() as out_dir:
            out_path = Path(out_dir)
            with patch(
                "pirml.compiler.model.StubModelAdapter.compile_once", return_value="invalid"
            ):
                result = compile_task(
                    task="echo hello",
                    tools_dir=Path("tests/fixtures/toolsearch/catalog"),
                    out_dir=out_path,
                    skip_smoke=True,
                )
            self.assertFalse(result.get("ok"))
            payload = json.loads((out_path / "compile_error.json").read_text(encoding="utf-8"))
            self.assertIn("stage", payload)
            self.assertEqual(payload.get("stage"), "extract")
            self.assertIn("errors", payload)
            self.assertIsInstance(payload["errors"], list)
            self.assertTrue(payload["errors"])


if __name__ == "__main__":
    unittest.main()
