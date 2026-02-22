from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.spec09_support import load_jsonl


class Spec09C0ReconcileTests(unittest.TestCase):
    def test_runtime_tool_surface_unchanged(self) -> None:
        src = Path("pirml/runtime/tools.py").read_text(encoding="utf-8")
        self.assertIn('registry.register("echo"', src)
        self.assertIn('registry.register("readfile"', src)
        self.assertIn('registry.register("bash"', src)

    def test_runtime_final_root_compact(self) -> None:
        schema = json.loads(Path("pirml/contracts/final.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema.get("type"), "object")
        self.assertEqual(set(schema.get("required", [])), {"ok", "results"})
        self.assertEqual(schema.get("additionalProperties"), False)
        self.assertEqual(
            set(schema.get("properties", {}).keys()), {"ok", "results", "output", "meta"}
        )

    def test_runtime_final_schema_rejects_extra_keys(self) -> None:
        schema = json.loads(Path("pirml/contracts/final.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema.get("additionalProperties"), False)

    def test_owner_path_unchanged(self) -> None:
        bridge = Path("pirml/ux/runtime_bridge.py").read_text(encoding="utf-8")
        self.assertIn('"-m",', bridge)
        self.assertIn('"pirml",', bridge)

        wrapper = Path("scripts/pirml_run.py").read_text(encoding="utf-8")
        self.assertIn("from pirml.ux.runtime_bridge import run_once", wrapper)

    def test_contradictions_x0_to_x12_are_decided(self) -> None:
        rows = load_jsonl("spec-0/09/11-contradictions.jsonl")
        contradictions = [row for row in rows if row.get("k") == "con"]
        ids = {str(row["id"]).split(".", 1)[0] for row in contradictions}
        self.assertEqual(ids, {f"X{i}" for i in range(13)})
        for row in contradictions:
            self.assertEqual(row.get("st"), "decided")
            self.assertIn(row.get("decision"), {"KEEP", "ADAPT", "DROP"})

    def test_status_truth_ledgers_exist(self) -> None:
        self.assertTrue(Path("spec-0/09-tasks.jsonl").is_file())
        self.assertTrue(Path("spec-0/09-tutorial.jsonl").is_file())

    def test_c0_done_across_ledgers(self) -> None:
        htn = load_jsonl("spec-0/09-htn.jsonl")
        c0_cycle = next(row for row in htn if row.get("k") == "cycle" and row.get("id") == "C0")
        c0_state = next(row for row in htn if row.get("k") == "state" and row.get("id") == "C0")
        self.assertEqual(c0_cycle.get("status"), "done")
        self.assertEqual(c0_state.get("status"), "done")

        tasks = load_jsonl("spec-0/09-tasks.jsonl")
        c0_task_state = next(
            row for row in tasks if row.get("k") == "state" and row.get("c") == "C0"
        )
        self.assertEqual(c0_task_state.get("st"), "done")

        cycle_rows = load_jsonl("spec-0/09/10-cycle-c0-reconcile.jsonl")
        cycle_meta = next(row for row in cycle_rows if row.get("k") == "meta")
        cycle = next(row for row in cycle_rows if row.get("k") == "cycle")
        self.assertEqual(cycle_meta.get("status"), "done")
        self.assertEqual(cycle.get("status"), "done")


if __name__ == "__main__":
    unittest.main()
