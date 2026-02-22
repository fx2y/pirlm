from __future__ import annotations

import importlib
import unittest


class Spec07C0DeclaredFailures(unittest.TestCase):
    def test_all_suites_exist(self) -> None:
        """C0.T09: Ensure all spec-07 suites are importable and implemented."""
        suites = [
            "tests.test_spec07_c0_reconcile",
            "tests.test_spec07_c1_runtime_shim",
            "tests.test_spec07_c2_extension_contract",
            "tests.test_spec07_c3_toolpack",
            "tests.test_spec07_c4_hybrid_tool",
            "tests.test_spec07_c5_headless",
            "tests.test_spec07_snippets",
            "tests.test_spec07_c7_schema_pointer_parity",
            "tests.test_spec07_c7_gate_contract",
        ]
        for suite in suites:
            with self.subTest(suite=suite):
                importlib.import_module(suite)


if __name__ == "__main__":
    unittest.main()
