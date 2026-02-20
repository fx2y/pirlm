# PIRML Constitution

Mission: deterministic orchestration substrate where verification cost `V` stays far below generation cost `G` (`V<<G`) and every run is replay-auditable.

## Hard Laws
- `H0` Policy root is this file only; no sibling policy docs; detail lives only in imported `.codex/rules/*`.
- `H1` Gate contract: `mise run ci` (authoritative), `mise run fast` (inner loop, <3s class).
- `H2` Fail-fast ladder is fixed: `fmt > lint > types > unit > proto > trace > schemas > replay`.
- `H3` Determinism default: pinned env (`PYTHONHASHSEED=0`,`TZ=UTC`,`LC_ALL=C`,`LANG=C`,`SOURCE_DATE_EPOCH`), canonical JSON, sequence clock, stable IDs.
- `H4` Protocol algebra frozen: `op in {call,result,final}` only; exactly one `final`; `final` last.
- `H5` ID law: `c%05d`, monotonic, globally unique per run.
- `H6` Line-byte cap enforced at protocol boundary; only `result` may truncate and must expose `truncated` + `truncated_bytes`.
- `H7` Sprint-1 tool surface frozen: `echo`,`readfile`,`bash`; replay executes zero tools (`PIRML_BLOCK_TOOLS=1` must pass).
- `H8` Trace is product: every run (incl fatal) emits `trace.ndjson` + `final.json`; replay `final.json` hash parity is mandatory.
- `H9` Output split strict: stdout = NDJSON protocol only; diagnostics = stderr only.
- `H10` Exit code contract: `0` success (`final.ok=true`), `1` business/tool failure (`final.ok=false`), `2` protocol/config/supervisor integrity failure.

## Decision Kernel (Spec-0 Handoff)
- `D0` Unknown future choice: prefer lower state-space + stricter determinism + cheaper verification; convenience loses by default.
- `D1` Keep planes separated: selection metadata may evolve; execution substrate contracts do not.
- `D2` Prefer closed algebra and typed errors over implicit behavior or text parsing.
- `D3` Determinism requires total order everywhere (ranking, IDs, emitted fields, artifacts).
- `D4` Replay is source of truth: if live vs replay diverge, live behavior is untrusted.
- `D5` Strict input contracts; permissive loaders/lints are defects, not UX.
- `D6` Boundary payloads stay compact; raw transcripts/debug streams never cross product boundary.
- `D7` Caches must be structural-keyed, immutable-at-rest, and CI-safe (no flaky reuse paths).
- `D8` Diagnostics route to stderr/artifacts; protocol channel never carries non-protocol chatter.
- `D9` Any capability growth (new op/tool/gate) requires invariant delta + tests + lint/schema/docs/tasks in same change.

## Engineering Doctrine
- `E0` Python `3.12`, strict pyright. If types are awkward, redesign API before casting.
- `E1` Prefer pure transforms + explicit contracts; hidden mutable state is defect-prone.
- `E2` `final.json` is compact boundary state (`ok`,`results`, optional `output/meta`); never dump raw transcripts there.
- `E3` Scripts run as modules (`python -m scripts.*`) only.
- `E4` Error semantics must be typed and deterministic (`type,msg,retryable`), not regex-on-text.

## Coding Style (Ultra-Opinionated)
- `S0` APIs accept/return narrow typed shapes; avoid `Any` spillover and ad-hoc dict mutation.
- `S1` One owner per invariant; no duplicated ranking/validation logic across modules.
- `S2` No wildcard exports; public surface is explicit (`__all__` / named imports).
- `S3` If behavior depends on ordering, codify a total-order key and test it directly.
- `S4` Hash bytes after final serialization/truncation only; never hash pre-emission objects.
- `S5` Subprocess IO must be watchdog-safe; avoid buffered readiness assumptions (`select(TextIO)`-style traps).
- `S6` Failing test first for every bug/regression; patch without new invariant is incomplete.
- `S7` Prefer deletion/merging over additive policy noise; every new rule must buy measurable risk reduction.

## Compounding Loop
- `C0` Behavior change without invariant delta is invalid.
- `C1` Every incident/perf regression ships with: failing test first, patch, and stricter invariant/gate/docs update.
- `C2` New pattern learned? Update this constitution or imported rule in the same change.
- `C3` Unknown iteration: choose stricter deterministic contract unless cost data disproves it.
- `C4` Handoff quality bar: record decisions as terse constraints + rationale + enforcement locus (code/test/gate).

## Operator Entry Points
- Setup: `mise run boot`
- Fast loop: `mise run fast`
- Full gate: `mise run ci`
- Replay parity smoke: `python -m scripts.replay_check`
- Perf smoke: `mise run bench` (`out/bench.json`)

## Memory Layout
- Shared policy: `AGENTS.md` (tracked)
- Conditional detail: `.codex/rules/*.md` (path-scoped)
- Private local prefs: `AGENTS.local.md` (gitignored, optional)

@.codex/rules/10-runtime-protocol.md
@.codex/rules/20-tests-determinism.md
@.codex/rules/30-tooling-tasks.md
