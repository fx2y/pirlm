import contextlib
import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pirml.artifacts.paths import default_layout
from pirml.artifacts.store import ArtifactStore
from pirml.compiler.model import ModelAdapter
from pirml.rlm.kernel import RlmKernel, RlmState


class TestSpec06C6Pointers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp_dir = Path("out/test_spec06_c6")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.layout = default_layout(self.tmp_dir / "art")
        self.layout.root.mkdir(parents=True, exist_ok=True)
        self.store = ArtifactStore(self.layout)

        self.model = MagicMock(spec=ModelAdapter)
        # Mock model to return Final=123
        self.model.compile_once.side_effect = ["Final = 123", "Final = 123"]

    async def test_pointer_emission_opt_in(self):
        """C6.T00, C6.T01: Flag-on emits pointer rows"""
        kernel = RlmKernel(self.store, self.model, emit_pi_pointers=True)

        # We need to capture stdout to see send_custom output
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            await kernel.run("test goal")

        output = f.getvalue()
        rows = [json.loads(line) for line in output.splitlines() if line.strip()]

        # Should see pirml_summary and pirml CustomEntry
        custom_rows = [r for r in rows if r.get("op") == "custom"]
        self.assertTrue(any(r["type"] == "pirml_summary" for r in custom_rows))
        self.assertTrue(any(r["type"] == "pirml" for r in custom_rows))

        # Verify content of 'pirml' row
        p_row = next(r for r in custom_rows if r["type"] == "pirml")
        self.assertIn("trace", p_row["data"])
        self.assertIn("final", p_row["data"])
        self.assertIn("roots", p_row["data"])
        self.assertEqual(p_row["data"]["trace"], str(self.layout.trace_path))

    async def test_pointer_emission_default_off(self):
        """C6.T00: Default is off (no env, no flag)"""
        with patch.dict(os.environ, {}, clear=True):
            kernel = RlmKernel(self.store, self.model)
            self.assertFalse(kernel.emit_pi_pointers)

            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                await kernel.run("test goal")

            output = f.getvalue()
            rows = [json.loads(line) for line in output.splitlines() if line.strip()]
            custom_rows = [r for r in rows if r.get("op") == "custom"]
            self.assertEqual(len(custom_rows), 0)

    async def test_env_gate(self):
        """C6.T00: PIRML_EMIT_PI_POINTERS=1 enables emission"""
        with patch.dict(os.environ, {"PIRML_EMIT_PI_POINTERS": "1"}):
            kernel = RlmKernel(self.store, self.model)
            self.assertTrue(kernel.emit_pi_pointers)

    async def test_no_ctx_contamination(self):
        """C6.T03: custom entries never added to governor candidate set"""
        kernel = RlmKernel(self.store, self.model, emit_pi_pointers=True)
        # Manually add a custom entry to history
        kernel.history.append(
            ev="custom", prefix="SHOULD_NOT_SEE_THIS", full_len=20, ts=123, data={"foo": "bar"}
        )

        prompt = kernel.build_prompt(RlmState(P="goal"))
        self.assertNotIn("SHOULD_NOT_SEE_THIS", prompt)
        self.assertNotIn("custom", prompt.lower())

    async def test_summary_row_content(self):
        """C6.T02: Summary row contains expected keys"""
        kernel = RlmKernel(self.store, self.model, emit_pi_pointers=True)

        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            kernel.build_prompt(RlmState(P="goal"))

        output = f.getvalue()
        rows = [json.loads(line) for line in output.splitlines() if line.strip()]
        s_row = next(r for r in rows if r["op"] == "custom" and r["type"] == "pirml_summary")

        self.assertIn("summary", s_row["data"])
        self.assertIn("firstKeptEntryId", s_row["data"])
        self.assertIn("tokensBefore", s_row["data"])
        self.assertIsInstance(s_row["data"]["tokensBefore"], int)


if __name__ == "__main__":
    unittest.main()
