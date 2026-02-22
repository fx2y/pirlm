from __future__ import annotations

import unittest

from tests.spec09_placeholders import Spec09PlaceholderCase


class Spec09C5RuntimePolicyTests(Spec09PlaceholderCase):
    @unittest.expectedFailure
    def test_contract_policy_fields_required_shape(self) -> None:
        self._todo("C5.I14 pass lane")

    @unittest.expectedFailure
    def test_verifier_blocks_outside_artifact_root(self) -> None:
        self._todo("C5.I14 fail lane")

    @unittest.expectedFailure
    def test_retry_only_when_idempotent(self) -> None:
        self._todo("C5.I15 pass lane")

    @unittest.expectedFailure
    def test_retry_rejected_when_non_idempotent(self) -> None:
        self._todo("C5.I15 fail lane")

    @unittest.expectedFailure
    def test_payload_cap_enforced(self) -> None:
        self._todo("C5.I15 cap lane")


if __name__ == "__main__":
    unittest.main()
