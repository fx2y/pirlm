# Spec10 Operator Field Course (Ultra-Opinionated)

As-of: `2026-02-24`.
Audience: `product-owner | qa | fde`.
Goal: convert claims into replay-verifiable proof bytes, fast.
Authority source: `spec-0/10/21-command-matrix.jsonl` (`W0..W10`).

## 0) Non-negotiables

- Use authority rows first; aliases are convenience only.
- Treat `W4b` live web as informational, never release gate.
- Parse failures must return typed JSON (`config|validation|integrity|unsupported`), no raw `usage:`.
- Every claim must bind `{proof_cmd,artifact_ptr,invariant}`.
- Done means post-edit rerun green: `fast + ci + replay_check + artifact_rebuild`.

## 1) Boot + trust check (2 min)

```bash
mise run boot
export PYTHONHASHSEED=0
python -m scripts.spec10_matrix
python -m scripts.spec10_matrix --lane W9
```

Pass:
- `W0..W10` present.
- `W9` cmd is `python -m scripts.spec10_incident --trace ... --out-dir ...`.

## 2) Lane map (what value each lane buys)

| Lane | Value | Cmd (authority) | Primary pointers |
|---|---|---|---|
| `W0` | release gate + run evidence | `mise run fast && mise run ci && python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/demo --project-root .` | `out/demo/trace.ndjson`, `out/demo/final.json` |
| `W1` | replay trust/parity | `python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/w1/live && python -m scripts.tools.replay tests/prog_ok.py out/w1/live/trace.ndjson --out-dir out/w1/replay` | `out/w1/live/trace.ndjson`, `out/w1/replay/final.json` |
| `W2` | tool authoring seam | `python -m pirml tool init acme.lookup --tools-dir out/w2/tools --force` | `out/w2/tools/acme.lookup.json` |
| `W3` | compile safety loop | `python -m scripts.compile --task "echo hi" --tools-dir tests/fixtures/toolsearch/catalog --out-dir out/w3/compile --input-file tests/fixtures/compile/model_ok.txt` | `out/w3/compile/prog.py`, `out/w3/compile/contract.json` |
| `W4` | deterministic web fixture evidence | `python -m scripts.web_fixture_smoke` | `out/web_smoke/web_trace.ndjson`, `out/web_smoke/web_output.json` |
| `W5` | artifact parity | `python -m scripts.artifact_rebuild --check` | `out/ci/trace.ndjson`, `out/ci/final.json` |
| `W6` | operator UX seam | `python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/w6` | `out/w6/trace.ndjson`, `out/w6/final.json` |
| `W7` | eval economics board | `mise run eval-golden && mise run eval-full && mise run eval-report` | `out/eval/full/report.json` |
| `W8` | policy shell smoke | `python -m scripts.spec09_tool_smoke` | `out/ci/trace.ndjson`, `out/ci/final.json` |
| `W9` | one-command incident | `python -m scripts.spec10_incident --trace out/ci/trace.ndjson --out-dir out/spec10_incident` | `out/spec10_incident/incident.json`, `out/spec10_incident/incident.details.json` |
| `W10` | final governance gate | `mise run ci` | `out/ci/*` |

## 3) Golden e2e (single-shot baseline)

```bash
python -m unittest -q \
  tests.test_spec10_c0_reconcile \
  tests.test_spec10_c1_command_matrix \
  tests.test_spec10_c2_proof_pack \
  tests.test_spec10_c3_incident_bundle \
  tests.test_spec10_c4_surface_resolvers \
  tests.test_spec10_c5_packaging_sync \
  tests.test_spec10_c6_gate_contract \
  tests.test_spec10_c7_hardening_sync
mise run fast
mise run ci
python -m scripts.spec10_proof_pack --out out/spec10_pack/index.jsonl
python -m scripts.spec10_incident --trace out/ci/trace.ndjson --out-dir out/spec10_incident
python -m scripts.replay_check
python -m scripts.artifact_rebuild --check
```

Pass: all `0`; else reopen owning cycle (`C1..C7`) before new claims.

## 4) Walkthrough pack A: Product-owner (proof sells)

### A1. Create proof index

```bash
python -m scripts.spec10_proof_pack --out out/spec10_pack/index.jsonl
```

Inspect:
- `out/spec10_pack/index.jsonl` rows include `lane,rc,sha256,*_ptr`.
- Required lanes `W0..W10` all `rc=0`.

### A2. Materialize persona claims

```bash
python -m scripts.spec10_sales_pack \
  --out out/spec10_sales \
  --pack-index out/spec10_pack/index.jsonl \
  --verification-matrix spec-0/10/81-verification-matrix.jsonl \
  --emit-md
```

Inspect:
- `out/spec10_sales/persona_pack.jsonl`.
- Each `k=persona` row has non-empty `proof_cmd` and resolvable `artifact_ptr`.
- `k=lane_truth` row: `W4b`, `truth=informational`, `status=unsupported`.

### A3. Demo script (15-sec hook -> 2-min proof)

1. Head AI Platform: run `W0`, then `W1`; show owner-path + replay parity.
2. Security/Policy: run `W8`, then `W1`; show typed deny and replay-safe behavior.
3. QA/RelEng: run `W1`, then `W3`; show deterministic replay + compile contract artifacts.
4. PM/ML lead: run `W7`, then `W4`; show KPI tuple + fixture evidence.
5. FDE: run `W9`, then `W5`; show incident class + parity checks.

## 5) Walkthrough pack B: QA (break it first)

### B1. Command authority integrity

```bash
python -m scripts.spec10_matrix
python -m scripts.spec10_matrix --lane W0
python -m scripts.spec10_matrix --lane W10
```

Pass: one authority row per lane; aliases non-authority.

