from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from .base import BaseCache, CacheHit, CacheRow


class FsCache(BaseCache):
    """B2b: FS blob + sqlite index (simplified for now to just FS for B2b)."""

    def __init__(self, root_dir: Path) -> None:
        self._root = root_dir
        self._root.mkdir(parents=True, exist_ok=True)
        self._meta_dir = self._root / "meta"
        self._body_dir = self._root / "bodies"
        self._meta_dir.mkdir(exist_ok=True)
        self._body_dir.mkdir(exist_ok=True)

    def _key_to_path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode()).hexdigest()
        return self._meta_dir / h

    def get(self, key: str) -> CacheHit | None:
        p = self._key_to_path(key)
        if not p.exists():
            return None
        try:
            with p.open("r") as f:
                meta = json.load(f)
            body_p = self._body_dir / meta["body_sha256"]
            if not body_p.exists():
                return None
            return {
                "key": key,
                "body_sha256": meta["body_sha256"],
                "body": body_p.read_bytes(),
                "status": meta["status"],
                "etag": meta.get("etag"),
                "last_modified": meta.get("last_modified"),
                "headers": meta["headers"],
            }
        except Exception:
            return None

    def put(self, row: CacheRow) -> None:
        body_p = self._body_dir / row["body_sha256"]
        if not body_p.exists():
            body_p.write_bytes(row["body"])

        p = self._key_to_path(row["key"])
        meta = {
            "key": row["key"],
            "body_sha256": row["body_sha256"],
            "status": row["status"],
            "etag": row.get("etag"),
            "last_modified": row.get("last_modified"),
            "headers": row["headers"],
            "fetched_at": int(time.time()),
        }
        with p.open("w") as f:
            json.dump(meta, f)

    def mark_304(
        self, key: str, *, etag: str | None, last_modified: str | None
    ) -> CacheHit | None:
        hit = self.get(key)
        if not hit:
            return None
        hit["etag"] = etag
        hit["last_modified"] = last_modified
        self.put(
            {
                "key": key,
                "body_sha256": hit["body_sha256"],
                "body": hit["body"],
                "status": hit["status"],
                "etag": etag,
                "last_modified": last_modified,
                "headers": hit["headers"],
            }
        )
        return hit

    def dedup_by_sha(self, body_sha256: str) -> list[str]:
        results = []
        for p in self._meta_dir.glob("*"):
            try:
                with p.open("r") as f:
                    meta = json.load(f)
                    if meta["body_sha256"] == body_sha256:
                        results.append(meta["key"])
            except Exception:
                continue
        return results


__all__ = ["FsCache"]
