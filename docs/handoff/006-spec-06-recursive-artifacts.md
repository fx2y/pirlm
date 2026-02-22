# PIRML Recursive Artifacts Handoff (Spec-06)

Mission: Maximize replay-verifiable value (`V<<G`) via off-context recursion. Bulk bytes stay in ArtifactFS; context stays `<=K`.

## Core Thesis
**Store Wide, Read Thin.** Never blit raw docs into reasoning. DERIVE views, SUMMARIZE chunks, PIN lineage. If it isn't in `trace.ndjson` with a resolvable CAS pointer, it's fake.

## The Model
- **L0 (Substrate):** Frozen tool surface (`{echo,readfile,bash}`). Replay-authoritative.
- **L1 (Artifacts/RLM):** Additive stack. CAS storage + Recursive Kernel.
- **G (Gate):** CI ladder. `mise run ci` enforces proto/trace/schema/replay parity.

## Hard Laws (Spec-06)
1. **Tool Law:** `L0` surface is FROZEN. RLM helpers (`get`,`put`,`llm_query`,`amap`) are internal Python, never runtime tools.
2. **CAS Law:** Artifact ID is `sha256(bytes)`. Same bytes -> same ID. Immutable.
3. **View Law:** View ID is `sha256(aid|canonical_spec)`. Derived on-demand, streaming materialized.
4. **Governor Law:** `subcall_warn>20`, `subcall_fail>200`. Context hard-cap `K` enforced by `pack_ctx`.
5. **State Law:** Kernel state (`DOCS`,`CHUNKS`,`SUMS`) is RUN-SCOPED. No cross-run bleed.
6. **Pointer Law:** Optional `custom` op carries lineage pointers. NO pointer text in context candidates.

---

## Walkthrough 1: Artifact Core Proof
Goal: Ingest bulk data and verify its deterministic CAS + Rebuild identity.

```bash
# 1. Populate ArtifactFS sample
python -m unittest -q tests.test_artifact_c1

# 2. Check Rebuild Parity (FS + Trace -> SQLite Index)
python -m scripts.artifact_rebuild --root out/test_artifact_c1 --check
# Expect: SUCCESS: Parity confirmed

# 3. Export & Schema-Lint Metadata
python -m scripts.artifact_rebuild --root out/test_artifact_c1 --export out/test_artifact_c1/meta.ndjson
python -m scripts.schema_lint 
  --artifact out/test_artifact_c1/meta.ndjson 
  --artifact-trace out/test_artifact_c1/trace.ndjson
```

## Walkthrough 2: Recursive Map-Reduce Smoke
Goal: Verify bounded parallel mapping with deterministic order merge.

```bash
# 1. Run pattern tests
python -m unittest -q tests.test_spec06_c4_patterns.TestRlmPatterns.test_map_reduce_pattern

# 2. Inspect lineage in trace (Optional)
grep "put" out/test_artifact_c1/trace.ndjson | grep "kind":"summary""
# Expect: summaries linked to parent aid/vid via "parents" field.
```

## Walkthrough 3: Matrix Winner Signoff
Goal: Prove implementation matches the declared winner row in the spec-06 matrix.

```bash
# 1. Run matrix eval (B1a..B7b winner implemented)
python -m scripts.spec06_eval --seed 0 --queries tests/fixtures/web/corpus.jsonl

# 2. Verify winner in canonical verdict
cat out/spec06_eval.canonical.json
# Expect: "winner_id": "(B1a,B2a,B3a,B4b,B5a,B6a,B7b)"
```

---

## Component Guide (Tacit Knowledge)

### `ArtifactStore` (CAS + Index)
- **Put:** `put_raw` (bytes) or `put_json` (objects). Returns `aid`.
- **Trace:** `trace.ndjson` is the source of truth. `index.sqlite` is a disposable cache.
- **Streaming:** `put_view_stream` handles 10MB+ extractions without OOM.

### `ViewDSL` (Slice + Dice)
- **Specs:** `lines(a,b)`, `regex(pat)`, `bytes(off,lim)`.
- **Materializer:** On-demand materialization to `art/views/<vid>.ndjson`.
- **Fail-Closed:** Invalid specs (e.g. `b < a`) raise `VIEW_SPEC_INVALID`.

### `RlmKernel` (The REPL)
- **Helpers:**
  - `get(id, spec)`: Fetches view text or raw artifact.
  - `put(data, kind, parents)`: Persists new artifact with lineage.
  - `llm_query(p)`: Budgeted subcall (LLM recursion).
  - `amap(prompts)`: Bounded parallel mapping.
- **Cohesion:** `build_rlm_prompt` anchors `P` (original prompt) and `Final` regardless of cost.

### `Governor` (Budget Guard)
- **Token Estimation:** `(len+2)//3` (monotonic upper bound).
- **Ctx Pack:** Sorts by `relevance/cost`. Drops low-value rows until `<= K`.
- **Budget:** `max_iters`, `max_subcalls`, `timeout_s` enforced in `RlmKernel.run`.

---

## Extension Checklist
1. **Failing Test:** `tests/test_spec06_c*`.
2. **Internal Helper:** Add to `pirml/rlm/kernel.py` (helpers dict). NEVER add to `TOOL_` registry.
3. **Budget:** If new helper costs tokens, update `pirml/rlm/governor.py` cost model.
4. **Signoff:** `python -m scripts.artifact_e2e_signoff`.

## Triage Cheat Sheet
- **Integrity Error:** CAS file missing or hash mismatch. Run `artifact_rebuild --check`.
- **Budget Exceeded:** Subcalls > 200. Check recursive depth or infinite loop in generated code.
- **View Missing:** `vid` exists in code but not on FS. View materialization likely failed or was skipped.
- **Replay Red:** Check if `RlmHistory` leaked into global state. Must be run-scoped.
