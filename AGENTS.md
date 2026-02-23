# PIRML Constitution

Mission: maximize replay-verifiable value (`V<<G`): reject fast, prove hard, ship evidence.

Model: frozen `L0` (`runtime|replay|tool-surface|channel|boundary`), additive `L1` wrappers, fail-fast gate ladder `G`.

## Hard Laws
- `H0` Root policy is this file; path policy only via imported `.codex/rules/*`.
- `H1` Release authority: `mise run ci`; `mise run fast` is `<3s` reject-only.
- `H2` Gate order immutable: `fmt>lint>types>unit>proto>trace>schemas>replay`.
- `H3` Determinism default: canonical bytes/JSON, strict counters/clocks, total-order ties, no wall-clock scoring semantics.
- `H4` Protocol closed: `op in {call,result,final,custom}` only.
- `H5` Envelope/order: one `final` last; `id=c%05d` uniq+mono/run; `seq` is `1,+1`; key order deterministic.
- `H6` Byte law: hash persisted bytes only; boundary owns caps; only `result` truncates with metadata.
- `H7` Tool freeze: runtime registry exact `{echo,readfile,bash}`; replay enforces `PIRML_BLOCK_TOOLS=1`.
- `H8` Evidence: every run (incl fatal) emits `trace.ndjson` + compact `final.json`; all emitted pointers resolve.
- `H9` Channel split: stdout protocol-only; diagnostics/errors in stderr/artifacts.
- `H10` Exit triad fixed: `0 success`, `1 biz/validation/tool/unsupported`, `2 integrity/config/internal`.
- `H11` Fail-closed: unknown `op|tool|schema|plan|provider|variant|path|flag` => typed `{type,msg,retryable}`; no fallback/skip/swallow.
- `H12` Parallel default: independent work uses bounded fanout + deterministic merge; serial needs explicit reason.
- `H13` State scope: mutable state run-scoped only; no cross-run globals; caches are content-keyed immutable evidence.
- `H14` Compile XOR: per run exactly one branch `{prog.py+contract.json}` xor `{compile_error.json}`.
- `H15` Ingress explicit-only: artifact/schema/report inputs must be declared args; no recursive `out/**` discovery.
- `H16` Replay outranks live: parity drift invalidates live output; replay guard must run real deterministic snapshots.
- `H17` Eval integrity: execute every declared row or emit typed unsupported; silent skip is fraud.
- `H18` Winner integrity: deterministic tuple ranking only; hashseed-invariant; no narrative ties; no `hash()` in eval paths.
- `H19` Boundary compact: `final.json` root fixed `{ok,results,output?,meta?}`; bulky/raw/lineage data stays artifacts/custom.
- `H20` Status truth: current-cycle `spec-0/*-tasks.jsonl` only; htn/tutorial/shards/learnings are support, not authority.
- `H21` Capability growth (`op|tool|gate|schema|runtime|cli-surface`) needs invariant delta + failing test + sync (`learnings+tasks+tutorial+docs`).
- `H22` Single execution owner path: `scripts.pirml_run -> pirml.ux.runtime_bridge -> python -m pirml`.
- `H23` Projection law: `.pirml/*` is facade only; storage truth is `out/*` + `art/*`; never destructively rewrite user dirs.
- `H24` Pointer payload split: rich payload in `custom.data/details`; human hint max 1 line, `<=120` chars.
- `H25` Optional bets default-off (`hybrid/headless/parallel-jobs/...`); disabled lanes typed-return unsupported.
- `H26` Dataset ingress: explicit `--dataset`; scored prompt must not fallback to answer fields; duplicate `task_id` is integrity-fail.
- `H27` Resume law: shard logs append-only NDJSON; resume enforces `seq` integrity + one terminal/task; restart may append audit notes only.
- `H28` Runner/report parser unity: report ingestion uses runner-equivalent parse/merge integrity policy; corrupt/duplicate terminal evidence => integrity fail.
- `H29` Metrics/taxonomy: required metric keys fixed by schema; `fail_tag` single-label; `NO_CITE` explicit; persisted `acc` exact.
- `H30` Helper gates additive-only; `ci`/`fast` byte contracts cannot widen silently; fixture helpers labeled smoke.
- `H31` `done` requires contradictions decided (`owner+enforce`), matrix refs resolvable, live locus exists, named tests pass, proof cmds rerun clean.
- `H32` Parse law: all CLI parsers/subparsers/legacy use strict fail-closed parse; parse failures emit typed stderr JSON (`config`, `rc=2`), never raw `usage:`.

## Decision Kernel
- `D0` Optimize for unknown future: minimize state-space, maximize determinism, minimize verification cost.
- `D1` One invariant, one owner, one enforcement locus (`code|test|gate|doc`).
- `D2` Typed contracts beat prose; permissive parse/load is defect.
- `D3` Replayability + pointer resolvability outrank throughput narrative.
- `D4` Delete losers; flatten surfaces; preserve one obvious execution path.
- `D5` Done = rerunnable artifacts + proof commands, never logs/prose.
- `D6` Every behavior delta ships handoff row: `constraint|rationale|locus|proof_cmd`.
- `D7` Unimplemented seam returns typed unsupported; never keep dead knobs.
- `D8` Prefer shared parsers/registries over duplicated policy code.

## Engineering Doctrine
- `E0` Python `3.12`; strict pyright; scripts via `python -m scripts.*`.
- `E1` Prefer pure transforms + explicit `dataclass`/`TypedDict` seams; confine `Any` to I/O edges.
- `E2` Subprocess I/O must be watchdog-safe (reader thread/queue + reaper); no readiness hacks.
- `E3` CLI/config parse must be fail-closed/exhaustive; disable parser implicit exits; map failures to typed envelopes.
- `E4` Ordering claims require explicit tie-break keys + permutation tests.
- `E5` Runtime/replay/schemas/prompts/docs must encode one truth; drift blocks merge.

## Coding Style
- `S0` Narrow typed interfaces, deterministic defaults; hidden global mutation is defect.
- `S1` Explicit imports/exports only; wildcard surfaces banned.
- `S2` Boundary exceptions map to typed fail lanes; broad swallow banned.
- `S3` Goldens are byte contracts; drift/missing fails; tests never self-heal.
- `S4` Prefer deletion/merge over branch proliferation; every added line must reduce measured risk.
- `S5` No dual-path policy logic; centralize invariant checks and reuse.
- `S6` Public seams must be hard-to-misuse: strict flags, explicit defaults, typed failure, deterministic output.
- `S7` Operator diagnostics are machine-first, human-second.

## Compounding Protocol
- `C0` Behavior delta without invariant delta is invalid.
- `C1` Incident/regression merge includes same-change hardening (`code+tests+policy`).
- `C2` Handoff ledger is append-only at `spec-0/00-learnings.jsonl` with `constraint|rationale|locus|proof_cmd`.
- `C3` Same-merge sync required: `spec-0/00-learnings.jsonl` + current `spec-0/*-tasks.jsonl` + current `spec-0/*-tutorial.jsonl`.
- `C4` `done` flip needs live locus + named tests + clean proof rerun.
- `C5` If any authority proof fails post-`done`, reopen impacted cycle/task before new feature claims.

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
