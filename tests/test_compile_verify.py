from __future__ import annotations

import unittest
from pathlib import Path

from tests.compile_manifest import VERIFY_RED_FAILS, load_fixture_cases


class TestCompileVerifyManifest(unittest.TestCase):
    def test_c0_declares_explicit_verify_fail_ids(self) -> None:
        expected_ids = (
            "FAIL_B1_TOOL_DEP_HALLUCINATION",
            "FAIL_B1_BUDGET_MISSING_OR_NEGATIVE",
            "FAIL_B1_IOSCHEMA_MISSING",
            "FAIL_B2_IMPORT_DENIED",
            "FAIL_B2_BANNED_CALL_DETECTED",
            "FAIL_B2_NONAWAIT_OR_UNKNOWN_WRAPPER",
            "FAIL_B2_HIDDEN_SERIAL_REJECTED",
            "FAIL_B2_EXTRA_PRINT_REJECTED",
        )
        actual_ids = tuple(row.id for row in VERIFY_RED_FAILS)
        self.assertEqual(actual_ids, expected_ids)

    def test_c0_fixture_corpus_includes_verify_rows(self) -> None:
        cases = load_fixture_cases(Path("tests/fixtures/compile/corpus.jsonl"))
        verify_cases = tuple(case for case in cases if case.stage == "verify")
        self.assertTrue(verify_cases)
        for case in verify_cases:
            self.assertIn("<<<PROG>>>", case.raw_model_text)
            self.assertIn("<<<CONTRACT>>>", case.raw_model_text)
            self.assertIn(case.expect, {"pass", "fail"})
            if case.expect == "fail":
                self.assertTrue(case.expected_fail_id)


if __name__ == "__main__":
    unittest.main()
