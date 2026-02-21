from __future__ import annotations

from pathlib import Path

from .base import BaseCache, CacheHit, CacheRow
from .sqlite import SqliteCache


def cache_factory(kind: str, path: Path) -> BaseCache:
    # B2a winner is sqlite; reject silent fallback.
    if kind != "sqlite":
        raise ValueError(f"unsupported cache backend: {kind}")
    return SqliteCache(path)


__all__ = ["BaseCache", "CacheHit", "CacheRow", "SqliteCache", "cache_factory"]
