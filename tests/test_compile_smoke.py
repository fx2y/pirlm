from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from pirml.compiler.compile import compile_task
from pirml.compiler.extract import extract_blocks
from pirml.compiler.smoke import run_smoke_subprocess
from pirml.compiler.types import CompileOutput
from pirml.compiler.verify import verify_compile_output
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

    def test_smoke_corpus_cases(self) -> None:
        cases = load_fixture_cases(Path("tests/fixtures/compile/corpus.jsonl"))
        for case in cases:
            if case.stage != "smoke":
                continue

            prog_src, contract_src = extract_blocks(case.raw_model_text)
            # Verify first just in case
            contract, errors = verify_compile_output(prog_src, contract_src, list(case.tools_topk))
            if errors:
                # B2 now rejects print-based chatter before smoke.
                if case.id in {"FX.C3.FAIL.STDOUT_CHATTER", "FX.C3.FAIL.MULTI_FINAL"}:
                    self.assertTrue(
                        any(err.get("code") == "banned_call" for err in errors),
                        f"Case {case.id} expected banned_call verify failure",
                    )
                    continue
                self.fail(f"Case {case.id} failed verification: {errors}")
            self.assertIsNotNone(contract)

            if contract is None:
                continue

            # Now smoke run
            res = run_smoke_subprocess(prog_src, contract)

            if case.expect == "pass":
                self.assertTrue(res.ok, f"Case {case.id} expected pass but failed: {res.error}")
            else:
                self.assertFalse(res.ok, f"Case {case.id} expected fail but passed")
                err = res.error
                self.assertIsNotNone(err)
                if err:
                    # Use get() for TypedDict if not required, but CompileErr (ErrorObject) has required keys.
                    self.assertEqual(
                        err.get("type"),
                        case.expected_fail_id,
                        f"Case {case.id} error type mismatch",
                    )

    def test_compile_task_with_smoke(self) -> None:
        """Verify compile_task integrated smoke stage."""
        # We use FX.C1.PASS.MINIMAL but change stage to smoke for testing
        cases = load_fixture_cases(Path("tests/fixtures/compile/corpus.jsonl"))
        pass_case = next(c for c in cases if c.id == "FX.C1.PASS.MINIMAL")

        with tempfile.TemporaryDirectory() as out_dir:
            out_path = Path(out_dir)
            tools_dir = Path("tools")  # use real tools dir

            # Mock model adapter to return the pass case text
            with patch(
                "pirml.compiler.model.StubModelAdapter.compile_once",
                return_value=pass_case.raw_model_text,
            ):
                res: CompileOutput = compile_task(
                    task=pass_case.task, tools_dir=tools_dir, out_dir=out_path, skip_smoke=False
                )
                self.assertTrue(res.get("ok"), f"compile_task failed: {res.get('error')}")
                self.assertTrue((out_path / "prog.py").exists())
                self.assertTrue((out_path / "contract.json").exists())
                self.assertFalse((out_path / "compile_error.json").exists())

        # Test smoke failure integration
        fail_case = next(c for c in cases if c.id == "FX.C3.FAIL.CALL_BUDGET")
        with tempfile.TemporaryDirectory() as out_dir:
            out_path = Path(out_dir)
            with patch(
                "pirml.compiler.model.StubModelAdapter.compile_once",
                return_value=fail_case.raw_model_text,
            ):
                res_fail: CompileOutput = compile_task(
                    task=fail_case.task, tools_dir=tools_dir, out_dir=out_path, skip_smoke=False
                )
                self.assertFalse(res_fail.get("ok"))
                err_file = res_fail.get("error")
                self.assertIsNotNone(err_file)
                # Use type guard/check for CompileErrorFile
                if err_file and "stage" in err_file:
                    ef = cast(dict[str, Any], err_file)
                    self.assertEqual(ef.get("stage"), "smoke")
                    errors = ef.get("errors", [])
                    self.assertEqual(errors[0].get("code"), "FAIL_B3_CALL_BUDGET_OVERFLOW")
                self.assertTrue((out_path / "compile_error.json").exists())

    def test_smoke_trace_deterministic_x3(self) -> None:
        case = next(
            c
            for c in load_fixture_cases(Path("tests/fixtures/compile/corpus.jsonl"))
            if c.id == "FX.C1.PASS.MINIMAL"
        )
        prog_src, contract_src = extract_blocks(case.raw_model_text)
        contract, errors = verify_compile_output(prog_src, contract_src, list(case.tools_topk))
        self.assertFalse(errors)
        self.assertIsNotNone(contract)
        if contract is None:
            return

        runs = [run_smoke_subprocess(prog_src, contract).stdout for _ in range(3)]
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[1], runs[2])

    def test_smoke_fail_trace_uses_closed_algebra(self) -> None:
        case = next(
            c
            for c in load_fixture_cases(Path("tests/fixtures/compile/corpus.jsonl"))
            if c.id == "FX.C3.FAIL.CALL_BUDGET"
        )
        prog_src, contract_src = extract_blocks(case.raw_model_text)
        contract, errors = verify_compile_output(prog_src, contract_src, list(case.tools_topk))
        self.assertFalse(errors)
        self.assertIsNotNone(contract)
        if contract is None:
            return

        res = run_smoke_subprocess(prog_src, contract)
        self.assertFalse(res.ok)
        lines = [line for line in res.stdout.splitlines() if line.strip()]
        self.assertTrue(lines)
        for line in lines:
            frame = cast(dict[str, Any], json.loads(line))
            self.assertIn(frame.get("op"), {"call", "result", "final"})

    def test_smoke_trace_emitted_on_timeout(self) -> None:
        case = next(
            c
            for c in load_fixture_cases(Path("tests/fixtures/compile/corpus.jsonl"))
            if c.id == "FX.C3.FAIL.TIMEOUT"
        )
        with tempfile.TemporaryDirectory() as out_dir:
            out_path = Path(out_dir)
            with patch(
                "pirml.compiler.model.StubModelAdapter.compile_once",
                return_value=case.raw_model_text,
            ):
                res = compile_task(
                    task=case.task,
                    tools_dir=Path("tests/fixtures/toolsearch/catalog"),
                    out_dir=out_path,
                    skip_smoke=False,
                )
            self.assertFalse(res.get("ok"))
            self.assertTrue((out_path / "smoke_trace.ndjson").exists())

    def test_smoke_failure_does_not_emit_debug_banner(self) -> None:
        case = next(
            c
            for c in load_fixture_cases(Path("tests/fixtures/compile/corpus.jsonl"))
            if c.id == "FX.C3.FAIL.CALL_BUDGET"
        )
        with tempfile.TemporaryDirectory() as out_dir:
            out_path = Path(out_dir)
            stderr_buffer = StringIO()
            with (
                patch(
                    "pirml.compiler.model.StubModelAdapter.compile_once",
                    return_value=case.raw_model_text,
                ),
                redirect_stderr(stderr_buffer),
            ):
                res = compile_task(
                    task=case.task,
                    tools_dir=Path("tests/fixtures/toolsearch/catalog"),
                    out_dir=out_path,
                    skip_smoke=False,
                )
            self.assertFalse(res.get("ok"))
            self.assertNotIn("--- SMOKE FAILED ---", stderr_buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
