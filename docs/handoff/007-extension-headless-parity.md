# PIRML Cycle 07 Handoff: Extension & Headless Parity

## Thesis
Spec-07 ships L1 observability and UX adapters (/pirml command, .pirml facade, CLI toolpack) without mutating the L0 core (runtime, replay, tool surface). If a feature requires new runtime tools, it violates Cycle 07.

## Invariant Ledger (Handoff Truth)
| Constraint | Rationale | Locus | Proof Command |
| :--- | :--- | :--- | :--- |
| **L0 Freeze** | Prevent replay drift | `pirml/runtime/tools.py` | `mise run ci && python -m scripts.replay_check` |
| **One Owner** | Avoid path/state drift | `scripts/pirml_run.py` | `python -m unittest -q tests.test_spec07_c1_runtime_shim` |
| **Byte Law** | Replayable hash/pointer | `pirml/ux/pointers.py` | `python -m unittest -q tests.test_spec07_c1_runtime_shim` |
| **Facade Safety** | No destructive rmtree | `pirml/ux/pointers.py` | `python -m unittest -q tests.test_spec07_c1_runtime_shim` |
| **Ctx Hygiene** | Payload in CustomEntry | `.pi/extensions/pirml/` | `npx tsx tests/test_spec07_c2_extension_contract.ts` |
| **Fail-Closed** | Deterministic machine rc | `scripts/tools/*.py` | `python -m unittest -q tests.test_spec07_c3_toolpack` |
| **Gate Purity** | H2 order immutable | `.mise.toml` | `python -m unittest -q tests.test_spec07_c7_gate_contract` |

## Architecture & Flows

### 1. Execution Pipeline (The "One Path")
`pi /pirml` -> `extension/command.ts` -> `extension/spawn.ts` -> `python -m scripts.pirml_run` -> `pirml.ux.runtime_bridge.run_once` -> `python -m pirml`.
*   **Result:** `out/<run_id>/` contains `trace.ndjson`, `final.json`, `metrics.csv`.
*   **Facade:** `.pirml/` symlinks to the latest run; absolute paths only.

### 2. Pointer Schema (The "Source of Truth")
Extension appends `CustomEntry` to session. Never put bulky data in `CustomMessage.content`.
```json
{
  "type": "custom", "customType": "pirml", "parentId": "parent_run_id_or_null",
  "data": {
    "runId": "r123", "trace": "out/r123/trace.ndjson", "final": "out/r123/final.json",
    "artifactsDir": "art", "roots": ["out/r123", "art"], "runSha": "hex...", "ts": 123
  }
}
```

### 3. CLI Toolpack (The "Operator Kit")
Wrappers in `scripts/tools/` for incident triage and data extraction.
*   `pirml-open <ID>`: CID/VID resolution. Supports path inputs (decode via `ArtifactStore`).
*   `pirml-slice <AID> <SPEC>`: Deterministic view creation (VID). No parallel parser stack.
*   `pirml-replay <PROG> <TRACE>`: Rerun with `PIRML_BLOCK_TOOLS=1`.

## Walkthroughs & Recipes

### 1. Verification of a Fresh Run
```bash
# B3: Generate evidence
python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/demo --project-root .

# B4: Verify facade
ls -l .pirml/trace.ndjson  # Must be absolute link
cat .pirml/final.json      # Must resolve

# B5: Replay from facade
python -m scripts.tools.replay tests/prog_ok.py .pirml/trace.ndjson --out-dir out/demo_replay
```

### 2. Troubleshooting a Broken Pointer
If `schema_lint` fails on `trace_ptr`:
1. Check `pirml/ux/pointers.py`: Is `runSha` derived from `final.read_bytes()`? (INV.5)
2. Check `scripts.pirml_run`: Is the `out-dir` correctly passed? (INV.1)
3. Run `python -m unittest tests.test_spec07_c7_schema_pointer_parity`.

### 3. Adding a Hybrid Tool Parameter (Bet-B)
1. Update `.pi/extensions/pirml/tool_run.ts` schema.
2. Assert `minimum` bounds and `typed unsupported` on flag-off.
3. Validate via `npx tsx tests/test_spec07_c4_hybrid_tool.ts`.

## Operator Checklist (Pre-Merge)
- [ ] `mise run fast` is green (<3s).
- [ ] `python -m scripts.replay_check` shows zero drift.
- [ ] `npx tsx tests/test_spec07_c2_extension_contract.ts` confirms lineage safety.
- [ ] `spec-0/07-tasks.jsonl` reflects reality (B00-B20 closed).
- [ ] `REL0` authority rerun green.

## Anti-Patterns (The "Don'ts")
- **X1:** Do not call `pirml.runtime.exec` directly in snippets; always use `python -m pirml`.
- **X2:** Do not mutate `.pirml/` except via `project_last_run`.
- **X3:** Do not add internal helpers to `runtime/tools.py`; keep them in `ux/` or `scripts/`.
- **X4:** Do not ship a "done" cycle without `mise run ci` signoff.

## Next Steps
To close Cycle 07, rerun `REL0` (see `spec-0/07-tutorial.jsonl:REL0`) and flip `spec-0/07-tasks.jsonl` state rows to `done`. Maintain the fail-closed doctrine at all costs.
