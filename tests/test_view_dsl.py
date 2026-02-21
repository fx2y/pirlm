from __future__ import annotations

import unittest

from pirml.artifacts.view_dsl import parse_spec, view_id_for


class TestViewDSL(unittest.TestCase):
    def test_view_id_stable_x3(self) -> None:
        """I05: view_id deterministic over canonical spec"""
        aid = "artifact123"
        spec = {"op": "lines", "a": 0, "b": 100}

        vid1 = view_id_for(aid, spec)  # type: ignore
        vid2 = view_id_for(aid, spec)  # type: ignore
        vid3 = view_id_for(aid, spec)  # type: ignore

        self.assertEqual(vid1, vid2)
        self.assertEqual(vid2, vid3)

    def test_field_order_does_not_change_view_id(self) -> None:
        """I05: field order does not change view_id"""
        aid = "artifact123"
        spec1 = {"op": "lines", "a": 0, "b": 100}
        spec2 = {"b": 100, "op": "lines", "a": 0}

        vid1 = view_id_for(aid, spec1)  # type: ignore
        vid2 = view_id_for(aid, spec2)  # type: ignore

        self.assertEqual(vid1, vid2)

    def test_unknown_op_typed_fail(self) -> None:
        """I06: Unknown/invalid slice op typed-fails"""
        spec = {"op": "invalid_op", "a": 0, "b": 100}
        with self.assertRaises(ValueError) as cm:
            parse_spec(spec)
        self.assertIn("Unknown view op", str(cm.exception))

    def test_invalid_span_typed_fail(self) -> None:
        """I06: Invalid span typed-fails"""
        spec = {"op": "lines", "a": 100, "b": 0}
        with self.assertRaises(ValueError) as cm:
            parse_spec(spec)
        self.assertIn("Invalid span", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
