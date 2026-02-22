# 007: Spec-07 UX Shim+Extension+Toolpack Live E2E Operator Course

Date baseline: `2026-02-22`.
Mode: ultra-opinionated, ultra-terse, proof-first, artifact-first.

## 0) Doctrine (break one => stop)
1. `L0` frozen: runtime tools stay `{echo,readfile,bash}`.
2. One execution owner only: `scripts.pirml_run -> pirml.ux.runtime_bridge -> python -m pirml`.
3. `.pirml/*` is projection convenience; storage truth is `out/*` (+`art/*` if present).
4. Runtime stdout is protocol rows only; wrapper diagnostics/errors go stderr/artifacts.
5. `final.json` root is fixed: `{ok,results,output?,meta?}`.
6. Pointer hash law: `runSha=sha256(persisted final bytes)`, never pre-write strings.
7. Optional bets default off (`hybrid`, `headless`) and must typed-return `unsupported` when off.
8. Authority ladder: `mise run fast` (reject), `mise run ci` (ship).
9. Status truth law: trust `spec-0/07-tasks.jsonl`, not shard status labels.

## 1) Reality Snapshot (as-of `2026-02-22`)
1. Status truth (`spec-0/07-tasks.jsonl`): `C0=done`; `C1..C7=partial`; blocker rows `B00..B20=done`.
2. Live shim works: `python -m scripts.pirml_run --prog ... --out-dir ...` emits summary row + pointers.
3. Projection contract works: `.pirml/{trace.ndjson,final.json,artifacts}` are symlinks; non-projection dirs are protected.
4. Replay wrapper works: `python -m scripts.tools.replay ...` delegates to `python -m pirml --replay ...` and enforces `PIRML_BLOCK_TOOLS=1`.
5. Toolpack works: `scripts.tools.open/slice/replay` emit typed JSON errors on fail lanes.
6. Headless works: disabled lane returns typed `unsupported`; enabled lane emits `pirml_summary` rows.
7. Extension contract has live test lanes (`python` + `tsx`); real `pi` runtime is optional for local demo.

## 2) 12-Minute E2E Value Proof (copy/paste)
```bash
set -euo pipefail
BASE=out/showcase/007/demo
rm -rf "$BASE"
mkdir -p "$BASE"

# 1) fast reject gate
mise run fast

# 2) authoritative run via shim
python -m scripts.pirml_run \
  --prog tests/prog_ok.py \
  --out-dir "$BASE/r1" \
  --project-root .

# 3) projection contract
test -L .pirml/trace.ndjson
test -L .pirml/final.json
test -L .pirml/artifacts
ls -l .pirml

# 4) deterministic replay via wrapper
python -m scripts.tools.replay \
  tests/prog_ok.py \
  "$BASE/r1/trace.ndjson" \
  --out-dir "$BASE/replay_r1"

# 5) toolpack contract lane
python -m unittest -q tests.test_spec07_c3_toolpack

# 6) extension/hybrid/headless/shim contracts
python -m unittest -q \
  tests.test_spec07_c1_runtime_shim \
  tests.test_spec07_c2_extension_contract \
  tests.test_spec07_c4_hybrid_tool \
  tests.test_spec07_c5_headless \
  tests.test_spec07_c7_gate_contract \
  tests.test_spec07_c7_schema_pointer_parity
npx tsx tests/test_spec07_c2_extension_contract.ts
npx tsx tests/test_spec07_c4_hybrid_tool.ts

# 7) schema pointer parity + replay authority
python -m scripts.web_fixture_smoke
python -m scripts.schema_lint \
  --web-output out/web_smoke/web_output.json \
  --web-trace out/web_smoke/web_trace.ndjson
python -m scripts.replay_check

# 8) ship authority
mise run ci
```

Pass bar:
1. Step 2 prints JSON summary with `runId/ok/pointer`.
2. Step 3 links resolve and point to latest run artifacts.
3. Step 4 returns `rc=0` and writes replay artifacts.
4. Steps 5-7 all green.
5. Step 8 green in immutable gate order.

## 3) Operator Walkthroughs
### Product Owner (12 min)
```bash
mise run fast
python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/spec07_po_r1 --project-root .
ls -l .pirml
python -m scripts.tools.replay tests/prog_ok.py out/spec07_po_r1/trace.ndjson --out-dir out/spec07_po_replay
python -m scripts.replay_check
```
Message: UX got faster/clearer; trust model unchanged.

