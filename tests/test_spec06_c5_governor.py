from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pirml.artifacts.store import ArtifactStore
from pirml.compiler.model import ModelAdapter
from pirml.rlm import RlmKernel, RlmState
from pirml.rlm.governor import apply_cohesion_rule, est_tokens, pack_ctx


class TestGovernor(unittest.TestCase):
    def test_token_estimation(self) -> None:
        # C5.T00: Deterministic and monotonic
        self.assertEqual(est_tokens(""), 0)
        self.assertGreater(est_tokens("abc"), 0)
        self.assertGreaterEqual(est_tokens("abcd"), est_tokens("abc"))
        # Monotonicity test
        last = 0
        for i in range(1, 100):
            curr = est_tokens("a" * i)
            self.assertGreaterEqual(curr, last)
            last = curr

    def test_pack_ctx_selection(self) -> None:
        # C5.T02: relevance/cost selection
        goal = "find apple"
        items = [
            {"id": "a", "text": "This is an apple", "kind": "var"},  # High relevance
            {
                "id": "b",
                "text": "Banana is yellow. " * 100,
                "kind": "var",
            },  # Low relevance, high cost
            {"id": "c", "text": "apple", "kind": "var"},  # High relevance, low cost
        ]
        # K cap very small
        packed = pack_ctx(goal, items, k_limit=10)
        # 'c' should be first (high rel, low cost)
        # 'a' should be second
        # 'b' should be excluded if budget is tight
        self.assertIn("c", packed)
        self.assertIn("a", packed)
        self.assertNotIn("b", packed)

    def test_cohesion_rule(self) -> None:
        # C5.T03: call/result pairs
        items = [
            {"id": "c1", "text": "call 1", "ev": "call"},
            {"id": "r1", "text": "result 1", "ev": "result"},
            {"id": "c2", "text": "call 2", "ev": "call"},
            {"id": "r2", "text": "result 2", "ev": "result"},
        ]
        # Only r2 is selected initially
        packed_ids = ["r2"]
        final_ids = apply_cohesion_rule(packed_ids, items)
        # c2 should be added because r2 is packed
        self.assertIn("c2", final_ids)
        self.assertIn("r2", final_ids)
        self.assertNotIn("c1", final_ids)


class TestKernelGovernor(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())
        from pirml.artifacts.paths import default_layout

        self.store = ArtifactStore(default_layout(self.tmp_dir))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir)

    async def test_bulk_off_ctx(self) -> None:
        # C5.T04
        class CapturingModel(ModelAdapter):
            def __init__(self) -> None:
                self.last_prompt = ""

            def compile_once(self, prompt: str) -> str:
                self.last_prompt = prompt
                return "Final = 'done'"

        model = CapturingModel()
        kernel = RlmKernel(self.store, model)

        # Inject huge list into BUF
        state = RlmState(P="test")
        state.BUF = ["data" * 1000] * 100  # Huge bulk

        prompt = kernel.build_prompt(state)
        # Verify prompt doesn't contain the full data 100 times
        self.assertLess(len(prompt), 50000)
        self.assertIn("BulkVar BUF", prompt)
        self.assertIn("BUF[0]", prompt)
        # Ensure it doesn't contain the full huge string repeated many times
        self.assertLess(prompt.count("data" * 1000), 1)

    async def test_web_output_projection(self) -> None:
        # C5.T05, T07
        class SimpleModel(ModelAdapter):
            def compile_once(self, prompt: str) -> str:
                return "Final = 'answer'"

        model = SimpleModel()
        kernel = RlmKernel(self.store, model)
        await kernel.run("what is up")

        out_file = self.tmp_dir / "web_output.json"
        self.assertTrue(out_file.exists())
        with open(out_file) as f:
            data = json.load(f)
            self.assertEqual(data["output"]["answer"], "answer")
            self.assertIn("citations", data["output"])
            self.assertTrue(data["ok"])


if __name__ == "__main__":
    unittest.main()
