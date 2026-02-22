from __future__ import annotations

import json
import os
import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from pirml.ux.headless import run_headless


class TestSpec07C5Headless(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.project_root = self.tmp_path / "project"
        self.project_root.mkdir()
        self.art_dir = self.tmp_path / "art"
        self.art_dir.mkdir()
        self.out_dir = self.tmp_path / "out"
        self.out_dir.mkdir()
        self.prog_path = Path("tests/prog_ok.py")

    def tearDown(self):
        self.tmp.cleanup()

    def test_feature_gate_disabled(self):
        # C5.T00: Unsupported if disabled
        with patch.dict(os.environ, {"PIRML_ENABLE_JSON_HEADLESS": "0"}):
            with StringIO() as out, StringIO() as err:
                with patch("sys.stdout", out), patch("sys.stderr", err):
                    with self.assertRaises(SystemExit) as cm:
                        run_headless(stream=["{}\n"])
                    self.assertEqual(cm.exception.code, 1)
                
                res = json.loads(out.getvalue())
                self.assertEqual(res["type"], "pirml_error")
                self.assertEqual(res["error"]["type"], "unsupported")

    def test_event_parsing_success(self):
        # C5.T01, C5.T02, C5.T03: Success path
        event = {
            "type": "tool_execution_start",
            "tool": "pirml_run",
            "args": {
                "prog": str(self.prog_path),
                "out-dir": str(self.out_dir / "r1")
            }
        }
        
        with patch.dict(os.environ, {"PIRML_ENABLE_JSON_HEADLESS": "1"}):
            with StringIO() as out:
                with patch("sys.stdout", out):
                    run_headless(stream=[json.dumps(event) + "\n"], project_root=self.project_root)
                
                res = json.loads(out.getvalue())
                self.assertEqual(res["type"], "pirml_summary")
                self.assertEqual(res["runId"], "r1")
                self.assertTrue(res["ok"])
                self.assertIsNotNone(res["pointer"])

    def test_ignore_unknown_event(self):
        # C5.T01: Ignore unknown
        events = [
            json.dumps({"type": "unknown_type"}) + "\n",
            json.dumps({"type": "tool_execution_start", "tool": "other_tool"}) + "\n"
        ]
        
        with patch.dict(os.environ, {"PIRML_ENABLE_JSON_HEADLESS": "1"}):
            with StringIO() as out, StringIO() as err:
                with patch("sys.stdout", out), patch("sys.stderr", err):
                    run_headless(stream=events)
                
                self.assertEqual(out.getvalue(), "")
                self.assertIn("Ignoring unknown event type unknown_type", err.getvalue())
                self.assertIn("Ignoring tool execution for unknown tool other_tool", err.getvalue())

    def test_ignore_turn_events(self):
        # C5.T01: Explicitly ignore turn events without noise
        events = [
            json.dumps({"type": "turn_start"}) + "\n",
            json.dumps({"type": "turn_end"}) + "\n"
        ]
        
        with patch.dict(os.environ, {"PIRML_ENABLE_JSON_HEADLESS": "1"}):
            with StringIO() as out, StringIO() as err:
                with patch("sys.stdout", out), patch("sys.stderr", err):
                    run_headless(stream=events)
                
                self.assertEqual(out.getvalue(), "")
                self.assertEqual(err.getvalue(), "")

    def test_reinjection_postponed(self):
        # C5.T04: Reinjection stub
        event = {"type": "pirml_reinject_request"}
        
        with patch.dict(os.environ, {"PIRML_ENABLE_JSON_HEADLESS": "1"}):
            with StringIO() as out:
                with patch("sys.stdout", out):
                    run_headless(stream=[json.dumps(event) + "\n"])
                
                res = json.loads(out.getvalue())
                self.assertEqual(res["type"], "pirml_error")
                self.assertEqual(res["error"]["type"], "not_implemented")

    def test_parse_error_robustness(self):
        # AC: parser stable across noise
        stream = [
            "non-json line\n",
            "{invalid-json}\n",
            "\n",
            json.dumps({"type": "turn_start"}) + "\n"
        ]
        
        with patch.dict(os.environ, {"PIRML_ENABLE_JSON_HEADLESS": "1"}):
            with StringIO() as out, StringIO() as err:
                with patch("sys.stdout", out), patch("sys.stderr", err):
                    run_headless(stream=stream)
                
                self.assertEqual(out.getvalue(), "")
                # We skip silently as per AC (non-json lines are noise)

if __name__ == "__main__":
    unittest.main()
