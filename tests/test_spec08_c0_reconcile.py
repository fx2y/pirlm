from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from pirml.runtime.tools import default_registry
from tests.spec08_support import load_jsonl


class Spec08C0ReconcileTests(unittest.TestCase):
    def test_tool_surface_unchanged(self) -> None:
        src = Path("pirml/runtime/tools.py").read_text(encoding="utf-8")
        registered = set(re.findall(r'registry\.register\("([^"]+)"', src))
        self.assertEqual(registered, {"echo", "readfile", "bash"})

        # Runtime fail-closed check for unknown tool remains active.
        result = default_registry().execute("spec08_unknown_tool", {})
        self.assertFalse(result.get("ok", True))
        self.assertEqual(result.get("error", {}).get("type"), "tool_not_found")

    def test_runtime_final_root_compact(self) -> None:
        schema = json.loads(Path("pirml/contracts/final.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema.get("type"), "object")
        self.assertEqual(set(schema.get("required", [])), {"ok", "results"})
        self.assertEqual(schema.get("additionalProperties"), False)
        props = set(schema.get("properties", {}).keys())
        self.assertEqual(props, {"ok", "results", "output", "meta"})

    def test_runtime_final_root_unchanged(self) -> None:
        self.test_runtime_final_root_compact()

    def test_contradictions_x0_to_x8_are_decided(self) -> None:
        rows = load_jsonl("spec-0/08/11-contradictions.jsonl")
        contradictions = [row for row in rows if row.get("k") == "con"]
        ids = {str(row["id"]).split(".", 1)[0] for row in contradictions}
        self.assertEqual(ids, {f"X{i}" for i in range(9)})
        for row in contradictions:
            self.assertEqual(row.get("st"), "decided")
            self.assertIn(row.get("decision"), {"KEEP", "ADAPT", "DROP"})

    def test_status_truth_ledgers_exist(self) -> None:
        self.assertTrue(Path("spec-0/08-tasks.jsonl").is_file())
        self.assertTrue(Path("spec-0/08-tutorial.jsonl").is_file())

    def test_c0_done_across_ledgers(self) -> None:
        htn = load_jsonl("spec-0/08-htn.jsonl")
        c0_cycle = next(row for row in htn if row.get("k") == "cycle" and row.get("id") == "C0")
        c0_state = next(row for row in htn if row.get("k") == "state" and row.get("id") == "C0")
        self.assertEqual(c0_cycle.get("status"), "done")
        self.assertEqual(c0_state.get("status"), "done")

        tasks = load_jsonl("spec-0/08-tasks.jsonl")
        c0_task_state = next(
            row for row in tasks if row.get("k") == "state" and row.get("c") == "C0"
        )
        self.assertEqual(c0_task_state.get("st"), "done")

        cycle_rows = load_jsonl("spec-0/08/10-cycle-c0-reconcile.jsonl")
        cycle_meta = next(row for row in cycle_rows if row.get("k") == "meta")
        cycle = next(row for row in cycle_rows if row.get("k") == "cycle")
        self.assertEqual(cycle_meta.get("status"), "done")
        self.assertEqual(cycle.get("status"), "done")


if __name__ == "__main__":
    unittest.main()