### QA (full contract closure)
```bash
python -m unittest -q \
  tests.test_spec07_c0_reconcile \
  tests.test_spec07_c0_declared_failures \
  tests.test_spec07_c1_runtime_shim \
  tests.test_spec07_c2_extension_contract \
  tests.test_spec07_c3_toolpack \
  tests.test_spec07_c4_hybrid_tool \
  tests.test_spec07_c5_headless \
  tests.test_spec07_c7_gate_contract \
  tests.test_spec07_c7_schema_pointer_parity \
  tests.test_spec07_snippets \
  tests.test_protocol \
  tests.test_replay \
  tests.test_schema_lint \
  tests.test_tool_surface_freeze
npx tsx tests/test_spec07_c2_extension_contract.ts
npx tsx tests/test_spec07_c4_hybrid_tool.ts
python -m scripts.replay_check
mise run ci
```
Stop-ship reds: replay drift, pointer non-resolve, stdout pollution, tool-surface growth, fail-open parser paths.

### FDE (incident triage, 8 min)
```bash
mise run fast
python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/spec07_fde_r1 --project-root .
python -m scripts.tools.replay tests/prog_ok.py out/spec07_fde_r1/trace.ndjson --out-dir out/spec07_fde_replay
python -m unittest -q tests.test_spec07_c3_toolpack
python -m scripts.replay_check
```
Escalate on authoritative red only (`ci`/replay/schema), never on “looks weird”.

### Integrator (toolpack-first, no `pi` required)
```bash
python -m unittest -q tests.test_artifact_c1
AID=$(python - <<'PY'
import json
from pathlib import Path
for ln in Path('out/test_artifact_c1/trace.ndjson').read_text().splitlines():
    row=json.loads(ln)
    if row.get('ev')=='put' and row.get('kind')=='raw':
        print(row['aid'])
        break
PY
)
python -m scripts.tools.open "$AID" --art-root out/test_artifact_c1 --mode meta
VID=$(python -m scripts.tools.slice "$AID" '{"op":"lines","a":0,"b":1}' --art-root out/test_artifact_c1)
python -m scripts.tools.open "$VID" --art-root out/test_artifact_c1 --mode text
```
Outcome: you can inspect raw bytes, build deterministic views, and reopen by `VID`.

## 4) Live Integration Lanes
### Lane A: Headless disabled/enabled proof
```bash
python -m pirml.ux.headless <<'EOF'
{"type":"tool_execution_start","tool":"pirml_run","args":{"prog":"tests/prog_ok.py","out-dir":"out/spec07_headless_r1"}}
EOF
echo rc_disabled=$?

PIRML_ENABLE_JSON_HEADLESS=1 python -m pirml.ux.headless <<'EOF'
{"type":"tool_execution_start","tool":"pirml_run","args":{"prog":"tests/prog_ok.py","out-dir":"out/spec07_headless_r1"}}
EOF
echo rc_enabled=$?
```
Expected: first row `type=pirml_error,error.type=unsupported`; second row `type=pirml_summary`.

### Lane B: Optional real `pi` session (only if `pi` installed)
```bash
command -v pi >/dev/null || { echo "pi not installed; use tsx contract lane"; exit 0; }
mkdir -p .pi/extensions
# repo already contains .pi/extensions/pirml
# in pi session:
# /reload
# /pirml run tests/prog_ok.py
# /tree
# /export
```
Expected: one `custom` pointer entry + one short `custom_message`; branch lineage via `parentId`.

### Lane C: Hybrid default-off safety
```bash
python -m unittest -q tests.test_spec07_c4_hybrid_tool
npx tsx tests/test_spec07_c4_hybrid_tool.ts
```
Expected: off by default; enabled only with `PIRML_ENABLE_HYBRID_TOOL=1`.

## 5) Scenario Bank (dense drills)
S01 preflight reject
```bash
mise run fast
```

S02 authority ladder
```bash
mise run ci
```

S03 shim success path
```bash
python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/spec07_s03 --project-root .
```

S04 shim timeout fail lane
```bash
python -m unittest -q tests.test_spec07_c1_runtime_shim.TestSpec07C1RuntimeShim.test_run_once_timeout
```

S05 runtime crash fail lane
```bash
python -m unittest -q tests.test_spec07_c1_runtime_shim.TestSpec07C1RuntimeShim.test_run_once_crash
```

S06 projection safety guard
```bash
python -m unittest -q tests.test_spec07_c1_runtime_shim.TestSpec07C1RuntimeShim.test_projection_refuses_non_projection_directory
```

S07 replay wrapper happy lane
```bash
python -m scripts.tools.replay tests/prog_ok.py out/spec07_s03/trace.ndjson --out-dir out/spec07_s07_replay
```

