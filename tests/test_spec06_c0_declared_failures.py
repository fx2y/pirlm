from __future__ import annotations

import importlib
import unittest


class Spec06C0DeclaredFailures(unittest.TestCase):
    @unittest.expectedFailure
    def test_c1_cas_immutability_suite_declared(self) -> None:
        importlib.import_module("pirml.artifacts.store")

    @unittest.expectedFailure
    def test_c2_view_id_determinism_suite_declared(self) -> None:
        importlib.import_module("pirml.artifacts.view_dsl")

    @unittest.expectedFailure
    def test_c3_metadata_only_history_suite_declared(self) -> None:
        importlib.import_module("pirml.rlm.history")

    @unittest.expectedFailure
    def test_c5_ctx_cap_suite_declared(self) -> None:
        importlib.import_module("pirml.rlm.governor")


if __name__ == "__main__":
    unittest.main()
