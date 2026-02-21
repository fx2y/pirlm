# 005: Spec-05 Web Substrate Live E2E Operator Course

Date baseline: `2026-02-21`.
Mode: ultra-opinionated, proof-first, artifact-first.

## 0) Doctrine (read once, obey forever)
1. L0 is frozen. Runtime tools stay `{echo,readfile,bash}`.
2. Web is L1 pipeline-local (`pirml/web/*`), never runtime tool growth.
3. Final boundary compactness is law: runtime `final.json={ok,results,output?,meta?}` only.
4. Web payload lives in `output`/artifacts (`web_output.json`, `web_trace*.ndjson`), not raw HTML in boundary.
5. Gate authority is `mise run ci`; `fast` is reject-signal only.
6. Replay truth outranks live intuition; parity drift is release blocker.
7. Fail-closed beats convenience: unknown plan/provider/cache/variant => typed error.

## 1) What is shipped (current reality)
1. Cycle state: `C0..C7 done`.
2. Winner lock: `(B1a,B2a,B3b,B4b,B5a)` = `(searx_json,sqlite,fallback_extract,bm25,quote_anchor)`.
3. Losers purged: `B2b/B3a/B4a` removed from runtime path.
4. Hard budgets: `serp_k<=8`, `per_domain_cap=2`, `chunk<=800c`, `N_chunks<=40`, bounded fetch fanout.
5. Winner rule: lexicographic max on `(acc,-bytes,-chunks,-fetches,cache_hit)`.
6. Current canonical winner proof:
`{"winner_id":"(B1a,B2a,B3b,B4b,B5a)","winner_metrics":{"acc":0.7954,"bytes_q":213,"cache_hit":0.0,"chunks_q":1,"fetches_q":1}}`

## 2) Mental model (tacit)
1. Pipeline: `Q -> search -> rank/diversify -> fetch -> extract -> boilerplate-kill -> bm25 -> topN -> join -> cite -> output`.
2. Evidence is files, not logs:
`out/web_smoke/{web_output.json,web_trace.ndjson,serp.ndjson,doc.ndjson,extract.ndjson,citation.ndjson,eval.ndjson}`.
3. C6 guardrails:
`scripts.web_eval` runs all declared matrix rows; unsupported rows are typed `ok=false`, never silently skipped.
4. C7 guardrails:
unique trace filenames per run, empty-result graceful finals, concise answer synthesis (first sentence top chunks).

## 3) 12-minute value proof (copy/paste)
```bash
set -euo pipefail
BASE=out/showcase/005/demo
rm -rf "$BASE"
mkdir -p "$BASE"

# 1) deterministic preflight
mise run fast

# 2) deterministic web e2e artifact bundle
python -m scripts.web_fixture_smoke
cp -R out/web_smoke "$BASE/web_smoke"

# 3) strict explicit-path schema proof (no out/** crawl)
python -m scripts.schema_lint \
  --serp "$BASE/web_smoke/serp.ndjson" \
  --doc "$BASE/web_smoke/doc.ndjson" \
  --extract "$BASE/web_smoke/extract.ndjson" \
  --citation "$BASE/web_smoke/citation.ndjson" \
  --web-eval "$BASE/web_smoke/eval.ndjson" \
  --web-output "$BASE/web_smoke/web_output.json" \
  --web-trace "$BASE/web_smoke/web_trace.ndjson"

# 4) matrix + deterministic winner
python -m scripts.web_eval
cp out/web_eval.json out/web_eval.canonical.json "$BASE/"
cat "$BASE/web_eval.canonical.json"

# 5) substrate integrity
python -m scripts.replay_check

# 6) authority gate
mise run ci
```

Pass if:
1. `web_output.json` has only `{answer,citations,trace_ptr}`.
2. `trace_ptr` resolves to existing `web_trace*.ndjson`.
3. `out/web_eval.canonical.json` winner is `(B1a,B2a,B3b,B4b,B5a)`.
4. `replay_check` prints `OK`.
5. `mise run ci` is green.

