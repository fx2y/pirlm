from __future__ import annotations

import json
import unittest
from pathlib import Path


class WebContractSchemaTests(unittest.TestCase):
    def test_web_contract_schema_files_exist_and_are_strict(self) -> None:
        schema_names = [
            "web_serp.schema.json",
            "web_doc.schema.json",
            "web_extract.schema.json",
            "web_citation.schema.json",
            "web_eval.schema.json",
        ]
        for name in schema_names:
            path = Path("pirml/contracts") / name
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["type"], "object")
            self.assertFalse(payload.get("additionalProperties", True))
            self.assertIn("required", payload)


if __name__ == "__main__":
    unittest.main()
