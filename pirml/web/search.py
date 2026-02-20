from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Protocol
from urllib.parse import urlsplit

from .types import SerpRow
from .urlnorm import normalize_url


class Provider(Protocol):
    def search(self, query: str) -> list[SerpRow]: ...


def rank_and_diversify(
    rows: Sequence[SerpRow],
    *,
    k: int,
    per_domain_cap: int = 2,
) -> list[SerpRow]:
    """Deterministic SERP normalization with URL dedup + domain cap."""
    unique: dict[str, SerpRow] = {}
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
    return selected


__all__ = ["Provider", "rank_and_diversify"]