S08 replay bad-trace typed fail lane
```bash
python -m scripts.tools.replay tests/prog_ok.py out/nope/trace.ndjson --out-dir out/spec07_bad_replay ; echo rc=$?
```

S09 open missing artifact typed fail lane
```bash
python -m scripts.tools.open missing --art-root out/test_artifact_c1 ; echo rc=$?
```

S10 slice invalid-op typed fail lane
```bash
AID=$(python - <<'PY'
import json
from pathlib import Path
for ln in Path('out/test_artifact_c1/trace.ndjson').read_text().splitlines():
    row=json.loads(ln)
    if row.get('ev')=='put' and row.get('kind')=='raw':
        print(row['aid'])
        break
PY
)
python -m scripts.tools.slice "$AID" '{"op":"invalid"}' --art-root out/test_artifact_c1 ; echo rc=$?
```

S11 toolpack full contract suite
```bash
python -m unittest -q tests.test_spec07_c3_toolpack
```

S12 extension python lane
```bash
python -m unittest -q tests.test_spec07_c2_extension_contract
```

S13 extension tsx lane
```bash
npx tsx tests/test_spec07_c2_extension_contract.ts
```

S14 branch lineage invariant
```bash
python -m unittest -q tests.test_spec07_c2_extension_contract
```

S15 context hygiene invariant
```bash
python -m unittest -q tests.test_spec07_c2_extension_contract tests.test_spec06_c6_pointers
```

S16 hybrid default-off invariant
```bash
python -m unittest -q tests.test_spec07_c4_hybrid_tool
```

S17 headless default-off invariant
```bash
python -m unittest -q tests.test_spec07_c5_headless.TestSpec07C5Headless.test_feature_gate_disabled
```

S18 headless event parser invariant
```bash
python -m unittest -q tests.test_spec07_c5_headless.TestSpec07C5Headless.test_event_parsing_success
```

S19 gate-order sentinel
```bash
python -m unittest -q tests.test_spec07_c7_gate_contract
```

S20 schema explicit-arg sentinel
```bash
python -m unittest -q tests.test_schema_lint.TestSchemaLintCLI.test_requires_explicit_artifacts
```

S21 pointer parity sentinel
```bash
python -m unittest -q tests.test_spec07_c7_schema_pointer_parity
```

S22 replay parity sentinel
```bash
python -m scripts.replay_check
```

S23 snippet drift sentinel
```bash
python -m unittest -q tests.test_spec07_snippets tests.test_replay_cli_docs
```

S24 tool-surface freeze sentinel
```bash
python -m unittest -q tests.test_tool_surface_freeze
```

S25 protocol algebra sentinel
```bash
python -m unittest -q tests.test_protocol
```

S26 status truth spot-check
```bash
jq -c 'select(.k=="state")' spec-0/07-tasks.jsonl
```

S27 typed-fail envelope spot-check
```bash
python -m scripts.tools.open missing --art-root art 2> /tmp/spec07_err.json || true
cat /tmp/spec07_err.json
```

S28 projection-only convenience check
```bash
ls -l .pirml
```

S29 web fixture + trace_ptr parity
```bash
python -m scripts.web_fixture_smoke
python -m scripts.schema_lint --web-output out/web_smoke/web_output.json --web-trace out/web_smoke/web_trace.ndjson
```

S30 declared-failures guard
```bash
python -m unittest -q tests.test_spec07_c0_declared_failures
```

S31 C0 contradiction guard
```bash
python -m unittest -q tests.test_spec07_c0_reconcile
```

S32 full spec-07 bundle
```bash
python -m unittest discover -s tests -p 'test_spec07_*.py' -q
npx tsx tests/test_spec07_c2_extension_contract.ts
npx tsx tests/test_spec07_c4_hybrid_tool.ts
python -m scripts.replay_check
python -m scripts.artifact_rebuild --check
mise run ci
```

## 6) Anti-Patterns (ban list)
1. Don’t call `pirml.runtime.exec` or `pirml.runtime.replay` as operator entrypoints.
2. Don’t treat `.pirml` as source-of-truth storage.
3. Don’t put pointer payload blobs in `custom_message` content.
4. Don’t add runtime tools for UX convenience.
5. Don’t run schema checks via implicit `out/**` discovery.
6. Don’t claim `done` from cycle shard labels; update `spec-0/07-tasks.jsonl` only after proof reruns.

## 7) Exit-Code Semantics
1. `0`: success.
2. `1`: business/validation/tool failure.
3. `2`: integrity/config/internal failure.
