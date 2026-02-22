# Cycle 08 Handoff: BrowseComp Harness

Ship spec-08 objective/replayable/costed BrowseComp harness (golden50+full1266) by reusing existing runtime/web/artifact substrate; no L0 mutation.

## Protocol & Execution Laws (Non-Negotiable)
- **L0 Freeze**: Runtime/replay/tool/channel/boundary contracts are immutable. L1 additive modules only.
- **Fail-Closed**: Unknown op/tool/provider/cache/variant/path/schema/plan => typed JSON stderr envelope + exit code.
- **Evidence Law**: Every run (incl fatal) emits `trace.ndjson` + `final.json`; all emitted pointers resolve.
- **Determinism**: Canonical bytes/JSON, strict clocks, run-scoped mutable state, explicit tie-breaks.
- **Replay Authority**: Replay outranks live. Replay guard executes real per-task deterministic snapshots under `PIRML_BLOCK_TOOLS=1`.
- **Append-Only Shards**: `runs/<suite>/*.ndjson` is immutable audit record. Resume skips existing terminals with audit notes.
- **Boundary Split**: `final.json` root remains `{ok,results,output?,meta?}`. Task-rich payload stays in external rows.

## CLI & Contract Surface
```bash
# 1. Evaluate: dataset(jsonl) -> eval rows (runs/<suite>/*.ndjson)
python -m pirml.eval --suite golden50 --dataset spec-0/08/golden50.jsonl --jobs 1 --out-dir out/eval/golden50

# 2. Report: aggregate terminals -> report.json + pareto.json + pointers sidecar
python -m pirml.report out/eval/full/runs/browsecomp/*.ndjson --out out/eval/full/report.json

# 3. Compare: machine-readable regression gate
python -m pirml.report out/eval/full/runs/bc/*.ndjson --out out/report.json 
  --compare prev.json now.json --acc-min-delta 0 --cost-max-delta 0 --delta-out delta.json

# 4. Render: human-readable KPI wall + Pareto
python -m pirml.md out/eval/full/report.json > out/eval/full/report.md
```

## Internal Seams & Taxonomy
- **Scorer**: `pirml/web/score.py` -> `score_exact_match` (deterministic, normalized, no jitter in `acc`).
- **Taxonomy**: `pirml/web/taxonomy.py` -> `classify_fail_tag` (restored `NO_CITE`, `REPLAY_MISMATCH`, `CTX_BLOAT`).
- **Runner**: `pirml/eval_runner/driver.py` -> handles sharding, resume, replay-guard, and per-task trace stubs.
- **Pointers**: `pirml/eval_pointers.py` -> enriched navigability via sidecar indices; custom message cap <=120 chars.

## Operator Walkthroughs

### PO: Verify Regression Gate
1. Run `mise run eval-golden` to execute the golden50 suite.
2. Generate report: `python -m pirml.report out/eval/golden50/runs/golden50/*.ndjson --out out/report.json`.
3. Check `report.md` for `KPI_WALL`: `acc`, `median_cost`, `median_latency`, `no_cite_rate`.
4. Validate `compare_delta.json` has `ok: true`.

### QA: Breach Fail Lanes
1. `python -m pirml.eval --jobs oops` -> expect `type=config` stderr + code 2.
2. `python -m pirml.eval --jobs 0` -> expect `type=config` stderr + code 2 (no silent zero-coercion).
3. Corrupt a shard NDJSON (delete a line's `seq`) -> `python -m pirml.report ...` -> expect `type=integrity` + code 2.
4. Duplicate a `task_id` in dataset -> `python -m pirml.eval ...` -> expect `type=validation` + code 1.

### FDE: Full Shard Fanout
1. Provision 32-process fanout (L1 wrapper style):
   ```bash
   for i in $(seq 0 31); do
     python -m pirml.eval --suite browsecomp --dataset corpus.jsonl --shards 32 --shard $i --out-dir out/eval/full &
   done; wait
   ```
2. Aggregate: `python -m pirml.report out/eval/full/runs/browsecomp/*.ndjson --out out/eval/full/report.json`.
3. Check Pareto: `out/eval/full/pareto.json` lists top `fail_tag` and failing `task_ids`.

## Verification Matrix (Cycle 08)
| ID | Invariant | Proof Command |
| :--- | :--- | :--- |
| **C1.F1** | Typed Parse | `python -m unittest -q tests.test_spec08_c1_cli_surface` |
| **C2.R1** | Replay Guard | `python -m unittest -q tests.test_spec08_c2_replay_guard` |
| **C2.I1** | Resume Integrity | `python -m unittest -q tests.test_spec08_c2_runner` |
| **C3.S1** | Exact Score | `python -m unittest -q tests.test_spec08_c3_scoring` |
| **C4.A1** | Report Dedup | `python -m unittest -q tests.test_spec08_c4_report` |
| **C5.M1** | Anti-Tautology | `python -m unittest -q tests.test_spec08_c5_golden_delta` |
| **C6.P1** | Pointer Resolvability | `python -m unittest -q tests.test_spec08_c6_pi_pointers` |
| **C7.S1** | Hardened Sync | `python -m unittest -q tests.test_spec08_c7_hardening_sync` |

## Done-Gate Signoff
- All C0-C7 tasks in `spec-0/08-tasks.jsonl` are `st=done`.
- Replay authority is verified via real per-task snapshot execution.
- Pointer navigability is restored without mutating historical shard bytes.
- Zero silent-skip policy is enforced at dataset and report layers.
