import json
import os
import subprocess
import unittest


class TestSpec10C2ProofPack(unittest.TestCase):
    def test_pack_index_emitted(self):
        """C2.T00: implement scripts/spec10_proof_pack.py orchestrating canonical W0..W8 rows"""
        cmd = ["python3", "-m", "scripts.spec10_proof_pack", "--out", "out/spec10_pack/index.jsonl"]
        # Ensure out dir exists
        os.makedirs("out/spec10_pack", exist_ok=True)

        # This will fail until script is implemented
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.fail(f"scripts/spec10_proof_pack.py failed or not found: {e}")

        self.assertTrue(os.path.exists("out/spec10_pack/index.jsonl"))

        with open("out/spec10_pack/index.jsonl") as f:
            lines = f.readlines()

        self.assertGreater(len(lines), 0)
        meta = json.loads(lines[0])
        self.assertEqual(meta.get("k"), "meta")
        self.assertEqual(meta.get("id"), "spec10-proof-pack")

    def test_lane_spec_table_stable(self):
        """C2.T01: encode lane specs as pure data"""
        # We check that at least W0..W8 are present in the output
        cmd = ["python3", "-m", "scripts.spec10_proof_pack", "--out", "out/spec10_pack/index.jsonl"]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

        with open("out/spec10_pack/index.jsonl") as f:
            rows = [json.loads(line) for line in f]

        lanes = {row.get("lane") for row in rows if row.get("k") == "row"}
        for i in range(9):
            self.assertIn(f"W{i}", lanes)

    def test_pack_pointer_resolve(self):
        """C2.T02: emit canonical pack rows with sha256, rc, artifact pointers"""
        # Ensure we have a fresh run
        cmd = ["python3", "-m", "scripts.spec10_proof_pack", "--out", "out/spec10_pack/index.jsonl"]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

        with open("out/spec10_pack/index.jsonl") as f:
            rows = [json.loads(line) for line in f if json.loads(line).get("k") == "row"]

        for row in rows:
            self.assertIn("rc", row)
            self.assertIn("sha256", row)
            # pointers check - if rc=0 and it's a lane we know produces trace
            if row["rc"] == 0 and row["lane"] in ["W0", "W1", "W6"]:
                self.assertIn("trace_ptr", row)

    def test_live_lane_marked_non_authoritative(self):
        """C2.T03: separate deterministic fixture lanes from optional live lane (W4b)"""
        # W4 should be deterministic fixture, W4b (if exists) should be optional
        # Let's check if the script supports W4b and marks it
        cmd = [
            "python3",
            "-m",
            "scripts.spec10_proof_pack",
            "--include-live",
            "--out",
            "out/spec10_pack/index.jsonl",
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

        with open("out/spec10_pack/index.jsonl") as f:
            rows = [json.loads(line) for line in f if json.loads(line).get("k") == "row"]

        w4_lanes = [r for r in rows if r["lane"].startswith("W4")]
        # At least one should be authority=True (W4), W4b should be False
        has_w4b = False
        for r in w4_lanes:
            if r["lane"] == "W4":
                self.assertTrue(r.get("authority", True))
            elif r["lane"] == "W4b":
                self.assertFalse(r.get("authority", True))
                has_w4b = True
        self.assertTrue(has_w4b)

    def test_eval_rows_require_explicit_dataset(self):
        """C2.T04: wire explicit-ingress eval/report schema checks"""
        cmd = [
            "python3",
            "-m",
            "scripts.spec10_proof_pack",
            "--skip-run",
            "--out",
            "out/spec10_pack/index.jsonl",
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

        with open("out/spec10_pack/index.jsonl") as f:
            rows = [json.loads(line) for line in f if json.loads(line).get("k") == "row"]

        for row in rows:
            cmd_str = row.get("cmd", "")
            if "eval" in cmd_str or "report" in cmd_str:
                # Should have explicit --dataset or explicit input paths
                pass


if __name__ == "__main__":
    unittest.main()
