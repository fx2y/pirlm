from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pirml.artifacts import ArtifactStore, default_layout
from pirml.eval_pointers import build_eval_pointer_payload, validate_eval_pointer_refs
from pirml.reporting import aggregate_report


class TestSpec08C6PiPointers(unittest.TestCase):
    def test_report_pointer_validation_passes(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            art_root = root / "art"
            store = ArtifactStore(default_layout(art_root))
            try:
                aid = store.put_raw(b"{}", kind="report", mime="application/json")
            finally:
                store.close()
            trace_path = root / "runs.ndjson"
            report_path = root / "report.json"
            trace_path.write_text("{}\n", encoding="utf-8")
            report_path.write_text("{}", encoding="utf-8")
            rows = [
                {
                    "terminal": True,
                    "task_id": "q1",
                    "suite": "golden50",
                    "ok": True,
                    "acc": 1.0,
                    "latency_ms": 1.0,
                    "cost_usd": 0.0,
                    "pi_ptr": build_eval_pointer_payload(
                        suite="golden50",
                        task_id="q1",
                        run_id="golden50-s00000",
                        trace_ptr=str(trace_path),
                        artifact_ids=[aid],
                        report_ptr=str(report_path),
                        fail_tag="",
                    ),
                }
            ]
            aggregate_report(rows, inputs=[str(trace_path)])
            validate_eval_pointer_refs(rows, art_root=art_root)

    def test_report_pointer_validation_fails_on_missing_ref(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            trace_path = root / "runs.ndjson"
            trace_path.write_text("{}\n", encoding="utf-8")
            rows = [
                {
                    "terminal": True,
                    "task_id": "q1",
                    "suite": "golden50",
                    "ok": False,
                    "acc": 0.0,
                    "latency_ms": 0.0,
                    "cost_usd": 0.0,
                    "fail_tag": "OUTPUT_INVALID",
                    "pi_ptr": build_eval_pointer_payload(
                        suite="golden50",
                        task_id="q1",
                        run_id="golden50-s00000",
                        trace_ptr=str(root / "missing.ndjson"),
                        artifact_ids=["missing-aid"],
                        report_ptr=str(root / "report.json"),
                        fail_tag="OUTPUT_INVALID",
                    ),
                }
            ]
            with self.assertRaisesRegex(Exception, "missing ref"):
                validate_eval_pointer_refs(rows, art_root=root / "art")


if __name__ == "__main__":
    unittest.main()
