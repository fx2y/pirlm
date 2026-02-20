from __future__ import annotations

import unittest
from pathlib import Path

from tests.compile_manifest import EXTRACT_RED_FAILS, all_red_fail_ids, load_fixture_cases


class TestCompileExtractManifest(unittest.TestCase):
    def test_c0_declares_explicit_extract_fail_ids(self) -> None:
        expected_ids = (
            "FAIL_B0_EXTRA_TEXT_REJECTED",
            "FAIL_B0_MISSING_CONTRACT_BLOCK",
            "FAIL_B0_DUPLICATE_SENTINEL",
            "FAIL_B0_CONTRACT_JSON_INVALID",
            "FAIL_B0_PROG_SIZE_OVER_CAP",
        )
        actual_ids = tuple(row.id for row in EXTRACT_RED_FAILS)
        self.assertEqual(actual_ids, expected_ids)

    def test_c0_fail_ids_are_globally_unique(self) -> None:
        ids = all_red_fail_ids()
        self.assertEqual(len(ids), len(set(ids)))

    def test_c0_fixture_corpus_includes_extract_rows(self) -> None:
        cases = load_fixture_cases(Path("tests/fixtures/compile/corpus.jsonl"))
        extract_cases = tuple(case for case in cases if case.stage == "extract")
        self.assertTrue(extract_cases)
        for case in extract_cases:
            self.assertIn("<<<PROG>>>", case.raw_model_text)
            self.assertIn(case.expect, {"pass", "fail"})
            if case.expect == "fail":
                self.assertTrue(case.expected_fail_id)


if __name__ == "__main__":
    unittest.main()
