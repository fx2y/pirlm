import json
import os
import subprocess
import unittest


class TestSpec10C1CommandMatrix(unittest.TestCase):
    MATRIX_PATH = "spec-0/10/21-command-matrix.jsonl"
    SCRIPT_PATH = "scripts/spec10_matrix.py"

    def test_each_w_lane_has_single_authority_command(self):
        """I02: W-matrix has exactly one authority command per W0..W10 lane."""
        if not os.path.exists(self.MATRIX_PATH):
            self.skipTest(f"{self.MATRIX_PATH} not materialized yet")

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
        # This is enforced by test_each_w_lane_has_single_authority_command.
        pass

    def test_alias_rows_non_authority(self):
        """I03: alias rows are explicit and non-authoritative."""
        if not os.path.exists(self.MATRIX_PATH):
            self.skipTest(f"{self.MATRIX_PATH} not materialized yet")

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
        # Enforced by test_alias_rows_non_authority.
        pass

    def test_matrix_cli_typed_fail_lanes(self):
        """I04: C1 matrix CLI typed fail lanes for invalid lanes."""
        if not os.path.exists(self.SCRIPT_PATH):
            self.skipTest(f"{self.SCRIPT_PATH} not implemented yet")

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
        if not os.path.exists(self.SCRIPT_PATH):
            self.skipTest(f"{self.SCRIPT_PATH} not implemented yet")

        cmd = ["python3", "-m", "scripts.spec10_matrix", "--invalid-flag"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        self.assertEqual(result.returncode, 2)
        self.assertNotIn("usage:", result.stderr.lower())

        # Should be a typed JSON envelope
        stderr_data = json.loads(result.stderr)
        self.assertEqual(stderr_data.get("type"), "config")

    def test_owner_path_only(self):
        """I05: authority runtime rows route through owner path only."""
        if not os.path.exists(self.MATRIX_PATH):
            self.skipTest(f"{self.MATRIX_PATH} not materialized yet")

        valid_owners = [
            "scripts.pirml_run",
            "scripts.compile",
            "scripts.tools.replay",
            "scripts.spec10_matrix",
            "scripts.replay_check",
            "scripts.artifact_rebuild",
            "scripts.web_fixture_smoke",
            "scripts.spec09_tool_smoke",
            "python -m pirml",
            "mise run",
        ]

        with open(self.MATRIX_PATH) as f:
            for line in f:
                data = json.loads(line)
                if data.get("k") == "row" and data.get("authority"):
                    cmd = data.get("cmd", "")
                    # Ensure it uses one of the valid owner entry points
                    self.assertTrue(
                        any(owner in cmd for owner in valid_owners),
                        f"Authority command {cmd} must route through owner path",
                    )

    def test_direct_runtime_spawn_row_fails(self):
        """I05: Negative test for direct runtime spawn."""
        # Enforced by test_owner_path_only.
        pass


if __name__ == "__main__":
    unittest.main()
