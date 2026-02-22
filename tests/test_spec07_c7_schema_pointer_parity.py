from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class TestSpec07C7SchemaPointerParity(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.out_dir = self.tmp_path / "out"
        self.out_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_trace_ptr_resolvability(self):
        # 1. Create a dummy trace and web_output.json
        trace_file = self.out_dir / "web_trace.ndjson"
        trace_file.write_text(
            '{"op":"search_call","ts":1700000000,"seq":1,"ms":10,"q":"test"}\n', encoding="utf-8"
        )

        web_out = self.out_dir / "web_output.json"
        web_out.write_text(
            json.dumps({"answer": "test", "citations": [], "trace_ptr": str(trace_file)}),
            encoding="utf-8",
        )

        # 2. Run schema_lint
        cmd = [
            sys.executable,
            "-m",
            "scripts.schema_lint",
            "--web-output",
            str(web_out),
            "--web-trace",
            str(trace_file),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"schema_lint failed: {res.stderr}")

    def test_trace_ptr_missing_fails(self):
        web_out = self.out_dir / "web_output.json"
        web_out.write_text(
            json.dumps({"answer": "test", "citations": [], "trace_ptr": "nonexistent.ndjson"}),
            encoding="utf-8",
        )

        cmd = [sys.executable, "-m", "scripts.schema_lint", "--web-output", str(web_out)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)
        self.assertIn("Error: web_output.trace_ptr target missing", res.stderr)

    def test_trace_ptr_not_in_args_fails(self):
        trace_file = self.out_dir / "web_trace.ndjson"
        trace_file.write_text(
            '{"op":"search_call","ts":1700000000,"seq":1,"ms":10,"q":"test"}\n', encoding="utf-8"
        )

        web_out = self.out_dir / "web_output.json"
        web_out.write_text(
            json.dumps({"answer": "test", "citations": [], "trace_ptr": str(trace_file)}),
            encoding="utf-8",
        )

        # Another trace file in args, but not the one pointed to
        other_trace = self.out_dir / "other.ndjson"
        other_trace.write_text("", encoding="utf-8")

        cmd = [
            sys.executable,
            "-m",
            "scripts.schema_lint",
            "--web-output",
            str(web_out),
            "--web-trace",
            str(other_trace),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)
        self.assertIn("not found in --web-trace args", res.stderr)


if __name__ == "__main__":
    unittest.main()
