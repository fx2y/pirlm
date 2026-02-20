from __future__ import annotations

from typing import Protocol, TypedDict


class CacheHit(TypedDict):
    key: str
    body_sha256: str
    body: bytes
    status: int
    etag: str | None
    last_modified: str | None
    headers: dict[str, str]


class CacheRow(TypedDict):
    key: str
    body_sha256: str
    body: bytes
    status: int
    etag: str | None
    last_modified: str | None
    headers: dict[str, str]


class BaseCache(Protocol):
    def get(self, key: str) -> CacheHit | None: ...

    def put(self, row: CacheRow) -> None: ...

    def mark_304(
        self, key: str, *, etag: str | None, last_modified: str | None
    ) -> CacheHit | None: ...

    def dedup_by_sha(self, body_sha256: str) -> list[str]: ...


__all__ = ["BaseCache", "CacheHit", "CacheRow"]
