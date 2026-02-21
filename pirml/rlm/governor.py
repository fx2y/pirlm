from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, cast

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
    Mandatory: critical items (like Goal P) are prioritized.
    """
    c_items: list[ContextItem] = []
    for it in items:
        text = it.get("text", "")
        if not isinstance(text, str):
            text = str(text)
        cost = est_tokens(text)
        rel = calculate_relevance(goal, text)
        is_critical = it.get("critical", False)
        # Add baseline relevance if it's a critical variable
        if is_critical:
            rel += 1000000.0  # Massive boost for critical items

        c_items.append(
            ContextItem(
                id=it["id"],
                text=text,
                relevance=rel,
                cost=cost,
                kind=it.get("kind", "var"),
            )
        )

    # Sort by relevance/cost DESC, then tie-break
    def sort_key(ci: ContextItem):
        ratio = ci.relevance / ci.cost if ci.cost > 0 else ci.relevance
        return (-ratio, ci.cost, ci.id)

    sorted_items = sorted(c_items, key=sort_key)

    packed_ids: list[str] = []
    current_cost = 0
    for ci in sorted_items:
        # If it's critical and doesn't fit, we might still want it,
        # but for now we follow the hard cap.
        if current_cost + ci.cost <= k_limit:
            packed_ids.append(ci.id)
            current_cost += ci.cost
        elif ci.relevance > 1000000.0:
            # S35: Mandatory retention for small critical items if they fit alone
            if not packed_ids and ci.cost <= k_limit:
                packed_ids.append(ci.id)
                current_cost += ci.cost

    return packed_ids


def apply_cohesion_rule(
    packed_ids: list[str], items: list[dict[str, Any]], k_limit: int = K_CAP_TOKENS
) -> list[str]:
    """C5.T03: preserve call/result adjacency and enforce hard cap post-cohesion.
    If we keep a 'result', we MUST keep its preceding 'call'.
    """
    packed_set = set(packed_ids)

    # 1. Expand for cohesion
    expanded_set = set(packed_ids)
    for i, it in enumerate(items):
        if (
            it["id"] in packed_set
            and it.get("ev") == "result"
            and i - 1 >= 0
            and items[i - 1].get("ev") == "call"
        ):
            # If this is a 'result', ensure its 'call' is present
            expanded_set.add(items[i - 1]["id"])

    # 2. Enforce hard-cap by dropping non-critical items from expansion if needed
    # Preserving relative order from 'items' is important for context coherence
    final_candidates = [it for it in items if it["id"] in expanded_set]

    current_cost = sum(est_tokens(it["text"]) for it in final_candidates)

    while current_cost > k_limit and final_candidates:
        # To keep it simple, we drop from the end of non-critical items
        drop_idx = -1
        for idx in range(len(final_candidates) - 1, -1, -1):
            if not final_candidates[idx].get("critical"):
                drop_idx = idx
                break

        if drop_idx == -1:
            # Only critical items left, and we are still over budget?
            # Must drop even critical items from the end to satisfy H5/K-cap
            drop_idx = len(final_candidates) - 1

        removed = final_candidates.pop(drop_idx)
        current_cost -= est_tokens(removed["text"])

    return [it["id"] for it in final_candidates]


def build_rlm_prompt(
    state: Any,  # RlmState
    history: Any,  # RlmHistory
    emit_pi_pointers: bool = False,
) -> str:
    """C5.T02/T04: Context Governor with bulk off-ctx.
    Encapsulates prompt construction with budget enforcement.
    """
    items: list[dict[str, Any]] = []
    # Variables
    s_dict = state.to_dict()
    for k, v in s_dict.items():
        critical = k == "P"
        if isinstance(v, list) and k in ("DOCS", "CHUNKS", "SUMS", "BUF"):
            v_list = cast(list[Any], v)
            # S34: Handle-only ctx pack / excerpt
            items.append(
                {
                    "id": f"var:{k}",
                    "text": f"BulkVar {k}: list (len={len(v_list)})",  # Meta only
                    "kind": "var",
                    "critical": critical,
                }
            )
            # Add excerpts separately as candidates
            for i, x in enumerate(v_list[:50]):
                items.append(
                    {
                        "id": f"var:{k}:{i}",
                        "text": f"{k}[{i}]: {str(x)[:240]}",  # S34 excerpt cap
                        "kind": "excerpt",
                        "critical": False,
                    }
                )
        else:
            v_any = cast(Any, v)
            items.append(
                {"id": f"var:{k}", "text": str(v_any), "kind": "var", "critical": critical}
            )

    # History
    for f in history:
        # C6.T03: Hard-block ctx contamination
        if f["ev"] == "custom":
            continue

        items.append(
            {
                "id": f"history:{f['seq']}",
                "text": f"Hist {f['seq']} ({f['ev']}): {f['prefix']}... (len={f['len']})",
                "kind": "history",
                "ev": f["ev"],
            }
        )

    # Pack under budget
    packed_ids = pack_ctx(state.P, items, k_limit=K_CAP_TOKENS)
    # Apply cohesion
    final_ids = apply_cohesion_rule(packed_ids, items, k_limit=K_CAP_TOKENS)

    final_ids_set = set(final_ids)
    parts = [f"Goal: {state.P}"]

    vars_block: list[str] = []
    hist_block: list[str] = []
    for it in items:
        if it["id"] in final_ids_set:
            if it["kind"] == "var":
                vars_block.append(it["text"])
            else:
                hist_block.append(it["text"])

    if vars_block:
        parts.append("Variables:\n" + "\n".join(vars_block))
    if hist_block:
        parts.append("History:\n" + "\n".join(hist_block))

    if emit_pi_pointers:
        from pirml.runtime.rpc import send_custom

        tokens_before = sum(est_tokens(it["text"]) for it in items)
        first_kept = final_ids[0] if final_ids else None
        send_custom(
            "pirml_summary",
            {
                "summary": f"Context packed: {len(final_ids)}/{len(items)} items kept",
                "firstKeptEntryId": first_kept,
                "tokensBefore": tokens_before,
            },
        )

    return "\n\n".join(parts)


def create_citation_map(
    source_items: list[dict[str, Any]],
    output: str,
    ts: int | None = None,
) -> list[dict[str, Any]]:
    """C5.T06: Emit citation map with resolvable lineage pointers.
    Preserves legacy fields: {url, doc_sha256, chunk_id, quote, retrieved_at}
    """
    # Simple heuristic: find artifact IDs mentioned in output
    citations: list[dict[str, Any]] = []
    now = ts if ts is not None else 1_700_000_000

    # regex for artifact IDs (cas_ prefix or raw 64-char hex)
    aids = re.findall(r"cas_([a-f0-9]{64})", output)
    # regex for view IDs (vid_ prefix or raw 64-char hex)
    vids = re.findall(r"vid_([a-f0-9]{64})", output)

    seen: set[str] = set()
    for aid in aids:
        if aid in seen:
            continue
        citations.append(
            {
                "url": f"artifact://cas_{aid}",  # Proxy URL for legacy compliance
                "doc_sha256": aid,
                "chunk_id": "root",
                "quote": output[:100],  # Excerpt
                "retrieved_at": now,
            }
        )
        seen.add(aid)

    for vid in vids:
        if vid in seen:
            continue
        citations.append(
            {
                "url": f"view://vid_{vid}",
                "doc_sha256": vid,
                "chunk_id": "view",
                "quote": output[:100],
                "retrieved_at": now,
            }
        )
        seen.add(vid)

    return citations
