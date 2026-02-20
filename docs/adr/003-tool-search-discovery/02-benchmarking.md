# ToolSearch Benchmarking & Compression

## Context Reduction Strategy
`reduction_pct = (1 - selected_bytes / full_bytes) * 100`

Target: **>80%** reduction for catalogs > 50 tools.

## Key Metrics (out/toolsearch_bench.json)
- `n_tools`: Total tools scanned.
- `index_latency_ms`: Time to build BM25 postings from cold manifest JSONs.
- `search_latency_ms_p95`: Query time after hot cache.
- `token_delta`: Difference in context window pressure.

## Canonical Proof
`out/toolsearch_bench.canonical.json` is checked by CI. It strips wall-clock noise and provides a binary `PASS/FAIL` based on preset budgets:
- Indexing: < 50ms (first run).
- Searching: < 5ms.
