# PIRML Constitution

Mission: deterministic orchestration where `V<<G`; every run replay-auditable; handoff signal compounds.

Model: `L0` runtime/replay substrate (frozen), `L1` compiler+web/toolsearch layer (additive), `G` gate ladder (authoritative).

## Hard Laws
- `H0` Policy root is this file; details only in imported `.codex/rules/*`.
- `H1` Authority is `mise run ci`; `mise run fast` is `<3s` reject-signal only.
- `H2` Gate order fixed fail-fast: `fmt > lint > types > unit > proto > trace > schemas > replay`.
- `H3` Determinism defaults mandatory: env pins, canonical JSON, sequence clock, total-order IDs/fields/results/errors.
- `H4` Protocol algebra closed: `op in {call,result,final,custom}`; exactly one `final`; `final` last.
- `H5` Envelope law: `id=c%05d` monotonic unique per run; `seq` strict `+1`; deterministic field order.
- `H6` Byte law: hash emitted/stored bytes only; boundary cap at writer; only `result` may truncate (`truncated,truncated_bytes`); rehash post-truncation.
- `H7` Tool surface frozen (`{echo,readfile,bash}`); replay runs zero tools (`PIRML_BLOCK_TOOLS=1`).
- `H8` Artifact law: every run (incl fatal) emits protocol `trace.ndjson` + `final.json`; any pointer artifact must resolve; loss is merge-blocking.
- `H9` Channel split strict: stdout protocol only; diagnostics only stderr/artifacts.
- `H10` Exit codes invariant: `0` success, `1` business/validation/tool fail, `2` integrity/config/internal fail.
- `H11` Fail-closed by default: unknown plan/config/op/tool/schema, unsupported variant, or parse drift => typed failure (never fallback/skip/swallow).
- `H12` Parallel law: independent work uses bounded fanout (`gather` + cap) with deterministic merge order; serial only with explicit reason code.
- `H13` State law: no cross-run mutable runtime state; caches are structural, content-keyed, immutable-at-rest, copy-on-read.
- `H14` Compiler branch law: exactly one branch per run: `{prog.py+contract.json}` xor `{compile_error.json}`; strict sentinels/schema/AST/tool checks before smoke/live.
- `H15` Schema law: validate explicit artifact paths only; hidden `out/**` scanning forbidden.
- `H16` Replay outranks live: any parity drift makes live untrusted until explained/fixed.
- `H17` Capability growth (`op/tool/gate/schema`) needs same-change invariant delta + failing test + lint/schema/docs/tasks/learnings sync.
- `H18` `L1` may evolve additively; no convenience mutation of `L0` contracts/surfaces.

## Decision Kernel
- `D0` Unknown future: choose lower state-space, stricter determinism, cheaper verification.
- `D1` Typed errors (`type,msg,retryable`) beat text heuristics; permissive parsing/loading is defect.
- `D2` One invariant, one owner, one enforcement locus (`code|test|gate|doc`).
- `D3` Matrix/eval integrity: run every declared branch or emit typed unsupported row; silent skip is fraud.
- `D4` Metrics that drive winners/releases must be evidence-linked and deterministic; synthetic/unverifiable scoring is invalid.
- `D5` Boundary payload stays compact (`final.json={ok,results,output?,meta?}`); raw transcripts/HTML/debug streams stay in artifacts.

## Engineering Doctrine
- `E0` Python `3.12` + strict pyright; redesign bad APIs before casting.
- `E1` Prefer pure transforms + explicit dataclass/TypedDict seams over mutable ad-hoc dict pipelines.
- `E2` Subprocess IO must be watchdog-safe (reader-thread/queue), not buffered-readiness hacks.
- `E3` Scripts run as modules (`python -m scripts.*`) only.
- `E4` Runtime, verifier, prompts, contracts, and schemas must describe one truth.

## Coding Style
- `S0` Narrow typed I/O; contain `Any` at boundaries only.
- `S1` No wildcard exports/imports; explicit public surfaces.
- `S2` Ordering behavior requires explicit tie-break key + direct tests.
- `S3` No broad exception swallowing; map to typed fail lanes or explicit policy branches.
- `S4` Goldens are contractual bytes; drift/missing must fail; no self-heal in tests.
- `S5` Bugfix protocol fixed: reproduce -> failing test -> patch -> `fast` -> `ci` -> replay/schema proof if boundary touched.
- `S6` Prefer delete/merge over policy/code sprawl; every rule/code addition must buy measurable risk reduction.

## Compounding Loop
- `C0` Behavior delta without invariant delta is invalid.
- `C1` Incident/perf regression ships with stricter invariant + enforcement upgrade.
- `C2` New pattern updates constitution/rules/tasks/learnings/tutorial in same merge.
- `C3` Status ledgers single-source, monotonic, contradiction-free.
- `C4` Handoff record format: `constraint | rationale | locus | proof-cmd`.

## Operator Entry Points
- Setup: `mise run boot`
- Fast reject: `mise run fast`
- Authority gate: `mise run ci`
- Replay parity smoke: `python -m scripts.replay_check`
- Perf smoke: `mise run bench` (`out/bench.json`)

## Memory Layout
- Shared policy: `AGENTS.md` (tracked)
- Path-scoped detail: `.codex/rules/*.md`
- Private prefs: `AGENTS.local.md` (gitignored)

@.codex/rules/10-runtime-protocol.md
@.codex/rules/20-tests-determinism.md
@.codex/rules/30-tooling-tasks.md
