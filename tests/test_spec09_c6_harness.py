from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class Spec09C6HarnessTests(unittest.TestCase):
    @staticmethod
    def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "scripts.spec09_tool_smoke", *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_tool_smoke_pass(self) -> None:
        proc = self._run_script()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout.strip())
        self.assertTrue(bool(payload["ok"]))
        self.assertEqual(payload["tool_init"], "demo.spec09_smoke")
        for key in (
            "tool_manifest_sha256",
            "live_final_sha256",
            "live_trace_sha256",
            "replay_final_sha256",
            "replay_trace_sha256",
        ):
            self.assertRegex(str(payload[key]), r"^[0-9a-f]{64}$")
        self.assertEqual(payload["live_final_sha256"], payload["replay_final_sha256"])

    def test_tool_smoke_x3_stable(self) -> None:
        outputs: list[str] = []
        for _ in range(3):
            proc = self._run_script()
            self.assertEqual(proc.returncode, 0, proc.stderr)
            outputs.append(proc.stdout.strip())
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])

    def test_tool_smoke_fails_on_invalid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools_dir = root / "tools"
            tools_dir.mkdir(parents=True, exist_ok=True)
            for path in sorted(Path("tools").glob("*.json")):
                shutil.copy2(path, tools_dir / path.name)
            bad_manifest = json.loads((tools_dir / "pirml.echo.json").read_text(encoding="utf-8"))
            bad_manifest["input_examples"] = [{"text": "only-one"}]
            (tools_dir / "pirml.echo.json").write_text(
                json.dumps(bad_manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, "-m", "pirml", "tool", "lint", "--tools-dir", str(tools_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1)
            err = json.loads(proc.stderr.strip())
            self.assertEqual(err["type"], "validation")
            self.assertTrue(str(err["msg"]))


if __name__ == "__main__":
    unittest.main()
