from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from tests.common import run_cli


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _load_trace(path: Path) -> list[dict[str, object]]:
    return [
        cast(dict[str, object], json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


class C4ObservabilityTests(unittest.TestCase):
    def test_trace_envelope_fields_are_stable_and_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            completed = run_cli(program="tests/prog_ok.py", out_dir=out_dir)
            self.assertEqual(completed.returncode, 0, completed.stderr)

            frames = _load_trace(out_dir / "trace.ndjson")
            self.assertGreater(len(frames), 0)

            expected_seq = 1
            for frame in frames:
                self.assertEqual(frame.get("seq"), expected_seq)
                expected_seq += 1
                self.assertIn(frame.get("dir"), {"in", "out"})
                ts = frame.get("ts")
                ms = frame.get("ms")
                self.assertIsInstance(ts, int)
                self.assertIsInstance(ms, int)
                assert isinstance(ms, int)
                self.assertGreaterEqual(ms, 0)

                op = frame.get("op")
                if op == "call":
                    self.assertEqual(frame.get("sha256_args"), _sha256_json(frame.get("args")))
                elif op == "result":
                    hash_target = frame.get("output") if "output" in frame else frame.get("error")
                    self.assertEqual(frame.get("sha256_output"), _sha256_json(hash_target))
                elif op == "final":
                    self.assertEqual(frame.get("sha256_output"), _sha256_json(frame.get("result")))

    def test_sensitive_call_args_are_redacted_in_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            out_dir = base / "out"
            prog = base / "prog_sensitive.py"
            secret = "sk_live_abc123"
            prog.write_text(
                "\n".join(
                    [
                        "from pirml.protocol import call, send_final",
                        "result = call('bash', {'command': 'printf ok', 'api_key': 'sk_live_abc123'})",
                        "send_final(True, {'ok': True, 'results': [{'id': result['id'], 'tool': 'bash', 'ok': result['ok']}]})",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = run_cli(program=str(prog), out_dir=out_dir)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            call_frame = _load_trace(out_dir / "trace.ndjson")[0]
            args = call_frame.get("args")
            self.assertIsInstance(args, dict)
            assert isinstance(args, dict)
            args_map = cast(dict[str, Any], args)
            self.assertIsInstance(args_map.get("api_key"), dict)
            redacted = cast(dict[str, Any], args_map["api_key"])
            self.assertEqual(
                redacted.get("redacted_sha256"),
                _sha256_json(secret),
            )
            self.assertNotIn(secret, json.dumps(call_frame, sort_keys=True))

    def test_G6_secret_redaction_variants(self) -> None:
        """G6: secret redaction keys include auth*"""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            prog = out_dir / "auth_leak.py"
            prog.write_text(
                "from pirml.protocol import call, send_final\n"
                "call('echo', {'auth_token': 'secret123', 'Authorization': 'Bearer abc'})\n"
                "send_final(True, {'ok': True, 'results': []})\n",
                encoding="utf-8",
            )

            run_cli(program=str(prog), out_dir=out_dir)
            trace_text = (out_dir / "trace.ndjson").read_text()
            self.assertNotIn("secret123", trace_text)
            self.assertNotIn("Bearer abc", trace_text)
            self.assertIn("redacted_sha256", trace_text)

    def test_metrics_row_contains_expected_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            completed = run_cli(program="tests/prog_ok.py", out_dir=out_dir)
            self.assertEqual(completed.returncode, 0, completed.stderr)

            metrics = (out_dir / "metrics.csv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                metrics[0], "calls,retries,failures,wall_ms,final_ok,trace_sha,final_sha"
            )
            cols = metrics[1].split(",")
            self.assertEqual(len(cols), 7)
            self.assertGreaterEqual(int(cols[0]), 1)
            self.assertGreaterEqual(int(cols[1]), 0)
            self.assertGreaterEqual(int(cols[2]), 0)
            self.assertGreaterEqual(int(cols[3]), 0)
            self.assertEqual(cols[4], "1")

            trace_sha = hashlib.sha256((out_dir / "trace.ndjson").read_bytes()).hexdigest()
            final_sha = hashlib.sha256((out_dir / "final.json").read_bytes()).hexdigest()
            self.assertEqual(cols[5], trace_sha)
            self.assertEqual(cols[6], final_sha)


if __name__ == "__main__":
    unittest.main()
