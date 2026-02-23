from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class TestSpec07C3Toolpack(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.art_dir = self.tmp_path / "art"
        self.art_dir.mkdir()
        self.out_dir = self.tmp_path / "out"
        self.out_dir.mkdir()

        # Create some dummy artifacts
        from pirml.artifacts.paths import default_layout
        from pirml.artifacts.store import ArtifactStore

        self.store = ArtifactStore(layout=default_layout(root=self.art_dir))
        self.aid = self.store.put_raw(b"line 1\nline 2\nline 3\n", kind="test", mime="text/plain")
        self.web_aid = self.store.put_raw(
            b"pirml deterministic evidence sample\n",
            kind="raw",
            mime="text/plain",
            src={"url": "https://example.com/docs/page"},
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_open_meta(self):
        # C3.T01: Implement `pirml-open` wrapper
        cmd = [
            sys.executable,
            "-m",
            "scripts.tools.open",
            self.aid,
            "--mode",
            "meta",
            "--art-root",
            str(self.art_dir),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        meta = json.loads(res.stdout)
        self.assertEqual(meta["id"], self.aid)

    def test_open_bytes(self):
        # C3.T01: Implement `pirml-open` wrapper
        cmd = [
            sys.executable,
            "-m",
            "scripts.tools.open",
            self.aid,
            "--mode",
            "bytes",
            "--art-root",
            str(self.art_dir),
        ]
        res = subprocess.run(cmd, capture_output=True)
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout, b"line 1\nline 2\nline 3\n")

    def test_open_not_found(self):
        # T07: Typed fail lanes
        cmd = [
            sys.executable,
            "-m",
            "scripts.tools.open",
            "missing",
            "--art-root",
            str(self.art_dir),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)
        err = json.loads(res.stderr)
        self.assertEqual(err["type"], "artifact")

    def test_open_path_view(self):
        # C3.T02: Support path inputs by extracting ID
        from typing import cast

        from pirml.artifacts.view_dsl import SliceSpec
        from pirml.artifacts.view_materialize import ViewMaterializer

        spec = cast(SliceSpec, {"op": "lines", "a": 0, "b": 0})
        mat = ViewMaterializer(self.store)
        vid = mat.materialize(self.aid, spec)

        path = f"art/views/{vid}.ndjson"
        cmd = [
            sys.executable,
            "-m",
            "scripts.tools.open",
            path,
            "--mode",
            "text",
            "--art-root",
            str(self.art_dir),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "line 1")

    def test_slice_lines(self):
        # C3.T03: Implement `pirml-slice` wrapper
        spec = {"op": "lines", "a": 0, "b": 1}
        cmd = [
            sys.executable,
            "-m",
            "scripts.tools.slice",
            self.aid,
            json.dumps(spec),
            "--art-root",
            str(self.art_dir),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        vid = res.stdout.strip()

        # Verify vid content via open text mode
        cmd_open = [
            sys.executable,
            "-m",
            "scripts.tools.open",
            vid,
            "--mode",
            "text",
            "--art-root",
            str(self.art_dir),
        ]
        res_open = subprocess.run(cmd_open, capture_output=True, text=True)
        self.assertEqual(res_open.stdout.strip(), "line 1\nline 2")

    def test_slice_bad_spec(self):
        # T07: Typed fail lanes
        cmd = [
            sys.executable,
            "-m",
            "scripts.tools.slice",
            self.aid,
            '{"op":"invalid"}',
            "--art-root",
            str(self.art_dir),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)
        err = json.loads(res.stderr)
        self.assertEqual(err["type"], "integrity")

    def test_replay_wrapper(self):
        # C3.T05: Implement `pirml-replay` wrapper
        # 1. Run live to get trace
        prog_path = Path("tests/prog_ok.py")
        run_out = self.tmp_path / "run_out"
        cmd_run = [
            sys.executable,
            "-m",
            "pirml",
            "--prog",
            str(prog_path),
            "--out-dir",
            str(run_out),
        ]
        subprocess.run(cmd_run, check=True)
        trace_path = run_out / "trace.ndjson"

        # 2. Replay via wrapper
        replay_out = self.tmp_path / "replay_out"
        cmd_replay = [
            sys.executable,
            "-m",
            "scripts.tools.replay",
            str(prog_path),
            str(trace_path),
            "--out-dir",
            str(replay_out),
        ]
        res = subprocess.run(cmd_replay, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertTrue((replay_out / "final.json").exists())

    def test_replay_missing_trace_typed_error(self):
        cmd = [
            sys.executable,
            "-m",
            "scripts.tools.replay",
            "tests/prog_ok.py",
            str(self.tmp_path / "missing" / "trace.ndjson"),
            "--out-dir",
            str(self.tmp_path / "replay_missing"),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)
        err = json.loads(res.stderr)
        self.assertEqual(err["type"], "artifact")

    def test_search_by_kind_and_url(self):
        cmd = [
            sys.executable,
            "-m",
            "scripts.tools.search",
            "--kind",
            "raw",
            "--url",
            "example.com/docs",
            "--json",
            "--art-root",
            str(self.art_dir),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        rows = json.loads(res.stdout)
        self.assertTrue(rows)
        ids = {row["id"] for row in rows}
        self.assertIn(self.web_aid, ids)

    def test_search_by_content(self):
        cmd = [
            sys.executable,
            "-m",
            "scripts.tools.search",
            "--contains",
            "deterministic evidence",
            "--json",
            "--art-root",
            str(self.art_dir),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        rows = json.loads(res.stdout)
        ids = {row["id"] for row in rows}
        self.assertIn(self.web_aid, ids)


if __name__ == "__main__":
    unittest.main()
