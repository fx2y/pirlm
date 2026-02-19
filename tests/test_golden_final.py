from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import run_cli


class GoldenFinalTests(unittest.TestCase):
    def test_prog_ok_final_json_matches_golden(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            completed = run_cli(program="tests/prog_ok.py", out_dir=out_dir)
            self.assertEqual(completed.returncode, 0, completed.stderr)

            actual = (out_dir / "final.json").read_bytes()
            expected = Path("tests/golden/prog_ok.final.json").read_bytes()
            self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
