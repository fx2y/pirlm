from __future__ import annotations

import unittest

from tests.spec09_placeholders import Spec09PlaceholderCase


class Spec09C6ChaosTests(Spec09PlaceholderCase):
    @unittest.expectedFailure
    def test_timeout_lane(self) -> None:
        self._todo("C6.I18 timeout lane")

    @unittest.expectedFailure
    def test_invalid_json_lane(self) -> None:
        self._todo("C6.I18 invalid-json lane")

    @unittest.expectedFailure
    def test_resume_after_forced_interrupt(self) -> None:
        self._todo("C6.I18 resume lane")

    @unittest.expectedFailure
    def test_replay_mismatch_lane(self) -> None:
        self._todo("C6.I18 replay-mismatch lane")


if __name__ == "__main__":
    unittest.main()
