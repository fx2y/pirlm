# PIRML Constitution

Mission: maximize replay-verifiable value (`V<<G`): reject fast, prove hard, ship evidence.

Model: `L0` frozen contracts (`runtime|replay|tool-surface|channel|boundary`); `L1` additive wrappers/adapters only; `G` fail-fast authority ladder.

## Hard Laws
- `H0` Root policy lives here; path-local norms only via imported `.codex/rules/*`.
- `H1` Release authority is `mise run ci`; `mise run fast` is `<3s` reject-only.
- `H2` Gate order immutable: `fmt>lint>types>unit>proto>trace>schemas>replay`.
- `H3` Determinism default: pinned env, canonical bytes/JSON, strict counters/clocks, total-order tie-breaks, no wall-clock scoring semantics.
- `H4` Protocol algebra closed: `op in {call,result,final,custom}` only.
- `H5` Envelope/order law: one `final` and last; `id=c%05d` unique+monotonic/run; `seq` starts `1` then strict `+1`; key order deterministic.
- `H6` Byte law: hash persisted bytes only; boundary writer owns caps; only `result` truncates and must emit truncation metadata.
- `H7` Tool surface freeze at `L0`: runtime registry exact `{echo,readfile,bash}`; replay enforces `PIRML_BLOCK_TOOLS=1`.
- `H8` Evidence law: every run (incl fatal) emits `trace.ndjson` + compact `final.json`; every emitted pointer must resolve.
- `H9` Channel split absolute: stdout=protocol only; diagnostics/errors in stderr/artifacts.
- `H10` Exit-code triad invariant: `0` success, `1` business/validation/tool/unsupported, `2` integrity/config/internal.
- `H11` Fail-closed default: unknown `op|tool|schema|plan|provider|variant|path|flag` => typed `{type,msg,retryable}`; no fallback/skip/swallow.
- `H12` Parallel law: independent work uses bounded fanout + deterministic merge; serial needs explicit reason.
- `H13` State law: mutable state is run-scoped only; no cross-run globals; caches are content-keyed immutable evidence.
- `H14` Compiler XOR law: exactly one branch/run: `{prog.py+contract.json}` xor `{compile_error.json}`.
- `H15` Artifact/schema ingress explicit-only: validate declared artifact args; no recursive `out/**` discovery.
- `H16` Replay outranks live: parity drift makes live output non-authoritative; replay guard must run real deterministic snapshot checks, not stubs.
- `H17` Eval integrity: execute every declared plan/task or emit typed unsupported row; silent skip is fraud.
- `H18` Winner integrity: deterministic tuple ranking only; hashseed-invariant; no narrative ties; no `hash()` on eval paths.
- `H19` Boundary compactness fixed: `final.json` root stays `{ok,results,output?,meta?}`; bulky/raw/debug/lineage data stays artifacts/custom payload.
- `H20` Status truth: current-cycle `spec-0/*-tasks.jsonl` only; HTN/cycle/tutorial shards are support, never authority.
- `H21` Capability growth (`op|tool|gate|schema|runtime|cli-surface`) requires same-change invariant delta + failing test + sync (`learnings+tasks+tutorial+docs`).
- `H22` One execution owner path: `scripts.pirml_run -> pirml.ux.runtime_bridge -> python -m pirml`.
- `H23` `.pirml/*` is projection facade only; storage truth is `out/*` + `art/*`; never destructively rewrite user dirs.
- `H24` Pointer payload split: rich nav payload in `custom.data/details`; human hint max one line, `<=120` chars.
- `H25` Optional bets default-off (`hybrid/headless/parallel-jobs/...`); disabled lanes typed-return unsupported, never implicit enable.
- `H26` Dataset ingress law: datasets are explicit (`--dataset`); scored prompt field cannot fallback to answer fields; duplicate `task_id` is integrity-fail.
- `H27` Append-only resume law: shard logs immutable NDJSON; resume enforces `seq` integrity + one terminal/task; restart may append audit notes only.
- `H28` Runner/report single-parser law: report ingestion uses runner-equivalent parse/merge integrity policy; corrupt/duplicate terminal evidence => integrity fail.
- `H29` Metrics/taxonomy law: required eval metrics are fixed schema keys; `fail_tag` single-label; `NO_CITE` explicit; persisted `acc` exact (no jitter contamination).
- `H30` Gate-helper law: helper tasks are additive-only; `ci`/`fast` command byte-contracts cannot widen silently; fixture helpers must be labeled smoke.
- `H31` Done-claim law: cycle `done` requires contradictions decided (`owner+enforce` bound), matrix refs resolvable, live locus exists, named tests pass, proof cmds rerun clean.

