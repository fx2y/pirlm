# PIRML Constitution

Mission: maximize replay-verifiable value (`V<<G`). Reject fast, prove hard, ship artifacts.

Model: `L0` frozen runtime/replay/tool/channel contract; `L1` additive UX/compiler/web/artifact/rlm; `G` fail-fast authority ladder.

## Hard Laws
- `H0` Root policy here; path-local norms only in imported `.codex/rules/*`.
- `H1` Authority=`mise run ci`; `mise run fast` is `<3s` reject-only signal.
- `H2` Gate order immutable: `fmt>lint>types>unit>proto>trace>schemas>replay`.
- `H3` Determinism default: pinned env, canonical bytes/JSON, strict clocks/counters, total-order tie-breakers.
- `H4` Protocol algebra closed: `op in {call,result,final,custom}`; one `final`; `final` last.
- `H5` Envelope/order law: `id=c%05d` unique monotonic/run; `seq` starts `1`, strict `+1`; deterministic key order.
- `H6` Byte law: hash persisted bytes only; writer owns caps; only `result` truncates and must emit truncation metadata.
- `H7` Tool surface freeze at `L0`: `{echo,readfile,bash}`; replay enforces `PIRML_BLOCK_TOOLS=1`.
- `H8` Artifact law: every run (incl fatal) emits `trace.ndjson` + compact `final.json`; all emitted pointers resolve.
- `H9` Channel split: stdout=protocol only; diagnostics in stderr/artifacts only.
- `H10` Exit codes invariant: `0` success, `1` business/validation/tool, `2` integrity/config/internal.
- `H11` Fail-closed default: unknown op/tool/schema/plan/config/variant/path => typed `{type,msg,retryable}`; no fallback/skip/swallow.
- `H12` Parallel law: independent work uses bounded fanout + deterministic merge; serial needs explicit reason.
- `H13` State law: mutable state run-scoped only; no cross-run globals; caches are content-keyed immutable evidence.
- `H14` Compiler XOR law: exactly one branch/run: `{prog.py+contract.json}` xor `{compile_error.json}`.
- `H15` Schema law: validate explicit artifact args only; no recursive `out/**` discovery.
- `H16` Replay outranks live: parity drift makes live output non-authoritative until fixed with proof.
- `H17` Eval integrity: execute every declared plan or emit typed unsupported row; silent skip is fraud.
- `H18` Winner integrity: deterministic tuple ranking, hashseed-invariant, evidence-linked; no narrative ties; no `hash()` on eval paths.
- `H19` Boundary compactness: `final.json` root remains `{ok,results,output?,meta?}`; bulky/raw/debug data stays artifacts.
- `H20` Status truth: `spec-0/*-tasks.jsonl` only; HTN/cycle/tutorial shards are intent/support, not status authority.
- `H21` Capability growth (`op/tool/gate/schema/runtime`) requires same-change invariant delta + failing test + sync of learnings/tasks/tutorial/docs.
- `H22` One execution owner for UX wrappers: `scripts.pirml_run -> pirml.ux.runtime_bridge -> python -m pirml`.
- `H23` `.pirml/*` is projection facade only; storage truth stays `out/*` + `art/*`; never destructively rewrite user dirs.
- `H24` Pointer payload split: rich payload in `custom` data/details; human message at most one-line hint.
- `H25` Optional bets default-off (`hybrid/headless/...`); disabled lane must typed-return unsupported, never implicit enable.

## Decision Kernel
- `D0` Unknown future: minimize state space, maximize determinism, minimize verification cost.
- `D1` One invariant, one owner, one enforcement locus (`code|test|gate|doc`).
- `D2` Typed contracts beat prose heuristics; permissive parse/load is defect.
- `D3` Replayability + pointer resolvability outrank throughput narrative.
- `D4` Delete losers, flatten surfaces, keep one obvious execution path.
- `D5` "Done" means executable artifacts and rerunnable proof commands, never logs/prose.
- `D6` Every behavior delta ships handoff row: `constraint | rationale | locus | proof_cmd`.

## Engineering Doctrine
- `E0` Python `3.12`, strict pyright, scripts invoked via `python -m scripts.*`.
- `E1` Prefer pure transforms + explicit dataclass/TypedDict seams; confine `Any` to I/O edges.
- `E2` Subprocess I/O must be watchdog-safe (reader thread/queue + reaper), never readiness hacks.
- `E3` API/config parsing is fail-closed and exhaustive; unknown values typed-fail early.
- `E4` Ordering claims require explicit tie-break keys in code and direct permutation tests.
- `E5` Runtime, replay, schemas, prompts, docs must encode one truth.

## Coding Style
- `S0` Narrow typed interfaces; deterministic defaults; hidden global mutation is a defect.
- `S1` Explicit imports/exports only; wildcard surfaces are banned.
- `S2` Boundary exceptions must map to typed fail lanes; broad swallowing is banned.
- `S3` Goldens are byte contracts; drift/missing fails; tests never self-heal.
- `S4` Prefer deletion/merge over branch proliferation; every added line must reduce measured risk.

## Compounding Protocol
- `C0` Behavior delta without invariant delta is invalid.
- `C1` Incident/perf regression merges must include same-change hardening (`code+tests+policy`).
- `C2` Handoff ledger is append-only in `spec-0/00-learnings.jsonl`; format: `constraint|rationale|locus|proof_cmd`.
- `C3` Same-merge sync required: `spec-0/00-learnings.jsonl` + current `spec-0/*-tasks.jsonl` + current `spec-0/*-tutorial.jsonl`.
- `C4` `done` flip requires: live locus exists, named tests exist, proof cmds rerun clean.

## Operator Entry Points
- Setup: `mise run boot`
- Fast reject: `mise run fast`
- Authority gate: `mise run ci`
- Replay parity: `python -m scripts.replay_check`
- Artifact parity: `python -m scripts.artifact_rebuild --check`
- Eval smoke: `python -m scripts.spec06_eval --seed 0 --queries tests/fixtures/web/corpus.jsonl`
- Perf smoke: `mise run bench` (`out/bench.json`)

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
