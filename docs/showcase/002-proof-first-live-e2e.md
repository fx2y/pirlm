# 002: Proof-First Live E2E (Sprint-1)

This is not a feature tour. It is an operator drill: prove invariants fast, then trust outputs.

## 0) Hard stance
1. Never trust `final.json` alone. Always pair with `trace.ndjson`.
2. Never demo on dirty gates. Run `mise run fast` first.
3. `stdout` is protocol NDJSON only; human diagnostics are `stderr`.
4. Only 3 ops exist: `call|result|final`. Any extra op is defect.
5. IDs are `c%05d`, monotonic (`c00001...`). Non-monotonic is defect.
6. Only `result` may truncate; must include `truncated=true` + `truncated_bytes`.
7. Replay must pass with tools blocked (`PIRML_BLOCK_TOOLS=1`) and match `final.json` hash.
8. Exit semantics are contract: `0` success, `1` business/tool failure, `2` protocol/supervisor failure.

## 1) One-shot 20m showcase (copy/paste)
```bash
set -euo pipefail
BASE=out/showcase/002
rm -rf "$BASE"
mkdir -p "$BASE"

# 1) preflight gate
mise run fast

# 2) live run (real tools: echo/readfile/bash)
python -m pirml --prog tests/prog_ok.py --out-dir "$BASE/live" >"$BASE/live.stdout.ndjson"

# 3) replay with tools blocked (still must pass)
PIRML_BLOCK_TOOLS=1 python -m pirml \
  --prog tests/prog_ok.py \
  --replay "$BASE/live/trace.ndjson" \
  --out-dir "$BASE/replay" >"$BASE/replay.stdout.ndjson"

# 4) parity proof
sha256sum "$BASE/live/final.json" "$BASE/replay/final.json"
tail -n 1 "$BASE/replay/trace.ndjson"

# 5) rc semantics drill
python -m pirml --prog tests/prog_fail.py --out-dir "$BASE/fail" >"$BASE/fail.stdout.ndjson" || test $? -eq 1
python -m pirml --prog tests/prog_ok.py --timeout 0.001 --out-dir "$BASE/timeout" >"$BASE/timeout.stdout.ndjson" || test $? -eq 2

# 6) observability + contract lint
python -m scripts.proto_lint --trace "$BASE/live/trace.ndjson"
python -m scripts.trace_lint --trace "$BASE/live/trace.ndjson"
python -m scripts.schema_lint --final "$BASE/live/final.json"
python -m scripts.replay_check
```

Pass criteria:
1. `live` and `replay` final hashes are identical.
2. Replay final trace frame has `meta.replay_match=true`.
3. `prog_fail` returns rc `1`.
4. Timeout drill returns rc `2`.
5. All lints print `OK` (or schema verifier success text).

## 2) Tacit operator model
1. `final.json` is boundary summary for product/business consumers.
2. `trace.ndjson` is forensic truth for engineers/QA/FDE.
3. If they disagree, trust trace first, then debug projection path.
4. If replay hash mismatches, treat as integrity failure (`rc=2`), not business failure.
5. If `trace.ndjson` missing on fatal path, block release immediately.

## 3) Walkthroughs (role-focused)

### PO track: prove compact boundary + deterministic replay
```bash
BASE=out/showcase/002/po
rm -rf "$BASE"
python -m pirml --prog tests/prog_ok.py --out-dir "$BASE/live" >"$BASE/live.stdout.ndjson"
cat "$BASE/live/final.json"
python -m scripts.trace_lint --trace "$BASE/live/trace.ndjson"
PIRML_BLOCK_TOOLS=1 python -m pirml --prog tests/prog_ok.py --replay "$BASE/live/trace.ndjson" --out-dir "$BASE/replay" >"$BASE/replay.stdout.ndjson"
sha256sum "$BASE/live/final.json" "$BASE/replay/final.json"
tail -n 1 "$BASE/replay/trace.ndjson"
```
Expect:
1. `final.json` has compact contract (`ok`,`results`, optional `output/meta` only).
2. Replay hash == live hash.
3. Replay final trace frame contains parity metadata.

### QA track: attack invariants, not happy paths
```bash
python -m unittest -q tests.test_protocol tests.test_replay
python -m unittest -q tests.test_c3_tools
python -m unittest -q tests.test_c4_observability
python -m unittest -q tests.test_golden_final
python -m pirml --prog tests/prog_ok.py --out-dir out/showcase/002/qa/proto >out/showcase/002/qa/proto.stdout.ndjson
python -m scripts.proto_lint --trace out/showcase/002/qa/proto/trace.ndjson
python -m scripts.trace_lint --trace out/showcase/002/qa/proto/trace.ndjson
python -m scripts.replay_check
```
Stop-ship failures:
1. duplicate/missing/out-of-order final or ids.
2. non-result overflow accepted.
3. replay order/cassette drift accepted.
4. secret-like args leaked in trace.

