from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from pirml.toolsearch.index import BM25Index, tool_doc_fields

if TYPE_CHECKING:
    from pirml.contracts.schemas import ToolManifest


class SearchError(Exception):
    def __init__(self, type: str, msg: str):
        self.type = type
        self.msg = msg
        super().__init__(f"{type}: {msg}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": {
                "type": self.type,
                "msg": self.msg,
                "retryable": False,
            },
        }


def regex_search(catalog: dict[str, ToolManifest], pattern: str) -> list[str]:
    """C2.T3: Regex search with safety guards."""
    # S.RX1: Safe regex
    if len(pattern) > 200:
        raise SearchError("pattern_too_long", f"Pattern length {len(pattern)} exceeds 200")

    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise SearchError("invalid_pattern", str(e)) from e

    hits: list[tuple[str, int, int]] = []
    for name, m in catalog.items():
        # Check name and all doc fields for regex match
        if rx.search(name) or rx.search(tool_doc_fields(m)):
            hot_rank = 0 if not m.get("defer_loading", True) else 1
            arg_count = len(m.get("input_schema", {}).get("properties") or {})
            hits.append((name, hot_rank, arg_count))

    # Stable sort for regex results (no score, so use tie-breakers)
    # S.SR1: Deterministic rank key (simplified for regex)
    hits.sort(key=lambda h: (h[1], h[2], h[0]))

    return [h[0] for h in hits]


def search_tools(
    catalog: dict[str, ToolManifest],
    query: str,
    mode: str = "bm25",
    k: int = 5,
) -> list[str]:
    """C2.T4: Unified search entry point with deterministic ranking."""
    if not catalog:
        # C2.T5: Fail fast on missing/empty catalog
        raise SearchError("missing_tool_definition", "Tool catalog is empty")

    # S.MF4: Reject all deferred
    if all(m.get("defer_loading", True) for m in catalog.values()):
        raise SearchError("all_deferred", "All tools in catalog are deferred")

    if mode == "regex":
        names = regex_search(catalog, query)
    else:
        index = BM25Index(catalog)
        hits = index.score(query)

        # S.SR1: Deterministic rank key
        # key=lambda h:(-h.score,0 if h.name==q_exact else 1,h.hot_rank,h.arg_count,h.name)
        # Note: we don't have q_exact easily here without passing it, but name match is a good tie-breaker
        hits.sort(
            key=lambda h: (
                -h.score,
                0 if h.name.lower() == query.lower() else 1,
                h.hot_rank,
                h.arg_count,
                h.name,
            )
        )
        names = [h.name for h in hits]

    return names[:k]
