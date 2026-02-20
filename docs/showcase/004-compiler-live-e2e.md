# 004: Spec-04 Compiler Live E2E Operator Course

Date baseline: `2026-02-20`.
Stance: zero vibes; proofs only.

## 0) Hard stance
1. L0 runtime/replay is frozen; compiler is additive L1.
2. Compile branch law is strict: `{prog.py,contract.json}` xor `{compile_error.json}`.
3. Extract is fail-closed: exact `<<<PROG>>>` then `<<<CONTRACT>>>`; no prose.
4. Verify is fail-closed: schema+AST+tool/gather/final discipline before execution.
5. Smoke is deterministic budget enforcement, not best-effort.
6. Replay parity is truth; mismatch => integrity failure.
7. Schema gate is explicit artifacts only (`--final/--contract/--compile-error`).

## 1) Mental model (carry forever)
1. `L0`: `python -m pirml` protocol executor (`call|result|final`, trace/final/replay/rc).
2. `L1`: `python -m scripts.compile` (`assemble->prompt->model->extract->verify->smoke->artifacts`).
3. `G`: `mise run ci` authority (`fmt>lint>types>unit>proto>trace>schemas>replay`).

## 2) 20m full value drill (copy/paste)
```bash
set -euo pipefail
BASE=out/showcase/004/demo
rm -rf "$BASE"
mkdir -p "$BASE"

# A) preflight
mise run fast

# B) compile pass (C1+C2+C3)
PIRML_MODEL_RAW="$(cat <<'RAW'
<<<PROG>>>
import asyncio
from pirml.runtime.rpc import send_final
async def main():
    send_final(True, {"ok":True,"results":[]})
if __name__=="__main__":
    asyncio.run(main())
<<<CONTRACT>>>
{"tool_deps":[],"io_schema":{"final_schema":{},"citations_schema":{},"trace_ptr":"t"},"budgets":{"max_calls":1,"max_parallel":1,"max_bytes_in":64,"max_bytes_out":64,"timeout_s":2},"assertions":[]}
RAW
)" \
python -m scripts.compile --task "pass" --tools-dir tests/fixtures/toolsearch/catalog --out-dir "$BASE/pass" --smoke

# C) verify fail (import denied)
PIRML_MODEL_RAW="$(cat <<'RAW'
<<<PROG>>>
import asyncio
import os
from pirml.runtime.rpc import send_final
async def main():
    send_final(True, {"ok":True,"results":[]})
if __name__=="__main__":
    asyncio.run(main())
<<<CONTRACT>>>
{"tool_deps":[],"io_schema":{"final_schema":{},"citations_schema":{},"trace_ptr":"t"},"budgets":{"max_calls":1,"max_parallel":1,"max_bytes_in":64,"max_bytes_out":64,"timeout_s":2},"assertions":[]}
RAW
)"
export PIRML_MODEL_RAW
set +e
python -m scripts.compile --task "verify-fail" --tools-dir tests/fixtures/toolsearch/catalog --out-dir "$BASE/fail-verify" --smoke
rc_verify=$?
set -e
unset PIRML_MODEL_RAW

# D) smoke fail (call budget overflow).
# NOTE: this case uses pirml.* tool names, so tools-dir MUST be ./tools, not tests/fixtures/toolsearch/catalog.
PIRML_MODEL_RAW="$(cat <<'RAW'
<<<PROG>>>
import asyncio
from pirml.runtime.rpc import send_final
async def main():
    # SERIAL_OK: rate_limit
    await TOOL_pirml_echo({"text":"1"})
    await TOOL_pirml_echo({"text":"2"})
    send_final(True, {"ok":True,"results":[]})
if __name__=="__main__":
    asyncio.run(main())
<<<CONTRACT>>>
{"tool_deps":["pirml.echo"],"io_schema":{"final_schema":{},"citations_schema":{},"trace_ptr":"t"},"budgets":{"max_calls":1,"max_parallel":1,"max_bytes_in":128,"max_bytes_out":128,"timeout_s":2},"assertions":[]}
RAW
)"
export PIRML_MODEL_RAW
set +e
python -m scripts.compile --task "smoke-fail" --tools-dir tools --out-dir "$BASE/fail-smoke" --smoke
rc_smoke=$?
set -e
unset PIRML_MODEL_RAW

# E) integrity/internal fail (rc=2)
set +e
PIRML_MODEL_RAW='invalid' python -m scripts.compile --task "internal" --tools-dir /tmp/does-not-exist --out-dir "$BASE/fail-internal"
rc_internal=$?
set -e

# F) compile rc contract + branch tuple proof
printf 'rc_verify=%s rc_smoke=%s rc_internal=%s\n' "$rc_verify" "$rc_smoke" "$rc_internal"
ls -la "$BASE/pass" "$BASE/fail-verify" "$BASE/fail-smoke" "$BASE/fail-internal"
test -f "$BASE/pass/prog.py" && test -f "$BASE/pass/contract.json" && test ! -f "$BASE/pass/compile_error.json"
test -f "$BASE/fail-verify/compile_error.json" && test ! -f "$BASE/fail-verify/prog.py"
test -f "$BASE/fail-smoke/compile_error.json" && test -f "$BASE/fail-smoke/smoke_trace.ndjson"
test -f "$BASE/fail-internal/compile_error.json"

# G) live integration: run compiled program on runtime, then replay with tools blocked
python -m pirml --prog "$BASE/pass/prog.py" --out-dir "$BASE/live" > "$BASE/live.stdout.ndjson"
PIRML_BLOCK_TOOLS=1 python -m pirml --prog "$BASE/pass/prog.py" --replay "$BASE/live/trace.ndjson" --out-dir "$BASE/replay" > "$BASE/replay.stdout.ndjson"
sha256sum "$BASE/live/final.json" "$BASE/replay/final.json"
python -m scripts.proto_lint --trace "$BASE/live/trace.ndjson"
python -m scripts.trace_lint --trace "$BASE/live/trace.ndjson"

# H) explicit schema contract checks
python -m scripts.schema_lint \
  --final "$BASE/live/final.json" \
  --contract "$BASE/pass/contract.json" \
  --compile-error "$BASE/fail-smoke/compile_error.json"
```

