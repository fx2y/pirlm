from __future__ import annotations

import json
import unittest
from pathlib import Path

from pirml.toolsearch.loader import load_catalog, load_selected
from pirml.toolsearch.render import render_selected_tools
from pirml.toolsearch.search import search_tools


class TestToolSearchGolden(unittest.TestCase):
    def setUp(self):
        self.fixtures_dir = Path("tests/fixtures/toolsearch/catalog")
        self.golden_dir = Path("tests/golden/toolsearch")
        self.golden_dir.mkdir(parents=True, exist_ok=True)
        self.catalog = load_catalog(self.fixtures_dir)

    def test_search_ranking_golden(self):
        queries = ["list files", "read content", "echo hello", "nonexistent"]
        results = {q: search_tools(self.catalog, q) for q in queries}
        golden_path = self.golden_dir / "search_ranking.json"

        # Sort keys to ensure byte-stability
        actual_json = json.dumps(results, indent=2, sort_keys=True)

        if not golden_path.exists():
            golden_path.write_text(actual_json)
            self.skipTest(f"Generated golden file: {golden_path}")

        expected_json = golden_path.read_text()
        self.assertEqual(
            actual_json,
            expected_json,
            "Ranking drift detected! Run with --update-golden if expected.",
        )

    def test_prompt_render_golden(self):
        selected_names = ["svc.read_file", "core.echo"]
        selected_tools = load_selected(selected_names, self.fixtures_dir)
        rendered = render_selected_tools(selected_tools)
        golden_path = self.golden_dir / "prompt_render.json"

        actual_json = json.dumps(rendered, indent=2, sort_keys=True)

        if not golden_path.exists():
            golden_path.write_text(actual_json)
            self.skipTest(f"Generated golden file: {golden_path}")

        expected_json = golden_path.read_text()
        self.assertEqual(
            actual_json,
            expected_json,
            "Render drift detected! Run with --update-golden if expected.",
        )


if __name__ == "__main__":
    unittest.main()
