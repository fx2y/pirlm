from __future__ import annotations

import unittest
from pathlib import Path

from tests.compile_manifest import SMOKE_RED_FAILS, load_fixture_cases


class TestCompileSmokeManifest(unittest.TestCase):
    def test_c0_declares_explicit_smoke_fail_ids(self) -> None:
        expected_ids = (
            "FAIL_B3_STDOUT_CHATTER",
            "FAIL_B3_MULTI_FINAL",
            "FAIL_B3_CALL_BUDGET_OVERFLOW",
            "FAIL_B3_PARALLEL_BUDGET_OVERFLOW",
            "FAIL_B3_BYTES_BUDGET_OVERFLOW",
            "FAIL_B3_TIMEOUT",
            "FAIL_B3_DETERMINISM_DRIFT",
        )
        actual_ids = tuple(row.id for row in SMOKE_RED_FAILS)
        self.assertEqual(actual_ids, expected_ids)

    def test_c0_fixture_corpus_includes_smoke_rows(self) -> None:
        cases = load_fixture_cases(Path("tests/fixtures/compile/corpus.jsonl"))
        smoke_cases = tuple(case for case in cases if case.stage == "smoke")
        self.assertTrue(smoke_cases)
        for case in smoke_cases:
            self.assertIn("<<<PROG>>>", case.raw_model_text)
            self.assertIn("<<<CONTRACT>>>", case.raw_model_text)
            self.assertIn(case.expect, {"pass", "fail"})
            if case.expect == "fail":
                self.assertTrue(case.expected_fail_id)

    def test_c0_fixture_corpus_is_deterministic_x3(self) -> None:
        path = Path("tests/fixtures/compile/corpus.jsonl")
        runs = [load_fixture_cases(path) for _ in range(3)]
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[1], runs[2])


if __name__ == "__main__":
    unittest.main()
