# PIRML v2 Substrate: Operational Handoff

Expert-level guide for operating and extending the PIRML deterministic orchestration substrate. 
**Core Axiom:** Verification cost `V << G` (Generation cost) via mandatory replay-auditable traces.

## 1. Hard Invariants (The "Truths")
Any breach of these is a `Sev-B` defect blocking any merge.

- **Protocol Algebra:** Frames $\in$ `{call, result, final}`. Exactly one `final`, always terminal. No `log` frames (use stderr).
- **ID Policy:** Strict `c%05d` (e.g., `c00001`). Monotonic, globally unique per run. `result.id` must map seen `call.id`.
- **Determinism:** Pinned env (`PYTHONHASHSEED=0`, `TZ=UTC`, `LC_ALL=C`). No network. No wall-clock in protocol (use `SequenceClock`).
- **Compact Final:** `final.json` is a boundary contract (`ok`, `results`, `output`, `meta`). **Zero** raw transcripts.
- **Trace is Product:** Every run emits `trace.ndjson` + `final.json`. Replay parity (`live.final.sha == replay.final.sha`) is mandatory.
- **Line-Byte Cap:** Default `8192`. Enforced at writer. Only `result` may truncate (explicit `truncated: true` + `truncated_bytes`).

## 2. The Artifact Stack
Found in `out/<run>/`:
- `trace.ndjson`: Forensic event log. Enveloped (`seq`, `dir`, `ms`, `ts`), Hashed (`sha256_args`, `sha256_output`), Redacted (`auth*`, `token`, `secret`).
- `final.json`: Compact model outcome. Golden baseline for replay parity.
- `metrics.csv`: KPI row (`calls`, `retries`, `failures`, `wall_ms`, `final_ok`, `trace_sha`, `final_sha`).

## 3. Tool Contracts (Sprint-1)
- **`echo`:** Basic passthrough.
- **`readfile`:** Byte-capped (`max_bytes`). UTF-8 replace on mid-char truncation. Meta: `size`, `read_bytes`, `truncated`.
- **`bash`:** Structured result (`exitCode`, `stdout`, `stderr`). Timeout-aware. 
- **Supervisor Retries:** 2 retries on `retryable: true` errors. Counted in `result.meta.retries`. Program only sees terminal result.

## 4. Operational Walkthroughs (The "How-To")

### A. Live Execution (The Standard Path)
```bash
# Run program and capture evidence
python -m pirml --prog tests/prog_ok.py --out-dir out/walk/live
# Verify: rc=0, final.ok=true, trace.ndjson contains 2 pairs of call/result + 1 final
```

### B. Replay Parity Proof (The Confidence Path)
```bash
# Replay from trace with tools BLOCKED
PIRML_BLOCK_TOOLS=1 python -m pirml --prog tests/prog_ok.py --replay out/walk/live/trace.ndjson --out-dir out/walk/replay
# Assert parity:
sha256sum out/walk/live/final.json out/walk/walk/replay/final.json
# Inspect parity metadata in replay trace final frame:
tail -n 1 out/walk/replay/trace.ndjson | jq '.meta.replay_match'
```

### C. Failure Semantics (The RC Contract)
- **RC=1 (Business Fail):** Tool error or program logic fail (`final.ok: false`).
- **RC=2 (Runtime Fatal):** Protocol violation, timeout, or supervisor crash.
```bash
# Force timeout (Supervisor fatal)
python -m pirml --prog tests/prog_ok.py --timeout 0.001; echo $? # 2
# Run failing logic (Business fail)
python -m pirml --prog tests/prog_fail.py; echo $? # 1
```

### D. Large Payload Truncation (The Safety Path)
```bash
# Cap protocol lines to 1KB
python -m pirml --prog tests/prog_large.py --max-line-bytes 1024
# Trace result will carry truncated:true and truncated_bytes: > 0
```

### E. Parallel Fanout (The Async Path)
```bash
# Program uses AsyncRpcClient to fire 3 parallel calls
python -m pirml --prog tests/prog_parallel.py --out-dir out/walk/parallel
# metrics.csv will show calls=3, but wall_ms stays low due to supervisor serial dispatch mock vs real tool speed
```

## 5. Maintenance Loop
1. **Inner Loop:** `mise run fast` (<3s class). Every file save.
2. **Full Gate:** `mise run ci`. Preserves ladder: `fmt > lint > types > unit > proto > trace > schemas > replay`.
3. **New Behavior?** 
   - Add failing test to `tests/test_protocol.py` (fatal path) or `tests/test_replay.py` (parity path).
   - Patch.
   - Run `python -m scripts.replay_check`.

## 6. Triage Guide
| Symptom | Tool | First Move |
| :--- | :--- | :--- |
| Replay Hash Drift | `scripts.replay_check` | Diff `live/final.json` vs `replay/final.json` |
| Protocol Violation | `scripts.proto_lint` | Check `trace.ndjson` for duplicate IDs or non-last `final` |
| Envelope/Hash Error | `scripts.trace_lint` | Check for non-monotonic `seq` or missing `ms` |
| Type Error | `pyright` | Check `pirml/runtime/rpc.py` signatures for `JSONObject` vs `Mapping` |

**Final Rule:** NEVER merge without `mise run ci` green and replay parity verified.
