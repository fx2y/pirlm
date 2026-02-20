# 004: Compiler Live E2E (Spec-04)

Date baseline: `2026-02-20`.
Objective: Single-shot compilation of natural language tasks into deterministic async programs.

## 0) Non-negotiables
1. **L1 Layer**: Compiler is a purely additive layer (L1); zero mutation of L0 runtime substrate.
2. **Artifact Tuple**: Success emits exactly `{prog.py, contract.json}`; failure emits `{compile_error.json}`.
3. **Fail-Closed**: AST verification blocks imports, banned calls, and hidden serialism.
4. **Smoke-Tested**: Generated code must pass a budget-enforced, fake-tool smoke run before release.
5. **Deterministic**: Same task + same model response => byte-identical artifacts.

## 1) 10-minute full showcase (copy/paste)
```bash
set -euo pipefail
BASE=out/showcase/004
rm -rf "$BASE"
mkdir -p "$BASE"

# A) Successful Compilation (Minimal)
export PIRML_MODEL_RAW='<<<PROG>>>
import asyncio
from pirml.runtime.rpc import send_final
async def main():
    send_final(True, {"ok":True,"results":[]})
if __name__=="__main__":
    asyncio.run(main())
<<<CONTRACT>>>
{"tool_deps":[],"io_schema":{"final_schema":{},"citations_schema":{},"trace_ptr":"t"},"budgets":{"max_calls":1,"max_parallel":1,"max_bytes_in":1,"max_bytes_out":1,"timeout_s":5},"assertions":[]}
'
python -m scripts.compile --task "Minimal pass" --tools-dir tests/fixtures/toolsearch/catalog --out-dir "$BASE/pass" --smoke

# B) Verification failure (Banned Import)
export PIRML_MODEL_RAW='<<<PROG>>>
import os
from pirml.runtime.rpc import send_final
async def main():
    send_final(True, {})
<<<CONTRACT>>>
{"tool_deps":[],"io_schema":{"final_schema":{},"citations_schema":{},"trace_ptr":"t"},"budgets":{"max_calls":1,"max_parallel":1,"max_bytes_in":1,"max_bytes_out":1,"timeout_s":5},"assertions":[]}
'
python -m scripts.compile --task "Banned import" --tools-dir tests/fixtures/toolsearch/catalog --out-dir "$BASE/fail-import" || echo "RC=$?"

# C) Smoke failure (Budget Overflow)
export PIRML_MODEL_RAW='<<<PROG>>>
import asyncio
from pirml.runtime.rpc import send_final
async def main():
    await TOOL_pirml_echo({"text": "hi"})
    await TOOL_pirml_echo({"text": "hi"})
    send_final(True, {"ok":True,"results":[]})
if __name__=="__main__":
    asyncio.run(main())
<<<CONTRACT>>>
{"tool_deps":["pirml.echo"],"io_schema":{"final_schema":{},"citations_schema":{},"trace_ptr":"t"},"budgets":{"max_calls":1,"max_parallel":1,"max_bytes_in":128,"max_bytes_out":128,"timeout_s":5},"assertions":[]}
'
# Note: we need to use a real tool from tests/fixtures/toolsearch/catalog
python -m scripts.compile --task "Budget overflow" --tools-dir tests/fixtures/toolsearch/catalog --out-dir "$BASE/fail-budget" --smoke || echo "RC=$?"

# D) Proof of Stability (Goldens)
python -m unittest -q tests.test_compile_golden
```

## 2) Operator Walkthrough: Release Gate
```bash
mise run fast
mise run schemas
python -m unittest -q tests.test_compile_extract tests.test_compile_verify tests.test_compile_smoke tests.test_compile_golden
```

## 3) Triage Map
1. `ExtractionError`: Check `<<<PROG>>>` and `<<<CONTRACT>>>` sentinels; ensure no extra prose.
2. `FAIL_B2_IMPORT_DENIED`: Remove unauthorized imports (e.g., `os`, `sys`, `subprocess`).
3. `FAIL_B2_HIDDEN_SERIAL_REJECTED`: Wrap independent `TOOL_*` calls in `asyncio.gather`.
4. `FAIL_B3_CALL_BUDGET_OVERFLOW`: Reduce number of tool calls or increase `max_calls` in contract (if allowed).
5. `FAIL_B1_TOOL_DEP_HALLUCINATION`: Ensure `tool_deps` in contract matches actual `TOOL_*` calls in code.

## 4) Anti-patterns
1. Printing to `stdout` in `prog.py`.
2. Using `call()` instead of `TOOL_*` wrappers.
3. Missing `await` on `TOOL_*` calls.
4. Manually parsing `contract.json` (the verifier/runner handles it).