### B2. Parse fail drills (typed rc2)

```bash
python -m scripts.spec10_matrix --lane WX
python -m scripts.spec10_incident --out-dir out/bad
python -m scripts.spec10_surface nope
```

Expected stderr JSON (examples):
- `{"type":"config","msg":"unknown lane: WX","retryable":false}`
- `{"type":"config","msg":"the following arguments are required: --trace","retryable":false}`
- `{"type":"config","msg":"argument surface: invalid choice: 'nope' ...","retryable":false}`

### B3. Determinism x3 gate

```bash
python -m unittest -q tests.test_spec10_c6_gate_contract
for i in 1 2 3; do
  python -m scripts.spec10_proof_pack --out out/spec10_pack/index.jsonl >/dev/null
  cp out/spec10_pack/index.jsonl out/spec10_pack/index.$i.jsonl
done
sha256sum out/spec10_pack/index.1.jsonl out/spec10_pack/index.2.jsonl out/spec10_pack/index.3.jsonl
```

Pass: all hashes equal.

### B4. Explicit ingress check

```bash
mise run eval-golden
mise run eval-full
mise run eval-report
python -m scripts.spec10_surface eval --report out/eval/full/report.json
```

Pass: surface returns `kpi_tuple`; no implicit dataset discovery path.

## 6) Walkthrough pack C: FDE (incident MTTR compression)

### C1. Build clean run

```bash
python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/ci --project-root .
```

### C2. Incident one-command

```bash
python -m scripts.spec10_incident --trace out/ci/trace.ndjson --out-dir out/spec10_incident
```

Expect compact report (actual):

```json
{"artifact_parity":true,"class":"OK","details_ptr":"out/spec10_incident/incident.details.json","notes":"class=OK replay_match=true artifact_parity=true trace=trace.ndjson","rc":0,"replay_match":true,"trace_ptr":"out/ci/trace.ndjson"}
```

### C3. Resolver triage board

```bash
python -m scripts.spec10_surface console --run out/ci
python -m scripts.spec10_surface evidence --trace out/ci/trace.ndjson
python -m scripts.spec10_surface eval --report out/eval/full/report.json
mkdir -p out/spec10_surface
printf '%s\n' '{"type":"policy_deny","msg":"blocked_by_policy","retryable":false,"rc":1,"decision":"deny"}' > out/spec10_surface/policy.ndjson
python -m scripts.spec10_surface policy --log out/spec10_surface/policy.ndjson
```

Pass cues:
- console: `final_last=true`, `final_root_compact=true`.
- evidence: monotonic `seq`, `final` last.
- eval: stable `kpi_tuple`.
- policy: raw typed rows preserved.

## 7) High-value scenarios (copy/paste library)

1. "Need release confidence now": run `W0 -> W1 -> W10`.
2. "Buyer asks for proof, not deck": run `A1 -> A2`, hand over `persona_pack.jsonl`.
3. "Policy bypass concern": run `W8`, then `surface policy`.
4. "Flake claim": run `B3` x3 hash drill.
5. "Replay drift suspicion": run `W1`, then `scripts.replay_check`.
6. "Schema/pointer debt suspicion": run `W5`, inspect `spec10_pack/index.jsonl`.
7. "Compile seam distrust": run `W3`, verify `prog.py|contract.json` artifacts.
8. "Need KPI story": run `W7`, then `surface eval`.
9. "Oncall page": run `C1 -> C2 -> C3` (console+evidence).
10. "Sales says live web required": run `python -m scripts.spec10_proof_pack --include-live --out out/spec10_pack/live.jsonl`; keep as non-authority.
11. "Need product-shell ergonomics": use `python -m pirml run|surface|incident` after authority proof exists.
12. "Pre-release final stamp": rerun section `3` exactly.

## 8) Buyer objection kills (machine-bound)

| Buyer | Objection | Kill move | Invariants |
|---|---|---|---|
| Head AI Platform | "another dashboard" | show `W0+W1` owner-path + typed fail lanes | `I05`,`I18` |
| Security/Policy | "policy bypass" | show `W8` + typed policy envelopes | `I17`,`I19` |
| QA/RelEng | "flaky" | show replay block + x3 stable proof-pack | `I15`,`I22` |
| PM/ML lead | "metrics gamed" | show eval tuple + fail taxonomy coupling | `I16`,`I20` |
| FDE | "need full payload inline" | show compact incident root + details pointer | `I12`,`I10` |

## 9) Disqualifiers (hard reject)

- Requests permissive fallback on unknown flags/providers/tools.
- Requests narrative/dashboard-only claims without artifact pointers.
- Requests runtime/protocol/tool-surface mutation as shortcut.
- Rejects explicit ingress (`--dataset`, explicit report inputs).

## 10) Authority aliases (allowed, non-authority)

- `python -m pirml run ...` -> delegates to `scripts.pirml_run`.
- `python -m pirml surface ...` -> delegates to `scripts.spec10_surface`.
- `python -m pirml incident ...` -> delegates to `scripts.spec10_incident`.
- `mise run spec10-*` helpers are additive convenience, not authority source.

## 11) Exit checklist (ship/no-ship)

```bash
python -m scripts.spec10_matrix
python -m scripts.spec10_proof_pack --out out/spec10_pack/index.jsonl
python -m scripts.spec10_sales_pack --out out/spec10_sales --pack-index out/spec10_pack/index.jsonl --emit-md
python -m scripts.spec10_incident --trace out/ci/trace.ndjson --out-dir out/spec10_incident
mise run ci
python -m scripts.replay_check
python -m scripts.artifact_rebuild --check
```

Ship only if:
- all cmds `rc=0`;
- pack pointers resolve;
- persona rows all bind real artifacts;
- `W4b` still labeled informational/unsupported.
