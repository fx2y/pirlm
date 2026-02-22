from __future__ import annotations

import unittest

from tests.spec09_placeholders import Spec09PlaceholderCase


class Spec09C6HarnessTests(Spec09PlaceholderCase):
    @unittest.expectedFailure
    def test_tool_smoke_pass(self) -> None:
        self._todo("C6.I17 pass lane")

    @unittest.expectedFailure
    def test_tool_smoke_x3_stable(self) -> None:
        self._todo("C6.I17 determinism lane")

    @unittest.expectedFailure
    def test_tool_smoke_fails_on_invalid_manifest(self) -> None:
        self._todo("C6.I17 fail lane")


if __name__ == "__main__":
    unittest.main()
