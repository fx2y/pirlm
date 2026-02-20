from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from pirml.compiler.extract import extract_blocks
from pirml.compiler.repair import repair_once
from pirml.compiler.verify import verify_compile_output
from tests.compile_manifest import VERIFY_RED_FAILS, load_fixture_cases


class TestCompileVerifyManifest(unittest.TestCase):
    def _base_contract(self, tool_deps: list[str]) -> str:
        return json.dumps(
            {
                "tool_deps": tool_deps,
                "io_schema": {
                    "trace_ptr": "trace.ndjson",
                    "final_schema": {},
                    "citations_schema": {},
                },
                "budgets": {
                    "max_calls": 5,
                    "max_parallel": 2,
                    "max_bytes_in": 1000,
                    "max_bytes_out": 1000,
                    "timeout_s": 5,
                },
                "assertions": [],
            }
        )

    def _prog_with_main(self, body: str) -> str:
        return (
            "import asyncio\n"
            "from pirml.runtime.rpc import send_final\n"
            "async def main():\n"
            f"{body}\n"
            "if __name__ == '__main__':\n"
            "    asyncio.run(main())\n"
        )

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

    def test_contract_unknown_key_rejected(self) -> None:
        prog = self._prog_with_main("    send_final(True, {})")
        contract_obj = json.loads(self._base_contract(["pirml.echo"]))
        contract_obj["unknown"] = 1
        _, errors = verify_compile_output(prog, json.dumps(contract_obj), ["pirml.echo"])
        self.assertTrue(any(e.get("code") == "contract_extra_keys" for e in errors))

    def test_contract_type_errors_do_not_raise(self) -> None:
        prog = self._prog_with_main("    send_final(True, {})")
        contract_obj = json.loads(self._base_contract(["pirml.echo"]))
        contract_obj["budgets"] = []
        _, errors = verify_compile_output(prog, json.dumps(contract_obj), ["pirml.echo"])
        self.assertTrue(any(e.get("code") == "invalid_budget_shape" for e in errors))

    def test_contract_schema_file_is_enforced(self) -> None:
        prog = self._prog_with_main("    send_final(True, {})")
        contract_src = self._base_contract(["pirml.echo"])
        with patch(
            "pirml.compiler.verify.load_contract_schema", side_effect=ValueError("bad schema")
        ):
            _, errors = verify_compile_output(prog, contract_src, ["pirml.echo"])
        self.assertTrue(any(e.get("code") == "contract_schema_invalid" for e in errors))

    def test_unawaited_tool_call_rejected(self) -> None:
        prog = self._prog_with_main(
            "    _x = TOOL_pirml_echo({'text': 'hi'})\n    send_final(True, {})"
        )
        contract_src = self._base_contract(["pirml.echo"])
        _, errors = verify_compile_output(prog, contract_src, ["pirml.echo"])
        self.assertTrue(any(e.get("code") == "unawaited_tool_call" for e in errors))

    def test_stdout_chatter_rejected_at_verify(self) -> None:
        prog = self._prog_with_main("    print('debug')\n    send_final(True, {})")
        contract_src = self._base_contract([])
        _, errors = verify_compile_output(prog, contract_src, [])
        self.assertTrue(any(e.get("code") == "banned_call" for e in errors))

    def test_fake_gather_attr_rejected(self) -> None:
        prog = (
            "import asyncio\n"
            "from pirml.runtime.rpc import send_final\n"
            "class Fake:\n"
            "    async def gather(self):\n"
            "        return None\n"
            "async def main():\n"
            "    await TOOL_pirml_echo({'text': 'a'})\n"
            "    await TOOL_pirml_readfile({'path': 'p'})\n"
            "    await Fake().gather()\n"
            "    send_final(True, {})\n"
            "if __name__ == '__main__':\n"
            "    asyncio.run(main())\n"
        )
        contract_src = self._base_contract(["pirml.echo", "pirml.readfile"])
        _, errors = verify_compile_output(prog, contract_src, ["pirml.echo", "pirml.readfile"])
        self.assertTrue(any(e.get("code") == "missing_gather" for e in errors))

    def test_dependency_chain_serial_ok(self) -> None:
        prog = self._prog_with_main(
            "    result = await TOOL_pirml_echo({'text': 'alpha'})\n"
            "    await TOOL_pirml_readfile({'path': result})\n"
            "    send_final(True, {})"
        )
        contract_src = self._base_contract(["pirml.echo", "pirml.readfile"])
        _, errors = verify_compile_output(prog, contract_src, ["pirml.echo", "pirml.readfile"])
        self.assertFalse(any(e.get("code") == "missing_gather" for e in errors), errors)

    def test_repair_does_not_synthesize_semantics(self) -> None:
        prog = self._prog_with_main("    send_final(True, {})")
        # Only alias migration is allowed; no synthetic budgets/assertions/tool_deps.
        contract_src = '{"final_schema":{"type":"object"}}'
        fixed_prog, fixed_contract, repaired = repair_once(
            prog,
            contract_src,
            [{"code": "contract_missing_keys", "msg": "missing", "line": None, "symbol": None}],
        )
        self.assertEqual(fixed_prog, prog)
        self.assertTrue(repaired)
        parsed = json.loads(fixed_contract)
        self.assertIn("io_schema", parsed)
        self.assertNotIn("budgets", parsed)
        self.assertNotIn("assertions", parsed)
        self.assertNotIn("tool_deps", parsed)


if __name__ == "__main__":
    unittest.main()
