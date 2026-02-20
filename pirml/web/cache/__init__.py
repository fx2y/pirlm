from __future__ import annotations

from pathlib import Path

from .base import BaseCache, CacheHit, CacheRow
from .fs import FsCache
from .sqlite import SqliteCache


def cache_factory(kind: str, path: Path) -> BaseCache:
    if kind == "sqlite":
        return SqliteCache(path)
    if kind == "fs":
        return FsCache(path)
    return SqliteCache(path)


__all__ = ["BaseCache", "CacheHit", "CacheRow", "FsCache", "SqliteCache", "cache_factory"]
