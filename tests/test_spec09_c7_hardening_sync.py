from __future__ import annotations

import unittest

from tests.spec09_placeholders import Spec09PlaceholderCase


class Spec09C7HardeningSyncTests(Spec09PlaceholderCase):
    @unittest.expectedFailure
    def test_snippet_contracts_match_cli_help(self) -> None:
        self._todo("C7.I20 pass lane")

    @unittest.expectedFailure
    def test_doc_commands_smoke(self) -> None:
        self._todo("C7.I20 smoke lane")

    @unittest.expectedFailure
    def test_docs_match_supported_lanes(self) -> None:
        self._todo("C7.X12 enforce lane")

    @unittest.expectedFailure
    def test_doc_snippet_unknown_flag_fails(self) -> None:
        self._todo("C7.I20 fail lane")


if __name__ == "__main__":
    unittest.main()
