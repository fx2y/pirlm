# Web Substrate Handoff (Spec-05)

## Architecture Map
`Q -> SERP -> Fetch -> ETL -> Join -> Cite -> Final(WebFinal)`

1.  **Search (`pirml.web.search`)**: Plug-in providers (Searx, Vendor). Diversified and capped at 8 URLs.
2.  **Fetch (`pirml.web.fetch`)**: stdlib-only concurrent fetching via `asyncio.to_thread`.
3.  **Cache (`pirml.web.cache`)**: Content-addressed (SHA256) storage. SQLite default.
4.  **ETL (`pirml.web.etl`)**: HTML structural parsing + Fallback text windowing. Boilerplate removal via global cross-doc chunk hashing.
5.  **Scoring (`pirml.web.etl.score`)**: BM25 ranking over chunks.
6.  **Join (`pirml.web.etl.join`)**: Deduplication and union of evidence.
7.  **Cite (`pirml.web.cite`)**: Quote span anchoring with <= 25 words and SequenceClock timestamps.

## Bet Winners (Cycle C3/C4)
Evaluation run on `tests/fixtures/web/corpus.jsonl` (N=50, seed=0).
Rule: Lexicographic max on `(acc, -bytes, -chunks, -fetches, cache_hit)`.

- **Winner**: `(B1a, B2a, B3b, B4b, B5a)`
  - **B1a (Provider)**: `searx_json`
  - **B2a (Cache)**: `sqlite`
  - **B3b (Parser)**: `dumb_text_primary`
  - **B4b (Scorer)**: `bm25_chunk`
  - **B5a (Cite)**: `quote_anchor`

## Rejected Options
- **B3a (HTML Structural Parser)**: Lost to `B3b` on chunk volume/byte efficiency metrics in mock shard (though structural info is preserved in `B3a`).
- **B2b (FS Cache)**: SQLite preferred for atomicity and single-file portability.
- **B4a (Keyword Scorer)**: BM25 significantly higher precision.

## Operator Runbook
- **Run Full Gate**: `mise run ci`
- **Run Eval Shard**: `mise run eval-web`
- **Update Goldens**: `PIRML_UPDATE_GOLDEN=1 mise run unit`
- **Web Bench**: `mise run bench-web`

## Invariants & Enforcement
- `C1.I1`: URL normalization idempotency.
- `C1.I2`: SERP domain capping.
- `C1.I4`: Cross-URL body deduplication.
- `C2.I1`: 800 char chunk cap.
- `C2.I2`: N=40 global chunk budget.
- `C2.I3`: 25 word citation quote cap.
