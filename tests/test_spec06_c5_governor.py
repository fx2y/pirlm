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

        from pirml.rlm.governor import build_rlm_prompt

        prompt = build_rlm_prompt(state, kernel.history, kernel.emit_pi_pointers)
        # Verify prompt doesn't contain the full data 100 times
        self.assertLess(len(prompt), 50000)
        self.assertIn("BulkVar BUF", prompt)
        self.assertIn("BUF[0]", prompt)
        # Ensure it doesn't contain the full huge string repeated many times
        self.assertLess(prompt.count("data" * 1000), 1)

    async def test_web_output_projection(self) -> None:
        # C5.T05, T07, G07
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
            self.assertEqual(data["answer"], "answer")
            self.assertIn("citations", data)
            self.assertIn("trace_ptr", data)

    def test_governor_hard_cap_enforcement(self) -> None:
        # 06.G05: Hard cap must hold even after cohesion
        items = [
            {"id": "c1", "text": "A" * 3000, "ev": "call"},
            {"id": "r1", "text": "B" * 3000, "ev": "result"},
            {"id": "c2", "text": "C" * 3000, "ev": "call"},
            {"id": "r2", "text": "D" * 3000, "ev": "result"},
        ]
        # Total cost is ~4000 tokens (1000 per 3000 chars)
        # Budget = 2500 tokens
        # Scenario: r1 and r2 are selected (2000 tokens)
        # Cohesion adds c1 and c2 (total 4000 tokens) -> MUST drop to fit in 2500
        final = apply_cohesion_rule(["r1", "r2"], items, k_limit=2500)

        from pirml.rlm.governor import est_tokens

        total_cost = sum(est_tokens(it["text"]) for it in items if it["id"] in final)
        self.assertLessEqual(total_cost, 2500)
        self.assertGreater(len(final), 0)

    def test_critical_p_retention(self) -> None:
        # 06.G05: Mandatory 'P' retention
        items = [
            {"id": "p", "text": "Goal: solve it", "critical": True},
            {"id": "huge", "text": "X" * 30000},  # Exceeds budget alone
        ]
        packed = pack_ctx("", items, k_limit=1000)
        self.assertIn("p", packed)
        self.assertNotIn("huge", packed)


if __name__ == "__main__":
    unittest.main()
