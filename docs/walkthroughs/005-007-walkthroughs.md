# 005-007: Live Substrate Master Walkthroughs

Expert-only. L0 frozen. Determinism absolute. Evidence outranks logs.

## 005: Web Substrate (Density + Truth)
Goal: Verify L1 web pipeline without L0 tool growth.

```bash
# Preflight
mise run fast

# Deterministic Bundle
python -m scripts.web_fixture_smoke

# Explicit Schema (No out/** crawl)
python -m scripts.schema_lint \
  --serp out/web_smoke/serp.ndjson \
  --web-output out/web_smoke/web_output.json \
  --citation out/web_smoke/citation.ndjson

# Accuracy Matrix & Winner Rule
python -m scripts.web_eval && cat out/web_eval.canonical.json

# Live Fetch Smoke
python -m scripts.web_smoke

# Replay Parity (Blocker)
python -m scripts.replay_check
```

## 006: ArtifactFS + RLM (Lineage + Context)
Goal: Bulky evidence persistence + context-efficient reasoning.

```bash
# CAS Ingestion (10MB proof)
python -m unittest -q tests.test_artifact_c1.TestArtifactC1.test_ingest_10mb

# Index Rebuild & Parity
python -m scripts.artifact_rebuild --root out/test_artifact_c1 --check

# View DSL (Deterministic VID generation)
AID=$(jq -r 'select(.ev=="put" and .kind=="raw") | .aid' out/test_artifact_c1/trace.ndjson | head -n1)
python -m scripts.tools.slice "$AID" '{"op":"lines","a":0,"b":5}' --art-root out/test_artifact_c1

# RLM Kernel & Governor (Hard Caps)
python -m unittest -q tests.test_rlm_kernel tests.test_spec06_c5_governor

# E2E Signoff (Stress + Rebuild)
python -m scripts.artifact_e2e_signoff
```

## 007: UX Shim + Toolpack (Authority + Projection)
Goal: Unified entry point + safe extension projection.

```bash
# Unified Shim (Only valid entry)
python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/walk_r1 --project-root .

# Projection (Symlink contract)
ls -l .pirml && test -L .pirml/trace.ndjson

# Toolpack Fail-Closed (Typed JSON stderr)
python -m scripts.tools.open missing --art-root art 2>&1 | jq .

# Replay Wrapper (PIRML_BLOCK_TOOLS=1)
python -m scripts.tools.replay tests/prog_ok.py out/walk_r1/trace.ndjson --out-dir out/walk_replay

# Headless Lane (JSON-only)
PIRML_ENABLE_JSON_HEADLESS=1 python -m pirml.ux.headless <<'EOF'
{"type":"tool_execution_start","tool":"pirml_run","args":{"prog":"tests/prog_ok.py","out-dir":"out/headless_walk"}}
EOF

# Authority Gate (Immutable order)
mise run ci
```

## The Verdict
L1 is hardened. Pointers resolve. Replay is law. Fail-closed or bust.