Expected:
1. `rc_verify=1 rc_smoke=1 rc_internal=2`.
2. Pass emits `prog.py+contract.json(+raw.txt,+smoke_trace.ndjson)` only.
3. Fail paths emit `compile_error.json`; smoke fail still emits `smoke_trace.ndjson`.
4. Live/replay final hashes match.

## 3) Walkthroughs by role

### PO: prove value without substrate risk
```bash
BASE=out/showcase/004/po
rm -rf "$BASE"
mise run fast
mise run schemas
ls -la out/compile-smoke out/compile-fail
python -m pirml --prog tests/prog_ok.py --out-dir "$BASE/live" > "$BASE/live.stdout.ndjson"
PIRML_BLOCK_TOOLS=1 python -m pirml --prog tests/prog_ok.py --replay "$BASE/live/trace.ndjson" --out-dir "$BASE/replay" > "$BASE/replay.stdout.ndjson"
sha256sum "$BASE/live/final.json" "$BASE/replay/final.json"
```
Decision line: compiler increases authoring speed; replay truth unchanged.

### QA: invariant closure, not happy-path demo
```bash
python -m unittest -q tests.test_compile_extract tests.test_compile_verify tests.test_compile_smoke tests.test_compile_golden tests.test_compile_cli
python -m unittest -q tests.test_protocol tests.test_replay
python -m scripts.tool_manifest_lint
python -m scripts.replay_check
mise run ci
```
Stop-ship: replay mismatch, schema drift, AST bypass, compile branch drift, gate-order drift.

### FDE: incident loop under pressure
```bash
BASE=out/showcase/004/fde
rm -rf "$BASE"
python -m pirml --prog tests/prog_parallel.py --out-dir "$BASE/parallel" > "$BASE/parallel.stdout.ndjson"
PIRML_BLOCK_TOOLS=1 python -m pirml --prog tests/prog_parallel.py --replay "$BASE/parallel/trace.ndjson" --out-dir "$BASE/parallel-replay" > "$BASE/parallel-replay.stdout.ndjson"
sha256sum "$BASE/parallel/final.json" "$BASE/parallel-replay/final.json"
python -m pirml --prog tests/prog_large.py --max-line-bytes 1024 --out-dir "$BASE/trunc" > "$BASE/trunc.stdout.ndjson"
rg -n '"truncated":true|"truncated_bytes":' "$BASE/trunc/trace.ndjson"
python -m scripts.proto_lint --trace "$BASE/parallel/trace.ndjson"
python -m scripts.trace_lint --trace "$BASE/parallel/trace.ndjson"
```

## 4) Scenario bank (high-density drills)

S01 extractor fail id map.
```bash
python -m unittest -q tests.test_compile_extract
```

S02 verify fail id map.
```bash
python -m unittest -q tests.test_compile_verify
```

S03 smoke fail id map.
```bash
python -m unittest -q tests.test_compile_smoke
```

S04 compile `--smoke` toggle contract.
```bash
python -m unittest -q tests.test_compile_cli.TestCompileCLI.test_smoke_flag_controls_stage
```

S05 compile rc `0/1/2` contract.
```bash
python -m unittest -q tests.test_compile_cli.TestCompileCLI.test_rc_contract_0_1_2
```

