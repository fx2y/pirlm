from __future__ import annotations

import json
import time
from collections import defaultdict
from collections.abc import Sequence
from typing import Protocol
from urllib.parse import urlsplit

from .trace import WebTracer
from .types import SerpRow
from .urlnorm import normalize_url


class Provider(Protocol):
    async def search(self, query: str, tracer: WebTracer | None = None) -> list[SerpRow]: ...


def rank_and_diversify(
    rows: Sequence[SerpRow],
    *,
    k: int,
    per_domain_cap: int = 2,
    tracer: WebTracer | None = None,
) -> list[SerpRow]:
    """Deterministic SERP normalization with URL dedup + domain cap."""
    start_ms = int(time.time() * 1000)
    unique: dict[str, SerpRow] = {}
    # Use (rank, source, url) as tie-break
    for row in sorted(rows, key=lambda item: (item["rank"], item["source"], item["url"])):
        key = normalize_url(row["url"])
        if key in unique:
            continue
        normalized: SerpRow = {
            "url": key,
            "title": row["title"],
            "snippet": row["snippet"],
            "rank": row["rank"],
            "source": row["source"],
        }
        unique[key] = normalized

    seen_by_domain: defaultdict[str, int] = defaultdict(int)
    selected: list[SerpRow] = []
    for row in unique.values():
        domain = urlsplit(row["url"]).netloc
        if seen_by_domain[domain] >= per_domain_cap:
            continue
        seen_by_domain[domain] += 1
        selected.append(row)
        if len(selected) >= k:
            break

    if tracer:
        tracer.emit(
            "search_result",
            status=200,
            bytes=0,  # Not applicable here
            ms=int(time.time() * 1000) - start_ms,
        )
    return selected


class MockProvider:
    def __init__(self, responses: dict[str, list[SerpRow]]) -> None:
        self._responses = responses

    async def search(self, query: str, tracer: WebTracer | None = None) -> list[SerpRow]:
        if tracer:
            tracer.emit("search_call", q=query, provider="mock")
        rows = self._responses.get(query, [])
        if tracer:
            tracer.emit("search_result", status=200, ms=1)
        return rows


class SearxJsonProvider:
    """B1a: Searx JSON provider (re-uses MockProvider logic for now but typed for B1)."""

    def __init__(self, responses: dict[str, list[SerpRow]]) -> None:
        self._mock = MockProvider(responses)

    async def search(self, query: str, tracer: WebTracer | None = None) -> list[SerpRow]:
        if tracer:
            tracer.emit("search_call", q=query, provider="searx_json")
        return await self._mock.search(query, tracer=tracer)


class VendorHttpProvider:
    """B1b: Vendor HTTP provider (re-uses MockProvider logic for now but typed for B1)."""

    def __init__(self, responses: dict[str, list[SerpRow]]) -> None:
        self._mock = MockProvider(responses)

    async def search(self, query: str, tracer: WebTracer | None = None) -> list[SerpRow]:
        if tracer:
            tracer.emit("search_call", q=query, provider="vendor_http")
        return await self._mock.search(query, tracer=tracer)


def provider_factory(kind: str, responses: dict[str, list[SerpRow]]) -> Provider:
    if kind == "searx_json":
        return SearxJsonProvider(responses)
    if kind == "vendor_http":
        return VendorHttpProvider(responses)
    return MockProvider(responses)


__all__ = [
    "MockProvider",
    "Provider",
    "SearxJsonProvider",
    "VendorHttpProvider",
    "provider_factory",
    "rank_and_diversify",
]
