# 000-3: Eval + Product Shell + Policy Live E2E Operator Course

Date baseline: `2026-02-23`.
Status: **Ultra-Opinionated Sign-off**.
Goal: Unified Pareto-optimal value proposition for PIRML live deployments.

## 0) Doctrine (The 10 Laws of Operator Trust)
1. **Status Authority**: `spec-0/00-3-tasks.jsonl` is the blocker-first truth.
2. **L0 Freeze**: Runtime tools are IMMUTABLE `{echo,readfile,bash}`. Policy is additive only.
3. **Explicit Ingress**: `--dataset` and `--tools-dir` are mandatory. No magic discovery.
4. **Determinism**: Canonical JSON, strict counters, no wall-clock scoring.
5. **Replay Supremacy**: Parity drift invalidates live claims. Replay is fail-closed.
6. **Parse Law**: CLI failures MUST emit typed JSON stderr (`type,msg,retryable`), `rc=2`.
7. **Append-only Evidence**: Shard logs (`.ndjson`) are immutable evidence; resume never rewrites.
8. **Integrity-First Reporting**: Corrupt logs or duplicate terminal rows => `integrity`/`rc=2`.
9. **Pointer Safety**: UI hints `<=120` chars; rich payloads stay in `pi_ptr`/sidecars.
10. **Release Authority**: `mise run ci` is the only truth. `fast` is for rejection only.

## 1) 15-Minute Unified Value Proof (Copy/Paste)
```bash
set -euo pipefail
BASE=out/showcase/000-3/demo
HOME_SANDBOX="$BASE/home"
TOOLS="$BASE/tools"
rm -rf "$BASE"
mkdir -p "$BASE" "$HOME_SANDBOX" "$TOOLS"

# 0) Preflight
mise run fast
mise run ci

# 1) Product Shell + Safe Ops
python -m pirml doctor --home "$HOME_SANDBOX" > "$BASE/doctor.ndjson" || true
python -m pirml install-pi-ext --target global --home "$HOME_SANDBOX" --project-root "$PWD" > "$BASE/install.json"

# 2) Tool Authoring (Bootstrap Flow)
python -m pirml tool init acme.echo --tools-dir "$TOOLS" --hot
python -m pirml tool lint --tools-dir "$TOOLS"
python -m pirml tool pack --tools-dir "$TOOLS" --out "$BASE/toolpack.json" --bootstrap

# 3) Eval Fixture Gate (Golden + Full Smoke)
python -m pirml.eval --suite golden50 --dataset spec-0/08/golden50.jsonl --jobs 1 --out-dir "$BASE/eval/golden"
python -m pirml.eval --suite browsecomp --dataset tests/fixtures/web/corpus.jsonl --jobs 1 --out-dir "$BASE/eval/full"

# 4) Reporting + KPI Wall
python -m pirml.report "$BASE/eval/full/runs/browsecomp"/*.ndjson --out "$BASE/eval/full/report.json"
python -m pirml.md "$BASE/eval/full/report.json" > "$BASE/eval/full/report.md"

# 5) Regression Guard (Comparator)
cp "$BASE/eval/full/report.json" "$BASE/eval/full/report.prev.json"
python -m pirml.report \
  "$BASE/eval/full/runs/browsecomp"/*.ndjson \
  --out "$BASE/eval/full/report.json" \
  --compare "$BASE/eval/full/report.prev.json" "$BASE/eval/full/report.json" \
  --acc-min-delta 0 \
  --delta-out "$BASE/eval/full/compare_delta.json"

# 6) Final Parity Check
python -m scripts.replay_check
python -m scripts.artifact_rebuild --check
```

## 2) Specialized Tracks
### Track A: The Eval Benchmarker (Accuracy/Cost/Latency)
Focus: Deterministic evidence for model/policy changes.
Value: Turns model debates into replay-verifiable KPI deltas (acc/cost/latency) with fail-closed regression gates.
```bash
# Real dataset single-process lane
python -m pirml.eval --suite prod --dataset /path/to/data.jsonl --out-dir out/eval/prod
# Multi-shard fanout (jobs=1 per process)
for s in $(seq 0 7); do
  python -m pirml.eval --suite prod --dataset /path/to/data.jsonl --shards 8 --shard "$s" --out-dir out/eval/prod &
done
wait
```

### Track B: The Tool Architect (Safe Capability Growth)
Focus: Scaffolding, linting, and indexing custom tools.
Value: Adds new tool capability without violating L0 freeze, manifest schema, or deterministic catalog contracts.
```bash
# Init 3 tools to satisfy hot-count policy without --bootstrap
python -m pirml tool init svc.read --tools-dir tools --hot
python -m pirml tool init svc.write --tools-dir tools --hot
python -m pirml tool init svc.delete --tools-dir tools --hot
python -m pirml tool pack --tools-dir tools --out out/catalog.json
```

### Track C: The Security/Policy Operator
Focus: Sandbox safety and extension policy.
Value: Proves policy boundaries are enforceable in live flow (deny/confirm/truncation) before production rollout.
```bash
# Verify extension policy via TS suite (Live Locus)
npx tsx tests/test_spec09_c4_extension_policy.ts
# Inspect doctor output for capability leaks
python -m pirml doctor
```

### Track D: The Integrator (Headless Automation)
Focus: One owner-path execution for CI/CD or Agentic use.
Value: Preserves single execution owner path while emitting machine-grade artifacts for automation and replay parity.
```bash
# Run a program headlessly and get a machine-readable summary
python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/headless_demo
# Replay the same trace to verify parity
python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/headless_demo --replay out/headless_demo/trace.ndjson
```

## 3) Scenario Bank (High-Signal Drills)
- **S01: Parse Law Breach**: `python -m pirml replay --timeout nope` (Must be typed JSON config, rc2).
- **S02: Integrity Fail**: Corrupt a `.ndjson` file and run `pirml.report` (Must be integrity/rc2).
- **S03: Replay Mismatch**: Mutate a `trace.ndjson` and run `scripts.replay_check` (Must catch drift).
- **S04: Resume Monotonicity**: Rerun `pirml.eval` on same `out-dir` (Must see `resume_skip` notes).

## 4) Anti-Patterns (The "Don't" List)
1. **Implicit Globbing**: Never pass `runs/*.ndjson` to report; use suite-scoped globs.
2. **Hidden Policy**: Do not embed policy logic in prompts; use `pirml/runtime/policy.py`.
3. **Wall-clock Dependence**: Never assert on exact `ms` latency in tests; use deterministic counters.
4. **Silent Failure**: Never swallow exceptions; map to typed `CliFailure` with correct `rc`.

## 5) Exit-Code Contract
- `0`: Success.
- `1`: Business/Validation/Unsupported (User Error/Model Failure).
- `2`: Integrity/Config/Internal (System Failure/Broken Contract).
