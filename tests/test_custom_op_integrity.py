from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from pirml.clock import SequenceClock
from pirml.engine import run_live
from pirml.protocol import MAX_LINE_BYTES_DEFAULT
from pirml.runtime.rpc import validate_strict_trace
from pirml.tools import ToolRegistry


class TestCustomOpIntegrity(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir)

    def test_custom_op_is_hashed_and_validated(self) -> None:
        # Create a program that sends a custom op
        prog_path = self.tmp_dir / "prog.py"
        prog_path.write_text(
            "from pirml.runtime.rpc import send_custom, send_final\n"
            "send_custom('test_type', {'foo': 'bar'})\n"
            "send_final(True, {'ok': True, 'results': []})\n"
        )

        registry = ToolRegistry()
        clock = SequenceClock(start=1000)

        output = run_live(
            program_path=prog_path,
            registry=registry,
            clock=clock,
            max_line_bytes=MAX_LINE_BYTES_DEFAULT,
        )

        # Check if custom frame has sha256_data
        custom_frames = [f for f in output.frames if f.get("op") == "custom"]
        self.assertEqual(len(custom_frames), 1)
        self.assertIn("sha256_data", custom_frames[0])
        self.assertIn("seq", custom_frames[0])
        self.assertIn("dir", custom_frames[0])

        # validate_strict_trace should pass
        validate_strict_trace(output.frames, max_line_bytes=MAX_LINE_BYTES_DEFAULT)

    def test_custom_op_missing_hash_fails_validation(self) -> None:
        # Create a program that sends a custom op
        prog_path = self.tmp_dir / "prog.py"
        prog_path.write_text(
            "from pirml.runtime.rpc import send_custom, send_final\n"
            "send_custom('test_type', {'foo': 'bar'})\n"
            "send_final(True, {'ok': True, 'results': []})\n"
        )

        registry = ToolRegistry()
        clock = SequenceClock(start=1000)

        output = run_live(
            program_path=prog_path,
            registry=registry,
            clock=clock,
            max_line_bytes=MAX_LINE_BYTES_DEFAULT,
        )

        # Tamper with the custom op: remove sha256_data
        frames = list(output.frames)
        for i, f in enumerate(frames):
            if f.get("op") == "custom":
                tampered = dict(f)
                del tampered["sha256_data"]
                frames[i] = tampered

        from pirml.runtime.rpc import ProtocolError

        with self.assertRaises(ProtocolError) as cm:
            validate_strict_trace(frames, max_line_bytes=MAX_LINE_BYTES_DEFAULT)
        self.assertIn("sha256_data", str(cm.exception))

    def test_custom_op_redaction(self) -> None:
        # Create a program that sends a custom op with a secret
        prog_path = self.tmp_dir / "prog.py"
        prog_path.write_text(
            "from pirml.runtime.rpc import send_custom, send_final\n"
            "send_custom('test_type', {'api_key': 'secret_123', 'foo': 'bar'})\n"
            "send_final(True, {'ok': True, 'results': []})\n"
        )

        registry = ToolRegistry()
        clock = SequenceClock(start=1000)

        output = run_live(
            program_path=prog_path,
            registry=registry,
            clock=clock,
            max_line_bytes=MAX_LINE_BYTES_DEFAULT,
        )

        # Check if custom frame has redacted api_key
        custom_frames = [f for f in output.frames if f.get("op") == "custom"]
        self.assertEqual(len(custom_frames), 1)
        data = custom_frames[0]["data"]
        self.assertIn("api_key", data)
        self.assertIn("redacted_sha256", data["api_key"])
        self.assertNotEqual(data["api_key"]["redacted_sha256"], "secret_123")
        self.assertEqual(data["foo"], "bar")


if __name__ == "__main__":
    unittest.main()
