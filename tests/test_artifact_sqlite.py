from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from pirml.artifacts.index_sqlite import ArtifactsIndex


class TestArtifactSqlite(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())
        self.db_path = self.test_dir / "index.sqlite"
        self.index = ArtifactsIndex(self.db_path)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir)

    def test_schema_has_no_blob_payload(self) -> None:
        """I03: Artifact sqlite stores metadata/paths only, no payload blobs"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(artifacts)")
        columns = cursor.fetchall()
        # column names: id, kind, mime, bytes, sha256, path, ts, src_json, notes
        column_names = [c[1] for c in columns]
        self.assertNotIn("payload", column_names)
        self.assertNotIn("data", column_names)

        # Check types
        for col in columns:
            if col[1] == "bytes" or col[1] == "ts":
                self.assertEqual(col[2].upper(), "INTEGER")
            else:
                self.assertEqual(col[2].upper(), "TEXT")

    def test_lookup_id_to_path(self) -> None:
        """I03: Lookup id to path"""
        from pirml.artifacts.types import ArtifactRecord

        rec: ArtifactRecord = {
            "id": "abc",
            "kind": "test",
            "mime": "text/plain",
            "bytes": 3,
            "sha256": "abc",
            "path": "obj/ab/c",
            "ts": 123,
            "parents": [],
            "src": {},
            "notes": "note",
        }
        self.index.put(rec)
        path = self.index.get_path("abc")
        self.assertEqual(path, "obj/ab/c")


if __name__ == "__main__":
    unittest.main()
