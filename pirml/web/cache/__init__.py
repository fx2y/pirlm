from __future__ import annotations

from pathlib import Path

from .base import BaseCache, CacheHit, CacheRow
from .sqlite import SqliteCache


def cache_factory(kind: str, path: Path) -> BaseCache:
    # B2a is the winner, sqlite only
    return SqliteCache(path)


__all__ = ["BaseCache", "CacheHit", "CacheRow", "SqliteCache", "cache_factory"]
