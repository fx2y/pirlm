from __future__ import annotations

import unittest


@unittest.skip("Spec08 C3 contract-registry declared in C0; implementation lands in C3.")
class Spec08C3ContractRegistryTests(unittest.TestCase):
    def test_trace_schema_registered(self) -> None:
        pass

    def test_web_trace_schema_registered(self) -> None:
        pass

    def test_lint_op_enum_matches_schema(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
