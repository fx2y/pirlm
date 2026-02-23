# 008-009: Expert E2E Walkthroughs (Enriched)

## Doctrine: Determinism or Death
- **L0 Freeze:** Runtime tools strictly `{echo, readfile, bash}`.
- **Parse Law:** RC=2 + typed stderr JSON on failure. NO `usage:` leaks.
- **Exit Triad:** `0=ok`, `1=biz/val/unsupported`, `2=integrity/config/internal`.
- **Replay Guard:** Parity drift = `fail_tag=REPLAY_MISMATCH`.
- **Owner Path:** `scripts.pirml_run -> pirml.ux.runtime_bridge -> python -m pirml`.

---

## 008: Eval + Report (BrowseComp)

### Phase 1: Dataset Prep & Deterministic Sampling
```bash
# 1) Sample 50 rows for CI stability
python -m pirml.select_golden --in data.jsonl --n 50 --seed 0 --out spec-0/08/golden50.jsonl

# 2) Verify ID uniqueness (dupe = Integrity/2)
python -c "import json; d=[json.loads(l)['task_id'] for l in open('spec-0/08/golden50.jsonl')]; assert len(d) == len(set(d))"
```

### Phase 2: Execution (Eval) + Sharded Parallelism
```bash
# 1) Execute shard 0/4 (strictly --jobs 1)
python -m pirml.eval --suite bc --dataset tests/fixtures/web/corpus.jsonl --shards 4 --shard 0 --jobs 1 --out-dir out/eval/bc

# 2) Prove resume law (append-only)
python -m pirml.eval --suite bc --dataset tests/fixtures/web/corpus.jsonl --shards 4 --shard 0 --jobs 1 --out-dir out/eval/bc
rg -q "resume_skip:terminal_exists" out/eval/bc/runs/bc/shard-00000.ndjson
```

### Phase 3: Aggregation (Report) & Pointers
```bash
# 1) Ingest shard logs (Suite-scoped globs only)
python -m pirml.report out/eval/bc/runs/bc/*.ndjson --out out/eval/bc/report.json

# 2) Inspect KPI wall
python -c "import json; r=json.load(open('out/eval/bc/report.json')); print({k:r[k] for k in ['acc','median_latency']})"

# 3) Verify pointer sidecar
test -f out/eval/bc/report.pointers.json
```

### Phase 4: Machine Comparator (Zero Regression)
```bash
# 1) Fail if accuracy drops vs baseline
python -m pirml.report out/eval/bc/runs/bc/*.ndjson 
  --out out/eval/bc/report.json 
  --compare baseline.json out/eval/bc/report.json 
  --acc-min-delta 0 --delta-out diff.json || echo "Regression detected"
```

---

## 009: Product Shell + Policy

### Phase 1: Environment Sanity (`doctor`)
```bash
# 1) Deterministic sandbox check
python -m pirml doctor --home /tmp/fakehome > doc.ndjson
rg -q '"extensions_installed":' doc.ndjson
```

### Phase 2: Extension Deployment (Safe Lane)
```bash
# 1) Project-local install (Idempotent)
python -m pirml install-pi-ext --target project --source-dir .pi/extensions/pirml --project-root $PWD

# 2) Verify TS policy logic
npx tsx tests/test_spec09_c4_extension_policy.ts
```

### Phase 3: Tool Authoring (Productivity)
```bash
# 1) Init deterministic template
python -m pirml tool init acme.lookup --tools-dir tools/

# 2) Lint with structured failure output
python -m pirml tool lint --tools-dir tools/

# 3) Pack immutable catalog (catalog_hash)
python -m pirml tool pack --tools-dir tools/ --out pack.json
python -c "import json; print(json.load(open('pack.json'))['catalog_hash'])"
```

### Phase 4: Integrity Proofs
```bash
# 1) Parse Law: RC=2 + JSON (No usage leak)
python -m pirml replay prog.py trace.ndjson --timeout nope 2> err.json || true
jq -e '.type == "config"' err.json

# 2) Replay Parity (Live vs Replay Hash)
python -m scripts.replay_check
```

---

## The Authority Close (Daily Confidence)
```bash
mise run fast    # <3s
mise run ci      # Canonical Truth
python -m scripts.replay_check
python -m scripts.artifact_rebuild --check
python -m unittest discover -s tests -p 'test_spec0[89]*.py' -q
```
