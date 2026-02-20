# 003: ToolSearch Live E2E Operator Course

Date baseline: `2026-02-20`.
Mode: contract-first, zero-vibes.

## 0) Non-negotiables
1. Substrate stays frozen: runtime executes only `echo|readfile|bash`.
2. ToolSearch is metadata-only selection; never expands runtime tool adapters.
3. `stdout` from `python -m pirml` is NDJSON protocol only; diagnostics belong to `stderr`/artifacts.
4. Protocol algebra is closed: `call|result|final`; exactly one `final`; `final` last.
5. Replay truth > live intuition. If parity fails, live run is untrusted.
6. Release confidence is `mise run ci` + replay parity + schema/proto/trace lint.

## 1) Mental model (carry forever)
1. L0 runtime: deterministic call execution, trace, replay, exit codes.
2. L1 ToolSearch: strict manifests -> deterministic top-k refs -> selected-only hydration -> prompt render.
3. L1 may evolve. L0 contracts do not.

## 2) 15-minute full showcase (copy/paste)
```bash
set -euo pipefail
BASE=out/showcase/003/demo
rm -rf "$BASE"
mkdir -p "$BASE"

# A) Contract preflight
mise run fast
python -m scripts.tool_manifest_lint --tools-dir tools

# B) Value proof: perf + context compression
python -m scripts.tool_search_bench
cat out/toolsearch_bench.canonical.json
cat out/toolsearch_tokens.json

# C) Selection -> hydration -> render (client-side)
python -c "import json;from pirml.toolsearch.loader import load_catalog,load_selected;from pirml.toolsearch.search import search_tools;from pirml.toolsearch.render import render_selected_tools;cat=load_catalog('tests/fixtures/toolsearch/catalog',strict=True);refs=search_tools(cat,'list files',k=3);sel=load_selected(refs[:2],'tests/fixtures/toolsearch/catalog');print(json.dumps({'refs':refs,'render':render_selected_tools(sel)},sort_keys=True,indent=2))"

# D) Live runtime integration
python -m pirml --prog tests/prog_ok.py --out-dir "$BASE/live" > "$BASE/live.stdout.ndjson"
python -m scripts.proto_lint --trace "$BASE/live/trace.ndjson"
python -m scripts.trace_lint --trace "$BASE/live/trace.ndjson"

# E) Replay with tools blocked + parity proof
PIRML_BLOCK_TOOLS=1 python -m pirml --prog tests/prog_ok.py --replay "$BASE/live/trace.ndjson" --out-dir "$BASE/replay" > "$BASE/replay.stdout.ndjson"
sha256sum "$BASE/live/final.json" "$BASE/replay/final.json"

# F) Failure semantics drill
set +e
python -m pirml --prog tests/prog_fail.py --out-dir "$BASE/fail" > "$BASE/fail.stdout.ndjson"; echo "rc_fail=$?"
python -m pirml --prog tests/prog_ok.py --timeout 0.001 --out-dir "$BASE/timeout" > "$BASE/timeout.stdout.ndjson"; echo "rc_timeout=$?"
set -e

# G) Truncation contract drill
python -m pirml --prog tests/prog_large.py --max-line-bytes 1024 --out-dir "$BASE/trunc" > "$BASE/trunc.stdout.ndjson"
rg -n '"truncated":true|"truncated_bytes":' "$BASE/trunc/trace.ndjson"
```

Expected (current repo state):
1. `out/toolsearch_bench.canonical.json`: `"status":"PASS"`.
2. `out/toolsearch_tokens.json`: `reduction_pct` near `99.51`.
3. Selection demo refs ordered: `svc.list_files`, `svc.read_file`, `core.echo`.
4. Live/replay final hashes equal (observed: `356564934c23925f...` for `prog_ok`).
5. Exit codes: `prog_fail` => `1`; forced timeout => `2`.
6. Truncation is explicit and only on `result` frames.

## 3) Walkthrough track: Product Owner
Goal: prove value without substrate risk.

