from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pirml.toolsearch.index import K_CAP, BM25Index, SearchHit, tokenize, tool_doc_fields
from pirml.toolsearch.loader import catalog_hash

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
SEARCH_CACHE: dict[tuple[str, str, str, int], tuple[str, ...]] = {}
INDEX_CACHE: dict[str, BM25Index] = {}
REWRITE_CACHE: dict[str, dict[str, list[str]]] = {}

# G.P2.6: regex-lookalike heuristic tokens (anchors, classes, alternation, quantifiers)
_REGEX_TOKENS_RE = re.compile(r"[\^\$\[\]\(\)\|\*\+\?\.\\\{\}]")


def _normalize_query(query: str) -> str:
    return query.strip().lower()


def _validate_catalog(catalog: Mapping[str, ToolManifest]) -> None:
    if not catalog:
        raise SearchError("missing_tool_definition", "Tool catalog is empty")
    if all(manifest.get("defer_loading", True) for manifest in catalog.values()):
        raise SearchError("all_deferred", "All tools in catalog are deferred")


def _is_ci() -> bool:
    return os.getenv("CI", "0") in ("1", "true", "TRUE")


def is_regex_query(query: str) -> bool:
    """G.P2.6: Public predicate — true if query contains regex metacharacters."""
    return bool(_REGEX_TOKENS_RE.search(query))


def _rank_bm25_hits(hits: list[SearchHit]) -> list[str]:
    ordered = sorted(hits, key=lambda h: (-h.score, h.hot_rank, h.arg_count, h.name))
    return [h.name for h in ordered]


def _apply_exact_name_boost(names: list[str], raw_query: str) -> list[str]:
    exact = _normalize_query(raw_query)
    exact_names = [name for name in names if name.lower() == exact]
    other_names = [name for name in names if name.lower() != exact]
    return exact_names + other_names


def _apply_namespace_boost(names: list[str], raw_query: str) -> list[str]:
    """G.P2.7: Promote tools whose namespace prefix matches a dotted prefix in the query.
    e.g. query 'svc.list_files' boosts tools with name starting 'svc.'.
    """
    if "." not in raw_query:
        return names
    ns = raw_query.split(".")[0].lower()
    ns_prefix = ns + "."
    in_ns = [n for n in names if n.lower().startswith(ns_prefix)]
    out_ns = [n for n in names if not n.lower().startswith(ns_prefix)]
    return in_ns + out_ns


def to_tool_references(names: list[str]) -> list[dict[str, str]]:
    """G.P2.8: Convert search result names to vendor-compatible tool_reference blocks.
    Vendor contract: list of {type: 'tool_use', name: <str>}.
    Cap enforced at K_CAP.
    """
    return [{"type": "tool_use", "name": n} for n in names[:K_CAP]]


def clear_caches() -> None:
    """G.P0.1: Clear all global search caches."""
    SEARCH_CACHE.clear()
    INDEX_CACHE.clear()
    REWRITE_CACHE.clear()


def get_catalog_hash(catalog: Mapping[str, ToolManifest]) -> str:
    """G.P0.1: content-based hash for deterministic caching."""
    return catalog_hash(catalog)


def cache_key(
    query: str, catalog: Mapping[str, ToolManifest], mode: str, k: int
) -> tuple[str, str, str, int]:
    """C4.T3: Generate a deterministic cache key."""
    cat_hash = get_catalog_hash(catalog)
    return (_normalize_query(query), cat_hash, mode, k)


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
    mode: str | None = None,
    k: int = K_CAP,
    stability_threshold: float = 0.0,
) -> list[str]:
    """C4.T3: Search with cache and optional stability reuse."""
    k = min(k, K_CAP)  # G.P1.7: enforce cap
    mode = mode or (_resolve_auto_mode(query))
    key = cache_key(query, catalog, mode, k)

    if key in SEARCH_CACHE:
        return list(SEARCH_CACHE[key])

    if stability_threshold > 0 and not _is_ci():
        for (prev_q, prev_cat_hash, prev_mode, prev_k), refs in SEARCH_CACHE.items():
            if (
                prev_cat_hash == key[1]
                and prev_mode == mode
                and prev_k == k
                and jaccard_similarity(prev_q, _normalize_query(query)) >= stability_threshold
            ):
                return list(refs)

    refs = search_tools(catalog, query, mode, k)
    SEARCH_CACHE[key] = tuple(refs)
    return list(refs)


