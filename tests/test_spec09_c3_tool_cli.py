from __future__ import annotations

import unittest

from tests.spec09_placeholders import Spec09PlaceholderCase


class Spec09C3ToolCliTests(Spec09PlaceholderCase):
    @unittest.expectedFailure
    def test_init_deterministic(self) -> None:
        self._todo("C3.I08 pass lane")

    @unittest.expectedFailure
    def test_init_catalog_loadable(self) -> None:
        self._todo("C3.I08 loader lane")

    @unittest.expectedFailure
    def test_init_scaffold_loadable_by_catalog_loader(self) -> None:
        self._todo("C3.X4 enforce lane")

    @unittest.expectedFailure
    def test_init_rejects_invalid_name(self) -> None:
        self._todo("C3.I08 fail lane")

    @unittest.expectedFailure
    def test_tool_lint_pass_fail_codes(self) -> None:
        self._todo("C3.I09 pass/fail lane")

    @unittest.expectedFailure
    def test_pack_deterministic(self) -> None:
        self._todo("C3.I10 pass lane")

    @unittest.expectedFailure
    def test_pack_includes_catalog_hash(self) -> None:
        self._todo("C3.I10 hash lane")

    @unittest.expectedFailure
    def test_pack_fails_without_catalog(self) -> None:
        self._todo("C3.I10 fail lane")


if __name__ == "__main__":
    unittest.main()
