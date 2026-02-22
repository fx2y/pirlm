# 008: Spec-08 BrowseComp Eval+Report Live E2E Operator Course

Date baseline: `2026-02-22`.
Mode: ultra-opinionated, ultra-terse, proof-first, artifact-first.

## 0) Doctrine (break one => stop)
1. Status authority is `spec-0/08-tasks.jsonl` (`C0..C7=done` as-of `2026-02-22`).
2. `L0` is frozen; this lane is additive eval/report wrappers only.
3. `--dataset` is mandatory; no implicit corpus discovery/download.
4. Runner is append-only NDJSON: `out-dir/runs/<suite>/shard-*.ndjson`.
5. Resume never rewrites terminal rows; reruns append `note=resume_skip:terminal_exists`.
6. `jobs>1` is currently typed `unsupported`; parallelize by process+shards, not by `--jobs`.
7. Replay guard is real and fail-closed: mismatch/error => `fail_tag=REPLAY_MISMATCH`, `acc=0`.
8. Report ingestion is strict: corrupt NDJSON / duplicate terminal rows => `integrity`/`2`.
9. Report inputs are suite-scoped globs only: `runs/<suite>/*.ndjson`.
10. Pointer payload is rich in `pi_ptr`/sidecar; UI hint must stay tiny (`<=120` chars).
11. Release authority is still immutable `mise run ci`; helper lanes are additive only.
12. Exit codes are law: `0 success`, `1 biz/validation/unsupported`, `2 integrity/config/internal`.

## 1) Reality Snapshot (current implementation)
1. Working CLIs: `python -m pirml.eval|report|select_golden|md`.
2. Helper tasks: `mise run eval-golden`, `mise run eval-full`, `mise run eval-report`.
3. `eval-golden` uses `spec-0/08/golden50.jsonl` (fixture gate, not production quality claim).
4. `eval-full` in-repo is fixture smoke (`tests/fixtures/web/corpus.jsonl`); real full1266 uses explicit override.
5. `report.json` emits KPI wall + CAS linkage under `report.artifacts`.
6. `report.pointers.json` sidecar persists per-task pointer payloads.
7. Comparator is machine gate (`--compare ... --*delta ... --delta-out ...`), not prose judgment.

## 2) 12-Minute Canonical E2E (copy/paste)
```bash
set -euo pipefail
BASE=out/showcase/008/demo
rm -rf "$BASE" out/eval/golden50 out/eval/full
mkdir -p "$BASE"

# 0) authority preflight
mise run fast
mise run ci

# 1) golden fixture gate
mise run eval-golden
python -m pirml.report out/eval/golden50/runs/golden50/*.ndjson --out out/eval/golden50/report.json
python -m pirml.md out/eval/golden50/report.json > out/eval/golden50/report.md

# 2) full fixture smoke + aggregate
mise run eval-full
mise run eval-report
python -m pirml.md out/eval/full/report.json > out/eval/full/report.md

# 3) machine comparator (self-baseline demo)
cp out/eval/full/report.json out/eval/full/report.prev.json
python -m pirml.report \
  out/eval/full/runs/browsecomp/*.ndjson \
  --out out/eval/full/report.json \
  --compare out/eval/full/report.prev.json out/eval/full/report.json \
  --acc-min-delta 0 \
  --cost-max-delta 0 \
  --latency-max-delta 0 \
  --acc-per-dollar-min-delta 0 \
  --acc-per-min-min-delta 0 \
  --delta-out out/eval/full/compare_delta.json

# 4) schema/replay/artifact parity
python -m scripts.web_fixture_smoke
python -m scripts.schema_lint \
  --web-eval out/web_smoke/eval.ndjson \
  --web-trace out/web_smoke/web_trace.ndjson \
  --web-output out/web_smoke/web_output.json
python -m scripts.replay_check
python -m scripts.artifact_rebuild --check

# 5) key artifacts
ls -la out/eval/golden50
ls -la out/eval/full
```

