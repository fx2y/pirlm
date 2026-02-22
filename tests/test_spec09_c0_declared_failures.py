from __future__ import annotations

import importlib
import unittest
from typing import Any

from tests.spec09_support import assert_test_ref_exists, load_jsonl, repo_path

_FAIL_TOKENS = (
    "fail",
    "fails",
    "unknown",
    "reject",
    "block",
    "timeout",
    "invalid",
    "mismatch",
    "unsupported",
    "error",
    "deny",
)


class Spec09C0DeclaredFailuresTests(unittest.TestCase):
    @staticmethod
    def _matrix_rows() -> list[dict[str, Any]]:
        return [
            row
            for row in load_jsonl("spec-0/09/81-verification-matrix.jsonl")
            if row.get("k") == "inv"
        ]

    def test_verification_matrix_owner_paths_exist(self) -> None:
        for row in self._matrix_rows():
            owner = str(row.get("owner", ""))
            owner_path = owner.split("::", 1)[0]
            if not owner_path or owner_path.startswith("spec-0/"):
                continue
            with self.subTest(owner=owner_path):
                self.assertTrue(repo_path(owner_path).is_file(), owner_path)

    def test_verification_matrix_test_refs_resolve(self) -> None:
        for row in self._matrix_rows():
            for test_ref in row.get("tests", []):
                ref = str(test_ref)
                if "::" not in ref:
                    continue
                module_ref = ref.split("::", 1)[0]
                if not (
                    module_ref.startswith("tests/")
                    or module_ref.startswith("tests.")
                    or module_ref.endswith(".ts")
                ):
                    continue
                with self.subTest(ref=ref):
                    assert_test_ref_exists(ref)

    def test_contradiction_enforce_test_refs_resolve(self) -> None:
        rows = [
            row for row in load_jsonl("spec-0/09/11-contradictions.jsonl") if row.get("k") == "con"
        ]
        for row in rows:
            for enforce_ref in row.get("enforce", []):
                ref = str(enforce_ref)
                if "::" not in ref:
                    continue
                module_ref = ref.split("::", 1)[0]
                if not (
                    module_ref.startswith("tests/")
                    or module_ref.startswith("tests.")
                    or module_ref.endswith(".ts")
                ):
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

    def test_each_invariant_declares_pass_and_fail_lane(self) -> None:
        for row in self._matrix_rows():
            tests = [
                str(ref)
                for ref in row.get("tests", [])
                if str(ref).startswith("tests/") or str(ref).startswith("tests.")
            ]
            if not tests:
                continue
            names = [ref.split("::", 1)[1] if "::" in ref else ref for ref in tests]
            has_fail_lane = any(
                any(token in name.lower() for token in _FAIL_TOKENS) for name in names
            )
            has_pass_lane = any("pass" in name.lower() for name in names) or any(
                not any(token in name.lower() for token in _FAIL_TOKENS) for name in names
            )
            with self.subTest(inv=row.get("id")):
                self.assertTrue(has_fail_lane, f"missing fail lane in {row.get('id')}: {names}")
                self.assertTrue(has_pass_lane, f"missing pass lane in {row.get('id')}: {names}")


if __name__ == "__main__":
    unittest.main()
