# PIRML Web Substrate Handoff (Spec-05)

Mission: Deterministic, L1-only web ETL for RAG without L0 tool surface growth. `V<<G`.

## Core Thesis
**ETL-before-reasoning.** Fetch wide, keep tiny, cite hard. If it isn't in `final.json` or `trace.ndjson`, it didn't happen.

## The Model
- **L0 (Substrate):** Frozen runtime tool surface (`{echo,readfile,bash}`).
- **L1 (Metadata):** Web substrate (`pirml.web`). Additive orchestration.
- **G (Gate):** Authoritative CI ladder. `mise run ci` is release-proof.

## Hard Laws (Spec-05)
1. **Tool Law:** Web is pipeline-local; no `TOOL_FETCH` or `TOOL_SEARCH` in runtime.
2. **Boundary Law:** `final.json` stays compact `{ok,results,output,meta}`. Answer/Citations stay in `output`.
3. **Budget Law:** `serp_k<=8`, `per_domain_cap=2`, `chunk<=800c`, `N_chunks<=40`.
4. **Deterministic Law:** No `time.time()`, no `random.random()`, no `hash()` in eval. Use `SequenceClock` + `sha256`.
5. **Schema Law:** Explicit artifact paths only. `scripts.schema_lint` MUST receive `--web-output`, `--web-trace`, etc.

## The Winner (Frozen Plan)
Winner-lock active: `(B1a,B2a,B3b,B4b,B5a)`
- **B1a (Provider):** `searx_json` (via `urllib`).
- **B2a (Cache):** `sqlite` (WAL, atomic).
- **B3b (Parser):** `fallback_extract` (Regex-based windowing + boilerplate kill).
- **B4b (Scoring):** `bm25` (Query-linked relevance).
- **B5a (Anchor):** `quote_anchor` (Verifiable quote <= 25 words).

## Metrics (Lexicographic Priority)
`metric_tuple = (acc, -bytes, -chunks, -fetches, cache_hit)`
- `acc`: Evidence-linked accuracy (citation coverage + tiny bonus).
- `-bytes`: Context density. Smaller is better.

---

## Walkthrough 1: Deterministic Web Smoke
Goal: Produce verifiable artifacts from fixture data.

```bash
# 1. Generate smoke artifacts
python -m scripts.web_fixture_smoke

# 2. Inspect the boundary payload
cat out/web_smoke/web_output.json
# Expect: {"answer": "...", "citations": [...], "trace_ptr": "out/web_smoke/web_trace.ndjson"}

# 3. Verify the trace
cat out/web_smoke/web_trace.ndjson
# Expect: NDJSON frames [fetch_call, fetch_result, ...] with seq incrementing.

# 4. Strict Schema Validation
python -m scripts.schema_lint \
  --web-output out/web_smoke/web_output.json \
  --web-trace out/web_smoke/web_trace.ndjson \
  --citation out/web_smoke/citation.ndjson
```

## Walkthrough 2: Matrix Evaluation & Winner Proof
Goal: Prove the frozen winner is still the metric champion.

```bash
# 1. Run full matrix eval
python -m scripts.web_eval

# 2. Check the canonical verdict
cat out/web_eval.canonical.json
# Expect: {"winner_id": "(B1a,B2a,B3b,B4b,B5a)", "metrics": {...}}

# 3. Verify no silent skips
grep "unsupported_plan" out/web_eval.json | wc -l
# Unsupported losers (B3a, B2b, etc.) MUST emit typed error rows, not disappear.
```

## Walkthrough 3: Live Replay Parity
Goal: Ensure web substrate hasn't corrupted runtime determinism.

```bash
# 1. Run authoritative parity check
python -m scripts.replay_check
# Expect: "OK"
# If failure: LIVE vs REPLAY final.json hash mismatch. INVESTIGATE IMMEDIATELY.
```

---

## Component Guide (Tacit Knowledge)

### `WebPipeline` (The Orchestrator)
- **Fanout:** Uses `asyncio.Semaphore(plan.max_parallel_fetch)` + `asyncio.gather`.
- **Order:** Merges results in stable order (Source Rank -> Doc Rank).
- **Fail-Lane:** Typed error accounting. `No search results` is a valid `final.output`, not a crash.

### `Fetcher` Hierarchy
- `RealDocFetcher`: `urllib` + `gzip` + `post-decompress-cap`. Hard cap at 5MB.
- `FixtureDocFetcher`: Manifest-based. Maps URLs to local body files. Use for all unit tests.
- `CachedDocFetcher`: Manages 304 (Not Modified) logic and SHA256-body deduplication.

### `ETL` Pipeline
- `fallback_extract`: Strips tags -> Regex windowing -> 600c chunks.
- `kill_boilerplate`: Global counter across all fetched chunks. Kills chunks appearing in >=3 docs.
- `score_bm25`: Ranks chunks by query token overlap.
- `select_top_chunks`: Global budget clamp (N=40).

---

## Extension Checklist (How to add a feature)
1. **Reproduction:** Add a failing test in `tests/test_web_*.py`.
2. **Invariant:** Update `spec-05/11-invariant-matrix.jsonl` with the new requirement.
3. **Patch:** Implement in `pirml/web/`.
4. **Fast:** `mise run fast` MUST reject within <3s.
5. **CI:** `mise run ci` MUST pass full ladder.
6. **Handoff:** Update `spec-0/00-learnings.jsonl` and this document.

## Triage Cheat Sheet
- **Dangling Pointer:** `trace_ptr` exists but `web_trace.ndjson` is missing. Check `WebPipeline.run` writer.
- **Hash-Seed Drift:** Metrics change across runs. Ensure `evidence_accuracy` uses `deterministic_jitter`.
- **Schema Red:** `additionalProperties: false` violation. Check `pirml/contracts/*.schema.json`.
- **Replay Red:** Web side-effect leaking into runtime state. Check `clock` or `tracer` sharing.