Pass bar:
1. Golden/full `runs/<suite>/shard-00000.ndjson` exist.
2. `report.json`, `pareto.json`, `report.md`, `report.pointers.json` exist.
3. `compare_delta.json` exists and is canonical JSON.
4. `schema_lint`, `replay_check`, `artifact_rebuild --check` all pass.
5. `ci` already passed before demo claims.

## 3) Live Integration Lanes
### Lane A: repo fixture smoke (fastest trustworthy loop)
```bash
rm -rf out/eval/golden50 out/eval/full
mise run eval-golden
mise run eval-full
mise run eval-report
python -m pirml.md out/eval/full/report.json > out/eval/full/report.md
```
Use for contract drift detection, not for product-quality marketing.

### Lane B: real dataset single-process lane (full1266 shape)
```bash
python -m pirml.eval \
  --suite browsecomp \
  --dataset /abs/path/to/full1266.jsonl \
  --jobs 1 \
  --out-dir out/eval/full1266
python -m pirml.report out/eval/full1266/runs/browsecomp/*.ndjson --out out/eval/full1266/report.json
python -m pirml.md out/eval/full1266/report.json > out/eval/full1266/report.md
```

### Lane C: real dataset process-fanout lane (`jobs` stays `1`)
```bash
for s in $(seq 0 31); do
  python -m pirml.eval \
    --suite browsecomp \
    --dataset /abs/path/to/full1266.jsonl \
    --shards 32 \
    --shard "$s" \
    --jobs 1 \
    --out-dir out/eval/full1266 &
done
wait
python -m pirml.report out/eval/full1266/runs/browsecomp/*.ndjson --out out/eval/full1266/report.json
python -m pirml.md out/eval/full1266/report.json > out/eval/full1266/report.md
```

### Lane D: release comparator gate
```bash
python -m pirml.report \
  out/eval/full1266/runs/browsecomp/*.ndjson \
  --out out/eval/full1266/report.json \
  --compare out/eval/full1266/baseline_report.json out/eval/full1266/report.json \
  --acc-min-delta -0.01 \
  --cost-max-delta 0.002 \
  --latency-max-delta 50 \
  --acc-per-dollar-min-delta -0.01 \
  --acc-per-min-min-delta -0.01 \
  --delta-out out/eval/full1266/delta.json
```

## 4) Walkthrough Tracks
### Product Owner (10m, value+caveat)
```bash
rm -rf out/eval/golden50 out/eval/full
mise run eval-golden
python -m pirml.report out/eval/golden50/runs/golden50/*.ndjson --out out/eval/golden50/report.json
python -m pirml.md out/eval/golden50/report.json > out/eval/golden50/report.md
mise run eval-full
mise run eval-report
python -m pirml.md out/eval/full/report.json > out/eval/full/report.md
cat out/eval/full/compare_delta.json 2>/dev/null || true
```
Narrative: deterministic quality/cost evidence exists; fixture lane is smoke; real claims require explicit dataset override.

### QA (contracts, not vibes)
```bash
python -m unittest -q tests.test_spec08_c0_reconcile tests.test_spec08_c0_declared_failures
python -m unittest -q tests.test_spec08_c1_cli_surface
python -m unittest -q tests.test_spec08_c2_runner tests.test_spec08_c2_replay_guard
python -m unittest -q tests.test_spec08_c3_metrics_schema tests.test_spec08_c3_scoring tests.test_spec08_c3_taxonomy tests.test_spec08_c3_contract_registry tests.test_spec08_c3_determinism
python -m unittest -q tests.test_spec08_c4_report tests.test_spec08_c4_pareto
python -m unittest -q tests.test_spec08_c5_golden_delta tests.test_spec08_c5_gate_contract
python -m unittest -q tests.test_spec08_c6_pi_pointers
npx tsx tests/test_spec08_c6_pi_pointers.ts
python -m unittest -q tests.test_spec08_c7_hardening_sync
mise run fast
mise run ci
python -m scripts.replay_check
```