def _resolve_auto_mode(query: str) -> str:
    """G.P2.6: Auto-detect mode from query shape; env var override always wins."""
    env_mode = os.getenv("SEARCH_BACKEND")
    if env_mode:
        return env_mode
    return "regex" if is_regex_query(query) else "bm25"


# --- Backend Protocol & Implementations (C4.P3) ---
@runtime_checkable
class SearchBackend(Protocol):
    """S.EXT1: Ext backend interface."""

    def search(
        self, catalog: Mapping[str, ToolManifest], query: str, k: int = K_CAP
    ) -> list[str]: ...


class BM25Backend:
    def search(self, catalog: Mapping[str, ToolManifest], query: str, k: int = K_CAP) -> list[str]:
        index = BM25Index(catalog)
        hits = index.score(query)
        return _rank_bm25_hits(hits)[:k]


class RegexBackend:
    def search(self, catalog: Mapping[str, ToolManifest], query: str, k: int = K_CAP) -> list[str]:
        return regex_search(catalog, query)[:k]


BACKENDS: dict[str, SearchBackend] = {
    "bm25": BM25Backend(),
    "regex": RegexBackend(),
}


# --- Search Pipeline ---
def build_rewrite_map(catalog: Mapping[str, ToolManifest]) -> dict[str, list[str]]:
    """C4.T1: Compile aliases/verbs/nouns into a deterministic rewrite map."""
    rewrite_map: dict[str, list[str]] = {}
    for name in sorted(catalog.keys()):
        m = catalog[name]
        terms = m.get("aliases", []) + m.get("verbs", []) + m.get("nouns", [])
        for term in terms:
            for tok in tokenize(term):
                if name not in rewrite_map.get(tok, []):
                    rewrite_map.setdefault(tok, []).append(name)
    for tok in rewrite_map:
        rewrite_map[tok].sort()
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
    mode: str | None = None,
    k: int = K_CAP,
) -> list[str]:
    """C2.T4: Unified search entry point with deterministic ranking and alias rewrite.
    G.P1.7: k capped at K_CAP.
    G.P2.6: mode auto-detected from query shape via _resolve_auto_mode.
    G.P2.7: namespace prefix boost applied after exact-name boost.
    """
    k = min(k, K_CAP)  # G.P1.7
    mode = mode or _resolve_auto_mode(query)  # G.P2.6

    _validate_catalog(catalog)

    cat_hash = get_catalog_hash(catalog)
    if cat_hash not in REWRITE_CACHE:
        REWRITE_CACHE[cat_hash] = build_rewrite_map(catalog)
    rewrite_map = REWRITE_CACHE[cat_hash]
    rewritten_query = rewrite_query(query, rewrite_map)

    if mode not in BACKENDS:
        raise SearchError("invalid_mode", f"Unknown search mode: {mode}")

    backend = BACKENDS[mode]
    search_query = rewritten_query if mode == "bm25" else query

    if mode == "bm25":
        if cat_hash not in INDEX_CACHE:
            INDEX_CACHE[cat_hash] = BM25Index(catalog)
        index: BM25Index = INDEX_CACHE[cat_hash]
        hits = index.score(search_query)
        names = _rank_bm25_hits(hits)[:100]
    else:
        names = backend.search(catalog, search_query, k=100)

    # G.P2.7: namespace prefix boost before final k-slice
    names = _apply_namespace_boost(names, query)
    names = _apply_exact_name_boost(names, query)
    return names[:k]


if __name__ == "__main__":
    import argparse
    import json
    import sys
    from pathlib import Path

    from pirml.toolsearch.loader import load_catalog

    parser = argparse.ArgumentParser(description="PIRML ToolSearch CLI")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--k", type=int, default=K_CAP, help="Top-K results")
    parser.add_argument(
        "--tools-dir", default="tests/fixtures/toolsearch/catalog", help="Tools directory"
    )
    parser.add_argument("--mode", choices=["bm25", "regex"], help="Search mode")
    args = parser.parse_args()

    try:
        catalog = load_catalog(Path(args.tools_dir), strict=True)
        results = search_tools(catalog, args.query, mode=args.mode, k=args.k)
        print(json.dumps(results, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
