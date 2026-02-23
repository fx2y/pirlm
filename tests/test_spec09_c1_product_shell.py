from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from typing import cast

from tests.common import parse_stdout_frames


class Spec09C1ProductShellTests(unittest.TestCase):
    @staticmethod
    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "pirml", *args],
            check=False,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def _assert_pirml_entrypoint(scripts: dict[str, object]) -> None:
        assert scripts.get("pirml") == "pirml.cli:main", scripts

    @staticmethod
    def _load_doctor_rows(stdout: str) -> list[dict[str, object]]:
        rows = [line for line in stdout.splitlines() if line.strip()]
        return [json.loads(line) for line in rows]

    @staticmethod
    def _assert_typed_config_stderr(proc: subprocess.CompletedProcess[str]) -> None:
        stderr = proc.stderr.strip()
        assert stderr, proc
        assert "usage:" not in stderr.lower(), stderr
        err = json.loads(stderr)
        assert err["type"] == "config", err

    def test_legacy_flags_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            proc = self._run("--prog", "tests/prog_ok.py", "--out-dir", str(out_dir))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            frames = parse_stdout_frames(proc.stdout)
            self.assertTrue(frames)
            self.assertEqual(frames[-1]["op"], "final")
            self.assertTrue((out_dir / "trace.ndjson").is_file())
            self.assertTrue((out_dir / "final.json").is_file())

    def test_unknown_subcommand_typed_config_error(self) -> None:
        proc = self._run("unknown-subcommand")
        self.assertEqual(proc.returncode, 2)
        err = json.loads(proc.stderr.strip())
        self.assertEqual(err["type"], "config")
        self.assertIn("unknown command", err["msg"])
        self.assertFalse(bool(err["retryable"]))

    def test_project_scripts_entrypoint(self) -> None:
        data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
        scripts = data["project"]["scripts"]
        self._assert_pirml_entrypoint(dict(scripts))

    def test_project_scripts_entrypoint_missing_fails(self) -> None:
        with self.assertRaises(AssertionError):
            self._assert_pirml_entrypoint({})

    def test_doctor_reports_path_fix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            root = Path(tmp) / "project"
            home.mkdir(parents=True, exist_ok=True)
            root.mkdir(parents=True, exist_ok=True)
            proc = self._run("doctor", "--project-root", str(root), "--home", str(home))
            self.assertEqual(proc.returncode, 1)
            rows = self._load_doctor_rows(proc.stdout)
            path_row = next(row for row in rows if row["check"] == "path_local_bin")
            self.assertFalse(bool(path_row["ok"]))
            self.assertIn("export PATH=", str(path_row["fix"]))

    def test_doctor_typed_error_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            root = Path(tmp) / "project"
            home.mkdir(parents=True, exist_ok=True)
            root.mkdir(parents=True, exist_ok=True)
            proc = self._run("doctor", "--project-root", str(root), "--home", str(home))
            self.assertEqual(proc.returncode, 1)
            rows = self._load_doctor_rows(proc.stdout)
            fail_rows = [row for row in rows if not bool(row.get("ok"))]
            self.assertTrue(fail_rows)
            for row in fail_rows:
                err = row.get("error")
                self.assertIsInstance(err, dict)
                if not isinstance(err, dict):
                    self.fail("doctor fail row missing typed error object")
                err_map = cast(dict[str, object], err)
                self.assertIn("type", err_map)
                self.assertIn("msg", err_map)
                self.assertIn("retryable", err_map)

    def test_install_global_project_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            root = Path(tmp) / "project"
            home.mkdir(parents=True, exist_ok=True)
            root.mkdir(parents=True, exist_ok=True)
            global_proc = self._run(
                "install-pi-ext",
                "--target",
                "global",
                "--home",
                str(home),
                "--project-root",
                str(root),
            )
            self.assertEqual(global_proc.returncode, 0, global_proc.stderr)
            project_proc = self._run(
                "install-pi-ext",
                "--target",
                "project",
                "--home",
                str(home),
                "--project-root",
                str(root),
            )
            self.assertEqual(project_proc.returncode, 0, project_proc.stderr)
            self.assertTrue((home / ".pi/agent/extensions/pirml/index.ts").is_file())
            self.assertTrue((root / ".pi/extensions/pirml/index.ts").is_file())

    def test_install_paths_match_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            root = Path(tmp) / "project"
            home.mkdir(parents=True, exist_ok=True)
            root.mkdir(parents=True, exist_ok=True)
            proc = self._run(
                "install-pi-ext",
                "--target",
                "global",
                "--home",
                str(home),
                "--project-root",
                str(root),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout.strip())
            self.assertEqual(
                Path(str(out["path"])),
                (home / ".pi/agent/extensions/pirml").resolve(),
            )

    def test_uninstall_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            root = Path(tmp) / "project"
            home.mkdir(parents=True, exist_ok=True)
            root.mkdir(parents=True, exist_ok=True)
            install = self._run(
                "install-pi-ext",
                "--target",
                "project",
                "--home",
                str(home),
                "--project-root",
                str(root),
            )
            self.assertEqual(install.returncode, 0, install.stderr)
            first = self._run(
                "uninstall-pi-ext",
                "--target",
                "project",
                "--home",
                str(home),
                "--project-root",
                str(root),
            )
            second = self._run(
                "uninstall-pi-ext",
                "--target",
                "project",
                "--home",
                str(home),
                "--project-root",
                str(root),
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertFalse((root / ".pi/extensions/pirml").exists())

    def test_install_rejects_unknown_target(self) -> None:
        proc = self._run("install-pi-ext", "--target", "bogus")
        self.assertEqual(proc.returncode, 2)
        err = json.loads(proc.stderr.strip())
        self.assertEqual(err["type"], "config")

    def test_replay_wrapper_delegates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live = root / "live"
            replay = root / "replay"
            live_proc = self._run("--prog", "tests/prog_ok.py", "--out-dir", str(live))
            self.assertEqual(live_proc.returncode, 0, live_proc.stderr)
            replay_proc = self._run(
                "replay",
                "tests/prog_ok.py",
                str(live / "trace.ndjson"),
                "--out-dir",
                str(replay),
            )
            self.assertEqual(replay_proc.returncode, 0, replay_proc.stderr)
            self.assertEqual(
                (live / "final.json").read_bytes(), (replay / "final.json").read_bytes()
            )

    def test_replay_parse_invalid_float_typed_no_usage(self) -> None:
        proc = self._run("replay", "tests/prog_ok.py", "out/ci/trace.ndjson", "--timeout", "nope")
        self.assertEqual(proc.returncode, 2)
        self._assert_typed_config_stderr(proc)

    def test_doctor_parse_missing_value_typed_no_usage(self) -> None:
        proc = self._run("doctor", "--home")
        self.assertEqual(proc.returncode, 2)
        self._assert_typed_config_stderr(proc)

    def test_install_parse_missing_value_typed_no_usage(self) -> None:
        proc = self._run("install-pi-ext", "--target")
        self.assertEqual(proc.returncode, 2)
        self._assert_typed_config_stderr(proc)

    def test_uninstall_parse_missing_value_typed_no_usage(self) -> None:
        proc = self._run("uninstall-pi-ext", "--target")
        self.assertEqual(proc.returncode, 2)
        self._assert_typed_config_stderr(proc)

    def test_legacy_parse_invalid_scalar_typed_no_usage(self) -> None:
        proc = self._run("--timeout", "nope", "--prog", "tests/prog_ok.py")
        self.assertEqual(proc.returncode, 2)
        self._assert_typed_config_stderr(proc)

    def test_legacy_parse_missing_value_typed_no_usage(self) -> None:
        proc = self._run("--prog")
        self.assertEqual(proc.returncode, 2)
        self._assert_typed_config_stderr(proc)

    def test_runtime_stdout_contract_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            proc = self._run("--prog", "tests/prog_ok.py", "--out-dir", str(out_dir))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            frames = parse_stdout_frames(proc.stdout)
            self.assertTrue(frames)
            for frame in frames:
                self.assertIn(frame["op"], {"call", "result", "final", "custom"})
            self.assertFalse(proc.stderr.strip())


if __name__ == "__main__":
    unittest.main()
