from __future__ import annotations

import json
import subprocess
import unittest
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


def _sha256_path(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _mk_trace(trace_path: Path) -> None:
    frames = [
        {
            "op": "call",
            "id": "c00001",
            "seq": 1,
            "dir": "in",
            "ms": 1,
            "ts": 1700000001,
            "tool": "echo",
            "args": {"text": "alpha"},
            "sha256_args": "fd95ccc5f06aab4d7e075f7790e2ef574260a505a4c9aa7ecf858f5a0b8dea83",
        },
        {
            "op": "result",
            "id": "c00001",
            "seq": 2,
            "dir": "out",
            "ms": 2,
            "ts": 1700000002,
            "ok": True,
            "output": "alpha",
            "sha256_output": "902cf2b465fb076229183b408aad4014266eb9eb72d448754227adc1eeac49b9",
        },
        {
            "op": "final",
            "seq": 3,
            "dir": "in",
            "ms": 3,
            "ts": 1700000003,
            "ok": True,
            "result": {"ok": True, "results": [{"id": "c00001", "ok": True, "tool": "echo"}]},
            "sha256_output": "9a8ece0dfd1e74060f516ddf4a4bdca939f89baad438875f4e8043e5e264f29d",
        },
    ]
    trace_path.write_text(
        "\n".join(json.dumps(row, separators=(",", ":")) for row in frames) + "\n"
    )


def _mk_final(final_path: Path, *, ok: bool = True) -> None:
    final_path.write_text(
        json.dumps(
            {"ok": ok, "results": [{"id": "c00001", "ok": ok, "tool": "echo"}]},
            separators=(",", ":"),
        )
    )


class TestSpec10C4SurfaceResolvers(unittest.TestCase):
    def test_surface_subcommand_contract(self):
        cmd = ["python3", "-m", "scripts.spec10_surface"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 2)
        self.assertNotIn("usage:", res.stderr.lower())
        err = json.loads(res.stderr)
        self.assertEqual(err["type"], "config")

    def test_surface_unknown_subcommand_typed(self):
        cmd = ["python3", "-m", "scripts.spec10_surface", "nope"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 2)
        err = json.loads(res.stderr)
        self.assertEqual(err["type"], "config")

    def test_console_view_fields(self):
        with TemporaryDirectory(prefix="spec10_c4_console_") as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            _mk_trace(run_dir / "trace.ndjson")
            _mk_final(run_dir / "final.json")

            cmd = ["python3", "-m", "scripts.spec10_surface", "console", "--run", str(run_dir)]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 0)
            payload = json.loads(res.stdout)

            self.assertEqual(payload["surface"], "console")
            self.assertEqual(payload["run_id"], run_dir.name)
            self.assertEqual(payload["rc"], 0)
            self.assertIn("parity", payload)
            self.assertIn("gate", payload)
            self.assertEqual(payload["pointers"]["trace_ptr"], str(run_dir / "trace.ndjson"))
            self.assertEqual(payload["pointers"]["final_ptr"], str(run_dir / "final.json"))

    def test_console_missing_artifact_fails(self):
        with TemporaryDirectory(prefix="spec10_c4_console_missing_") as tmp:
            cmd = [
                "python3",
                "-m",
                "scripts.spec10_surface",
                "console",
                "--run",
                str(Path(tmp) / "run"),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 2)
            err = json.loads(res.stderr)
            self.assertEqual(err["type"], "integrity")

    def test_evidence_view_final_last_and_id_seq(self):
        with TemporaryDirectory(prefix="spec10_c4_evidence_") as tmp:
            trace_path = Path(tmp) / "trace.ndjson"
            _mk_trace(trace_path)

            cmd = [
                "python3",
                "-m",
                "scripts.spec10_surface",
                "evidence",
                "--trace",
                str(trace_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 0)
            payload = json.loads(res.stdout)

            self.assertEqual(payload["surface"], "evidence")
            self.assertTrue(payload["summary"]["final_last"])
            self.assertEqual(payload["summary"]["first_seq"], 1)
            self.assertEqual(payload["summary"]["last_seq"], 3)

    def test_evidence_duplicate_final_fails(self):
        with TemporaryDirectory(prefix="spec10_c4_evidence_dup_") as tmp:
            trace_path = Path(tmp) / "trace.ndjson"
            _mk_trace(trace_path)
            extra: dict[str, Any] = {
                "op": "final",
                "seq": 4,
                "dir": "in",
                "ms": 4,
                "ts": 1700000004,
                "ok": True,
                "result": {"ok": True, "results": []},
                "sha256_output": "356564934c23925f484358ec5a2bfa98be95469fde0d36679e18ebc693a8ca16",
            }
            trace_path.write_text(trace_path.read_text(encoding="utf-8") + json.dumps(extra) + "\n")

            cmd = [
                "python3",
                "-m",
                "scripts.spec10_surface",
                "evidence",
                "--trace",
                str(trace_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 2)
            err = json.loads(res.stderr)
            self.assertEqual(err["type"], "integrity")

    def test_eval_view_tuple_ordering(self):
        with TemporaryDirectory(prefix="spec10_c4_eval_") as tmp:
            report_path = Path(tmp) / "report.json"
            delta_path = Path(tmp) / "delta.json"
            report_path.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "acc": 0.75,
                        "acc_per_$": 1.2,
                        "acc_per_min": 0.8,
                        "median_latency": 120.0,
                        "median_cost": 0.02,
                        "fail_pareto": [{"fail_tag": "TIMEOUT", "count": 2, "top_task_ids": []}],
                    }
                ),
                encoding="utf-8",
            )
            delta_path.write_text(json.dumps({"ok": True, "acc_delta": 0.01}), encoding="utf-8")

            cmd = [
                "python3",
                "-m",
                "scripts.spec10_surface",
                "eval",
                "--report",
                str(report_path),
                "--delta",
                str(delta_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 0)
            payload = json.loads(res.stdout)

            self.assertEqual(payload["surface"], "eval")
            self.assertEqual(payload["kpi_tuple"], [0.75, 1.2, 0.8, 120.0, 0.02])
            self.assertEqual(payload["fail_pareto"][0]["fail_tag"], "TIMEOUT")
            self.assertEqual(payload["delta"]["acc_delta"], 0.01)

    def test_eval_view_hash_tie_break_drift_fails(self):
        with TemporaryDirectory(prefix="spec10_c4_eval_missing_") as tmp:
            report_path = Path(tmp) / "report.json"
            report_path.write_text(json.dumps({"ok": True, "acc": 0.75}), encoding="utf-8")
            cmd = [
                "python3",
                "-m",
                "scripts.spec10_surface",
                "eval",
                "--report",
                str(report_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 1)
            err = json.loads(res.stderr)
            self.assertEqual(err["type"], "validation")

    def test_policy_view_raw_typed_errors(self):
        with TemporaryDirectory(prefix="spec10_c4_policy_") as tmp:
            policy_path = Path(tmp) / "doctor.ndjson"
            rows = [
                {
                    "check": "pipx",
                    "ok": False,
                    "error": {"type": "unsupported", "msg": "pipx missing", "retryable": False},
                },
                {"decision": "allow", "type": "policy_decision", "msg": "caller allowed", "rc": 0},
            ]
            policy_path.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
            )

            cmd = ["python3", "-m", "scripts.spec10_surface", "policy", "--log", str(policy_path)]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 0)
            payload = json.loads(res.stdout)

            self.assertEqual(payload["surface"], "policy")
            self.assertGreaterEqual(len(payload["rows"]), 2)
            self.assertEqual(payload["rows"][0]["type"], "unsupported")
            self.assertIn("msg", payload["rows"][0])

    def test_policy_view_prose_only_fails(self):
        with TemporaryDirectory(prefix="spec10_c4_policy_bad_") as tmp:
            policy_path = Path(tmp) / "policy.log"
            policy_path.write_text("not-json\nstill-not-json\n", encoding="utf-8")
            cmd = ["python3", "-m", "scripts.spec10_surface", "policy", "--log", str(policy_path)]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 2)
            err = json.loads(res.stderr)
            self.assertEqual(err["type"], "integrity")

    def test_runtime_stdout_contract_preserved(self):
        with TemporaryDirectory(prefix="spec10_c4_stdout_") as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            trace_path = run_dir / "trace.ndjson"
            _mk_trace(trace_path)
            _mk_final(run_dir / "final.json")
            before = _sha256_path(trace_path)

            cmd = ["python3", "-m", "scripts.spec10_surface", "console", "--run", str(run_dir)]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 0)
            self.assertEqual(len([line for line in res.stdout.splitlines() if line.strip()]), 1)
            json.loads(res.stdout)

            after = _sha256_path(trace_path)
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