S06 dead flag guard (`--model` rejected).
```bash
python -m unittest -q tests.test_compile_cli.TestCompileCLI.test_model_arg_is_rejected
```

S07 schema requires explicit artifact args.
```bash
python -m unittest -q tests.test_schema_lint.TestSchemaLintCLI.test_requires_explicit_artifacts
```

S08 schema missing final is hard-fail.
```bash
python -m unittest -q tests.test_schema_lint.TestSchemaLintCLI.test_missing_final_is_failure
```

S09 schema ignores unscoped dirty `out/**`.
```bash
python -m unittest -q tests.test_schema_lint.TestSchemaLintCLI.test_ignores_unscoped_out_artifacts
```

S10 replay rejects missing envelope.
```bash
python -m unittest -q tests.test_replay.ReplayTests.test_replay_rejects_trace_missing_envelope
```

S11 replay rejects call-id mismatch.
```bash
python -m unittest -q tests.test_replay.ReplayTests.test_replay_fails_on_call_sequence_mismatch
```

S12 replay blocks tool execution.
```bash
python -m unittest -q tests.test_replay.ReplayTests.test_replay_mode_does_not_execute_tools
```

S13 replay metadata parity proof.
```bash
python -m unittest -q tests.test_replay.ReplayTests.test_replay_trace_contains_hash_parity_metadata
```

S14 runtime rc semantics.
```bash
set +e
python -m pirml --prog tests/prog_fail.py --out-dir out/showcase/004/s14/fail >/dev/null; echo rc_fail=$?
python -m pirml --prog tests/prog_ok.py --timeout 0.001 --out-dir out/showcase/004/s14/timeout >/dev/null; echo rc_timeout=$?
set -e
```

S15 compile+smoke deterministic x3 bytes.
```bash
for i in 1 2 3; do
  out="out/showcase/004/s15/run-$i"
  rm -rf "$out"
  PIRML_MODEL_RAW="$(cat <<'RAW'
<<<PROG>>>
import asyncio
from pirml.runtime.rpc import send_final
async def main():
    send_final(True, {"ok":True,"results":[]})
if __name__=="__main__":
    asyncio.run(main())
<<<CONTRACT>>>
{"tool_deps":[],"io_schema":{"final_schema":{},"citations_schema":{},"trace_ptr":"t"},"budgets":{"max_calls":1,"max_parallel":1,"max_bytes_in":64,"max_bytes_out":64,"timeout_s":2},"assertions":[]}
RAW
)" python -m scripts.compile --task det --tools-dir tests/fixtures/toolsearch/catalog --out-dir "$out" --smoke >/dev/null
  sha256sum "$out/prog.py" "$out/contract.json" "$out/smoke_trace.ndjson"
done
```

S16 runtime deterministic x3 bytes.
```bash
for i in 1 2 3; do
  out="out/showcase/004/s16/run-$i"
  rm -rf "$out"
  python -m pirml --prog tests/prog_ok.py --out-dir "$out" >/dev/null
  sha256sum "$out/final.json" "$out/trace.ndjson"
done
```

S17 compile corpus goldens.
```bash
python -m unittest -q tests.test_compile_golden
```

S18 toolsearch+compiler fast reject gate.
```bash
mise run fast
```

S19 full gate ladder.
```bash
mise run ci
```

S20 replay smoke contract.
```bash
python -m scripts.replay_check
```

## 5) Triage map (symptom -> first move)
1. `compile_error stage=extract`: `cat out/<run>/raw.txt`; check sentinel/order/prose.
2. `ast_import_denied|banned_call|unawaited_tool_call`: run `tests.test_compile_verify` first.
3. `unknown_tool_deps`: verify `--tools-dir` namespace matches `tool_deps` names.
4. `missing_gather|invalid_serial_reason`: enforce `asyncio.gather` or valid `SERIAL_OK` reason.
5. `FAIL_B3_*`: inspect `smoke_trace.ndjson`; budget or output discipline broke.
6. `schema_lint red`: pass explicit artifact args; do not rely on workspace scan.
7. `replay rc=2`: run `python -m scripts.replay_check`; inspect trace envelope/order/hash.

## 6) Ban list
1. No runtime op/tool growth for compiler convenience.
2. No permissive extract/verify/schema behavior.
3. No protocol chatter on stdout.
4. No golden auto-heal in CI path.
5. No release on `fast` only.

## 7) Release bar
1. `mise run fast`.
2. `python -m unittest -q tests.test_compile_extract tests.test_compile_verify tests.test_compile_smoke tests.test_compile_golden tests.test_compile_cli`.
3. `python -m scripts.schema_lint --final out/ci/final.json --contract out/compile-smoke/contract.json --compile-error out/compile-fail/compile_error.json`.
4. `python -m scripts.replay_check`.
5. `mise run ci`.

If any red: demo-only, not releasable.
