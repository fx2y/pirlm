# ADR 005: Evaluation Matrix & Winner Selection

## Evaluation Shard (`tests/fixtures/web/corpus.jsonl`)
- **Queries:** 50 diverse queries (temporal, factual, list, null).
- **Oracle:** Pre-computed evidence-linked accuracy score (acc).
- **Metric Tuple:** `(acc, -bytes, -chunks, -fetches, cache_hit)`.

## Matrix Run (`python -m scripts.web_eval`)
```sh
# Executes all declared plans (B1-B5 axes)
# Unsupported variants => typed error rows
# Output: out/web_eval.json (full NDJSON)
# Output: out/web_eval.canonical.json (winner verdict)
```

## Winner Rule
```py
def pick_winner(results: list[Result]) -> Plan:
    # 1. Sort by lexicographic metric tuple
    # 2. Tie-break: choose lower state-space (fewer deps/files)
    return sorted(results, key=lambda r: r.metrics, reverse=True)[0]
```

## Hard Constraints
- `N_chunks <= 40` global.
- `chunk <= 800c`.
- `serp_k <= 8`.
- `per_domain_cap = 2`.
