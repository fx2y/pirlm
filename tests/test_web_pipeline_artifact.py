from __future__ import annotations

import hashlib
import json
import shutil
import unittest
from pathlib import Path
from typing import TYPE_CHECKING

from pirml.artifacts import ArtifactStore, default_layout
from pirml.clock import SequenceClock
from pirml.web.fetch import FixtureDocFetcher
from pirml.web.pipeline import WebPipeline, WebPlan

if TYPE_CHECKING:
    from pirml.web.trace import WebTracer
    from pirml.web.types import SerpRow


class MockProvider:
    async def search(self, query: str, tracer: WebTracer | None = None) -> list[SerpRow]:
        return [
            {
                "url": "https://example.com/1",
                "title": "T1",
                "snippet": "S1",
                "rank": 1,
                "source": "test",
            }
        ]


class TestWebPipelineArtifact(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp_dir = Path("out/test_web_pipeline_artifact")
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        self.tmp_dir.mkdir(parents=True)

        self.layout = default_layout(self.tmp_dir)
        self.store = ArtifactStore(self.layout)

        # Create a dummy fixture for fetcher
        self.fixture_path = self.tmp_dir / "fixtures.json"
        body_file = "body1.html"
        body_content = "<html><body>This is a long enough body text to pass the boilerplate filter. It has more than 20 characters.</body></html>"
        (self.tmp_dir / body_file).write_text(body_content)
        self.fixture_path.write_text(
            json.dumps(
                {
                    "responses": [
                        {
                            "url": "https://example.com/1",
                            "final_url": "https://example.com/1",
                            "status": 200,
                            "headers": {"content-type": "text/html"},
                            "content_type": "text/html",
                            "encoding_guess": "utf-8",
                            "body_file": body_file,
                        }
                    ]
                }
            )
        )
        self.fetcher = FixtureDocFetcher(self.fixture_path)
        self.clock = SequenceClock.from_env()
        self.pipeline = WebPipeline(
            provider=MockProvider(),  # type: ignore
            fetcher=self.fetcher,
            clock=self.clock,
            artifact_store=self.store,
            trace_dir=self.tmp_dir,
        )

    async def test_run_ingests_artifacts(self) -> None:
        plan = WebPlan(provider="mock", cache="none")
        result = await self.pipeline.run("test query", plan)

        self.assertIn("long", result["answer"].lower())

        # Check if artifact was stored
        body = "<html><body>This is a long enough body text to pass the boilerplate filter. It has more than 20 characters.</body></html>"
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()

        meta = self.store.get_meta(sha)
        self.assertIsNotNone(meta)
        if meta:
            self.assertEqual(meta["id"], sha)
            self.assertEqual(meta["kind"], "raw")


if __name__ == "__main__":
    unittest.main()
