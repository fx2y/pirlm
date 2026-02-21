from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# S33: determinism default mandatory
K_CAP_TOKENS: int = 8000  # Default hard cap


def tokenize(text: str) -> list[str]:
    """C2.T1: Simple whitespace + punctuation tokenizer."""
    return [t.lower() for t in re.findall(r"\w+", text) if t]


def est_tokens(text: str) -> int:
    """C5.T00: Deterministic token-cost estimator with monotonic upper bound.
    Using 1 token per 3 chars (upper bound).
    """
    if not text:
        return 0
    return (len(text) + 2) // 3


def calculate_relevance(goal: str, text: str) -> float:
    """C5.T01: Relevance scorer uses existing lexical primitives.
    Simple TF based overlap for RLM context.
    """
    goal_toks = tokenize(goal)
    text_toks = tokenize(text)
    if not goal_toks or not text_toks:
        return 0.0

    g_set = set(goal_toks)
    t_counts: dict[str, int] = {}
    for tok in text_toks:
        if tok in g_set:
            t_counts[tok] = t_counts.get(tok, 0) + 1

    # Simple score: count of goal tokens found in text (weighted by frequency in text)
    score = sum(t_counts.values())
    return float(score)


@dataclass(frozen=True)
class ContextItem:
    id: str
    text: str
    relevance: float
    cost: int
    kind: str = "var"


def pack_ctx(
    goal: str,
    items: list[dict[str, Any]],  # keys: id, text, kind?
    k_limit: int = K_CAP_TOKENS,
) -> list[str]:
    """C5.T02: pack_ctx selects items by max(relevance/token_cost) under hard K cap.
    Stability: sort by relevance/cost DESC, then cost ASC, then id ASC.
    """
    c_items = []
    for it in items:
        text = it.get("text", "")
        if not isinstance(text, str):
            text = str(text)
        cost = est_tokens(text)
        rel = calculate_relevance(goal, text)
        # Add baseline relevance if it's a critical variable (e.g. Prompt/P)
        if it.get("critical"):
            rel += 1000.0

        c_items.append(
            ContextItem(
                id=it["id"], text=text, relevance=rel, cost=cost, kind=it.get("kind", "var")
            )
        )

    # Sort by relevance/cost DESC, then tie-break
    def sort_key(ci: ContextItem):
        # Ratio of relevance to cost
        ratio = ci.relevance / ci.cost if ci.cost > 0 else ci.relevance
        # Negative ratio for DESC, cost for ASC, id for ASC
        return (-ratio, ci.cost, ci.id)

    sorted_items = sorted(c_items, key=sort_key)

    packed_ids = []
    current_cost = 0
    for ci in sorted_items:
        if current_cost + ci.cost <= k_limit:
            packed_ids.append(ci.id)
            current_cost += ci.cost

    return packed_ids


def apply_cohesion_rule(packed_ids: list[str], items: list[dict[str, Any]]) -> list[str]:
    """C5.T03: preserve call/result adjacency.
    If we keep a 'result', we MUST keep its preceding 'call'.
    If we keep a 'call', we SHOULD keep its following 'result' if available.
    """
    {it["id"]: it for it in items}
    packed_set = set(packed_ids)
    final_ids = []

    for i, it in enumerate(items):
        if it["id"] in packed_set:
            final_ids.append(it["id"])
            continue

        # Cohesion: check if this is a 'call' whose 'result' is packed
        if (
            it.get("ev") == "call"
            and i + 1 < len(items)
            and items[i + 1].get("ev") == "result"
            and items[i + 1]["id"] in packed_set
        ):
            final_ids.append(it["id"])  # Force call into context

        # Or if this is a 'result' whose 'call' is packed
        if (
            it.get("ev") == "result"
            and i - 1 >= 0
            and items[i - 1].get("ev") == "call"
            and items[i - 1]["id"] in packed_set
        ):
            final_ids.append(it["id"])  # Force result into context (optional, but good)

    # Re-sort/dedup preserving order
    unique_ids = []
    seen = set()
    for o_it in items:
        oid = o_it["id"]
        if oid in final_ids and oid not in seen:
            unique_ids.append(oid)
            seen.add(oid)
    return unique_ids


def create_citation_map(
    source_items: list[dict[str, Any]],
    output: str,
) -> list[dict[str, Any]]:
    """C5.T06: Emit citation map with resolvable lineage pointers.
    Preserves legacy fields: {url, doc_sha256, chunk_id, quote, retrieved_at}
    Adds: {artifact_id, view_id}
    """
    # Simple heuristic: find artifact IDs mentioned in output
    citations = []
    import time

    now = int(time.time())

    # regex for artifact IDs (cas_...)
    aids = re.findall(r"cas_[a-f0-9]{16,}", output)
    # regex for view IDs (vid_...)
    vids = re.findall(r"vid_[a-f0-9]{16,}", output)

    seen = set()
    for aid in aids:
        if aid in seen:
            continue
        citations.append(
            {
                "url": f"artifact://{aid}",  # Proxy URL for legacy compliance
                "doc_sha256": aid.replace("cas_", ""),
                "chunk_id": "root",
                "quote": output[:100],  # Excerpt
                "retrieved_at": now,
                "artifact_id": aid,
            }
        )
        seen.add(aid)

    for vid in vids:
        if vid in seen:
            continue
        citations.append(
            {
                "url": f"view://{vid}",
                "doc_sha256": vid.replace("vid_", ""),
                "chunk_id": "view",
                "quote": output[:100],
                "retrieved_at": now,
                "view_id": vid,
            }
        )
        seen.add(vid)

    return citations
