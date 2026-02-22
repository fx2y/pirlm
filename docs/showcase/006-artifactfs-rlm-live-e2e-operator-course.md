# 006: Spec-06 ArtifactFS+RLM Live E2E Operator Course

Date baseline: `2026-02-21`.
Mode: ultra-opinionated, proof-first, artifact-first, terse.

## 0) Non-negotiables (break any => stop)
1. `L0` frozen: runtime tool surface stays `{echo,readfile,bash}`.
2. `L1` adds `ArtifactFS/ViewDSL/RLM/Governor`; no `L0` convenience mutation.
3. Protocol algebra: `{call,result,final,custom}`; one `final`; `final` last.
4. Boundary root is fixed: `final.json == {ok,results,output?,meta?}`.
5. Hash stored/emitted bytes only; never pre-transform text.
6. `fast` rejects; `ci` authorizes.
7. Replay parity outranks live intuition.
8. Schema checks are explicit-path only; no hidden `out/**` walks.

## 1) Reality snapshot (current implementation)
1. Status truth (`spec-0/06-tasks.jsonl`): `C0..C7=done`.
2. Design shards may lag (`C4/C6` show `planned`); ignore shard status for ship decisions.
3. Matrix harness (`scripts/spec06_eval.py`) declares 8 plans, implements row:
`(B1a,B2a,B3a,B4b,B5a,B6a,B7b)`.
4. Other matrix rows are explicit `note:"unsupported row (loser/unimplemented)"`.
5. Core evidence paths:
`out/test_artifact_c1/*`, `out/spec06_eval.canonical.json`, `out/bench.json`, `out/ci/{trace.ndjson,final.json}`.

## 2) 15-min value extraction (deterministic, copy/paste)
```bash
set -euo pipefail
BASE=out/showcase/006/demo
rm -rf "$BASE"
mkdir -p "$BASE"

# 0) preflight reject gate
mise run fast

# 1) generate deterministic ArtifactFS fixture
python -m unittest -q tests.test_artifact_c1
cp -R out/test_artifact_c1 "$BASE/art"

# 2) export index + validate artifact schemas
python -m scripts.artifact_rebuild --root "$BASE/art" --export "$BASE/art/meta.ndjson"
python -m scripts.schema_lint --artifact "$BASE/art/meta.ndjson" --artifact-trace "$BASE/art/trace.ndjson"

# 3) parity check (trace+fs -> sqlite rebuild)
python -m scripts.artifact_rebuild --root "$BASE/art" --check

# 4) spec-06 matrix evidence
python -m scripts.spec06_eval --seed 0 --queries tests/fixtures/web/corpus.jsonl
cp out/spec06_eval.canonical.json "$BASE/"
cat "$BASE/spec06_eval.canonical.json"

# 5) hardening signoff (stress + e2e + schema + bench + rebuild)
python -m scripts.artifact_e2e_signoff

# 6) replay trust
python -m scripts.replay_check

# 7) authority gate
mise run ci
```

Pass criteria:
1. `art/meta.ndjson` exists and schema-lints clean.
2. `artifact_rebuild --check` prints `SUCCESS: Parity confirmed`.
3. `spec06_eval.canonical.json` contains implemented row with `note:"winner implemented"`.
4. `artifact_e2e_signoff` prints `HARDENING SIGNOFF SUCCESS`.
5. `replay_check` returns `OK`.
6. `mise run ci` green in strict ladder order.

## 3) Live integration lanes (real network + real e2e)

Lane A: real fetch smoke (network, non-gating).
```bash
python -m scripts.web_smoke
```
Expected: `Smoke success...`; if offline, failure is environmental, not spec drift.

Lane B: live searx search + live fetch + ArtifactFS ingestion.
```bash
SEARX_BASE_URL='http://<searx-host>:<port>' python - <<'PY'
import asyncio, json
from pathlib import Path
from pirml.artifacts import ArtifactStore, default_layout
from pirml.clock import SequenceClock
from pirml.web.cache.sqlite import SqliteCache
from pirml.web.fetch import CachedDocFetcher, RealDocFetcher
from pirml.web.pipeline import WebPipeline, WebPlan
from pirml.web.search import provider_factory
from pirml.web.trace import WebTracer

async def main():
    out = Path("out/showcase/006/live_web")
    out.mkdir(parents=True, exist_ok=True)
    store = ArtifactStore(default_layout(out / "art"))
    pipe = WebPipeline(
        provider=provider_factory("searx_json", {}),
        fetcher=CachedDocFetcher(RealDocFetcher(), SqliteCache(out / "cache.sqlite")),
        clock=SequenceClock.from_env(),
        tracer=WebTracer(),
        trace_dir=out,
        artifact_store=store,
    )
    final = await pipe.run(
        "OpenAI API rate limits",
        WebPlan(provider="searx_json", cache="sqlite", serp_k=4, max_chunks=12, max_parallel_fetch=2),
        trace_filename="web_trace_live.ndjson",
    )
    print(json.dumps(final, indent=2))
    print("raw_artifacts=", len(store.find_by_kind("raw")))

asyncio.run(main())
PY
```
Expected value: live answer+cites+trace pointer + persisted raw artifacts for forensic replay.

