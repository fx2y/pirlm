from __future__ import annotations

import importlib
import unittest
from pathlib import Path
from typing import Any

from tests.spec08_support import assert_test_ref_exists, load_jsonl


class Spec08C0DeclaredFailuresTests(unittest.TestCase):
    @staticmethod
    def _matrix_rows() -> list[dict[str, Any]]:
        return [
            row
            for row in load_jsonl("spec-0/08/81-verification-matrix.jsonl")
            if row.get("k") == "inv"
        ]

    def test_verification_matrix_owner_paths_exist(self) -> None:
        for row in self._matrix_rows():
            owner = str(row.get("owner", ""))
            owner_path = owner.split("::", 1)[0]
            if not owner_path:
                continue
            with self.subTest(owner=owner_path):
                self.assertTrue(Path(owner_path).is_file(), owner_path)

    def test_verification_matrix_test_refs_resolve(self) -> None:
        for row in self._matrix_rows():
            for test_ref in row.get("tests", []):
                ref = str(test_ref)
                if "::" not in ref:
                    continue
                module_ref = ref.split("::", 1)[0]
                if not (module_ref.startswith("tests/") or module_ref.startswith("tests.")):
                    continue
                with self.subTest(ref=ref):
                    assert_test_ref_exists(ref)

    def test_contradiction_enforce_test_refs_resolve(self) -> None:
        rows = [
            row for row in load_jsonl("spec-0/08/11-contradictions.jsonl") if row.get("k") == "con"
        ]
        for row in rows:
            for enforce_ref in row.get("enforce", []):
                ref = str(enforce_ref)
                if "::" not in ref:
                    continue
                module_ref = ref.split("::", 1)[0]
                if not (module_ref.startswith("tests/") or module_ref.startswith("tests.")):
                    continue
                with self.subTest(ref=ref):
                    assert_test_ref_exists(ref)

    def test_declared_python_suites_importable(self) -> None:
        suites: set[str] = set()
        for row in self._matrix_rows():
            for test_ref in row.get("tests", []):
                ref = str(test_ref)
                if "::" not in ref:
                    continue
                module_ref = ref.split("::", 1)[0]
                if module_ref.endswith(".ts") or module_ref.startswith("tests/"):
                    continue
                if module_ref.startswith("tests."):
                    suites.add(module_ref)
        for suite in sorted(suites):
            with self.subTest(suite=suite):
                importlib.import_module(suite)


if __name__ == "__main__":
    unittest.main()
