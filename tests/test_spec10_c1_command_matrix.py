import json
import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.spec10_matrix import VALID_OWNERS


class TestSpec10C1CommandMatrix(unittest.TestCase):
    MATRIX_PATH = "spec-0/10/21-command-matrix.jsonl"
    SCRIPT_PATH = "scripts/spec10_matrix.py"

    def _full_matrix_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = [{"k": "meta", "id": "spec10-matrix"}]
        for idx in range(11):
            rows.append(
                {
                    "k": "row",
                    "lane": f"W{idx}",
                    "cmd": "python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/spec10_c1",
                    "authority": True,
                }
            )
        return rows

    def _write_matrix(self, path: Path, rows: list[dict[str, object]]) -> None:
        path.write_text(
            "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
            encoding="utf-8",
        )

    def test_each_w_lane_has_single_authority_command(self):
        """I02: W-matrix has exactly one authority command per W0..W10 lane."""
        self.assertTrue(os.path.exists(self.MATRIX_PATH), f"missing matrix: {self.MATRIX_PATH}")

        lanes: dict[str, str] = {}
        with open(self.MATRIX_PATH) as f:
            for line in f:
                data = json.loads(line)
                if data.get("k") == "row":
                    lane = str(data.get("lane"))
                    is_authority = bool(data.get("authority", False))
                    if is_authority:
                        self.assertNotIn(lane, lanes, f"Duplicate authority for lane {lane}")
                        lanes[lane] = str(data.get("cmd"))

        expected_lanes = [f"W{i}" for i in range(11)]
        for lane in expected_lanes:
            self.assertIn(lane, lanes, f"Missing authority command for lane {lane}")

    def test_duplicate_authority_rows_fail(self):
        """I02: Negative test for duplicate authority rows."""
        with TemporaryDirectory(prefix="spec10_c1_dupe_") as tmp:
            matrix = Path(tmp) / "matrix.jsonl"
            rows = self._full_matrix_rows()
            rows.append(
                {
                    "k": "row",
                    "lane": "W0",
                    "cmd": "python -m scripts.spec10_matrix",
                    "authority": True,
                }
            )
            self._write_matrix(matrix, rows)
            cmd = ["python3", "-m", "scripts.spec10_matrix", "--matrix", str(matrix)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            err = json.loads(result.stderr)
            self.assertEqual(err["type"], "integrity")
            self.assertIn("duplicate authority lane", err["msg"])

    def test_alias_rows_non_authority(self):
        """I03: alias rows are explicit and non-authoritative."""
        self.assertTrue(os.path.exists(self.MATRIX_PATH), f"missing matrix: {self.MATRIX_PATH}")

        with open(self.MATRIX_PATH) as f:
            for line in f:
                data = json.loads(line)
                if data.get("k") == "alias":
                    self.assertFalse(
                        data.get("authority", False),
                        f"Alias row {data.get('alias')} must not be authority",
                    )
                    self.assertTrue(
                        data.get("ref"),
                        f"Alias row {data.get('alias')} must have a reference to an authority lane",
                    )

    def test_alias_without_authority_fails(self):
        """I03: Negative test for alias without authority ref."""
        with TemporaryDirectory(prefix="spec10_c1_alias_") as tmp:
            matrix = Path(tmp) / "matrix.jsonl"
            rows = self._full_matrix_rows()
            rows.append({"k": "alias", "alias": "bad", "ref": "W99", "authority": False})
            self._write_matrix(matrix, rows)
            cmd = ["python3", "-m", "scripts.spec10_matrix", "--matrix", str(matrix)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            err = json.loads(result.stderr)
            self.assertEqual(err["type"], "integrity")
            self.assertIn("alias ref missing lane", err["msg"])

    def test_matrix_cli_typed_fail_lanes(self):
        """I04: C1 matrix CLI typed fail lanes for invalid lanes."""
        self.assertTrue(os.path.exists(self.SCRIPT_PATH), f"missing script: {self.SCRIPT_PATH}")

        # Use an invalid lane
        cmd = ["python3", "-m", "scripts.spec10_matrix", "--lane", "W99"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        # C1 matrix/CLI parse failures are typed config rc2 (I04)
        self.assertEqual(
            result.returncode, 2, f"Expected rc2 for invalid lane, got {result.returncode}"
        )

        stderr_data = json.loads(result.stderr)
        self.assertEqual(stderr_data.get("type"), "config")
        self.assertIn("W99", stderr_data.get("msg"))

    def test_parse_fail_typed_no_usage(self):
        """I04: Verify no `usage:` leakage in stderr on parse failure."""
        self.assertTrue(os.path.exists(self.SCRIPT_PATH), f"missing script: {self.SCRIPT_PATH}")

        cmd = ["python3", "-m", "scripts.spec10_matrix", "--invalid-flag"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        self.assertEqual(result.returncode, 2)
        self.assertNotIn("usage:", result.stderr.lower())

        # Should be a typed JSON envelope
        stderr_data = json.loads(result.stderr)
        self.assertEqual(stderr_data.get("type"), "config")

    def test_owner_path_only(self):
        """I05: authority runtime rows route through owner path only."""
        self.assertTrue(os.path.exists(self.MATRIX_PATH), f"missing matrix: {self.MATRIX_PATH}")

        with open(self.MATRIX_PATH) as f:
            for line in f:
                data = json.loads(line)
                if data.get("k") == "row" and data.get("authority"):
                    cmd = data.get("cmd", "")
                    # Ensure it uses one of the valid owner entry points
                    self.assertTrue(
                        any(owner in cmd for owner in VALID_OWNERS),
                        f"Authority command {cmd} must route through owner path",
                    )

    def test_direct_runtime_spawn_row_fails(self):
        """I05: Negative test for direct runtime spawn."""
        with TemporaryDirectory(prefix="spec10_c1_spawn_") as tmp:
            matrix = Path(tmp) / "matrix.jsonl"
            rows = self._full_matrix_rows()
            for row in rows:
                if row.get("k") == "row" and row.get("lane") == "W0":
                    row["cmd"] = "python tests/prog_ok.py"

            self._write_matrix(matrix, rows)
            cmd = ["python3", "-m", "scripts.spec10_matrix", "--matrix", str(matrix)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            err = json.loads(result.stderr)
            self.assertEqual(err["type"], "integrity")
            self.assertIn("authority command must route through owner path", err["msg"])


if __name__ == "__main__":
    unittest.main()
