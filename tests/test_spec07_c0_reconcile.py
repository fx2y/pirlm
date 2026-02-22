from __future__ import annotations

import json
import unittest
from pathlib import Path


class Spec07C0ReconcileTests(unittest.TestCase):
    def _load_text(self, relpath: str) -> str:
        return Path(relpath).read_text(encoding="utf-8")

    def _load_jsonl(self, relpath: str) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for line in Path(relpath).read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
        return rows

    def test_spec_uses_cli_entrypoints_not_runtime_modules(self) -> None:
        spec = self._load_text("spec-0/07-spec.md")
        self.assertNotIn("python -m pirml.runtime.exec", spec)
        self.assertNotIn("python -m pirml.runtime.replay", spec)
        self.assertIn("python -m pirml --prog <prog.py> --out-dir <out_dir>", spec)
        self.assertIn("--replay out/<run_id>/trace.ndjson", spec)

    def test_pointer_policy_is_custom_entry_first(self) -> None:
        spec = self._load_text("spec-0/07-spec.md")
        self.assertIn("CustomEntry", spec)
        self.assertIn("optional CustomMessage is one-line summary only", spec)

    def test_final_boundary_example_is_compact_root(self) -> None:
        spec = self._load_text("spec-0/07-spec.md")
        self.assertIn('{"ok":true,"results":[],"output":', spec)
        self.assertNotIn(
            '{"answer":"…","citations":[{"url":"…","artifact":"a1"}],"runId":"r1"}',
            spec,
        )

    def test_contradictions_x0_to_x10_are_decided(self) -> None:
        rows = self._load_jsonl("spec-0/07/11-contradictions.jsonl")
        contradictions = [row for row in rows if row.get("k") == "con"]
        ids = {str(row["id"]).split(".", 1)[0] for row in contradictions}
        self.assertEqual(ids, {f"X{i}" for i in range(11)})
        for row in contradictions:
            self.assertIn(row.get("decision"), {"KEEP", "ADAPT", "DROP"})
            self.assertIn(row.get("st"), {"decided", "closed"})

    def test_status_truth_ledgers_exist(self) -> None:
        self.assertTrue(Path("spec-0/07-tasks.jsonl").is_file())
        self.assertTrue(Path("spec-0/07-tutorial.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