```bash
python -m scripts.tool_search_bench
cat out/toolsearch_bench.canonical.json
cat out/toolsearch_tokens.json
python -c "import json;from pirml.toolsearch.loader import load_catalog,load_selected;from pirml.toolsearch.search import search_tools;from pirml.toolsearch.render import render_selected_tools;cat=load_catalog('tests/fixtures/toolsearch/catalog',strict=True);refs=search_tools(cat,'list files',k=3);print(json.dumps({'refs':refs,'render':render_selected_tools(load_selected(refs[:2],'tests/fixtures/toolsearch/catalog'))},sort_keys=True,indent=2))"
python -m pirml --prog tests/prog_ok.py --out-dir out/showcase/003/po/live > out/showcase/003/po/live.stdout.ndjson
PIRML_BLOCK_TOOLS=1 python -m pirml --prog tests/prog_ok.py --replay out/showcase/003/po/live/trace.ndjson --out-dir out/showcase/003/po/replay > out/showcase/003/po/replay.stdout.ndjson
sha256sum out/showcase/003/po/live/final.json out/showcase/003/po/replay/final.json
```

Narrative:
1. Context shrinks hard (`selected_bytes << full_bytes`).
2. Runtime behavior remains unchanged and replay-auditable.

## 4) Walkthrough track: QA
Goal: prove each invariant with pass/fail tests.

```bash
python -m unittest -q tests.test_toolsearch_lint tests.test_toolsearch_search tests.test_toolsearch_hydrate_render tests.test_toolsearch_bets tests.test_toolsearch_golden
python -m unittest -q tests.test_protocol tests.test_replay
python -m scripts.tool_manifest_lint --tools-dir tools
python -m pirml --prog tests/prog_ok.py --out-dir out/showcase/003/qa/live > out/showcase/003/qa/live.stdout.ndjson
python -m scripts.proto_lint --trace out/showcase/003/qa/live/trace.ndjson
python -m scripts.trace_lint --trace out/showcase/003/qa/live/trace.ndjson
python -m scripts.schema_lint
python -m scripts.replay_check
```

Stop-ship:
1. Manifest strictness drift.
2. Search ranking nondeterminism.
3. Missing typed errors (`invalid_pattern`, `pattern_too_long`, `all_deferred`, `missing_ref`, `invalid_policy_combo`).
4. Any replay parity mismatch.

## 5) Walkthrough track: FDE
Goal: deterministic incident loop under pressure.

```bash
BASE=out/showcase/003/fde
rm -rf "$BASE"
mkdir -p "$BASE"
python -m pirml --prog tests/prog_parallel.py --out-dir "$BASE/parallel" > "$BASE/parallel.stdout.ndjson"
PIRML_BLOCK_TOOLS=1 python -m pirml --prog tests/prog_parallel.py --replay "$BASE/parallel/trace.ndjson" --out-dir "$BASE/parallel-replay" > "$BASE/parallel-replay.stdout.ndjson"
sha256sum "$BASE/parallel/final.json" "$BASE/parallel-replay/final.json"
python -m pirml --prog tests/prog_large.py --max-line-bytes 1024 --out-dir "$BASE/trunc" > "$BASE/trunc.stdout.ndjson"
rg -n '"truncated":true|"truncated_bytes":' "$BASE/trunc/trace.ndjson"
tail -n 2 "$BASE/parallel/metrics.csv"
python -c "from pirml.toolsearch.loader import load_catalog;from pirml.toolsearch.search import search_tools;cat=load_catalog('tests/fixtures/toolsearch/catalog',strict=True);runs=[search_tools(cat,'read content',k=3) for _ in range(3)];print(runs);assert runs[0]==runs[1]==runs[2]"
```

Interpretation:
1. Parallel run parity hash match => stable execution+replay path.
2. `metrics.csv` is triage row (`final_ok,trace_sha,final_sha`).
3. Search x3 identity proves deterministic ranking on same inputs.

