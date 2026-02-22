from __future__ import annotations

import json
import unittest
from pathlib import Path

from pirml.web.contracts import WEB_SCHEMA_PATHS, WEB_TRACE_OPS
from scripts.schema_lint import validate_web_trace_row


class Spec08C3ContractRegistryTests(unittest.TestCase):
    def test_trace_schema_registered(self) -> None:
        self.assertIn("web_trace", WEB_SCHEMA_PATHS)
        self.assertTrue(WEB_SCHEMA_PATHS["web_trace"].is_file())

    def test_web_trace_schema_registered(self) -> None:
        payload = json.loads(
            Path("pirml/contracts/web_trace_frame.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["title"], "WebTraceFrame")

    def test_lint_op_enum_matches_schema(self) -> None:
        payload = json.loads(
            Path("pirml/contracts/web_trace_frame.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(tuple(payload["properties"]["op"]["enum"]), WEB_TRACE_OPS)
        self.assertEqual(
            validate_web_trace_row({"op": "bad", "ts": 0, "seq": 1, "ms": 0}, 0),
            [f"rows[0].op must be one of {list(WEB_TRACE_OPS)}"],
        )


if __name__ == "__main__":
    unittest.main()
