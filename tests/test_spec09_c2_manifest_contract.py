from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from pirml.compiler.compile import assemble_tools_topk
from pirml.contracts.schemas import ToolManifest
from pirml.runtime.lint import lint_manifest


def _manifest(**overrides: object) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "name": "svc.echo",
        "description": "Echo tool. Keeps payload small. When NOT to use: avoid for heavy transforms.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "input_examples": [{"text": "a"}, {"text": "b"}, {"text": "c"}],
        "idempotent": True,
        "cacheable": True,
        "max_payload_bytes": 4096,
        "timeout_s": 5,
        "retry": {"max_attempts": 1},
        "allowed_callers": ["code_exec"],
        "defer_loading": False,
    }
    manifest.update(overrides)
    return manifest


class Spec09C2ManifestContractTests(unittest.TestCase):
    @staticmethod
    def _run_lint_script(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "scripts.tool_manifest_lint", *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_schema_and_typeddict_sync(self) -> None:
        schema = json.loads(
            Path("pirml/contracts/tool_manifest.schema.json").read_text(encoding="utf-8")
        )
        schema_keys = set(schema["properties"].keys())
        typed_keys = set(ToolManifest.__annotations__.keys())
        self.assertEqual(schema_keys, typed_keys)

    def test_unknown_manifest_key_fails(self) -> None:
        errors = lint_manifest(_manifest(unknown_policy=True))
        self.assertTrue(any(e["code"] == "schema" for e in errors))

    def test_examples_minimum_enforced(self) -> None:
        errors = lint_manifest(_manifest(input_examples=[{"text": "a"}, {"text": "b"}]))
        self.assertTrue(any(e["code"] == "M5" for e in errors))

    def test_allowed_callers_xor(self) -> None:
        self.assertEqual(lint_manifest(_manifest(allowed_callers=["direct"])), [])

    def test_allowed_callers_unknown_value_fails(self) -> None:
        errors = lint_manifest(_manifest(allowed_callers=["agent"]))
        self.assertTrue(any(e["code"] == "M8" for e in errors))

    def test_payload_cap_required(self) -> None:
        manifest = _manifest()
        del manifest["max_payload_bytes"]
        errors = lint_manifest(manifest)
        self.assertTrue(any(e["code"] == "M7" for e in errors))

    def test_compile_rejects_non_code_exec_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tools_dir = Path(tmp) / "tools"
            tools_dir.mkdir(parents=True, exist_ok=True)
            manifest = _manifest(name="svc.echo", allowed_callers=["direct"])
            (tools_dir / "svc.echo.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "denies caller 'code_exec'"):
                assemble_tools_topk(tools_dir=tools_dir, query="echo", k=1)

    def test_tool_manifest_lint_script_typed_stderr_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tools_dir = Path(tmp) / "tools"
            tools_dir.mkdir(parents=True, exist_ok=True)
            bad = _manifest(input_examples=[{"text": "a"}])
            (tools_dir / "svc.echo.json").write_text(json.dumps(bad), encoding="utf-8")
            proc = self._run_lint_script("--tools-dir", str(tools_dir))
            self.assertEqual(proc.returncode, 1)
            err = json.loads(proc.stderr.strip())
            self.assertEqual(err["type"], "validation")
            self.assertIn("manifest lint failed", err["msg"])
            self.assertFalse(bool(err["retryable"]))


if __name__ == "__main__":
    unittest.main()
