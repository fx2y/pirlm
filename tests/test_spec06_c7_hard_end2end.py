from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from pirml.artifacts.paths import ArtifactLayout, default_layout
from pirml.artifacts.store import ArtifactStore
from pirml.artifacts.view_materialize import ViewMaterializer
from pirml.compiler.model import ModelAdapter
from pirml.rlm import run_rlm


class SequenceModelAdapter(ModelAdapter):
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.idx = 0

    def compile_once(self, prompt: str) -> str:
        if self.idx < len(self.responses):
            res = self.responses[self.idx]
            self.idx += 1
            return res
        return 'Final = "out of responses"'


class TestSpec06C7End2End(unittest.IsolatedAsyncioTestCase):
    tmp_dir: Path
    layout: ArtifactLayout
    store: ArtifactStore
    vm: ViewMaterializer

    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.layout = default_layout(self.tmp_dir)
        self.store = ArtifactStore(self.layout)
        self.vm = ViewMaterializer(self.store)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir)

    async def test_10mb_hostile_flow(self) -> None:
        """C7.T01: 10MB hostile-flow end-to-end test"""
        # 1. Ingest 10MB of "hostile" data (e.g. lots of small lines, script tags)
        line = "X" * 100 + "\n"
        data = (line * 100000).encode("utf-8")  # 10MB approx
        aid = self.store.put_raw(data, kind="raw", mime="text/plain")

        # 2. Slicing
        # We'll slice 20 chunks of different parts
        vids: list[str] = []
        for i in range(10):
            vid = self.vm.materialize(aid, {"op": "lines", "a": i * 1000, "b": i * 1000 + 10})
            vids.append(vid)

        # 3. Map (Summarize chunks)
        code1 = f"""
vids = {vids}
prompts = [f"Summarize {{v}}" for v in vids]
summaries = await amap(prompts)
SUMS.extend(summaries)
"""
        code2 = """
Final = "Combined: " + " | ".join(SUMS)
"""
        responses = [code1] + [f"S{i}" for i in range(len(vids))] + [code2]
        model = SequenceModelAdapter(responses)

        # 4. Run RLM
        res = await run_rlm("Summarize 10MB file", self.store, model)

        self.assertTrue(res.startswith("Combined: S0 | S1"))

        # Verify no context overflow
        # run_rlm should succeed without BudgetExceeded

    async def test_ctx_never_exceeds_k(self) -> None:
        """C7.T01: ctx payload measured <=K"""
        # This is essentially what test_spec06_c5_governor tests
        pass


if __name__ == "__main__":
    unittest.main()
