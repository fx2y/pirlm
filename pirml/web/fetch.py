from __future__ import annotations

import asyncio
import contextlib
import gzip
import hashlib
import json
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypedDict, cast
from urllib.request import Request, urlopen

from .cache.base import BaseCache
from .trace import WebTracer
from .types import DocRow
from .urlnorm import normalize_url


@dataclass(frozen=True)
class FetchConfig:
    ua: str = "pirml/0.1"
    timeout_s: float = 15.0
    max_bytes: int = 5242880


class Fetcher(Protocol):
    async def fetch(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        tracer: WebTracer | None = None,
    ) -> DocRow: ...


class FixtureRow(TypedDict):
    url: str
    final_url: str
    status: int
    headers: dict[str, str]
    content_type: str
    encoding_guess: str
    body_file: str


@dataclass(frozen=True)
class _FixturePayload:
    row: FixtureRow
    body: bytes


def _decode_body(body: bytes, encoding_guess: str) -> str:
    candidates = [encoding_guess.lower(), "utf-8", "cp1252", "latin-1"]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return body.decode(candidate)
        except (UnicodeDecodeError, LookupError):
            continue
    return body.decode("latin-1", errors="replace")


class RealDocFetcher:
    """Production fetcher using stdlib urllib + asyncio.to_thread."""

    def __init__(self, config: FetchConfig | None = None) -> None:
        self._config = config or FetchConfig()

    async def fetch(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        tracer: WebTracer | None = None,
    ) -> DocRow:
        if tracer:
            tracer.emit("fetch_call", url=url, cache_hit=False)
        start_ms = int(time.time() * 1000)
        try:
            row = await asyncio.to_thread(
                self._sync_fetch, url, etag=etag, last_modified=last_modified
            )
            if tracer:
                tracer.emit(
                    "fetch_result",
                    url=url,
                    status=row["status"],
                    bytes=row["bytes"],
                    sha256=row["body_sha256"],
                    ms=int(time.time() * 1000) - start_ms,
                    cache_hit=False,
                )
            return row
        except Exception as e:
            if tracer:
                tracer.emit("fetch_result", url=url, status=0, error=str(e), cache_hit=False)
            raise

    def _sync_fetch(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> DocRow:
        headers = {
            "User-Agent": self._config.ua,
            "Accept-Encoding": "gzip, deflate",
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        req = Request(url, headers=headers)
        from urllib.error import HTTPError

        try:
            with urlopen(req, timeout=self._config.timeout_s) as resp:
                return self._parse_response(url, resp)
        except HTTPError as e:
            if e.code == 304:
                return self._parse_response(url, e)  # type: ignore
            raise

    def _parse_response(self, url: str, resp: Any) -> DocRow:
        status = resp.status
        headers = {k.lower(): v for k, v in resp.getheaders()}
        final_url = normalize_url(resp.url)
        content_type = headers.get("content-type", "application/octet-stream").split(";")[0]

        if status == 304:
            return {
                "url": normalize_url(url),
                "final_url": final_url,
                "status": 304,
                "headers": headers,
                "content_type": content_type,
                "bytes": 0,
                "encoding_guess": "",
                "body": "",
                "body_sha256": "",
            }

        raw_body = resp.read(self._config.max_bytes + 1)
        if len(raw_body) > self._config.max_bytes:
            # hard-stop pre-decode
            raw_body = raw_body[: self._config.max_bytes]

        encoding = headers.get("content-encoding", "").lower()
        if encoding == "gzip":
            with contextlib.suppress(OSError, zlib.error):
                raw_body = gzip.decompress(raw_body)
        elif encoding == "deflate":
            with contextlib.suppress(zlib.error):
                raw_body = zlib.decompress(raw_body)

        encoding_guess = ""
        if "charset=" in headers.get("content-type", "").lower():
            encoding_guess = headers["content-type"].lower().split("charset=")[-1].strip()

        body_text = _decode_body(raw_body, encoding_guess)
        body_sha256 = hashlib.sha256(raw_body).hexdigest()

        return {
            "url": normalize_url(url),
            "final_url": final_url,
            "status": status,
            "headers": headers,
            "content_type": content_type,
            "bytes": len(raw_body),
            "encoding_guess": encoding_guess,
            "body": body_text,
            "body_sha256": body_sha256,
        }


def _load_fixture_manifest(path: Path) -> list[FixtureRow]:
    payload_raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload_raw, dict):
        raise ValueError("fixture manifest must be an object")
    payload = cast(dict[str, Any], payload_raw)
    rows_candidate = payload.get("responses")
    if not isinstance(rows_candidate, list):
        raise ValueError("fixture manifest missing list field: responses")
    rows_raw = cast(list[Any], rows_candidate)
    rows: list[FixtureRow] = []
    for item in rows_raw:
        if not isinstance(item, dict):
            raise ValueError("fixture response must be an object")
        row_map = cast(dict[str, Any], item)
        row: FixtureRow = {
            "url": cast(str, row_map["url"]),
            "final_url": cast(str, row_map["final_url"]),
            "status": cast(int, row_map["status"]),
            "headers": cast(dict[str, str], row_map["headers"]),
            "content_type": cast(str, row_map["content_type"]),
            "encoding_guess": cast(str, row_map["encoding_guess"]),
            "body_file": cast(str, row_map["body_file"]),
        }
        rows.append(row)
    return rows


class FixtureDocFetcher:
    """Deterministic fetch substrate for offline unit tests."""

    def __init__(self, fixtures_path: Path) -> None:
        base = fixtures_path.parent
        records: dict[str, _FixturePayload] = {}
        for row in _load_fixture_manifest(fixtures_path):
            body_path = base / row["body_file"]
            body = body_path.read_bytes()
            records[normalize_url(row["url"])] = _FixturePayload(row=row, body=body)
        self._records = records

    async def fetch(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        tracer: WebTracer | None = None,
    ) -> DocRow:
        key = normalize_url(url)
        if key not in self._records:
            raise KeyError(f"fixture not found for normalized url: {key}")
        payload = self._records[key]

        if tracer:
            tracer.emit("fetch_call", url=key, cache_hit=False)
        # In fixture mode, we don't really support 304 unless we mock it in manifest
        # For now, just return 200
        body_sha256 = hashlib.sha256(payload.body).hexdigest()
        body_text = _decode_body(payload.body, payload.row["encoding_guess"])
        row: DocRow = {
            "url": key,
            "final_url": normalize_url(payload.row["final_url"]),
            "status": payload.row["status"],
            "headers": dict(payload.row["headers"]),
            "content_type": payload.row["content_type"],
            "bytes": len(payload.body),
            "encoding_guess": payload.row["encoding_guess"],
            "body": body_text,
            "body_sha256": body_sha256,
        }
        if tracer:
            tracer.emit(
                "fetch_result",
                url=key,
                status=row["status"],
                bytes=row["bytes"],
                sha256=row["body_sha256"],
                cache_hit=False,
            )
        return row


class CachedDocFetcher:
    """Wrapper that manages cache logic (conditional GET, dedup)."""

    def __init__(self, fetcher: Fetcher, cache: BaseCache) -> None:
        self._fetcher = fetcher
        self._cache = cache

    async def fetch(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        tracer: WebTracer | None = None,
    ) -> DocRow:
        key = normalize_url(url)
        hit = self._cache.get(key)

        # Use passed in validators if provided, else use cache
        effective_etag = etag or (hit["etag"] if hit else None)
        effective_last_mod = last_modified or (hit["last_modified"] if hit else None)

        if tracer:
            tracer.emit("fetch_call", url=key, cache_hit=hit is not None)

        start_ms = int(time.time() * 1000)
        # Don't pass tracer to underlying fetcher to avoid duplicate frames
        row = await self._fetcher.fetch(
            url, etag=effective_etag, last_modified=effective_last_mod, tracer=None
        )

        if row["status"] == 304 and hit:
            # Re-fetch metadata might have updated etag/last_modified
            new_etag = row["headers"].get("etag")
            new_last_mod = row["headers"].get("last-modified")
            updated = self._cache.mark_304(key, etag=new_etag, last_modified=new_last_mod)
            if updated:
                if tracer:
                    tracer.emit(
                        "fetch_result",
                        url=key,
                        status=200,
                        bytes=len(updated["body"]),
                        sha256=updated["body_sha256"],
                        cache_hit=True,
                        ms=int(time.time() * 1000) - start_ms,
                    )
                return {
                    "url": key,
                    "final_url": row["final_url"],
                    "status": 200,  # Return as 200 to caller
                    "headers": updated["headers"],
                    "content_type": updated["headers"].get("content-type", "text/html"),
                    "bytes": len(updated["body"]),
                    "encoding_guess": "utf-8",
                    "body": _decode_body(updated["body"], "utf-8"),
                    "body_sha256": updated["body_sha256"],
                }

        if row["status"] == 200:
            self._cache.put(
                {
                    "key": key,
                    "body_sha256": row["body_sha256"],
                    "body": row["body"].encode("utf-8"),
                    "status": 200,
                    "etag": row["headers"].get("etag"),
                    "last_modified": row["headers"].get("last-modified"),
                    "headers": row["headers"],
                }
            )
            if tracer:
                tracer.emit(
                    "fetch_result",
                    url=key,
                    status=200,
                    bytes=row["bytes"],
                    sha256=row["body_sha256"],
                    cache_hit=False,
                    ms=int(time.time() * 1000) - start_ms,
                )

        return row


def load_fixture_fetcher(path: Path) -> FixtureDocFetcher:
    return FixtureDocFetcher(fixtures_path=path)


__all__ = [
    "CachedDocFetcher",
    "FetchConfig",
    "Fetcher",
    "FixtureDocFetcher",
    "FixtureRow",
    "RealDocFetcher",
    "load_fixture_fetcher",
]
