from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class TestSpec07Snippets(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.art_dir = self.tmp_path / "art"
        self.art_dir.mkdir()
        self.out_dir = self.tmp_path / "out"
        self.out_dir.mkdir()
        self.prog_path = Path("tests/prog_ok.py")

    def tearDown(self):
        self.tmp.cleanup()

    def test_run_snippet(self):
        # python -m pirml --prog tests/prog_ok.py --out-dir out/r1
        out_r1 = self.out_dir / "r1"
        cmd = [
            sys.executable,
            "-m",
            "pirml",
            "--prog",
            str(self.prog_path),
            "--out-dir",
            str(out_r1),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertTrue((out_r1 / "final.json").exists())
        self.assertTrue((out_r1 / "trace.ndjson").exists())

    def test_replay_snippet(self):
        # python -m pirml --prog tests/prog_ok.py --replay out/r1/trace.ndjson --out-dir out/r2
        out_r1 = self.out_dir / "r1"
        out_r2 = self.out_dir / "r2"

        # 1. Run to get trace
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pirml",
                "--prog",
                str(self.prog_path),
                "--out-dir",
                str(out_r1),
            ],
            check=True,
        )

        # 2. Replay
        cmd = [
            sys.executable,
            "-m",
            "pirml",
            "--prog",
            str(self.prog_path),
            "--replay",
            str(out_r1 / "trace.ndjson"),
            "--out-dir",
            str(out_r2),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertTrue((out_r2 / "final.json").exists())

    def test_toolpack_snippets(self):
        # 1. pirml-open <aid>
        # Need an actual aid
        from pirml.artifacts.paths import default_layout
        from pirml.artifacts.store import ArtifactStore

        store = ArtifactStore(layout=default_layout(root=self.art_dir))
        aid = store.put_raw(b"test", kind="test", mime="text/plain")

        cmd_open = [
            sys.executable,
            "-m",
            "scripts.tools.open",
            aid,
            "--art-root",
            str(self.art_dir),
        ]
        res = subprocess.run(cmd_open, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)

        # 2. pirml-slice <aid> '<spec>'
        spec = {"op": "lines", "a": 0, "b": 0}
        cmd_slice = [
            sys.executable,
            "-m",
            "scripts.tools.slice",
            aid,
            json.dumps(spec),
            "--art-root",
            str(self.art_dir),
        ]
        res = subprocess.run(cmd_slice, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        vid = res.stdout.strip()
        self.assertTrue(len(vid) == 64)  # sha256 hex digest

        # 3. pirml-replay <prog> <trace>
        out_r1 = self.out_dir / "r1"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pirml",
                "--prog",
                str(self.prog_path),
                "--out-dir",
                str(out_r1),
            ],
            check=True,
        )

        out_r3 = self.out_dir / "r3"
        cmd_replay = [
            sys.executable,
            "-m",
            "scripts.tools.replay",
            str(self.prog_path),
            str(out_r1 / "trace.ndjson"),
            "--out-dir",
            str(out_r3),
        ]
        res = subprocess.run(cmd_replay, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertTrue((out_r3 / "final.json").exists())


if __name__ == "__main__":
    unittest.main()
