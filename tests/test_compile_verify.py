from __future__ import annotations

import unittest
from pathlib import Path

from tests.compile_manifest import VERIFY_RED_FAILS, load_fixture_cases
from pirml.compiler.extract import extract_blocks
from pirml.compiler.verify import verify_compile_output


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

    def test_verify_corpus_cases(self) -> None:
        cases = load_fixture_cases(Path("tests/fixtures/compile/corpus.jsonl"))
        # We test both 'extract' (which should pass verification if not intentional fail)
        # and 'verify' stages.
        for case in cases:
            if case.stage not in ("extract", "verify"):
                continue
            
            # If it failed extraction, skip here (that's test_compile_extract's job)
            try:
                prog_src, contract_src = extract_blocks(case.raw_model_text)
            except Exception:
                continue

            contract, errors = verify_compile_output(prog_src, contract_src, list(case.tools_topk))
            
            if case.expect == "pass":
                self.assertFalse(errors, f"Case {case.id} expected pass but got errors: {errors}")
                self.assertIsNotNone(contract)
            else:
                # If it's a verify stage fail, it must have errors
                if case.stage == "verify":
                    self.assertTrue(errors, f"Case {case.id} expected fail but got no errors")
                    # We could also check error codes if we mapped expected_fail_id to codes


if __name__ == "__main__":
    unittest.main()
