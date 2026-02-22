from __future__ import annotations

import importlib
import unittest


class Spec07C0DeclaredFailures(unittest.TestCase):
    @unittest.expectedFailure
    def test_c1_runtime_shim_suite_declared(self) -> None:
        """C0.T09: C1 shim suite is declared before implementation."""
        importlib.import_module("tests.test_spec07_c1_runtime_shim")

    @unittest.expectedFailure
    def test_c2_extension_contract_suite_declared(self) -> None:
        """C0.T09: C2 extension contract suite is declared before implementation."""
        importlib.import_module("tests.test_spec07_c2_extension_contract")

    @unittest.expectedFailure
    def test_c3_toolpack_suite_declared(self) -> None:
        """C0.T09: C3 toolpack suite is declared before implementation."""
        importlib.import_module("tests.test_spec07_c3_toolpack")


if __name__ == "__main__":
    unittest.main()