## Decision Kernel
- `D0` Unknown future: minimize state-space, maximize determinism, minimize verification cost.
- `D1` One invariant, one owner, one enforcement locus (`code|test|gate|doc`).
- `D2` Typed contracts beat prose; permissive parse/load is defect.
- `D3` Replayability + pointer resolvability outrank throughput narrative.
- `D4` Delete losers; flatten surfaces; preserve one obvious execution path.
- `D5` "Done" means rerunnable artifacts + proof commands, never logs/prose.
- `D6` Every behavior delta ships handoff row: `constraint|rationale|locus|proof_cmd`.
- `D7` If seam is unimplemented, expose typed unsupported; never keep dead knobs.
- `D8` Prefer shared parsers/registries over duplicated policy code.

## Engineering Doctrine
- `E0` Python `3.12`; strict pyright; scripts invoked via `python -m scripts.*`.
- `E1` Prefer pure transforms + explicit dataclass/TypedDict seams; confine `Any` to I/O edges.
- `E2` Subprocess I/O watchdog-safe (reader thread/queue + reaper), never readiness hacks.
- `E3` CLI/config parsing fail-closed/exhaustive: disable implicit parser exits; map parse/config failures to typed envelopes.
- `E4` Ordering claims require explicit tie-break keys in code + permutation tests.
- `E5` Runtime/replay/schemas/prompts/docs encode one truth; drift is a blocker.

## Coding Style
- `S0` Narrow typed interfaces, deterministic defaults; hidden global mutation is defect.
- `S1` Explicit imports/exports only; wildcard surfaces banned.
- `S2` Boundary exceptions map to typed fail lanes; broad swallow banned.
- `S3` Goldens are byte contracts; drift/missing fails; tests never self-heal.
- `S4` Prefer deletion/merge over branch proliferation; every added line must reduce measured risk.
- `S5` Avoid dual-path policy logic; centralize invariants in one module and reuse.

## Compounding Protocol
- `C0` Behavior delta without invariant delta is invalid.
- `C1` Incident/regression merges include same-change hardening (`code+tests+policy`).
- `C2` Handoff ledger is append-only at `spec-0/00-learnings.jsonl` with `constraint|rationale|locus|proof_cmd`.
- `C3` Same-merge sync required: `spec-0/00-learnings.jsonl` + current `spec-0/*-tasks.jsonl` + current `spec-0/*-tutorial.jsonl`.
- `C4` `done` flip requires live locus + named tests + clean proof rerun.

## Operator Entry Points
- Setup: `mise run boot`
- Fast reject: `mise run fast`
- Authority gate: `mise run ci`
- Replay parity: `python -m scripts.replay_check`
- Artifact parity: `python -m scripts.artifact_rebuild --check`
- Eval smoke (`golden`): `mise run eval-golden`
- Eval smoke (`full-fixture`): `mise run eval-full`
- Eval report smoke: `mise run eval-report`

## Memory Layout
- Root policy: `AGENTS.md`
- Path policy: `.codex/rules/*.md`
- Status authority: `spec-0/*-tasks.jsonl`
- Learning ledger: `spec-0/00-learnings.jsonl`
- Operator flow: `spec-0/*-tutorial.jsonl`
- Private prefs: `AGENTS.local.md` (gitignored)

@.codex/rules/10-runtime-protocol.md
@.codex/rules/20-tests-determinism.md
@.codex/rules/30-tooling-tasks.md
