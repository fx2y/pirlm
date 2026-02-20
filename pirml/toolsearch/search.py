from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pirml.toolsearch.index import BM25Index, tokenize, tool_doc_fields

if TYPE_CHECKING:
    from pirml.contracts.schemas import ToolManifest


# --- Search Error Taxonomy ---
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


# --- Search Cache & Stability (C4.P2) ---
SEARCH_CACHE: dict[tuple[Any, ...], list[str]] = {}
INDEX_CACHE: dict[str, Any] = {}
REWRITE_CACHE: dict[str, dict[str, list[str]]] = {}
_CAT_HASH_CACHE: dict[int, str] = {}


def get_catalog_hash(catalog: Mapping[str, ToolManifest]) -> str:
    cat_id = id(catalog)
    if cat_id in _CAT_HASH_CACHE:
        return _CAT_HASH_CACHE[cat_id]

    cat_blob = json.dumps(catalog, sort_keys=True)
    h = hashlib.sha256(cat_blob.encode("utf-8")).hexdigest()
    _CAT_HASH_CACHE[cat_id] = h
    return h


def cache_key(
    query: str, catalog: Mapping[str, ToolManifest], mode: str, k: int
) -> tuple[str, str, str, int]:
    """C4.T3: Generate a deterministic cache key."""
    cat_hash = get_catalog_hash(catalog)
    return (query.strip().lower(), cat_hash, mode, k)


def jaccard_similarity(q1: str, q2: str) -> float:
    """Measure token similarity between two queries."""
    s1 = set(tokenize(q1))
    s2 = set(tokenize(q2))
    if not s1 and not s2:
        return 1.0
    return len(s1 & s2) / len(s1 | s2)


def search_with_cache(
    catalog: Mapping[str, ToolManifest],
    query: str,
    mode: str = None,  # type: ignore
    k: int = 5,
    stability_threshold: float = 0.0,
) -> list[str]:
    """C4.T3: Search with cache and optional stability reuse."""
    mode = mode or os.getenv("SEARCH_BACKEND", "bm25")
    key = cache_key(query, catalog, mode, k)

    # Direct hit
    if key in SEARCH_CACHE:
        return SEARCH_CACHE[key]

    # Stability reuse
    if stability_threshold > 0 and os.getenv("CI", "0") not in ("1", "true", "TRUE"):
        for (prev_q, prev_cat_hash, prev_mode, prev_k), refs in SEARCH_CACHE.items():
            if (
                prev_cat_hash == key[1]
                and prev_mode == mode
                and prev_k == k
                and jaccard_similarity(prev_q, query) >= stability_threshold
            ):
                return refs

    # Miss: run actual search
    refs = search_tools(catalog, query, mode, k)
    SEARCH_CACHE[key] = refs
    return refs


# --- Backend Protocol & Implementations (C4.P3) ---
@runtime_checkable
class SearchBackend(Protocol):
    """S.EXT1: Ext backend interface."""

    def search(self, catalog: Mapping[str, ToolManifest], query: str, k: int = 5) -> list[str]: ...


class BM25Backend:
    def search(self, catalog: Mapping[str, ToolManifest], query: str, k: int = 5) -> list[str]:
        index = BM25Index(catalog)
        hits = index.score(query)
        # S.SR1: Deterministic rank key
        hits.sort(key=lambda h: (-h.score, h.hot_rank, h.arg_count, h.name))
        return [h.name for h in hits[:k]]


class RegexBackend:
    def search(self, catalog: Mapping[str, ToolManifest], query: str, k: int = 5) -> list[str]:
        return regex_search(catalog, query)[:k]


BACKENDS: dict[str, SearchBackend] = {
    "bm25": BM25Backend(),
    "regex": RegexBackend(),
}


# --- Search Pipeline ---
def build_rewrite_map(catalog: Mapping[str, ToolManifest]) -> dict[str, list[str]]:
    """C4.T1: Compile aliases/verbs/nouns into a deterministic rewrite map."""
    rewrite_map: dict[str, list[str]] = {}
    for name, m in catalog.items():
        terms = m.get("aliases", []) + m.get("verbs", []) + m.get("nouns", [])
        for term in terms:
            for tok in tokenize(term):
                if name not in rewrite_map.get(tok, []):
                    rewrite_map.setdefault(tok, []).append(name)
    return rewrite_map


def rewrite_query(query: str, rewrite_map: dict[str, list[str]]) -> str:
    """S.AS1: Normalize query by expanding aliases to canonical tool names."""
    tokens = tokenize(query)
    out: list[str] = []
    for tok in tokens:
        if tok in rewrite_map:
            out.extend(rewrite_map[tok])
        else:
            out.append(tok)
    return " ".join(out)


def regex_search(catalog: Mapping[str, ToolManifest], pattern: str) -> list[str]:
    """C2.T3: Regex search with safety guards."""
    if len(pattern) > 200:
        raise SearchError("pattern_too_long", f"Pattern length {len(pattern)} exceeds 200")
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise SearchError("invalid_pattern", str(e)) from e

    hits: list[tuple[str, int, int]] = []
    for name, m in catalog.items():
        if rx.search(name) or rx.search(tool_doc_fields(m)):
            hot_rank = 0 if not m.get("defer_loading", True) else 1
            arg_count = len(m.get("input_schema", {}).get("properties") or {})
            hits.append((name, hot_rank, arg_count))
    hits.sort(key=lambda h: (h[1], h[2], h[0]))
    return [h[0] for h in hits]


def search_tools(
    catalog: Mapping[str, ToolManifest],
    query: str,
    mode: str = None,  # type: ignore
    k: int = 5,
) -> list[str]:
    """C2.T4: Unified search entry point with deterministic ranking and alias rewrite."""
    mode = mode or os.getenv("SEARCH_BACKEND", "bm25")
    if not catalog:
        raise SearchError("missing_tool_definition", "Tool catalog is empty")
    if all(m.get("defer_loading", True) for m in catalog.values()):
        raise SearchError("all_deferred", "All tools in catalog are deferred")

    cat_hash = get_catalog_hash(catalog)
    if cat_hash not in REWRITE_CACHE:
        REWRITE_CACHE[cat_hash] = build_rewrite_map(catalog)
    rewrite_map = REWRITE_CACHE[cat_hash]
    rewritten_query = rewrite_query(query, rewrite_map)

    if mode not in BACKENDS:
        raise SearchError("invalid_mode", f"Unknown search mode: {mode}")

    backend = BACKENDS[mode]
    search_query = rewritten_query if mode == "bm25" else query

    # For BM25, we use index caching
    if mode == "bm25":
        if cat_hash not in INDEX_CACHE:
            INDEX_CACHE[cat_hash] = BM25Index(catalog)
        index: BM25Index = INDEX_CACHE[cat_hash]
        hits = index.score(search_query)
        hits.sort(key=lambda h: (-h.score, h.hot_rank, h.arg_count, h.name))
        names = [h.name for h in hits[:100]]
    else:
        names = backend.search(catalog, search_query, k=100)

    # Re-apply exact name boost
    final_names: list[str] = []
    exact_match = query.lower().strip()
    for name in names:
        if name.lower() == exact_match:
            final_names.insert(0, name)
        else:
            final_names.append(name)

    return final_names[:k]
