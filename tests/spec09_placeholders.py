from __future__ import annotations

import unittest


class Spec09PlaceholderCase(unittest.TestCase):
    def _todo(self, case: str) -> None:
        self.fail(f"spec09 placeholder not implemented: {case}")
