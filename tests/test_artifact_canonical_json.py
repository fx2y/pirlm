from __future__ import annotations

import unittest

from pirml.artifacts import canonical_json_bytes


class ArtifactCanonicalJsonTests(unittest.TestCase):
    def test_bytes_stable_x3(self) -> None:
        obj = {"z": 9, "a": {"k": "v", "n": 1}, "b": [3, 2, 1]}
        runs = [canonical_json_bytes(obj) for _ in range(3)]
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[1], runs[2])

    def test_field_order_does_not_change_bytes(self) -> None:
        left = {"b": 2, "a": 1}
        right = {"a": 1, "b": 2}
        self.assertEqual(canonical_json_bytes(left), canonical_json_bytes(right))


if __name__ == "__main__":
    unittest.main()