## 4) Live integration lanes
Lane A (already verified here): live fetch integration (`RealDocFetcher`) via `scripts.web_smoke`.
```bash
python -m scripts.web_smoke
```
Expected: `Smoke success: ...` and non-zero citation count.

Lane B (true live search + live fetch): needs reachable Searx endpoint.
```bash
SEARX_BASE_URL='http://<your-searx-host>:<port>' python - <<'PY'
import asyncio
from pathlib import Path
from pirml.clock import SequenceClock
from pirml.web.cache.sqlite import SqliteCache
from pirml.web.fetch import CachedDocFetcher, RealDocFetcher
from pirml.web.pipeline import WebPipeline, WebPlan
from pirml.web.search import provider_factory
from pirml.web.trace import WebTracer

async def main():
    provider = provider_factory("searx_json", {})
    fetcher = CachedDocFetcher(RealDocFetcher(), SqliteCache(Path(".tmp/web_live.sqlite")))
    pipe = WebPipeline(
        provider=provider,
        fetcher=fetcher,
        clock=SequenceClock.from_env(),
        tracer=WebTracer(),
        trace_dir=Path("out/web_live"),
    )
    final = await pipe.run(
        "OpenAI API rate limits",
        WebPlan(provider="searx_json", cache="sqlite", serp_k=4, max_chunks=12, max_parallel_fetch=2),
        trace_filename="web_trace_live.ndjson",
    )
    print(final["answer"])
    print("citations=", len(final["citations"]))
    print("trace_ptr=", final["trace_ptr"])

asyncio.run(main())
PY
```
If this fails, fix endpoint reachability first; do not mutate pipeline laws.

## 5) Walkthroughs by role
### Product-owner track (value + risk)
```bash
mise run fast
python -m scripts.web_fixture_smoke
cat out/web_smoke/web_output.json
cat out/web_smoke/web_trace.ndjson | head -n 8
python -m scripts.schema_lint --web-output out/web_smoke/web_output.json --web-trace out/web_smoke/web_trace.ndjson --citation out/web_smoke/citation.ndjson
python -m scripts.web_eval
cat out/web_eval.canonical.json
python -m scripts.replay_check
```
Decision sentence:
Spec-05 adds web evidence density at L1 while keeping L0 replay contracts unchanged.

### QA track (invariant closure, no vibes)
```bash
python -m unittest -q tests.test_urlnorm
python -m unittest -q tests.test_web_search
python -m unittest -q tests.test_web_fetch_cache
python -m unittest -q tests.test_web_etl
python -m unittest -q tests.test_web_cite
python -m unittest -q tests.test_web_eval
python -m unittest -q tests.test_web_c0 tests.test_web_c1 tests.test_web_c2
python -m unittest -q tests.test_web_contracts tests.test_web_golden tests.test_schema_lint
mise run ci
```
Stop-ship reds:
replay parity drift, schema strictness drift, silent fallback, ordering nondeterminism, missing artifact pointers.

### FDE track (incident triage)
```bash
python -m scripts.web_fixture_smoke
cat out/web_smoke/web_output.json
cat out/web_smoke/web_trace.ndjson
python -m scripts.web_eval
cat out/web_eval.json
python -m scripts.replay_check
mise run ci
```
Escalate only on authoritative red (`ci`/replay/schema), not narrative discomfort.

## 6) Scenario bank (micro-drills)
S01 baseline preflight
```bash
mise run fast
```

S02 deterministic web bundle
```bash
python -m scripts.web_fixture_smoke
```

S03 explicit schema contract
```bash
python -m scripts.schema_lint --serp out/web_smoke/serp.ndjson --doc out/web_smoke/doc.ndjson --extract out/web_smoke/extract.ndjson --citation out/web_smoke/citation.ndjson --web-eval out/web_smoke/eval.ndjson --web-output out/web_smoke/web_output.json --web-trace out/web_smoke/web_trace.ndjson
```

S04 winner proof
```bash
python -m scripts.web_eval && cat out/web_eval.canonical.json
```

S05 replay integrity
```bash
python -m scripts.replay_check
```

S06 full release gate
```bash
mise run ci
```

S07 live fetch smoke
```bash
python -m scripts.web_smoke
```

