from __future__ import annotations

import json
import subprocess
import unittest
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from pirml.cli_common import CliFailure
from scripts import spec10_incident


def _mk_trace(trace_path: Path, *, ok: bool = True, fail_tag: str = "") -> None:
    frame: dict[str, Any] = {
        "op": "final",
        "id": "c00001",
        "seq": 1,
        "dir": "in",
        "ms": 1,
        "ts": 1700000001,
        "ok": ok,
        "result": {"ok": ok, "results": []},
        "sha256_output": "356564934c23925f484358ec5a2bfa98be95469fde0d36679e18ebc693a8ca16",
    }
    if fail_tag:
        frame["fail_tag"] = fail_tag
    trace_path.write_text(json.dumps(frame) + "\n", encoding="utf-8")


def _mk_final(final_path: Path, *, ok: bool = True) -> None:
    final_path.write_text(
        json.dumps({"ok": ok, "results": [], "output": {"ok": ok}}, sort_keys=True),
        encoding="utf-8",
    )


def _fake_run_factory(
    root: Path, *, replay_ok: bool = True
) -> Callable[[list[str], dict[str, str] | None], subprocess.CompletedProcess[str]]:
    def _fake_run(
        cmd: list[str], env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        del env
        if "scripts.tools.replay" in cmd:
            out_idx = cmd.index("--out-dir") + 1
            replay_out = Path(cmd[out_idx])
            replay_out.mkdir(parents=True, exist_ok=True)
            if replay_ok:
                (replay_out / "final.json").write_bytes((root / "final.json").read_bytes())
            else:
                _mk_final(replay_out / "final.json", ok=False)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    return _fake_run


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

            with patch(
                "scripts.spec10_incident._run_command",
                side_effect=_fake_run_factory(root, replay_ok=True),
            ):
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

            with (
                patch(
                    "scripts.spec10_incident._run_command",
                    side_effect=_fake_run_factory(root, replay_ok=False),
                ),
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
            self.assertEqual(report["rc"], 2)

    def test_report_shape_compact(self):
        with TemporaryDirectory(prefix="spec10_c3_shape_") as tmp:
            root = Path(tmp)
            trace_path = root / "trace.ndjson"
            _mk_trace(trace_path)
            _mk_final(root / "final.json")
            out_dir = root / "out"

            with patch(
                "scripts.spec10_incident._run_command",
                side_effect=_fake_run_factory(root, replay_ok=True),
            ):
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

            with patch(
                "scripts.spec10_incident._run_command",
                side_effect=_fake_run_factory(root, replay_ok=True),
            ):
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
            frame: dict[str, Any] = {
                "op": "final",
                "id": "c00001",
                "seq": 1,
                "dir": "in",
                "ms": 1,
                "ts": 1700000001,
                "ok": True,
                "result": {"ok": True, "results": [{"blob": heavy}]},
                "sha256_output": "356564934c23925f484358ec5a2bfa98be95469fde0d36679e18ebc693a8ca16",
            }
            trace_path.write_text(json.dumps(frame) + "\n", encoding="utf-8")
            _mk_final(root / "final.json")
            out_dir = root / "out"

            with patch(
                "scripts.spec10_incident._run_command",
                side_effect=_fake_run_factory(root, replay_ok=True),
            ):
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

            with patch(
                "scripts.spec10_incident._run_command",
                side_effect=_fake_run_factory(root, replay_ok=True),
            ):
                result = spec10_incident.run_incident(
                    trace_path=trace_path,
                    out_dir=out_dir,
                    prog_path=Path("tests/prog_ok.py"),
                    timeout_s=30.0,
                )

            self.assertEqual(result.report["class"], "OUTPUT_INVALID")
            self.assertNotRegex(result.report["class"], r"[|,;]")

    def test_strict_trace_validation_runs_pre_classification(self):
        with TemporaryDirectory(prefix="spec10_c3_strict_trace_") as tmp:
            root = Path(tmp)
            trace_path = root / "trace.ndjson"
            trace_path.write_text(
                json.dumps(
                    {"op": "bogus", "id": "c00001", "seq": 1, "ok": True, "result": {"ok": True}}
                )
                + "\n",
                encoding="utf-8",
            )
            _mk_final(root / "final.json")
            out_dir = root / "out"

            with self.assertRaises(CliFailure) as ctx:
                spec10_incident.run_incident(
                    trace_path=trace_path,
                    out_dir=out_dir,
                    prog_path=Path("tests/prog_ok.py"),
                    timeout_s=30.0,
                )
            self.assertEqual(ctx.exception.err_type, "integrity")


if __name__ == "__main__":
    unittest.main()