## 6) Scenario library (micro-drills)
S1. Preflight gate:
```bash
mise run fast
```

S2. Full release gate:
```bash
mise run ci
```

S3. Manifest lint only:
```bash
python -m scripts.tool_manifest_lint --tools-dir tools
```

S4. Bench + token artifact refresh:
```bash
python -m scripts.tool_search_bench && cat out/toolsearch_bench.canonical.json && cat out/toolsearch_tokens.json
```

S5. Deterministic selection smoke:
```bash
python -c "from pirml.toolsearch.loader import load_catalog;from pirml.toolsearch.search import search_tools;cat=load_catalog('tests/fixtures/toolsearch/catalog',strict=True);print([search_tools(cat,'list files',k=3) for _ in range(3)])"
```

S6. Invalid regex taxonomy:
```bash
python -m unittest -q tests.test_toolsearch_search.TestToolSearch.test_regex_invalid_pattern tests.test_toolsearch_search.TestToolSearch.test_regex_pattern_too_long
```

S7. Hydration missing-ref fail:
```bash
python -m unittest -q tests.test_toolsearch_hydrate_render.TestHydrateRender.test_hydrate_tools_missing
```

S8. Policy guard fail (`server_search + examples`):
```bash
python -m unittest -q tests.test_toolsearch_hydrate_render.TestHydrateRender.test_enforce_client_search_mode_fail
```

S9. Golden ranking stability:
```bash
python -m unittest -q tests.test_toolsearch_golden.TestToolSearchGolden.test_search_ranking_golden
```

S10. Golden render stability:
```bash
python -m unittest -q tests.test_toolsearch_golden.TestToolSearchGolden.test_prompt_render_golden
```

S11. Leak-strip contract at final boundary:
```bash
python -m pirml --prog tests/prog_leak.py --out-dir out/showcase/003/s11 > out/showcase/003/s11.stdout.ndjson
cat out/showcase/003/s11/final.json
```
Expect: row keeps `{id,ok,tool}` only; extra keys dropped.

S12. Protocol lint on live artifact:
```bash
python -m scripts.proto_lint --trace out/showcase/003/s11/trace.ndjson
```

S13. Replay smoke:
```bash
python -m scripts.replay_check
```

S14. Typed business failure:
```bash
python -m pirml --prog tests/prog_fail.py --out-dir out/showcase/003/s14 > out/showcase/003/s14.stdout.ndjson; echo $?
```

S15. Integrity failure via timeout:
```bash
python -m pirml --prog tests/prog_ok.py --timeout 0.001 --out-dir out/showcase/003/s15 > out/showcase/003/s15.stdout.ndjson; echo $?
```

## 7) Triage map (fastest path)
1. `ranking drift`: run golden tests first; inspect tie-break key and exact-name boost path.
2. `manifest red`: run `tool_manifest_lint`; fix schema/name/description/examples/hot-count.
3. `invalid_policy_combo`: disable server-side search when examples are included.
4. `cache weirdness`: `python -c "from pirml.runtime.search import clear_caches;clear_caches();print('cleared')"` then rerun x3.
5. `ci types red`: treat as release blocker; patch signatures/types, not casts-first.
6. `replay mismatch`: compare live/replay final hashes, then inspect `final.meta.replay_match`.

## 8) Anti-patterns (ban list)
1. Expanding runtime ToolRegistry from manifests.
2. Printing ToolSearch diagnostics to runtime stdout.
3. Hydrating full catalog for prompts.
4. Downgrading typed errors to warnings.
5. Gating CI on non-canonical bench bytes.
6. Releasing on `fast`-green without `ci` + replay parity.

## 9) Release checklist
1. `mise run fast` green.
2. `python -m scripts.tool_manifest_lint --tools-dir tools` returns `0`.
3. ToolSearch suites (incl golden) green.
4. `out/toolsearch_bench.canonical.json` has `"status":"PASS"`.
5. `python -m scripts.replay_check` prints `OK`.
6. `mise run ci` green.

If any item fails: demo only, not releasable.