### FDE track: runbook for incident-grade reproducibility
```bash
BASE=out/showcase/002/fde
rm -rf "$BASE"
python -m pirml --prog tests/prog_ok.py --out-dir "$BASE/ok" >"$BASE/ok.stdout.ndjson"
python -m pirml --prog tests/prog_parallel.py --out-dir "$BASE/parallel" >"$BASE/parallel.stdout.ndjson"
python -m pirml --prog tests/prog_large.py --max-line-bytes 1024 --out-dir "$BASE/trunc" >"$BASE/trunc.stdout.ndjson"
PIRML_BLOCK_TOOLS=1 python -m pirml --prog tests/prog_parallel.py --replay "$BASE/parallel/trace.ndjson" --out-dir "$BASE/parallel-replay" >"$BASE/parallel-replay.stdout.ndjson"
tail -n 2 "$BASE/parallel/metrics.csv"
rg -n '"truncated":true|"truncated_bytes":' "$BASE/trunc/trace.ndjson"
```
Expect:
1. parallel run finishes without deadlock.
2. truncation is explicit on `result` frame only.
3. metrics row exposes `calls,retries,failures,wall_ms,final_ok,trace_sha,final_sha`.

## 4) Scenario library (copy/paste micro-drills)

### S1: Baseline live integration
```bash
python -m pirml --prog tests/prog_ok.py --out-dir out/showcase/002/s1 >out/showcase/002/s1.stdout.ndjson
cat out/showcase/002/s1/final.json
```

### S2: Replay parity + no-tool guarantee
```bash
PIRML_BLOCK_TOOLS=1 python -m pirml --prog tests/prog_ok.py --replay out/showcase/002/s1/trace.ndjson --out-dir out/showcase/002/s2 >out/showcase/002/s2.stdout.ndjson
sha256sum out/showcase/002/s1/final.json out/showcase/002/s2/final.json
tail -n 1 out/showcase/002/s2/trace.ndjson
```

### S3: Business failure semantics (`rc=1`)
```bash
python -m pirml --prog tests/prog_fail.py --out-dir out/showcase/002/s3 >out/showcase/002/s3.stdout.ndjson; echo $?
cat out/showcase/002/s3/final.json
```

### S4: Supervisor/protocol failure semantics (`rc=2`)
```bash
python -m pirml --prog tests/prog_ok.py --timeout 0.001 --out-dir out/showcase/002/s4 >out/showcase/002/s4.stdout.ndjson; echo $?
cat out/showcase/002/s4/final.json
```

### S5: Parallel fanout e2e
```bash
python -m pirml --prog tests/prog_parallel.py --out-dir out/showcase/002/s5 >out/showcase/002/s5.stdout.ndjson
cat out/showcase/002/s5/final.json
```

### S6: Result truncation proof
```bash
python -m pirml --prog tests/prog_large.py --max-line-bytes 1024 --out-dir out/showcase/002/s6 >out/showcase/002/s6.stdout.ndjson
rg -n '"truncated":true|"truncated_bytes":' out/showcase/002/s6/trace.ndjson
```

### S7: Protocol lint on real artifact
```bash
python -m scripts.proto_lint --trace out/showcase/002/s1/trace.ndjson
```

### S8: Trace envelope lint on real artifact
```bash
python -m scripts.trace_lint --trace out/showcase/002/s1/trace.ndjson
```

### S9: Schema contract lint
```bash
python -m scripts.schema_lint --final out/showcase/002/s1/final.json
```

### S10: Canonical replay smoke
```bash
python -m scripts.replay_check
```

### S11: Secret redaction probe
```bash
cat > /tmp/pirlm_redact_probe.py <<'PY'
from pirml.protocol import call, send_final
call("echo", {"auth_token": "secret123", "Authorization": "Bearer abc"})
send_final(True, {"ok": True, "results": []})
PY
python -m pirml --prog /tmp/pirlm_redact_probe.py --out-dir out/showcase/002/s11 >out/showcase/002/s11.stdout.ndjson
rg -n 'secret123|Bearer abc|redacted_sha256' out/showcase/002/s11/trace.ndjson
```
Expect: secrets absent; `redacted_sha256` present.

### S12: Metrics-as-evidence
```bash
tail -n 2 out/showcase/002/s1/metrics.csv
```
Read columns: `calls,retries,failures,wall_ms,final_ok,trace_sha,final_sha`.

## 5) Fast triage playbooks
1. Replay mismatch:
`sha256sum live/final.json replay/final.json` -> inspect replay final frame `meta` -> inspect call-id sequence drift.
2. Proto lint fail:
read failing line -> classify (`op/id/final-order/overflow`) -> reproduce with tiny fixture.
3. Timeout flake:
separate tool timeout vs global timeout -> inspect `stderr` for `global timeout reached`.
4. Secret leak:
`rg -n 'token|secret|api_key|auth' trace.ndjson` -> add failing test first -> patch redaction map.

## 6) Release gate (strict)
```bash
mise run ci
python -m scripts.replay_check
python -m scripts.proto_lint --trace out/ci/trace.ndjson
python -m scripts.trace_lint --trace out/ci/trace.ndjson
```
Release-ready iff:
1. all commands pass,
2. replay parity holds,
3. `final.json` remains compact contract,
4. showcase flow is reproducible twice.

## 7) Anti-patterns (ban list)
1. Adding `op=log`.
2. Random/non-monotonic IDs.
3. Treating trace as optional debug output.
4. Stuffing raw tool payload blobs into `final.json`.
5. Bypassing tool registry choke-point.
6. Hiding protocol errors as business failures.
