# 000-2: Master Live E2E Signoff (Operator Course)

Date: `2026-02-23`.
Status: Ultra-Opinionated, Live-First, No-Mock.

This document provides a single, unified path to verify the entire PIRML L1 substrate (Web, ArtifactFS, UX Shim). It prioritizes real-world value over synthetic test coverage.

## 0) Prerequisites
1. `mise run boot` (Environment ready)
2. `SEARX_BASE_URL` (Optional, for Live Search lane)
3. `PIRML_ENABLE_JSON_HEADLESS=1` (For automation lanes)

## 1) The 5-Minute "Value Burst" (One-Shot)
Run this to confirm the basic machine-to-machine and human-to-machine contracts.

```bash
set -euo pipefail
BASE=out/signoff/$(date +%s)
mkdir -p "$BASE"

# 1. Authoritative Live Run (L1 Web + L1 Artifacts)
python -m scripts.pirml_run \
  --prog tests/prog_ok.py \
  --out-dir "$BASE/run" \
  --project-root .

# Optional operator summary lane
python -m scripts.pirml_run \
  --prog tests/prog_ok.py \
  --out-dir "$BASE/run-human" \
  --project-root . \
  --human

# 2. Evidence Integrity Check
python -m scripts.artifact_rebuild --root "$BASE/run/art" --check
python -m scripts.replay_check

# 3. Protocol Schema Signoff
python -m scripts.schema_lint \
  --final "$BASE/run/final.json" \
  --trace "$BASE/run/trace.ndjson"

echo "VALUE BURST SUCCESS: $BASE"
```

## 2) Live Web Substrate (The Search Lane)
PIRML is only as good as its evidence. We verify the "Live doc fetch" lane.

```bash
# Lane A: Live Fetch (Real network, no mock)
python -m scripts.web_smoke
```
Expected: answer preview + citation list (`url`, `chunk_id`, quote snippet).

## 3) ArtifactFS + RLM (The Context Lane)
Verify that bulky evidence is safely off-context but resolvable.

```bash
# 1. Generate multi-MB evidence
python -m unittest -q tests.test_artifact_c1.TestArtifactC1.test_ingest_10mb

# 2. Build a deterministic "view" (slice)
AID=$(jq -r 'select(.ev=="put" and .kind=="raw") | .aid' out/test_artifact_c1/trace.ndjson | head -n1)
VID=$(python -m scripts.tools.slice "$AID" '{"op":"lines","a":0,"b":5}' --art-root out/test_artifact_c1)

# 3. Open by View ID
python -m scripts.tools.open "$VID" --art-root out/test_artifact_c1 --mode text

# 4. Search artifacts by metadata/content
python -m scripts.tools.search --kind raw --contains deterministic --json --art-root out/test_artifact_c1
```

## 4) UX + Extension (The Integrator Lane)
Verify that PIRML projects into modern tools (VSCode/Extension) correctly.

```bash
# 1. Projection Verification
ls -l .pirml/final.json
ls -l .pirml/trace.ndjson

# 2. Hybrid Tool safety
PIRML_ENABLE_HYBRID_TOOL=1 python -m unittest -q tests.test_spec07_c4_hybrid_tool
```

## 5) Evaluative Truth (The Pareto Lane)
We use a more opinionated accuracy metric that rewards evidence coverage, not just string matching.

```bash
# Run web matrix eval
python -m scripts.web_eval
cat out/web_eval.canonical.json
```
Expected: `acc` is evidence-linked (citation coverage), deterministic tuple winner still unchanged.

---

## Gaps & Blockers (The "Reality Check")

1.  **[DONE] Brittle Accuracy**: `eval_shard` now uses `evidence_accuracy` (citation-coverage based), not exact answer parroting.
2.  **[DONE] Human-Friendly Summary**: `scripts.pirml_run --human` prints concise operator fields.
3.  **[DONE] Artifact Search**: `scripts.tools.search` supports `--kind|--url|--contains|--limit|--json`.
4.  **[DONE] Projection Staleness**: runtime shim now replaces stale `.pirml` symlink roots safely before projection.
5.  **[DONE] Smoke Noise**: expected smoke failures no longer print debug banners to stderr.
6.  **[DONE] Web Smoke Visibility**: live smoke prints answer snippet + citation previews.

## Signoff Verdict
The L1 substrate is **Verifiable**, **Hardened**, and now operator-readable across live, artifact, UX, and eval lanes.
