from __future__ import annotations

import unittest


@unittest.skip("Spec08 C2 replay guard declared in C0; implementation lands in C2.")
class Spec08C2ReplayGuardTests(unittest.TestCase):
    def test_replay_mismatch_tag(self) -> None:
        pass

    def test_replay_block_tools(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
