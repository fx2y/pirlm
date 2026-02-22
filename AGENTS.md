# PIRML Constitution

Mission: maximize replay-verifiable value (`V<<G`): reject fast, prove hard, ship only with artifacts.

Model: `L0` runtime/replay substrate (frozen), `L1` additive compiler+web+artifact+RLM layer, `G` authoritative gate ladder.

## Hard Laws
- `H0` Policy root is this file; path-local norms live only in imported `.codex/rules/*`.
- `H1` Authority is `mise run ci`; `mise run fast` is `<3s` reject signal, never release proof.
- `H2` Gate order is immutable fail-fast: `fmt > lint > types > unit > proto > trace > schemas > replay`.
- `H3` Determinism defaults mandatory: env pins, canonical JSON, strict clocks/counters, explicit total-order tie-breakers.
- `H4` Protocol algebra closed: `op in {call,result,final,custom}`; exactly one `final`; `final` last.
- `H5` Envelope law: `id=c%05d` monotonic unique/run; `seq` starts `1`, strict `+1`; field order deterministic.
- `H6` Byte law: hash persisted/emitted bytes only; writer owns boundary cap; only `result` may truncate and must emit truncation metadata.
- `H7` Tool surface frozen at `L0`: `{echo,readfile,bash}`; replay blocks tools (`PIRML_BLOCK_TOOLS=1`).
- `H8` Artifact law: every run (incl fatal) emits `trace.ndjson` + compact `final.json`; any emitted pointer must resolve.
- `H9` Channel split strict: stdout carries protocol only; diagnostics live in stderr/artifacts only.
- `H10` Exit-code invariant: `0=success`, `1=business/validation/tool`, `2=integrity/config/internal`.
- `H11` Fail-closed default: unknown op/tool/schema/plan/config/variant/path => typed failure (`type,msg,retryable`); no fallback/skip/swallow.
- `H12` Parallel law: independent work uses bounded fanout with deterministic merge; serial path needs explicit reason.
- `H13` State law: mutable state is run-scoped; cross-run globals are defects; caches are content-keyed immutable evidence.
- `H14` Compiler branch law: exactly one branch/run: `{prog.py+contract.json}` xor `{compile_error.json}`.
- `H15` Schema law: validate explicit artifact args only; hidden recursive `out/**` scans are forbidden.
- `H16` Replay outranks live: parity drift makes live untrusted until fixed with proof.
- `H17` Eval integrity: run every declared plan or emit typed unsupported row; silent skip is fraud.
- `H18` Winner integrity: ranking must be deterministic, hashseed-invariant, evidence-linked; no narrative tie-breaks.
- `H19` Boundary compactness: `final.json` root stays `{ok,results,output?,meta?}`; bulky/raw/debug payloads stay in artifacts.
- `H20` Status truth is task ledger (`spec-0/*-tasks.jsonl`); design shards may guide intent but never override status.
- `H21` Capability growth (`op/tool/gate/schema/runtime`) requires same-change invariant delta + failing test + docs/tasks/learnings/tutorial sync.
- `H22` `L1` may evolve additively; convenience mutation of `L0` contracts/surfaces is prohibited.

## Decision Kernel
- `D0` Unknown future => choose lower state space, stricter determinism, cheaper verification.
- `D1` One invariant, one owner, one enforcement locus (`code|test|gate|doc`).
- `D2` Typed contracts beat text heuristics; permissive parse/load is defect.
- `D3` Replayability and pointer resolvability outrank throughput narratives.
- `D4` Do less but prove more: delete losers, flatten surfaces, keep one obvious path.
- `D5` "Done" means executable proof artifacts, not green-only logs or prose.
- `D6` Any behavioral delta must ship with handoff record: `constraint | rationale | locus | proof-cmd`.

## Engineering Doctrine
- `E0` Python `3.12`, strict pyright, module execution via `python -m scripts.*` only.
- `E1` Prefer pure transforms + explicit dataclass/TypedDict seams; contain `Any` at I/O boundaries only.
- `E2` Subprocess I/O must be watchdog-safe (reader thread/queue), never readiness hacks.
- `E3` API design is fail-closed: reject unknown variants early with typed errors.
- `E4` Ordering claims require explicit tie-break keys in code plus direct tests.
- `E5` Runtime, verifier, prompts, contracts, and schemas must describe one truth.

## Coding Style
- `S0` Narrow typed interfaces; deterministic defaults; no hidden global mutation.
- `S1` No wildcard imports/exports; explicit public surfaces.
- `S2` No broad exception swallowing on boundary paths; map to typed fail lanes.
- `S3` Goldens are contractual bytes; drift/missing is failure; tests never self-heal.
- `S4` Bugfix protocol: reproduce -> failing test -> patch -> `mise run fast` -> `mise run ci` -> replay/schema proof if boundary touched.
- `S5` Prefer deletion/merge over policy sprawl; every added rule/code must reduce measurable risk.

## Compounding Loop
- `C0` Behavior delta without invariant delta is invalid.
- `C1` Incident/perf regressions must harden policy and enforcement in the same merge.
- `C2` Policy/docs/tasks/learnings/tutorial stay monotonic, contradiction-free, and synchronized.
- `C3` Handoff records are append-only evidence for future iterations.

## Operator Entry Points
- Setup: `mise run boot`
- Fast reject: `mise run fast`
- Authority gate: `mise run ci`
- Replay parity smoke: `python -m scripts.replay_check`
- Artifact parity smoke: `python -m scripts.artifact_rebuild --check`
- Matrix smoke: `python -m scripts.spec06_eval --seed 0 --queries tests/fixtures/web/corpus.jsonl`
- Perf smoke: `mise run bench` (`out/bench.json`)

## Memory Layout
- Root policy: `AGENTS.md`
- Path policy: `.codex/rules/*.md`
- Status truth: `spec-0/*-tasks.jsonl`
- Learning ledger: `spec-0/00-learnings.jsonl`
- Operator flow: `spec-0/*-tutorial.jsonl`
- Private prefs: `AGENTS.local.md` (gitignored)

@.codex/rules/10-runtime-protocol.md
@.codex/rules/20-tests-determinism.md
@.codex/rules/30-tooling-tasks.md
