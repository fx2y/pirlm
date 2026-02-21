from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from typing import cast

from pirml.artifacts.store import ArtifactStore
from pirml.compiler.model import StubModelAdapter
from pirml.rlm import RlmBudget, RlmErrorType, RlmKernel, RlmKernelError, run_rlm


class TestRlmKernel(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())
        from pirml.artifacts.paths import default_layout

        self.store = ArtifactStore(default_layout(self.tmp_dir))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir)

    async def test_rlm_basic_loop(self) -> None:
        # C3.T04: Stop condition Final
        model = StubModelAdapter('Final = "success"')
        res = await run_rlm("test", self.store, model)
        self.assertEqual(res, "success")

    async def test_rlm_history_metadata(self) -> None:
        # C3.T03: Metadata-only history
        code = 'print("A" * 1000); Final = "done"'
        model = StubModelAdapter(code)

        kernel = RlmKernel(self.store, model)
        res = await kernel.run("test")

        self.assertEqual(res, "done")
        self.assertEqual(len(kernel.history), 1)
        frame = list(kernel.history)[0]
        self.assertEqual(frame["len"], 1001)  # 1000 + newline
        self.assertEqual(len(frame["prefix"]), 100)
        self.assertNotIn("A" * 1000, frame["prefix"])

    async def test_rlm_budget_fail(self) -> None:
        # C3.T06: Budget guards max_iters
        model = StubModelAdapter('print("waiting...")')
        budget = cast(
            RlmBudget, {"max_iters": 2, "max_subcalls": 10, "max_parallel": 5, "timeout_s": 10.0}
        )

        with self.assertRaises(RlmKernelError) as cm:
            await run_rlm("test", self.store, model, budget)
        self.assertEqual(cm.exception.error["type"], RlmErrorType.MAX_ITERS_REACHED)

    async def test_rlm_subcall_budget(self) -> None:
        # C3.T06: Budget guards max_subcalls
        code = 'await llm_query("ping"); await llm_query("ping"); Final = "done"'
        model = StubModelAdapter(code)
        budget = cast(
            RlmBudget, {"max_iters": 5, "max_subcalls": 1, "max_parallel": 5, "timeout_s": 10.0}
        )

        with self.assertRaises(RlmKernelError) as cm:
            await run_rlm("test", self.store, model, budget)
        self.assertEqual(cm.exception.error["type"], RlmErrorType.BUDGET_EXCEEDED)

    async def test_rlm_helpers(self) -> None:
        # C3.T02: get/put helpers
        content = "hello world"
        aid = self.store.put_raw(content.encode("utf-8"), kind="raw", mime="text/plain")

        # Code that gets an artifact, modifies it, and puts it back
        # G08: helpers now handle cas_ prefix
        code = f'text = get("cas_{aid}"); Final = put(text.upper(), kind="final")'
        model = StubModelAdapter(code)

        res_aid = await run_rlm("test", self.store, model)
        self.assertEqual(len(res_aid), 68)  # cas_ + 64 hex
        self.assertTrue(res_aid.startswith("cas_"))

        clean_aid = res_aid[4:]
        res_content = self.store.get_bytes(clean_aid).decode("utf-8")
        self.assertEqual(res_content, "HELLO WORLD")

    async def test_rlm_state_vars(self) -> None:
        # C3.T01: State dataclass owns big vars
        code = 'DOCS.append("doc1"); CHUNKS.append("chunk1"); Final = "ok"'
        model = StubModelAdapter(code)

        kernel = RlmKernel(self.store, model)
        res = await kernel.run("test")
        self.assertEqual(res, "ok")

    async def test_rlm_timeout(self) -> None:
        # C3.T06: Budget guards timeout
        # Using a loop that takes some time or just sleep if allowed
        code = "import time\ntime.sleep(0.2)"
        model = StubModelAdapter(code)
        budget = cast(
            RlmBudget, {"max_iters": 5, "max_subcalls": 10, "max_parallel": 5, "timeout_s": 0.1}
        )

        with self.assertRaises(RlmKernelError) as cm:
            await run_rlm("test", self.store, model, budget)
        self.assertEqual(cm.exception.error["type"], RlmErrorType.INTEGRITY)

    async def test_rlm_state_bleed(self) -> None:
        # 06.G04: Reset history and subcall_count per run
        model = StubModelAdapter('await llm_query("ping"); Final = "ok"')
        kernel = RlmKernel(self.store, model)

        await kernel.run("run 1")
        self.assertEqual(len(kernel.history), 1)
        self.assertEqual(kernel.subcall_count, 1)

        await kernel.run("run 2")
        self.assertEqual(len(kernel.history), 1)  # Should NOT be 2
        self.assertEqual(kernel.subcall_count, 1)  # Should NOT be 2

    async def test_rlm_determinism_clock(self) -> None:
        # 06.G06: SequenceClock used for timestamps
        from pirml.clock import SequenceClock

        clock = SequenceClock(start=1000)
        # 64 char hex
        fake_id = "a" * 64
        model = StubModelAdapter(f'Final = "cas_{fake_id}"')
        kernel = RlmKernel(self.store, model, clock=clock)

        await kernel.run("test")

        # Check web_output.json timestamp
        out_file = self.tmp_dir / "web_output.json"
        import json

        with open(out_file) as f:
            data = json.load(f)
            # History log: ts=clock.now() (1000)
            # Final: ts_now = clock.now() (1001)
            # Citations should use 1001
            self.assertTrue(len(data["citations"]) > 0, f"Expected citations in {data}")
            self.assertEqual(data["citations"][0]["retrieved_at"], 1001)
            self.assertEqual(data["citations"][0]["doc_sha256"], fake_id)
