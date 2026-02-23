# 004-005: Expert Operator Walkthroughs

## 004: Compiler E2E Mastery (L1 Over L0)

### 1. The L1 Pipeline Drill
```bash
set -euo pipefail
BASE=out/walk/004; rm -rf "$BASE"; mkdir -p "$BASE"
# Input Setup
export PIRML_MODEL_RAW="<<<PROG>>>
import asyncio
from pirml.runtime.rpc import send_final
async def main():
    send_final(True, {'ok':True,'results':[]})
if __name__=='__main__': asyncio.run(main())
<<<CONTRACT>>>
{'tool_deps':[],'io_schema':{'final_schema':{},'citations_schema':{},'trace_ptr':'t'},'budgets':{'max_calls':1,'max_parallel':1,'max_bytes_in':64,'max_bytes_out':64,'timeout_s':2},'assertions':[]}
"
# Compile Pass
python -m scripts.compile --task p --tools-dir tools --out-dir "$BASE/p" --smoke
# Branch Law & Verification
test -f "$BASE/p/prog.py" && test ! -f "$BASE/p/compile_error.json"
# Verify Fail (Import Denied)
PIRML_MODEL_RAW=$(echo "$PIRML_MODEL_RAW" | sed 's/import asyncio/import asyncio, os/') \
python -m scripts.compile --task f --tools-dir tools --out-dir "$BASE/f" --smoke || true
test -f "$BASE/f/compile_error.json" && test ! -f "$BASE/f/prog.py"
```

### 2. Execution/Replay Proof
```bash
# Live Run
python -m pirml --prog "$BASE/p/prog.py" --out-dir "$BASE/live" > "$BASE/live.stdout.ndjson"
# Replay Guard (Tools Blocked)
PIRML_BLOCK_TOOLS=1 python -m pirml --prog "$BASE/p/prog.py" --replay "$BASE/live/trace.ndjson" --out-dir "$BASE/replay"
# Parity Check (Stop-ship if diff)
sha256sum "$BASE/live/final.json" "$BASE/replay/final.json"
# Protocol Integrity
python -m scripts.proto_lint --trace "$BASE/live/trace.ndjson"
```

### 3. Triage
- **Extract Fail:** `cat "$BASE/p/raw.txt"` (check sentinels).
- **Verify Fail:** `jq . "$BASE/f/compile_error.json"` (check `ast_import_denied`).

---

## 005: Web Substrate Mastery (Evidence-First)

### 1. Pipeline Artifact Generation
```bash
# Generate Bundle
python -m scripts.web_fixture_smoke
# Inspect Boundary Compactness
jq . out/web_smoke/web_output.json
# Pointer Resolution
TRACE_PTR=$(jq -r .trace_ptr out/web_smoke/web_output.json)
ls -la "out/web_smoke/$TRACE_PTR"
```

### 2. Matrix Evaluation & Winner Lock
```bash
# Matrix Run
python -m scripts.web_eval
# Winner Lock (Deterministic Ranking)
jq -r .winner_id out/web_eval.canonical.json
# Expected: (B1a,B2a,B3b,B4b,B5a)
# Integrity: No silent skips
grep '"ok":false' out/web_eval.json || echo "All rows accounted"
```

### 3. Schema & Replay Authority
```bash
# Explicit Path Linting (Opinionated: No scans)
python -m scripts.schema_lint \
  --serp out/web_smoke/serp.ndjson \
  --doc out/web_smoke/doc.ndjson \
  --extract out/web_smoke/extract.ndjson \
  --citation out/web_smoke/citation.ndjson \
  --web-output out/web_smoke/web_output.json \
  --web-trace out/web_smoke/web_trace.ndjson
# Replay Authority (Hard Blocker)
python -m scripts.replay_check
```

### 4. Constraints (C6/C7 Guardrails)
- `serp_k <= 8`, `domain_cap=2`.
- `chunk <= 800c`, `N_chunks <= 40`.
- Citation words `<= 25`.

## 5) Release Gate
```bash
mise run fast    # Signal
mise run ci      # Authority
python -m scripts.replay_check
# Final Stance: Zero vibes; proofs only.
```
