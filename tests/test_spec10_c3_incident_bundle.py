from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pirml.cli_common import CliFailure
from scripts import spec10_incident


def _mk_trace(trace_path: Path, *, ok: bool = True, fail_tag: str = "") -> None:
    frame = {
        "op": "final",
        "id": "c00001",
        "seq": 1,
        "ok": ok,
        "result": {"ok": ok, "results": []},
    }
    if fail_tag:
        frame["fail_tag"] = fail_tag
    trace_path.write_text(json.dumps(frame) + "\n", encoding="utf-8")


def _mk_final(final_path: Path, *, ok: bool = True) -> None:
    final_path.write_text(
        json.dumps({"ok": ok, "results": [], "output": {"ok": ok}}, sort_keys=True),
        encoding="utf-8",
    )


class TestSpec10C3IncidentBundle(unittest.TestCase):
    def test_missing_trace_typed_error(self):
        with TemporaryDirectory(prefix="spec10_c3_missing_trace_") as tmp:
            out_dir = Path(tmp) / "out"
            cmd = [
                "python3",
                "-m",
                "scripts.spec10_incident",
                "--trace",
                str(Path(tmp) / "missing.ndjson"),
                "--out-dir",
                str(out_dir),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 2)
            self.assertNotIn("usage:", res.stderr.lower())
            err = json.loads(res.stderr)
            self.assertEqual(err["type"], "config")

    def test_invalid_timeout_typed_error(self):
        with TemporaryDirectory(prefix="spec10_c3_bad_timeout_") as tmp:
            trace_path = Path(tmp) / "trace.ndjson"
            out_dir = Path(tmp) / "out"
            _mk_trace(trace_path)
            _mk_final(trace_path.parent / "final.json")

            cmd = [
                "python3",
                "-m",
                "scripts.spec10_incident",
                "--trace",
                str(trace_path),
                "--out-dir",
                str(out_dir),
                "--timeout",
                "nope",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 2)
            err = json.loads(res.stderr)
            self.assertEqual(err["type"], "config")

    def test_incident_bundle_replay_and_artifact_checks(self):
        with TemporaryDirectory(prefix="spec10_c3_ok_") as tmp:
            root = Path(tmp)
            trace_path = root / "trace.ndjson"
            _mk_trace(trace_path)
            _mk_final(root / "final.json")
            out_dir = root / "out"

            def _fake_run(cmd, env=None):
                if "scripts.tools.replay" in cmd:
                    replay_out = Path(cmd[cmd.index("--out-dir") + 1])
                    replay_out.mkdir(parents=True, exist_ok=True)
                    (replay_out / "final.json").write_bytes((root / "final.json").read_bytes())
                return subprocess.CompletedProcess(cmd, 0, "", "")

            with patch("scripts.spec10_incident._run_command", side_effect=_fake_run):
                result = spec10_incident.run_incident(
                    trace_path=trace_path,
                    out_dir=out_dir,
                    prog_path=Path("tests/prog_ok.py"),
                    timeout_s=30.0,
                )

            self.assertEqual(result.report["class"], "OK")
            self.assertTrue(result.report["replay_match"])
            self.assertTrue(result.report["artifact_parity"])
            self.assertTrue((out_dir / "incident.json").is_file())
            self.assertTrue((out_dir / "incident.details.json").is_file())

    def test_replay_mismatch_classified(self):
        with TemporaryDirectory(prefix="spec10_c3_replay_mismatch_") as tmp:
            root = Path(tmp)
            trace_path = root / "trace.ndjson"
            _mk_trace(trace_path)
            _mk_final(root / "final.json")
            out_dir = root / "out"

            def _fake_run(cmd, env=None):
                if "scripts.tools.replay" in cmd:
                    replay_out = Path(cmd[cmd.index("--out-dir") + 1])
                    replay_out.mkdir(parents=True, exist_ok=True)
                    _mk_final(replay_out / "final.json", ok=False)
                return subprocess.CompletedProcess(cmd, 0, "", "")

            with (
                patch("scripts.spec10_incident._run_command", side_effect=_fake_run),
                self.assertRaises(CliFailure) as ctx,
            ):
                spec10_incident.run_incident(
                    trace_path=trace_path,
                    out_dir=out_dir,
                    prog_path=Path("tests/prog_ok.py"),
                    timeout_s=30.0,
                )

            self.assertEqual(ctx.exception.err_type, "integrity")
            report = json.loads((out_dir / "incident.json").read_text(encoding="utf-8"))
            self.assertEqual(report["class"], "REPLAY_MISMATCH")

    def test_report_shape_compact(self):
        with TemporaryDirectory(prefix="spec10_c3_shape_") as tmp:
            root = Path(tmp)
            trace_path = root / "trace.ndjson"
            _mk_trace(trace_path)
            _mk_final(root / "final.json")
            out_dir = root / "out"

            def _fake_run(cmd, env=None):
                if "scripts.tools.replay" in cmd:
                    replay_out = Path(cmd[cmd.index("--out-dir") + 1])
                    replay_out.mkdir(parents=True, exist_ok=True)
                    (replay_out / "final.json").write_bytes((root / "final.json").read_bytes())
                return subprocess.CompletedProcess(cmd, 0, "", "")

            with patch("scripts.spec10_incident._run_command", side_effect=_fake_run):
                spec10_incident.run_incident(
                    trace_path=trace_path,
                    out_dir=out_dir,
                    prog_path=Path("tests/prog_ok.py"),
                    timeout_s=30.0,
                )

            report = json.loads((out_dir / "incident.json").read_text(encoding="utf-8"))
            self.assertEqual(
                set(report.keys()),
                {
                    "class",
                    "rc",
                    "replay_match",
                    "artifact_parity",
                    "trace_ptr",
                    "notes",
                    "details_ptr",
                },
            )

    def test_hint_len_and_details_split(self):
        with TemporaryDirectory(prefix="spec10_c3_hint_") as tmp:
            root = Path(tmp)
            trace_path = root / "trace.ndjson"
            _mk_trace(trace_path)
            _mk_final(root / "final.json")
            out_dir = root / "out"

            def _fake_run(cmd, env=None):
                if "scripts.tools.replay" in cmd:
                    replay_out = Path(cmd[cmd.index("--out-dir") + 1])
                    replay_out.mkdir(parents=True, exist_ok=True)
                    (replay_out / "final.json").write_bytes((root / "final.json").read_bytes())
                return subprocess.CompletedProcess(cmd, 0, "", "")

            with patch("scripts.spec10_incident._run_command", side_effect=_fake_run):
                spec10_incident.run_incident(
                    trace_path=trace_path,
                    out_dir=out_dir,
                    prog_path=Path("tests/prog_ok.py"),
                    timeout_s=30.0,
                )

            report = json.loads((out_dir / "incident.json").read_text(encoding="utf-8"))
            self.assertLessEqual(len(report["notes"]), 120)
            self.assertTrue(Path(report["details_ptr"]).is_file())

    def test_inline_heavy_payload_fails(self):
        with TemporaryDirectory(prefix="spec10_c3_heavy_") as tmp:
            root = Path(tmp)
            trace_path = root / "trace.ndjson"
            heavy = "x" * 2000
            frame = {
                "op": "final",
                "id": "c00001",
                "seq": 1,
                "ok": True,
                "result": {"ok": True, "results": [{"blob": heavy}]},
            }
            trace_path.write_text(json.dumps(frame) + "\n", encoding="utf-8")
            _mk_final(root / "final.json")
            out_dir = root / "out"

            def _fake_run(cmd, env=None):
                if "scripts.tools.replay" in cmd:
                    replay_out = Path(cmd[cmd.index("--out-dir") + 1])
                    replay_out.mkdir(parents=True, exist_ok=True)
                    (replay_out / "final.json").write_bytes((root / "final.json").read_bytes())
                return subprocess.CompletedProcess(cmd, 0, "", "")

            with patch("scripts.spec10_incident._run_command", side_effect=_fake_run):
                spec10_incident.run_incident(
                    trace_path=trace_path,
                    out_dir=out_dir,
                    prog_path=Path("tests/prog_ok.py"),
                    timeout_s=30.0,
                )

            report = json.loads((out_dir / "incident.json").read_text(encoding="utf-8"))
            report_dump = json.dumps(report)
            self.assertNotIn(heavy, report_dump)
            details = json.loads((out_dir / "incident.details.json").read_text(encoding="utf-8"))
            details_dump = json.dumps(details)
            self.assertNotIn(heavy, details_dump)

    def test_fail_tag_mapping_single_label(self):
        with TemporaryDirectory(prefix="spec10_c3_fail_tag_") as tmp:
            root = Path(tmp)
            trace_path = root / "trace.ndjson"
            _mk_trace(trace_path, ok=False)
            _mk_final(root / "final.json", ok=False)
            out_dir = root / "out"

            def _fake_run(cmd, env=None):
                if "scripts.tools.replay" in cmd:
                    replay_out = Path(cmd[cmd.index("--out-dir") + 1])
                    replay_out.mkdir(parents=True, exist_ok=True)
                    (replay_out / "final.json").write_bytes((root / "final.json").read_bytes())
                return subprocess.CompletedProcess(cmd, 0, "", "")

            with patch("scripts.spec10_incident._run_command", side_effect=_fake_run):
                result = spec10_incident.run_incident(
                    trace_path=trace_path,
                    out_dir=out_dir,
                    prog_path=Path("tests/prog_ok.py"),
                    timeout_s=30.0,
                )

            self.assertEqual(result.report["class"], "OUTPUT_INVALID")
            self.assertNotRegex(result.report["class"], r"[|,;]")


if __name__ == "__main__":
    unittest.main()
