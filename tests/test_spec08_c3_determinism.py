from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pirml.web.search import rank_and_diversify
from pirml.web.trace import WebTracer
from pirml.web.types import SerpRow


class Spec08C3DeterminismTests(unittest.TestCase):
    def test_no_time_time_calls(self) -> None:
        content = Path("pirml/web/search.py").read_text(encoding="utf-8")
        self.assertNotIn("time.time(", content)

    def test_metrics_byte_stable_x3(self) -> None:
        frames: list[str] = []
        for _ in range(3):
            tracer = WebTracer(start_ts=1_700_000_000)
            tracer.emit("metrics", bytes_into_model=10, tokens_in=1, tokens_out=2)
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "trace.ndjson"
                tracer.write_to(out)
                frames.append(out.read_text(encoding="utf-8"))
        self.assertEqual(frames[0], frames[1])
        self.assertEqual(frames[1], frames[2])

    def test_search_metrics_byte_stable_x3(self) -> None:
        rows: list[SerpRow] = [
            {
                "url": "https://a.example/1",
                "title": "t1",
                "snippet": "s1",
                "rank": 1,
                "source": "x",
            },
            {
                "url": "https://a.example/2",
                "title": "t2",
                "snippet": "s2",
                "rank": 2,
                "source": "x",
            },
        ]
        all_runs: list[str] = []
        for _ in range(3):
            tracer = WebTracer(start_ts=1_700_000_000)
            rank_and_diversify(rows, k=2, per_domain_cap=2, tracer=tracer)
            all_runs.append(json.dumps(tracer.get_frames(), sort_keys=True, separators=(",", ":")))
        self.assertEqual(all_runs[0], all_runs[1])
        self.assertEqual(all_runs[1], all_runs[2])


if __name__ == "__main__":
    unittest.main()
