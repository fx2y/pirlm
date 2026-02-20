from __future__ import annotations

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


__all__ = ["MockProvider", "Provider", "rank_and_diversify"]
