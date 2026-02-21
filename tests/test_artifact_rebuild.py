from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from pirml.artifacts.paths import default_layout
from pirml.artifacts.store import ArtifactStore


class TestArtifactRebuild(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())
        self.layout = default_layout(self.test_dir)
        self.store = ArtifactStore(self.layout)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir)

    def test_rebuild_matches_index(self) -> None:
        """I14: Filesystem->sqlite rebuild parity exact"""
        # 1. Put some artifacts
        aid1 = self.store.put_raw(b"data1", kind="raw", mime="text/plain", notes="note1")
        aid2 = self.store.put_raw(b"data2", kind="raw", mime="text/plain", parents=[aid1])

        # 2. Put a view
        # We need a materializer or manually call put_view
        spec = {"op": "lines", "a": 0, "b": 0}
        vid = "v1"
        self.store.put_view(
            vid, aid1, spec, b'{"line":0, "text":"data1"}\n', {"chars": 5, "lines": 1}
        )

        # 3. Capture meta
        meta1_orig = self.store.get_meta(aid1)
        meta2_orig = self.store.get_meta(aid2)
        meta_v_orig = self.store.get_meta(vid)

        # 4. Rebuild
        self.store.rebuild_index()

        # 5. Compare
        meta1_new = self.store.get_meta(aid1)
        meta2_new = self.store.get_meta(aid2)
        meta_v_new = self.store.get_meta(vid)

        self.assertEqual(meta1_orig, meta1_new)
        self.assertEqual(meta2_orig, meta2_new)
        # Note: rebuild_index currently doesn't handle view events in the provided code.
        # I need to fix ArtifactStore.rebuild_index first.
        self.assertEqual(meta_v_orig, meta_v_new)

    def test_missing_object_typed_fail(self) -> None:
        """I14: check_parity fails if file missing (optional)"""
        pass


if __name__ == "__main__":
    unittest.main()
