from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from pirml.artifacts.errors import ArtifactErrorType, ArtifactPathError
from pirml.artifacts.paths import default_layout
from pirml.artifacts.store import ArtifactStore
from pirml.artifacts.view_dsl import SliceSpec, derive_view_id
from pirml.artifacts.view_materialize import ViewMaterializer


class TestViewMaterialize(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.layout = default_layout(self.tmp_dir)
        self.store = ArtifactStore(self.layout)
        self.vm = ViewMaterializer(self.store)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir)

    def test_deterministic_view_id(self) -> None:
        # C2.T01: same artifact+spec => identical view_id
        aid = "a" * 64
        spec = cast(SliceSpec, {"op": "lines", "a": 1, "b": 10})
        vid1 = derive_view_id(aid, spec)
        vid2 = derive_view_id(aid, spec)
        self.assertEqual(vid1, vid2)

        # Field order should not matter due to canonical_json
        spec2 = cast(SliceSpec, {"b": 10, "op": "lines", "a": 1})
        vid3 = derive_view_id(aid, spec2)
        self.assertEqual(vid1, vid3)

    def test_slice_lines(self) -> None:
        # C2.T02: lines slice
        content = """line0
line1
line2
line3
line4
"""
        aid = self.store.put_raw(content.encode("utf-8"), kind="raw", mime="text/plain")

        spec = cast(SliceSpec, {"op": "lines", "a": 1, "b": 2})
        vid = self.vm.materialize(aid, spec)

        view_path = self.layout.views_dir / f"{vid}.ndjson"
        self.assertTrue(view_path.exists())

        view_rows = [line for line in view_path.read_text().splitlines() if line]
        self.assertEqual(len(view_rows), 2)
        self.assertIn('"line":1', view_rows[0])
        self.assertIn('"text":"line1"', view_rows[0])
        self.assertIn('"line":2', view_rows[1])
        self.assertIn('"text":"line2"', view_rows[1])

    def test_slice_regex(self) -> None:
        # C2.T02: regex slice
        content = """apple
banana
cherry
apple pie
"""
        aid = self.store.put_raw(content.encode("utf-8"), kind="raw", mime="text/plain")

        spec = cast(SliceSpec, {"op": "regex", "pat": "apple", "max_hits": 10})
        vid = self.vm.materialize(aid, spec)

        view_path = self.layout.views_dir / f"{vid}.ndjson"
        view_rows = [line for line in view_path.read_text().splitlines() if line]
        self.assertEqual(len(view_rows), 2)
        self.assertIn('"text":"apple"', view_rows[0])
        self.assertIn('"text":"apple pie"', view_rows[1])

    def test_slice_bytes(self) -> None:
        # C2.T02: bytes slice
        content = b"0123456789"
        aid = self.store.put_raw(content, kind="raw", mime="application/octet-stream")

        spec = cast(SliceSpec, {"op": "bytes", "offset": 2, "limit": 4})
        vid = self.vm.materialize(aid, spec)

        view_path = self.layout.views_dir / f"{vid}.ndjson"
        view_rows = [line for line in view_path.read_text().splitlines() if line]
        self.assertEqual(len(view_rows), 1)
        self.assertIn('"text":"2345"', view_rows[0])
        self.assertIn('"offset":2', view_rows[0])
        self.assertIn('"bytes":4', view_rows[0])

    def test_html_text(self) -> None:
        # C2.T03: html_text op
        html = "<html><script>alert(1)</script><body><h1>Title</h1><p>Text</p></body></html>"
        aid = self.store.put_raw(html.encode("utf-8"), kind="raw", mime="text/html")

        spec = cast(SliceSpec, {"op": "html_text"})
        vid = self.vm.materialize(aid, spec)

        view_path = self.layout.views_dir / f"{vid}.ndjson"
        view_rows = [line for line in view_path.read_text().splitlines() if line]
        # Should drop script, and find Title and Text
        texts = [row for row in view_rows if "Title" in row or "Text" in row]
        self.assertEqual(len(texts), 2)
        self.assertNotIn("alert", view_path.read_text())

    def test_unsupported_op(self) -> None:
        # C2.T00: unknown op typed-fail
        aid = self.store.put_raw(b"test", kind="raw", mime="text/plain")
        spec = cast(Any, {"op": "invalid_op"})
        with self.assertRaises(ArtifactPathError) as cm:
            self.vm.materialize(aid, spec)
        self.assertEqual(cm.exception.error["type"], ArtifactErrorType.VIEW_OP_UNSUPPORTED)

    def test_post_ops(self) -> None:
        # C2.T07: Integrate ETL ops
        content = """apple
apple
banana
cherry
"""
        aid = self.store.put_raw(content.encode("utf-8"), kind="raw", mime="text/plain")

        # Join/Dedup post op
        spec = cast(
            SliceSpec, {"op": "lines", "a": 0, "b": 3, "post": [{"op": "dedup", "params": {}}]}
        )
        vid = self.vm.materialize(aid, spec)

        view_path = self.layout.views_dir / f"{vid}.ndjson"
        view_rows = [line for line in view_path.read_text().splitlines() if line]
        # apple is repeated, should be deduped
        self.assertEqual(len(view_rows), 3)

    def test_view_linking(self) -> None:
        # C2.T06: Link into index and trace
        aid = self.store.put_raw(b"test", kind="raw", mime="text/plain")
        spec = cast(SliceSpec, {"op": "lines", "a": 0, "b": 0})
        vid = self.vm.materialize(aid, spec)

        # Check index
        meta = self.store.get_meta(vid)
        self.assertIsNotNone(meta)
        if meta:
            self.assertEqual(meta["kind"], "slice")
            self.assertEqual(meta["parents"], [aid])
            src = meta["src"]
            self.assertIn("stats", src)
            stats = src.get("stats")
            self.assertIsNotNone(stats)
            if stats:
                self.assertIn("chars", stats)

        # Check trace
        trace_text = self.layout.trace_path.read_text()
        self.assertIn('"ev":"view"', trace_text)
        self.assertIn(f'"vid":"{vid}"', trace_text)
        self.assertIn(f'"aid":"{aid}"', trace_text)

    def test_schema_lint(self) -> None:
        # C2.T08: Schema lint support for view artifacts
        aid = self.store.put_raw(b"line0\nline1\n", kind="raw", mime="text/plain")
        spec = cast(SliceSpec, {"op": "lines", "a": 0, "b": 1})
        vid = self.vm.materialize(aid, spec)
        view_path = self.layout.views_dir / f"{vid}.ndjson"

        res = subprocess.run(
            [sys.executable, "scripts/schema_lint.py", "--view", str(view_path)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn(f"Verified {view_path}", res.stdout)
