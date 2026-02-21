from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from pirml.artifacts.store import ArtifactStore
from pirml.compiler.model import StubModelAdapter
from pirml.rlm import RlmKernel
from pirml.rlm.recursion import amap_recursive


class TestRecursionMap(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())
        from pirml.artifacts.paths import default_layout

        self.store = ArtifactStore(default_layout(self.tmp_dir))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir)

    async def test_order_stable_under_parallelism(self) -> None:
        """I17: Parallel merge order deterministic under bounded gather"""

        class IndexedModel(StubModelAdapter):
            def compile_once(self, prompt: str) -> str:
                # Artificial delay: prompts 0-4 are slow, 5-9 are fast.
                # Bounded parallel (5) will start 0-4.
                # If they were NOT ordered, 5-9 would finish and appear first.
                import time

                try:
                    idx = int(prompt.split()[-1])
                except (IndexError, ValueError):
                    idx = 0
                if idx < 5:
                    time.sleep(0.1)
                return f"result {idx}"

        model = IndexedModel()
        kernel = RlmKernel(
            self.store,
            model,
            budget={"max_parallel": 5, "max_iters": 10, "max_subcalls": 100, "timeout_s": 30.0},
        )

        prompts = [f"prompt {i}" for i in range(10)]
        results = await amap_recursive(kernel, prompts)

        expected = [f"result {i}" for i in range(10)]
        self.assertEqual(results, expected)

    async def test_over_parallel_cap_bounded(self) -> None:
        """Verify that concurrency is actually bounded by the semaphore."""
        active_count = 0
        max_active = 0

        class TrackingModel(StubModelAdapter):
            def compile_once(self, prompt: str) -> str:
                nonlocal active_count, max_active
                active_count += 1
                max_active = max(max_active, active_count)
                import time

                time.sleep(0.05)
                active_count -= 1
                return "done"

        model = TrackingModel()
        # Cap at 2
        kernel = RlmKernel(
            self.store,
            model,
            budget={"max_parallel": 2, "max_iters": 10, "max_subcalls": 100, "timeout_s": 30.0},
        )

        prompts = ["p"] * 10
        await amap_recursive(kernel, prompts)

        self.assertEqual(max_active, 2)


if __name__ == "__main__":
    unittest.main()
