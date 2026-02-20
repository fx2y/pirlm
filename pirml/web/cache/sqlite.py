from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .base import BaseCache, CacheHit, CacheRow


class SqliteCache(BaseCache):
    def __init__(self, db_path: Path, timeout: float = 10.0) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(str(db_path), timeout=timeout, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_table()

    def _create_table(self) -> None:
        # metadata table: key -> sha256
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS http_meta (
                key TEXT PRIMARY KEY,
                body_sha256 TEXT,
                status INTEGER,
                etag TEXT,
                last_modified TEXT,
                headers_json TEXT,
                fetched_at INTEGER
            )
            """
        )
        # body table: sha256 -> body
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS http_bodies (
                sha256 TEXT PRIMARY KEY,
                body BLOB
            )
            """
        )

    def get(self, key: str) -> CacheHit | None:
        row = self._conn.execute(
            """
            SELECT m.key, m.body_sha256, b.body, m.status, m.etag, m.last_modified, m.headers_json 
            FROM http_meta m
            JOIN http_bodies b ON m.body_sha256 = b.sha256
            WHERE m.key = ?
            """,
            (key,),
        ).fetchone()
        if not row:
            return None
        return {
            "key": row[0],
            "body_sha256": row[1],
            "body": row[2],
            "status": row[3],
            "etag": row[4],
            "last_modified": row[5],
            "headers": json.loads(row[6]),
        }

    def put(self, row: CacheRow) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO http_bodies (sha256, body) VALUES (?, ?)",
            (row["body_sha256"], row["body"]),
        )
        self._conn.execute(
            """
            INSERT OR REPLACE INTO http_meta
            (key, body_sha256, status, etag, last_modified, headers_json, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["key"],
                row["body_sha256"],
                row["status"],
                row["etag"],
                row["last_modified"],
                json.dumps(row["headers"]),
                int(time.time()),
            ),
        )

    def mark_304(self, key: str, *, etag: str | None, last_modified: str | None) -> CacheHit | None:
        # Update metadata for existing entry
        self._conn.execute(
            "UPDATE http_meta SET etag = ?, last_modified = ?, fetched_at = ? WHERE key = ?",
            (etag, last_modified, int(time.time()), key),
        )
        return self.get(key)

    def dedup_by_sha(self, body_sha256: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT key FROM http_meta WHERE body_sha256 = ?", (body_sha256,)
        ).fetchall()
        return [r[0] for r in rows]


__all__ = ["SqliteCache"]
