from __future__ import annotations
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from pirml.artifacts.store import ArtifactStore
from pirml.compiler.model import ModelAdapter
from pirml.rlm import RlmBudget, RlmKernel, run_rlm

import threading

class SequenceModelAdapter(ModelAdapter):
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.idx = 0
        self.lock = threading.Lock()
    def compile_once(self, prompt: str) -> str:
        with self.lock:
            if self.idx < len(self.responses):
                res = self.responses[self.idx]
                self.idx += 1
                return res
            return 'Final = "out of responses"'

class TestRlmPatterns(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())
        from pirml.artifacts.paths import default_layout
        self.store = ArtifactStore(default_layout(self.tmp_dir))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir)

    async def test_map_reduce_pattern(self) -> None:
        # C4.T02, T03, T04
        # 1. Map: process 3 chunks in parallel
        # 2. Reduce: combine results
        code1 = """
chunks = ["C1", "C2", "C3"]
prompts = [f"Summarize {c}" for c in chunks]
results = await amap(prompts)
SUMS.extend(results)
"""
        code2 = """
Final = " | ".join(SUMS)
"""
        model = SequenceModelAdapter([code1, code2])
        # We need to mock the llm_query behavior too. 
        # But llm_query uses model.compile_once too!
        # So we need many responses.
        # 1. Root call -> code1
        # 2. amap -> 3 x llm_query -> 3 responses
        # 3. Root call -> code2
        
        responses = [
            code1,
            "S1", "S2", "S3", # results of amap
            code2
        ]
        model = SequenceModelAdapter(responses)
        
        res = await run_rlm("map reduce test", self.store, model)
        self.assertEqual(res, "S1 | S2 | S3")

    async def test_targeted_retrieval(self) -> None:
        # C4.T05
        # LLM uses regex to find a specific part then queries it
        aid = self.store.put_raw(b"Secret key: 12345\nOther stuff...", kind="raw", mime="text/plain")
        
        code1 = f"""
import re
text = get("{aid}")
match = re.search(r"Secret key: (\d+)", text)
if match:
    # Shortcut!
    Final = match.group(1)
else:
    Final = "not found"
"""
        model = SequenceModelAdapter([code1])
        res = await run_rlm("targeted test", self.store, model)
        self.assertEqual(res, "12345")

    async def test_subcall_governor_enforcement(self) -> None:
        # C4.T07
        code = """
for i in range(5):
    await llm_query(f"q{i}")
Final = "done"
"""
        budget = cast(RlmBudget, {
            "max_iters": 10,
            "max_subcalls": 3, # Hard limit
            "max_parallel": 5,
            "timeout_s": 10.0
        })
        model = SequenceModelAdapter([code, "r0", "r1", "r2", "r3"])
        
        from pirml.rlm import RlmKernelError, RlmErrorType
        with self.assertRaises(RlmKernelError) as cm:
            await run_rlm("governor test", self.store, model, budget)
        self.assertEqual(cm.exception.error["type"], RlmErrorType.BUDGET_EXCEEDED)

    async def test_progressive_deepening(self) -> None:
        # C4.T06: Coarse summary -> reslice hotspot
        aid = self.store.put_raw(b"Page 1 content\n[HOTSPOT: find details here]\nPage 2 content", kind="raw", mime="text/plain")
        
        # 1. Look for hotspot
        code1 = f"""
text = get("{aid}")
if "HOTSPOT" in text:
    BUF.append("found hotspot")
    # In real world, we would slice the hotspot part
    # Here we just put a finding
    put("found detailed info", kind="summary", parents=["{aid}"])
Final = "done"
"""
        model = SequenceModelAdapter([code1])
        await run_rlm("deepening test", self.store, model)
        
        # Verify parent link exists in index
        meta = self.store.index.get_meta(aid)
        # Find summary artifact
        summary_ids = self.store.find_by_kind("summary")
        self.assertTrue(len(summary_ids) > 0)
        summary_id = summary_ids[0]
        parents = self.store.resolve_parents(summary_id)
        self.assertIn(aid, parents)

    async def test_parent_links(self) -> None:
        # C4.T03
        aid1 = self.store.put_raw(b"parent1", kind="raw", mime="text/plain")
        aid2 = self.store.put_raw(b"parent2", kind="raw", mime="text/plain")
        
        code = f"""
put("summary", kind="summary", parents=["{aid1}", "{aid2}"])
Final = "ok"
"""
        model = SequenceModelAdapter([code])
        await run_rlm("parent link test", self.store, model)
        
        # Find the summary
        summary_ids = self.store.find_by_kind("summary")
        summary_id = [sid for sid in summary_ids if self.store.get_bytes(sid) == b"summary"][0]
        parents = self.store.resolve_parents(summary_id)
        self.assertIn(aid1, parents)
        self.assertIn(aid2, parents)

if __name__ == "__main__":
    unittest.main()
