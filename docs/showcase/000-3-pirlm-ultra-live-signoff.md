# PIRML Ultra Live Signoff (2026-02-24)

This is the authoritative live signoff for the current PIRML implementation.
It merges the most critical proofs from Spec-08, 09, and 10 into a single, user-friendly flow.

## 0) Prerequisites
- Operating System: Linux
- Runtime: Python 3.12+
- Tools: `mise`, `npx` (optional for TS proofs)

## 1) The "One-Command" Authority
Run this to confirm the baseline integrity of the entire system.

```bash
# 1.1) Hard Gating (Fast + CI)
mise run fast
mise run ci

# 1.2) Replay + Artifact Parity
python -m scripts.replay_check
python -m scripts.artifact_rebuild --check

# 1.3) Verification Matrix
python -m scripts.spec10_matrix
```

## 2) Developer Experience: Tool Authoring & Product Shell
Verify the end-to-end flow for creating and managing tools.

```bash
# 2.1) Tool Scaffold & Lint
BASE=out/signoff/dev
TOOLS="$BASE/tools"
mkdir -p "$TOOLS"
python -m pirml tool init acme.lookup --tools-dir "$TOOLS" --hot
python -m pirml tool lint --tools-dir "$TOOLS"

# 2.2) Tool Packing (Bootstrap mode for single-tool catalogs)
python -m pirml tool pack --tools-dir "$TOOLS" --out "$BASE/toolpack.json" --bootstrap

# 2.3) Product Doctor (Environment Check)
python -m pirml doctor --home "$BASE/home"
```

## 3) Quality & Economics: Eval & Reporting
Verify the system's ability to measure performance and cost.

```bash
# 3.1) Run Eval (Golden50)
python -m pirml.eval --suite golden50 --dataset spec-0/08/golden50.jsonl --jobs 1 --out-dir out/eval/golden50

# 3.2) Aggregate Report
python -m pirml.report out/eval/golden50/runs/golden50/*.ndjson --out out/eval/golden50/report.json

# 3.3) Human-Readable KPI Wall
python -m pirml.md out/eval/golden50/report.json > out/eval/golden50/report.md
cat out/eval/golden50/report.md
```

## 4) Reliability & Support: Incident Response
Verify the tools used for debugging and incident triage.

```bash
# 4.1) Incident Generation
# Use the CI trace as a baseline
python -m scripts.spec10_incident --trace out/ci/trace.ndjson --out-dir out/signoff/incident

# 4.2) Resolver Triage
python -m pirml surface console --run out/ci
python -m pirml surface evidence --trace out/ci/trace.ndjson
```

## 5) Final Proof Packaging
Generate the authoritative proof package for this release.

```bash
python -m scripts.spec10_proof_pack --out out/signoff/proof_index.jsonl
python -m scripts.spec10_sales_pack 
  --out out/signoff/sales 
  --pack-index out/signoff/proof_index.jsonl 
  --emit-md
```

---
**Signoff Status:** Green if all above commands return `rc=0`.
**Report Issues:** Use `spec-0/00-3-tasks.jsonl` for tracking gaps.
