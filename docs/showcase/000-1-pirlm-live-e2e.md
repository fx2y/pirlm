# 000-1: PIRML Operator Signoff (Unified Live E2E)

This is the definitive operator drill. If this passes, the system is verified for production-grade use.
**Stance**: Proof-first. Replay truth > Live intuition. Zero-vibes.

## 0) Mental Model
1. **L0 (Runtime)**: Deterministic executor. `call|result|final` only. `trace.ndjson` is the source of truth.
2. **L1 (ToolSearch)**: Pareto-optimal context reduction. Picks the right tools, ignores the noise.
3. **L1 (Compiler)**: Rigid extractor + verifier. `{prog.py, contract.json}` or `{compile_error.json}`.
4. **G (Gates)**: `mise run ci` is the only authority.

## 1) Preflight: The Gate Authority
```bash
# Must be clean before any showcase.
mise run fast
```

## 2) The Full Loop (Copy/Paste)
```bash
set -euo pipefail
BASE=out/showcase/signoff
rm -rf "$BASE"
mkdir -p "$BASE"

# A) Tool Discovery & Catalog Proof
# Verify root tools catalog is valid and provides context reduction.
python -m scripts.tool_manifest_lint --tools-dir tools
python -m scripts.tool_search_bench
cat out/toolsearch_bench.canonical.json # Status: PASS

# B) Model Authoring -> Compilation -> Smoke
# We simulate a model response. 
cat > "$BASE/model_response.txt" <<'EOF'
<<<PROG>>>
import asyncio
from pirml.runtime.rpc import send_final
async def main():
    # SERIAL_OK: baseline
    await TOOL_pirml_echo({"text": "Hello PIRML"})
    send_final(True, {"ok": True, "results": [{"id": "c00001", "ok": True, "tool": "pirml.echo"}]})
if __name__ == "__main__":
    asyncio.run(main())
<<<CONTRACT>>>
{
  "tool_deps": ["pirml.echo"],
  "io_schema": {"final_schema": {}, "citations_schema": {}, "trace_ptr": "t"},
  "budgets": {"max_calls": 1, "max_parallel": 1, "max_bytes_in": 128, "max_bytes_out": 128, "timeout_s": 5},
  "assertions": []
}
EOF

python -m scripts.compile \
    --task "unified-signoff" \
    --tools-dir tools \
    --out-dir "$BASE/compiled" \
    --input-file "$BASE/model_response.txt" \
    --smoke

# C) Execution (Live Runtime)
# Run the compiled program. Stdout is protocol-only.
python -m pirml \
    --prog "$BASE/compiled/prog.py" \
    --out-dir "$BASE/live" > "$BASE/live.stdout.ndjson"

# D) Verification (Replay Parity)
# Replay with TOOLS BLOCKED. Parity must hold 100%.
PIRML_BLOCK_TOOLS=1 python -m pirml \
    --prog "$BASE/compiled/prog.py" \
    --replay "$BASE/live/trace.ndjson" \
    --out-dir "$BASE/replay" > "$BASE/replay.stdout.ndjson"

# E) Parity Check
sha256sum "$BASE/live/final.json" "$BASE/replay/final.json"
tail -n 1 "$BASE/replay/trace.ndjson" | grep '"replay_match":true'

# F) Schema Enforcement
python -m scripts.schema_lint \
    --final "$BASE/live/final.json" \
    --contract "$BASE/compiled/contract.json"
```

## 3) Failure Semantics Drill
```bash
# Business Failure (rc=1)
python -m pirml --prog tests/prog_fail.py --out-dir "$BASE/fail-biz" >/dev/null || test $? -eq 1

# Integrity/Timeout Failure (rc=2)
python -m pirml --prog tests/prog_ok.py --timeout 0.001 --out-dir "$BASE/fail-integrity" >/dev/null || test $? -eq 2
```

## 4) Acceptance Criteria
1. `mise run fast` is green.
2. `toolsearch_bench` status is `PASS`.
3. Compilation branch is `{prog.py, contract.json}`.
4. `live` and `replay` hashes are IDENTICAL.
5. `replay_match: true` in final trace frame.
6. `schema_lint` returns `OK`.
7. Exit codes `1` and `2` are strictly enforced.

## 5) Anti-Patterns (Banned)
1. Adding `op=log` to the protocol.
2. Silent fallbacks on budget overflow.
3. Trusting `final.json` without `trace.ndjson`.
4. Mocking replay.