### FDE (real deployment loop)
```bash
python -m pirml.eval --suite browsecomp --dataset /abs/path/to/siteA.jsonl --jobs 1 --out-dir out/eval/siteA
python -m pirml.report out/eval/siteA/runs/browsecomp/*.ndjson --out out/eval/siteA/report.json
python -m pirml.md out/eval/siteA/report.json > out/eval/siteA/report.md
python -m pirml.report \
  out/eval/siteA/runs/browsecomp/*.ndjson \
  --out out/eval/siteA/report.json \
  --compare out/eval/siteA/baseline_report.json out/eval/siteA/report.json \
  --acc-min-delta -0.01 \
  --cost-max-delta 0.002 \
  --latency-max-delta 50 \
  --acc-per-dollar-min-delta -0.01 \
  --acc-per-min-min-delta -0.01 \
  --delta-out out/eval/siteA/delta.json
```

### Integrator (pointer/resolution seam)
```bash
mise run eval-full
python -m pirml.report out/eval/full/runs/browsecomp/*.ndjson --out out/eval/full/report.json
python - <<'PY'
import json
from pathlib import Path
p=Path("out/eval/full/report.pointers.json")
rows=json.loads(p.read_text(encoding="utf-8"))
print("entries",len(rows))
print("sample_keys",sorted(rows[0].keys()) if rows else [])
print("pi_ptr_keys",sorted(rows[0]["pi_ptr"].keys()) if rows else [])
PY
python -m unittest -q tests.test_spec08_c6_pi_pointers
npx tsx tests/test_spec08_c6_pi_pointers.ts
```

## 5) Scenario Bank (dense drills)
S01 preflight reject:
```bash
mise run fast
```

S02 release authority:
```bash
mise run ci
```

S03 CLI surface freshness:
```bash
python -m pirml.eval --help
python -m pirml.report --help
python -m pirml.select_golden --help
python -m pirml.md --help
```

S04 clean golden run:
```bash
rm -rf out/eval/golden50
python -m pirml.eval --suite golden50 --dataset spec-0/08/golden50.jsonl --jobs 1 --out-dir out/eval/golden50
```

S05 golden report:
```bash
python -m pirml.report out/eval/golden50/runs/golden50/*.ndjson --out out/eval/golden50/report.json
```

S06 golden markdown:
```bash
python -m pirml.md out/eval/golden50/report.json > out/eval/golden50/report.md
```

S07 full fixture run:
```bash
rm -rf out/eval/full
python -m pirml.eval --suite browsecomp --dataset tests/fixtures/web/corpus.jsonl --jobs 1 --out-dir out/eval/full
```

S08 full report:
```bash
python -m pirml.report out/eval/full/runs/browsecomp/*.ndjson --out out/eval/full/report.json
```

S09 compare delta (strict zero regression):
```bash
cp out/eval/full/report.json out/eval/full/report.prev.json
python -m pirml.report out/eval/full/runs/browsecomp/*.ndjson --out out/eval/full/report.json --compare out/eval/full/report.prev.json out/eval/full/report.json --acc-min-delta 0 --cost-max-delta 0 --latency-max-delta 0 --acc-per-dollar-min-delta 0 --acc-per-min-min-delta 0 --delta-out out/eval/full/compare_delta.json
```

S10 dataset missing fail lane:
```bash
python -m pirml.eval --suite golden50 --jobs 1 --out-dir out/eval/missing ; echo rc=$?
```

S11 parser type fail lane:
```bash
python -m pirml.eval --suite golden50 --dataset spec-0/08/golden50.jsonl --jobs oops ; echo rc=$?
```

S12 validation fail lane (`--jobs 0`):
```bash
python -m pirml.eval --suite golden50 --dataset spec-0/08/golden50.jsonl --jobs 0 ; echo rc=$?
```

S13 validation fail lane (`--shards 0`):
```bash
python -m pirml.eval --suite golden50 --dataset spec-0/08/golden50.jsonl --shards 0 ; echo rc=$?
```

S14 validation fail lane (`--timeout-s 0`):
```bash
python -m pirml.eval --suite golden50 --dataset spec-0/08/golden50.jsonl --timeout-s 0 ; echo rc=$?
```

S15 unsupported lane (`jobs>1`):
```bash
python -m pirml.eval --suite golden50 --dataset spec-0/08/golden50.jsonl --jobs 2 ; echo rc=$?
```

