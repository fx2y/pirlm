from __future__ import annotations

import unittest

from tests.spec09_placeholders import Spec09PlaceholderCase


class Spec09C2ManifestContractTests(Spec09PlaceholderCase):
    @unittest.expectedFailure
    def test_schema_and_typeddict_sync(self) -> None:
        self._todo("C2.I06 pass lane")

    @unittest.expectedFailure
    def test_unknown_manifest_key_fails(self) -> None:
        self._todo("C2.I06 fail lane")

    @unittest.expectedFailure
    def test_examples_minimum_enforced(self) -> None:
        self._todo("C2.I07 examples rule")

    @unittest.expectedFailure
    def test_allowed_callers_xor(self) -> None:
        self._todo("C2.I07 XOR pass lane")

    @unittest.expectedFailure
    def test_allowed_callers_unknown_value_fails(self) -> None:
        self._todo("C2.I07 fail lane")

    @unittest.expectedFailure
    def test_payload_cap_required(self) -> None:
        self._todo("C2.I07 payload cap lane")


if __name__ == "__main__":
    unittest.main()
