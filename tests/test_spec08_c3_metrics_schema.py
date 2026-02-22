from __future__ import annotations

import unittest


@unittest.skip("Spec08 C3 metrics/schema declared in C0; implementation lands in C3.")
class Spec08C3MetricsSchemaTests(unittest.TestCase):
    def test_required_fields(self) -> None:
        pass

    def test_eval_row_requires_new_fields(self) -> None:
        pass

    def test_unexpected_field_fails(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
