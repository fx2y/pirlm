import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import cast

from pirml.contracts.schemas import ToolManifest
from pirml.toolsearch.loader import HydrationError, hydrate_tools, load_selected
from pirml.toolsearch.render import RenderError, enforce_client_search_mode, render_selected_tools


class TestHydrateRender(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tools_dir = Path(self.tmpdir) / "tools"
        self.tools_dir.mkdir()

        self.tool1 = cast(
            ToolManifest,
            {
                "name": "svc.tool1",
                "description": "Tool 1 description. Sentence two. Sentence three with when NOT to use.",
                "input_schema": {"type": "object", "properties": {"arg": {"type": "integer"}}},
                "input_examples": [{"arg": 1}],
                "defer_loading": False,
                "tags": ["tag1"],
            },
        )
        self.tool2 = cast(
            ToolManifest,
            {
                "name": "svc.tool2",
                "description": "Tool 2 description. Sentence two. Sentence three with avoid token.",
                "input_schema": {"type": "object"},
                "defer_loading": True,
            },
        )

        with open(self.tools_dir / "svc.tool1.json", "w") as f:
            json.dump(self.tool1, f)
        with open(self.tools_dir / "svc.tool2.json", "w") as f:
            json.dump(self.tool2, f)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_hydrate_tools_ok(self):
        catalog = {"svc.tool1": self.tool1, "svc.tool2": self.tool2}
        hydrated = hydrate_tools(["svc.tool2", "svc.tool1"], catalog)
        self.assertEqual(len(hydrated), 2)
        self.assertEqual(hydrated[0]["name"], "svc.tool2")
        self.assertEqual(hydrated[1]["name"], "svc.tool1")

    def test_hydrate_tools_missing(self):
        catalog = {"svc.tool1": self.tool1}
        with self.assertRaises(HydrationError) as cm:
            hydrate_tools(["svc.tool1", "svc.tool_missing"], catalog)
        self.assertEqual(cm.exception.type, "missing_ref")
        self.assertIn("svc.tool_missing", cm.exception.msg)

    def test_load_selected_ok(self):
        selected = load_selected(["svc.tool1"], self.tools_dir)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["name"], "svc.tool1")

    def test_load_selected_missing(self):
        with self.assertRaises(HydrationError) as cm:
            load_selected(["svc.tool_missing"], self.tools_dir)
        self.assertEqual(cm.exception.type, "missing_ref")

    def test_load_selected_inconsistent_name(self):
        # Create a file with mismatched name
        with open(self.tools_dir / "mismatch.json", "w") as f:
            json.dump(self.tool1, f)  # tool1 has name "svc.tool1"

        with self.assertRaises(HydrationError) as cm:
            load_selected(["mismatch"], self.tools_dir)
        self.assertEqual(cm.exception.type, "inconsistent_name")

    def test_render_selected_tools(self):
        tools = [self.tool1, self.tool2]
        rendered = render_selected_tools(tools)
        self.assertEqual(len(rendered), 2)

        # Tool 1 should have 4 specified fields
        self.assertEqual(rendered[0]["name"], "svc.tool1")
        self.assertEqual(rendered[0]["description"], self.tool1["description"])
        self.assertEqual(rendered[0]["input_schema"], self.tool1["input_schema"])
        self.assertEqual(rendered[0]["input_examples"], self.tool1["input_examples"])
        self.assertNotIn("tags", rendered[0])
        self.assertNotIn("defer_loading", rendered[0])

        # Tool 2 should have 3 specified fields (no examples)
        self.assertEqual(rendered[1]["name"], "svc.tool2")
        self.assertNotIn("input_examples", rendered[1])

    def test_enforce_client_search_mode_fail(self):
        # tool1 has examples, so server_side_search=True should fail
        with self.assertRaises(RenderError) as cm:
            enforce_client_search_mode(True, [self.tool1])
        self.assertEqual(cm.exception.type, "invalid_policy_combo")

    def test_enforce_client_search_mode_ok(self):
        # tool2 has no examples, so server_side_search=True is OK
        enforce_client_search_mode(True, [self.tool2])
        # server_side_search=False is always OK even with examples
        enforce_client_search_mode(False, [self.tool1])