S16 duplicate dataset id fail lane:
```bash
cat > /tmp/spec08_dup.jsonl <<'EOF'
{"task_id":"D1","query":"q1","expected_answer":"a1"}
{"task_id":"D1","query":"q2","expected_answer":"a2"}
EOF
python -m pirml.eval --suite browsecomp --dataset /tmp/spec08_dup.jsonl --jobs 1 --out-dir out/eval/dup ; echo rc=$?
```

S17 anti-tautology manifest check:
```bash
python - <<'PY'
import json
from pathlib import Path
bad=[]
for i,l in enumerate(Path("spec-0/08/golden50.jsonl").read_text().splitlines(),1):
    r=json.loads(l); q=r.get("query",""); a=r.get("expected_answer","")
    if q==a: bad.append((i,r.get("task_id")))
print("bad_rows",bad)
assert not bad
PY
```

S18 resume append-only proof:
```bash
python -m pirml.eval --suite browsecomp --dataset tests/fixtures/web/corpus.jsonl --jobs 1 --out-dir out/eval/full
python -m pirml.eval --suite browsecomp --dataset tests/fixtures/web/corpus.jsonl --jobs 1 --out-dir out/eval/full
rg -n "resume_skip:terminal_exists" out/eval/full/runs/browsecomp/*.ndjson
```

S19 report corrupt NDJSON integrity fail:
```bash
mkdir -p /tmp/spec08_corrupt
printf '{"ok":true,"terminal":true,"task_id":"X","suite":"browsecomp","seq":1}\n{bad-json}\n' >/tmp/spec08_corrupt/shard-00000.ndjson
python -m pirml.report /tmp/spec08_corrupt/*.ndjson --out /tmp/spec08_corrupt/report.json ; echo rc=$?
```

S20 duplicate terminal integrity fail:
```bash
mkdir -p /tmp/spec08_dupterm
printf '{"ok":true,"terminal":true,"task_id":"Q1","suite":"browsecomp","seq":1}\n{"ok":true,"terminal":true,"task_id":"Q1","suite":"browsecomp","seq":2}\n' >/tmp/spec08_dupterm/shard-00000.ndjson
python -m pirml.report /tmp/spec08_dupterm/*.ndjson --out /tmp/spec08_dupterm/report.json ; echo rc=$?
```

S21 report input path law (wrong glob should fail):
```bash
python -m pirml.report out/eval/full/runs/*.ndjson --out out/eval/full/report.bad.json ; echo rc=$?
```

S22 pointer sidecar presence:
```bash
python -m pirml.report out/eval/full/runs/browsecomp/*.ndjson --out out/eval/full/report.json
test -f out/eval/full/report.pointers.json
```

S23 pointer payload shape:
```bash
python - <<'PY'
import json
from pathlib import Path
rows=json.loads(Path("out/eval/full/report.pointers.json").read_text())
print(sorted(rows[0]["pi_ptr"].keys()) if rows else [])
PY
```

S24 pointer fail lane test:
```bash
python -m unittest -q tests.test_spec08_c6_pi_pointers.Spec08C6PiPointersTests.test_report_pointer_validation_fails_on_directory_ref
```

S25 TS message-cap/payload split proof:
```bash
npx tsx tests/test_spec08_c6_pi_pointers.ts
```

S26 replay guard proof suite:
```bash
python -m unittest -q tests.test_spec08_c2_replay_guard
```

S27 deterministic rerun x3 bytes:
```bash
rm -rf out/eval/r0 out/eval/r1 out/eval/r2
for i in 0 1 2; do python -m pirml.eval --suite golden50 --dataset spec-0/08/golden50.jsonl --seed 0 --jobs 1 --out-dir out/eval/r$i; done
sha256sum out/eval/r0/runs/golden50/*.ndjson out/eval/r1/runs/golden50/*.ndjson out/eval/r2/runs/golden50/*.ndjson
```

S28 schema explicit-arg proof:
```bash
python -m scripts.web_fixture_smoke
python -m scripts.schema_lint --web-eval out/web_smoke/eval.ndjson --web-trace out/web_smoke/web_trace.ndjson --web-output out/web_smoke/web_output.json
```

