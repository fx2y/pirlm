from __future__ import annotations

import unittest
from unittest.mock import patch

from pirml.clock import SequenceClock


class RlmHistoryTests(unittest.TestCase):
    def test_clock_monotonic_without_wall_time(self) -> None:
        clock = SequenceClock(start=1700000000)
        with patch("time.time", side_effect=AssertionError("wall clock should not be used")):
            ticks = [clock.now(), clock.now(), clock.now()]
        self.assertEqual(ticks, [1700000000, 1700000001, 1700000002])


if __name__ == "__main__":
    unittest.main()
