from __future__ import annotations
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from pirml.artifacts.store import ArtifactStore
from pirml.compiler.model import ModelAdapter
from pirml.rlm import RlmBudget, RlmKernel, run_rlm
from pirml.web.etl import chunk_views, pack_batches

class StressModelAdapter(ModelAdapter):
    def __init__(self) -> None:
        self.root_calls = 0
    def compile_once(self, prompt: str) -> str:
        # If it's the root prompt (first time or following iters)
        if "Recursive map-reduce" in prompt:
            self.root_calls += 1
            if self.root_calls == 1:
                return """
view_texts = [get(vid) for vid in DOCS]
chunks = chunk_views(view_texts, max_chars=12000)
batches = pack_batches(chunks, max_chars=24000)
prompts = [f"Summarize: {b}" for b in batches]
summaries = await amap(prompts)
SUMS.extend(summaries)
"""
            else:
                return 'Final = "Summary of 1M chars"'
        
        # If it's a subcall (summarizing a batch)
        if "Summarize:" in prompt:
            return "Batch summary"
        
        return 'Final = "Unexpected prompt"'

class TestRlmStress(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())
        from pirml.artifacts.paths import default_layout
        self.store = ArtifactStore(default_layout(self.tmp_dir))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir)

    async def test_1m_char_map_reduce(self) -> None:
        # C4.T09: 1M-char synthetic workload
        # Create a large artifact
        large_text = "A" * 1_000_000
        aid = self.store.put_raw(large_text.encode("utf-8"), kind="raw", mime="text/plain")
        
        # Manually create a view for the whole thing
        from pirml.artifacts.view_materialize import ViewMaterializer
        vm = ViewMaterializer(self.store)
        vid = vm.materialize(aid, {"op": "lines", "a": 0, "b": 1000000}) # approximate
        
        model = StressModelAdapter()
        kernel = RlmKernel(self.store, model)
        # Inject the view into DOCS
        from pirml.rlm.kernel import RlmState
        state = RlmState(P="Recursive map-reduce for large text", DOCS=[vid])
        
        # Need to fix RlmKernel to allow passing initial state or just use a helper
        # For now, I'll just use run and hope the LLM code can find it
        # Actually, let's just use run_rlm and let the model handle discovery?
        # But DOCS is empty by default.
        
        # I'll update RlmKernel.run to accept initial state overrides if needed, 
        # or just make the model find the artifact.
        
        code1 = f"""
DOCS.append("{vid}")
view_texts = [get(v) for v in DOCS]
chunks = chunk_views(view_texts, max_chars=50000)
batches = pack_batches(chunks, max_chars=100000)
prompts = [f"Summarize: {{b}}" for b in batches]
summaries = await amap(prompts)
SUMS.extend(summaries)
for s in summaries:
    put(s, kind="summary", parents=["{vid}"])
"""
        code2 = """
Final = f"Reduced summary of {len(SUMS)} parts"
"""
        # 1M chars / 100k batches => ~10 batches
        
        model_responses = [code1] + [f"Summary part {i}" for i in range(10)] + [code2]
        from tests.test_spec06_c4_patterns import SequenceModelAdapter
        model = SequenceModelAdapter(model_responses)
        
        res = await run_rlm("Recursive map-reduce for large text", self.store, model)
        print(f"RESULT: {res}")
        self.assertEqual(res, "Reduced summary of 10 parts")
        self.assertTrue(len(self.store.find_by_kind("summary")) >= 10)

if __name__ == "__main__":
    unittest.main()
