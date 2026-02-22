from __future__ import annotations

import json
import unittest
from pathlib import Path

from pirml.web.contracts import WEB_EVAL_REQUIRED_FIELDS
from scripts.schema_lint import validate_web_eval_row


class Spec08C3MetricsSchemaTests(unittest.TestCase):
    def test_required_fields(self) -> None:
        schema = json.loads(
            Path("pirml/contracts/web_eval.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(schema["required"]), set(WEB_EVAL_REQUIRED_FIELDS))

    def test_eval_row_requires_new_fields(self) -> None:
        errors = validate_web_eval_row({"qid": "Q1"}, 0)
        self.assertTrue(any("missing required" in err for err in errors))

    def test_unexpected_field_fails(self) -> None:
        row = {
            "qid": "Q1",
            "plan": "p",
            "acc": 1.0,
            "fetches": 1,
            "bytes": 1,
            "chunks": 1,
            "cache_hit": 1.0,
            "fail_tag": "",
            "timeout_s": 0.0,
            "latency_ms": 1.0,
            "cost_usd": 0.0,
            "tokens_in": 1,
            "tokens_out": 1,
            "bytes_into_model": 1,
            "tool_calls": 1,
            "fanout_peak": 1,
            "invalid_output": False,
            "no_cite": False,
            "replay_match": True,
            "extra": "x",
        }
        errors = validate_web_eval_row(row, 0)
        self.assertTrue(any("unexpected field 'extra'" in err for err in errors))


if __name__ == "__main__":
    unittest.main()
