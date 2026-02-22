from __future__ import annotations

import asyncio
import json
import os
from collections import defaultdict
from collections.abc import Sequence
from typing import Protocol
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

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
            bytes=0,
            ms=len(selected),
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
    """B1a: Searx JSON provider."""

    def __init__(
        self,
        base_url: str | None = None,
        responses: dict[str, list[SerpRow]] | None = None,
    ) -> None:
        self.base_url = base_url
        self._mock = MockProvider(responses or {})

    async def search(self, query: str, tracer: WebTracer | None = None) -> list[SerpRow]:
        if tracer:
            tracer.emit("search_call", q=query, provider="searx_json")

        if self.base_url:
            try:
                rows = await asyncio.to_thread(self._sync_search, query)
                if tracer:
                    tracer.emit(
                        "search_result",
                        status=200,
                        ms=len(rows),
                    )
                return rows
            except Exception as e:
                if tracer:
                    tracer.emit(
                        "search_result",
                        status=0,
                        error=str(e),
                        ms=0,
                    )
                raise
        else:
            return await self._mock.search(query, tracer=tracer)

    def _sync_search(self, query: str) -> list[SerpRow]:
        params = {
            "q": query,
            "format": "json",
            "categories": "general",
        }
        # Safely join base_url
        base = self.base_url or ""
        url = f"{base.rstrip('/')}/search?{urlencode(params)}"
        req = Request(url, headers={"User-Agent": "pirml/0.1"})

        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])

            serp_rows: list[SerpRow] = []
            for i, res in enumerate(results):
                serp_rows.append(
                    {
                        "url": res["url"],
                        "title": res["title"],
                        "snippet": res.get("content", ""),
                        "rank": i + 1,
                        "source": "searx",
                    }
                )
            return serp_rows


def provider_factory(kind: str, responses: dict[str, list[SerpRow]]) -> Provider:
    # B1 winner is searx_json; keep explicit mock hook for deterministic tests.
    if kind == "searx_json":
        base_url = os.environ.get("SEARX_BASE_URL")
        return SearxJsonProvider(base_url=base_url, responses=responses)
    if kind == "mock":
        return MockProvider(responses)
    if kind == "vendor_http":
        raise ValueError(
            "provider variant B1b/vendor_http is not supported in winner-locked runtime"
        )
    raise ValueError(f"unknown provider kind: {kind}")


__all__ = [
    "MockProvider",
    "Provider",
    "SearxJsonProvider",
    "provider_factory",
    "rank_and_diversify",
]
