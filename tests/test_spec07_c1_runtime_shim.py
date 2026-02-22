from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from pirml.runtime.tools import default_registry
from pirml.ux.errors import TimeoutError
from pirml.ux.runtime_bridge import replay, run_once
from pirml.ux.types import PointerPayload


class TestSpec07C1RuntimeShim(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.out_dir = self.tmp_path / "out_r1"
        self.project_root = self.tmp_path / "project"
        self.project_root.mkdir()
        self.art_dir = self.tmp_path / "art"
        self.art_dir.mkdir()
        self.prog_path = Path("tests/prog_ok.py")

    def tearDown(self):
        self.tmp.cleanup()

    def test_run_once_success(self):
        res = run_once(
            prog_path=self.prog_path,
            out_dir=self.out_dir,
            project_root=self.project_root,
            art_root=self.art_dir,
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["runId"], "out_r1")
        ptr = res["pointer"]
        self.assertIsNotNone(ptr)
        if ptr:
            self.assertEqual(ptr["runId"], "out_r1")
        
        # C1.T04: projection facade check
        pirml_dir = self.project_root / ".pirml"
        self.assertTrue((pirml_dir / "trace.ndjson").is_symlink())
        self.assertTrue((pirml_dir / "final.json").is_symlink())
        self.assertTrue((pirml_dir / "artifacts").is_symlink())

    def test_run_once_timeout(self):
        hang_prog = self.tmp_path / "hang.py"
        hang_prog.write_text("import time\ntime.sleep(10)", encoding="utf-8")
        
        with self.assertRaises(TimeoutError):
            run_once(
                prog_path=hang_prog,
                out_dir=self.out_dir,
                timeout=0.1,
            )

    def test_run_once_crash(self):
        # Program crashes -> pirml emits fallback final.json
        crash_prog = self.tmp_path / "crash.py"
        crash_prog.write_text("import sys\nsys.exit(1)", encoding="utf-8")
        
        res = run_once(
            prog_path=crash_prog,
            out_dir=self.out_dir,
            art_root=self.art_dir,
        )
        self.assertFalse(res["ok"])
        self.assertIsNotNone(res["pointer"])
        error = res["error"]
        self.assertIsNotNone(error)
        if error:
            self.assertEqual(error["type"], "runtime")

    def test_replay_success(self):
        res1 = run_once(self.prog_path, self.out_dir, art_root=self.art_dir)
        ptr1 = cast(PointerPayload, res1["pointer"])
        trace_path = Path(ptr1["trace"])
        
        replay_out = self.tmp_path / "out_replay"
        res2 = replay(self.prog_path, trace_path, replay_out, art_root=self.art_dir)
        self.assertTrue(res2["ok"])
        self.assertEqual(res2["runId"], "out_replay")

    def test_guardrail_tool_registry(self):
        registry = default_registry()
        tools = set(registry._tools.keys()) # type: ignore
        self.assertEqual(tools, {"echo", "readfile", "bash"})

    def test_pointer_resolvability(self):
        res = run_once(self.prog_path, self.out_dir, project_root=self.project_root, art_root=self.art_dir)
        ptr = res["pointer"]
        self.assertIsNotNone(ptr)
        if ptr:
            self.assertTrue(Path(ptr["trace"]).exists())
            self.assertTrue(Path(ptr["final"]).exists())
            self.assertTrue(Path(ptr["artifactsDir"]).exists())
            for r in ptr["roots"]:
                self.assertTrue(Path(r).exists())

    def test_ux_summary_derivation(self):
        from pirml.ux.layout import derive_summary
        
        run_once(self.prog_path, self.out_dir, art_root=self.art_dir)
        final_path = self.out_dir / "final.json"
        data = json.loads(final_path.read_text(encoding="utf-8"))
        data["output"] = {"answer": "this is a test answer"}
        final_path.write_text(json.dumps(data), encoding="utf-8")
        
        summary = derive_summary(self.out_dir)
        self.assertEqual(summary, "this is a test answer")
        
        web_out_path = self.out_dir / "web_output.json"
        web_out_path.write_text(json.dumps({"answer": "rich web answer"}), encoding="utf-8")
        summary = derive_summary(self.out_dir)
        self.assertEqual(summary, "rich web answer")

if __name__ == "__main__":
    unittest.main()
