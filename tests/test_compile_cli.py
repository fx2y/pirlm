from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GOOD_RAW = """<<<PROG>>>
import asyncio
from pirml.runtime.rpc import send_final
async def main():
    send_final(True, {"ok": True, "results": []})
if __name__ == "__main__":
    asyncio.run(main())
<<<CONTRACT>>>
{"tool_deps":[],"io_schema":{"trace_ptr":"trace.ndjson","final_schema":{},"citations_schema":{}},"budgets":{"max_calls":1,"max_parallel":1,"max_bytes_in":128,"max_bytes_out":128,"timeout_s":5},"assertions":[]}
"""


class TestCompileCLI(unittest.TestCase):
    def _run(self, out_dir: Path, *extra_args: str, env: dict[str, str] | None = None):
        cmd = [
            sys.executable,
            "-m",
            "scripts.compile",
            "--task",
            "echo hi",
            "--tools-dir",
            "tests/fixtures/toolsearch/catalog",
            "--out-dir",
            str(out_dir),
            *extra_args,
        ]
        proc_env = dict(os.environ)
        if env:
            proc_env.update(env)
        return subprocess.run(cmd, capture_output=True, text=True, check=False, env=proc_env)

    def test_smoke_flag_controls_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)

            no_smoke_out = base / "no-smoke"
            res_no_smoke = self._run(no_smoke_out, env={"PIRML_MODEL_RAW": GOOD_RAW})
            self.assertEqual(res_no_smoke.returncode, 0, res_no_smoke.stderr)
            self.assertFalse((no_smoke_out / "smoke_trace.ndjson").exists())

            smoke_out = base / "smoke"
            res_smoke = self._run(smoke_out, "--smoke", env={"PIRML_MODEL_RAW": GOOD_RAW})
            self.assertEqual(res_smoke.returncode, 0, res_smoke.stderr)
            self.assertTrue((smoke_out / "smoke_trace.ndjson").exists())

    def test_rc_contract_0_1_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)

            rc0 = self._run(base / "ok", env={"PIRML_MODEL_RAW": GOOD_RAW})
            self.assertEqual(rc0.returncode, 0, rc0.stderr)

            rc1 = self._run(base / "biz", env={"PIRML_MODEL_RAW": "invalid"})
            self.assertEqual(rc1.returncode, 1, rc1.stderr)

            bad_tools = base / "missing-tools"
            rc2 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.compile",
                    "--task",
                    "echo hi",
                    "--tools-dir",
                    str(bad_tools),
                    "--out-dir",
                    str(base / "int"),
                ],
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "PIRML_MODEL_RAW": GOOD_RAW},
            )
            self.assertEqual(rc2.returncode, 2, rc2.stderr)

    def test_model_arg_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            res = self._run(out_dir, "--model", "stub", env={"PIRML_MODEL_RAW": GOOD_RAW})
            self.assertEqual(res.returncode, 2)
            self.assertIn("unrecognized arguments: --model", res.stderr)


if __name__ == "__main__":
    unittest.main()
