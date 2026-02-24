from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import cast

from tests.spec09_support import load_jsonl, repo_path


class Spec09C7HardeningSyncTests(unittest.TestCase):
    @staticmethod
    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "pirml", *args],
            check=False,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def _run_module(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            check=False,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def _typed_stderr(proc: subprocess.CompletedProcess[str]) -> dict[str, object]:
        return cast(dict[str, object], json.loads(proc.stderr.strip()))

    def test_snippet_contracts_match_cli_help(self) -> None:
        rows = {str(row.get("id")): row for row in load_jsonl("spec-0/09/95-snippets.jsonl")}
        self.assertIn("--tools-dir", str(rows["S15"]["snip"]))
        self.assertNotIn("--out tools", str(rows["S15"]["snip"]))
        self.assertIn("scripts.tools.replay <prog.py> <trace.ndjson>", str(rows["S09"]["snip"]))
        self.assertIn("scripts.tool_manifest_lint --tools-dir tools", str(rows["S42"]["snip"]))
        self.assertIn("mise run fast && mise run ci", str(rows["S40"]["snip"]))
        self.assertIn("npx tsx tests/test_spec09_c4_extension_policy.ts", str(rows["S40"]["snip"]))
        self.assertNotIn("spec09_tool_smoke --out", str(rows["S35"]["snip"]))

        top_help = self._run("-h")
        self.assertEqual(top_help.returncode, 0, top_help.stderr)
        for cmd in ["doctor", "install-pi-ext", "uninstall-pi-ext", "replay", "tool"]:
            self.assertIn(cmd, top_help.stdout)
        tool_help = self._run("tool", "-h")
        self.assertEqual(tool_help.returncode, 0, tool_help.stderr)
        self.assertIn("{init,lint,pack}", tool_help.stdout)
        self.assertIn("--tools-dir", self._run("tool", "init", "-h").stdout)
        self.assertIn("--tools-dir", self._run("tool", "lint", "-h").stdout)
        self.assertIn("--out", self._run("tool", "pack", "-h").stdout)
        self.assertIn("--target", self._run("install-pi-ext", "-h").stdout)
        self.assertIn("prog trace", self._run("replay", "-h").stdout)

    def test_doc_commands_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools_dir = root / "tools"
            pack_out = root / "out" / "tool-pack.json"
            home = root / "home"
            project = root / "project"
            live_out = root / "live"
            replay_out = root / "replay"
            home.mkdir(parents=True, exist_ok=True)
            project.mkdir(parents=True, exist_ok=True)

            init_proc = self._run("tool", "init", "demo.foo", "--tools-dir", str(tools_dir))
            self.assertEqual(init_proc.returncode, 0, init_proc.stderr)
            lint_proc = self._run("tool", "lint", "--tools-dir", "tools")
            self.assertEqual(lint_proc.returncode, 0, lint_proc.stderr)
            pack_proc = self._run(
                "tool",
                "pack",
                "--tools-dir",
                "tools",
                "--out",
                str(pack_out),
            )
            self.assertEqual(pack_proc.returncode, 0, pack_proc.stderr)
            self.assertTrue(pack_out.is_file())

            live_proc = self._run("--prog", "tests/prog_ok.py", "--out-dir", str(live_out))
            self.assertEqual(live_proc.returncode, 0, live_proc.stderr)
            replay_proc = self._run(
                "replay",
                "tests/prog_ok.py",
                str(live_out / "trace.ndjson"),
                "--out-dir",
                str(replay_out),
            )
            self.assertEqual(replay_proc.returncode, 0, replay_proc.stderr)
            self.assertEqual(
                (live_out / "final.json").read_bytes(),
                (replay_out / "final.json").read_bytes(),
            )

            install_proc = self._run(
                "install-pi-ext",
                "--target",
                "project",
                "--project-root",
                str(project),
                "--home",
                str(home),
            )
            self.assertEqual(install_proc.returncode, 0, install_proc.stderr)
            self.assertTrue((project / ".pi/extensions/pirml/index.ts").is_file())
            uninstall_proc = self._run(
                "uninstall-pi-ext",
                "--target",
                "project",
                "--project-root",
                str(project),
                "--home",
                str(home),
            )
            self.assertEqual(uninstall_proc.returncode, 0, uninstall_proc.stderr)

            doctor_proc = self._run("doctor", "--project-root", str(project), "--home", str(home))
            self.assertIn(doctor_proc.returncode, (0, 1), doctor_proc.stderr)
            self.assertTrue(doctor_proc.stdout.strip())
            for line in doctor_proc.stdout.splitlines():
                row = json.loads(line)
                self.assertIn("check", row)
                self.assertIn("ok", row)

    def test_docs_match_supported_lanes(self) -> None:
        text = repo_path("spec-0/09-spec.md").read_text(encoding="utf-8")
        stale_patterns = (
            "pirml tool lint tools/demo_foo/tool.json",
            "pirml run tasks/demo.ndjson",
            "pirml replay traces/golden.ndjson",
            "pirml replay trace.ndjson",
            "pirml demo",
            "pirml tool lint --all",
            "pirml test --golden",
            "pirml test --chaos",
            "tools/NAME/tool.json",
            "tests/NAME_examples.jsonl",
        )
        for pattern in stale_patterns:
            with self.subTest(pattern=pattern):
                self.assertNotIn(pattern, text)

        required_patterns = (
            "pirml replay <prog.py> <trace.ndjson>",
            "pirml tool pack --tools-dir tools --out artifacts/tool_index.json",
            "python -m scripts.spec09_tool_smoke",
            "mise run spec09-golden",
            "mise run spec09-chaos",
        )
        for pattern in required_patterns:
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, text)

    def test_doc_snippet_unknown_flag_fails(self) -> None:
        proc = self._run("tool", "init", "demo.foo", "--out", "tools")
        self.assertEqual(proc.returncode, 2)
        err = self._typed_stderr(proc)
        self.assertEqual(err["type"], "config")
        self.assertIn("unknown args", str(err["msg"]))

        proc2 = self._run("tool", "lint", "--all")
        self.assertEqual(proc2.returncode, 2)
        err2 = self._typed_stderr(proc2)
        self.assertEqual(err2["type"], "config")
        self.assertIn("unknown args", str(err2["msg"]))

    def test_parse_fail_lanes_never_emit_usage_text(self) -> None:
        checks = [
            ("replay", "tests/prog_ok.py", "out/ci/trace.ndjson", "--timeout", "bad"),
            ("doctor", "--home"),
            ("install-pi-ext", "--target"),
            ("tool", "init"),
            ("tool", "lint", "--tools-dir"),
            ("--timeout", "bad", "--prog", "tests/prog_ok.py"),
        ]
        for argv in checks:
            with self.subTest(argv=argv):
                proc = self._run(*argv)
                self.assertEqual(proc.returncode, 2)
                self.assertNotIn("usage:", proc.stderr.lower())
                err = self._typed_stderr(proc)
                self.assertEqual(err["type"], "config")


if __name__ == "__main__":
    unittest.main()