Lane C: live RLM pointer channel (`custom`) with opt-in.
```bash
PIRML_EMIT_PI_POINTERS=1 python -m unittest -q \
  tests.test_spec06_c6_pointers.TestSpec06C6Pointers.test_pointer_emission_opt_in
```
Expected: `custom` rows emitted; pointer text excluded from packed context.

## 4) Walkthrough tracks

### Product Owner (12 min, value+risk)
```bash
mise run fast
python -m unittest -q tests.test_artifact_c1 tests.test_web_pipeline_artifact
python -m scripts.artifact_rebuild --root out/test_artifact_c1 --export out/test_artifact_c1/meta.ndjson
python -m scripts.schema_lint --artifact out/test_artifact_c1/meta.ndjson --artifact-trace out/test_artifact_c1/trace.ndjson
python -m scripts.spec06_eval --seed 0 --queries tests/fixtures/web/corpus.jsonl
cat out/spec06_eval.canonical.json
python -m scripts.replay_check
mise run ci
```
Decision line: Spec-06 increases context-efficient reasoning and lineage evidence while preserving `L0` replay/boundary contracts.

### QA (full invariant closure)
```bash
python -m unittest -q \
  tests.test_artifact_fs tests.test_artifact_sqlite tests.test_artifact_rebuild \
  tests.test_view_dsl tests.test_view_materialize \
  tests.test_rlm_kernel tests.test_rlm_history tests.test_recursion_map \
  tests.test_spec06_c4_patterns tests.test_spec06_c4_stress \
  tests.test_spec06_c5_governor tests.test_spec06_c6_pointers \
  tests.test_spec06_c7_hard_end2end tests.test_tool_surface_freeze \
  tests.test_protocol tests.test_replay
python -m scripts.artifact_rebuild --root out/test_artifact_c1 --check
python -m scripts.artifact_e2e_signoff
python -m scripts.replay_check
mise run ci
```
Stop-ship reds: replay drift, schema drift, pointer loss, cap bypass, nondeterministic merge, fail-open parser path.

### FDE (incident triage, 8 min)
```bash
mise run fast
python -m unittest -q tests.test_spec06_c4_patterns tests.test_spec06_c5_governor tests.test_spec06_c6_pointers
python -m scripts.spec06_eval --seed 0 --queries tests/fixtures/web/corpus.jsonl
cat out/spec06_eval.canonical.json
python -m scripts.artifact_rebuild --root out/test_artifact_c1 --check
python -m scripts.replay_check
```
Escalate only on authoritative red (`ci`/replay/schema/parity), not narrative discomfort.

## 5) Scenario bank (dense drills)
S01 preflight reject
```bash
mise run fast
```

S02 authority ladder
```bash
mise run ci
```

S03 ArtifactFS core contracts
```bash
python -m unittest -q tests.test_artifact_c1 tests.test_artifact_fs tests.test_artifact_sqlite
```

S04 10MB ingest proof
```bash
python -m unittest -q tests.test_artifact_c1.TestArtifactC1.test_ingest_10mb
```

S05 CAS path canonicality
```bash
python -m unittest -q tests.test_artifact_paths
```

S06 view-id determinism
```bash
python -m unittest -q tests.test_view_dsl.TestViewDSL.test_view_id_stable_x3
```

S07 fail-closed slice parser
```bash
python -m unittest -q tests.test_view_dsl.TestViewDSL.test_unknown_op_typed_fail
```

S08 invalid span typed fail
```bash
python -m unittest -q tests.test_view_dsl.TestViewDSL.test_invalid_span_typed_fail
```

S09 streaming materializer path
```bash
python -m unittest -q tests.test_view_materialize
```

S10 web->artifact ingestion integration
```bash
python -m unittest -q tests.test_web_pipeline_artifact
```

S11 RLM history meta-only
```bash
python -m unittest -q tests.test_rlm_kernel.TestRlmKernel.test_rlm_history_metadata tests.test_rlm_kernel.TestRlmKernel.test_large_stdout_not_in_history
```

S12 subcall budget enforcement
```bash
python -m unittest -q tests.test_rlm_kernel.TestRlmKernel.test_warn_threshold_emits_stderr tests.test_rlm_kernel.TestRlmKernel.test_rlm_subcall_budget
```

