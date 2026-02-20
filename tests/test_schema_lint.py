from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestSchemaLintCLI(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "scripts.schema_lint", *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_requires_explicit_artifacts(self) -> None:
        completed = self._run()
        self.assertEqual(completed.returncode, 1)
        self.assertIn("at least one artifact path", completed.stderr)

    def test_missing_final_is_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing-final.json"
            completed = self._run("--final", str(missing))
            self.assertEqual(completed.returncode, 1)
            self.assertIn("Required final artifact missing", completed.stderr)

    def test_ignores_unscoped_out_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            final_path = root / "final.json"
            final_path.write_text(json.dumps({"ok": True, "results": []}), encoding="utf-8")

            junk = root / "out" / "junk" / "contract.json"
            junk.parent.mkdir(parents=True, exist_ok=True)
            junk.write_text("{not json", encoding="utf-8")

            completed = self._run("--final", str(final_path))
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_missing_required_contract_is_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing-contract.json"
            completed = self._run("--contract", str(missing))
            self.assertEqual(completed.returncode, 1)
            self.assertIn("Required contract artifact missing", completed.stderr)


if __name__ == "__main__":
    unittest.main()
