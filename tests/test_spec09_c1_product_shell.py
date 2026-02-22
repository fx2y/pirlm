from __future__ import annotations

import unittest

from tests.spec09_placeholders import Spec09PlaceholderCase


class Spec09C1ProductShellTests(Spec09PlaceholderCase):
    @unittest.expectedFailure
    def test_legacy_flags_unchanged(self) -> None:
        self._todo("C1.I02 pass lane")

    @unittest.expectedFailure
    def test_unknown_subcommand_typed_config_error(self) -> None:
        self._todo("C1.I02 fail lane")

    @unittest.expectedFailure
    def test_project_scripts_entrypoint(self) -> None:
        self._todo("C1.I03 pass lane")

    @unittest.expectedFailure
    def test_project_scripts_entrypoint_missing_fails(self) -> None:
        self._todo("C1.I03 fail lane")

    @unittest.expectedFailure
    def test_doctor_reports_path_fix(self) -> None:
        self._todo("C1.I04 pass lane")

    @unittest.expectedFailure
    def test_doctor_typed_error_envelope(self) -> None:
        self._todo("C1.I04 fail lane")

    @unittest.expectedFailure
    def test_install_global_project_paths(self) -> None:
        self._todo("C1.I05 pass lane")

    @unittest.expectedFailure
    def test_install_paths_match_docs(self) -> None:
        self._todo("C1.X5 path parity")

    @unittest.expectedFailure
    def test_uninstall_idempotent(self) -> None:
        self._todo("C1.I05 idempotency lane")

    @unittest.expectedFailure
    def test_install_rejects_unknown_target(self) -> None:
        self._todo("C1.I05 fail lane")

    @unittest.expectedFailure
    def test_replay_wrapper_delegates(self) -> None:
        self._todo("C1.X8 replay wrapper")

    @unittest.expectedFailure
    def test_runtime_stdout_contract_preserved(self) -> None:
        self._todo("C1.X11 stdout split")


if __name__ == "__main__":
    unittest.main()