S08 URL normalization contracts
```bash
python -m unittest -q tests.test_urlnorm
```

S09 deterministic SERP prune + caps
```bash
python -m unittest -q tests.test_web_search.WebSearchTests.test_serp_pruning_is_deterministic_and_capped
```

S10 fail-closed provider factory
```bash
python -m unittest -q tests.test_web_search.WebSearchTests.test_provider_factory_unknown_fails_closed
```

S11 decode/cap robustness
```bash
python -m unittest -q tests.test_web_fetch_cache.WebFetchCacheTests.test_gzip_and_charset_decode_pass tests.test_web_fetch_cache.WebFetchCacheTests.test_post_decompress_cap_is_enforced
```

S12 cache integrity
```bash
python -m unittest -q tests.test_web_fetch_cache.WebFetchCacheTests.test_cache_304_and_sha256_dedup tests.test_web_fetch_cache.WebFetchCacheTests.test_cache_body_sha_matches_stored_body_bytes
```

S13 ETL fail lane
```bash
python -m unittest -q tests.test_web_etl.WebETLTests.test_global_selector_fails_on_zero_budget
```

S14 citation fail lane
```bash
python -m unittest -q tests.test_web_cite.WebCiteTests.test_citation_fails_on_missing_chunk
```

S15 eval plan parse fail lane
```bash
python -m unittest -q tests.test_web_eval.WebEvalTests.test_resolve_plan_rejects_invalid_shape
```

S16 unsupported variant rejection
```bash
python -m unittest -q tests.test_web_eval.WebEvalTests.test_resolve_plan_rejects_unsupported_variants
```

S17 deterministic winner rule
```bash
python -m unittest -q tests.test_web_eval.WebEvalTests.test_winner_selection_is_deterministic
```

S18 evidence-linked acc (not synthetic hash)
```bash
python -m unittest -q tests.test_web_eval.WebEvalTests.test_evidence_accuracy_depends_on_citations
```

S19 strict web schema files
```bash
python -m unittest -q tests.test_web_contracts
```

S20 golden byte drift guard
```bash
python -m unittest -q tests.test_web_golden
```

S21 explicit-path schema behavior
```bash
python -m unittest -q tests.test_schema_lint.TestSchemaLintCLI.test_web_artifacts_validate_with_explicit_paths
```

S22 schema fail drill (wrong artifact type)
```bash
python -m scripts.schema_lint --citation tests/fixtures/web/responses.json; echo $?
```

S23 runtime tool surface freeze proof
```bash
python -m unittest -q tests.test_web_c0.WebC0Tests.test_runtime_tool_surface_remains_frozen
```

S24 cycle hardening suite
```bash
python -m unittest -q tests.test_web_c0 tests.test_web_c1 tests.test_web_c2
```

## 7) Debug map (symptom -> first move)
1. Winner missing: `cat out/web_eval.json`; confirm at least one `ok=true` row.
2. Schema red: verify each explicit path exists; then check `trace_ptr` target is included in `--web-trace`.
3. Ranking drift: run `tests.test_urlnorm` + `tests.test_web_search`; inspect tie-break key and domain cap.
4. Cache mismatch: run `tests.test_web_fetch_cache`; verify sha computed from stored bytes.
5. Citation unverifiable: run `tests.test_web_cite`; verify quote is resolvable and `<=25` words.
6. Replay mismatch: `python -m scripts.replay_check`; treat as blocker, not warning.

## 8) Anti-pattern blacklist
1. Re-introducing loser variants as fallback.
2. Wall-clock/random entropy in canonical artifacts.
3. Raw HTML crossing boundary.
4. Broad exception swallow on boundary paths.
5. Relying on `fast` for release.
6. Hidden schema scan of `out/**`.

## 9) Release checklist (strict)
1. `mise run fast`
2. `python -m scripts.web_fixture_smoke`
3. explicit `schema_lint` over web artifacts
4. `python -m scripts.web_eval` + canonical winner check
5. `python -m scripts.replay_check`
6. `mise run ci`

If any item is red: demo-only, merge blocked.
