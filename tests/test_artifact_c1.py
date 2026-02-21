from __future__ import annotations

import hashlib
import json
import shutil
import unittest
from pathlib import Path

from pirml.artifacts import ArtifactKind, ArtifactStore, default_layout


class TestArtifactC1(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path("out/test_artifact_c1")
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        self.tmp_dir.mkdir(parents=True)
        self.layout = default_layout(self.tmp_dir)
        self.store = ArtifactStore(self.layout)

    def test_put_raw_and_get(self) -> None:
        data = b"hello world"
        aid = self.store.put_raw(data, kind=ArtifactKind.RAW, mime="text/plain")

        # Verify dedupe
        aid2 = self.store.put_raw(data, kind=ArtifactKind.RAW, mime="text/plain")
        self.assertEqual(aid, aid2)

        # Verify get_bytes
        fetched = self.store.get_bytes(aid)
        self.assertEqual(data, fetched)

        # Verify meta
        meta = self.store.get_meta(aid)
        self.assertIsNotNone(meta)
        if meta:
            self.assertEqual(meta["id"], aid)
            self.assertEqual(meta["kind"], "raw")
            self.assertEqual(meta["bytes"], len(data))

    def test_put_json_and_get(self) -> None:
        obj = {"a": 1, "b": [2, 3]}
        aid = self.store.put_json(obj, kind=ArtifactKind.FINAL)

        fetched_bytes = self.store.get_bytes(aid)
        fetched_obj = json.loads(fetched_bytes)
        self.assertEqual(obj, fetched_obj)

    def test_lineage(self) -> None:
        aid1 = self.store.put_raw(b"parent", kind=ArtifactKind.RAW, mime="text/plain")
        aid2 = self.store.put_raw(
            b"child", kind=ArtifactKind.SUMMARY, mime="text/plain", parents=[aid1]
        )

        parents = self.store.resolve_parents(aid2)
        self.assertEqual(parents, [aid1])

    def test_rebuild_index(self) -> None:
        aid = self.store.put_raw(b"data", kind=ArtifactKind.RAW, mime="text/plain")

        # Delete index and rebuild
        self.store.rebuild_index()

        meta = self.store.get_meta(aid)
        self.assertIsNotNone(meta)
        if meta:
            self.assertEqual(meta["id"], aid)

    def test_cas_path_sharding(self) -> None:
        data = b"sharded"
        aid = self.store.put_raw(data, kind=ArtifactKind.RAW, mime="text/plain")

        # art/obj/aa/bb/sha...
        expected_path = self.layout.obj_dir / aid[:2] / aid[2:4] / aid
        self.assertTrue(expected_path.exists())

    def test_trace_append(self) -> None:
        self.store.put_raw(b"t1", kind=ArtifactKind.RAW, mime="text/plain")
        self.store.put_raw(b"t2", kind=ArtifactKind.RAW, mime="text/plain")

        trace_content = self.layout.trace_path.read_text().splitlines()
        self.assertEqual(len(trace_content), 2)

        frame1 = json.loads(trace_content[0])
        self.assertEqual(frame1["seq"], 1)
        self.assertEqual(frame1["ev"], "put")

    def test_ingest_10mb(self) -> None:
        """C1.T10: 10MB ingest test"""
        data = b"x" * (10 * 1024 * 1024)
        aid = self.store.put_raw(data, kind=ArtifactKind.RAW, mime="application/octet-stream")

        meta = self.store.get_meta(aid)
        self.assertIsNotNone(meta)
        if meta:
            self.assertEqual(meta["bytes"], len(data))

        fetched = self.store.get_bytes(aid)
        self.assertEqual(len(fetched), len(data))
        self.assertEqual(hashlib.sha256(data).hexdigest(), aid)


if __name__ == "__main__":
    unittest.main()