S13 timeout fail lane
```bash
python -m unittest -q tests.test_rlm_kernel.TestRlmKernel.test_rlm_timeout
```

S14 run-scoped state (no bleed)
```bash
python -m unittest -q tests.test_rlm_kernel.TestRlmKernel.test_rlm_state_bleed
```

S15 map->reduce pattern
```bash
python -m unittest -q tests.test_spec06_c4_patterns.TestRlmPatterns.test_map_reduce_pattern
```

S16 targeted retrieval fast path
```bash
python -m unittest -q tests.test_spec06_c4_patterns.TestRlmPatterns.test_targeted_retrieval
```

S17 progressive deepening
```bash
python -m unittest -q tests.test_spec06_c4_patterns.TestRlmPatterns.test_progressive_deepening
```

S18 parent-link lineage
```bash
python -m unittest -q tests.test_spec06_c4_patterns.TestRlmPatterns.test_parent_links
```

S19 parallel merge stability
```bash
python -m unittest -q tests.test_recursion_map
```

S20 governor selector + hard cap
```bash
python -m unittest -q tests.test_spec06_c5_governor.TestGovernor.test_pack_ctx_selection tests.test_spec06_c5_governor.TestKernelGovernor.test_governor_hard_cap_enforcement
```

S21 bulk-off-ctx guard
```bash
python -m unittest -q tests.test_spec06_c5_governor.TestKernelGovernor.test_bulk_off_ctx
```

S22 final projector shape
```bash
python -m unittest -q tests.test_spec06_c5_governor.TestKernelGovernor.test_web_output_projection tests.test_protocol
```

S23 pointer default-off invariant
```bash
python -m unittest -q tests.test_spec06_c6_pointers.TestSpec06C6Pointers.test_pointer_emission_default_off
```

S24 pointer opt-in invariant
```bash
python -m unittest -q tests.test_spec06_c6_pointers.TestSpec06C6Pointers.test_pointer_emission_opt_in
```

S25 no ctx contamination from custom rows
```bash
python -m unittest -q tests.test_spec06_c6_pointers.TestSpec06C6Pointers.test_no_ctx_contamination
```

S26 hostile-flow hard e2e
```bash
python -m unittest -q tests.test_spec06_c7_hard_end2end tests.test_spec06_c4_stress
```

S27 rebuild parity
```bash
python -m scripts.artifact_rebuild --root out/test_artifact_c1 --check
```

S28 schema strictness for artifact rows
```bash
python -m scripts.artifact_rebuild --root out/test_artifact_c1 --export out/test_artifact_c1/meta.ndjson
python -m scripts.schema_lint --artifact out/test_artifact_c1/meta.ndjson --artifact-trace out/test_artifact_c1/trace.ndjson
```

S29 matrix execution evidence
```bash
python -m scripts.spec06_eval --seed 0 --queries tests/fixtures/web/corpus.jsonl
cat out/spec06_eval.canonical.json
```

S30 signoff bundle
```bash
python -m scripts.artifact_e2e_signoff
```

S31 replay parity
```bash
python -m scripts.replay_check
```

S32 runtime tool-surface freeze
```bash
python -m unittest -q tests.test_tool_surface_freeze tests.test_web_c0
```

S33 replay CLI docs correctness
```bash
python -m unittest -q tests.test_replay_cli_docs
```

S34 fail lane: schema wrong file type (`rc=1`)
```bash
set +e
python -m scripts.schema_lint --artifact tests/fixtures/web/corpus.jsonl
echo rc=$?
set -e
```

S35 fail lane: rebuild integrity (`rc=2`)
```bash
python -m unittest -q tests.test_artifact_c1 >/dev/null
victim=$(find out/test_artifact_c1/obj -type f | head -n1); rm -f "$victim"
set +e
python -m scripts.artifact_rebuild --root out/test_artifact_c1 --check
echo rc=$?
set -e
```

S36 perf smoke
```bash
mise run bench
cat out/bench.json
```

## 6) Anti-pattern bans
1. Do not ship from `fast` green.
2. Do not hash pre-normalized/pre-truncation text.
3. Do not allow unknown slice/config/tool variants to pass.
4. Do not inject raw bulk docs into context pack.
5. Do not print diagnostics on protocol stdout.
6. Do not treat replay mismatch as flake.
7. Do not enable pointer spillover by default in core path.

## 7) Release checklist (hard)
1. `mise run fast`
2. `python -m scripts.spec06_eval --seed 0 --queries tests/fixtures/web/corpus.jsonl`
3. `python -m scripts.artifact_rebuild --root out/test_artifact_c1 --check`
4. `python -m scripts.artifact_e2e_signoff`
5. `python -m scripts.replay_check`
6. `mise run ci`
