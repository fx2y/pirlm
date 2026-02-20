# PIRML Constitution

Mission: deterministic orchestration where `V<<G`, every run is replay-auditable, and handoff signal compounds.

Model: `L0` runtime/replay substrate (frozen), `L1` compiler/toolsearch metadata (additive), `G` gate ladder (authoritative).

## Hard Laws
- `H0` Policy root is this file; detail lives only in imported `.codex/rules/*`.
- `H1` Authority: `mise run ci` only; `mise run fast` is <3s reject-signal, never release-proof.
- `H2` Gate order is fixed fail-fast: `fmt > lint > types > unit > proto > trace > schemas > replay`.
- `H3` Determinism defaults are mandatory: env pins + canonical JSON + sequence clock + stable ordering/IDs.
- `H4` Protocol algebra is closed: `op in {call,result,final}`; exactly one `final`; `final` is last.
- `H5` ID/envelope law: `id=c%05d` monotonic unique per run; `seq` strict `+1`; deterministic field order.
- `H6` Boundary-byte law: hash emitted bytes only; line-cap at writer; only `result` may truncate with `truncated,truncated_bytes`; rehash post-truncation.
- `H7` Tool law (Sprint-1 frozen): `{echo,readfile,bash}` only; replay executes zero tools (`PIRML_BLOCK_TOOLS=1`).
- `H8` Artifact law: every run (incl fatal) emits `trace.ndjson` + `final.json`; replay `final.json` hash parity is merge-blocking.
- `H9` Channel split: stdout carries protocol only; diagnostics go to stderr/artifacts only.
- `H10` Exit codes are invariant: `0` success, `1` business/tool/validation fail, `2` integrity/config/supervisor fail.
- `H11` `L1` additivity: compiler/search/hydration may evolve; no `L0` runtime/protocol/tool-surface mutation for convenience.
- `H12` Compiler branch law: exactly one output branch per run: `{prog.py+contract.json}` xor `{compile_error.json}`.
- `H13` Compiler fail-closed law: strict sentinel extraction, strict schema verification, strict AST/tool/gather checks before any smoke/live execution.
- `H14` Schema gate law: validate explicit artifact paths only; hidden `out/**` scanning is forbidden.
- `H15` Capability growth (`op/tool/gate/schema`) requires same-change invariant delta + failing test + lint/schema/docs/tasks/learnings updates.

## Decision Kernel
- `D0` Unknown future: pick lower state-space + stricter determinism + cheaper verification.
- `D1` Replay outranks live: divergence means live is untrusted until explained/fixed.
- `D2` Typed errors (`type,msg,retryable`) beat text heuristics; permissive parsing/loading is a defect.
- `D3` Total order everywhere: ranking, IDs, emitted fields, artifacts, error lists.
- `D4` Boundary payloads stay compact (`final.json` is `{ok,results,output?,meta?}`); never leak raw transcripts.
- `D5` One invariant, one owner, one canonical enforcement locus.
- `D6` Structural caches only: key by content, immutable-at-rest, CI-safe, copy-on-read.

## Engineering Doctrine
- `E0` Python `3.12` + strict pyright; redesign awkward APIs before casting.
- `E1` Prefer pure transforms and explicit dataclass/TypedDict boundaries over mutable ad-hoc dict flows.
- `E2` Subprocess IO must be watchdog-safe (reader-thread/queue), never fragile buffered readiness tricks.
- `E3` Scripts execute as modules (`python -m scripts.*`) only.
- `E4` Prompt, verifier, runtime contracts must be mutually consistent (no dual truth).

## Coding Style
- `S0` Narrow typed inputs/outputs; avoid `Any` spread.
- `S1` No wildcard exports; explicit public surfaces only.
- `S2` Ordering-dependent behavior must define and test the exact tie-break key.
- `S3` Golden artifacts are contractual bytes; tests must fail on drift/missing, never self-heal.
- `S4` Bugfix protocol is fixed: reproduce -> failing test -> patch -> `fast` -> `ci` -> replay/schema proof if boundary touched.
- `S5` Prefer deletion/merge over policy sprawl; every new rule must reduce real risk.

## Compounding Loop
- `C0` Behavior delta without invariant delta is invalid.
- `C1` Every incident/perf regression ships with stricter invariant + enforcement upgrade.
- `C2` New learned pattern must update constitution/rules/tasks/learnings in same change.
- `C3` Status ledgers are single-source and monotonic; contradictory cycle states are defects.
- `C4` Handoff records stay ultra-terse: constraint + rationale + enforcement locus (`code|test|gate|doc`).

## Operator Entry Points
- Setup: `mise run boot`
- Fast reject: `mise run fast`
- Full authority: `mise run ci`
- Replay parity smoke: `python -m scripts.replay_check`
- Perf smoke: `mise run bench` (`out/bench.json`)

## Memory Layout
- Shared policy: `AGENTS.md` (tracked)
- Path-scoped detail: `.codex/rules/*.md`
- Optional private prefs: `AGENTS.local.md` (gitignored)

@.codex/rules/10-runtime-protocol.md
@.codex/rules/20-tests-determinism.md
@.codex/rules/30-tooling-tasks.md
