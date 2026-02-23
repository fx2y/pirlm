from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .types import ArtifactMeta, ArtifactRecord


class ArtifactsIndex:
    def __init__(self, db_path: Path, timeout: float = 10.0) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), timeout=timeout, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                kind TEXT,
                mime TEXT,
                bytes INTEGER,
                sha256 TEXT,
                path TEXT,
                ts INTEGER,
                src_json TEXT,
                notes TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS parents (
                child TEXT,
                parent TEXT,
                pos INTEGER,
                PRIMARY KEY (child, parent, pos)
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sha ON artifacts(sha256)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_kind ON artifacts(kind)")

    def put(self, rec: ArtifactRecord) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO artifacts
            (id, kind, mime, bytes, sha256, path, ts, src_json, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rec["id"],
                rec["kind"],
                rec["mime"],
                rec["bytes"],
                rec["sha256"],
                rec["path"],
                rec["ts"],
                json.dumps(rec["src"], sort_keys=True, separators=(",", ":")),
                rec.get("notes"),
            ),
        )
        for i, p in enumerate(rec["parents"]):
            self._conn.execute(
                "INSERT OR IGNORE INTO parents (child, parent, pos) VALUES (?, ?, ?)",
                (rec["id"], p, i),
            )

    def get_meta(self, aid: str) -> ArtifactMeta | None:
        row = self._conn.execute(
            "SELECT id, kind, mime, bytes, sha256, ts, src_json FROM artifacts WHERE id = ?",
            (aid,),
        ).fetchone()
        if not row:
            return None

        parents = [
            r[0]
            for r in self._conn.execute(
                "SELECT parent FROM parents WHERE child = ? ORDER BY pos", (aid,)
            ).fetchall()
        ]

        return {
            "id": row[0],
            "kind": row[1],
            "mime": row[2],
            "bytes": row[3],
            "sha256": row[4],
            "ts": row[5],
            "src": json.loads(row[6]),
            "parents": parents,
        }

    def get_path(self, aid: str) -> str | None:
        row = self._conn.execute("SELECT path FROM artifacts WHERE id = ?", (aid,)).fetchone()
        return row[0] if row else None

    def get_kind(self, aid: str) -> str | None:
        row = self._conn.execute("SELECT kind FROM artifacts WHERE id = ?", (aid,)).fetchone()
        return row[0] if row else None

    def resolve_parents(self, aid: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT parent FROM parents WHERE child = ? ORDER BY pos", (aid,)
        ).fetchall()
        return [r[0] for r in rows]

    def find_by_kind(self, kind: str) -> list[str]:
        rows = self._conn.execute("SELECT id FROM artifacts WHERE kind = ?", (kind,)).fetchall()
        return [r[0] for r in rows]

    def list_meta(self, *, kind: str | None = None, limit: int | None = None) -> list[ArtifactMeta]:
        query = "SELECT id, kind, mime, bytes, sha256, ts, src_json FROM artifacts"
        params: list[object] = []
        if kind is not None:
            query += " WHERE kind = ?"
            params.append(kind)
        query += " ORDER BY ts ASC, id ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        rows = self._conn.execute(query, tuple(params)).fetchall()
        metas: list[ArtifactMeta] = []
        for row in rows:
            aid = str(row[0])
            parents = [
                r[0]
                for r in self._conn.execute(
                    "SELECT parent FROM parents WHERE child = ? ORDER BY pos", (aid,)
                ).fetchall()
            ]
            metas.append(
                {
                    "id": aid,
                    "kind": row[1],
                    "mime": row[2],
                    "bytes": row[3],
                    "sha256": row[4],
                    "ts": row[5],
                    "src": json.loads(row[6]),
                    "parents": parents,
                }
            )
        return metas

    def close(self) -> None:
        self._conn.close()
