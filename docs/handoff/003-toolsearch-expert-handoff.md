# Handoff: ToolSearch Stack on PirLM Substrate (Spec-03)

**Objective**: Deterministic tool selection with context compression (V<<G) while preserving Sprint-1 substrate invariants.

## 1. Thesis & Mental Model
*   **Substrate (L0)**: Executes `{echo, readfile, bash}`. Protocol is NDJSON-only, 3-op `{call, result, final}`. Frozen.
*   **ToolSearch (L1)**: Metadata-only selection layer. Catalogues `tools/*.json`. BM25 + Regex.
*   **Compression**: Selected-only render reduces context by >99% (Proof: `out/toolsearch_tokens.json`).

## 2. Substrate Laws (Do Not Mutate)
*   `H1` **Protocol**: stdout is NDJSON-only. stderr is diagnostics-only.
*   `H2` **Algebra**: Exactly one `final` and it must be the last frame.
*   `H3` **IDs**: `c%05d` monotonic starting at `c00001`.
*   `H4` **Truncation**: Only `result` frames may set `truncated: true`. Recompute hashes post-truncation.
*   `H5` **Replay**: `PIRML_BLOCK_TOOLS=1` must achieve bit-identical `final.json` hash parity.

## 3. ToolSearch Constitutional Contracts
*   `C1` **Manifest**: Dotted name (<=64), >=3 sentences description (must incl. NOT-use guidance), validated examples.
*   `C2` **Catalog**: 3-5 hot tools required. All-deferred is a hard-fail (`all_deferred`).
*   `C3` **Search**: BM25/Regex over `{name, tags, desc, schema_props}`. Output is capped at top-k=5 refs.
*   `C4` **Determinism**: Identical query+catalog => byte-identical ordered results (Tie-break: `-score, hot, args, name`).
*   `C5` **Hydration**: Selected-only expansion. Missing reference raises `HydrationError(missing_ref)`.
*   `C6` **Policy**: `server_toolsearch + include_examples` is `invalid_policy_combo`. Fail fast.

## 4. Operator Walkthroughs

### PO: Business Value Proof
```bash
# Generate evidence artifacts
python -m scripts.tool_search_bench
# Verify context reduction
cat out/toolsearch_tokens.json # Goal: reduction_pct > 90%
# Verify performance (p50 < 15ms)
cat out/toolsearch_bench.canonical.json
```

### QA: Invariant Stress-Test
```bash
# 1. Total-order stability check
python -c "from pirml.toolsearch.loader import load_catalog; from pirml.toolsearch.search import search_tools; cat=load_catalog('tests/fixtures/toolsearch/catalog',strict=True); r1=search_tools(cat,'file',k=3); r2=search_tools(cat,'file',k=3); assert r1==r2"
# 2. Strict loader duplicate check
python -m unittest -q tests.test_toolsearch_lint.TestToolSearchLint.test_strict_loader
# 3. Regex failure taxonomy check
python -m unittest -q tests.test_toolsearch_search.TestToolSearch.test_regex_invalid_pattern
```

### FDE: Incident Response (Replay)
```bash
# 1. Capture live trace
python -m pirml --prog tests/prog_parallel.py --out-dir out/triage/live
# 2. Execute replay (tools blocked)
PIRML_BLOCK_TOOLS=1 python -m pirml --prog tests/prog_parallel.py --replay out/triage/live/trace.ndjson --out-dir out/triage/replay
# 3. Proof of parity
sha256sum out/triage/live/final.json out/triage/replay/final.json # Must match
```

## 5. Developer Course (Step-by-Step)

### Step 1: Manifest Authoring
Create `tools/my_tool.json`:
```json
{
  "name": "svc.my_tool",
  "description": "Does X. Use for Y. When NOT to use: avoid for Z.",
  "input_schema": {"type": "object", "properties": {"a": {"type": "string"}}},
  "defer_loading": true
}
```

### Step 2: Quality Gate (Lint)
```bash
python -m scripts.tool_manifest_lint --tools-dir tools
# RC=0 => Pass. Error categories: M1 (name), M2 (desc), M3 (schema), schema (keys).
```

### Step 3: Search Integration
```python
from pirml.toolsearch.loader import load_catalog, load_selected
from pirml.toolsearch.search import search_tools
from pirml.toolsearch.render import render_selected_tools

cat = load_catalog("tools", strict=True)
refs = search_tools(cat, "do X", k=3)
selected = load_selected(refs, "tools")
prompt_context = render_selected_tools(selected)
```

### Step 4: Verification
```bash
mise run fast  # Inner-loop unit tests (<3s)
mise run ci    # Full gate (fmt > lint > types > unit > proto > trace > schemas > replay)
```

## 6. Performance & Budget (2026-02-20)
*   **Index Build**: ~56ms (Target: 50ms). Status: **FAIL** in canonical bench on slow hosts.
*   **Search p50**: ~14ms (Target: 15ms). Status: **PASS**.
*   **Caches**: Content-hashed (`catalog_hash`). Immutability via tuple storage.

## 7. Anti-patterns (The "Don'ts")
*   `X0` Do **NOT** print ToolSearch diagnostics to `stdout`. Use `stderr` or artifacts.
*   `X1` Do **NOT** expand the whole catalog for the LLM. Only `hydrate_selected`.
*   `X2` Do **NOT** mutate the runtime `ToolRegistry` with search manifests. Keep metadata separate from executor.
*   `X3` Do **NOT** soften typed errors (e.g., `invalid_pattern`) into silent fallbacks. Fail fast.