S29 replay authority proof:
```bash
python -m scripts.replay_check
```

S30 artifact parity proof:
```bash
python -m scripts.artifact_rebuild --check
```

S31 comparator fail lane demo:
```bash
cp out/eval/full/report.json out/eval/full/report.prev.json
python -m pirml.report out/eval/full/runs/browsecomp/*.ndjson --out out/eval/full/report.json --compare out/eval/full/report.prev.json out/eval/full/report.json --acc-min-delta 999 --delta-out out/eval/full/compare_delta.fail.json ; echo rc=$?
```

S32 comparator missing-input fail lane:
```bash
python -m pirml.report out/eval/full/runs/browsecomp/*.ndjson --out out/eval/full/report.json --compare /tmp/nope.prev out/eval/full/report.json ; echo rc=$?
```

S33 strict config type fail lane:
```bash
cat > /tmp/spec08_bad_cfg.json <<'EOF'
{"suite":"golden50","dataset":"spec-0/08/golden50.jsonl","jobs":1,"require_citations":"false"}
EOF
python -m pirml.eval --config /tmp/spec08_bad_cfg.json ; echo rc=$?
```

S34 unknown config key fail lane:
```bash
cat > /tmp/spec08_bad_cfg2.json <<'EOF'
{"suite":"golden50","dataset":"spec-0/08/golden50.jsonl","jobs":1,"mystery":1}
EOF
python -m pirml.eval --config /tmp/spec08_bad_cfg2.json ; echo rc=$?
```

S35 deterministic selector smoke:
```bash
python -m pirml.select_golden --in spec-0/08/golden50.jsonl --n 50 --seed 0 --out out/eval/golden50.smoke.jsonl
sha256sum out/eval/golden50.smoke.jsonl
```

S36 markdown idempotence:
```bash
python -m pirml.md out/eval/full/report.json > /tmp/spec08_a.md
python -m pirml.md out/eval/full/report.json > /tmp/spec08_b.md
cmp /tmp/spec08_a.md /tmp/spec08_b.md && echo OK
```

S37 spec08 suite bundle:
```bash
python -m unittest discover -s tests -p 'test_spec08*.py' -q
```

S38 helper proof bundle:
```bash
mise run eval-golden
mise run eval-full
mise run eval-report
```

S39 report KPI quick view:
```bash
python - <<'PY'
import json
d=json.load(open("out/eval/full/report.json"))
print({k:d[k] for k in ["suite","total_tasks","acc","median_latency","median_cost","acc_per_$","acc_per_min","invalid_output_rate","no_cite_rate","replay_mismatch_rate"]})
PY
```

S40 full release-ready minimum:
```bash
mise run fast
mise run ci
python -m scripts.replay_check
python -m scripts.artifact_rebuild --check
python -m unittest discover -s tests -p 'test_spec08*.py' -q
npx tsx tests/test_spec08_c6_pi_pointers.ts
```

## 6) Anti-Patterns (ban list)
1. Claiming fixture `eval-full` equals production full1266 evidence.
2. Using `--jobs>1` and calling it throughput-ready.
3. Reusing dirty `out/eval/*` then reading resume notes as fresh terminals.
4. Feeding `pirml.report` flat `runs/*.ndjson` globs.
5. Mutating old shard logs to enrich pointers.
6. Hiding pointer payload in context text/custom message.
7. Treating `fast` green as release authority.
8. Ignoring typed fail lanes because happy path is green.

## 7) Triage Shortcuts
1. Parse/config failures: inspect typed stderr JSON (`type,msg,retryable`) first.
2. Bad KPI shifts: compare `report.json` vs `compare_delta.json` before reading prose.
3. Integrity reds: run `tests.test_spec08_c2_runner` + `tests.test_spec08_c4_report`.
4. Replay suspicion: run `tests.test_spec08_c2_replay_guard` + `python -m scripts.replay_check`.
5. Pointer/nav breakage: run both pointer suites (`py` + `tsx`) and inspect `report.pointers.json`.

## 8) Exit-Code Contract
1. `0`: success.
2. `1`: business/validation/unsupported/tool.
3. `2`: integrity/config/internal.
