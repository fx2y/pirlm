from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pirml.toolsearch.loader import catalog_hash, load_catalog


class Spec09C3ToolCliTests(unittest.TestCase):
    @staticmethod
    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "pirml", *args],
            check=False,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def _copy_catalog(src: Path, dst: Path) -> None:
        dst.mkdir(parents=True, exist_ok=True)
        for path in sorted(src.glob("*.json")):
            shutil.copy2(path, dst / path.name)

    @staticmethod
    def _assert_typed_config_stderr(proc: subprocess.CompletedProcess[str]) -> None:
        stderr = proc.stderr.strip()
        assert stderr, proc
        assert "usage:" not in stderr.lower(), stderr
        err = json.loads(stderr)
        assert err["type"] == "config", err

    def test_init_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "a"
            b = root / "b"
            proc_a = self._run("tool", "init", "demo.echo", "--tools-dir", str(a))
            proc_b = self._run("tool", "init", "demo.echo", "--tools-dir", str(b))
            self.assertEqual(proc_a.returncode, 0, proc_a.stderr)
            self.assertEqual(proc_b.returncode, 0, proc_b.stderr)

            self.assertEqual(
                (a / "demo.echo.json").read_bytes(),
                (b / "demo.echo.json").read_bytes(),
            )
            self.assertEqual(
                (a / "demo.echo.README.md").read_bytes(),
                (b / "demo.echo.README.md").read_bytes(),
            )
            self.assertEqual(
                (a / "demo.echo.examples.jsonl").read_bytes(),
                (b / "demo.echo.examples.jsonl").read_bytes(),
            )

    def test_init_catalog_loadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tools_dir = Path(tmp) / "tools"
            proc = self._run("tool", "init", "demo.echo", "--tools-dir", str(tools_dir))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            catalog = load_catalog(tools_dir, strict=True)
            self.assertIn("demo.echo", catalog)

    def test_init_scaffold_loadable_by_catalog_loader(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tools_dir = Path(tmp) / "tools"
            proc = self._run("tool", "init", "svc.list_items", "--tools-dir", str(tools_dir))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            catalog = load_catalog(tools_dir, strict=True)
            tool = catalog["svc.list_items"]
            self.assertEqual(tool.get("name"), "svc.list_items")
            self.assertIn("input_schema", tool)

    def test_init_rejects_invalid_name(self) -> None:
        proc = self._run("tool", "init", "BadName", "--tools-dir", "tools")
        self.assertEqual(proc.returncode, 1)
        err = json.loads(proc.stderr.strip())
        self.assertEqual(err["type"], "validation")
        self.assertIn("dotted namespace", err["msg"])

    def test_tool_lint_pass_fail_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools_dir = root / "tools"
            self._copy_catalog(Path("tools"), tools_dir)
            pass_proc = self._run("tool", "lint", "--tools-dir", str(tools_dir))
            self.assertEqual(pass_proc.returncode, 0, pass_proc.stderr)
            pass_json = json.loads(pass_proc.stdout.strip())
            self.assertTrue(bool(pass_json["ok"]))

            bad_manifest = json.loads((tools_dir / "pirml.echo.json").read_text(encoding="utf-8"))
            bad_manifest["input_examples"] = [{"text": "only-one"}]
            (tools_dir / "pirml.echo.json").write_text(
                json.dumps(bad_manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            fail_proc = self._run("tool", "lint", "--tools-dir", str(tools_dir))
            self.assertEqual(fail_proc.returncode, 1)
            err = json.loads(fail_proc.stderr.strip())
            self.assertEqual(err["type"], "validation")
            self.assertIn("data", err)
            self.assertIn("errors", err["data"])
            self.assertGreaterEqual(len(err["data"]["errors"]), 1)

    def test_tool_lint_bootstrap_single_init_catalog_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tools_dir = Path(tmp) / "tools"
            init_proc = self._run("tool", "init", "demo.echo", "--tools-dir", str(tools_dir))
            self.assertEqual(init_proc.returncode, 0, init_proc.stderr)
            lint_proc = self._run("tool", "lint", "--tools-dir", str(tools_dir))
            self.assertEqual(lint_proc.returncode, 0, lint_proc.stderr)
            payload = json.loads(lint_proc.stdout.strip())
            self.assertTrue(bool(payload["ok"]))
            self.assertEqual(int(payload["count"]), 1)

    def test_pack_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools_dir = root / "tools"
            self._copy_catalog(Path("tools"), tools_dir)
            out_a = root / "a.json"
            out_b = root / "b.json"
            proc_a = self._run("tool", "pack", "--tools-dir", str(tools_dir), "--out", str(out_a))
            proc_b = self._run("tool", "pack", "--tools-dir", str(tools_dir), "--out", str(out_b))
            self.assertEqual(proc_a.returncode, 0, proc_a.stderr)
            self.assertEqual(proc_b.returncode, 0, proc_b.stderr)
            self.assertEqual(out_a.read_bytes(), out_b.read_bytes())

    def test_pack_includes_catalog_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools_dir = root / "tools"
            self._copy_catalog(Path("tools"), tools_dir)
            out_path = root / "pack.json"
            proc = self._run("tool", "pack", "--tools-dir", str(tools_dir), "--out", str(out_path))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            packed = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIn("catalog_hash", packed)
            self.assertEqual(
                packed["catalog_hash"], catalog_hash(load_catalog(tools_dir, strict=True))
            )

    def test_pack_fails_without_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"
            out_path = Path(tmp) / "pack.json"
            proc = self._run("tool", "pack", "--tools-dir", str(missing), "--out", str(out_path))
            self.assertEqual(proc.returncode, 2)
            err = json.loads(proc.stderr.strip())
            self.assertEqual(err["type"], "config")

    def test_init_hot_sets_defer_loading_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tools_dir = Path(tmp) / "tools"
            proc = self._run("tool", "init", "demo.hot", "--tools-dir", str(tools_dir), "--hot")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            manifest = json.loads((tools_dir / "demo.hot.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest.get("defer_loading"))

    def test_pack_with_bootstrap_passes_on_underfilled_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tools_dir = Path(tmp) / "tools"
            init_proc = self._run("tool", "init", "demo.echo", "--tools-dir", str(tools_dir))
            self.assertEqual(init_proc.returncode, 0, init_proc.stderr)
            # Should pass with --bootstrap
            proc = self._run(
                "tool",
                "pack",
                "--tools-dir",
                str(tools_dir),
                "--out",
                str(Path(tmp) / "pack.json"),
                "--bootstrap",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((Path(tmp) / "pack.json").exists())

    def test_pack_fails_on_underfilled_hot_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tools_dir = Path(tmp) / "tools"
            init_proc = self._run("tool", "init", "demo.echo", "--tools-dir", str(tools_dir))
            self.assertEqual(init_proc.returncode, 0, init_proc.stderr)
            proc = self._run(
                "tool", "pack", "--tools-dir", str(tools_dir), "--out", str(Path(tmp) / "pack.json")
            )
            self.assertEqual(proc.returncode, 1)
            err = json.loads(proc.stderr.strip())
            self.assertEqual(err["type"], "validation")
            self.assertIn("cannot pack invalid catalog", err["msg"])
            self.assertIn("data", err)
            self.assertIn("errors", err["data"])

    def test_init_parse_missing_required_name_typed_no_usage(self) -> None:
        proc = self._run("tool", "init")
        self.assertEqual(proc.returncode, 2)
        self._assert_typed_config_stderr(proc)

    def test_lint_parse_missing_value_typed_no_usage(self) -> None:
        proc = self._run("tool", "lint", "--tools-dir")
        self.assertEqual(proc.returncode, 2)
        self._assert_typed_config_stderr(proc)

    def test_pack_parse_missing_value_typed_no_usage(self) -> None:
        proc = self._run("tool", "pack", "--out")
        self.assertEqual(proc.returncode, 2)
        self._assert_typed_config_stderr(proc)


if __name__ == "__main__":
    unittest.main()
